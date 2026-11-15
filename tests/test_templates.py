"""Experiment templates, config model, camera rules and the rigid-body event detector (pure Python, no Blender)."""
import copy
import json
import math

import numpy as np
import pytest

from shorts_engine import camera_rig, events, experiment, templates, timeline
from shorts_engine.config import ConfigError, ExperimentConfig, from_dict, load_config
from shorts_engine.templates import TEMPLATES, collider_layout, get_template, spawn_positions

NEW = ["multiple_balls", "ball_funnel", "ring_toss", "cloth_objects"]


def doc(exp, **extra):
    t = get_template(exp)
    d = {"schema_version": 2, "name": f"x_{exp}", "experiment": {"type": exp},
         "stages": [{"params": {t.stage_param: v}} for v in t.default_stage_values]}
    d.update(extra)
    return d


def test_registry_lists_exactly_the_implemented_experiments():
    assert sorted(TEMPLATES) == sorted(["cloth_drape"] + NEW)
    assert experiment.EXPERIMENT_TYPES is TEMPLATES


@pytest.mark.parametrize("exp", NEW)
def test_default_config_for_every_template_resolves(exp):
    cfg = from_dict(doc(exp))
    t = get_template(exp)
    assert isinstance(cfg, ExperimentConfig) and cfg.experiment_type == exp
    assert cfg.stage_count == len(t.default_stage_values) == len(cfg.stages())
    assert cfg.simulation == t.simulation
    assert set(cfg.params) == set(t.params)
    assert all(st.params == {t.stage_param: v} for st, v in zip(cfg.stages(), t.default_stage_values))
    assert len({st.blend_path for st in cfg.stages()}) == cfg.stage_count          # unique paths per stage


@pytest.mark.parametrize("exp", NEW)
def test_labels_and_hooks_describe_the_experiment(exp):
    cfg = from_dict(doc(exp))
    labels = [s.label for s in cfg.stages()]
    assert len(set(labels)) == len(labels) and all(labels)
    assert not any("faces" in l.lower() for l in labels)
    assert "FACES" not in cfg.hook_text()
    for i, hook in enumerate(get_template(exp).hooks):                 # every hook template formats cleanly
        c = from_dict(doc(exp, seed=i, hook={"text": "auto", "seconds": 2.0, "mode": "closeup"}))
        assert c.hook_text() == c.hook_text().strip() and "{" not in c.hook_text()


def test_balls_labels_and_dynamic_hook():
    cfg = from_dict(doc("multiple_balls", hook={"text": "WHAT HAPPENS WHEN WE DROP {last} BALLS?", "mode": "closeup", "seconds": 2}))
    assert [s.label for s in cfg.stages()] == ["1 BALL", "10 BALLS", "50 BALLS", "100 BALLS"]
    assert cfg.hook_text().replace("\n", " ") == "WHAT HAPPENS WHEN WE DROP 100 BALLS?"
    assert max(len(line) for line in cfg.hook_text().split("\n")) <= 16, "long questions wrap to fit the frame"


def test_hook_depends_on_the_actual_experiment_numbers():
    d = doc("multiple_balls", hook={"text": "{first} VS {last}", "mode": "closeup", "seconds": 2})
    d["stages"] = [{"params": {"balls": 3}}, {"params": {"balls": 300}}]
    assert from_dict(d).hook_text() == "3 VS 300"


def test_auto_hook_rotates_with_seed():
    texts = {from_dict(doc("multiple_balls", seed=s)).hook_text() for s in range(3)}
    assert len(texts) == 3


def test_invalid_hook_placeholder_is_rejected():
    with pytest.raises(ConfigError, match="hook.text"):
        from_dict(doc("ball_funnel", hook={"text": "{nonsense}", "mode": "closeup", "seconds": 2}))


def test_cloth_hook_unchanged_in_legacy_format():
    cfg = load_config("configs/v1_1_a_baseline.json")
    assert "256" in cfg.hook_text() and "FACES" in cfg.hook_text()


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize("exp,key,bad", [
    ("multiple_balls", "ball_radius", 5.0), ("multiple_balls", "restitution", 1.5), ("multiple_balls", "friction", -1),
    ("multiple_balls", "drop_height", 0), ("ball_funnel", "balls", 2.5), ("ball_funnel", "funnel_height", 0.1),
    ("ring_toss", "rings", 0), ("ring_toss", "tilt_degrees", 90), ("cloth_objects", "faces", 99),
    ("cloth_objects", "spacing", 0.2)])
