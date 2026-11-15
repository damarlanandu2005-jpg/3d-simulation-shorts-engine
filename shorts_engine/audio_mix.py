"""Final audio step: place sound effects on the final timeline, mix them with the music, mux into the MP4.

    python -m shorts_engine.audio_mix --config CONFIG [--skip-extras]

Reads the silent video (``<name>_silent.mp4``) and, when SFX are on, each stage's ``events.json`` (written by
``generate_scene.py --mode events``). Writes ``<name>.mp4`` and ``audio_timeline.json`` (the final cue list,
handy for checking sync). Pure Python + FFmpeg; no Blender needed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass

from . import assemble, timeline
from .config import Config, ConfigError, load_config
from .events import TimedEvent, filter_events, load_events, strength_to_gain_db


@dataclass
class MixPlan:
    cmd: list
    duration: float
    cues: list  # [{time, type, sound, strength, gain_db, stage}] after filtering


def probe_channels(path) -> int:
    """Channel count of an audio file (1 if it cannot be probed)."""
    if not shutil.which("ffprobe"):
        return 1
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return int(out.stdout.strip())
    except ValueError:
        return 1


def load_all_events(cfg: Config) -> dict:
    out = {}
    for st in cfg.stages():
        path = cfg.stage_events_path(st.index)
        if not path.is_file():
            raise ConfigError(f"no events for stage {st.index}: {path} is missing "
                              "(run the bake step with audio.sfx_enabled=true, or set audio.sfx_enabled=false)")
        out[st.index] = load_events(path)
    return out


def select_cues(cfg: Config, timed: list[TimedEvent]) -> list[TimedEvent]:
    a = cfg.audio
    return filter_events(timed, a.sfx_min_strength, a.sfx_min_gap, a.sfx_max_events)


def plan_mix(cfg: Config, events_by_stage: dict | None = None, skip_extras: bool = False,
             ffmpeg: str = "ffmpeg") -> MixPlan:
    a = cfg.audio
    segs = timeline.segments(cfg, skip_extras)
    duration = sum(s.frames for s in segs) / cfg.fps
    music = None
    if a.music_enabled:
        music = cfg.music_path()
        if not music.is_file():
            raise ConfigError(f"audio.music file not found: {music} (set audio.music_enabled=false or fix the path)")
    cues: list[TimedEvent] = []
    sfx = []
    if a.sfx_enabled:
        cues = select_cues(cfg, timeline.place_events(segs, events_by_stage or {}, cfg.fps))
        for c in cues:
            path = cfg.sfx_path(c.sound_name)
            if not path.is_file():
                raise ConfigError(f"sound effect '{c.sound_name}' not found: {path} "
                                  f"(needed by a '{c.event.type}' event; add the file or set audio.sfx_enabled=false)")
            sfx.append((path, c.time, strength_to_gain_db(c.strength, a.sfx_volume_db), probe_channels(path)))
    if music is None and not sfx:
        raise ConfigError("audio is enabled but there is nothing to mix (no music and no sound-effect events)")
    cmd = assemble.audio_mix_cmd(cfg.silent_video_path(), music, cfg.final_video_path(), duration,
                                 a.volume_db, a.fade_in, a.fade_out, ffmpeg, sfx=sfx,
                                 music_channels=probe_channels(music) if music else 1)
    cue_info = [{"time": round(c.time, 3), "type": c.event.type, "sound": c.sound_name,
                 "strength": c.strength, "gain_db": round(g, 2), "stage": c.stage}
                for c, (_, _, g, _) in zip(cues, sfx)]
    return MixPlan(cmd, duration, cue_info)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="audio_mix")
    p.add_argument("--config", required=True)
    p.add_argument("--skip-extras", action="store_true")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    if not cfg.audio.enabled:
        print("audio.enabled is false; nothing to do")
        return 0
    try:
        events = load_all_events(cfg) if cfg.audio.sfx_enabled else {}
        plan = plan_mix(cfg, events, args.skip_extras)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    (cfg.root_dir / "audio_timeline.json").write_text(
        json.dumps({"duration": plan.duration, "fps": cfg.fps, "sfx": plan.cues}, indent=1))
    print(f"final timeline {plan.duration:.2f}s; sound effects: {len(plan.cues)}")
    for c in plan.cues:
        print(f"  t={c['time']:7.3f}s  {c['type']:<9} -> {c['sound']:<13} strength {c['strength']:.2f}  {c['gain_db']:+.1f} dB")
    proc = subprocess.run(plan.cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-3000:] + "\n")
        return proc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
