"""Batch generation, content diversity and the content library (pure Python; the real-Blender batch is in
tests/test_batch_blender.py)."""
import json
from collections import Counter
from pathlib import Path

import pytest

from shorts_engine import batch, diversity, library
from shorts_engine.config import ConfigError, load_config
from shorts_engine.templates import TEMPLATES


# ------------------------------------------------------------------ diversity
def test_plan_experiments_is_balanced_and_does_not_repeat_back_to_back():
    plan = diversity.plan_experiments(10, ["multiple_balls", "ball_funnel"], seed=1)
    c = Counter(plan)
    assert c["multiple_balls"] == c["ball_funnel"] == 5
    assert all(a != b for a, b in zip(plan, plan[1:]))


def test_plan_experiments_prefers_what_the_library_lacks():
    hist = [("multiple_balls", {})] * 5 + [("ball_funnel", {})] * 5
    plan = diversity.plan_experiments(4, ["multiple_balls", "ball_funnel", "ring_toss"], hist, seed=2)
    assert plan[:2] != ["multiple_balls", "multiple_balls"] and set(plan) == {"ring_toss"} | (set(plan) - {"ring_toss"})
    assert plan.count("ring_toss") >= 3


def test_plan_experiments_all_and_deterministic():
    a = diversity.plan_experiments(len(TEMPLATES), seed=3)
    assert sorted(a) == sorted(TEMPLATES) and a == diversity.plan_experiments(len(TEMPLATES), seed=3)


@pytest.mark.parametrize("bad", [0, -2, 1.5, True])
def test_plan_experiments_rejects_bad_counts(bad):
    with pytest.raises(ConfigError):
        diversity.plan_experiments(bad)


def test_plan_experiments_unknown_name():
    with pytest.raises(ConfigError, match="unknown experiment"):
        diversity.plan_experiments(2, ["nope"])


# ------------------------------------------------------------------ batch planning / writing
def test_batch_names_seeds_and_configs_are_unique(tmp_path):
    vs = batch.plan_batch("multiple_balls", 10, 42)
    m = batch.write_batch(vs, tmp_path / "b", 42, "720p")
    assert m["count"] == 10 and len({i["name"] for i in m["items"]}) == 10 and len({i["seed"] for i in m["items"]}) == 10
    assert len({i["config_hash"] for i in m["items"]}) == 10
    for it in m["items"]:
        cfg = load_config(it["config"])
        assert cfg.experiment_type == "multiple_balls" and Path(cfg.output.dir) == tmp_path / "b" / "videos"
        meta = json.loads(Path(it["config"] + ".meta.json").read_text())
        assert meta["seed"] == it["seed"] and meta["changed"] == it["changed"] and meta["batch_seed"] == 42


def test_batch_auto_experiments_covers_every_type():
    vs = batch.plan_batch("auto", len(TEMPLATES), 9)
    assert {v.experiment for v in vs} == set(TEMPLATES)


def test_batch_is_reproducible_for_the_same_seed(tmp_path):
    a = batch.write_batch(batch.plan_batch("ring_toss,ball_funnel", 4, 8), tmp_path / "a", 8, "720p")
    b = batch.write_batch(batch.plan_batch("ring_toss,ball_funnel", 4, 8), tmp_path / "b", 8, "720p")
    assert [i["config_hash"] for i in a["items"]] != [] and \
        [(i["name"], i["seed"], i["changed"]) for i in a["items"]] == [(i["name"], i["seed"], i["changed"]) for i in b["items"]]


def test_batch_refuses_to_overwrite_a_different_config(tmp_path):
    vs = batch.plan_batch("ball_funnel", 2, 3)
    batch.write_batch(vs, tmp_path / "b", 3, "720p")
    batch.write_batch(vs, tmp_path / "b", 3, "720p")                      # identical config: fine (resume)
    vs[0].config["seed"] += 1
    with pytest.raises(ConfigError, match="already exists"):
        batch.write_batch(vs, tmp_path / "b", 3, "720p")


