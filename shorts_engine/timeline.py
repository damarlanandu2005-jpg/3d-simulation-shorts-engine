"""Layout of the final video: which clip plays when. Used for audio placement (pure Python, no bpy).

Order: [hook] -> stage 0 -> [card 0] -> stage 1 -> ... Every clip is encoded at the same fps, so the
start time of a segment is the sum of the frame counts before it divided by fps.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .events import SimEvent, TimedEvent, frame_to_time


@dataclass
class Segment:
    kind: str            # hook | stage | card
    stage: int | None    # stage whose simulation is shown (None for cards)
    first: int           # first simulation frame shown (1-based)
    last: int
    start_time: float = 0.0

    @property
    def frames(self) -> int:
        return self.last - self.first + 1


def segments(cfg: Config, skip_extras: bool = False) -> list[Segment]:
    stages = cfg.stages()
    hook_mode = cfg.video.hook.mode
    if skip_extras and hook_mode == "closeup":
        hook_mode = "tail"
    cards = [] if skip_extras else cfg.cards()
    out: list[Segment] = []
    if hook_mode == "closeup" or (hook_mode == "tail" and cfg.video.hook_seconds > 0):
        first, last = cfg.hook_frame_range()
        out.append(Segment("hook", len(stages) - 1, first, last))
    for st in stages:
        out.append(Segment("stage", st.index, 1, cfg.frame_count))
        if st.index < len(cards):
            out.append(Segment("card", None, 1, cards[st.index].frames))
    t = 0.0
    for seg in out:
        seg.start_time = t
        t += seg.frames / cfg.fps
    return out


def total_seconds(cfg: Config, skip_extras: bool = False) -> float:
    return sum(s.frames for s in segments(cfg, skip_extras)) / cfg.fps


def place_events(segs: list[Segment], events_by_stage: dict[int, list[SimEvent]], fps: float) -> list[TimedEvent]:
    """Map per-stage simulation events onto the final timeline (an event is placed in every segment that shows
    its frame, e.g. in the replayed hook as well as in the stage clip)."""
    timed: list[TimedEvent] = []
    for seg in segs:
        if seg.stage is None:
            continue
        for ev in events_by_stage.get(seg.stage, []):
            if seg.first <= ev.frame <= seg.last + 1 - 1e-9:
                timed.append(TimedEvent(seg.start_time + frame_to_time(ev.frame, seg.first, fps), ev, seg.stage))
    return sorted(timed, key=lambda t: t.time)
