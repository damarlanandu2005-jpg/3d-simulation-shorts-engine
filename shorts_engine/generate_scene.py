"""Blender entry point. Runs inside Blender (or inside the ``bpy`` pip module).

    blender --background --python shorts_engine/generate_scene.py -- \
        --config configs/example_cloth.json --stage 0 --mode build
    blender --background --python shorts_engine/generate_scene.py -- \
        --config configs/example_cloth.json --stage 0 --mode render --frame-start 1 --frame-end 60

Modes:
    build   create the scene, save the .blend, bake the physics cache next to it
    render  open the saved .blend and render a frame range to PNGs (skips existing frames)
    all     build then render every frame
    hook    render the closeup hook (camera push-in over the last stage's baked cloth)
    card    render a multiplier title card (--card-index N); needs no bake

What is baked vs. applied at render time: physics, geometry and materials are fixed when the scene is
BUILT (changing them needs a rebuild). Render settings (samples, denoise, resolution), the camera and the
label text are re-applied from the config at RENDER time, so editing them needs no re-bake.

Splitting "build" from "render" means physics is baked once and any number of workers can
render different frame ranges from the same .blend + cache.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from shorts_engine import camera, materials, simulation  # noqa: E402
from shorts_engine.config import load_config  # noqa: E402


def metric(**kwargs) -> None:
    """Machine-readable line the orchestrator parses."""
    print("SHORTS_METRIC " + json.dumps(kwargs), flush=True)


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(prog="generate_scene")
    p.add_argument("--config", required=True)
    p.add_argument("--stage", type=int, default=0, help="index into config.resolutions")
    p.add_argument("--mode", choices=["build", "render", "all", "hook", "card", "events"], default="all")
    p.add_argument("--card-index", type=int, default=0, help="card mode: card shown after this stage")
    p.add_argument("--frame-start", type=int, default=None)
    p.add_argument("--frame-end", type=int, default=None)
    return p.parse_args(argv)


def apply_render_settings(scene, cfg, samples: int | None = None) -> None:
    """Settings that must follow the CURRENT config at render time (not the value saved in the .blend)."""
    scene.render.resolution_x = cfg.output.width
    scene.render.resolution_y = cfg.output.height
    scene.render.resolution_percentage = 100
    scene.render.engine = cfg.render.engine
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    cy = scene.cycles
    cy.samples = samples or cfg.render.samples
    cy.max_bounces = cfg.render.max_bounces
    cy.transparent_max_bounces = max(cy.transparent_max_bounces, 64)   # folded, dissolving cloth is many transparent layers deep
    cy.use_denoising = cfg.render.denoise
    if cfg.render.denoise:
        # OPTIX is only a valid enum value once an OptiX GPU is enabled, so it is set in prepare_render()
        # AFTER the device is chosen. OpenImageDenoise always works.
        cy.denoiser = "OPENIMAGEDENOISE"


def prepare_render(scene, cfg, samples: int | None = None):
    """Apply render settings and pick the device. Returns (device, denoiser_actually_used or None)."""
    apply_render_settings(scene, cfg, samples)
    device = select_device(scene, cfg.render.device)
    cy = scene.cycles
    if cy.use_denoising and cfg.render.denoiser == "OPTIX":
        if device == "OPTIX":
            try:
                cy.denoiser = "OPTIX"
            except TypeError:
                print("WARNING: Blender did not offer the OptiX denoiser; using OpenImageDenoise instead")
        else:
            print(f"WARNING: OptiX denoiser needs an OptiX GPU (device is {device}); using OpenImageDenoise instead")
    return device, (cy.denoiser if cy.use_denoising else None)


def configure_scene(scene, cfg) -> None:
    scene.render.fps = cfg.fps
    scene.frame_start = 1
    scene.frame_end = cfg.frame_count
    apply_render_settings(scene, cfg)


def select_device(scene, requested: str) -> str:
    """Pick the Cycles device. AUTO tries OPTIX, then CUDA, then CPU. Returns what was used."""
    if requested == "CPU":
        scene.cycles.device = "CPU"
        return "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_type in ("OPTIX", "CUDA"):
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == dev_type]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == dev_type
                scene.cycles.device = "GPU"
                return dev_type
    except Exception as exc:  # no cycles addon prefs / no GPU backend in this build
        print(f"GPU detection failed ({exc!r}); using CPU")
    scene.cycles.device = "CPU"
    return "CPU"


def build_stage(cfg, stage) -> None:
    t0 = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    configure_scene(scene, cfg)
    materials.setup_world(scene, cfg.material.background_color, cfg.material.look)
    materials.add_lights(scene, cfg.material.look)

    cam = camera.add_camera(scene, cfg.camera_for_stage(stage.index), cfg.output.width, cfg.output.height)
    label_mat = materials.emission("LabelMat", cfg.label.color, 1.0)
    camera.add_label(scene, cam, stage.label, cfg.label.size, label_mat)

    builder = simulation.SIMULATORS[cfg.experiment_type]
    handle = builder(scene, cfg, stage)

    # The disk cache lives next to the .blend, so save before baking.
    stage.blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(stage.blend_path.resolve()))
    setup_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    method = simulation.bake_for(cfg, scene, handle, cfg.frame_count)
    bake_s = time.perf_counter() - t1
    post = simulation.POST_BAKE.get(cfg.experiment_type)
    outcome = post(scene, cfg, stage, handle) if post else None         # facts read from the baked result (winner, fill levels)
    if outcome is not None:
        (stage.blend_path.parent / "result.json").write_text(json.dumps(outcome, indent=1))
        metric(kind="outcome", stage=stage.index, **outcome)
    bpy.ops.wm.save_mainfile()
    metric(stage=stage.index, faces=stage.faces, params=stage.params, setup_seconds=round(setup_s, 2),
           bake_seconds=round(bake_s, 2), bake_method=method, frames=cfg.frame_count)


def require_blend(stage) -> None:
    if not stage.blend_path.exists():
        raise SystemExit(f"{stage.blend_path} not found: build (bake) this stage first (--mode build)")


def render_stage(cfg, stage, frame_start, frame_end) -> None:
    require_blend(stage)
    bpy.ops.wm.open_mainfile(filepath=str(stage.blend_path.resolve()))
    scene = bpy.context.scene
    # samples/denoise/resolution, camera and label come from the config, not the saved .blend
    device, denoiser = prepare_render(scene, cfg)
    camera.apply_camera(cfg.camera_for_stage(stage.index))
    camera.set_label(stage.label, cfg.label.size, camera.LABEL_Y)
    stage.frames_dir.mkdir(parents=True, exist_ok=True)

    frame_start = frame_start or 1
    frame_end = frame_end or cfg.frame_count
    if not (1 <= frame_start <= frame_end <= cfg.frame_count):
        raise SystemExit(f"frame range {frame_start}-{frame_end} outside 1-{cfg.frame_count}")

    motion = getattr(cfg, "camera_motion", "static")
    before = camera_motion_callback(cfg, stage) if (motion != "static" or scene.get("sim_markers")) else None
    before = with_label_schedule(scene, cfg, before)
    render_frames(scene, range(frame_start, frame_end + 1), lambda f: stage.frames_dir / f"frame_{f:04d}.png",
                  stage.index, stage.faces, device, denoiser, before_frame=before)


def with_label_schedule(scene, cfg, before):
    """Texts that change during a clip (question -> answer). The schedule is stored in the .blend by the builder."""
    raw = scene.get("sim_markers")
    schedule = json.loads(raw).get("label_schedule") if raw else None
    if not schedule:
        return before
    steps = sorted((int(f), t) for f, t in schedule)

    def at(frame):
        text = ""
        for f, t in steps:
            if frame >= f:
                text = t
        return text

    def move(frame):
        text = at(frame)
        bpy.data.objects["Label"].hide_render = not text
        if text:
            camera.set_label(text, cfg.label.size, camera.LABEL_Y)
        if before:
            before(frame)
    return move


def tracked_objects():
    """The moving bodies of a rigid-body scene (balls, rings)."""
    return [o for o in bpy.data.objects if o.name.startswith(("Ball_", "Ring_"))]


def strongest_event_frame(cfg, stage):
    from shorts_engine import events as ev
    path = cfg.stage_events_path(stage.index)
    if not path.is_file():
        return None
    found = ev.load_events(path)
    return int(round(max(found, key=lambda e: e.strength).frame)) if found else None


def camera_path_callback(scene):
    """A camera path written by the experiment builder (sim_markers["camera_path"]): [[frame, cam xyz, target xyz], ...].

    Linear between keys; builders put dense keys where the camera follows the action and few keys where it glides.
    """
    raw = scene.get("sim_markers")
    path = json.loads(raw).get("camera_path") if raw else None
    if not path:
        return None
    keys = sorted(path, key=lambda k: k[0])
    cam, target = bpy.data.objects["Camera"], bpy.data.objects["CameraTarget"]

    def move(frame):
        if frame <= keys[0][0]:
            a = b = keys[0]
        elif frame >= keys[-1][0]:
            a = b = keys[-1]
        else:
            b = next(k for k in keys if k[0] >= frame)
            a = keys[keys.index(b) - 1]
        t = 0.0 if a is b or b[0] == a[0] else (frame - a[0]) / (b[0] - a[0])
        cam.location = [a[1][i] + (b[1][i] - a[1][i]) * t for i in range(3)]
        target.location = [a[2][i] + (b[2][i] - a[2][i]) * t for i in range(3)]
    return move


def camera_motion_callback(cfg, stage):
    """Per-frame camera move (push-in / follow / impact punch-in) from the experiment's camera.motion."""
    from shorts_engine import camera_rig
    path = camera_path_callback(bpy.context.scene)
    if path:
        return path
    base = cfg.camera_for_stage(stage.index)
    event_frame = strongest_event_frame(cfg, stage) if cfg.camera_motion == "impact" else None
    objs = tracked_objects()

    def move(frame):
        m = camera_rig.motion_offsets(cfg.camera_motion, frame, cfg.frame_count, event_frame)
        xy = (0.0, 0.0)
        if m["target_follow"] and objs:
            xy = (m["target_follow"] * sum(o.location.x for o in objs) / len(objs),
                  m["target_follow"] * sum(o.location.y for o in objs) / len(objs))
        camera.apply_camera(replace(base, distance=base.distance * m["distance_scale"],
                                    height=base.target_z + (base.height - base.target_z) * m["distance_scale"]), xy)
    return move


