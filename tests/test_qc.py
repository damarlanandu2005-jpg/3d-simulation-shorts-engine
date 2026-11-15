import json
import shutil
import subprocess

import pytest

from shorts_engine import qc

pytestmark = pytest.mark.skipif(not qc.have_ffprobe(), reason="ffmpeg/ffprobe not installed")


def make(path, w=90, h=160, fps=30, secs=2.0, audio=True, audio_secs=None):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate={fps}:duration={secs}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={audio_secs or secs}", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)
    return path


def artifacts(tmp_path):
    (tmp_path / "benchmark.json").write_text('{"summary": {}}')
    (tmp_path / "metadata.json").write_text('{"name": "x"}')
    return tmp_path / "benchmark.json", tmp_path / "metadata.json"


def run(tmp_path, video, **kw):
    b, m = artifacts(tmp_path)
    args = dict(width=90, height=160, fps=30, expected_seconds=2.0, audio_expected=True, benchmark=b, metadata=m)
    args.update(kw)
    return qc.check_video(video, **args)


def failed(rep):
    return {c.name for c in rep.failed()}


def test_good_video_passes_every_check(tmp_path):
    rep = run(tmp_path, make(tmp_path / "v.mp4"))
    assert rep.passed, [c for c in rep.checks if not c.ok]
    assert {c.name for c in rep.checks} >= {
        "video exists", "valid video stream", "correct resolution", "correct aspect ratio", "valid fps", "valid duration",
        "complete frames", "no corrupted output", "valid audio stream", "matching audio/video duration",
        "benchmark exists", "metadata exists"}


def test_missing_and_empty_video(tmp_path):
    assert failed(run(tmp_path, tmp_path / "none.mp4")) >= {"video exists"}
    empty = tmp_path / "e.mp4"; empty.write_bytes(b"")
    assert "video exists" in failed(run(tmp_path, empty))


def test_wrong_resolution_and_aspect(tmp_path):
    rep = run(tmp_path, make(tmp_path / "v.mp4", w=160, h=90))
    assert {"correct resolution", "correct aspect ratio"} <= failed(rep)
    rep = run(tmp_path, make(tmp_path / "w.mp4", w=100, h=160))
    assert "correct resolution" in failed(rep)


def test_wrong_fps_duration_and_frame_count(tmp_path):
    rep = run(tmp_path, make(tmp_path / "v.mp4", fps=24))
    assert "valid fps" in failed(rep)
    rep = run(tmp_path, make(tmp_path / "w.mp4", secs=1.0, audio_secs=1.0))
    assert {"valid duration", "complete frames"} <= failed(rep)


def test_missing_audio_stream_and_mismatched_audio_duration(tmp_path):
    assert "valid audio stream" in failed(run(tmp_path, make(tmp_path / "v.mp4", audio=False)))
    rep = run(tmp_path, make(tmp_path / "w.mp4", audio_secs=1.0))
    assert "matching audio/video duration" in failed(rep)


def test_audio_not_expected_but_present(tmp_path):
    assert "no unexpected audio" in failed(run(tmp_path, make(tmp_path / "v.mp4"), audio_expected=False))
    assert run(tmp_path, make(tmp_path / "w.mp4", audio=False), audio_expected=False).passed


def test_truncated_and_garbage_files_are_flagged_corrupt(tmp_path):
    good = make(tmp_path / "v.mp4")
    data = good.read_bytes()
    cut = tmp_path / "cut.mp4"; cut.write_bytes(data[: len(data) // 2])
    rep = run(tmp_path, cut)
    assert not rep.passed and failed(rep) & {"valid video stream", "no corrupted output", "complete frames"}
    junk = tmp_path / "junk.mp4"; junk.write_bytes(b"not a video" * 100)
    assert "valid video stream" in failed(run(tmp_path, junk))


def test_damaged_payload_is_detected(tmp_path):
    good = make(tmp_path / "v.mp4")
    data = bytearray(good.read_bytes())
    mid = len(data) // 2
    data[mid:mid + 400] = bytes(400)
    bad = tmp_path / "bad.mp4"; bad.write_bytes(bytes(data))
    assert not run(tmp_path, bad).passed


def test_missing_benchmark_or_metadata(tmp_path):
    v = make(tmp_path / "v.mp4")
    rep = qc.check_video(v, 90, 160, 30, 2.0, True, tmp_path / "nobench.json", tmp_path / "nometa.json")
    assert {"benchmark exists", "metadata exists"} <= failed(rep)
    (tmp_path / "bad.json").write_text("{oops")
    assert "benchmark exists" in failed(qc.check_video(v, 90, 160, 30, 2.0, True, tmp_path / "bad.json", None))


def test_report_serialises(tmp_path):
    rep = run(tmp_path, make(tmp_path / "v.mp4"))
    d = json.loads(json.dumps(rep.to_dict()))
    assert d["passed"] is True and all({"name", "ok", "detail"} <= set(c) for c in d["checks"])


def test_cli_exit_codes(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"name": "q", "resolutions": [64], "fps": 30, "duration": 1.0,
                               "video": {"hook_seconds": 0.0}, "output": {"width": 90, "height": 160, "dir": str(tmp_path)}}))
    root = tmp_path / "q"; root.mkdir()
    make(root / "q.mp4", secs=1.0, audio=False)
    assert qc.main(["--config", str(cfg)]) == 3                       # no benchmark / metadata yet
    (root / "benchmark.json").write_text('{"summary": {}}'); (root / "metadata.json").write_text('{"name": "q"}')
    assert qc.main(["--config", str(cfg)]) == 0
    assert json.loads((root / "qc_report.json").read_text())["passed"]
    assert qc.main(["--config", str(tmp_path / "missing.json")]) == 2
