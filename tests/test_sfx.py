import json
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from shorts_engine import assemble, audio_mix, events, render, timeline
from shorts_engine.config import ConfigError, from_dict, load_config
from shorts_engine.events import SimEvent, TimedEvent

ROOT = Path(__file__).resolve().parent.parent
A_PATH = str(ROOT / "configs" / "v1_1_a_baseline.json")
A = load_config(A_PATH)
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


def te(t, strength=1.0, type_="impact", sound=None):
    return TimedEvent(t, SimEvent(type_, 10, strength, sound))


# ---------------------------------------------------------------- timing
def test_event_frame_to_timestamp_uses_fps():
    assert events.frame_to_time(1, 1, 30) == 0.0          # first frame of a clip is t = 0
    assert events.frame_to_time(31, 1, 30) == pytest.approx(1.0)
    assert events.frame_to_time(31, 1, 60) == pytest.approx(0.5)
    assert events.frame_to_time(61, 31, 30) == pytest.approx(1.0)  # relative to the hook's first frame


def test_stage_offset_puts_the_event_on_the_final_timeline():
    segs = timeline.segments(A)
    assert [s.kind for s in segs] == ["hook", "stage", "stage", "stage", "stage"]
    hook_len, stage_len = 60 / 30, 90 / 30
    assert [s.start_time for s in segs] == pytest.approx([0, hook_len, hook_len + stage_len,
                                                          hook_len + 2 * stage_len, hook_len + 3 * stage_len])
    # frame 40 of the 1,024-face stage (stage index 1)
    placed = timeline.place_events(segs, {1: [SimEvent("impact", 40)]}, A.fps)
    assert len(placed) == 1 and placed[0].time == pytest.approx(hook_len + stage_len + 39 / 30)
    assert placed[0].time > 5.0                                   # NOT near the start of the video


def test_cards_shift_later_stages_when_enabled():
    cfg = replace(A, video=replace(A.video, cards=replace(A.video.cards, enabled=True)))
    segs = timeline.segments(cfg)
    assert [s.kind for s in segs][:4] == ["hook", "stage", "card", "stage"]
    assert timeline.total_seconds(cfg) == pytest.approx(14 + 3 * 15 / 30)
    assert timeline.total_seconds(A) == pytest.approx(14.0)


def test_events_in_the_hook_replay_are_placed_in_the_hook_too():
    segs = timeline.segments(A)                                    # hook shows frames 31..90 of the last stage
    placed = timeline.place_events(segs, {3: [SimEvent("impact", 45), SimEvent("impact", 10)]}, A.fps)
    times = [p.time for p in placed]
    assert times[0] == pytest.approx(14 / 30)                      # inside the hook (frame 45 - 31 = 14 frames in)
    assert len(placed) == 3                                        # frame 45 also plays in the stage clip; frame 10 only there


def test_events_use_the_configured_fps_not_a_constant():
    cfg = from_dict({"fps": 60, "duration": 2, "resolutions": [64, 256], "video": {"hook": {"mode": "none"}}})
    placed = timeline.place_events(timeline.segments(cfg), {1: [SimEvent("impact", 61)]}, cfg.fps)
    assert placed[0].time == pytest.approx(2.0 + 60 / 60)


# ---------------------------------------------------------------- strength / filtering
def test_strength_maps_to_volume():
    g = events.strength_to_gain_db
    assert g(1.0, -8) == pytest.approx(-8)
    assert g(0.5, -8) == pytest.approx(-14.02, abs=0.05)
    assert g(0.1, -8) == pytest.approx(-28)
    assert g(0.9, -8) > g(0.65, -8) > g(0.4, -8)                   # strong -> louder
    assert g(0.0, -8) == -60


def test_minimum_strength_threshold():
    kept = events.filter_events([te(1, 0.05), te(2, 0.14), te(3, 0.15), te(4, 0.9)], 0.15, 0.0)
    assert [e.time for e in kept] == [3, 4]


def test_debounce_keeps_the_stronger_event_of_a_cluster():
    kept = events.filter_events([te(1.00, 0.4), te(1.05, 0.9), te(1.10, 0.5), te(2.0, 0.3)], 0.1, 0.15)
    assert [(e.time, e.strength) for e in kept] == [(1.05, 0.9), (2.0, 0.3)]


def test_different_sounds_do_not_debounce_each_other():
    kept = events.filter_events([te(1.0, 0.8, "impact"), te(1.02, 0.8, "bounce")], 0.1, 0.15)
    assert len(kept) == 2


def test_multiple_events_boom_bounce_bounce():
    evs = [te(1.0, 0.9, "impact"), te(1.6, 0.65, "bounce"), te(2.1, 0.4, "bounce")]
    kept = events.filter_events(evs, 0.15, 0.15)
    assert [e.sound_name for e in kept] == ["soft_impact", "bounce", "bounce"]