def render_frames(scene, frames, path_for, stage_index, faces, device, denoiser, before_frame=None, kind="render"):
    t0 = time.perf_counter()
    rendered = skipped = 0
    for frame in frames:
        out = path_for(frame)
        if out.exists():
            skipped += 1
            continue
        scene.frame_set(frame)
        if before_frame:
            before_frame(frame)
        scene.render.filepath = str(out.resolve())
        bpy.ops.render.render(write_still=True)
        rendered += 1
    render_s = time.perf_counter() - t0
    metric(kind=kind, stage=stage_index, faces=faces, render_seconds=round(render_s, 2), device=device,
           frames_rendered=rendered, frames_skipped=skipped,
           seconds_per_frame=round(render_s / rendered, 2) if rendered else None,
           samples=scene.cycles.samples, denoise=scene.cycles.use_denoising, denoiser=denoiser,
           width=scene.render.resolution_x, height=scene.render.resolution_y)


def render_hook(cfg, stage) -> None:
    """Camera push-in over the finished (last-stage) cloth. Reuses the baked cache: no extra simulation."""
    hook = cfg.video.hook
    if hook.mode != "closeup":
        raise SystemExit("video.hook.mode is not 'closeup'; nothing to render")
    require_blend(stage)
    bpy.ops.wm.open_mainfile(filepath=str(stage.blend_path.resolve()))
    scene = bpy.context.scene
    c = hook.closeup
    device, denoiser = prepare_render(scene, cfg, c.samples or None)
    if hook.text:
        camera.set_label(cfg.hook_text(), hook.text_size, hook.text_y)
    else:
        bpy.data.objects["Label"].hide_render = True
    first, last = cfg.hook_frame_range()
    cfg.hook_frames_dir.mkdir(parents=True, exist_ok=True)
    span = max(1, last - first)

    def move_camera(frame):
        t = (frame - first) / span
        dist = c.distance_start + (c.distance_end - c.distance_start) * t
        camera.apply_camera(replace(cfg.camera, distance=dist, height=c.height, target_z=c.target_z, per_stage=[]))

    render_frames(scene, range(first, last + 1), lambda f: cfg.hook_frames_dir / f"frame_{f:04d}.png",
                  stage.index, stage.faces, device, denoiser, before_frame=move_camera, kind="hook")


