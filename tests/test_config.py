from pathlib import Path

import pytest

from shorts_engine.config import (
    ConfigError, faces_to_segments, format_label, from_dict, load_config, short_face_label,
)

ROOT = Path(__file__).resolve().parent.parent


def test_example_and_smoke_configs_load():
    for name in ("example_cloth.json", "ci_smoke.json"):
        cfg = load_config(ROOT / "configs" / name)
        assert cfg.stages()
        assert cfg.output.height > cfg.output.width


def test_example_config_has_expected_stages():
    cfg = load_config(ROOT / "configs" / "example_cloth.json")
    assert [s.faces for s in cfg.stages()] == [64, 1024, 4096, 16384]
    assert [s.segments for s in cfg.stages()] == [8, 32, 64, 128]
    assert [s.label for s in cfg.stages()] == ["64 FACE", "1024 FACE", "4096 FACE", "16K FACE"]
    assert cfg.frame_count == 120


def test_faces_must_be_perfect_square():
    assert faces_to_segments(1024) == 32
    for bad in (0, 1, 3, 99, 1001, -4):
        with pytest.raises(ConfigError):
            faces_to_segments(bad)
    with pytest.raises(ConfigError):
        faces_to_segments(True)


def test_short_labels():
    assert short_face_label(64) == "64"
    assert short_face_label(4096) == "4096"
    assert short_face_label(16384) == "16K"
    assert short_face_label(1_000_000) == "1 M"
    assert format_label("{faces} faces", 64) == "64 faces"


def test_unknown_keys_are_rejected():
    with pytest.raises(ConfigError, match="unknown key"):
        from_dict({"phisics": {}})
    with pytest.raises(ConfigError, match="physics"):
        from_dict({"physics": {"gravty": 9.8}})


@pytest.mark.parametrize("patch", [
    {"simulation": "fluid"},
    {"object": {"type": "teapot"}},
    {"resolutions": []},
    {"resolutions": [64, 99]},
    {"fps": 0},
    {"duration": 0},
    {"output": {"width": 1280, "height": 720}},   # not vertical
    {"output": {"width": 721, "height": 1280}},   # odd width
    {"material": {"cloth_color": [1, 1, 1]}},
    {"material": {"cloth_style": "lace"}},
    {"render": {"device": "TPU"}},
    {"label": {"template": "{nope}"}},
    {"name": "has space"},
])
def test_invalid_values_rejected(patch):
    with pytest.raises(ConfigError):
        from_dict(patch)


def test_missing_and_bad_files(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ConfigError, match="valid JSON"):
        load_config(bad)


def test_output_paths_are_namespaced_per_stage(tmp_path):
    cfg = from_dict({"name": "x", "output": {"dir": str(tmp_path), "width": 360, "height": 640}})
    st = cfg.stages()[0]
    assert st.blend_path.parent == tmp_path / "x" / "stage_00_64"
    assert st.frames_dir.name == "frames"
    assert cfg.final_video_path() == tmp_path / "x" / "x.mp4"


def test_example_config_uses_kaggle_sweep_render_settings():
    """First Kaggle production test: 16 samples, denoising OFF (chosen from the Kaggle quality sweep)."""
    cfg = load_config(ROOT / "configs" / "example_cloth.json")
    assert (cfg.render.engine, cfg.render.samples, cfg.render.denoise, cfg.render.device) == ("CYCLES", 16, False, "AUTO")
    assert (cfg.output.width, cfg.output.height, cfg.fps, cfg.duration) == (720, 1280, 30, 4.0)
    assert cfg.resolutions == [64, 1024, 4096, 16384]
