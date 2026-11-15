"""Measure Cycles render speed for this project's heaviest stage (16384-face cloth).

Run it in the environment you want to measure (e.g. a Kaggle notebook with a GPU):

    python kaggle/gpu_benchmark.py                 # 16384 faces, 720x1280, 32 samples
    python kaggle/gpu_benchmark.py --faces 1024    # quicker sanity run
    python kaggle/gpu_benchmark.py --python /path/to/venv/bin/python

Needs Python 3.11 with bpy 4.5 (see kaggle/setup_kaggle.sh). Writes benchmark_result.json: send
that file (or the printed summary) back. Nothing here uploads anything or needs credentials.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shorts_engine.render import parse_metrics  # noqa: E402

GEN = ROOT / "shorts_engine" / "generate_scene.py"

DEVICE_PROBE = r"""
import bpy, json
bpy.ops.wm.read_factory_settings(use_empty=True)
prefs = bpy.context.preferences.addons["cycles"].preferences
out = {}
for t in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
    try:
        prefs.compute_device_type = t
        prefs.get_devices()
        out[t] = [d.name for d in prefs.devices if d.type == t]
    except Exception as e:
        out[t] = "error: " + repr(e)[:80]
print("DEVICES " + json.dumps(out))
print("BPY " + bpy.app.version_string)
"""


def sh(cmd, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    except FileNotFoundError:  # e.g. nvidia-smi on a machine without an NVIDIA driver
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: not found")


def write_config(path: Path, args, device: str, out_dir: Path) -> None:
    path.write_text(json.dumps({
        "name": "gpu_bench",
        "resolutions": [args.faces],
        "fps": 30,
        "duration": args.duration,
        "output": {"width": args.width, "height": args.height, "dir": str(out_dir)},
        "render": {"samples": args.samples, "device": device},
    }, indent=2))


def run_scene(py, cfg_path, *extra):
    t0 = time.perf_counter()
    proc = sh([py, str(GEN), "--config", str(cfg_path), "--stage", "0", *extra])
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-3000:] + proc.stderr[-3000:])
        raise SystemExit(f"failed: {' '.join(extra)}")
    metrics = parse_metrics(proc.stdout)
    return (metrics[-1] if metrics else {}), wall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable, help="python with bpy 4.5 installed")
    ap.add_argument("--faces", type=int, default=16384)
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--duration", type=float, default=4.0, help="seconds of animation (30 fps)")
    ap.add_argument("--frames", type=int, default=4, help="measured frames per device")
    ap.add_argument("--no-cpu", action="store_true", help="skip the CPU comparison")
    ap.add_argument("--out", default="output/gpu_bench")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "settings": {k: getattr(args, k) for k in ("faces", "width", "height", "samples", "duration", "frames")}}

    smi = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    result["nvidia_smi"] = smi.stdout.strip() if smi.returncode == 0 else "not available (no NVIDIA GPU visible)"
    probe = sh([args.python, "-c", DEVICE_PROBE])
    if probe.returncode != 0:
        sys.stderr.write(probe.stderr[-2000:])
        raise SystemExit("could not import bpy with that python; run kaggle/setup_kaggle.sh first")
    for line in probe.stdout.splitlines():
        if line.startswith("DEVICES "):
            result["cycles_devices"] = json.loads(line[8:])
        if line.startswith("BPY "):
            result["bpy"] = line[4:]
    print("GPU:", result["nvidia_smi"])
    print("Cycles devices:", result["cycles_devices"])

    cfg_auto, cfg_cpu = out_dir / "auto.json", out_dir / "cpu.json"
    write_config(cfg_auto, args, "AUTO", out_dir)
    write_config(cfg_cpu, args, "CPU", out_dir)
    total_frames = round(args.duration * 30)
    first = max(1, total_frames // 2)            # mid-animation frames, cloth already draped

    print(f"\n[1/3] Baking {args.faces} faces x {total_frames} frames (CPU-only step)...")
    bake, bake_wall = run_scene(args.python, cfg_auto, "--mode", "build")
    result["bake"] = {"seconds": bake.get("bake_seconds"), "method": bake.get("bake_method"), "wall": round(bake_wall, 1)}
    print("      bake:", result["bake"])

    print("\n[2/3] Rendering on AUTO device (first frame = warm-up, kernel load)...")
    warm, _ = run_scene(args.python, cfg_auto, "--mode", "render", "--frame-start", str(first), "--frame-end", str(first))
    meas, _ = run_scene(args.python, cfg_auto, "--mode", "render",
                        "--frame-start", str(first + 1), "--frame-end", str(first + args.frames))
    result["auto"] = {"device": meas.get("device"), "warmup_seconds": warm.get("render_seconds"),
                      "seconds_per_frame": meas.get("seconds_per_frame")}
    print("      auto:", result["auto"])

    if not args.no_cpu:
        print("\n[3/3] Rendering on CPU for comparison...")
        s = first + args.frames + 1
        cpu, _ = run_scene(args.python, cfg_cpu, "--mode", "render", "--frame-start", str(s), "--frame-end", str(s + 1))
        result["cpu"] = {"device": cpu.get("device"), "seconds_per_frame": cpu.get("seconds_per_frame")}
        print("      cpu:", result["cpu"])

    used_gpu = result["auto"]["device"] not in (None, "CPU")
    result["gpu_used"] = used_gpu
    spf = result["auto"]["seconds_per_frame"]
    if spf:
        frames_all = 4 * total_frames  # 4 stages in the example config; lower stages render no slower
        result["estimate_full_example_minutes"] = round(spf * frames_all / 60, 1)
        result["estimate_note"] = (f"{frames_all} frames x {spf}s/frame on {result['auto']['device']}; "
                                   "bake time for the other stages not included")
    (out_dir / "benchmark_result.json").write_text(json.dumps(result, indent=2))
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2))
    if not used_gpu:
        print("\nWARNING: Cycles fell back to CPU. Check the accelerator setting and the device list above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
