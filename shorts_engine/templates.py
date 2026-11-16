"""Experiment templates: the data that makes an experiment (pure Python, never imports bpy).

An ``ExperimentTemplate`` describes everything experiment-specific that the generic pipeline needs:

    parameters      physical parameters with defaults and valid ranges (``ParamDef``)
    stage progression  the one parameter that changes from stage to stage (balls 1->100, hole size, ...)
    label           on-screen label per stage
    hooks           the opening question(s), written from the experiment's own numbers
    camera          how to frame the scene (``frame_region``) so nothing important is clipped
    scene builder / event detector   names of the Blender functions (simulation.py / generate_scene.py)
    variations      physically meaningful ranges the batch generator may sample

The render pipeline (bake -> render -> events -> assemble -> audio) is shared; a new experiment adds a template
here plus a scene builder in simulation.py. A template is only registered once its Blender simulation exists
and has been run (see tests/test_experiments_blender.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import SUPPORTED_OBJECTS, ConfigError, faces_to_segments


# ---------------------------------------------------------------------------------------------- parameters
@dataclass(frozen=True)
class ParamDef:
    """A typed, range-checked experiment parameter."""
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    kind: str = "float"                # float | int | choice | square (perfect-square integer)
    choices: tuple = ()
    description: str = ""

    def check(self, value: Any, path: str) -> Any:
        if self.kind == "choice":
            if value not in self.choices:
                raise ConfigError(f"{path} must be one of {list(self.choices)}, got {value!r}")
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{path} must be a number, got {value!r}")
        if self.kind in ("int", "square") and isinstance(value, float):
            raise ConfigError(f"{path} must be an integer, got {value!r}")
        if self.kind == "square":
            try:
                faces_to_segments(value)
            except ConfigError as exc:
                raise ConfigError(f"{path}: {exc}") from exc
        if self.minimum is not None and value < self.minimum:
            raise ConfigError(f"{path} must be >= {self.minimum}, got {value}")
        if self.maximum is not None and value > self.maximum:
            raise ConfigError(f"{path} must be <= {self.maximum}, got {value}")
        if not math.isfinite(value):
            raise ConfigError(f"{path} must be finite, got {value}")
        return value


@dataclass(frozen=True)
class Region:
    """Axis-aligned region (metres) the camera must keep in frame: half-width and height above the floor."""
    half_width: float
    top: float
    bottom: float = 0.0


@dataclass(frozen=True)
class ExperimentTemplate:
    name: str
    description: str
    simulation: str                                  # "cloth" | "rigid_body"
    objects: tuple                                   # allowed experiment.object values
    default_object: str
    params: dict                                     # name -> ParamDef (experiment.params)
    stage_param: str                                 # name of the progression parameter
    stage_def: ParamDef
    default_stage_values: tuple
    label: str                                       # default label template ({stage_param}, derived values)
    label_values: Callable[[dict, Any], dict]        # (params, stage value) -> placeholders for label/hook
    hooks: tuple                                     # hook templates; placeholders from hook_values()
    frame_region: Callable[[dict, Any], Region]      # (params, stage value) -> what must stay in frame
    camera_defaults: dict = field(default_factory=dict)
    variations: dict = field(default_factory=dict)   # param -> (low, high) physical ranges for batch variation
    stage_variations: tuple = ()                     # alternative stage progressions the batch generator can pick
    events: str = "impulse"                          # event detector key (generate_scene.EVENT_DETECTORS)
    validate: Callable | None = None                 # (params, stage values, shape) -> raises ConfigError on a broken combination
    stage_extras: tuple = ()                         # other params a stage may override (the escalation beyond stage_param)
    default_extras: Callable | None = None           # (params, stage values) -> one override dict per stage
    material_defaults: dict = field(default_factory=dict)   # look of this experiment (the config's material section overrides)
    stage_meaning: str = ""

    def resolve_params(self, given: dict, path: str = "experiment.params") -> dict:
        unknown = set(given) - set(self.params)
        if unknown:
            raise ConfigError(f"unknown key(s) in '{path}': {sorted(unknown)}; allowed: {sorted(self.params)}")
        return {k: d.check(given.get(k, d.default), f"{path}.{k}") for k, d in self.params.items()}

    def check_stage_value(self, value: Any, path: str) -> Any:
        return self.stage_def.check(value, path)

    def hook_values(self, params: dict, stage_values: list, first_params: dict | None = None) -> dict:
        """Placeholders available to hook text: stage_param first/last, ratio, plus every parameter.

        ``params`` are the final stage's parameters (so {balls} is the extreme count); ``first_params`` the first stage's."""
        first, last = stage_values[0], stage_values[-1]
        vals = {**self.label_values(params, last), **params}
        vals.update(first=fmt_num(first), last=fmt_num(last),
                    total_ratio=fmt_num(last / first if first else 0))
        vals.update({f"{k}_first": v for k, v in self.label_values(first_params or params, first).items()})
        vals.update({f"{k}_last": v for k, v in self.label_values(params, last).items()})
        vals.update(stages=len(stage_values))
        return vals


def fmt_num(x: float) -> str:
    if isinstance(x, int) or float(x) == int(x):
        return f"{int(x):,}"
    return f"{x:.2f}".rstrip("0").rstrip(".")


def plural(n: int, word: str) -> str:
    return word if n == 1 else word + "S"


# ---------------------------------------------------------------------------------------------- spawn layouts
PITCH = 2.5      # centre-to-centre spacing of spawned objects in radii (> 2 + jitter, so they never start overlapping)
def spawn_positions(n: int, radius: float, spread: float, z0: float, seed: int = 0) -> list:
    """Non-overlapping start positions for ``n`` objects of ``radius`` inside a disc of ``spread``, in stacked layers.

    Deterministic for a given seed: grid positions (spacing 2.3 r) plus a small seeded jitter that cannot cause overlap.
    Returns [(x, y, z)].
    """
    import random
    rnd = random.Random(seed * 7919 + n)
    pitch = PITCH * radius
    cells = []
    k = int(spread / pitch) + 1
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            x, y = (i + 0.5 * (j % 2)) * pitch, j * pitch * 0.866
            if math.hypot(x, y) <= spread:
                cells.append((x, y))
    cells.sort(key=lambda c: (round(math.hypot(*c), 6), c))     # centre-out so a partial layer stays compact
    if not cells:
        cells = [(0.0, 0.0)]
    jitter = 0.08 * radius
    out = []
    for idx in range(n):
        layer, c = divmod(idx, len(cells))
        x, y = cells[c]
        out.append((x + rnd.uniform(-jitter, jitter), y + rnd.uniform(-jitter, jitter),
                    z0 + layer * pitch + rnd.uniform(0, jitter)))
    return out


def _cells_per_layer(radius: float, spread: float) -> int:
    pitch = PITCH * radius
    k = int(spread / pitch) + 1
    count = 0
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            if math.hypot((i + 0.5 * (j % 2)) * pitch, j * pitch * 0.866) <= spread:
                count += 1
    return max(1, count)


def collider_layout(count: int, spacing: float) -> list:
    """Centres (x, y) of ``count`` objects arranged compactly around the origin (1: centre, 2: pair, 3: triangle, 4: square...)."""
    if count == 1:
        return [(0.0, 0.0)]
    if count == 2:
        return [(-spacing / 2, 0.0), (spacing / 2, 0.0)]
    if count == 4:
        h = spacing / 2
        return [(-h, -h), (h, -h), (h, h), (-h, h)]
    r = spacing / (2 * math.sin(math.pi / count))
    return [(r * math.cos(2 * math.pi * i / count + math.pi / 2), r * math.sin(2 * math.pi * i / count + math.pi / 2))
            for i in range(count)]


# ---------------------------------------------------------------------------------------------- the templates
def _cloth_label(params, faces):
    from .config import short_face_label
    return {"faces": f"{faces:,}", "faces_short": short_face_label(faces)}


_SHAPE_WORD = {"sphere": "BALL", "cube": "CUBE", "cylinder": "CAN"}


def _balls_label(params, n):
    word = _SHAPE_WORD.get(params.get("shape", "sphere"), "BALL")
    return {"balls": f"{n:,}", "ball_word": plural(n, word), "thing": word, "things": word + "S"}


def _balls_region(p, n):
    r = p["ball_radius"]
    layers = math.ceil(n / _cells_per_layer(r, p["spread"]))
    top = p["wall_height"] + 0.3          # balls enter from above the frame; the container fills it
    return Region(half_width=p["arena_radius"] + 0.15, top=top)


def _funnel_label(p, hole):
    n = int(p["balls"])
    return {"hole_ratio": fmt_num(round(hole / p["ball_radius"], 1)), "hole": fmt_num(hole), "balls": f"{n:,}",
            "ball_word": plural(n, "BALL")}


def _funnel_region(p, hole):
    return Region(half_width=p["funnel_radius"] * 1.12, top=p["funnel_z"] + p["funnel_height"] + 0.6)


def _ring_size_word(ratio):
    for limit, word in ((2.5, "WIDE RING"), (1.8, "LOOSE RING"), (1.3, "SNUG RING"), (1.0, "TIGHT RING")):
        if ratio >= limit:
            return word
    return "TOO TIGHT"


def _ring_label(p, ratio):
    return {"hole_ratio": fmt_num(ratio), "rings": p["rings"], "ring_word": plural(p["rings"], "RING"),
            "ring_size": _ring_size_word(ratio)}


def _ring_region(p, ratio):
    return Region(half_width=p["arena_radius"] + 0.1, top=p["pole_height"] + 0.6 + 2.0 * p["ring_minor"] * p["rings"])


def ramp(final: float, n: int, start: float, integer: bool = True) -> list:
    """Escalation curve from ``start`` to ``final`` over ``n`` stages (geometric: each stage clearly more than the last)."""
    if n == 1:
        return [final]
    vals = [start * (final / start) ** (i / (n - 1)) for i in range(n)]
    if integer:
        vals = [max(1, round(v)) for v in vals]
        for i in range(1, n):                              # strictly increasing
            vals[i] = max(vals[i], vals[i - 1] + 1)
        vals[-1] = max(vals[-1], int(final))
    return vals


def _funnel_extras(p, stage_values):
    n = len(stage_values)
    return [{"balls": int(b)} for b in ramp(p["balls"], n, max(3, p["balls"] // 8))]


def _ring_extras(p, stage_values):
    n = len(stage_values)
    return [{"rings": int(r)} for r in ramp(p["rings"], n, 1)]


def _objects_label(p, n):
    return {"objects": n, "object_word": plural(n, "OBJECT")}


def _objects_region(p, n):
    pos = collider_layout(n, p["spacing"])
    half = max(max(abs(x), abs(y)) for x, y in pos) + p["object_scale"] + 0.3
    half = max(half, p["cloth_size"] / 2 * 0.6)
    return Region(half_width=half, top=p["object_scale"] * 2 + p["drop_height"] + 0.6)


def _fail(msg):
    raise ConfigError(msg)


def _check_balls(p, stages, shape):
    r, arena = p["ball_radius"], p["arena_radius"]
    if p["spread"] + r > arena * 0.95:
        _fail(f"spread ({p['spread']}) + ball_radius must fit inside arena_radius ({arena}): objects would start outside the arena")
    if 3 * r > arena:
        _fail(f"ball_radius {r} is too large for arena_radius {arena}")
    if p["wall_height"] > 0:
        settled = max(stages) * (4 / 3) * r ** 3 / (0.6 * arena ** 2)
        if settled > p["wall_height"] * 0.9:
            _fail(f"{max(stages)} objects fill the container to {settled:.2f} m, above its wall ({p['wall_height']} m); raise wall_height or widen arena_radius")
    cap = 3 * 0.8 * (arena / r) ** 2
    if max(stages) > cap:
        _fail(f"{max(stages)} objects of radius {r} do not fit in an arena of radius {arena} (limit about {int(cap)}); "
              "enlarge arena_radius or reduce the count")


def _check_funnel(p, stages, shape):
    r, R = p["ball_radius"], p["funnel_radius"]
    for h in stages:
        if h >= R * 0.8:
            _fail(f"hole_radius {h} must be well below funnel_radius {R} (< {R * 0.8:.2f})")
        if h < r * 0.5:
            _fail(f"hole_radius {h} is smaller than half a ball radius ({r}); nothing could ever pass")
    h0 = max(stages)
    volume = (1 / 3) * p["funnel_height"] * (R * R + R * h0 + h0 * h0)
    if p["balls"] * (4 / 3) * r ** 3 > 0.9 * volume:
        _fail(f"{p['balls']} balls of radius {r} do not fit in the funnel (volume {volume:.2f}); reduce balls or ball_radius")
    if 2 * r > R * 0.5:
        _fail(f"ball_radius {r} is too large relative to funnel_radius {R}")


def _check_rings(p, stages, shape):
    outer = p["pole_radius"] * max(stages) + 2 * p["ring_minor"]
    if outer > p["arena_radius"] * 0.65:
        _fail(f"ring outer radius {outer:.2f} is too large for the arena (limit {p['arena_radius'] * 0.65:.2f}); "
              "reduce the hole ratio or ring_minor, or enlarge arena_radius")
    if p["ring_minor"] > p["pole_radius"] * 3:
        _fail("ring_minor (tube radius) must not exceed three pole radii")
    if min(stages) * p["pole_radius"] < p["ring_minor"] * 0.3:
        _fail("ring hole is degenerate (smaller than a third of the tube radius)")


def _check_cloth_objects(p, stages, shape):
    for n in stages:
        extent = max(max(abs(x), abs(y)) for x, y in collider_layout(n, p["spacing"])) + p["object_scale"]
        if p["cloth_size"] < 1.6 * extent:
            _fail(f"cloth_size {p['cloth_size']} is too small to cover {n} object(s) (needs >= {1.6 * extent:.1f}); "
                  "increase cloth_size or reduce spacing/object_scale")
    if p["spacing"] < 2.0 * p["object_scale"] * 1.0 and max(stages) > 1:
        _fail(f"spacing {p['spacing']} is smaller than the object size ({2 * p['object_scale']:.1f}): objects would overlap")


_BALL_SHAPES = ("sphere", "cube", "cylinder")

TEMPLATES: dict[str, ExperimentTemplate] = {}


def register(t: ExperimentTemplate) -> ExperimentTemplate:
    TEMPLATES[t.name] = t
    return t


register(ExperimentTemplate(
    name="cloth_drape",
    description="A cloth sheet is dropped onto an object; stages repeat it at different mesh resolutions.",
    simulation="cloth", objects=SUPPORTED_OBJECTS, default_object="sphere",
    params={
        "cloth_size": ParamDef(4.4, 0.5, 30, description="side length of the square cloth sheet (metres)"),
        "drop_height": ParamDef(1.3, 0.05, 30, description="height of the sheet above the top of the object (metres)"),
    },
    stage_param="faces", stage_def=ParamDef(None, 4, 4_000_000, kind="square"),
    default_stage_values=(64, 1024, 4096, 16384),
    label="{faces_short} FACE", label_values=_cloth_label,
    hooks=("WHAT HAPPENS WHEN WE ADD {total_ratio}× MORE FACES?",),
    frame_region=lambda p, v: Region(3.0, 3.6),
    variations={"cloth_size": (3.2, 5.6), "drop_height": (0.6, 2.4)},
    events="cloth",
    stage_meaning="mesh resolution: number of cloth faces (a perfect square, e.g. 64, 1024, 4096, 16384)",
))

register(ExperimentTemplate(
    name="multiple_balls",
    description="Balls are dropped into a round arena; stages raise the number of balls (1 -> 100).",
    simulation="rigid_body", objects=_BALL_SHAPES, default_object="sphere",
    params={
        "ball_radius": ParamDef(0.2, 0.08, 0.6, description="radius of each object (m)"),
        "drop_height": ParamDef(2.0, 0.3, 12, description="height of the lowest layer above the floor (m)"),
        "spread": ParamDef(1.0, 0.2, 4.0, description="radius of the area the objects start over (m)"),
        "arena_radius": ParamDef(1.3, 1.0, 8.0, description="radius of the container that keeps objects in frame (m)"),
        "wall_height": ParamDef(3.0, 0.0, 6.0, description="height of the container wall (m); 0 = open floor"),
        "restitution": ParamDef(0.55, 0.0, 0.95, description="bounciness (0 = dead, 0.95 = super ball)"),
        "friction": ParamDef(0.5, 0.0, 2.0, description="surface friction"),
    },
    stage_param="balls", stage_def=ParamDef(None, 1, 400, kind="int"), default_stage_values=(5, 15, 30, 60, 100),
    label="{balls} {ball_word}", label_values=_balls_label,
    hooks=("WHAT HAPPENS WHEN {last} {things} DROP AT ONCE?", "HOW MANY {things} CAN ONE BOX TAKE?", "{first} {things}... NOW {last}."),
    frame_region=_balls_region, validate=_check_balls, camera_defaults={"elevation": 14.0},
    variations={"ball_radius": (0.16, 0.26), "drop_height": (1.4, 3.0), "restitution": (0.15, 0.75),
                "friction": (0.1, 1.2), "spread": (0.8, 1.05)},
    stage_variations=((5, 15, 30, 60, 100), (4, 12, 30, 70), (3, 10, 25, 50, 90, 120), (6, 20, 45, 80)),
    events="impulse", stage_meaning="number of objects dropped",
))

register(ExperimentTemplate(
    name="ball_funnel",
    description="Balls pour into a funnel; stages shrink the hole (large -> small) until the flow jams.",
    simulation="rigid_body", objects=("sphere",), default_object="sphere",
    params={
        "ball_radius": ParamDef(0.16, 0.08, 0.4, description="ball radius (m)"),
        "balls": ParamDef(60, 2, 200, kind="int", description="balls poured in the FINAL stage (earlier stages pour fewer)"),
        "funnel_radius": ParamDef(1.6, 0.8, 5.0, description="radius of the funnel opening (m)"),
        "funnel_height": ParamDef(1.8, 0.6, 5.0, description="height of the funnel cone (m)"),
        "funnel_z": ParamDef(1.0, 0.5, 4.0, description="height of the hole above the floor (m)"),
        "drop_height": ParamDef(0.8, 0.2, 6.0, description="height of the lowest ball above the funnel rim (m)"),
        "restitution": ParamDef(0.3, 0.0, 0.9),
        "friction": ParamDef(0.35, 0.0, 2.0),
    },
    stage_param="hole_radius", stage_def=ParamDef(None, 0.1, 3.0), default_stage_values=(0.8, 0.58, 0.42, 0.32, 0.24),
    label="{balls} {ball_word}", label_values=_funnel_label,
    hooks=("CAN {balls} BALLS ESCAPE A TINY HOLE?", "HOW SMALL CAN THE HOLE GET?", "WHEN DOES THE FLOW JAM?"),
    frame_region=_funnel_region, validate=_check_funnel, camera_defaults={"elevation": 40.0},
    stage_extras=("balls",), default_extras=_funnel_extras,
    variations={"balls": (45, 80), "restitution": (0.05, 0.6), "friction": (0.1, 0.9), "ball_radius": (0.13, 0.19),
                "funnel_height": (1.5, 2.2)},
    stage_variations=((0.8, 0.58, 0.42, 0.32, 0.24), (0.9, 0.6, 0.42, 0.3), (0.85, 0.6, 0.45, 0.35, 0.28, 0.22)),
    events="impulse", stage_meaning="radius of the funnel hole (m); the label shows it in ball widths",
))

register(ExperimentTemplate(
    name="ring_toss",
    description="Rings are dropped onto a pole; stages shrink the ring hole until it no longer fits over the pole.",
    simulation="rigid_body", objects=("torus",), default_object="torus",
    params={
        "pole_radius": ParamDef(0.2, 0.05, 0.5, description="pole radius (m)"),
        "pole_height": ParamDef(2.0, 0.5, 5.0, description="pole height (m)"),
        "ring_minor": ParamDef(0.11, 0.03, 0.3, description="tube radius of each ring (m)"),
        "rings": ParamDef(5, 1, 12, kind="int", description="rings dropped in the FINAL stage (earlier stages drop fewer)"),
        "arena_radius": ParamDef(1.25, 0.9, 4.0, description="radius of the low wall that keeps rings in frame (m)"),
        "wall_height": ParamDef(0.9, 0.2, 3.0, description="height of that wall (m)"),
        "drop_height": ParamDef(1.1, 0.3, 6.0, description="height of the lowest ring above the pole top (m)"),
        "tilt_degrees": ParamDef(8.0, 0.0, 45.0, description="random starting tilt of each ring"),
        "restitution": ParamDef(0.25, 0.0, 0.9),
        "friction": ParamDef(0.5, 0.0, 2.0),
    },
    stage_param="hole_ratio", stage_def=ParamDef(None, 0.3, 6.0), default_stage_values=(2.6, 2.0, 1.5, 1.15, 0.9),
    label="{ring_size}", label_values=_ring_label,
    hooks=("HOW SMALL CAN THE RING HOLE GET?", "WILL THE RINGS STILL FIT THE POLE?", "HOW MANY RINGS CAN ONE POLE TAKE?"),
    frame_region=_ring_region, validate=_check_rings, camera_defaults={"elevation": 16.0},
    stage_extras=("rings",), default_extras=_ring_extras,
    variations={"rings": (4, 7), "drop_height": (0.8, 1.8), "tilt_degrees": (0.0, 20.0), "restitution": (0.05, 0.5),
                "friction": (0.2, 1.0), "pole_height": (1.7, 2.4)},
    stage_variations=((2.6, 2.0, 1.5, 1.15, 0.9), (2.6, 1.8, 1.3, 1.05, 0.8), (2.6, 1.8, 1.3, 1.0), (2.6, 2.1, 1.7, 1.35, 1.1, 0.85)),
    events="impulse", stage_meaning="ring hole radius as a multiple of the pole radius (<1 cannot slide over the pole)",
))

register(ExperimentTemplate(
    name="cloth_objects",
    description="A cloth sheet is dropped over several objects (spheres, cubes, rings...); stages add objects.",
    simulation="cloth", objects=SUPPORTED_OBJECTS, default_object="sphere",
    params={
        "cloth_size": ParamDef(6.4, 1.0, 30),
        "drop_height": ParamDef(1.2, 0.05, 30),
        "faces": ParamDef(4096, 4, 1_000_000, kind="square", description="cloth mesh resolution"),
        "object_scale": ParamDef(0.8, 0.2, 2.0, description="object size relative to the single-object scene"),
        "spacing": ParamDef(2.3, 1.0, 6.0, description="distance between neighbouring objects (m)"),
    },
    stage_param="objects", stage_def=ParamDef(None, 1, 6, kind="int"), default_stage_values=(1, 2, 3, 4),
    label="{objects} {object_word}", label_values=_objects_label,
    hooks=("HOW MANY OBJECTS CAN ONE CLOTH COVER?", "WHAT HAPPENS WHEN THE CLOTH MEETS {last} OBJECTS?", "{first} OBJECT VS {last} OBJECTS"),
    frame_region=_objects_region, validate=_check_cloth_objects,
    variations={"cloth_size": (5.0, 7.6), "drop_height": (0.6, 2.0), "object_scale": (0.6, 1.0), "spacing": (2.0, 2.8)},
    stage_variations=((1, 2, 3, 4), (1, 2, 3, 4, 5), (1, 2, 4), (2, 3, 4, 5)),
    material_defaults={"cloth_style": "solid", "cloth_color": [0.93, 0.3, 0.5, 1.0], "cloth_metallic": 0.0, "cloth_roughness": 0.35},
    events="cloth", stage_meaning="number of objects the cloth falls on",
))


def get_template(name: Any) -> ExperimentTemplate:
    if not isinstance(name, str) or not name:
        raise ConfigError(f"experiment.type must be a non-empty string, got {name!r}")
    if name in TEMPLATES:
        return TEMPLATES[name]
    from .experiment import PLANNED_EXPERIMENTS
    hint = " (it is on the roadmap but not implemented yet)" if name in PLANNED_EXPERIMENTS else ""
    raise ConfigError(f"experiment type {name!r} is not available{hint}; supported: {sorted(TEMPLATES)}")
