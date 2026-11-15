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
    p.add_argument("--mode", choices=["build", "render", "all", "hook", "card"], default="all")
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
    materials.setup_world(scene, cfg.material.background_color)
    materials.add_lights(scene)

    cam = camera.add_camera(scene, cfg.camera_for_stage(stage.index), cfg.output.width, cfg.output.height)
    label_mat = materials.emission("LabelMat", cfg.label.color, 1.0)
    camera.add_label(scene, cam, stage.label, cfg.label.size, label_mat)

    builder = simulation.SIMULATORS[cfg.simulation]
    cloth = builder(scene, cfg, stage)

    # The disk cache lives next to the .blend, so save before baking.
    stage.blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(stage.blend_path.resolve()))
    setup_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    method = simulation.bake(scene, cloth, 1, cfg.frame_count)
    bake_s = time.perf_counter() - t1
    bpy.ops.wm.save_mainfile()
    metric(stage=stage.index, faces=stage.faces, setup_seconds=round(setup_s, 2),
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

    render_frames(scene, range(frame_start, frame_end + 1), lambda f: stage.frames_dir / f"frame_{f:04d}.png",
                  stage.index, stage.faces, device, denoiser)


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


def main(argv=None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.mode == "card":
        render_card(cfg, args.card_index)
        return
    if not 0 <= args.stage < len(cfg.resolutions):
        raise SystemExit(f"--stage {args.stage} out of range (0..{len(cfg.resolutions) - 1})")
    stage = cfg.stages()[args.stage]
    if args.mode in ("build", "all"):
        build_stage(cfg, stage)
    if args.mode in ("render", "all"):
        render_stage(cfg, stage, args.frame_start, args.frame_end)
    if args.mode == "hook":
        render_hook(cfg, stage)


if __name__ == "__main__":
    main()
