import sys
from pathlib import Path

import pytest

from shorts_engine import render
from shorts_engine.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = str(ROOT / "configs" / "example_cloth.json")


def test_split_frame_range_covers_everything_without_overlap():
    ranges = render.split_frame_range(1, 120, 7)
    assert ranges[0][0] == 1 and ranges[-1][1] == 120
    covered = [f for a, b in ranges for f in range(a, b + 1)]
    assert covered == list(range(1, 121))
    assert len(ranges) == 7


def test_split_frame_range_edge_cases():
    assert render.split_frame_range(5, 5, 4) == [(5, 5)]          # more chunks than frames
    assert render.split_frame_range(1, 10, 1) == [(1, 10)]
    with pytest.raises(ValueError):
        render.split_frame_range(0, 10, 2)
    with pytest.raises(ValueError):
        render.split_frame_range(10, 5, 2)
    with pytest.raises(ValueError):
        render.split_frame_range(1, 10, 0)


def _plan(**kw):
    cfg = load_config(CFG_PATH)
    return cfg, render.plan_jobs(cfg, CFG_PATH, ["blender"], True, **kw)


def test_full_plan_order_and_counts():
    cfg, jobs = _plan()
    kinds = [j.kind for j in jobs]
    assert kinds == ["bake", "render"] * 4 + ["clip"] * 4 + ["hook", "concat"]


def test_blender_command_shape():
    _, jobs = _plan()
    cmd = jobs[0].cmd
    assert cmd[:3] == ["blender", "--background", "--python"]
    assert "--" in cmd and cmd[cmd.index("--") + 1:][:2] == ["--config", CFG_PATH]
    assert cmd[-2:] == ["--mode", "build"]


def test_bpy_command_shape():
    cfg = load_config(CFG_PATH)
    jobs = render.plan_jobs(cfg, CFG_PATH, ["python"], False)
    assert jobs[0].cmd[0] == "python" and "--background" not in jobs[0].cmd and "--" not in jobs[0].cmd


def test_chunks_make_independent_render_jobs():
    _, jobs = _plan(stages=[3], chunks=4, do_assemble=False)
    renders = [j for j in jobs if j.kind == "render"]
    assert len(renders) == 4
    assert all(j.stage == 3 for j in jobs)
    starts = [int(j.cmd[j.cmd.index("--frame-start") + 1]) for j in renders]
    assert starts == [1, 31, 61, 91]


def test_partial_runs_never_assemble():
    _, jobs = _plan(stages=[0])
    assert not any(j.kind in ("clip", "hook", "concat") for j in jobs)
    _, jobs = _plan(frame_start=1, frame_end=10)
    assert not any(j.kind in ("clip", "hook", "concat") for j in jobs)


def test_render_only_and_bake_only():
    _, jobs = _plan(do_bake=False, do_assemble=False)
    assert {j.kind for j in jobs} == {"render"}
    _, jobs = _plan(do_render=False, do_assemble=False)
    assert {j.kind for j in jobs} == {"bake"}


def test_bad_stage_or_frame_range():
    cfg = load_config(CFG_PATH)
    with pytest.raises(ConfigError):
        render.plan_jobs(cfg, CFG_PATH, ["blender"], True, stages=[9])
    with pytest.raises(ConfigError):
        render.plan_jobs(cfg, CFG_PATH, ["blender"], True, frame_end=9999)


def test_parse_metrics_ignores_noise():
    out = 'Blender 4.5\nSHORTS_METRIC {"a": 1}\nSHORTS_METRIC {broken\nbake: frame 1 :: 3\n'
    assert render.parse_metrics(out) == [{"a": 1}]


def test_dry_run_cli(capsys):
    rc = render.main(["--config", CFG_PATH, "--dry-run", "--blender", "blender"])
    assert rc == 0
    assert "concatenate" in capsys.readouterr().out


def test_cli_reports_config_errors(tmp_path, capsys):
    rc = render.main(["--config", str(tmp_path / "missing.json"), "--dry-run"])
    assert rc == 2


# ---------------------------------------------------------------- V1.1: hook, cards, extras
A_PATH = str(ROOT / "configs" / "v1_1_a_baseline.json")


def _plan_a(cards=False, audio=True, sfx=False, **kw):
    """Plan config A; `cards=True` re-enables the (optional) multiplier cards, `audio=False` drops the music."""
    import json
    from shorts_engine.config import from_dict
    data = json.loads(Path(A_PATH).read_text(encoding="utf-8"))
    data["video"]["cards"]["enabled"] = cards
    data["audio"]["enabled"] = audio
    data["audio"]["sfx_enabled"] = sfx
    cfg = from_dict(data)
    return cfg, render.plan_jobs(cfg, A_PATH, ["blender"], True, **kw)


def _concat_names(jobs):
    text = next(j for j in jobs if j.kind == "concat").write_text[1]
    return [Path(line.split("'")[1]).name for line in text.strip().splitlines()]


