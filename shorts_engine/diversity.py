"""Content diversity: decide WHICH experiments to make next (pure Python).

Balanced across experiment types (the least-produced experiment goes first, so a library of 10 videos is not 10
cloth drapes) and, inside an experiment, new variations are kept physically far from the ones that already exist
(see ``variation.generate_variations(avoid=...)``). Deterministic for a given seed.
"""
from __future__ import annotations

import random
from collections import Counter

from .config import ConfigError
from .templates import TEMPLATES


def plan_experiments(count: int, experiments=None, history=None, seed: int = 0) -> list[str]:
    """Experiment name for each of ``count`` slots: always the least-represented one (history + this plan).

    ``history`` is a list of (experiment, vector) pairs from the content library. The same experiment is never
    picked twice in a row while another one is equally under-represented.
    """
    names = list(experiments) if experiments else sorted(TEMPLATES)
    for n in names:
        if n not in TEMPLATES:
            raise ConfigError(f"unknown experiment {n!r}; available: {sorted(TEMPLATES)}")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ConfigError(f"count must be an integer >= 1, got {count!r}")
    rng = random.Random(seed)
    used = Counter(e for e, _ in (history or []) if e in names)
    plan: list[str] = []
    for _ in range(count):
        low = min(used[n] for n in names)
        pool = [n for n in names if used[n] == low]
        if len(pool) > 1 and plan and plan[-1] in pool:
            pool.remove(plan[-1])
        pick = rng.choice(sorted(pool))
        plan.append(pick)
        used[pick] += 1
    return plan


def summarize(plan: list[str]) -> dict:
    return dict(Counter(plan))
