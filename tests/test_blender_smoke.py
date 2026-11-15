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


# ---------------------------------------------------------------- V1.1
@pytest.fixture()
def v11_cfg(tmp_path):
    cfg = {"name": "v11", "resolutions": [64, 256], "fps": 10, "duration": 1.0,
           "output": {"width": 90, "height": 160, "dir": str(tmp_path)},
           "render": {"samples": 2, "device": "CPU"},
           "video": {"hook_seconds": 0.5,
                     "hook": {"mode": "closeup", "text": "A {total_ratio}x\nB", "closeup": {"samples": 3}},
                     "cards": {"enabled": True, "seconds": 0.4, "samples": 2}}}
    p = tmp_path / "v11.json"
    p.write_text(json.dumps(cfg))
    return p


def test_closeup_hook_renders_from_baked_cache(v11_cfg, tmp_path):
    _run(v11_cfg, "--stage", "1", "--mode", "build")
    m = _run(v11_cfg, "--stage", "1", "--mode", "hook")[0]
    frames = sorted((tmp_path / "v11" / "hook" / "frames").glob("*.png"))
    assert [f.name for f in frames] == [f"frame_{n:04d}.png" for n in range(6, 11)]   # last 0.5 s of 10 frames
    assert m["kind"] == "hook" and m["frames_rendered"] == 5 and m["samples"] == 3  # closeup.samples override


def test_hook_without_a_baked_stage_fails_with_a_clear_message(v11_cfg):
    proc = subprocess.run([sys.executable, str(GEN), "--config", str(v11_cfg), "--stage", "1", "--mode", "hook"],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode != 0 and "build" in (proc.stderr + proc.stdout)


def test_card_renders_without_any_bake(v11_cfg, tmp_path):
    m = _run(v11_cfg, "--mode", "card", "--card-index", "0")[0]
    frames = sorted((tmp_path / "v11" / "card_00" / "frames").glob("*.png"))
    assert len(frames) == 4 == m["frames_rendered"]                          # 0.4 s at 10 fps
    assert m["denoise"] is False and m["samples"] == 2


def test_optix_denoiser_falls_back_to_oidn_without_an_optix_gpu(cfg_path, tmp_path):
    _run(cfg_path, "--stage", "0", "--mode", "build")
    cfg = json.loads(cfg_path.read_text())
    cfg["render"].update({"denoise": True, "denoiser": "OPTIX", "device": "CPU"})
    cfg_path.write_text(json.dumps(cfg))
    m = _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "2", "--frame-end", "2")[0]
    assert m["denoise"] is True and m["denoiser"] == "OPENIMAGEDENOISE"


def test_camera_and_label_edits_apply_at_render_time(cfg_path, tmp_path):
    """Changing camera/label in the config must change the image without re-baking."""
    _run(cfg_path, "--stage", "0", "--mode", "build")
    frame = tmp_path / "smoke" / "stage_00_64" / "frames" / "frame_0006.png"
    _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "6", "--frame-end", "6")
    before = frame.read_bytes()
    cfg = json.loads(cfg_path.read_text())
    cfg["camera"] = {"per_stage": [{"distance": 6.0}]}
    cfg_path.write_text(json.dumps(cfg))
    frame.unlink()
    _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "6", "--frame-end", "6")
    assert frame.read_bytes() != before
    cfg["label"] = {"template": "CHANGED {faces}"}
    cfg_path.write_text(json.dumps(cfg))
    after_camera = frame.read_bytes()
    frame.unlink()
    _run(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "6", "--frame-end", "6")
    assert frame.read_bytes() != after_camera


def test_events_mode_detects_the_cloth_hitting_the_sphere(tmp_path):
    """Bake a tiny stage, then read the physical events from the baked cache (no physics/render changes)."""
    cfg = {"name": "ev", "fps": 24, "duration": 3, "resolutions": [64],
           "output": {"dir": str(tmp_path), "width": 64, "height": 128},
           "camera": {"per_stage": []}, "video": {"hook": {"mode": "none"}},
           "audio": {"enabled": True, "sfx_enabled": True}}
    path = tmp_path / "ev.json"
    path.write_text(json.dumps(cfg))
    _run(path, "--stage", "0", "--mode", "build")
    (m,) = _run(path, "--stage", "0", "--mode", "events")
    assert m["kind"] == "events" and m["events"] >= 1
    data = json.loads(next(tmp_path.rglob("events.json")).read_text())
    first = data["events"][0]
    assert first["type"] == "impact" and first["source"] == "Collider"
    assert 8 < first["frame"] < 30                      # ~0.6 s free fall from 1.3 m at 24 fps
    assert first["strength"] > 0.4
    assert [e["frame"] for e in data["events"]] == sorted(e["frame"] for e in data["events"])
    assert len(data["events"]) <= 6                     # a handful of events, not one per frame


def test_new_format_config_drives_real_blender_identically_to_the_legacy_format(tmp_path):
    """Phase 2: the experiment-format config must produce the same simulation events as the flat format."""
    from shorts_engine.experiment import to_experiment_dict
    from shorts_engine.config import from_dict

    flat = {"name": "compat", "fps": 24, "duration": 2, "resolutions": [64],
            "output": {"dir": str(tmp_path / "flat"), "width": 64, "height": 128},
            "camera": {"per_stage": []}, "video": {"hook": {"mode": "none"}},
            "audio": {"enabled": True, "sfx_enabled": True}}
    new = to_experiment_dict(from_dict(flat))
    new["output"]["dir"] = str(tmp_path / "new")
    events = {}
    for label, data in (("flat", flat), ("new", new)):
        path = tmp_path / f"{label}.json"
        path.write_text(json.dumps(data))
        _run(path, "--stage", "0", "--mode", "build")
        _run(path, "--stage", "0", "--mode", "events")
        events[label] = json.loads(next((tmp_path / label).rglob("events.json")).read_text())["events"]
    assert events["flat"] and events["flat"] == events["new"]     # identical physics -> identical contact events