def test_v11_production_plan_has_no_cards_and_ends_with_music():
    cfg, jobs = _plan_a()
    kinds = [j.kind for j in jobs]
    assert kinds == (["bake", "render"] * 4 + ["hook_render"] + ["clip"] * 4 + ["hook", "concat", "audio"])
    assert "card_render" not in kinds
    hook_job = next(j for j in jobs if j.kind == "hook_render")
    assert hook_job.cmd[-2:] == ["--mode", "hook"] and hook_job.stage == 3      # last stage's baked cache


def test_stage_sequence_is_exactly_hook_then_four_stages():
    cfg, jobs = _plan_a()
    assert _concat_names(jobs) == ["hook.mp4", "stage_00_64.mp4", "stage_01_1024.mp4",
                                   "stage_02_4096.mp4", "stage_03_16384.mp4"]


def test_multiplier_cards_are_still_available_when_enabled():
    cfg, jobs = _plan_a(cards=True)
    kinds = [j.kind for j in jobs]
    assert kinds == (["bake", "render"] * 4 + ["hook_render"] + ["card_render"] * 3 + ["clip"] * 7 + ["hook", "concat", "audio"])
    cards = [j for j in jobs if j.kind == "card_render"]
    assert [j.cmd[j.cmd.index("--card-index") + 1] for j in cards] == ["0", "1", "2"]
    assert _concat_names(jobs) == [
        "hook.mp4", "stage_00_64.mp4", "card_00.mp4", "stage_01_1024.mp4", "card_01.mp4",
        "stage_02_4096.mp4", "card_02.mp4", "stage_03_16384.mp4"]


def test_closeup_hook_encodes_with_its_own_start_frame_and_checks_frames():
    cfg, jobs = _plan_a()
    hook = next(j for j in jobs if j.kind == "hook")
    assert hook.cmd[hook.cmd.index("-start_number") + 1] == "31"
    assert hook.check_frames == (cfg.hook_frames_dir, 31, 90)
    stage_clips = [j for j in jobs if j.kind == "clip" and j.stage is not None]
    assert all(j.check_frames[1:] == (1, 90) for j in stage_clips)


def test_only_extras_rerenders_hook_and_cards_without_touching_stages():
    cfg, jobs = _plan_a(cards=True, only_extras=True)
    kinds = [j.kind for j in jobs]
    assert "bake" not in kinds and "render" not in kinds
    assert kinds[:4] == ["hook_render"] + ["card_render"] * 3 and kinds[-2:] == ["concat", "audio"]


def test_skip_extras_gives_the_plain_v1_structure():
    cfg, jobs = _plan_a(cards=True, skip_extras=True)
    kinds = [j.kind for j in jobs]
    assert kinds == ["bake", "render"] * 4 + ["clip"] * 4 + ["hook", "concat", "audio"]
    hook = next(j for j in jobs if j.kind == "hook")
    assert "-sseof" in hook.cmd                                                  # tail hook, no extra render


def test_partial_runs_do_not_plan_extras():
    _, jobs = _plan_a(stages=[0])
    assert {j.kind for j in jobs} == {"bake", "render"}
    _, jobs = _plan_a(frame_start=1, frame_end=10)
    assert not any(j.kind in ("hook_render", "card_render", "concat") for j in jobs)


def test_missing_frames_stop_encoding_with_a_clear_message(tmp_path):
    (tmp_path / "frame_0001.png").write_bytes(b"x")
    job = render.Job("encode clip", "clip", ["true"], check_frames=(tmp_path, 1, 3))
    with pytest.raises(SystemExit, match="2 frame"):
        render.run_jobs([job])
    (tmp_path / "frame_0002.png").write_bytes(b"x")
    (tmp_path / "frame_0003.png").write_bytes(b"x")
    results = render.run_jobs([render.Job("encode clip", "clip", [sys.executable, "-c", "pass"], check_frames=(tmp_path, 1, 3))])
    assert results[0]["kind"] == "clip"


def test_summarize_reports_the_baseline_fields():
    cfg = load_config(A_PATH)
    results = [
        {"job": "bake", "kind": "bake", "wall_seconds": 10.0, "peak_rss_mb_so_far": 1, "metrics": [{"bake_seconds": 9.5}]},
        {"job": "render", "kind": "render", "wall_seconds": 20.0, "peak_rss_mb_so_far": 1,
         "metrics": [{"render_seconds": 19.0, "frames_rendered": 90, "frames_skipped": 0, "device": "OPTIX",
                      "samples": 16, "denoiser": None, "width": 720, "height": 1280}]},
    ]
    s = render.summarize(cfg, results, 33.3)
    assert s["total_wall_seconds"] == 33.3 and s["frames_rendered"] == 90 and s["bake_seconds"] == 9.5
    assert s["render_devices"] == ["OPTIX"] and s["samples_used"] == [16] and s["resolutions_used"] == ["720x1280"]
    assert s["wall_seconds_by_job_kind"] == {"bake": 10.0, "render": 20.0}
