"""Orchestrator: plans and runs bake -> render -> ffmpeg for one config.

    python -m shorts_engine.render --config configs/example_cloth.json
    python -m shorts_engine.render --config configs/example_cloth.json --dry-run
    python -m shorts_engine.render --config ... --stages 3 --render-only --frame-start 1 --frame-end 60

Blender is located via ``--blender``, the ``BLENDER_BIN`` env var, or ``blender`` on PATH. If none
is found, ``--use-bpy`` runs the same scripts with the ``bpy`` pip module (Python 3.11 + bpy 4.5).

Because bake and render are separate jobs, independent clips (``--stages``) or frame ranges
(``--frame-start/--frame-end/--chunks``) can be handed to different machines later.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import assemble

try:  # not available on Windows
    import resource
except ImportError:  # pragma: no cover
    resource = None
from .config import Config, ConfigError, load_config

GENERATE_PY = Path(__file__).with_name("generate_scene.py")


@dataclass
class Job:
    name: str
    kind: str  # bake | render | hook_render | card_render | clip | hook | concat
    cmd: list
    stage: int | None = None
    write_text: tuple | None = None  # (path, text) written before running (concat list)
    check_frames: tuple | None = None  # (frames_dir, first, last) that must all exist before running


def find_blender(explicit: str | None = None) -> str | None:
    for candidate in (explicit, os.environ.get("BLENDER_BIN")):
        if candidate:
            return candidate
    return shutil.which("blender")


def split_frame_range(start: int, end: int, chunks: int) -> list[tuple[int, int]]:
    """Split inclusive [start, end] into up to ``chunks`` contiguous, non-empty ranges."""
    if start < 1 or end < start:
        raise ValueError(f"invalid frame range {start}-{end}")
    if chunks < 1:
        raise ValueError("chunks must be >= 1")
    total = end - start + 1
    chunks = min(chunks, total)
    base, extra = divmod(total, chunks)
    ranges, cur = [], start
    for i in range(chunks):
        size = base + (1 if i < extra else 0)
        ranges.append((cur, cur + size - 1))
        cur += size
    return ranges


def scene_cmd(runner: list[str], use_blender: bool, args: list[str]) -> list[str]:
    """Command that runs generate_scene.py either inside Blender or with the bpy module."""
    if use_blender:
        return runner + ["--background", "--python", str(GENERATE_PY), "--"] + args
    return runner + [str(GENERATE_PY)] + args


def plan_jobs(
    cfg: Config,
    config_path: str,
    runner: list[str],
    use_blender: bool,
    stages: list[int] | None = None,
    chunks: int = 1,
    frame_start: int | None = None,
    frame_end: int | None = None,
    do_bake: bool = True,
    do_render: bool = True,
    do_assemble: bool = True,
    ffmpeg: str = "ffmpeg",
    skip_extras: bool = False,
    only_extras: bool = False,
) -> list[Job]:
    """Plan bake/render/encode jobs.

    "Extras" are the closeup hook render and the multiplier cards. They are planned only for a full
    run (all stages, full frame range) or with ``only_extras`` (re-render just those, then assemble).
    ``skip_extras`` plans the plain V1 structure instead (no cards; a closeup hook becomes the tail hook).
    """
    all_stages = cfg.stages()
    selected = stages if stages is not None else list(range(len(all_stages)))
    for i in selected:
        if not 0 <= i < len(all_stages):
            raise ConfigError(f"stage {i} out of range 0..{len(all_stages) - 1}")

    fs = frame_start or 1
    fe = frame_end or cfg.frame_count
    if fe > cfg.frame_count:
        raise ConfigError(f"frame-end {fe} exceeds the {cfg.frame_count} frames per clip")
    full_run = stages is None and (fs, fe) == (1, cfg.frame_count)
    if only_extras:
        selected = []
    extras = (full_run or only_extras) and not skip_extras

    jobs: list[Job] = []
    for i in selected:
        st = all_stages[i]
        base = ["--config", str(config_path), "--stage", str(i)]
        if do_bake:
            jobs.append(Job(f"bake stage {i} ({st.faces} faces)", "bake",
                            scene_cmd(runner, use_blender, base + ["--mode", "build"]), i))
        if do_render:
            for (a, b) in split_frame_range(fs, fe, chunks):
                jobs.append(Job(f"render stage {i} frames {a}-{b}", "render",
                                scene_cmd(runner, use_blender, base + ["--mode", "render",
                                                                       "--frame-start", str(a), "--frame-end", str(b)]), i))

    # skip_extras = plain V1 structure: no cards, and the closeup hook falls back to the tail hook
    hook_mode = cfg.video.hook.mode
    if skip_extras and hook_mode == "closeup":
        hook_mode = "tail"
    closeup = hook_mode == "closeup"
    cards = [] if skip_extras else cfg.cards()
    if extras and do_render:
        if closeup:
            last = len(all_stages) - 1
            jobs.append(Job("render closeup hook", "hook_render",
                            scene_cmd(runner, use_blender, ["--config", str(config_path), "--stage", str(last), "--mode", "hook"]), last))
        for card in cards:
            jobs.append(Job(f"render card {card.index} ({card.title})", "card_render",
                            scene_cmd(runner, use_blender, ["--config", str(config_path), "--mode", "card",
                                                            "--card-index", str(card.index)])))

    if do_assemble and (full_run or only_extras):
        hook_first, hook_last = cfg.hook_frame_range()
        for st in all_stages:
            jobs.append(Job(f"encode clip {st.index}", "clip",
                            assemble.stage_clip_cmd(st.frames_dir, cfg.fps, st.clip_path, cfg.video.crf, ffmpeg), st.index,
                            check_frames=(st.frames_dir, 1, cfg.frame_count)))
        for card in cards:
            jobs.append(Job(f"encode card {card.index}", "clip",
                            assemble.stage_clip_cmd(card.frames_dir, cfg.fps, card.clip_path, cfg.video.crf, ffmpeg),
                            check_frames=(card.frames_dir, 1, card.frames)))

        sequence: list[Path] = []
        for st in all_stages:
            sequence.append(st.clip_path)
            if st.index < len(cards):
                sequence.append(cards[st.index].clip_path)

        hook = cfg.hook_clip_path
        if hook_mode == "closeup":
            jobs.append(Job("encode closeup hook", "hook",
                            assemble.stage_clip_cmd(cfg.hook_frames_dir, cfg.fps, hook, cfg.video.crf, ffmpeg, start_number=hook_first),
                            check_frames=(cfg.hook_frames_dir, hook_first, hook_last)))
            sequence = [hook] + sequence
        elif hook_mode == "tail" and cfg.video.hook_seconds > 0:
            jobs.append(Job("encode hook", "hook",
                            assemble.hook_cmd(all_stages[-1].clip_path, cfg.video.hook_seconds, cfg.fps, hook, cfg.video.crf, ffmpeg)))
            sequence = [hook] + sequence

        list_file = cfg.root_dir / "concat.txt"
        jobs.append(Job("concatenate", "concat",
                        assemble.concat_cmd(list_file, cfg.final_video_path(), ffmpeg),
                        write_text=(list_file, assemble.concat_list_text(sequence))))
    return jobs


def parse_metrics(stdout: str) -> list[dict]:
    out = []
    for line in stdout.splitlines():
        if line.startswith("SHORTS_METRIC "):
            try:
                out.append(json.loads(line[len("SHORTS_METRIC "):]))
            except json.JSONDecodeError:
                pass
    return out


def _peak_child_rss_mb() -> float:
    """Peak resident memory of finished child processes so far (Linux reports KiB, macOS bytes)."""
    if resource is None:
        return 0.0
    raw = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def gpu_name() -> str | None:
    try:
        proc = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip().replace("\n", "; ") if proc.returncode == 0 and proc.stdout.strip() else None


def summarize(cfg: Config, results: list[dict], total_wall: float) -> dict:
    """Production baseline: totals plus the settings that were actually used (read back from Blender)."""
    renders = [m for r in results for m in r["metrics"] if "render_seconds" in m]
    bakes = [m for r in results for m in r["metrics"] if "bake_seconds" in m]
    by_kind: dict = {}
    for r in results:
        by_kind[r["kind"]] = round(by_kind.get(r["kind"], 0.0) + r["wall_seconds"], 1)
    return {
        "config": cfg.name,
        "total_wall_seconds": round(total_wall, 1),
        "wall_seconds_by_job_kind": by_kind,
        "frames_rendered": sum(m.get("frames_rendered", 0) for m in renders),
        "frames_skipped": sum(m.get("frames_skipped", 0) for m in renders),
        "bake_seconds": round(sum(m["bake_seconds"] for m in bakes), 1),
        "render_devices": sorted({m["device"] for m in renders if m.get("device")}),
        "samples_used": sorted({m["samples"] for m in renders if m.get("samples")}),
        "denoiser_used": sorted({str(m.get("denoiser")) for m in renders if "denoiser" in m}),
        "resolutions_used": sorted({f"{m['width']}x{m['height']}" for m in renders if m.get("width")}),
        "gpu": gpu_name(),
        "python": sys.version.split()[0],
    }


def run_jobs(jobs: list[Job], dry_run: bool = False) -> list[dict]:
    results = []
    for job in jobs:
        print(f"\n== {job.name}\n   $ {' '.join(map(str, job.cmd))}", flush=True)
        if dry_run:
            continue
        if job.check_frames:
            fdir, first, last = job.check_frames
            missing = assemble.missing_frames(fdir, last, first)
            if missing:
                shown = ", ".join(map(str, missing[:10])) + (" ..." if len(missing) > 10 else "")
                raise SystemExit(f"cannot run '{job.name}': {len(missing)} frame(s) missing in {fdir}: {shown}")
        if job.write_text:
            path, text = job.write_text
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(text)
        before = _peak_child_rss_mb()
        t0 = time.perf_counter()
        proc = subprocess.run(job.cmd, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        peak_mb = max(before, _peak_child_rss_mb())
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout[-3000:] + "\n" + proc.stderr[-3000:] + "\n")
            raise SystemExit(f"job failed ({proc.returncode}): {job.name}")
        metrics = parse_metrics(proc.stdout)
        results.append({"job": job.name, "kind": job.kind, "wall_seconds": round(wall, 2),
                        "peak_rss_mb_so_far": round(peak_mb, 1), "metrics": metrics})
        for m in metrics:
            print("   ", m)
        print(f"   done in {wall:.1f}s", flush=True)
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bake, render and assemble a simulation Short.")
    p.add_argument("--config", required=True)
    p.add_argument("--blender", help="path to the blender executable")
    p.add_argument("--use-bpy", action="store_true", help="use the bpy pip module instead of a blender binary")
    p.add_argument("--stages", help="comma-separated stage indices (default: all)")
    p.add_argument("--frame-start", type=int)
    p.add_argument("--frame-end", type=int)
    p.add_argument("--chunks", type=int, default=1, help="split the frame range into N render jobs")
    p.add_argument("--bake-only", action="store_true")
    p.add_argument("--render-only", action="store_true", help="skip baking (reuse existing .blend + cache)")
    p.add_argument("--no-assemble", action="store_true")
    p.add_argument("--skip-extras", action="store_true", help="do not render the closeup hook / multiplier cards")
    p.add_argument("--only-extras", action="store_true",
                   help="re-render only the closeup hook and cards (stages must already be rendered), then assemble")
    p.add_argument("--dry-run", action="store_true", help="print the commands without running anything")
    args = p.parse_args(argv)

    try:
        cfg = load_config(args.config)
        if args.use_bpy:
            runner, use_blender = [sys.executable], False
        else:
            blender = find_blender(args.blender)
            if not blender:
                if not args.dry_run:
                    raise ConfigError("blender not found: pass --blender, set BLENDER_BIN, or use --use-bpy")
                blender = "blender"
            runner, use_blender = [blender], True
        stages = [int(s) for s in args.stages.split(",")] if args.stages else None
        jobs = plan_jobs(
            cfg, args.config, runner, use_blender, stages=stages, chunks=args.chunks,
            frame_start=args.frame_start, frame_end=args.frame_end,
            do_bake=not args.render_only, do_render=not args.bake_only,
            do_assemble=not (args.no_assemble or args.bake_only),
            skip_extras=args.skip_extras, only_extras=args.only_extras,
        )
    except (ConfigError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    t_start = time.perf_counter()
    results = run_jobs(jobs, dry_run=args.dry_run)
    if not args.dry_run:
        cfg.root_dir.mkdir(parents=True, exist_ok=True)
        bench = cfg.root_dir / "benchmark.json"
        summary = summarize(cfg, results, time.perf_counter() - t_start)
        bench.write_text(json.dumps({"summary": summary, "jobs": results}, indent=2))
        print(f"\nbenchmark written to {bench}")
        print(json.dumps(summary, indent=2))
        if cfg.final_video_path().exists():
            print(f"final video: {cfg.final_video_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
