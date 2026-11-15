"""FFmpeg command builders. Pure Python: builds argument lists, never imports bpy.

All clips are encoded with identical settings (H.264, yuv420p, same fps) so the final join
can use the concat demuxer with ``-c copy`` (no re-encode, no quality loss).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def stage_clip_cmd(frames_dir: Path, fps: int, out: Path, crf: int = 18, ffmpeg: str = "ffmpeg",
                   start_number: int = 1) -> list[str]:
    """PNG sequence frame_0001.png... -> H.264 mp4 (``start_number`` for ranges like the closeup hook)."""
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps),
        "-start_number", str(start_number),
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


def audio_mix_cmd(video: Path, music: Path, out: Path, duration: float, volume_db: float = -18.0,
                  fade_in: float = 0.5, fade_out: float = 1.0, ffmpeg: str = "ffmpeg") -> list[str]:
    """Mix a background track under ``video`` without re-encoding the video.

    The track is looped if it is shorter than the video and trimmed if it is longer, so the audio
    never outlasts the picture. Fades are clamped to half the duration each.
    """
    if duration <= 0:
        raise ValueError("duration must be > 0")
    fi = min(max(fade_in, 0.0), duration / 2)
    fo = min(max(fade_out, 0.0), duration / 2)
    chain = ["aresample=48000", f"volume={volume_db:g}dB"]
    if fi > 0:
        chain.append(f"afade=t=in:st=0:d={fi:.3f}")
    if fo > 0:
        chain.append(f"afade=t=out:st={duration - fo:.3f}:d={fo:.3f}")
    chain += [f"atrim=0:{duration:.3f}", "asetpts=PTS-STARTPTS"]
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", f"[1:a]{','.join(chain)}[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.3f}", "-shortest", "-movflags", "+faststart",
        str(out),
    ]


def expected_frames(frames_dir: Path, last: int, first: int = 1) -> list[Path]:
    return [Path(frames_dir) / f"frame_{i:04d}.png" for i in range(first, last + 1)]


def missing_frames(frames_dir: Path, last: int, first: int = 1) -> list[int]:
    """Frame numbers in first..last with no PNG. ffmpeg silently stops at the first gap, so check before encoding."""
    return [i for i, p in zip(range(first, last + 1), expected_frames(frames_dir, last, first)) if not p.exists()]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)