def test_out_of_range_parameters_are_rejected(exp, key, bad):
    d = doc(exp)
    d["experiment"]["params"] = {key: bad}
    with pytest.raises(ConfigError, match=key):
        from_dict(d)


@pytest.mark.parametrize("exp,bad", [("multiple_balls", 0), ("multiple_balls", 1.5), ("multiple_balls", "ten"),
                                     ("multiple_balls", 10_000), ("ball_funnel", 0.01), ("ring_toss", -1),
                                     ("cloth_objects", 99)])
def test_invalid_stage_values_are_rejected(exp, bad):
    d = doc(exp)
    d["stages"][1]["params"][get_template(exp).stage_param] = bad
    with pytest.raises(ConfigError, match=r"stages\[1\]"):
        from_dict(d)


def test_stage_must_use_the_experiments_own_parameter():
    d = doc("multiple_balls")
    d["stages"][0]["params"] = {"faces": 64}
    with pytest.raises(ConfigError, match="faces"):
        from_dict(d)


def test_cloth_stage_param_is_not_accepted_by_other_experiments_and_vice_versa():
    d = doc("cloth_drape")
    d["stages"][0]["params"] = {"balls": 5}
    with pytest.raises(ConfigError, match="balls"):
        from_dict(d)


@pytest.mark.parametrize("obj,ok", [("sphere", True), ("cube", True), ("cylinder", True), ("torus", False), ("cone", False)])
def test_ball_shapes(obj, ok):
    d = doc("multiple_balls")
    d["experiment"]["object"] = obj
    if ok:
        assert from_dict(d).shape == obj
    else:
        with pytest.raises(ConfigError, match="experiment.object"):
            from_dict(d)


def test_unknown_param_and_empty_stages_rejected():
    d = doc("ring_toss"); d["experiment"]["params"] = {"bogus": 1}
    with pytest.raises(ConfigError, match="unknown key"):
        from_dict(d)
    d = doc("ring_toss"); d["stages"] = []
    with pytest.raises(ConfigError, match="non-empty"):
        from_dict(d)


def test_multiplier_cards_are_cloth_only():
    with pytest.raises(ConfigError, match="cloth_drape"):
        from_dict(doc("multiple_balls", video={"cards": {"enabled": True}}))


def test_camera_preset_and_motion_validation():
    from_dict(doc("multiple_balls", camera={"preset": "top", "motion": "follow"}))
    for bad in ({"preset": "diagonal"}, {"motion": "spin"}):
        with pytest.raises(ConfigError, match="camera"):
            from_dict(doc("multiple_balls", camera=bad))
    with pytest.raises(ConfigError, match="only available"):
        from_dict(doc("cloth_drape", camera={"preset": "top"}))


def test_stage_label_template_validation():
    with pytest.raises(ConfigError, match="label.template"):
        from_dict(doc("multiple_balls", label={"template": "{faces_short} FACES"}))
    assert from_dict(doc("multiple_balls", label={"template": "N={balls}"})).stages()[1].label == "N=10"


def test_physics_and_seed_validation_still_apply():
    with pytest.raises(ConfigError, match="gravity"):
        from_dict(doc("multiple_balls", simulation={"physics": {"gravity": -3}}))
    with pytest.raises(ConfigError, match="seed"):
        from_dict(doc("multiple_balls", seed=-1))


@pytest.mark.parametrize("exp", NEW)
def test_migrate_round_trip_for_new_experiments(exp):
    cfg = from_dict(doc(exp, seed=3))
    again = from_dict(experiment.to_experiment_dict(cfg))
    assert again == cfg
    assert experiment.describe(cfg).type == exp


def test_cli_lists_all_experiments(capsys):
    assert experiment.main(["list"]) == 0
    out = capsys.readouterr().out
    for name in ["cloth_drape"] + NEW:
        assert name in out


