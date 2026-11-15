"""Compare Cycles sample counts and denoising: render time vs. similarity to a high-sample reference.

    python kaggle/quality_sweep.py                       # 16384 faces, 720x1280, samples 32/16/8
    python kaggle/quality_sweep.py --samples 64,32,16,8 --reference-samples 256
    python kaggle/quality_sweep.py --python /path/to/venv/bin/python

Bakes once, then renders the SAME frames for every variant (with and without denoising) and
a reference. PSNR/SSIM against the reference are rough guides only: open the images in
output/quality_sweep/compare/ (montage.png shows them side by side) before choosing settings.
Needs Python 3.11 + bpy 4.5 (see kaggle/setup_kaggle.sh). No credentials involved.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_benchmark import run_scene, sh  # noqa: E402


def write_config(path: Path, args, samples: int, denoise: bool, out_dir: Path) -> None:
    path.write_text(json.dumps({
        "name": "quality_sweep",
        "resolutions": [args.faces],
        "fps": 30,
        "duration": args.duration,
        "output": {"width": args.width, "height": args.height, "dir": str(out_dir)},
        "render": {"samples": samples, "denoise": denoise, "device": args.device},
    }, indent=2))


def ffmpeg_score(ref: Path, img: Path, kind: str) -> float | None:
    graph = "[0][1]psnr" if kind == "psnr" else "[0][1]ssim"
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(img), "-i", str(ref), "-lavfi", graph, "-f", "null", "-"],
                          capture_output=True, text=True)
    m = re.search(r"average:(inf|[\d.]+)" if kind == "psnr" else r"All:([\d.]+)", proc.stderr)
    if not m:
        return None
    return 99.0 if m.group(1) == "inf" else float(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--faces", type=int, default=16384)
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=1280)
    ap.add_argument("--duration", type=float, default=4.0)
    ap.add_argument("--samples", default="32,16,8", help="comma-separated sample counts to test")
    ap.add_argument("--reference-samples", type=int, default=128)
    ap.add_argument("--frames", type=int, default=2, help="frames timed per variant")
    ap.add_argument("--device", default="AUTO", choices=["AUTO", "CPU", "GPU"])
    ap.add_argument("--out", default="output/quality_sweep")
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    compare = out_dir / "compare"
    compare.mkdir()
    sample_list = [int(s) for s in args.samples.split(",")]
    total = round(args.duration * 30)
    mid = max(1, total // 2)
    frames_dir = out_dir / "quality_sweep" / f"stage_00_{args.faces}" / "frames"

    variants = [("reference", args.reference_samples, True)]
    for s in sample_list:
        variants += [(f"s{s}_denoise", s, True), (f"s{s}_raw", s, False)]

    cfgs = {}
    for name, s, dn in variants:
        cfgs[name] = out_dir / f"{name}.json"
        write_config(cfgs[name], args, s, dn, out_dir)

    print(f"[bake] {args.faces} faces x {total} frames ...")
    bake, _ = run_scene(args.python, cfgs["reference"], "--mode", "build")
    print("   bake:", bake.get("bake_seconds"), "s via", bake.get("bake_method"))

    print("[warm-up] one throwaway frame (kernel load) ...")
    run_scene(args.python, cfgs["reference"], "--mode", "render", "--frame-start", str(mid - 1), "--frame-end", str(mid - 1))

    rows = []
    for name, s, dn in variants:
        shutil.rmtree(frames_dir, ignore_errors=True)
        m, _ = run_scene(args.python, cfgs[name], "--mode", "render",
                         "--frame-start", str(mid), "--frame-end", str(mid + args.frames - 1))
        shutil.copy(frames_dir / f"frame_{mid:04d}.png", compare / f"{name}.png")
        rows.append({"variant": name, "samples": s, "denoise": dn, "device": m.get("device"),
                     "seconds_per_frame": m.get("seconds_per_frame")})
        print(f"   {name:14s} {m.get('seconds_per_frame')} s/frame on {m.get('device')}")

    ref = compare / "reference.png"
    for r in rows:
        if r["variant"] == "reference":
            continue
        img = compare / f"{r['variant']}.png"
        r["psnr_db"] = ffmpeg_score(ref, img, "psnr")
        r["ssim"] = ffmpeg_score(ref, img, "ssim")

    ordered = [compare / f"{r['variant']}.png" for r in rows]
    inputs = sum((["-i", str(p)] for p in ordered), [])
    chains = ";".join(f"[{i}]scale=240:-1[a{i}]" for i in range(len(ordered)))
    stack = "".join(f"[a{i}]" for i in range(len(ordered))) + f"hstack=inputs={len(ordered)}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", f"{chains};{stack}",
                    str(compare / "montage.png")], check=False)

    print("\nvariant         samples denoise  s/frame   PSNR dB   SSIM")
    for r in rows:
        print(f"{r['variant']:15s} {r['samples']:7d} {str(r['denoise']):7s} {str(r['seconds_per_frame']):8s} "
              f"{str(r.get('psnr_db', '-')):9s} {r.get('ssim', '-')}")
    good = [r for r in rows if r.get("ssim") and r["ssim"] >= 0.98 and r["seconds_per_frame"]]
    if good:
        best = min(good, key=lambda r: r["seconds_per_frame"])
        print(f"\nfastest with SSIM >= 0.98: {best['variant']} ({best['seconds_per_frame']} s/frame). "
              "Suggestion only: check compare/montage.png yourself.")
    else:
        print("\nno variant reached SSIM 0.98 against the reference; compare the images by eye.")
    print("order in montage.png (left to right):", ", ".join(r["variant"] for r in rows))
    (out_dir / "quality_sweep_result.json").write_text(json.dumps(
        {"settings": {k: getattr(args, k) for k in ("faces", "width", "height", "device", "frames", "reference_samples")},
         "bake_seconds": bake.get("bake_seconds"), "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