@pytest.mark.parametrize("bad", [0, 101, -1, 2.5, "3"])
def test_batch_rejects_bad_counts(bad):
    with pytest.raises(ConfigError, match="variations"):
        batch.plan_batch("multiple_balls", bad, 1)


def test_batch_seed_resolution():
    assert batch.resolve_seed("12") == 12 and isinstance(batch.resolve_seed("auto"), int)
    for bad in ("-3", "abc", None.__class__):
        if bad is None.__class__:
            with pytest.raises(ConfigError):
                batch.resolve_seed(bad)
        else:
            with pytest.raises(ConfigError, match="seed"):
                batch.resolve_seed(bad)


def test_unsafe_names_never_reach_disk(tmp_path):
    vs = batch.plan_batch("multiple_balls", 1, 1)
    vs[0].name = "../evil"
    with pytest.raises(ConfigError, match="unsafe"):
        batch.write_batch(vs, tmp_path / "b", 1, "720p")
    assert not (tmp_path / "evil.json").exists()


def test_cli_writes_configs_and_manifest_without_running(tmp_path, capsys):
    assert batch.main(["--experiment", "multiple_balls", "--variations", "3", "--seed", "7", "--out", str(tmp_path)]) == 0
    m = json.loads((tmp_path / "batch_7" / "manifest.json").read_text())
    assert m["count"] == 3 and all(i["status"] == "planned" for i in m["items"])
    assert batch.main(["--experiment", "teleporter", "--variations", "1", "--out", str(tmp_path)]) == 2


# ------------------------------------------------------------------ batch running (fake renderer)
def fake_run(videos: Path, outcomes: dict):
    def runner(args):
        cfg = json.loads(Path(args[1]).read_text())
        name = cfg["name"]
        code = outcomes.get(name, 0)
        d = videos / name
        d.mkdir(parents=True, exist_ok=True)
        meta = json.loads(Path(args[1] + ".meta.json").read_text())
        (d / "metadata.json").write_text(json.dumps({"name": name, "variation": meta}))
        (d / "qc_report.json").write_text(json.dumps({"passed": code == 0}))
        if code == 99:
            raise RuntimeError("boom")
        return code
    return runner


def test_run_batch_isolates_failures_and_records_status(tmp_path):
    vs = batch.plan_batch("multiple_balls", 4, 11)
    m = batch.write_batch(vs, tmp_path, 11, "720p")
    names = [i["name"] for i in m["items"]]
    out = batch.run_batch(m, tmp_path, [], runner=fake_run(tmp_path / "videos", {names[1]: 3, names[2]: 99}))
    assert [i["status"] for i in out["items"]] == ["ok", "qc_failed", "failed", "ok"]
    assert out["status_counts"] == {"ok": 2, "qc_failed": 1, "failed": 1}
    assert "boom" in out["items"][2]["error"]
    saved = json.loads((tmp_path / "manifest.json").read_text())
    assert saved["status_counts"] == out["status_counts"]


def test_run_batch_skips_finished_identical_videos(tmp_path):
    m = batch.write_batch(batch.plan_batch("ring_toss", 2, 5), tmp_path, 5, "720p")
    calls = []
    runner = fake_run(tmp_path / "videos", {})
    batch.run_batch(m, tmp_path, [], runner=lambda a: calls.append(a) or runner(a))
    assert len(calls) == 2
    m2 = batch.write_batch(batch.plan_batch("ring_toss", 2, 5), tmp_path, 5, "720p")
    out = batch.run_batch(m2, tmp_path, [], runner=lambda a: calls.append(a) or runner(a))
    assert len(calls) == 2 and [i["status"] for i in out["items"]] == ["skipped_existing"] * 2


