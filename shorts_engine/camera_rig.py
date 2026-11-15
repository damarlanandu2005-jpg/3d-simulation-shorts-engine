"""Camera framing and motion rules (pure Python, no bpy).

``fit_camera`` turns "this region must stay in frame" (from the experiment template) into the engine's camera
numbers (distance, height, target_z) for a named preset, using the real vertical-sensor geometry and the 9:16
frame, so important objects are not clipped. ``motion_offsets`` gives per-frame camera moves.
"""
from __future__ import annotations

import math

PRESETS = ("wide", "close", "top", "side")
MOTIONS = ("static", "push_in", "follow", "impact")
SENSOR_HEIGHT = 36.0            # camera.py uses a vertical sensor fit with a 36 mm sensor
LABEL_MARGIN = 1.18             # the label/hook text uses the top of the frame
# preset -> (elevation degrees, distance scale, target height fraction of region)
_PRESET = {"wide": (24.0, 1.0, 0.42), "side": (3.0, 1.0, 0.42), "top": (82.0, 1.0, 0.0), "close": (18.0, 0.62, 0.30)}


def fit_camera(half_width: float, top: float, bottom: float = 0.0, preset: str = "wide",
               focal: float = 50.0, aspect: float = 9 / 16, margin: float = 1.12, elevation: float | None = None) -> dict:
    """Camera that keeps a region (half_width wide each side, from ``bottom`` to ``top``) inside a vertical frame."""
    if preset not in _PRESET:
        raise ValueError(f"unknown camera preset {preset!r}; choose from {PRESETS}")
    elev_deg, scale, frac = _PRESET[preset]
    if elevation is not None and preset in ("wide", "close"):     # experiment-specific viewing angle (e.g. look into a funnel)
        elev_deg = elevation
    e = math.radians(elev_deg)
    tan_v = (SENSOR_HEIGHT / 2) / focal / LABEL_MARGIN     # the label/hook text uses the top of the frame
    tan_h = (SENSOR_HEIGHT / 2) / focal * aspect
    height_extent = top - bottom
    tz = bottom if preset == "top" else bottom + height_extent * frac
    fwd = (0.0, math.cos(e), -math.sin(e))                # camera sits at -y, above the target, looking at it
    up = (0.0, math.sin(e), math.cos(e))
    need = 0.0
    for x in (-half_width, half_width):                   # every corner of the region must project inside the frame
        for y in (-half_width, half_width):
            for z in (bottom, top):
                p = (x, y, z - tz)
                depth_offset = p[1] * fwd[1] + p[2] * fwd[2]          # corner depth relative to the target depth
                lateral_up = abs(p[1] * up[1] + p[2] * up[2])
                need = max(need, abs(x) / tan_h - depth_offset)
                if preset != "top":                                    # looking straight down the up axis is the footprint
                    need = max(need, lateral_up / tan_v - depth_offset)
                else:
                    need = max(need, abs(y) / tan_v - depth_offset)
    d = margin * need * scale
    if preset == "close":                                  # a tighter shot may crop the sides on purpose; keep >= 60%
        d = max(d, margin * (half_width / tan_h) * 0.6)
    return {"distance": round(d * math.cos(e), 3), "height": round(tz + d * math.sin(e), 3), "target_z": round(tz, 3)}


def smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def motion_offsets(motion: str, frame: int, frames: int, event_frame: int | None = None) -> dict:
    """Per-frame camera change: {'distance_scale', 'target_follow'} (1.0 / 0.0 = unchanged)."""
    if motion not in MOTIONS:
        raise ValueError(f"unknown camera motion {motion!r}; choose from {MOTIONS}")
    t = (frame - 1) / max(1, frames - 1)
    if motion == "push_in":                                # slow push towards the final result
        return {"distance_scale": 1.0 - 0.16 * smoothstep(t), "target_follow": 0.0}
    if motion == "follow":
        return {"distance_scale": 1.0, "target_follow": 0.6}
    if motion == "impact" and event_frame is not None:     # quick punch-in around the strongest event, then ease out
        k = 1.0 - min(1.0, abs(frame - event_frame) / 18.0)
        return {"distance_scale": 1.0 - 0.14 * smoothstep(k), "target_follow": 0.0}
    return {"distance_scale": 1.0, "target_follow": 0.0}
