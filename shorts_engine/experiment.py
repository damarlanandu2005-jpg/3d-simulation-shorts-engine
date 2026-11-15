"""General experiment schema (v2) <-> the engine's resolved ``Config``.

Pure Python (never imports bpy). The engine keeps using ``Config`` everywhere; this module adds a cleaner,
experiment-oriented way to *write* configs and translates it into ``Config``:

    experiment (type, object, params)   what physical question is being asked
    simulation (fps, duration, physics) how it is simulated
    stages [{params, camera}]           the progression shown in the video (for cloth_drape: mesh resolution)
    camera / render / material / output / label / hook / video / audio   as before

The old flat format (``"simulation": "cloth"``, ``"resolutions": [...]``) still loads unchanged; ``experiment`` in the
file selects the new format. Both resolve to the same ``Config`` (see tests: the V1.1 production reference is
identical in both formats). New experiment types register an ``ExperimentType`` here; only types whose Blender
simulation exists and is tested are registered (today: ``cloth_drape``).

    python -m shorts_engine.experiment list
    python -m shorts_engine.experiment describe CONFIG
    python -m shorts_engine.experiment migrate CONFIG      # print CONFIG in the new format
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

from .config import (
    CameraCfg,
    Config,
    ConfigError,
    ExperimentConfig,
    PhysicsCfg,
    load_config,
)
from .templates import TEMPLATES, ExperimentTemplate, get_template

SCHEMA_VERSION = 2
# Roadmap names that are NOT implemented: used only to give a clearer error, never listed as supported.
PLANNED_EXPERIMENTS = ("cloth_drop", "ball_drop", "paper_drape", "paper_collision", "softbody_collision",
                       "rope_collision", "particle_flow", "pendulum", "domino_chain")

# the registry of everything this engine can generate (see templates.py)
EXPERIMENT_TYPES: dict[str, ExperimentTemplate] = TEMPLATES
ExperimentType = ExperimentTemplate
EXPERIMENT_FOR_SIMULATION = {"cloth": "cloth_drape"}      # legacy flat configs are always the V1 cloth drape


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path} must be a number, got {value!r}")
    if positive and value <= 0:
        raise ConfigError(f"{path} must be > 0, got {value}")
    return value


_TOP_KEYS = {"schema_version", "name", "seed", "experiment", "simulation", "stages", "camera", "material",
             "render", "output", "label", "hook", "video", "audio"}
_EXPERIMENT_KEYS = {"type", "object", "params"}
_SIMULATION_KEYS = {"fps", "duration", "physics"}
_STAGE_KEYS = {"params", "camera"}
_HOOK_KEYS = {"seconds", "mode", "text", "text_size", "text_y", "closeup", "window"}
_VIDEO_KEYS = {"crf", "cards"}
_CAMERA_KEYS = {"distance", "height", "target_z", "focal_length", "preset", "motion"}
_CAMERA_OVERRIDE_KEYS = ("distance", "height", "target_z", "focal_length")
_PASSTHROUGH = ("material", "render", "output", "label", "audio")


def _obj(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"'{path}' must be an object, got {type(value).__name__}")
    return value


def _only(data: dict, allowed: set, path: str) -> None:
    bad = set(data) - allowed
    if bad:
        raise ConfigError(f"unknown key(s) in '{path}': {sorted(bad)}; allowed: {sorted(allowed)}")


get_experiment_type = get_template


# ------------------------------------------------------------------ new format -> flat Config dict
def experiment_to_legacy(data: dict) -> dict:
    """Validate the experiment-format dict and translate it to the flat dict a ``Config`` is built from.

    ``cloth_drape`` translates to the V1 flat format (so it stays byte-identical to the V1.1 reference). Every other
    experiment produces a dict with an ``experiment`` key, which ``from_dict`` builds as an ``ExperimentConfig``.
    """
    data = _obj(data, "<config>")
    _only(data, _TOP_KEYS, "<config>")
    if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ConfigError(f"schema_version must be {SCHEMA_VERSION}, got {data['schema_version']!r}")
    for required in ("experiment", "stages"):
        if required not in data:
            raise ConfigError(f"'{required}' is required in the experiment format")

    exp = _obj(data["experiment"], "experiment")
    _only(exp, _EXPERIMENT_KEYS, "experiment")
    t = get_template(exp.get("type"))
    generic = t.name != "cloth_drape"
    obj = exp.get("object", t.default_object)
    if obj not in t.objects:
        raise ConfigError(f"experiment.object {obj!r} is not valid for {t.name}; allowed: {list(t.objects)}")
    given = _obj(exp.get("params", {}), "experiment.params")
    _only(given, set(t.params), "experiment.params")
    resolved = t.resolve_params(given)
    out: dict = {"simulation": t.simulation}

    if generic:
        out.update(experiment=t.name, shape=obj, params=resolved)
        out["object"] = {"type": obj if obj in ("sphere", "cube", "cylinder", "torus", "cone") else "sphere"}
        if "cloth_size" in resolved:
            out["object"].update(cloth_size=resolved["cloth_size"], cloth_drop_height=resolved["drop_height"])
    else:
        out["object"] = {"type": obj}
        for pname in given:                                  # V1 behaviour: only explicitly given values are written
            section, key = {"cloth_size": ("object", "cloth_size"), "drop_height": ("object", "cloth_drop_height")}[pname]
            out.setdefault(section, {})[key] = resolved[pname]

    sim = _obj(data.get("simulation", {}), "simulation")
    _only(sim, _SIMULATION_KEYS, "simulation")
    for key in ("fps", "duration"):
        if key in sim:
            out[key] = _number(sim[key], f"simulation.{key}", positive=True)
    if "physics" in sim:
        physics = _obj(sim["physics"], "simulation.physics")
        _only(physics, {f.name for f in fields(PhysicsCfg)}, "simulation.physics")
        out["physics"] = dict(physics)

    stages = data["stages"]
    if not isinstance(stages, list) or not stages:
        raise ConfigError("stages must be a non-empty list")
    values: list = []
    cameras: list[dict] = []
    for i, st in enumerate(stages):
        path = f"stages[{i}]"
        st = _obj(st, path)
        _only(st, _STAGE_KEYS, path)
        sp = _obj(st.get("params", {}), f"{path}.params")
        _only(sp, {t.stage_param}, f"{path}.params")
        if t.stage_param not in sp:
            raise ConfigError(f"{path}.params.{t.stage_param} is required for {t.name} ({t.stage_meaning})")
        values.append(t.check_stage_value(sp[t.stage_param], f"{path}.params.{t.stage_param}"))
        cam = _obj(st.get("camera", {}), f"{path}.camera")
        _only(cam, set(_CAMERA_OVERRIDE_KEYS), f"{path}.camera")
        for key, value in cam.items():
            _number(value, f"{path}.camera.{key}", positive=key in ("distance", "focal_length"))
        cameras.append(dict(cam))
    if generic:
        out["stage_values"] = values
    else:
        out["resolutions"] = values
    while cameras and not cameras[-1]:                       # trailing empty overrides mean "use the base camera"
        cameras.pop()

    camera = dict(_obj(data.get("camera", {}), "camera"))
    if "per_stage" in camera:
        raise ConfigError("camera.per_stage is not used in the experiment format; put overrides in stages[].camera")
    _only(camera, _CAMERA_KEYS, "camera")
    for key in ("preset", "motion"):
        if key in camera:
            if not generic:
                raise ConfigError(f"camera.{key} is only available for the newer experiments, not {t.name}")
            out[f"camera_{key}"] = camera.pop(key)
    if camera or cameras:
        out["camera"] = camera
        if cameras:
            out["camera"]["per_stage"] = cameras

    video = _obj(data.get("video", {}), "video")
    if "hook" in video or "hook_seconds" in video:
        raise ConfigError("video.hook / video.hook_seconds are not used in the experiment format; use the top-level 'hook'")
    _only(video, _VIDEO_KEYS, "video")
    out_video = dict(video)
    if "hook" in data:
        hook = dict(_obj(data["hook"], "hook"))
        _only(hook, _HOOK_KEYS, "hook")
        if "window" in hook:
            if not generic:
                raise ConfigError(f"hook.window is only available for the newer experiments, not {t.name}")
            out["hook_window"] = hook.pop("window")
        if "seconds" in hook:
            out_video["hook_seconds"] = _number(hook.pop("seconds"), "hook.seconds", positive=True)
        out_video["hook"] = hook
    if out_video:
        out["video"] = out_video

    for key in ("name", "seed"):
        if key in data:
            out[key] = data[key]
    for key in _PASSTHROUGH:
        if key in data:
            out[key] = dict(_obj(data[key], key))
    if generic:                                              # experiment-specific defaults the file did not set
        out.setdefault("label", {}).setdefault("template", t.label)
        if "size" not in out["label"]:                       # long labels shrink so they stay inside the 9:16 frame
            longest = max(len(t.label.format(**{**resolved, t.stage_param: v, **t.label_values(resolved, v)}))
                          if out["label"]["template"] == t.label else 0 for v in values)
            if longest > 13:
                out["label"]["size"] = round(0.2 * 13 / longest, 3)
        out["camera_preset"] = out.get("camera_preset", "wide")
        out.setdefault("hook_window", "start" if t.simulation == "rigid_body" else "end")
        out_video = out.setdefault("video", {})
        out_video.setdefault("hook", {}).setdefault("mode", "closeup")
        out_video["hook"].setdefault("text", "auto")
        out_video.setdefault("hook_seconds", 2.0)
        hook_closeup = out_video["hook"].setdefault("closeup", {})
        if not hook_closeup:
            last = t.frame_region(resolved, values[-1])
            from .camera_rig import fit_camera
            fit = fit_camera(last.half_width, last.top, last.bottom, "close", out.get("camera", {}).get("focal_length", 50.0),
                             elevation=t.camera_defaults.get("elevation"))
            hook_closeup.update(distance_start=round(fit["distance"] * 1.25, 3), distance_end=fit["distance"],
                                height=fit["height"], target_z=fit["target_z"])
    return out


# ------------------------------------------------------------------ Config -> new format (migration / describe)
def to_experiment_dict(cfg: Config) -> dict:
    """Express a resolved config in the experiment format (complete and explicit)."""
    t = get_template(cfg.experiment_type)
    d = asdict(cfg)
    per_stage = [dict(c) for c in d["camera"]["per_stage"]]
    generic = isinstance(cfg, ExperimentConfig)
    values = list(cfg.stage_values) if generic else list(cfg.resolutions)
    stages = []
    for i, v in enumerate(values):
        stage: dict = {"params": {t.stage_param: v}}
        if i < len(per_stage) and per_stage[i]:
            stage["camera"] = per_stage[i]
        stages.append(stage)
    hook = dict(d["video"]["hook"])
    hook["seconds"] = d["video"]["hook_seconds"]
    camera = {k: v for k, v in d["camera"].items() if k != "per_stage"}
    if generic:
        camera.update(preset=cfg.camera_preset, motion=cfg.camera_motion)
        hook["window"] = cfg.hook_window
        params, shape = dict(cfg.params), cfg.shape
    else:
        params, shape = {"cloth_size": cfg.object.cloth_size, "drop_height": cfg.object.cloth_drop_height}, cfg.object.type
    return {
        "schema_version": SCHEMA_VERSION,
        "name": cfg.name,
        "seed": cfg.seed,
        "experiment": {"type": t.name, "object": shape, "params": params},
        "simulation": {"fps": cfg.fps, "duration": cfg.duration, "physics": d["physics"]},
        "stages": stages,
        "camera": camera,
        "material": d["material"],
        "render": d["render"],
        "output": d["output"],
        "label": d["label"],
        "hook": hook,
        "video": {"crf": d["video"]["crf"], "cards": d["video"]["cards"]},
        "audio": d["audio"],
    }


@dataclass
class StageSpec:
    index: int
    params: dict
    camera: dict


@dataclass
class ExperimentSpec:
    """The experiment-level view of a config."""
    type: str
    object: str
    params: dict
    stages: list


def describe(cfg: Config) -> ExperimentSpec:
    t = get_template(cfg.experiment_type)
    d = to_experiment_dict(cfg)
    stages = [StageSpec(i, st["params"], st.get("camera", {})) for i, st in enumerate(d["stages"])]
    return ExperimentSpec(t.name, d["experiment"]["object"], d["experiment"]["params"], stages)


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shorts_engine.experiment")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="experiment types this engine can generate")
    d = sub.add_parser("describe", help="show the experiment-level view of a config")
    d.add_argument("config")
    m = sub.add_parser("migrate", help="print a config in the experiment format")
    m.add_argument("config")
    args = p.parse_args(argv)
    try:
        if args.cmd == "list":
            for t in EXPERIMENT_TYPES.values():
                print(f"{t.name}: {t.description}\n  objects: {', '.join(t.objects)}\n"
                      f"  stage parameter: {t.stage_param} - {t.stage_meaning}\n"
                      f"  parameters: {', '.join(f'{k}={d.default}' for k, d in t.params.items())}")
        elif args.cmd == "describe":
            spec = describe(load_config(args.config))
            print(json.dumps(asdict(spec), indent=1))
        else:
            print(json.dumps(to_experiment_dict(load_config(args.config)), indent=1))
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