def render_card(cfg, card_index: int) -> None:
    cards = cfg.cards()
    if not cards:
        raise SystemExit("video.cards.enabled is false; nothing to render")
    if not 0 <= card_index < len(cards):
        raise SystemExit(f"--card-index {card_index} out of range (0..{len(cards) - 1})")
    card = cards[card_index]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = cfg.fps
    scene.frame_start, scene.frame_end = 1, card.frames
    device, _ = prepare_render(scene, cfg, cfg.video.cards.samples)
    scene.cycles.use_denoising = False  # flat text on a flat background does not need it
    materials.setup_world(scene, cfg.material.background_color)
    camera.add_camera(scene, replace(cfg.camera, distance=5.0, height=0.0, target_z=0.0, focal_length=50.0, per_stage=[]),
                      cfg.output.width, cfg.output.height)
    mat = materials.emission("CardMat", cfg.label.color, 1.0)
    title = camera.add_card_text(scene, card.title, cfg.video.cards.title_size, (0.0, 0.0, 0.25), mat)
    camera.add_card_text(scene, card.subtitle, cfg.video.cards.subtitle_size, (0.0, 0.0, -0.4), mat)
    # little "pop": the multiplier grows slightly over the card
    title.scale = (0.85, 0.85, 0.85)
    title.keyframe_insert("scale", frame=1)
    title.scale = (1.0, 1.0, 1.0)
    title.keyframe_insert("scale", frame=max(2, card.frames))

    card.frames_dir.mkdir(parents=True, exist_ok=True)
    render_frames(scene, range(1, card.frames + 1), lambda f: card.frames_dir / f"frame_{f:04d}.png",
                  card_index, 0, device, None, kind="card")


