"""Phase 2: the general experiment configuration (schema v2), validation and backward compatibility."""
import copy
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import update_golden  # noqa: E402

from shorts_engine import experiment, render  # noqa: E402
from shorts_engine.config import ConfigError, from_dict, load_config  # noqa: E402

LEGACY = ROOT / "configs" / "v1_1_a_baseline.json"
V2 = ROOT / "configs" / "experiments" / "cloth_drape_reference.json"
GOLDEN = ROOT / "tests" / "golden"
ALL_CONFIGS = sorted((ROOT / "configs").glob("*.json")) + [V2]


def v2_data():
    return json.loads(V2.read_text(encoding="utf-8"))


def bad(mutate, match):
    data = v2_data()
    mutate(data)
    with pytest.raises(ConfigError, match=match):
        from_dict(data)


# ------------------------------------------------------------------ valid configs / compatibility
def test_new_format_reference_resolves_to_the_phase1_golden_config():
    golden = json.loads((GOLDEN / "reference_config.json").read_text())
    assert asdict(load_config(V2)) == golden


def test_legacy_reference_still_resolves_to_the_phase1_golden_config():
    golden = json.loads((GOLDEN / "reference_config.json").read_text())
    assert asdict(load_config(LEGACY)) == golden


def test_both_formats_give_identical_configs_and_plans():
    assert load_config(V2) == load_config(LEGACY)
    golden_plan = json.loads((GOLDEN / "reference_plan.json").read_text())
    for path in (LEGACY, V2):
        assert update_golden.reference_plan_summary(load_config(path), str(path)) == golden_plan


def test_phase1_reference_facts_hold_in_the_new_format():
    cfg = load_config(V2)
    assert (cfg.output.width, cfg.output.height, cfg.fps) == (720, 1280, 30)
    assert [s.label for s in cfg.stages()] == ["64 FACES", "1,024 FACES", "4,096 FACES", "16,384 FACES"]
    assert cfg.video.hook.mode == "closeup" and not cfg.video.cards.enabled and cfg.cards() == []
    assert cfg.audio.enabled and cfg.audio.sfx_enabled
    jobs = render.plan_jobs(cfg, str(V2), ["blender"], True)
    kinds = [j.kind for j in jobs]
    assert kinds[:8] == ["bake", "render"] * 4 and kinds[-2:] == ["concat", "audio"]


@pytest.mark.parametrize("path", ALL_CONFIGS, ids=lambda p: p.name)
def test_every_shipped_config_loads_and_has_an_experiment_type(path):
    cfg = load_config(path)
    assert cfg.experiment_type == "cloth_drape"
    assert "experiment_type" not in asdict(cfg)          # derived, so the serialised config (golden) is unchanged


@pytest.mark.parametrize("path", ALL_CONFIGS, ids=lambda p: p.name)
def test_migration_round_trip_preserves_the_effective_config(path):
    cfg = load_config(path)
    again = from_dict(experiment.to_experiment_dict(cfg))
    assert [again.camera_for_stage(i) for i in range(len(cfg.resolutions))] == \
           [cfg.camera_for_stage(i) for i in range(len(cfg.resolutions))]
    norm = lambda c: asdict(replace(c, camera=replace(c.camera, per_stage=[])))  # noqa: E731
    assert norm(again) == norm(cfg)                        # everything except trailing-empty camera overrides


def test_describe_is_the_same_for_both_formats():
    a, b = experiment.describe(load_config(LEGACY)), experiment.describe(load_config(V2))
    assert a == b and a.type == "cloth_drape" and a.object == "sphere"
    assert [s.params["faces"] for s in a.stages] == [64, 1024, 4096, 16384]
    assert a.stages[1].camera == {"distance": 10.4} and a.stages[0].camera == {}


def test_minimal_new_format_config_uses_the_defaults():
    cfg = from_dict({"experiment": {"type": "cloth_drape"}, "stages": [{"params": {"faces": 64}}]})
    assert cfg.simulation == "cloth" and cfg.object.type == "sphere" and cfg.resolutions == [64]
    assert cfg.camera.per_stage == []


def test_cli_list_describe_migrate(capsys):
    assert experiment.main(["list"]) == 0
    assert "cloth_drape" in capsys.readouterr().out
    assert experiment.main(["describe", str(LEGACY)]) == 0
    assert json.loads(capsys.readouterr().out)["type"] == "cloth_drape"
    assert experiment.main(["migrate", str(LEGACY)]) == 0
    assert from_dict(json.loads(capsys.readouterr().out)).name == "v1_1_a"
    assert experiment.main(["describe", str(ROOT / "nope.json")]) == 1


# ------------------------------------------------------------------ invalid experiment type / object
@pytest.mark.parametrize("name", ["banana", "", None, 5, "Cloth_Drape"])
def test_invalid_experiment_types(name):
    bad(lambda d: d["experiment"].update(type=name), "experiment type|experiment.type")


@pytest.mark.parametrize("name", ["paper_drape", "pendulum", "softbody_collision", "rope_collision"])
def test_roadmap_experiments_are_not_pretended_to_exist(name):
    bad(lambda d: d["experiment"].update(type=name), "not implemented yet")
    assert name not in experiment.EXPERIMENT_TYPES


def test_missing_experiment_type_or_stages():
    bad(lambda d: d["experiment"].pop("type"), "experiment.type")
    bad(lambda d: d.pop("stages"), "'stages' is required")
    bad(lambda d: d.pop("experiment"), "'experiment' is required|experiment")


