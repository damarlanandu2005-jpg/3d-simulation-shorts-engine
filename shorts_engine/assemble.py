"""FFmpeg command builders. Pure Python: builds argument lists, never imports bpy.

All clips are encoded with identical settings (H.264, yuv420p, same fps) so the final join
can use the concat demuxer with ``-c copy`` (no re-encode, no quality loss).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def stage_clip_cmd(frames_dir: Path, fps: int, out: Path, crf: int = 18, ffmpeg: str = "ffmpeg") -> list[str]:
    """PNG sequence frame_0001.png... -> H.264 mp4."""
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-start_number", "1",
        "-i", str(Path(frames_dir) / "frame_%04d.png"),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", "-an",
        str(out),
    ]


def hook_cmd(source_clip: Path, seconds: float, fps: int, out: Path, crf: int = 18, ffmpeg: str = "ffmpeg") -> list[str]:
    """Last ``seconds`` of the final (best-looking) clip, re-encoded with the shared settings."""
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-sseof", f"-{seconds:g}",
        "-i", str(source_clip),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", "-an",
        str(out),
    ]


def concat_list_text(clips: list[Path]) -> str:
    """Contents of an ffmpeg concat-demuxer list file (absolute paths, quotes escaped)."""
    lines = []
    for clip in clips:
        path = str(Path(clip).resolve()).replace("'", "'\\''")
        lines.append(f"file '{path}'")
    return "\n".join(lines) + "\n"


def concat_cmd(list_file: Path, out: Path, ffmpeg: str = "ffmpeg") -> list[str]:
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", "-movflags", "+faststart",
        str(out),
    ]


def expected_frames(frames_dir: Path, frame_count: int) -> list[Path]:
    return [Path(frames_dir) / f"frame_{i:04d}.png" for i in range(1, frame_count + 1)]


def missing_frames(frames_dir: Path, frame_count: int) -> list[int]:
    return [i for i, p in enumerate(expected_frames(frames_dir, frame_count), start=1) if not p.exists()]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)
