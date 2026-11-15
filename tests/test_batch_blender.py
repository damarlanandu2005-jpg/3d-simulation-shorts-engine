"""A real batch: variations of three experiments rendered end to end in Blender, QC-checked, then catalogued."""
import importlib.util
import json
import shutil

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("bpy") is None or not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="needs bpy + ffmpeg/ffprobe")


def test_batch_of_new_experiments_renders_passes_qc_and_is_catalogued(tmp_path):
    from shorts_engine import batch, library
    variations = batch.plan_batch("multiple_balls,ball_funnel,ring_toss", 3, 21)
    assert {v.experiment for v in variations} == {"multiple_balls", "ball_funnel", "ring_toss"}
    for v in variations:                                     # tiny settings: the point is the real pipeline, not the pixels
        v.config["simulation"] = {"fps": 24, "duration": 1.0}
        v.config["output"] = {"width": 90, "height": 160}
        v.config["render"] = {"samples": 2, "device": "CPU", "denoise": False}
        v.config["hook"]["seconds"] = 1.0
    manifest = batch.write_batch(variations, tmp_path, 21, "720p")
    out = batch.run_batch(manifest, tmp_path, ["--use-bpy"])
    assert [i["status"] for i in out["items"]] == ["ok"] * 3, out["items"]
    for item in out["items"]:
        root = tmp_path / "videos" / item["name"]
        for f in (f"{item['name']}.mp4", "benchmark.json", "metadata.json", "qc_report.json", "audio_timeline.json"):
            assert (root / f).is_file(), (item["name"], f)
        meta = json.loads((root / "metadata.json").read_text())
        assert meta["variation"]["seed"] == item["seed"] and meta["variation"]["changed"] == item["changed"]
    idx = library.build_index([tmp_path], tmp_path / "library.json")
    assert idx["count"] == 3 and idx["qc_failed"] == []
    again = batch.run_batch(batch.write_batch(variations, tmp_path, 21, "720p"), tmp_path, ["--use-bpy"])
    assert [i["status"] for i in again["items"]] == ["skipped_existing"] * 3
