"""Automated quality control for a finished video (pure Python + ffprobe/ffmpeg; no Blender).

    python -m shorts_engine.qc --config CONFIG [--skip-extras]

Checks (each reported with ok/detail, written to ``qc_report.json`` next to the video; exit code 3 if any fail):

    video exists / not empty            valid H.264-style video stream      aspect ratio 9:16 and the configured resolution
    fps matches the config              duration matches the planned timeline    every frame present (frame count)
    decodes without errors              audio stream present when audio is on    audio/video duration match
    benchmark.json exists               metadata.json exists
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DURATION_TOLERANCE = 0.15       # seconds: planned vs actual video duration
AV_TOLERANCE = 0.12             # seconds: audio vs video stream duration


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class QCReport:
    video: str
    checks: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(name, bool(ok), detail))
        return bool(ok)

    def to_dict(self) -> dict:
        return {"video": self.video, "passed": self.passed,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks]}

    def failed(self) -> list:
        return [c for c in self.checks if not c.ok]


def have_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None


def probe(path: Path) -> dict:
    """ffprobe the file: streams (with frame counts) and container duration. Raises RuntimeError if unreadable."""
    proc = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                           "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,duration,nb_frames,"
                           "nb_read_frames,channels:format=duration", "-of", "json", str(path)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[-300:] or "ffprobe failed")
    return json.loads(proc.stdout)


def _fps(text: str) -> float:
    try:
        a, b = text.split("/")
        return float(a) / float(b) if float(b) else 0.0
    except (ValueError, AttributeError):
        return 0.0


def decode_errors(path: Path) -> str:
    """Decode the whole file and return ffmpeg's error output ('' = clean)."""
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    return (proc.stderr or "").strip() if proc.returncode == 0 else (proc.stderr or "decode failed").strip()


def check_video(path: Path, width: int, height: int, fps: float, expected_seconds: float, audio_expected: bool,
                benchmark: Path | None = None, metadata: Path | None = None) -> QCReport:
    """Run every check against a video file. ``expected_seconds`` is the planned timeline length."""
    path = Path(path)
    rep = QCReport(str(path))
    if not rep.add("video exists", path.is_file() and path.stat().st_size > 0,
                   f"{path} ({path.stat().st_size if path.is_file() else 0} bytes)"):
        _artifacts(rep, benchmark, metadata)
        return rep
    try:
        info = probe(path)
    except RuntimeError as exc:
        rep.add("valid video stream", False, f"unreadable: {exc}")
        _artifacts(rep, benchmark, metadata)
        return rep
    streams = info.get("streams", [])
    vids = [s for s in streams if s.get("codec_type") == "video"]
    auds = [s for s in streams if s.get("codec_type") == "audio"]
    if not rep.add("valid video stream", len(vids) == 1 and vids[0].get("codec_name") is not None,
                   f"{len(vids)} video stream(s)" + (f", codec {vids[0].get('codec_name')}" if vids else "")):
        _artifacts(rep, benchmark, metadata)
        return rep
    v = vids[0]
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    rep.add("correct resolution", (w, h) == (width, height), f"{w}x{h} (expected {width}x{height})")
    rep.add("correct aspect ratio", h > 0 and abs(w / h - width / height) < 1e-3 and h > w,
            f"{w}:{h} = {w / h:.4f}" if h else "no height")
    actual_fps = _fps(v.get("avg_frame_rate") or v.get("r_frame_rate", ""))
    rep.add("valid fps", abs(actual_fps - fps) < 0.01, f"{actual_fps:.3f} (expected {fps})")
    vdur = float(v.get("duration") or info.get("format", {}).get("duration") or 0)
    rep.add("valid duration", abs(vdur - expected_seconds) <= DURATION_TOLERANCE,
            f"{vdur:.3f}s (planned {expected_seconds:.3f}s)")
    frames = int(v.get("nb_read_frames") or v.get("nb_frames") or 0)
    want = round(expected_seconds * fps)
    rep.add("complete frames", frames == want, f"{frames} frames (planned {want})")
    err = decode_errors(path)
    rep.add("no corrupted output", err == "", err[:200] or "decodes cleanly")
    if audio_expected:
        ok = bool(auds)
        rep.add("valid audio stream", ok, f"{len(auds)} audio stream(s)" + (f", codec {auds[0].get('codec_name')}" if ok else ""))
        if ok:
            adur = float(auds[0].get("duration") or 0)
            rep.add("matching audio/video duration", abs(adur - vdur) <= AV_TOLERANCE, f"audio {adur:.3f}s vs video {vdur:.3f}s")
    else:
        rep.add("no unexpected audio", not auds, f"{len(auds)} audio stream(s)")
    _artifacts(rep, benchmark, metadata)
    return rep


def _artifacts(rep: QCReport, benchmark: Path | None, metadata: Path | None) -> None:
    for label, p in (("benchmark exists", benchmark), ("metadata exists", metadata)):
        if p is not None:
            ok = Path(p).is_file() and Path(p).stat().st_size > 2
            if ok:
                try:
                    json.loads(Path(p).read_text())
                except json.JSONDecodeError:
                    ok = False
            rep.add(label, ok, str(p))


def run_qc(cfg, skip_extras: bool = False) -> QCReport:
    """QC the final video of ``cfg`` against its planned timeline (see timeline.py)."""
    from . import timeline
    return check_video(cfg.final_video_path(), cfg.output.width, cfg.output.height, cfg.fps,
                       timeline.total_seconds(cfg, skip_extras), cfg.audio.enabled,
                       cfg.root_dir / "benchmark.json", cfg.root_dir / "metadata.json")


def write_report(cfg, report: QCReport) -> Path:
    path = cfg.root_dir / "qc_report.json"
    path.write_text(json.dumps(report.to_dict(), indent=1))
    return path


def main(argv=None) -> int:
    from .config import ConfigError, load_config
    p = argparse.ArgumentParser(prog="shorts_engine.qc")
    p.add_argument("--config", required=True)
    p.add_argument("--skip-extras", action="store_true")
    args = p.parse_args(argv)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not have_ffprobe():
        print("ERROR: ffmpeg/ffprobe not found", file=sys.stderr)
        return 2
    rep = run_qc(cfg, args.skip_extras)
    cfg.root_dir.mkdir(parents=True, exist_ok=True)
    out = write_report(cfg, rep)
    for c in rep.checks:
        print(f"  [{'ok' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
    print(f"QC {'PASSED' if rep.passed else 'FAILED'} -> {out}")
    return 0 if rep.passed else 3


if __name__ == "__main__":
    sys.exit(main())
