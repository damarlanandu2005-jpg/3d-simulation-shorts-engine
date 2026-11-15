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
    SUPPORTED_OBJECTS,
    CameraCfg,
    Config,
    ConfigError,
    PhysicsCfg,
    faces_to_segments,
    load_config,
)

SCHEMA_VERSION = 2
# Roadmap names that are NOT implemented: used only to give a clearer error, never listed as supported.
PLANNED_EXPERIMENTS = ("cloth_drop", "multiple_balls", "ball_drop", "ball_funnel", "rings", "paper_drape",
                       "paper_collision", "softbody_collision", "rope_collision", "particle_flow")


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path} must be a number, got {value!r}")
    if positive and value <= 0:
        raise ConfigError(f"{path} must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class ParamSpec:
    """One experiment-level parameter and where it lands in ``Config``."""
    config_path: tuple[str, str]           # (section, field) in Config, e.g. ("object", "cloth_size")
    check: Callable[[Any, str], Any]
    description: str = ""


@dataclass(frozen=True)
class ExperimentType:
    name: str
    description: str
    simulation: str                          # Config.simulation / key into simulation.SIMULATORS
    objects: tuple[str, ...]                 # allowed values of experiment.object
    params: dict = field(default_factory=dict)         # experiment.params: name -> ParamSpec
    stage_params: dict = field(default_factory=dict)   # stages[].params: name -> validator(value, path)
    stage_meaning: str = ""


def _check_faces(value: Any, path: str) -> int:
    try:
        faces_to_segments(value)
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return value


EXPERIMENT_TYPES: dict[str, ExperimentType] = {
    "cloth_drape": ExperimentType(
        name="cloth_drape",
        description="A cloth sheet is dropped onto an object; stages repeat it at different mesh resolutions.",
        simulation="cloth",
        objects=SUPPORTED_OBJECTS,
        params={
            "cloth_size": ParamSpec(("object", "cloth_size"), lambda v, p: _number(v, p, positive=True),
                                    "side length of the square cloth sheet (metres)"),
            "drop_height": ParamSpec(("object", "cloth_drop_height"), lambda v, p: _number(v, p, positive=True),
                                     "height of the sheet above the top of the object (metres)"),
        },
        stage_params={"faces": _check_faces},
        stage_meaning="mesh resolution: number of cloth faces (a perfect square, e.g. 64, 1024, 4096, 16384)",
    ),
}

EXPERIMENT_FOR_SIMULATION = {t.simulation: t.name for t in EXPERIMENT_TYPES.values()}

_TOP_KEYS = {"schema_version", "name", "seed", "experiment", "simulation", "stages", "camera", "material",
             "render", "output", "label", "hook", "video", "audio"}
_EXPERIMENT_KEYS = {"type", "object", "params"}
_SIMULATION_KEYS = {"fps", "duration", "physics"}
_STAGE_KEYS = {"params", "camera"}
_HOOK_KEYS = {"seconds", "mode", "text", "text_size", "text_y", "closeup"}
_VIDEO_KEYS = {"crf", "cards"}
_CAMERA_KEYS = {"distance", "height", "target_z", "focal_length"}
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


def get_experiment_type(name: Any) -> ExperimentType:
    if not isinstance(name, str) or not name:
        raise ConfigError(f"experiment.type must be a non-empty string, got {name!r}")
    if name in EXPERIMENT_TYPES:
        return EXPERIMENT_TYPES[name]
    hint = " (it is on the roadmap but not implemented yet)" if name in PLANNED_EXPERIMENTS else ""
    raise ConfigError(f"experiment type {name!r} is not available{hint}; supported: {sorted(EXPERIMENT_TYPES)}")


# ------------------------------------------------------------------ new format -> flat Config dict
def experiment_to_legacy(data: dict) -> dict:
    """Validate the experiment-format dict and translate it to the flat dict ``Config`` is built from."""
    data = _obj(data, "<config>")
    _only(data, _TOP_KEYS, "<config>")
    if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ConfigError(f"schema_version must be {SCHEMA_VERSION}, got {data['schema_version']!r}")
    for required in ("experiment", "stages"):
        if required not in data:
            raise ConfigError(f"'{required}' is required in the experiment format")

    # experiment
    exp = _obj(data["experiment"], "experiment")
    _only(exp, _EXPERIMENT_KEYS, "experiment")
    etype = get_experiment_type(exp.get("type"))
    obj = exp.get("object", "sphere")
    if obj not in etype.objects:
        raise ConfigError(f"experiment.object {obj!r} is not valid for {etype.name}; allowed: {list(etype.objects)}")
    params = _obj(exp.get("params", {}), "experiment.params")
    _only(params, set(etype.params), "experiment.params")
    out: dict = {"simulation": etype.simulation, "object": {"type": obj}}
    for pname, value in params.items():
        spec = etype.params[pname]
        section, key = spec.config_path
        out.setdefault(section, {})[key] = spec.check(value, f"experiment.params.{pname}")

    # simulation
    sim = _obj(data.get("simulation", {}), "simulation")
    _only(sim, _SIMULATION_KEYS, "simulation")
    for key in ("fps", "duration"):
        if key in sim:
            out[key] = _number(sim[key], f"simulation.{key}", positive=True)
    if "physics" in sim:
        physics = _obj(sim["physics"], "simulation.physics")
        _only(physics, {f.name for f in fields(PhysicsCfg)}, "simulation.physics")
        out["physics"] = dict(physics)

    # stages
    stages = data["stages"]
    if not isinstance(stages, list) or not stages:
        raise ConfigError("stages must be a non-empty list")
    stage_values: dict[str, list] = {name: [] for name in etype.stage_params}
    cameras: list[dict] = []
    for i, st in enumerate(stages):
        path = f"stages[{i}]"
        st = _obj(st, path)
        _only(st, _STAGE_KEYS, path)
        sp = _obj(st.get("params", {}), f"{path}.params")
        _only(sp, set(etype.stage_params), f"{path}.params")
        for name, check in etype.stage_params.items():
            if name not in sp:
                raise ConfigError(f"{path}.params.{name} is required for {etype.name} ({etype.stage_meaning})")
            stage_values[name].append(check(sp[name], f"{path}.params.{name}"))
        cam = _obj(st.get("camera", {}), f"{path}.camera")
        _only(cam, set(_CAMERA_OVERRIDE_KEYS), f"{path}.camera")
        for key, value in cam.items():
            _number(value, f"{path}.camera.{key}", positive=key in ("distance", "focal_length"))
        cameras.append(dict(cam))
    out["resolutions"] = stage_values["faces"]          # cloth_drape's stage parameter (Config's historical name)
    while cameras and not cameras[-1]:                  # trailing empty overrides mean "use the base camera"
        cameras.pop()

    # camera
    camera = _obj(data.get("camera", {}), "camera")
    if "per_stage" in camera:
        raise ConfigError("camera.per_stage is not used in the experiment format; put overrides in stages[].camera")
    _only(camera, _CAMERA_KEYS, "camera")
    if camera or cameras:
        out["camera"] = dict(camera)
        if cameras:
            out["camera"]["per_stage"] = cameras

    # hook / video
    video = _obj(data.get("video", {}), "video")
    if "hook" in video or "hook_seconds" in video:
        raise ConfigError("video.hook / video.hook_seconds are not used in the experiment format; use the top-level 'hook'")
    _only(video, _VIDEO_KEYS, "video")
    out_video = dict(video)
    if "hook" in data:
        hook = dict(_obj(data["hook"], "hook"))
        _only(hook, _HOOK_KEYS, "hook")
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
    return out


# ------------------------------------------------------------------ Config -> new format (migration / describe)
def to_experiment_dict(cfg: Config) -> dict:
    """Express a resolved ``Config`` in the experiment format (complete and explicit)."""
    etype = get_experiment_type(EXPERIMENT_FOR_SIMULATION.get(cfg.simulation))
    d = asdict(cfg)
    per_stage = [dict(c) for c in d["camera"]["per_stage"]]
    stages = []
    for i, faces in enumerate(cfg.resolutions):
        stage: dict = {"params": {"faces": faces}}
        if i < len(per_stage) and per_stage[i]:
            stage["camera"] = per_stage[i]
        stages.append(stage)
    hook = dict(d["video"]["hook"])
    hook["seconds"] = d["video"]["hook_seconds"]
    return {
        "schema_version": SCHEMA_VERSION,
        "name": cfg.name,
        "seed": cfg.seed,
        "experiment": {"type": etype.name, "object": cfg.object.type,
                       "params": {"cloth_size": cfg.object.cloth_size, "drop_height": cfg.object.cloth_drop_height}},
        "simulation": {"fps": cfg.fps, "duration": cfg.duration, "physics": d["physics"]},
        "stages": stages,
        "camera": {k: v for k, v in d["camera"].items() if k != "per_stage"},
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
    """The experiment-level view of a config (what Phase 3's templates will consume)."""
    type: str
    object: str
    params: dict
    stages: list


def describe(cfg: Config) -> ExperimentSpec:
    etype = get_experiment_type(EXPERIMENT_FOR_SIMULATION.get(cfg.simulation))
    stages = [StageSpec(i, {"faces": f}, {k: v for k, v in
                                          (cfg.camera.per_stage[i] if i < len(cfg.camera.per_stage) else {}).items()})
              for i, f in enumerate(cfg.resolutions)]
    return ExperimentSpec(etype.name, cfg.object.type,
                          {"cloth_size": cfg.object.cloth_size, "drop_height": cfg.object.cloth_drop_height}, stages)


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
                print(f"{t.name}: {t.description}\n  objects: {', '.join(t.objects)}\n  stage parameter: {t.stage_meaning}")
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
