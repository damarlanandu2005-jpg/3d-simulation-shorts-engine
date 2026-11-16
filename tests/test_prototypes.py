"""The three creative prototypes (roll_off, sheet_reveal, jar_packing): config, template and camera rules (pure Python)."""
import json
from pathlib import Path

import pytest

from shorts_engine.camera_rig import fit_camera
from shorts_engine.config import ConfigError, load_config
from shorts_engine.templates import (RACE_SHAPES, TEMPLATES, get_template, jar_pours, race_geometry)

ROOT = Path(__file__).resolve().parent.parent
PROTOS = sorted((ROOT / "configs" / "prototypes").glob("*.json"))


def test_prototype_configs_load():
    assert {p.stem for p in PROTOS} == {"roll_off", "sheet_reveal", "jar_packing"}
    for p in PROTOS:
        cfg = load_config(p)
        assert cfg.stage_count >= 1 and cfg.output.width == 720


def test_templates_registered_with_story_question_hooks():
    for name, hook in (("roll_off", "WHICH ONE WINS?"), ("sheet_reveal", "WHAT'S UNDER THE SHEET?"),
                       ("jar_packing", "IS THE JAR REALLY FULL?")):
        assert get_template(name).hooks == (hook,)
    assert len(RACE_SHAPES) == 6 and len(set(RACE_SHAPES)) == 6


def test_race_region_is_deeper_than_wide_and_camera_fits_it():
    t = get_template("roll_off")
    region = t.frame_region(t.resolve_params({}), 17.0)
    assert region.half_depth > region.half_width            # the ramp runs away from the camera
    square = fit_camera(region.half_width, region.top, 0.0, "wide", 50.0, elevation=68.0)
    deep = fit_camera(region.half_width, region.top, 0.0, "wide", 50.0, elevation=68.0, half_depth=region.half_depth)
    assert deep["distance"] > square["distance"]            # a deeper region needs the camera further away


def test_race_geometry():
    g = race_geometry({"incline": 30.0, "lane_width": 1.0, "ramp_length": 10.0})
    assert g["width"] == 6.0 and abs(g["rise"] - 5.0) < 1e-6


@pytest.mark.parametrize("exp,params,msg", [
    ("roll_off", {"lane_width": 0.6}, "lane_width"),
    ("jar_packing", {"n_tiny": 3000, "n_small": 1500, "n_medium": 600}, "jar holds only"),
    ("jar_packing", {"big_radius": 0.9}, "too large"),
    ("sheet_reveal", {"cloth_size": 3.0}, "too small"),
])
def test_broken_scenes_are_rejected(exp, params, msg):
    t = get_template(exp)
    stage = {"roll_off": 17.0, "sheet_reveal": "snowman", "jar_packing": 4}[exp]
    with pytest.raises(ConfigError, match=msg):
        t.validate(t.resolve_params(params), [stage], "x")


def test_jar_pours_get_smaller():
    radii = [r for r, _ in jar_pours(get_template("jar_packing").resolve_params({}))]
    assert radii == sorted(radii, reverse=True) and radii[1] <= 0.42 * radii[0] + 1e-9


def test_sheet_reveal_hook_window_clue_precedes_the_reveal():
    cfg = load_config(ROOT / "configs" / "prototypes" / "sheet_reveal.json")
    first, last = cfg.hook_frame_range()
    reveal = round(cfg.params["reveal_start"] * cfg.fps)
    assert last < reveal and last - first + 1 == round(cfg.video.hook_seconds * cfg.fps)


def test_clue_window_only_for_experiments_with_a_reveal():
    data = json.loads((ROOT / "configs" / "prototypes" / "roll_off.json").read_text())
    data["hook"] = {"mode": "closeup", "window": "clue"}
    with pytest.raises(ConfigError, match="clue"):
        from shorts_engine.config import from_dict
        from_dict(data)


def test_frictionless_second_heat_is_allowed_per_stage():
    cfg = load_config(ROOT / "configs" / "prototypes" / "roll_off.json")
    assert cfg.stage_params(1)["ramp_friction"] == 0.0 and cfg.stage_params(0)["ramp_friction"] > 0


def test_new_templates_are_in_the_registry_only_once():
    assert {"roll_off", "sheet_reveal", "jar_packing"} <= set(TEMPLATES)
