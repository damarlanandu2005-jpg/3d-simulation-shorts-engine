"""Blender entry point. Runs inside Blender (or inside the ``bpy`` pip module).

    blender --background --python shorts_engine/generate_scene.py -- \
        --config configs/example_cloth.json --stage 0 --mode build
    blender --background --python shorts_engine/generate_scene.py -- \
        --config configs/example_cloth.json --stage 0 --mode render --frame-start 1 --frame-end 60

Modes:
    build   create the scene, save the .blend, bake the physics cache next to it
    render  open the saved .blend and render a frame range to PNGs (skips existing frames)
    all     build then render every frame

Splitting "build" from "render" means physics is baked once and any number of workers can
render different frame ranges from the same .blend + cache.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

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
    p.add_argument("--stage", type=int, required=True, help="index into config.resolutions")
    p.add_argument("--mode", choices=["build", "render", "all"], default="all")
    p.add_argument("--frame-start", type=int, default=None)
    p.add_argument("--frame-end", type=int, default=None)
    return p.parse_args(argv)


def apply_render_settings(scene, cfg) -> None:
    """Settings that must follow the CURRENT config at render time (not the value saved in the .blend)."""
    scene.render.resolution_x = cfg.output.width
    scene.render.resolution_y = cfg.output.height
    scene.render.resolution_percentage = 100
    scene.render.engine = cfg.render.engine
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    cy = scene.cycles
    cy.samples = cfg.render.samples
    cy.max_bounces = cfg.render.max_bounces
    cy.use_denoising = cfg.render.denoise
    if cfg.render.denoise:
        cy.denoiser = "OPENIMAGEDENOISE"


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

    cam = camera.add_camera(scene, cfg.camera, cfg.output.width, cfg.output.height)
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


def render_stage(cfg, stage, frame_start, frame_end) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(stage.blend_path.resolve()))
    scene = bpy.context.scene
    apply_render_settings(scene, cfg)  # samples/denoise/resolution come from the config, not the saved .blend
    device = select_device(scene, cfg.render.device)
    stage.frames_dir.mkdir(parents=True, exist_ok=True)

    frame_start = frame_start or 1
    frame_end = frame_end or cfg.frame_count
    if not (1 <= frame_start <= frame_end <= cfg.frame_count):
        raise SystemExit(f"frame range {frame_start}-{frame_end} outside 1-{cfg.frame_count}")

    t0 = time.perf_counter()
    rendered = skipped = 0
    for frame in range(frame_start, frame_end + 1):
        out = stage.frames_dir / f"frame_{frame:04d}.png"
        if out.exists():
            skipped += 1
            continue
        scene.frame_set(frame)
        scene.render.filepath = str(out.resolve())
        bpy.ops.render.render(write_still=True)
        rendered += 1
    render_s = time.perf_counter() - t0
    metric(stage=stage.index, faces=stage.faces, render_seconds=round(render_s, 2), device=device,
           frames_rendered=rendered, frames_skipped=skipped,
           seconds_per_frame=round(render_s / rendered, 2) if rendered else None,
           samples=scene.cycles.samples, denoise=scene.cycles.use_denoising,
           width=scene.render.resolution_x, height=scene.render.resolution_y)


def main(argv=None) -> None:
    args = parse_args(argv)
    cfg = load_config(args.config)
    if not 0 <= args.stage < len(cfg.resolutions):
        raise SystemExit(f"--stage {args.stage} out of range (0..{len(cfg.resolutions) - 1})")
    stage = cfg.stages()[args.stage]
    if args.mode in ("build", "all"):
        build_stage(cfg, stage)
    if args.mode in ("render", "all"):
        render_stage(cfg, stage, args.frame_start, args.frame_end)


if __name__ == "__main__":
    main()
