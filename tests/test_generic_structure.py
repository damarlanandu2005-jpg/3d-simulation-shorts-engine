"""Phases 6-8 on non-cloth experiments: Shorts structure/hook, and event-driven audio placement."""
import numpy as np

from shorts_engine import audio_mix, events, timeline
from shorts_engine.config import from_dict
from shorts_engine.events import SimEvent


def cfg(**extra):
    d = {"schema_version": 2, "name": "g", "experiment": {"type": "multiple_balls"}, "simulation": {"duration": 3.0},
         "stages": [{"params": {"balls": n}} for n in (1, 10, 50)],
         "audio": {"enabled": True, "music_enabled": False, "sfx_enabled": True},
         "hook": {"mode": "closeup", "seconds": 2.0, "window": "start", "text": "auto"}}
    d.update(extra)
    return from_dict(d)


def test_structure_is_hook_then_stages_with_no_cards():
    c = cfg()
    segs = timeline.segments(c)
    assert [s.kind for s in segs] == ["hook", "stage", "stage", "stage"]
    assert timeline.total_seconds(c) == 2.0 + 3 * 3.0
    assert [round(s.start_time, 3) for s in segs] == [0.0, 2.0, 5.0, 8.0]


def test_events_inside_the_hook_window_sound_in_the_hook_and_in_the_stage():
    c = cfg()
    by_stage = {0: [], 1: [], 2: [SimEvent("bounce", 20.0, 0.9)]}        # impact at 0.63 s of the last stage's sim
    placed = timeline.place_events(timeline.segments(c), by_stage, c.fps)
    times = sorted(round(t.time, 3) for t in placed)
    assert times == [round((20 - 1) / 30, 3), round(8.0 + (20 - 1) / 30, 3)]


def test_event_driven_audio_cues_for_multiple_impacts():
    fps = 30
    traj = np.zeros((90, 3, 3))
    for j, t_hit in enumerate((15, 30, 45)):                              # three balls landing one after another
        for i in range(90):
            t = i / fps
            tt = t_hit / fps
            traj[i, j, 2] = max(0.2, 0.2 + 0.5 * 9.81 * tt ** 2 - 0.5 * 9.81 * t ** 2) if i < t_hit else 0.2
            if i >= t_hit:
                traj[i, j, 2] = 0.2 + max(0.0, 0.3 - abs(i - t_hit) * 0.05) * (i < t_hit + 6)
    ev = events.detect_impulses(traj, fps, 9.81, 6.0, [0.2] * 3, names=["a", "b", "c"])
    assert len(ev) >= 3 and sorted({e.source for e in ev}) == ["a", "b", "c"]
    c = cfg()
    plan = audio_mix.plan_mix(c, {0: ev, 1: [], 2: []})
    assert plan.cues and all(0 <= cue["time"] <= plan.duration for cue in plan.cues)
    assert {cue["sound"] for cue in plan.cues} <= {"bounce", "soft_landing", "soft_impact"}


def test_sound_spam_is_limited_for_100_simultaneous_impacts():
    c = cfg(audio={"enabled": True, "music_enabled": False, "sfx_enabled": True, "sfx_max_events": 24})
    burst = [SimEvent("bounce", 20.0 + (i % 5) * 0.2, 0.3 + (i % 7) / 10, source=f"b{i}") for i in range(100)]
    plan = audio_mix.plan_mix(c, {0: [], 1: [], 2: burst})
    assert 0 < len(plan.cues) <= 24