def test_no_sound_spam_from_repeated_tiny_events():
    spam = [te(1 + i * 0.01, 0.05) for i in range(300)]
    assert events.filter_events(spam, 0.15, 0.15) == []
    loud_spam = [te(1 + i * 0.01, 0.9) for i in range(300)]       # 300 strong events within 3 s, same sound
    assert len(events.filter_events(loud_spam, 0.15, 0.15)) <= 20
    many = [te(i * 1.0, min(1.0, 0.5 + i / 100)) for i in range(60)]
    assert len(events.filter_events(many, 0.15, 0.15, max_events=10)) == 10


def test_event_validation():
    with pytest.raises(ValueError):
        SimEvent("explosion", 5)
    with pytest.raises(ValueError):
        SimEvent("impact", 5, strength=1.5)
    assert SimEvent("bounce", 5).sound_name == "bounce"
    assert SimEvent("bounce", 5, sound="whoosh").sound_name == "whoosh"


def test_every_event_type_maps_to_a_bundled_sound_file():
    for etype, sound in events.SOUND_FOR_TYPE.items():
        assert (ROOT / "assets" / "audio" / "sfx" / f"{sound}.wav").is_file(), (etype, sound)


# ---------------------------------------------------------------- detection from a distance series
def test_detect_first_contact_with_interpolated_frame_and_strength():
    d = [2.0, 1.5, 1.0, 0.5, 0.01, 0.0, 0.0, 0.0]
    (e,) = events.detect_contacts(d, 30, 0.03, 5.0)
    assert e.type == "impact" and 4 < e.frame < 5 and e.strength == pytest.approx(1.0)   # 15 m/s vs ref 5 -> clamped


def test_detect_bounce_sequence_gives_decreasing_strengths():
    # falls, bounces twice with decreasing speed, then settles
    d = [3, 2, 1, 0.02, 0.5, 1.0, 0.5, 0.02, 0.3, 0.6, 0.3, 0.02, 0.02, 0.02, 0.02]
    evs = events.detect_contacts([float(x) for x in d], 30, 0.05, 30.0, "impact", "bounce")
    assert [e.type for e in evs] == ["impact", "bounce", "bounce"]
    assert evs[0].strength >= evs[1].strength >= evs[2].strength


def test_resting_contact_jitter_produces_no_events():
    d = [1.0, 0.5, 0.03] + [0.03, 0.04, 0.035, 0.05, 0.03, 0.045] * 20     # never separates by 3x threshold
    assert len(events.detect_contacts(d, 30, 0.06, 5.0)) == 1


def test_already_touching_at_start_gives_no_arrival_event():
    assert events.detect_contacts([0.01, 0.01, 0.01], 30, 0.05, 5.0) == []


# ---------------------------------------------------------------- mixing plan
def _cfg(tmp_path, **audio):
    base = {"enabled": True, "sfx_enabled": True, "music_enabled": True}
    base.update(audio)
    return from_dict({"name": "sfxtest", "fps": 10, "duration": 2, "resolutions": [64, 256],
                      "output": {"dir": str(tmp_path), "width": 64, "height": 128},
                      "camera": {"per_stage": []}, "video": {"hook": {"mode": "none"}}, "audio": base})


def test_sfx_disabled_means_no_sfx_inputs(tmp_path):
    cfg = _cfg(tmp_path, sfx_enabled=False)
    plan = audio_mix.plan_mix(cfg, {0: [SimEvent("impact", 5)]})
    assert plan.cues == [] and plan.cmd.count("-i") == 2            # video + music only


def test_missing_sfx_asset_is_a_clear_error(tmp_path):
    cfg = _cfg(tmp_path, sfx_dir="assets/audio/nope")
    with pytest.raises(ConfigError, match="sound effect 'soft_impact' not found"):
        audio_mix.plan_mix(cfg, {0: [SimEvent("impact", 5, 0.9)]})


def test_missing_events_file_is_a_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="no events for stage 0"):
        audio_mix.load_all_events(_cfg(tmp_path))


def test_weak_events_do_not_need_their_asset(tmp_path):
    cfg = _cfg(tmp_path, sfx_dir="assets/audio/nope")
    plan = audio_mix.plan_mix(cfg, {0: [SimEvent("impact", 5, 0.05)]})   # filtered out first
    assert plan.cues == []


def test_audio_config_needs_music_or_sfx():
    with pytest.raises(ConfigError):
        from_dict({"audio": {"enabled": True, "music_enabled": False, "sfx_enabled": False}})
    with pytest.raises(ConfigError):
        from_dict({"audio": {"enabled": True, "sfx_min_strength": 2}})


