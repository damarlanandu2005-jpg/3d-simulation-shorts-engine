"""Real Blender tests for every non-cloth experiment (skipped without the bpy module).

Each experiment is built and simulated in real Blender; the physical outcome is asserted (not just that it ran).
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "shorts_engine" / "generate_scene.py"
pytestmark = pytest.mark.skipif(importlib.util.find_spec("bpy") is None, reason="bpy not installed")

FINAL_POSITIONS = """
import bpy, json, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
s = bpy.context.scene
s.frame_set(int(sys.argv[2]))
print("POS " + json.dumps({o.name: list(o.location) for o in bpy.data.objects if o.name.startswith(("Ball_", "Ring_"))}))
cloth = bpy.data.objects.get("Cloth")
if cloth:
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get(); m = cloth.evaluated_get(dg).to_mesh()
    pts = np.empty(len(m.vertices) * 3, dtype=np.float32); m.vertices.foreach_get("co", pts)
    print("CLOTH " + json.dumps({"min_z": float(pts.reshape(-1, 3)[:, 2].min()), "max_z": float(pts.reshape(-1, 3)[:, 2].max())}))
"""


def write_cfg(tmp_path, exp, obj, stages, params=None, duration=3.0, name=None, fps=30, size=(90, 160)):
    from shorts_engine.templates import get_template
    key = get_template(exp).stage_param
    cfg = {"schema_version": 2, "name": name or f"t_{exp}", "experiment": {"type": exp, "object": obj, "params": params or {}},
           "simulation": {"fps": fps, "duration": duration}, "stages": [{"params": {key: v}} for v in stages],
           "render": {"samples": 2, "device": "CPU", "denoise": False},
           "output": {"width": size[0], "height": size[1], "dir": str(tmp_path)},
           "hook": {"mode": "closeup", "seconds": 1.0, "text": "auto"},
           "audio": {"enabled": True, "music_enabled": True, "sfx_enabled": True}}
    p = tmp_path / f"{cfg['name']}.json"
    p.write_text(json.dumps(cfg))
    return p


def gen(cfg, *args):
    proc = subprocess.run([sys.executable, str(GEN), "--config", str(cfg), *args], capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2500:] + proc.stderr[-2500:]
    return [json.loads(l.split(" ", 1)[1]) for l in proc.stdout.splitlines() if l.startswith("SHORTS_METRIC ")]


def inspect(blend, frame):
    proc = subprocess.run([sys.executable, "-c", FINAL_POSITIONS, str(blend), str(frame)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = {}
    for line in proc.stdout.splitlines():
        if line.startswith(("POS ", "CLOTH ")):
            k, v = line.split(" ", 1)
            out[k] = json.loads(v)
    return out


def image_std(png) -> float:
    """Standard deviation of the pixel values (0 for a flat image), read with Blender itself (no extra dependency)."""
    code = ("import bpy, sys, numpy as np\nim = bpy.data.images.load(sys.argv[1])\n"
            "a = np.empty(len(im.pixels), dtype=np.float32); im.pixels.foreach_get(a)\nprint('STD', float(a.std()))")
    proc = subprocess.run([sys.executable, "-c", code, str(png)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-1000:]
    return float(next(l for l in proc.stdout.splitlines() if l.startswith("STD")).split()[1])


def blend_of(tmp_path, name, tag):
    return tmp_path / name / tag / f"{tag}.blend"


def events_of(tmp_path, name, tag):
    return json.loads((tmp_path / name / tag / "events.json").read_text())["events"]


# ------------------------------------------------------------------------------------------ multiple_balls
def test_multiple_balls_simulates_and_settles(tmp_path):
    cfg = write_cfg(tmp_path, "multiple_balls", "sphere", [1, 60])
    m = gen(cfg, "--stage", "1", "--mode", "build")[0]
    assert m["bake_method"] == "rigid_keyframes" and m["params"] == {"balls": 60}
    blend = blend_of(tmp_path, "t_multiple_balls", "stage_01_60")
    start, end = inspect(blend, 1)["POS"], inspect(blend, 90)["POS"]
    assert len(end) == 60
    r = 0.22
    assert all(p[2] > 0.5 for p in start.values()), "balls start in the air"
    assert all(p[2] < 1.6 for p in end.values()), "balls must end on the floor / in a low pile"
    assert min(p[2] for p in end.values()) < r + 0.1, "some balls rest on the floor"
    assert all((p[0] ** 2 + p[1] ** 2) ** 0.5 < 2.7 for p in end.values()), "walls keep every ball inside the arena"
    gen(cfg, "--stage", "1", "--mode", "events")
    ev = events_of(tmp_path, "t_multiple_balls", "stage_01_60")
    assert len(ev) >= 5 and {e["type"] for e in ev} <= {"bounce", "landing", "collision"}
    assert any(e["type"] == "collision" for e in ev), "ball-ball / ball-wall impacts are reported"


def test_multiple_balls_is_deterministic_and_seed_changes_layout(tmp_path):
    a = write_cfg(tmp_path, "multiple_balls", "sphere", [6], name="a", duration=1.0)
    gen(a, "--stage", "0", "--mode", "build")
    pa = inspect(blend_of(tmp_path, "a", "stage_00_6"), 30)["POS"]
    gen(a, "--stage", "0", "--mode", "build")
    assert inspect(blend_of(tmp_path, "a", "stage_00_6"), 30)["POS"] == pa
    cfg = json.loads(a.read_text()); cfg.update(seed=5, name="b")
    b = tmp_path / "b.json"; b.write_text(json.dumps(cfg))
    gen(b, "--stage", "0", "--mode", "build")
    assert inspect(blend_of(tmp_path, "b", "stage_00_6"), 30)["POS"] != pa


@pytest.mark.parametrize("shape", ["cube", "cylinder"])
def test_multiple_balls_other_shapes_run(tmp_path, shape):
    cfg = write_cfg(tmp_path, "multiple_balls", shape, [5], name=f"s_{shape}", duration=1.5)
    gen(cfg, "--stage", "0", "--mode", "build")
    end = inspect(blend_of(tmp_path, f"s_{shape}", "stage_00_5"), 45)["POS"]
    assert len(end) == 5 and all(p[2] < 1.5 for p in end.values())


# ------------------------------------------------------------------------------------------ ball_funnel
def test_funnel_smaller_hole_lets_fewer_balls_through(tmp_path):
    cfg = write_cfg(tmp_path, "ball_funnel", "sphere", [0.9, 0.3], duration=3.0)
    through = {}
    for i, tag in enumerate(("stage_00_0p9", "stage_01_0p3")):
        gen(cfg, "--stage", str(i), "--mode", "build")
        pos = inspect(blend_of(tmp_path, "t_ball_funnel", tag), 90)["POS"]
        through[i] = sum(1 for p in pos.values() if p[2] < 1.2)       # funnel hole is at z = 1.5
    assert through[0] >= 30, through
    assert through[1] <= through[0] - 15, f"a 1.7x hole must jam/slow the flow: {through}"


def test_funnel_emits_collision_events(tmp_path):
    cfg = write_cfg(tmp_path, "ball_funnel", "sphere", [0.6], name="f", duration=2.0)
    gen(cfg, "--stage", "0", "--mode", "build")
    gen(cfg, "--stage", "0", "--mode", "events")
    assert len(events_of(tmp_path, "f", "stage_00_0p6")) >= 5


# ------------------------------------------------------------------------------------------ ring_toss
def test_ring_slides_over_pole_only_when_the_hole_is_big_enough(tmp_path):
    cfg = write_cfg(tmp_path, "ring_toss", "torus", [2.5, 0.8], params={"rings": 2, "tilt_degrees": 3.0}, duration=3.0)
    state = {}
    for i, tag in enumerate(("stage_00_2p5", "stage_01_0p8")):
        gen(cfg, "--stage", str(i), "--mode", "build")
        pos = inspect(blend_of(tmp_path, "t_ring_toss", tag), 90)["POS"]
        state[i] = [p for p in pos.values() if (p[0] ** 2 + p[1] ** 2) ** 0.5 < 0.45 and p[2] < 0.5]  # rings around the pole base
    assert len(state[0]) == 2, "rings with a big hole must end up around the pole"
    assert len(state[1]) == 0, "rings smaller than the pole cannot be around its base"


# ------------------------------------------------------------------------------------------ cloth_objects
def test_cloth_drapes_over_several_objects(tmp_path):
    cfg = write_cfg(tmp_path, "cloth_objects", "sphere", [1, 3], params={"faces": 1024}, duration=2.0, name="co")
    res = {}
    for i, tag in enumerate(("stage_00_1", "stage_01_3")):
        m = gen(cfg, "--stage", str(i), "--mode", "build")[0]
        assert m["bake_method"] == "ptcache"
        res[i] = inspect(blend_of(tmp_path, "co", tag), 60)["CLOTH"]
    assert res[1]["min_z"] > -0.05, "cloth must not fall through the floor"
    assert res[1]["max_z"] > 1.2 and res[0]["max_z"] > 1.2, "cloth is held up by the objects"
    gen(cfg, "--stage", "1", "--mode", "events")
    assert len(events_of(tmp_path, "co", "stage_01_3")) >= 1


# ------------------------------------------------------------------------------------------ render + full pipeline
def test_every_experiment_renders_a_non_blank_frame(tmp_path):
    for exp, obj, v in (("multiple_balls", "sphere", 5), ("ball_funnel", "sphere", 0.6), ("ring_toss", "torus", 1.5)):
        cfg = write_cfg(tmp_path, exp, obj, [v], name=f"r_{exp}", duration=1.0)
        gen(cfg, "--stage", "0", "--mode", "build")
        gen(cfg, "--stage", "0", "--mode", "render", "--frame-start", "20", "--frame-end", "20")
        png = next((tmp_path / f"r_{exp}").glob("stage_00_*/frames/frame_0020.png"))
        assert image_std(png) > 0.03, f"{exp}: frame looks blank"


@pytest.mark.parametrize("motion", ["push_in", "follow", "impact"])
def test_camera_motions_render(tmp_path, motion):
    cfg_path = write_cfg(tmp_path, "multiple_balls", "sphere", [4], name=f"m_{motion}", duration=1.0)
    c = json.loads(cfg_path.read_text()); c["camera"] = {"preset": "wide", "motion": motion}
    cfg_path.write_text(json.dumps(c))
    gen(cfg_path, "--stage", "0", "--mode", "build")
    gen(cfg_path, "--stage", "0", "--mode", "events")
    m = gen(cfg_path, "--stage", "0", "--mode", "render", "--frame-start", "5", "--frame-end", "8")[0]
    assert m["frames_rendered"] == 4


def test_full_pipeline_for_a_new_experiment_produces_video(tmp_path):
    """bake -> render -> events -> hook -> assemble -> audio -> QC, end to end, for multiple_balls."""
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe not installed")
    from shorts_engine import render
    cfg = write_cfg(tmp_path, "multiple_balls", "sphere", [1, 6], name="full", duration=1.0, fps=24, size=(90, 160))
    assert render.main(["--config", str(cfg), "--use-bpy"]) == 0
    root = tmp_path / "full"
    assert (root / "full.mp4").is_file() and (root / "benchmark.json").is_file()
    cues = json.loads((root / "audio_timeline.json").read_text())["sfx"]
    assert cues, "physics events produced sound effects"


def test_pipeline_writes_metadata_benchmark_and_a_passing_qc_report(tmp_path):
    """The render orchestrator runs QC automatically and writes metadata for every finished video."""
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe not installed")
    from shorts_engine import render
    cfg = write_cfg(tmp_path, "ball_funnel", "sphere", [0.8, 0.5], name="qcrun", duration=1.0, fps=24, size=(90, 160))
    assert render.main(["--config", str(cfg), "--use-bpy"]) == 0
    root = tmp_path / "qcrun"
    qc = json.loads((root / "qc_report.json").read_text())
    assert qc["passed"], [c for c in qc["checks"] if not c["ok"]]
    meta = json.loads((root / "metadata.json").read_text())
    assert meta["experiment"] == "ball_funnel" and meta["resolution"] == "90x160" and meta["experiment_config"]["stages"]