# ------------------------------------------------------------------ pipeline plan is generic
@pytest.mark.parametrize("exp", NEW)
def test_render_plan_and_timeline_for_new_experiments(exp):
    from shorts_engine import render
    cfg = from_dict(doc(exp, audio={"enabled": True, "sfx_enabled": True}, simulation={"duration": 3.0}))
    jobs = render.plan_jobs(cfg, "x.json", ["blender"], True)
    kinds = [j.kind for j in jobs]
    n = cfg.stage_count
    assert kinds.count("bake") == n and kinds.count("render") == n and kinds.count("events") == n
    assert kinds.count("hook_render") == 1 and kinds[-2:] == ["concat", "audio"]
    assert not any(k == "card_render" for k in kinds)
    assert timeline.total_seconds(cfg) == 2.0 + 3.0 * n
    segs = timeline.segments(cfg)
    assert segs[0].kind == "hook" and (segs[0].first, segs[0].last) == cfg.hook_frame_range()


def test_hook_window_start_vs_end():
    start = from_dict(doc("multiple_balls", hook={"seconds": 2, "window": "start"}))
    end = from_dict(doc("multiple_balls", hook={"seconds": 2, "window": "end"}))
    assert start.hook_frame_range() == (1, 60) and end.hook_frame_range()[1] == end.frame_count
    assert from_dict(doc("cloth_objects")).hook_window == "end" and from_dict(doc("ball_funnel")).hook_window == "start"
    with pytest.raises(ConfigError, match="window"):
        from_dict(doc("multiple_balls", hook={"seconds": 2, "window": "middle"}))


# ------------------------------------------------------------------ spawn layouts
@pytest.mark.parametrize("n,r,spread", [(1, 0.2, 1.0), (10, 0.22, 1.5), (100, 0.22, 1.5), (300, 0.15, 1.2)])
def test_spawn_positions_count_and_no_overlap(n, r, spread):
    pts = np.array(spawn_positions(n, r, spread, 1.0, seed=2))
    assert pts.shape == (n, 3)
    d = np.linalg.norm(pts[:, None] - pts[None], axis=2) + np.eye(n) * 10
    assert d.min() > 2 * r, "spawned objects must not overlap"
    assert pts[:, 2].min() >= 1.0


def test_spawn_positions_deterministic_and_seeded():
    a = spawn_positions(30, 0.2, 1.5, 1.0, 1)
    assert a == spawn_positions(30, 0.2, 1.5, 1.0, 1) and a != spawn_positions(30, 0.2, 1.5, 1.0, 2)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
def test_collider_layout_separated(n):
    pts = collider_layout(n, 2.0)
    assert len(pts) == n
    for i in range(n):
        for j in range(i):
            assert math.dist(pts[i], pts[j]) >= 1.99


# ------------------------------------------------------------------ camera
@pytest.mark.parametrize("preset", camera_rig.PRESETS)
@pytest.mark.parametrize("exp", NEW + ["cloth_drape"])
def test_fitted_camera_keeps_the_region_in_frame(exp, preset):
    """Project the region's corners through the real camera model: nothing may fall outside the 9:16 frame."""
    t = get_template(exp)
    for v in t.default_stage_values:
        r = t.frame_region(t.resolve_params({}), v)
        cam = camera_rig.fit_camera(r.half_width, r.top, r.bottom, preset, elevation=t.camera_defaults.get('elevation'))
        tan_v = 18.0 / 50.0
        tan_h = tan_v * 9 / 16
        c = np.array([0, -cam["distance"], cam["height"]]); target = np.array([0, 0, cam["target_z"]])
        fwd = (target - c) / np.linalg.norm(target - c)
        right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        for x in (-r.half_width, r.half_width):
            for y in (-r.half_width, r.half_width):
                for z in (r.bottom, r.top):
                    q = np.array([x, y, z]) - c
                    depth = q @ fwd
                    assert depth > 0
                    if preset == "close":                      # a close-up may crop the sides on purpose
                        continue
                    assert abs(q @ right) / depth <= tan_h * 1.02, (exp, preset, v, "clipped horizontally")
                    if preset != "top":
                        assert abs(q @ up) / depth <= tan_v * 1.02, (exp, preset, v, "clipped vertically")


def test_camera_for_stage_uses_preset_and_overrides_and_manual():
    cfg = from_dict(doc("multiple_balls", camera={"preset": "wide"}))
    near, far = cfg.camera_for_stage(0), cfg.camera_for_stage(3)
    assert far.target_z > near.target_z, "more balls = taller stack = camera aims higher"
    cfg = from_dict(doc("multiple_balls"))
    cfg.stages()
    d = doc("multiple_balls"); d["stages"][1]["camera"] = {"distance": 20.0}
    assert from_dict(d).camera_for_stage(1).distance == 20.0
    d = doc("multiple_balls", camera={"preset": "manual", "distance": 9.0, "height": 3.0, "target_z": 0.5})
    c = from_dict(d).camera_for_stage(0)
    assert (c.distance, c.height, c.target_z) == (9.0, 3.0, 0.5)


