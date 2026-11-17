"""Real Blender tests of the three prototypes: the physical outcome is asserted, not just that it ran."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from shorts_engine.config import load_config
from tests.test_experiments_blender import gen

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(importlib.util.find_spec("bpy") is None, reason="bpy not installed")

READ_MARKERS = ("import bpy, json, sys\nbpy.ops.wm.open_mainfile(filepath=sys.argv[1])\n"
                "print('MARK ' + bpy.context.scene['sim_markers'])\n")


def small_cfg(tmp_path, name, duration, **params):
    d = json.loads((ROOT / "configs" / "prototypes" / f"{name}.json").read_text())
    d["simulation"] = {"fps": 30, "duration": duration}
    d["experiment"]["params"] = params
    d["render"] = {"samples": 2, "device": "CPU", "denoise": False}
    d["output"] = {"width": 90, "height": 160, "dir": str(tmp_path)}
    d["audio"] = {"enabled": True, "music_enabled": True, "sfx_enabled": True}
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(d))
    return p, load_config(p)


def markers(blend):
    out = subprocess.run([sys.executable, "-c", READ_MARKERS, str(blend)], capture_output=True, text=True, timeout=300).stdout
    return json.loads([l for l in out.splitlines() if l.startswith("MARK ")][0][5:])


def test_roll_off_is_a_real_shared_race(tmp_path):
    p, cfg = small_cfg(tmp_path, "roll_off", 16.5)
    gen(p, "--stage", "0", "--mode", "build")
    m = markers(cfg.stages()[0].blend_path)
    assert m["winner"] == "sphere" and not m["still_moving"]
    d = m["distances_m"]
    assert d["sphere"] > d["ring"] > d["cube"]                       # rolling beats rolling-with-wobble beats tumbling
    assert d["sphere"] - d["cube"] > 4.0                            # a real spread, not a dead heat
    assert m["order"][0] in ("sphere", "can") and m["order"][-1] in ("cube", "prism", "cone")
    assert len(m["camera_path"]) == cfg.frame_count                 # a camera path was planned for every frame
    assert m["label_schedule"][1][1].endswith("WINS!")


def test_jar_packing_fills_gaps_without_spilling(tmp_path):
    p, cfg = small_cfg(tmp_path, "jar_packing", 19.5)
    gen(p, "--stage", "0", "--mode", "build")
    m = markers(cfg.stages()[0].blend_path)
    assert m["outside_jar"] == 0 and m["above_rim"] <= 6
    levels = m["fill_levels"]
    # the jar looks full after the large rocks; the later pours fit in the gaps and the level never climbs far past the rim
    assert len(levels) == 4 and max(levels) - levels[0] < 0.3 and max(levels) < 2.2 + 0.35
    assert m["added"] == 36 + 110 + 260 and m["label_schedule"][-2][1].startswith("406")
    assert len(m["camera_path"]) >= 5


def test_sheet_reveal_has_moving_shapes_a_reveal_and_a_camera(tmp_path):
    p, cfg = small_cfg(tmp_path, "sheet_reveal", 15.5, faces=2500)
    gen(p, "--stage", "0", "--mode", "build")
    m = markers(cfg.stages()[0].blend_path)
    assert m["clearance_m"] >= 0.02                                  # the hidden shapes never overlap while moving
    assert m["reveal_end"] > m["reveal_start"] and m["reveal_start"] + 30 < cfg.frame_count
    assert len(m["camera_path"]) == cfg.frame_count