def test_plan_adds_events_jobs_only_when_sfx_is_on():
    def plan(sfx, **kw):
        data = json.loads(Path(A_PATH).read_text(encoding="utf-8"))
        data["audio"]["sfx_enabled"] = sfx
        cfg = from_dict(data)
        return render.plan_jobs(cfg, A_PATH, ["blender"], True, **kw)
    kinds = [j.kind for j in plan(True)]
    assert kinds.count("events") == 4 and kinds.index("events") > kinds.index("bake")
    assert "events" not in [j.kind for j in plan(False)]
    assert "events" not in [j.kind for j in plan(True, stages=[0])]       # partial runs stay partial
    ev_job = next(j for j in plan(True) if j.kind == "events")
    assert ev_job.cmd[-2:] == ["--mode", "events"]


# ---------------------------------------------------------------- real FFmpeg
def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def probe_json(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"]


def window_rms_db(path, start, dur):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(dur), "-i", str(path), "-vn",
                        "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr).group(1))


@needs_ffmpeg
def test_music_plus_sfx_end_to_end(tmp_path):
    cfg = _cfg(tmp_path, music_enabled=True)                        # 2 stages x 2 s = 4 s at 10 fps, no hook
    root = cfg.root_dir
    root.mkdir(parents=True)
    ff("-f", "lavfi", "-i", "testsrc=size=64x128:rate=10:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(cfg.silent_video_path()))
    events.save_events(cfg.stage_events_path(0), [SimEvent("impact", 6, 0.9), SimEvent("landing", 12, 0.5)], 10, 0)
    events.save_events(cfg.stage_events_path(1), [SimEvent("impact", 11, 1.0)], 10, 1)
    assert audio_mix.main(["--config", _write(tmp_path, cfg)]) == 0

    streams = probe_json(cfg.final_video_path())
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    a = float(next(s for s in streams if s["codec_type"] == "audio")["duration"])
    v = float(next(s for s in streams if s["codec_type"] == "video")["duration"])
    assert a <= v + 0.03 and a >= v - 0.1                           # audio duration matches the video

    tl = json.loads((root / "audio_timeline.json").read_text())
    assert [round(c["time"], 2) for c in tl["sfx"]] == [0.5, 1.1, 3.0]     # (6-1)/10, (12-1)/10, 2 + (11-1)/10

    # music-only render of the same video for comparison: the impact windows must be louder with SFX
    plain = tmp_path / "music_only.mp4"
    subprocess.run(assemble.audio_mix_cmd(cfg.silent_video_path(), cfg.music_path(), plain, 4.0, -18, 0.5, 1.0), check=True)
    for t in (0.5, 3.0):
        assert window_rms_db(cfg.final_video_path(), t, 0.3) > window_rms_db(plain, t, 0.3) + 3
    assert window_rms_db(cfg.final_video_path(), 2.2, 0.3) == pytest.approx(window_rms_db(plain, 2.2, 0.3), abs=1.0)


@needs_ffmpeg
def test_sfx_only_without_music_still_has_an_audio_stream(tmp_path):
    cfg = _cfg(tmp_path, music_enabled=False)
    cfg.root_dir.mkdir(parents=True)
    ff("-f", "lavfi", "-i", "testsrc=size=64x128:rate=10:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
       str(cfg.silent_video_path()))
    events.save_events(cfg.stage_events_path(0), [SimEvent("impact", 6, 0.9)], 10, 0)
    events.save_events(cfg.stage_events_path(1), [], 10, 1)
    assert audio_mix.main(["--config", _write(tmp_path, cfg)]) == 0
    assert "audio" in {s["codec_type"] for s in probe_json(cfg.final_video_path())}
    assert window_rms_db(cfg.final_video_path(), 0.45, 0.3) > window_rms_db(cfg.final_video_path(), 2.5, 0.3) + 10


@needs_ffmpeg
def test_louder_strength_gives_louder_sfx(tmp_path):
    levels = {}
    for strength in (1.0, 0.3):
        d = tmp_path / str(strength)
        cfg = _cfg(d, music_enabled=False)
        cfg.root_dir.mkdir(parents=True)
        ff("-f", "lavfi", "-i", "testsrc=size=64x128:rate=10:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           str(cfg.silent_video_path()))
        events.save_events(cfg.stage_events_path(0), [SimEvent("impact", 6, strength)], 10, 0)
        events.save_events(cfg.stage_events_path(1), [], 10, 1)
        assert audio_mix.main(["--config", _write(d, cfg)]) == 0
        levels[strength] = window_rms_db(cfg.final_video_path(), 0.45, 0.4)
    assert levels[1.0] - levels[0.3] == pytest.approx(20 * __import__("math").log10(1 / 0.3), abs=1.5)


def _write(tmp_path, cfg):
    """Re-serialise the test config to disk so the CLI can load it."""
    from dataclasses import asdict
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(asdict(cfg)))
    return str(path)
