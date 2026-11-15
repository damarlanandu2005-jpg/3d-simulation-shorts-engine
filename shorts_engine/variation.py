"""Parameter variation system (pure Python): physically meaningful variations of an experiment.

A variation changes the *physical question* (object count, size, bounciness, friction, drop height, hole size,
object shape, mesh density, stage progression...), never just a colour. Every variation has

    * its own seed (derived from the master seed and its index, so a batch is reproducible),
    * a changed-parameter record (what physically differs from the template defaults),
    * a minimum distance to the others in its batch (no near-duplicates).

``generate_variations`` returns ready-to-run experiment configs (schema v2) plus that metadata.
"""
from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import dataclass, field

from .config import ConfigError, from_dict
from .templates import ExperimentTemplate, get_template

PRESETS = {
    # fast production / testing preset
    "720p": {"output": {"width": 720, "height": 1280}, "render": {"samples": 16, "denoise": False}},
    # quality preset
    "1080p": {"output": {"width": 1080, "height": 1920}, "render": {"samples": 32, "denoise": False}},
}
MIN_CHANGE_FRACTION = 0.10      # a variation must move at least one parameter by >= 10% of its allowed variation range


def derive_seed(master_seed: int, index: int) -> int:
    h = hashlib.sha256(f"{master_seed}:{index}".encode()).hexdigest()
    return int(h[:8], 16)


def production_base(preset: str = "720p") -> dict:
    """Experiment-config skeleton shared by all variations (the production look: closeup hook, music + SFX)."""
    if preset not in PRESETS:
        raise ConfigError(f"unknown preset {preset!r}; choose from {sorted(PRESETS)}")
    base = {"schema_version": 2, "simulation": {"fps": 30, "duration": 3.0},
            "camera": {"preset": "wide", "motion": "static"},
            "hook": {"mode": "closeup", "seconds": 2.0, "text": "auto"},
            "audio": {"enabled": True, "music_enabled": True, "sfx_enabled": True}}
    for k, v in PRESETS[preset].items():
        base[k] = dict(v)
    base["output"]["dir"] = "output"
    return base


@dataclass
class Variation:
    name: str
    seed: int
    index: int
    experiment: str
    config: dict
    changed: dict                       # parameter -> value, only what differs from the template defaults
    stage_values: list
    shape: str
    vector: dict = field(default_factory=dict)       # normalised coordinates used for the distance metric

    def info(self) -> dict:
        return {"name": self.name, "seed": self.seed, "index": self.index, "experiment": self.experiment,
                "changed": self.changed, "stage_values": self.stage_values, "shape": self.shape}


def _candidate(base: dict, t: ExperimentTemplate, shape: str, changed: dict, stage_values: list) -> dict:
    cfg = copy.deepcopy(base)
    cfg["name"] = "candidate"
    if t.name == "cloth_drape":
        cfg["camera"] = {}
        cfg["hook"] = {"mode": "closeup", "seconds": 2.0, "text": ""}
    cfg["experiment"] = {"type": t.name, "object": shape, "params": changed}
    cfg["stages"] = [{"params": {t.stage_param: v}} for v in stage_values]
    return cfg


def _sig(x: float, digits: int = 3) -> float:
    return float(f"{x:.{digits}g}")


def _sample(rng: random.Random, t: ExperimentTemplate, name: str):
    lo, hi = t.variations[name]
    d = t.params[name]
    v = rng.uniform(lo, hi)
    return int(round(v)) if d.kind in ("int", "square") else _sig(v)


def _vector(t: ExperimentTemplate, params: dict, stage_idx: int, shape: str) -> dict:
    vec = {}
    for k, (lo, hi) in t.variations.items():
        vec[k] = (params[k] - lo) / (hi - lo) if hi > lo else 0.0
    vec["_stages"] = float(stage_idx)
    vec["_shape"] = float(t.objects.index(shape)) if shape in t.objects else 0.0
    return vec


def vector_of(experiment: str, params: dict, stage_values: list, shape: str) -> dict:
    """Normalised coordinates of an existing configuration (params = resolved experiment parameters)."""
    t = get_template(experiment)
    stage_idx = 0
    if list(stage_values) != list(t.default_stage_values) and t.stage_variations:
        alt = [list(x) for x in t.stage_variations]
        stage_idx = alt.index(list(stage_values)) + 1 if list(stage_values) in alt else len(alt) + 1
    full = {n: params.get(n, t.params[n].default) for n in t.variations}
    return _vector(t, full, stage_idx, shape)