def detect_stage_events(cfg, stage) -> None:
    """Read the baked simulation and write ``events.json`` (physical events for the sound-effect layer).

    Thin read-only layer: it steps through the baked result and turns contacts into events (see events.py).
    Nothing about the physics or the render is changed, and nothing is saved back to the .blend.
    """
    from shorts_engine import events as ev

    require_blend(stage)
    bpy.ops.wm.open_mainfile(filepath=str(stage.blend_path.resolve()))
    scene = bpy.context.scene
    t0 = time.perf_counter()
    kind = cfg.template.events if hasattr(cfg, "template") else "cloth"
    found, debug = EVENT_DETECTORS[kind](cfg, scene)
    found.sort(key=lambda e: e.frame)
    path = cfg.stage_events_path(stage.index)
    ev.save_events(path, found, cfg.fps, stage.index, debug)
    metric(kind="events", stage=stage.index, faces=stage.faces, events=len(found),
           seconds=round(time.perf_counter() - t0, 2), path=str(path))


def cloth_events(cfg, scene):
    """Cloth: distance of a sample of cloth vertices to every collider and to the ground."""
    import numpy as np
    from mathutils import bvhtree

    from shorts_engine import events as ev

    cloth = bpy.data.objects["Cloth"]
    colliders = [o for o in bpy.data.objects if o.name.startswith("Collider")]
    for mod in cloth.modifiers:                      # look only at the simulated mesh, not wireframe/solidify
        if mod.type != "CLOTH":
            mod.show_viewport = False
    trees = []
    for collider in colliders:
        world = collider.matrix_world
        trees.append(bvhtree.BVHTree.FromPolygons([world @ v.co for v in collider.data.vertices],
                                                  [tuple(p.vertices) for p in collider.data.polygons]))
    n = len(cloth.data.vertices)
    sample = np.unique(np.linspace(0, n - 1, min(n, 1500)).astype(int))
    d_collider, d_ground = [], []
    for frame in range(1, cfg.frame_count + 1):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        mesh = cloth.evaluated_get(dg).to_mesh()
        pts = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", pts)
        cloth.evaluated_get(dg).to_mesh_clear()
        pts = pts.reshape(-1, 3)[sample]
        d_ground.append(float(pts[:, 2].min()))
        best = float("inf")
        for tree in trees:
            for p in pts:
                hit = tree.find_nearest(p)
                if hit[0] is not None:
                    best = min(best, hit[3])
        d_collider.append(best)

    # cloth rests about 2x collision_distance (+ collider thickness) away from the surface, so 'touching' is a bit above that
    thr = cfg.physics.collision_distance * 2 + 0.03
    ref = math.sqrt(2 * cfg.physics.gravity * max(cfg.object.cloth_drop_height, 0.1))  # free-fall speed over the drop
    found = (ev.detect_contacts(d_collider, cfg.fps, thr, ref, "impact", "bounce", "Collider")
             + ev.detect_contacts(d_ground, cfg.fps, thr, ref, "landing", "landing", "Ground"))
    return found, {"threshold": round(thr, 4), "ref_speed": round(ref, 3),
                   "collider_distance": [round(d, 4) for d in d_collider],
                   "ground_distance": [round(d, 4) for d in d_ground]}


