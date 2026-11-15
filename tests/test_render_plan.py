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
