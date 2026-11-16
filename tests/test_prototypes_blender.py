"""Real Blender tests of the three prototypes: the physical outcome is asserted, not just that it ran."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from shorts_engine.config import load_config
from tests.test_experiments_blender import gen

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(importlib.util.find_spec("bpy") is None, reason="bpy not installed")


def small_cfg(tmp_path, name, duration, **sim):
    d = json.loads((ROOT / "configs" / "prototypes" / f"{name}.json").read_text())
    d["simulation"] = {"fps": 30, "duration": duration, **sim}
    d["render"] = {"samples": 2, "device": "CPU", "denoise": False}
    d["output"] = {"width": 90, "height": 160, "dir": str(tmp_path)}
    d["audio"] = {"enabled": True, "music_enabled": True, "sfx_enabled": True}
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(d))
    return p, load_config(p)


def result(cfg, stage):
    return json.loads((Path(cfg.stages()[stage].blend_path).parent / "result.json").read_text())


def test_roll_off_real_physics(tmp_path):
    p, cfg = small_cfg(tmp_path, "roll_off", 7.0, payoff_duration=7.0)
    for st in (0, 1):
        gen(p, "--stage", str(st), "--mode", "build")
    r = result(cfg, 0)
    assert r["winner"] == "sphere" and not r["dead_heat"] and not r["did_not_finish"]
    assert r["order"][0] == "sphere" and r["order"][-1] in ("cube", "prism")      # rolling beats sliding
    assert r["finish_spread_frames"] > 10
    ice = result(cfg, 1)
    assert ice["dead_heat"] and ice["finish_spread_frames"] <= 2                  # no friction: identical acceleration


def test_jar_packing_fills_gaps_without_spilling(tmp_path):
    p, cfg = small_cfg(tmp_path, "jar_packing", 13.5)
    gen(p, "--stage", "0", "--mode", "build")
    r = result(cfg, 0)
    assert r["outside_jar"] == 0 and r["above_rim"] <= 3
    levels = r["fill_levels"]
    # the jar looks full after the large rocks and the later pours fit in the gaps: the level never climbs past the rim
    assert len(levels) == 4 and max(levels) - levels[0] < 0.3 and max(levels) < 2.2 + 0.35


def test_sheet_reveal_bakes_a_draped_sheet_with_reveal_markers(tmp_path):
    import subprocess, sys
    p, cfg = small_cfg(tmp_path, "sheet_reveal", 8.0)
    gen(p, "--stage", "0", "--mode", "build")
    code = ("import bpy, json, sys\nbpy.ops.wm.open_mainfile(filepath=sys.argv[1])\n"
            "m = json.loads(bpy.context.scene['sim_markers'])\n"
            "print('MARK ' + json.dumps(m))\n")
    out = subprocess.run([sys.executable, "-c", code, str(cfg.stages()[0].blend_path)], capture_output=True, text=True, timeout=300).stdout
    marks = json.loads([l for l in out.splitlines() if l.startswith("MARK ")][0][5:])
    assert marks["reveal_end"] > marks["reveal_start"] >= round(cfg.params["reveal_start"] * cfg.fps) - 1
