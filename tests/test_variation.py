import json
import itertools

import pytest

from shorts_engine import variation
from shorts_engine.config import ConfigError, from_dict
from shorts_engine.templates import TEMPLATES, get_template

ALL = sorted(TEMPLATES)


@pytest.mark.parametrize("exp", ALL)
def test_variations_are_unique_valid_and_physical(exp):
    vs = variation.generate_variations(exp, 12, master_seed=7)
    assert len(vs) == 12
    assert len({v.name for v in vs}) == 12 and len({v.seed for v in vs}) == 12
    assert len({json.dumps(v.config, sort_keys=True) for v in vs}) == 12
    t = get_template(exp)
    for v in vs:
        cfg = from_dict(json.loads(json.dumps(v.config)))               # validated, round-trips through JSON
        assert cfg.seed == v.seed and cfg.name == v.name
        assert v.changed and set(v.changed) <= set(t.variations), "variation must change physical parameters"
        for k, val in v.changed.items():
            lo, hi = t.variations[k]
            assert lo <= val <= hi
    for a, b in itertools.combinations(vs, 2):
        assert variation.distance(a.vector, b.vector) > 0, "no two variations may be identical physically"


@pytest.mark.parametrize("exp", ALL)
def test_variations_are_not_just_cosmetic(exp):
    for v in variation.generate_variations(exp, 8, master_seed=3):
        assert "material" not in v.config
        t = get_template(exp)
        moved = [k for k, x in v.changed.items() if abs(x - t.params[k].default) >= 0.1 * (t.variations[k][1] - t.variations[k][0])]
        assert moved or v.shape != t.default_object or v.stage_values != list(t.default_stage_values)


def test_deterministic_for_a_master_seed_and_different_across_seeds():
    a = [v.config for v in variation.generate_variations("multiple_balls", 5, 11)]
    assert a == [v.config for v in variation.generate_variations("multiple_balls", 5, 11)]
    assert a != [v.config for v in variation.generate_variations("multiple_balls", 5, 12)]


def test_batch_is_a_prefix_of_a_longer_batch_seeds_unchanged():
    short = variation.generate_variations("ring_toss", 3, 5)
    long = variation.generate_variations("ring_toss", 6, 5)
    assert [v.seed for v in short] == [v.seed for v in long[:3]]


def test_presets_720p_fast_and_1080p_quality_and_denoise_not_mandatory():
    for preset, size in (("720p", (720, 1280)), ("1080p", (1080, 1920))):
        cfg = from_dict(variation.generate_variations("ball_funnel", 1, 1, preset=preset)[0].config)
        assert (cfg.output.width, cfg.output.height) == size
        assert cfg.render.denoise is False and cfg.render.denoiser != "OPTIX"
    with pytest.raises(ConfigError, match="preset"):
        variation.production_base("4k")


@pytest.mark.parametrize("bad", [0, -1, 2.5, "3", True])
def test_invalid_counts(bad):
    with pytest.raises(ConfigError, match="variations"):
        variation.generate_variations("multiple_balls", bad)


def test_unknown_experiment():
    with pytest.raises(ConfigError, match="not available"):
        variation.generate_variations("teleporter", 2)


def test_seed_derivation_is_stable_and_spread():
    assert variation.derive_seed(1, 0) == variation.derive_seed(1, 0)
    assert len({variation.derive_seed(1, i) for i in range(1000)}) == 1000


def test_cloth_drape_variation_keeps_the_v1_hook_and_no_camera_preset():
    cfg = from_dict(variation.generate_variations("cloth_drape", 1, 2)[0].config)
    assert "MORE FACES" in cfg.hook_text() and cfg.experiment_type == "cloth_drape"
