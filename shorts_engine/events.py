"""Simulation events -> timed sound-effect cues (pure Python, no bpy).

A simulation reports *what happened and how hard* as a list of ``SimEvent`` (a type, a frame and a
strength in 0..1). Everything after that -- thresholds, debouncing, stage offsets, volume, FFmpeg --
is shared, so a future ball / ring / paper simulation only has to emit events.

Frames are Blender frames (1-based). Within a clip, frame ``first`` is at t = 0, so
``t = (frame - first) / fps``.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

# event type -> default sound name (file assets/audio/sfx/<sound>.wav). An event can override with `sound`.
# roll/splash have no dedicated asset yet and reuse the closest one.
SOUND_FOR_TYPE = {
    "impact": "soft_impact",
    "collision": "soft_impact",
    "bounce": "bounce",
    "contact": "soft_landing",
    "landing": "soft_landing",
    "roll": "soft_landing",
    "whoosh": "whoosh",
    "splash": "whoosh",
}
EVENT_TYPES = tuple(SOUND_FOR_TYPE)


@dataclass
class SimEvent:
    type: str
    frame: float            # may be fractional (sub-frame interpolation)
    strength: float = 1.0   # 0..1, drives volume
    sound: str | None = None  # overrides SOUND_FOR_TYPE[type]
    source: str = ""        # what produced it, e.g. "Collider" (informational)

    def __post_init__(self):
        if self.type not in SOUND_FOR_TYPE:
            raise ValueError(f"unknown event type {self.type!r}; allowed: {', '.join(EVENT_TYPES)}")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"event strength must be within 0..1, got {self.strength}")
        if self.frame < 1:
            raise ValueError(f"event frame must be >= 1, got {self.frame}")

    @property
    def sound_name(self) -> str:
        return self.sound or SOUND_FOR_TYPE[self.type]


@dataclass
class TimedEvent:
    """An event placed on the FINAL video timeline."""
    time: float
    event: SimEvent
    stage: int | None = None

    @property
    def sound_name(self) -> str:
        return self.event.sound_name

    @property
    def strength(self) -> float:
        return self.event.strength


def frame_to_time(frame: float, first_frame: int, fps: float) -> float:
    return (frame - first_frame) / fps


def strength_to_gain_db(strength: float, base_db: float, floor_db: float = -60.0) -> float:
    """Amplitude follows strength: 1.0 -> base_db, 0.5 -> base_db - 6 dB, 0.1 -> base_db - 20 dB."""
    if strength <= 0:
        return floor_db
    return max(floor_db, base_db + 20.0 * math.log10(min(strength, 1.0)))


def filter_events(timed: list[TimedEvent], min_strength: float, min_gap: float, max_events: int = 0) -> list[TimedEvent]:
    """Anti-spam. (1) drop weak events, (2) merge events of the same sound closer than ``min_gap`` seconds
    (the stronger one survives), (3) optionally keep only the ``max_events`` strongest. Time-ordered result."""
    kept: list[TimedEvent] = []
    last_by_sound: dict[str, int] = {}
    for ev in sorted((e for e in timed if e.strength >= min_strength), key=lambda e: e.time):
        idx = last_by_sound.get(ev.sound_name)
        if idx is not None and ev.time - kept[idx].time < min_gap:
            if ev.strength > kept[idx].strength:
                kept[idx] = ev
            continue
        last_by_sound[ev.sound_name] = len(kept)
        kept.append(ev)
    if max_events and len(kept) > max_events:
        keep_ids = {id(e) for e in sorted(kept, key=lambda e: -e.strength)[:max_events]}
        kept = [e for e in kept if id(e) in keep_ids]
    return sorted(kept, key=lambda e: e.time)


def detect_contacts(distances: list[float], fps: float, threshold: float, ref_speed: float,
                    first_type: str = "impact", next_type: str = "bounce", source: str = "",
                    rearm: float = 3.0, rearm_frames: int = 2) -> list[SimEvent]:
    """Find contact events from a per-frame 'distance between object and surface' series.

    ``distances[0]`` is frame 1. A contact starts when the distance falls to ``threshold`` or below; its
    frame is linearly interpolated inside the frame step and its strength is the peak closing speed just before
    contact divided by ``ref_speed`` (clamped to 1). After contact the surfaces must separate beyond
    ``rearm * threshold`` for ``rearm_frames`` frames before another contact counts as a ``next_type``
    event, so resting contact and jitter never produce events.
    """
    events: list[SimEvent] = []
    if len(distances) < 2 or ref_speed <= 0:
        return events
    touching = distances[0] <= threshold      # already touching at frame 1: no 'arrival' event
    apart = 0
    n_contacts = 0
    for i in range(1, len(distances)):
        prev, cur = distances[i - 1], distances[i]
        if touching:
            apart = apart + 1 if cur > threshold * rearm else 0
            if apart >= rearm_frames:
                touching, apart = False, 0
            continue
        if cur <= threshold < prev:
            frac = (prev - threshold) / (prev - cur)
            frame = i + frac           # frame index i-1 is Blender frame i; add the fraction into the step
            # peak closing speed over the last 3 steps (the cloth is already slowing inside the contact step)
            speed = max((distances[k - 1] - distances[k]) * fps for k in range(max(1, i - 2), i + 1))
            strength = max(0.0, min(1.0, speed / ref_speed))
            events.append(SimEvent(first_type if n_contacts == 0 else next_type, round(frame, 3),
                                   round(strength, 3), source=source))
            n_contacts += 1
            touching = True
    return events


def save_events(path: Path, events: list[SimEvent], fps: float, stage: int, extra: dict | None = None) -> None:
    data = {"version": 1, "fps": fps, "stage": stage, "events": [asdict(e) for e in events]}
    if extra:
        data["debug"] = extra
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1))


def load_events(path: Path) -> list[SimEvent]:
    data = json.loads(Path(path).read_text())
    return [SimEvent(**e) for e in data["events"]]


def detect_impulses(traj, fps: float, gravity: float, ref_speed: float, radii=None, ground_z: float = 0.0,
                    names=None, threshold: float = 0.12, rearm_frames: int = 3, source: str = "") -> list[SimEvent]:
    """Collision events for any set of rigid bodies from their trajectories alone (no geometry needed).

    ``traj`` has shape (frames, objects, 3); frame 0 is Blender frame 1. A body that is only falling, rolling or
    resting changes velocity by at most gravity*dt per frame; anything beyond that is an impulse from a contact
    (ground, wall, funnel, another body). The excess speed change divided by ``ref_speed`` is the strength.
    Peaks are taken per body and a body must stay quiet for ``rearm_frames`` before it can trigger again.

    Event type: a hard hit near the floor is a ``bounce`` (soft ones a ``landing``); hits elsewhere are ``collision``.
    """
    import numpy as np

    traj = np.asarray(traj, dtype=float)
    if traj.ndim != 3 or traj.shape[0] < 4 or ref_speed <= 0:
        return []
    frames, n, _ = traj.shape
    radii = np.full(n, 0.2) if radii is None else np.asarray(radii, dtype=float)
    vel = np.diff(traj, axis=0) * fps                          # vel[k] = velocity over (frame k+1 -> k+2)
    acc = np.diff(vel, axis=0)                                 # change of velocity per frame step
    acc[..., 2] += gravity / fps                               # remove the free-fall part (gravity * dt)
    excess = np.linalg.norm(acc, axis=2)                       # (frames-2, n): impulse speed per body
    strength = np.clip(excess / ref_speed, 0.0, 1.0)
    events: list[SimEvent] = []
    for j in range(n):
        s = strength[:, j]
        last = -10 ** 9
        for k in range(len(s)):
            if s[k] < threshold:
                continue
            lo, hi = max(0, k - 1), min(len(s), k + 2)
            if s[k] < s[lo:hi].max() or k - last <= rearm_frames:   # local peak only, then re-arm
                continue
            last = k
            frame = k + 2                                      # change observed between frame k+2 and k+3 -> contact near k+2.5
            z = traj[min(k + 1, frames - 1), j, 2]
            near_floor = z - radii[j] <= ground_z + 0.08
            hit_floor = near_floor and vel[k, j, 2] < -0.15          # was moving down into the floor
            etype = "collision"
            if hit_floor:
                etype = "bounce" if s[k] >= 0.3 else "landing"
            events.append(SimEvent(etype, float(frame) + 0.5, round(float(s[k]), 3),
                                   source=(names[j] if names is not None else f"body_{j}") if not source else source))
    events.sort(key=lambda e: e.frame)
    return events
