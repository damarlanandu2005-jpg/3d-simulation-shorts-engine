"""Flexible stage counts, per-stage escalation (extras), payoff stage length and curated batches (no Blender needed)."""
import json
from pathlib import Path

import pytest

from shorts_engine import batch, timeline
from shorts_engine.config import ConfigError, ExperimentConfig, from_dict
from shorts_engine.templates import TEMPLATES, get_template, ramp

ROOT = Path(__file__).resolve().parent.parent


def doc(exp, stages=None, **extra):
    t = get_template(exp)
    vals = stages or t.default_stage_values
    d = {"schema_version": 2, "name": f"esc_{exp}", "experiment": {"type": exp},
         "stages": [{"params": {t.stage_param: v}} for v in vals]}
    d.update(extra)
    return d


@pytest.mark.parametrize("exp", ["multiple_balls", "ball_funnel", "ring_toss", "cloth_objects"])
@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_any_stage_count_from_three_to_six(exp, n):
    t = get_template(exp)
    base = list(t.stage_variations[0])
    vals = (base * 2)[:n] if len(base) < n else base[:n]
    if exp == "ball_funnel":
        vals = sorted({round(0.9 - 0.12 * i, 2) for i in range(n)}, reverse=True)
    elif exp == "ring_toss":
        vals = [round(2.6 - 0.35 * i, 2) for i in range(n)]
    elif exp == "multiple_balls":
        vals = [5, 12, 25, 45, 70, 95][:n]
    elif exp == "cloth_objects":
        vals = list(range(1, n + 1))
    cfg = from_dict(doc(exp, vals))
    assert cfg.stage_count == n == len(cfg.stages())


def test_ramp_is_strictly_increasing_and_ends_on_the_final_value():
    for final, n, start in [(60, 5, 7), (100, 3, 12), (5, 5, 1), (80, 6, 10)]:
        r = ramp(final, n, start)
        assert len(r) == n and r[-1] == final and all(b > a for a, b in zip(r, r[1:]))


def test_funnel_stages_escalate_ball_count_and_shrink_the_hole():
    cfg = from_dict(doc("ball_funnel"))
    balls = [st.params["balls"] for st in cfg.stages()]
    holes = [st.params["hole_radius"] for st in cfg.stages()]
    assert balls == sorted(balls) and len(set(balls)) == 5 and balls[-1] == 60
    assert holes == sorted(holes, reverse=True)
    assert [st.label for st in cfg.stages()][-1] == "60 BALLS"


def test_ring_stages_escalate_ring_count_and_name_the_difficulty():
    cfg = from_dict(doc("ring_toss"))
    assert [st.params["rings"] for st in cfg.stages()] == [1, 2, 3, 4, 5]
    assert [st.label for st in cfg.stages()] == ["WIDE RING", "LOOSE RING", "SNUG RING", "TIGHT RING", "TOO TIGHT"]


def test_explicit_stage_extras_win_over_the_template_ramp():
    d = doc("ball_funnel")
    for st, n in zip(d["stages"], [4, 8, 16, 32, 64]):
        st["params"]["balls"] = n
    cfg = from_dict(d)
    assert [st.params["balls"] for st in cfg.stages()] == [4, 8, 16, 32, 64]
    assert from_dict(json.loads(json.dumps(__import__("shorts_engine.experiment", fromlist=["x"]).to_experiment_dict(cfg)))).stage_extras == cfg.stage_extras


def test_stage_extras_only_accept_declared_parameters():
    d = doc("ball_funnel")
    d["stages"][0]["params"]["friction"] = 0.2
    with pytest.raises(ConfigError, match="friction"):
        from_dict(d)


def test_payoff_stage_is_longer_and_the_timeline_follows():
    cfg = from_dict(doc("multiple_balls", simulation={"fps": 30, "duration": 3.0, "payoff_duration": 5.0}))
    assert isinstance(cfg, ExperimentConfig)
    assert [cfg.stage_frames(i) for i in range(5)] == [90, 90, 90, 90, 150] and cfg.frame_count == 150
    assert [st.frames for st in cfg.stages()] == [90, 90, 90, 90, 150]
    segs = timeline.segments(cfg)
    stage_segs = [s for s in segs if s.kind == "stage"]
    assert [s.frames for s in stage_segs] == [90, 90, 90, 90, 150]
    assert timeline.total_seconds(cfg) == pytest.approx(2.0 + 4 * 3.0 + 5.0)


def test_payoff_must_not_be_shorter_than_a_stage():
    with pytest.raises(ConfigError, match="payoff_duration"):
        from_dict(doc("multiple_balls", simulation={"duration": 3.0, "payoff_duration": 2.0}))


def test_payoff_duration_is_not_available_for_the_v1_cloth_drape():
    with pytest.raises(ConfigError, match="payoff_duration"):
        from_dict(doc("cloth_drape", simulation={"payoff_duration": 4.0}))


def test_every_curated_config_is_valid_and_differs():
    files = sorted((ROOT / "configs" / "curated").glob("*.json"))
    assert len(files) >= 6
    vs = batch.load_curated(files)
    assert len({v.name for v in vs}) == len(vs)
    assert {v.experiment for v in vs} >= {"multiple_balls", "ball_funnel", "ring_toss", "cloth_objects", "cloth_drape"}
    assert any(len(v.stage_values) == 5 for v in vs), "at least one five-stage story"


def test_curated_batch_writes_a_manifest_with_unique_dirs(tmp_path):
    vs = batch.load_curated(sorted((ROOT / "configs" / "curated").glob("*.json")))
    m = batch.write_batch(vs, tmp_path, 9, "720p")
    assert m["count"] == len(vs) and len({i["config_hash"] for i in m["items"]}) == len(vs)
    assert all(Path(i["config"]).is_file() for i in m["items"])