def distance(a: dict, b: dict) -> float:
    """Mean normalised difference over the physical dimensions (stage progression / shape count as 0 or 1)."""
    keys = set(a) | set(b)
    total = 0.0
    for k in keys:
        x, y = a.get(k, 0.0), b.get(k, 0.0)
        total += (1.0 if x != y else 0.0) if k.startswith("_") else abs(x - y)
    return total / max(1, len(keys))


def _meaningful(t: ExperimentTemplate, changed: dict, stage_idx: int, shape: str) -> bool:
    if stage_idx != 0 or shape != t.default_object:
        return True
    for k, v in changed.items():
        lo, hi = t.variations[k]
        if abs(v - t.params[k].default) >= MIN_CHANGE_FRACTION * (hi - lo):
            return True
    return False


def generate_variations(experiment: str, count: int, master_seed: int = 0, preset: str = "720p",
                        base: dict | None = None, min_distance: float = 0.12, avoid: list | None = None,
                        first_index: int = 0) -> list[Variation]:
    """``count`` distinct, validated variations of ``experiment`` (deterministic for a given master seed).

    ``avoid`` is a list of vectors (see ``vector_of``) of videos that already exist: new variations keep a minimum
    distance from them too (content diversity across batches). ``first_index`` continues numbering of a batch.
    """
    t = get_template(experiment)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ConfigError(f"variations must be an integer >= 1, got {count!r}")
    if not t.variations:
        raise ConfigError(f"experiment {experiment!r} defines no variation ranges")
    base = copy.deepcopy(base) if base is not None else production_base(preset)
    out: list[Variation] = []
    for index in range(first_index, first_index + count):
        seed = derive_seed(master_seed, index)
        rng = random.Random(seed)
        threshold = min_distance
        accepted = None
        for attempt in range(200):
            if attempt and attempt % 40 == 0:
                threshold /= 2                                      # ranges are finite; relax gradually, never to zero
            k = rng.randint(min(2, len(t.variations)), min(3, len(t.variations)))
            names = sorted(rng.sample(sorted(t.variations), k))
            changed = {n: _sample(rng, t, n) for n in names}
            stage_idx = rng.randrange(len(t.stage_variations) + 1) if t.stage_variations else 0
            stage_values = list(t.default_stage_values) if stage_idx == 0 else list(t.stage_variations[stage_idx - 1])
            shape = rng.choice(t.objects) if len(t.objects) > 1 and t.name != "cloth_drape" else t.default_object
            if t.name in ("cloth_drape", "cloth_objects"):
                shape = rng.choice(t.objects) if rng.random() < 0.5 else t.default_object
            if not _meaningful(t, changed, stage_idx, shape):
                continue
            params = {n: t.params[n].default for n in t.variations}
            params.update(changed)
            vec = _vector(t, params, stage_idx, shape)
            try:                                                    # skip physically broken combinations
                from_dict(_candidate(base, t, shape, changed, stage_values))
            except ConfigError:
                continue
            if all(distance(vec, o.vector) >= threshold for o in [*out, *[Variation('', 0, 0, '', {}, {}, [], '', v) for v in (avoid or [])]]):
                accepted = (changed, stage_values, shape, vec)
                break
        if accepted is None:
            raise ConfigError(f"could not find {count} sufficiently different variations of {experiment}")
        changed, stage_values, shape, vec = accepted
        name = f"{experiment}_s{master_seed}_{index:03d}"
        cfg = copy.deepcopy(base)
        cfg.update(name=name, seed=seed % (2 ** 31))
        if t.name == "cloth_drape":                                 # the V1 cloth drape has no camera preset / auto hook
            cfg["camera"] = {}
            cfg["hook"] = {"mode": "closeup", "seconds": 2.0, "text": "WHAT HAPPENS WHEN\nWE ADD {total_ratio}\u00d7\nMORE FACES?"}
        cfg["experiment"] = {"type": experiment, "object": shape, "params": changed}
        cfg["stages"] = [{"params": {t.stage_param: v}} for v in stage_values]
        from_dict(copy.deepcopy(cfg))                               # every generated config must validate
        out.append(Variation(name, cfg["seed"], index, experiment, cfg, changed, stage_values, shape, vec))
    return out