@pytest.mark.parametrize("obj", ["pyramid", "", None, 3])
def test_invalid_object_types(obj):
    bad(lambda d: d["experiment"].update(object=obj), "experiment.object")


def test_unknown_experiment_params_and_keys():
    bad(lambda d: d["experiment"]["params"].update(ball_count=10), "unknown key.*experiment.params")
    bad(lambda d: d["experiment"].update(speed=3), "unknown key.*'experiment'")


# ------------------------------------------------------------------ invalid stage definitions
@pytest.mark.parametrize("stages", [[], "64", None, {"params": {"faces": 64}}])
def test_stages_must_be_a_non_empty_list(stages):
    bad(lambda d: d.update(stages=stages), "stages must be a non-empty list")


def test_invalid_stage_entries():
    bad(lambda d: d.update(stages=[64, 1024]), r"stages\[0\]")
    bad(lambda d: d.update(stages=[{}]), r"stages\[0\]\.params\.faces is required")
    bad(lambda d: d["stages"][1].update(colour="red"), r"unknown key.*stages\[1\]")
    bad(lambda d: d["stages"][1]["params"].update(balls=3), r"unknown key.*stages\[1\]\.params")


@pytest.mark.parametrize("faces", [0, 3, 99, -64, 64.0, "64", True, None])
def test_invalid_stage_face_counts(faces):
    bad(lambda d: d["stages"][2]["params"].update(faces=faces), r"stages\[2\]\.params\.faces")


@pytest.mark.parametrize("cam", [{"distance": 0}, {"distance": -3}, {"distance": "far"}, {"zoom": 2}, {"focal_length": 0}])
def test_invalid_stage_camera_overrides(cam):
    bad(lambda d: d["stages"][1].update(camera=cam), r"stages\[1\]\.camera")


def test_per_stage_camera_and_video_hook_belong_to_the_legacy_format_only():
    bad(lambda d: d["camera"].update(per_stage=[{}]), "stages\\[\\]\\.camera")
    bad(lambda d: d["video"].update(hook={}), "top-level 'hook'")
    bad(lambda d: d["video"].update(hook_seconds=2), "top-level 'hook'")


# ------------------------------------------------------------------ invalid simulation parameters
@pytest.mark.parametrize("key,value", [("gravity", 0), ("gravity", -9.8), ("gravity", 1000), ("mass", 0), ("mass", "heavy"),
                                       ("tension", -1), ("compression", 0), ("shear", 0), ("bending", -0.1),
                                       ("air_damping", -1), ("quality", 0), ("quality", 2.5),
                                       ("collision_distance", 0), ("collision_distance", 5)])
def test_invalid_physics_parameters(key, value):
    bad(lambda d: d["simulation"].update(physics={key: value}), f"physics.{key}")


@pytest.mark.parametrize("key,value", [("fps", 0), ("fps", 500), ("duration", 0), ("duration", -1), ("duration", 99),
                                       ("fps", "fast")])
def test_invalid_fps_and_duration(key, value):
    bad(lambda d: d["simulation"].update({key: value}), "fps|duration")


def test_invalid_simulation_keys_and_experiment_params():
    bad(lambda d: d["simulation"].update(wind=3), "unknown key.*'simulation'")
    bad(lambda d: d["simulation"].update(physics={"stiffness": 3}), "unknown key.*simulation.physics")
    bad(lambda d: d["experiment"]["params"].update(cloth_size=0), "cloth_size")
    bad(lambda d: d["experiment"]["params"].update(drop_height=-1), "drop_height")
    bad(lambda d: d.update(seed=-1), "seed")
    bad(lambda d: d.update(seed=1.5), "seed")


def test_invalid_simulation_parameters_in_the_legacy_format_too():
    data = json.loads(LEGACY.read_text())
    for path, value, match in [(("physics",), {"gravity": 0}, "physics.gravity"),
                               (("object",), {"type": "sphere", "cloth_size": -1}, "cloth_size"),
                               (("object",), {"type": "pyramid"}, "object.type")]:
        d = copy.deepcopy(data)
        d[path[0]] = value
        with pytest.raises(ConfigError, match=match):
            from_dict(d)
    d = copy.deepcopy(data)
    d["simulation"] = "softbody"
    with pytest.raises(ConfigError, match="not implemented"):
        from_dict(d)


# ------------------------------------------------------------------ invalid render / output settings
@pytest.mark.parametrize("section,update,match", [
    ("render", {"engine": "EEVEE"}, "render.engine"),
    ("render", {"device": "TPU"}, "render.device"),
    ("render", {"samples": 0}, "render.samples"),
    ("render", {"denoiser": "MAGIC"}, "render.denoiser"),
    ("render", {"max_bounces": -1}, "max_bounces"),
    ("output", {"width": 721}, "even"),
    ("output", {"width": 1280, "height": 720}, "vertical"),
    ("output", {"width": 8, "height": 16}, "too small"),
    ("label", {"template": "{nope}"}, "label.template"),
    ("render", {"quality": 3}, "unknown key"),
])
def test_invalid_render_and_output_settings(section, update, match):
    bad(lambda d: d[section].update(update), match)


def test_unknown_top_level_key_and_schema_version():
    bad(lambda d: d.update(balls=5), "unknown key.*<config>")
    bad(lambda d: d.update(schema_version=3), "schema_version")
    bad(lambda d: d.update(name="has space"), "name")