def test_camera_presets_differ_in_elevation():
    elev = {p: camera_rig.fit_camera(2.5, 3.0, 0.0, p)["height"] / camera_rig.fit_camera(2.5, 3.0, 0.0, p)["distance"] for p in camera_rig.PRESETS}
    assert elev["side"] < elev["wide"] < elev["top"]


def test_motion_offsets():
    m = camera_rig.motion_offsets
    assert m("static", 10, 90) == {"distance_scale": 1.0, "target_follow": 0.0}
    assert m("push_in", 90, 90)["distance_scale"] < m("push_in", 1, 90)["distance_scale"] == 1.0
    assert m("follow", 5, 90)["target_follow"] > 0
    assert m("impact", 40, 90, 40)["distance_scale"] < m("impact", 80, 90, 40)["distance_scale"] == 1.0
    assert m("impact", 5, 90, None)["distance_scale"] == 1.0
    with pytest.raises(ValueError):
        m("spin", 1, 2)


# ------------------------------------------------------------------ rigid-body events from trajectories
def bouncing(frames=90, fps=30, g=9.81, z0=2.0, e=0.6, r=0.2):
    z, v, out = z0, 0.0, []
    for _ in range(frames):
        out.append(z)
        v -= g / fps
        z += v / fps
        if z < r:
            z, v = r, -v * e
    tr = np.zeros((frames, 1, 3))
    tr[:, 0, 2] = out
    return tr


def test_impulses_find_bounces_with_decreasing_strength_and_right_time():
    ev = events.detect_impulses(bouncing(), 30, 9.81, 6.0, [0.2])
    assert len(ev) >= 3 and ev[0].type == "bounce"
    assert [e.strength for e in ev[:3]] == sorted([e.strength for e in ev[:3]], reverse=True)
    t_hit = math.sqrt(2 * 1.8 / 9.81)
    assert abs((ev[0].frame - 1) / 30 - t_hit) < 0.1


def test_impulses_ignore_free_fall_and_rest():
    fall = np.zeros((40, 1, 3)); fall[:, 0, 2] = [10 - 0.5 * 9.81 * (i / 30) ** 2 for i in range(40)]
    assert events.detect_impulses(fall, 30, 9.81, 6.0, [0.2]) == []
    rest = np.zeros((40, 1, 3)); rest[:, 0, 2] = 0.2
    assert events.detect_impulses(rest, 30, 9.81, 6.0, [0.2]) == []


def test_impulses_report_ball_ball_collision_away_from_the_floor():
    fps, n = 30, 40
    tr = np.zeros((n, 2, 3))
    for i in range(n):
        tr[i, 0] = [-2 + 0.1 * i * (i < 20) + 0.1 * 20 * (i >= 20), 0, 5]
        tr[i, 1] = [2 - 0.1 * i * (i < 20) - 0.1 * 20 * (i >= 20), 0, 5]
    # head-on at frame ~20: both reverse
    for i in range(20, n):
        tr[i, 0, 0] = tr[19, 0, 0] - 0.1 * (i - 19)
        tr[i, 1, 0] = tr[19, 1, 0] + 0.1 * (i - 19)
    for j in range(2):
        tr[:, j, 2] = 5.0                                          # no gravity here (floating bodies)
    ev = events.detect_impulses(tr, fps, 0.0, 6.0, [0.2, 0.2])
    assert ev and all(e.type == "collision" for e in ev)
    assert {e.source for e in ev} == {"body_0", "body_1"}


def test_impulse_events_feed_the_existing_sound_pipeline():
    ev = events.detect_impulses(bouncing(), 30, 9.81, 6.0, [0.2])
    assert {e.sound_name for e in ev} <= {"bounce", "soft_landing", "soft_impact"}


def test_impulses_degenerate_inputs():
    assert events.detect_impulses(np.zeros((2, 1, 3)), 30, 9.81, 6.0) == []
    assert events.detect_impulses(np.zeros((10, 1, 3)), 30, 9.81, 0.0) == []


def test_example_configs_all_load():
    for p in sorted((__import__("pathlib").Path(__file__).resolve().parent.parent / "configs" / "experiments").glob("*.json")):
        assert load_config(p).stage_count >= 1, p
