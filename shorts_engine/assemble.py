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


def audio_mix_cmd(video: Path, music: Path | None, out: Path, duration: float, volume_db: float = -18.0,
                  fade_in: float = 0.5, fade_out: float = 1.0, ffmpeg: str = "ffmpeg",
                  sfx: list[tuple] | None = None, music_channels: int = 1) -> list[str]:
    """Mix background music and/or sound effects under ``video`` without re-encoding the video.

    * Music (optional): looped if shorter than the video, trimmed if longer, faded in/out (fades are
      clamped to half the duration each), gained by ``volume_db``.
    * ``sfx``: list of ``(wav_path, start_seconds, gain_db[, channels])``; each is delayed to its start time. Effects
      starting at or after the end of the video are skipped.
    * The result never outlasts the picture. With no music the effects sit on a silent base track.
    """
    if duration <= 0:
        raise ValueError("duration must be > 0")
    sfx = [(e[0], e[1], e[2], e[3] if len(e) > 3 else 1) for e in (sfx or []) if e[1] < duration]
    if music is None and not sfx:
        raise ValueError("nothing to mix: need music and/or sfx")
    fi = min(max(fade_in, 0.0), duration / 2)
    fo = min(max(fade_out, 0.0), duration / 2)

    def to_stereo(channels: int) -> str:
        # a plain mono->stereo upmix is 3 dB quieter; duplicating the channel keeps the level unchanged
        return "pan=stereo|c0=c0|c1=c0" if channels == 1 else "aformat=channel_layouts=stereo"

    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]
    graph: list[str] = []
    labels: list[str] = []
    n_in = 1
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        chain = ["aresample=48000", f"volume={volume_db:g}dB"]
        if fi > 0:
            chain.append(f"afade=t=in:st=0:d={fi:.3f}")
        if fo > 0:
            chain.append(f"afade=t=out:st={duration - fo:.3f}:d={fo:.3f}")
        chain += [f"atrim=0:{duration:.3f}", "asetpts=PTS-STARTPTS"]
        if not sfx:
            graph.append(f"[{n_in}:a]{','.join(chain)}[a]")
        else:
            graph.append(f"[{n_in}:a]{','.join(chain)},{to_stereo(music_channels)}[m]")
            labels.append("[m]")
        n_in += 1
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        graph.append(f"[{n_in}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[m]")
        labels.append("[m]")
        n_in += 1
    for k, (path, start, gain, channels) in enumerate(sfx):
        cmd += ["-i", str(path)]
        ms = max(0, round(start * 1000))
        graph.append(f"[{n_in}:a]aresample=48000,{to_stereo(channels)},volume={gain:g}dB,"
                     f"adelay={ms}:all=1,apad,atrim=0:{duration:.3f}[s{k}]")
        labels.append(f"[s{k}]")
        n_in += 1
    if sfx:
        # every input is padded to the full duration, so amix's 1/N scaling is constant; volume=N undoes it
        # (identical result on old and new FFmpeg, whose amix `normalize` option differs)
        graph.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0,"
                     f"volume={len(labels)},alimiter=limit=0.95,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[a]")
    cmd += ["-filter_complex", ";".join(graph),
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.3f}", "-shortest", "-movflags", "+faststart",
            str(out)]
    return cmd


def expected_frames(frames_dir: Path, last: int, first: int = 1) -> list[Path]:
    return [Path(frames_dir) / f"frame_{i:04d}.png" for i in range(first, last + 1)]


def missing_frames(frames_dir: Path, last: int, first: int = 1) -> list[int]:
    """Frame numbers in first..last with no PNG. ffmpeg silently stops at the first gap, so check before encoding."""
    return [i for i, p in zip(range(first, last + 1), expected_frames(frames_dir, last, first)) if not p.exists()]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)
