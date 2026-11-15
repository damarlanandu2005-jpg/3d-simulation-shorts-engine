import json
from pathlib import Path

import pytest

from shorts_engine.config import ConfigError, format_ratio, from_dict, load_config

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs"
A, B, C = (load_config(CONFIGS / n) for n in ("v1_1_a_baseline.json", "v1_1_b_optix.json", "v1_1_c_1080p.json"))


def test_v1_config_is_unchanged_by_v11_defaults():
    cfg = load_config(CONFIGS / "example_cloth.json")
    assert cfg.video.hook.mode == "tail" and not cfg.video.cards.enabled and cfg.cards() == []
    assert cfg.render.denoiser == "OPENIMAGEDENOISE"
    assert all(cfg.camera_for_stage(i) == cfg.camera for i in range(4))


def test_test_configs_differ_only_where_intended():
    assert (A.render.samples, A.render.denoise) == (16, False)
    assert (B.render.samples, B.render.denoise, B.render.denoiser) == (16, True, "OPTIX")
    assert (A.output.width, A.output.height) == (720, 1280)
    assert (C.output.width, C.output.height) == (1080, 1920)
    assert (C.render.samples, C.render.denoise) == (16, False)
    assert len({A.name, B.name, C.name}) == 3
    for other in (B, C):
        assert other.resolutions == A.resolutions and other.duration == A.duration == 3.0
        assert other.video == A.video and other.camera == A.camera and other.label == A.label


def test_labels_use_thousands_separator():
    assert [s.label for s in A.stages()] == ["64 FACES", "1,024 FACES", "4,096 FACES", "16,384 FACES"]


def test_production_configs_have_cards_off_and_music_on():
    for cfg in (A, B, C):
        assert not cfg.video.cards.enabled and cfg.cards() == []
        assert cfg.audio.enabled and cfg.audio.volume_db == -18 and cfg.music_path().is_file()


def test_cards_and_ratios():
    from dataclasses import replace
    on = replace(A, video=replace(A.video, cards=replace(A.video.cards, enabled=True)))
    assert [(c.title, c.subtitle) for c in on.cards()] == [("×16", "MORE FACES"), ("×4", "MORE FACES"), ("×4", "MORE FACES")]
    assert all(c.frames == 15 for c in on.cards())  # 0.5 s at 30 fps
    assert format_ratio(64, 16384) == "256" and format_ratio(64, 100) == "1.6"


def test_hook_text_and_range():
    assert A.hook_text() == "WHAT HAPPENS WHEN\nWE ADD 256×\nMORE FACES?"
    assert A.frame_count == 90 and A.hook_frame_range() == (31, 90)
    short = from_dict({"duration": 1, "fps": 10, "video": {"hook_seconds": 5}})
    assert short.hook_frame_range() == (1, 10)  # capped at the clip length


def test_per_stage_camera_merges_and_ignores_missing_entries():
    assert A.camera_for_stage(0).distance == 11.0
    assert [A.camera_for_stage(i).distance for i in range(4)] == [11.0, 10.4, 9.8, 9.2]
    assert A.camera_for_stage(3).height == A.camera.height
    cfg = from_dict({"camera": {"per_stage": [{"distance": 9}]}})
    assert cfg.camera_for_stage(0).distance == 9 and cfg.camera_for_stage(2).distance == cfg.camera.distance


@pytest.mark.parametrize("patch", [
    {"camera": {"per_stage": [{}] * 5}},                       # more entries than stages
    {"camera": {"per_stage": [{"zoom": 2}]}},                  # unknown key
    {"camera": {"per_stage": [{"distance": "far"}]}},          # not a number
    {"camera": {"per_stage": [{"distance": 0}]}},              # must be > 0
    {"camera": {"per_stage": [5]}},                            # not an object
    {"render": {"denoiser": "NLM"}},
    {"video": {"hook": {"mode": "spin"}}},
    {"video": {"hook": {"mode": "closeup"}, "hook_seconds": 0}},
    {"video": {"hook": {"text": "{oops}"}}},
    {"video": {"hook": {"mode": "closeup", "closeup": {"distance_start": 0}}}},
    {"video": {"cards": {"enabled": True, "seconds": 5}}},
    {"video": {"cards": {"enabled": True, "title": "{nope}"}}},
    {"video": {"cards": {"enabled": True}}, "resolutions": [1024, 64]},   # not increasing
    {"video": {"cards": {"enabled": True}}, "resolutions": [64]},         # needs two stages
])
def test_invalid_v11_values_rejected(patch):
    with pytest.raises(ConfigError):
        from_dict(patch)


def test_closeup_distance_validated_in_closeup_mode():
    with pytest.raises(ConfigError):
        from_dict({"video": {"hook": {"mode": "closeup", "closeup": {"distance_end": -1}}}})


def test_config_with_non_ascii_text_loads_regardless_of_locale(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"video": {"cards": {"title": "×{ratio}"}}}, ensure_ascii=False), encoding="utf-8")
    assert load_config(p).video.cards.title == "×{ratio}"
