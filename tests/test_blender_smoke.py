"""Real Blender test. Skipped automatically when the bpy module is not installed.

    pip install "bpy==4.5.*"      # needs Python 3.11
    pytest tests/test_blender_smoke.py
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "shorts_engine" / "generate_scene.py"

pytestmark = pytest.mark.skipif(importlib.util.find_spec("bpy") is None, reason="bpy not installed")


def _run(cfg_path, *extra):
    proc = subprocess.run([sys.executable, str(GEN), "--config", str(cfg_path), *extra],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    return [json.loads(l.split(" ", 1)[1]) for l in proc.stdout.splitlines() if l.startswith("SHORTS_METRIC ")]


@pytest.fixture()
def cfg_path(tmp_path):
    cfg = {"name": "smoke", "resolutions": [64], "fps": 12, "duration": 1.0,
           "output": {"width": 90, "height": 160, "dir": str(tmp_path)},
           "render": {"samples": 2, "device": "CPU"}}
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    return p


def test_build_bakes_and_saves_blend(cfg_path, tmp_path):
    metrics = _run(cfg_path, "--stage", "0", "--mode", "build")
    assert metrics[0]["faces"] == 64 and metrics[0]["frames"] == 12
    assert metrics[0]["bake_method"] == "ptcache"
    stage_dir = tmp_path / "smoke" / "stage_00_64"
    assert (stage_dir / "stage_00_64.blend").exists()
    assert list(stage_dir.glob("blendcache_*/*.bphys"))


def test_render_frame_range_is_resumable(cfg_path, tmp_path):
    _run(cfg_path, "--stage", "0", "--mode", "build")
    first = _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "5", "--frame-end", "6")[0]
    assert first["frames_rendered"] == 2
    frames = sorted((tmp_path / "smoke" / "stage_00_64" / "frames").glob("*.png"))
    assert [f.name for f in frames] == ["frame_0005.png", "frame_0006.png"]
    again = _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "5", "--frame-end", "7")[0]
    assert again["frames_rendered"] == 1 and again["frames_skipped"] == 2


def test_cloth_actually_moves(cfg_path, tmp_path):
    """The baked frames must differ: frame 1 (sheet in the air) vs the last frame (draped)."""
    _run(cfg_path, "--stage", "0", "--mode", "build")
    _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "1", "--frame-end", "1")
    _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "12", "--frame-end", "12")
    frames = tmp_path / "smoke" / "stage_00_64" / "frames"
    assert (frames / "frame_0001.png").read_bytes() != (frames / "frame_0012.png").read_bytes()


def test_render_settings_follow_current_config_not_the_saved_blend(cfg_path, tmp_path):
    """Regression: samples/denoise were frozen into the .blend at build time."""
    _run(cfg_path, "--stage", "0", "--mode", "build")          # built with samples=2
    cfg = json.loads(cfg_path.read_text())
    cfg["render"].update({"samples": 5, "denoise": False})
    cfg["output"].update({"width": 120, "height": 214})
    cfg_path.write_text(json.dumps(cfg))
    m = _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "3", "--frame-end", "3")[0]
    assert m["samples"] == 5 and m["denoise"] is False
    assert (m["width"], m["height"]) == (120, 214)
