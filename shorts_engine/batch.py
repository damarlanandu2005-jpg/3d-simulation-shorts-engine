"""Batch generation: N physically different videos of one (or several) experiments, safely.

    python -m shorts_engine.batch --experiment multiple_balls --variations 10 --seed auto --out output/batches --run
    python -m shorts_engine.batch --experiment auto --variations 8 --out output/batches            # configs only
    python -m shorts_engine.batch --experiment ball_funnel,ring_toss --variations 4 --preset 1080p --run --use-bpy

Per video the batch writes a unique, validated config (+ the variation record), then (with ``--run``) runs the full
pipeline: bake -> render -> events -> assemble -> audio -> QC, producing benchmark.json, metadata.json and
qc_report.json next to the video. One failing video never stops the batch (it is recorded); an existing finished video
with the same config is skipped (``--resume`` behaviour is the default), and a different config is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from .config import ConfigError, from_dict
from .diversity import plan_experiments, summarize
from .library import history_vectors, read_json, scan
from .templates import TEMPLATES
from .variation import PRESETS, generate_variations

MAX_VARIATIONS = 100
_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


def resolve_seed(seed) -> int:
    if seed in (None, "auto"):
        return int(time.time()) % 1_000_000
    try:
        value = int(seed)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"--seed must be 'auto' or a non-negative integer, got {seed!r}") from exc
    if value < 0:
        raise ConfigError("--seed must be >= 0")
    return value


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def plan_batch(experiments: str | list, count: int, master_seed: int, preset: str = "720p",
               library_roots=(), min_distance: float = 0.12) -> list:
    """Variations for the whole batch. ``experiments`` = name, comma list or 'auto' (all, diversity-balanced)."""
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_VARIATIONS:
        raise ConfigError(f"--variations must be an integer between 1 and {MAX_VARIATIONS}, got {count!r}")
    if preset not in PRESETS:
        raise ConfigError(f"--preset must be one of {sorted(PRESETS)}")
    names = None if experiments in ("auto", None) else (experiments.split(",") if isinstance(experiments, str) else list(experiments))
    if names:
        names = [n.strip() for n in names]
    history = history_vectors(scan(library_roots)) if library_roots else []
    slots = plan_experiments(count, names, history, master_seed)
    out, counters = [], {}
    for exp in slots:
        i = counters.get(exp, 0)
        counters[exp] = i + 1
    for exp, n in counters.items():
        avoid = [v for e, v in history if e == exp]
        out += generate_variations(exp, n, master_seed, preset, min_distance=min_distance, avoid=avoid)
    # keep the planned (balanced, non-repeating) order, with batch-unique indices in the names
    by_exp = {e: [v for v in out if v.experiment == e] for e in counters}
    ordered = []
    for exp in slots:
        ordered.append(by_exp[exp].pop(0))
    return ordered


def write_batch(variations, batch_dir: Path, master_seed: int, preset: str) -> dict:
    """Write configs + variation records + manifest. Refuses to overwrite a different config."""
    batch_dir = Path(batch_dir)
    cfg_dir, video_dir = batch_dir / "configs", batch_dir / "videos"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for v in variations:
        if not _SAFE.match(v.name):
            raise ConfigError(f"unsafe output name {v.name!r}")
        cfg = json.loads(json.dumps(v.config))
        cfg["output"] = {**cfg.get("output", {}), "dir": str(video_dir)}
        from_dict(json.loads(json.dumps(cfg)))
        path = cfg_dir / f"{v.name}.json"
        h = config_hash(cfg)
        if path.exists() and config_hash(json.loads(path.read_text())) != h:
            raise ConfigError(f"{path} already exists with a different configuration; use another --seed or --out")
        path.write_text(json.dumps(cfg, indent=1))
        Path(str(path) + ".meta.json").write_text(json.dumps({**v.info(), "batch_seed": master_seed, "preset": preset,
                                                              "config_hash": h}, indent=1))
        items.append({"name": v.name, "experiment": v.experiment, "seed": v.seed, "config": str(path), "config_hash": h,
                      "changed": v.changed, "stage_values": v.stage_values, "shape": v.shape, "status": "planned"})
    manifest = {"version": 1, "batch_seed": master_seed, "preset": preset, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "count": len(items), "experiments": summarize([i["experiment"] for i in items]), "items": items}
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def already_done(item: dict, video_root: Path) -> bool:
    qc = read_json(Path(video_root) / item["name"] / "qc_report.json")
    meta = read_json(Path(video_root) / item["name"] / "metadata.json")
    return bool(qc and qc.get("passed") and meta and (meta.get("variation") or {}).get("config_hash") == item["config_hash"])


def safe_config(cfg: dict) -> dict:
    """A cheaper, more conservative render of the same physical experiment (same seed, same parameters)."""
    safe = json.loads(json.dumps(cfg))
    safe.setdefault("render", {}).update({"samples": 8, "denoise": False})
    safe["camera"] = {**(safe.get("camera") or {}), "preset": "wide", "motion": "static"}
    safe["hook"] = {**(safe.get("hook") or {}), "mode": "closeup"}
    return safe


def _run_once(runner, cfg_path, render_args, item):
    try:
        return runner(["--config", str(cfg_path), *render_args])
    except SystemExit as exc:                                       # job failures raise SystemExit in the orchestrator
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:                                        # noqa: BLE001 - isolate any per-video failure
        item["error"] = repr(exc)[:300]
        return 1


def run_batch(manifest: dict, batch_dir: Path, render_args: list[str], runner=None) -> dict:
    """Run every planned video; record status/duration/QC per item; never stop on a single failure."""
    from . import render
    runner = runner or render.main
    batch_dir = Path(batch_dir)
    t0 = time.perf_counter()
    for item in manifest["items"]:
        if already_done(item, batch_dir / "videos"):
            item["status"] = "skipped_existing"
            continue
        t = time.perf_counter()
        code = _run_once(runner, item["config"], render_args, item)
        vdir = batch_dir / "videos" / item["name"]
        qc0 = read_json(vdir / "qc_report.json")
        if code != 0 or (qc0 and qc0.get("passed") is False):         # diagnose, then retry once with a safe configuration
            item["attempts"] = [{"config": item["config"], "exit_code": code, "error": item.get("error"),
                                 "qc_failures": (qc0 or {}).get("failures") or (qc0 or {}).get("errors")}]
            safe_path = Path(item["config"]).with_name(Path(item["config"]).stem + ".safe.json")
            safe_path.write_text(json.dumps(safe_config(json.loads(Path(item["config"]).read_text())), indent=1))
            meta = Path(str(item["config"]) + ".meta.json")
            if meta.is_file():
                Path(str(safe_path) + ".meta.json").write_text(meta.read_text())
            code = _run_once(runner, safe_path, render_args, item)
            item["retried_with_safe_config"] = str(safe_path)
            item["attempts"].append({"config": str(safe_path), "exit_code": code})
        item["seconds"] = round(time.perf_counter() - t, 1)
        item["exit_code"] = code
        qc = read_json(batch_dir / "videos" / item["name"] / "qc_report.json")
        item["qc_passed"] = qc.get("passed") if qc else None
        item["status"] = "ok" if code == 0 and item["qc_passed"] is not False else ("qc_failed" if code == 3 else "failed")
        (batch_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    manifest["total_seconds"] = round(time.perf_counter() - t0, 1)
    manifest["status_counts"] = summarize([i["status"] for i in manifest["items"]])
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shorts_engine.batch", description="Generate a batch of physically different Shorts.")
    p.add_argument("--experiment", default="auto", help=f"name, comma list or 'auto'; available: {', '.join(sorted(TEMPLATES))}")
    p.add_argument("--variations", type=int, default=4)
    p.add_argument("--seed", default="auto", help="master seed or 'auto' (recorded in the manifest)")
    p.add_argument("--preset", default="720p", choices=sorted(PRESETS))
    p.add_argument("--out", default="output/batches")
    p.add_argument("--run", action="store_true", help="render the videos (default: only write the configs + manifest)")
    p.add_argument("--use-bpy", action="store_true")
    p.add_argument("--blender")
    p.add_argument("--library", action="append", default=[], help="existing output dir(s) to stay diverse from")
    args = p.parse_args(argv)
    try:
        seed = resolve_seed(args.seed)
        variations = plan_batch(args.experiment, args.variations, seed, args.preset, args.library or [args.out])
        batch_dir = Path(args.out) / f"batch_{seed}"
        manifest = write_batch(variations, batch_dir, seed, args.preset)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"batch {batch_dir}: {manifest['count']} video(s) {manifest['experiments']} (seed {seed}, {args.preset})")
    for it in manifest["items"]:
        print(f"  {it['name']:<34} {it['experiment']:<15} changed={it['changed']} stages={it['stage_values']} shape={it['shape']}")
    if not args.run:
        print(f"configs written; run them with --run (manifest: {batch_dir / 'manifest.json'})")
        return 0
    render_args = (["--use-bpy"] if args.use_bpy else []) + (["--blender", args.blender] if args.blender else [])
    manifest = run_batch(manifest, batch_dir, render_args)
    print(f"batch finished in {manifest['total_seconds']}s: {manifest['status_counts']}")
    return 0 if all(i["status"] in ("ok", "skipped_existing") for i in manifest["items"]) else 1


if __name__ == "__main__":
    sys.exit(main())