def impulse_events(cfg, scene):
    """Rigid bodies: velocity changes beyond gravity along each body's trajectory (see events.detect_impulses)."""
    import numpy as np

    from shorts_engine import events as ev

    objs = sorted(tracked_objects(), key=lambda o: o.name)
    traj = np.zeros((cfg.frame_count, len(objs), 3))
    for frame in range(1, cfg.frame_count + 1):
        scene.frame_set(frame)
        for j, o in enumerate(objs):
            traj[frame - 1, j] = o.location
    p = cfg.params
    radius = p.get("ball_radius", p.get("ring_minor", 0.15))
    ref = math.sqrt(2 * cfg.physics.gravity * max(p.get("drop_height", 1.0), 0.5))
    found = ev.detect_impulses(traj, cfg.fps, cfg.physics.gravity, ref, [radius] * len(objs), 0.0, [o.name for o in objs])
    return found, {"ref_speed": round(ref, 3), "bodies": len(objs)}


def _with_accents(base):
    """Wrap a detector: add the story's accent sounds (release whoosh, winner / reveal accent, new pour) from the markers."""
    def detect(cfg, scene):
        from shorts_engine import events as ev
        found, debug = base(cfg, scene)
        m = json.loads(scene["sim_markers"]) if scene.get("sim_markers") else {}
        extra = []
        if "release" in m:                                  # race: the release, then the winner's finish
            extra.append(ev.SimEvent("whoosh", float(m["release"]), 0.8, source="release"))
        if "winner_frame" in m:
            extra.append(ev.SimEvent("bounce", float(m["winner_frame"]) + 1, 1.0, source="winner"))
        if "reveal_start" in m:                             # sheet: the dissolve
            extra.append(ev.SimEvent("whoosh", float(m["reveal_start"]), 0.9, source="reveal"))
        for k, start in enumerate(m.get("pour_starts") or []):
            if start and k > 0:                             # jar: each new, smaller pour
                extra.append(ev.SimEvent("whoosh", float(start), 0.45, source=f"pour_{k}"))
        return found + extra, {**debug, "accents": [e.source for e in extra]}
    return detect


EVENT_DETECTORS = {"cloth": cloth_events, "impulse": impulse_events, "race": _with_accents(impulse_events),
                   "jar": _with_accents(impulse_events), "sheet": _with_accents(cloth_events)}


def main(argv=None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.mode == "card":
        render_card(cfg, args.card_index)
        return
    if not 0 <= args.stage < cfg.stage_count:
        raise SystemExit(f"--stage {args.stage} out of range (0..{cfg.stage_count - 1})")
    stage = cfg.stages()[args.stage]
    if args.mode in ("build", "all"):
        build_stage(cfg, stage)
    if args.mode in ("render", "all"):
        render_stage(cfg, stage, args.frame_start, args.frame_end)
    if args.mode == "hook":
        render_hook(cfg, stage)
    if args.mode == "events":
        detect_stage_events(cfg, stage)


if __name__ == "__main__":
    main()
