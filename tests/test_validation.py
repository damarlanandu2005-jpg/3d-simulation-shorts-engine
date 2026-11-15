import copy
import pytest
from shorts_engine.config import from_dict, ConfigError
from shorts_engine.variation import generate_variations


def _cfg(exp, params, stage_param, stages, obj=None):
    d = {"schema_version": 2, "name": "t", "experiment": {"type": exp, "params": params}, "stages": [{"params": {stage_param: v}} for v in stages]}
    if obj:
        d["experiment"]["object"] = obj
    return d


def _try(*a, **k):
    try:
        from_dict(_cfg(*a, **k))
    except ConfigError:
        return False
    except Exception:
        return None
    return True


def test_spread_outside_arena_rejected():
    assert _try("multiple_balls", {"spread": 9, "arena_radius": 2}, "balls", [1, 10]) is False


def test_funnel_hole_too_large_rejected():
    assert _try("ball_funnel", {"funnel_radius": 1.0}, "hole_radius", [0.9, 0.6]) is False


def test_cloth_too_small_for_objects_rejected():
    assert _try("cloth_objects", {"cloth_size": 2.0}, "objects", [1, 4]) is False


def test_default_combinations_valid():
    for e, sp, st in [("multiple_balls", "balls", [1, 10, 50, 100]), ("ball_funnel", "hole_radius", [0.9, 0.6, 0.42, 0.3]),
                      ("ring_toss", "hole_ratio", [2.5, 1.5, 1.15, 0.85]), ("cloth_objects", "objects", [1, 2, 3, 4])]:
        assert _try(e, {}, sp, st) is True


def test_variations_all_valid():
    for e in ["multiple_balls", "ball_funnel", "ring_toss", "cloth_objects"]:
        for v in generate_variations(e, 6, master_seed=3):
            from_dict(v.config)