# ------------------------------------------------------------------ library
def make_video_dir(root, name, experiment="multiple_balls", qc=True, params=None, stages=(1, 10, 50, 100), obj="sphere"):
    d = root / name
    d.mkdir(parents=True)
    st = [{"params": {"balls": s}} for s in stages]
    (d / "metadata.json").write_text(json.dumps({
        "name": name, "experiment": experiment, "seed": 5, "resolution": "720x1280", "planned_seconds": 14.0,
        "created_utc": "2026-01-01T00:00:00Z", "stage_labels": ["x"],
        "experiment_config": {"experiment": {"type": experiment, "object": obj, "params": params or {}}, "stages": st}}))
    (d / "qc_report.json").write_text(json.dumps({"passed": qc}))
    (d / "benchmark.json").write_text(json.dumps({"summary": {"total_wall_seconds": 12.5, "render_devices": ["CPU"]}}))
    (d / f"{name}.mp4").write_bytes(b"x")
    return d


def test_library_index_lists_videos_with_qc_and_benchmarks(tmp_path):
    make_video_dir(tmp_path / "v", "a")
    make_video_dir(tmp_path / "v", "b", qc=False)
    (tmp_path / "v" / "junk").mkdir()
    idx = library.build_index([tmp_path], tmp_path / "library.json")
    assert idx["count"] == 2 and idx["qc_failed"] == ["b"] and idx["by_experiment"]["multiple_balls"] == 2
    e = {x["name"]: x for x in idx["entries"]}["a"]
    assert e["video_exists"] and e["render_seconds"] == 12.5 and e["stage_values"] == [1, 10, 50, 100]
    assert json.loads((tmp_path / "library.json").read_text())["count"] == 2


def test_library_cli(tmp_path, capsys):
    make_video_dir(tmp_path / "v", "a"); make_video_dir(tmp_path / "v", "b", qc=False)
    assert library.main(["index", str(tmp_path)]) == 0
    assert library.main(["list", str(tmp_path), "--failed"]) == 0
    out = capsys.readouterr().out
    assert "b " in out and "qc=False" in out
    assert library.main(["experiments"]) == 0 and "ball_funnel" in capsys.readouterr().out


def test_history_feeds_diversity_and_new_batches_avoid_existing_videos(tmp_path):
    make_video_dir(tmp_path / "v", "old", params={"ball_radius": 0.2, "drop_height": 2.0, "friction": 0.5})
    make_video_dir(tmp_path / "v", "bad", qc=False)
    hist = library.history_vectors(library.scan([tmp_path]))
    assert len(hist) == 1, "videos that failed QC are not counted as existing content"
    vs = batch.plan_batch("auto", 4, 1, library_roots=[tmp_path])
    assert Counter(v.experiment for v in vs)["multiple_balls"] <= 1      # the library already has a ball video
    from shorts_engine.variation import distance
    mine = [v for v in vs if v.experiment == "multiple_balls"]
    assert all(distance(v.vector, hist[0][1]) > 0 for v in mine)


def test_library_ignores_unreadable_metadata(tmp_path):
    d = tmp_path / "v" / "x"; d.mkdir(parents=True)
    (d / "metadata.json").write_text("{broken")
    assert library.scan([tmp_path]) == []


def test_failed_item_is_retried_with_a_safe_config_and_recovers(tmp_path):
    vs = batch.plan_batch("multiple_balls", 2, 12)
    m = batch.write_batch(vs, tmp_path, 12, "720p")
    base = fake_run(tmp_path / "videos", {})

    def runner(args):
        cfg = json.loads(Path(args[1]).read_text())
        if cfg["render"].get("samples") != 8:          # the original fails, the safe retry succeeds
            raise RuntimeError("out of memory")
        return base(args)

    out = batch.run_batch(m, tmp_path, [], runner=runner)
    assert [i["status"] for i in out["items"]] == ["ok", "ok"]
    first = out["items"][0]
    assert first["retried_with_safe_config"].endswith(".safe.json") and len(first["attempts"]) == 2
    assert "out of memory" in first["attempts"][0]["error"]
