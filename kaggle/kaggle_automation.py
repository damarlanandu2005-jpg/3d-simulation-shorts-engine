#!/usr/bin/env python3
"""GitHub -> Kaggle GPU test automation helper (stdlib only).

Subcommands (all driven by the GitHub workflow .github/workflows/kaggle-gpu-test.yml):

  prepare   write a Kaggle kernel folder (script + kernel-metadata.json) for one fixed test config
  wait      poll `kaggle kernels status` until the run finishes; exit non-zero unless COMPLETE
  verify    check the downloaded kernel output has the .mp4, benchmark.json and run_info.json

Safety rules enforced here:
  * The test is chosen by a KEY (baseline | optix | 1080p | one of the experiment keys) that maps to a fixed
    config path, or by a validated repo-relative ``configs/**.json`` path (``--config-path``: strict pattern, no
    ``..``, must exist in the pinned checkout and load as a valid config), or it is a BATCH of an allow-listed
    experiment (``--batch-experiment/--batch-variations/--batch-seed/--preset``, each validated).
    Nothing else from the caller ever reaches the kernel script (no free-form commands).
  * The commit is a 40-char hex SHA, the repo URL is a constant.
  * No credentials are written into the kernel; the kernel clones a PUBLIC repo.
  * Credentials are only read from the environment by the `kaggle` CLI; this file never prints them.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_URL = "https://github.com/damarlanandu2005-jpg/3d-simulation-shorts-engine.git"

# The ONLY configs the automation may run. Key -> (repo-relative config path, output name in config).
CONFIGS = {
    "baseline": ("configs/v1_1_a_baseline.json", "v1_1_a"),
    "optix": ("configs/v1_1_b_optix.json", "v1_1_b"),
    "1080p": ("configs/v1_1_c_1080p.json", "v1_1_c"),
}

# Experiment configs (Phases 3-4) that may be rendered by key, in addition to the three V1.1 tests above.
EXPERIMENT_CONFIGS = {
    "multiple_balls": ("configs/experiments/multiple_balls_100.json", "multiple_balls_100"),
    "ball_funnel": ("configs/experiments/ball_funnel_hole.json", "ball_funnel_hole"),
    "ring_toss": ("configs/experiments/ring_toss_smaller.json", "ring_toss_smaller"),
    "cloth_objects": ("configs/experiments/cloth_objects_more.json", "cloth_objects_more"),
}
ALL_CONFIGS = {**CONFIGS, **EXPERIMENT_CONFIGS}
CONFIG_PATH_RE = re.compile(r"^configs/[A-Za-z0-9_][A-Za-z0-9_./-]{0,120}\.json$")
PRESETS = ("720p", "1080p")
MAX_BATCH_VARIATIONS = 12      # keeps a batch inside a Kaggle session (a 720p video takes ~15-25 min on a T4)
REPO_ROOT = Path(__file__).resolve().parent.parent

ACCELERATOR = "NvidiaTeslaT4"  # default; passed to `kaggle kernels push --accelerator`
ACCELERATORS = ("NvidiaTeslaT4", "NvidiaL4", "default")  # "default" = request a GPU, let Kaggle choose
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
RUN_RE = re.compile(r"^[0-9]{1,20}$")

TERMINAL_OK = {"COMPLETE"}
TERMINAL_BAD = {"ERROR", "CANCEL_ACKNOWLEDGED", "CANCELLED", "CANCELED"}


class AutomationError(Exception):
    pass


def resolve_config(key: str) -> tuple[str, str]:
    if key not in ALL_CONFIGS:
        raise AutomationError(f"unknown test_config {key!r}; allowed: {', '.join(ALL_CONFIGS)}")
    return ALL_CONFIGS[key]


def resolve_config_path(path: str, root: Path = REPO_ROOT) -> tuple[str, str]:
    """A repo-relative config path chosen by the caller: strictly validated, must load as a real config."""
    if not isinstance(path, str) or not CONFIG_PATH_RE.match(path) or ".." in path.split("/") or "//" in path:
        raise AutomationError(f"config path {path!r} must look like configs/<name>.json (letters, digits, _ . - /; no '..')")
    full = (root / path).resolve()
    if root.resolve() not in full.parents or not full.is_file():
        raise AutomationError(f"config {path} does not exist in this checkout")
    try:
        data = json.loads(full.read_text())
    except json.JSONDecodeError as exc:
        raise AutomationError(f"config {path} is not valid JSON: {exc}") from exc
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not re.match(r"^[A-Za-z0-9_.-]{1,80}$", name):
        raise AutomationError(f"config {path} needs a simple string 'name' (letters, digits, _ . -)")
    sys.path.insert(0, str(root))
    try:
        from shorts_engine.config import ConfigError, load_config
        try:
            load_config(full)
        except ConfigError as exc:
            raise AutomationError(f"config {path} is invalid: {exc}") from exc
    finally:
        sys.path.remove(str(root))
    return path, name


def validate_batch(experiment: str, variations, seed, preset: str, root: Path = REPO_ROOT) -> dict:
    sys.path.insert(0, str(root))
    try:
        from shorts_engine.templates import TEMPLATES
    finally:
        sys.path.remove(str(root))
    if experiment != "auto" and experiment not in TEMPLATES:
        raise AutomationError(f"batch experiment must be 'auto' or one of {sorted(TEMPLATES)}, got {experiment!r}")
    try:
        n, sd = int(variations), int(seed)
    except (TypeError, ValueError) as exc:
        raise AutomationError("batch variations and seed must be integers") from exc
    if not 1 <= n <= MAX_BATCH_VARIATIONS:
        raise AutomationError(f"batch variations must be between 1 and {MAX_BATCH_VARIATIONS}")
    if not 0 <= sd <= 999_999:
        raise AutomationError("batch seed must be between 0 and 999999")
    if preset not in PRESETS:
        raise AutomationError(f"preset must be one of {PRESETS}")
    return {"experiment": experiment, "variations": n, "seed": sd, "preset": preset}


def kernel_slug(key: str, sha: str, run_id: str) -> str:
    """Unique per workflow run so a stale previous run can never be mistaken for this one."""
    return f"se-v11-{key.replace('_', '-')}-{sha[:7]}-{run_id}".lower()


# ---------------------------------------------------------------- kernel script

KERNEL_TEMPLATE = r'''# Generated by kaggle/kaggle_automation.py -- do not edit by hand.
import atexit, json, os, re, shutil, subprocess, sys, time, traceback
from pathlib import Path

REPO_URL = __REPO_URL__
SHA = __SHA__
CONFIG = __CONFIG__          # fixed repo-relative path from the allow-list
OUT_NAME = __OUT_NAME__
KEY = __KEY__
BATCH = __BATCH__            # None for a single video, else {"experiment", "variations", "seed", "preset"}

WORK = Path("/kaggle/working")
RESULT = WORK / "result"
BUILD = Path("/tmp/se_build")  # repo + frames live here, NOT in /kaggle/working, so they are not saved as kernel output
atexit.register(lambda: shutil.rmtree(WORK / "venv311", ignore_errors=True))  # setup_kaggle.sh may create it
RESULT.mkdir(parents=True, exist_ok=True)
info = {"test_config": KEY, "config": CONFIG, "commit": SHA, "status": "started",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def save_info():
    (RESULT / "run_info.json").write_text(json.dumps(info, indent=2))


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def fail(msg):
    info["status"] = "failed"
    info["error"] = msg
    save_info()
    print("FAILED:", msg, flush=True)
    sys.exit(1)


try:
    save_info()
    # 1. GPU must be present -- fail loudly otherwise (a CPU render would silently take hours).
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                          "--format=csv,noheader"], capture_output=True, text=True)
    if gpu.returncode != 0 or not gpu.stdout.strip():
        fail("no GPU visible (nvidia-smi failed). Kernel was not given a GPU accelerator.")
    info["gpu"] = gpu.stdout.strip()
    print("GPU:", info["gpu"], flush=True)

    # 2. Clone the exact commit (public repo, no credentials).
    BUILD.mkdir(parents=True, exist_ok=True)
    repo = BUILD / "repo"
    if repo.exists():
        shutil.rmtree(repo)
    run(["git", "clone", "--quiet", REPO_URL, str(repo)])
    run(["git", "-C", str(repo), "checkout", "--quiet", SHA])
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    if head != SHA:
        fail(f"checked-out commit {head} != requested {SHA}")
    info["checked_out"] = head
    if not BATCH and not (repo / CONFIG).is_file():
        fail(f"config missing at that commit: {CONFIG}")

    # 3. Setup: bpy + ffmpeg. The last line printed is ENGINE_PYTHON=<interpreter>.
    setup = subprocess.run(["bash", "kaggle/setup_kaggle.sh"], cwd=repo, capture_output=True,
                           text=True)
    print(setup.stdout[-4000:], flush=True)
    print(setup.stderr[-2000:], file=sys.stderr, flush=True)
    if setup.returncode != 0:
        fail(f"kaggle/setup_kaggle.sh exited {setup.returncode}. stdout tail:\n{setup.stdout[-1500:]}\nstderr tail:\n{setup.stderr[-1500:]}")
    m = re.findall(r"^ENGINE_PYTHON=(.+)$", setup.stdout, flags=re.M)
    if not m:
        fail("setup_kaggle.sh did not print ENGINE_PYTHON=")
    py = m[-1].strip()
    info["engine_python"] = py

    # 4. Verify bpy imports with that interpreter.
    chk = subprocess.run([py, "-c", "import bpy; print(bpy.app.version_string)"],
                         capture_output=True, text=True)
    if chk.returncode != 0:
        fail("import bpy failed with " + py + ": " + chk.stderr[-800:])
    info["bpy"] = chk.stdout.strip()

    # 5. Render. Render settings come from the config untouched (single video) or from the batch preset.
    info["status"] = "rendering"
    save_info()
    t0 = time.time()
    tail = []
    if BATCH is None:
        cmd = [py, "-m", "shorts_engine.render", "--config", CONFIG, "--use-bpy"]
    else:
        cmd = [py, "-m", "shorts_engine.batch", "--experiment", BATCH["experiment"], "--variations", str(BATCH["variations"]),
               "--seed", str(BATCH["seed"]), "--preset", BATCH["preset"], "--out", "output/batches", "--run", "--use-bpy"]
        info["batch"] = BATCH
    with open(RESULT / "render.log", "w") as logf:
        proc = subprocess.Popen(cmd, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            print(line, end="", flush=True)
            logf.write(line)
            tail.append(line)
            tail = tail[-60:]
        proc.wait()
    info["wall_seconds"] = round(time.time() - t0, 1)
    if proc.returncode != 0:
        fail(f"render exited {proc.returncode}. Last output:\n" + "".join(tail)[-2500:])

    # 6. Collect outputs and require them.
    PER_VIDEO = ("benchmark.json", "metadata.json", "qc_report.json", "audio_timeline.json")
    if BATCH is None:
        out_dir = repo / "output" / OUT_NAME
        mp4, bench = out_dir / f"{OUT_NAME}.mp4", out_dir / "benchmark.json"
        if not mp4.is_file() or mp4.stat().st_size == 0:
            fail(f"missing or empty video: {mp4}")
        if not bench.is_file():
            fail(f"missing benchmark.json: {bench}")
        shutil.copy2(mp4, RESULT / mp4.name)
        for fname in PER_VIDEO:
            if (out_dir / fname).is_file():
                shutil.copy2(out_dir / fname, RESULT / fname)
        files = [mp4]
    else:
        batch_dir = repo / "output" / "batches" / f"batch_{BATCH['seed']}"
        manifest = json.loads((batch_dir / "manifest.json").read_text())
        shutil.copy2(batch_dir / "manifest.json", RESULT / "manifest.json")
        files = []
        for item in manifest["items"]:
            vdir = batch_dir / "videos" / item["name"]
            dest = RESULT / item["name"]
            dest.mkdir(parents=True, exist_ok=True)
            for fname in (f"{item['name']}.mp4",) + PER_VIDEO:
                if (vdir / fname).is_file():
                    shutil.copy2(vdir / fname, dest / fname)
            if (vdir / f"{item['name']}.mp4").is_file():
                files.append(vdir / f"{item['name']}.mp4")
        subprocess.run([py, "-m", "shorts_engine.library", "index", str(batch_dir)], cwd=repo, check=False)
        if (batch_dir / "library.json").is_file():
            shutil.copy2(batch_dir / "library.json", RESULT / "library.json")
        info["batch_status"] = manifest.get("status_counts")
    info["streams"] = []
    for f in files:
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,duration",
                             "-of", "compact", str(f)], capture_output=True, text=True)
        info["streams"] += [f"{f.stem}: {line}" for line in pr.stdout.strip().splitlines()]
    info["status"] = "ok"
    info["video_bytes"] = sum(f.stat().st_size for f in files)
    save_info()
    print("DONE", json.dumps(info), flush=True)
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    info["status"] = "failed"
    info["error"] = traceback.format_exc()[-1500:]
    save_info()
    sys.exit(1)
'''


def build_kernel_script(key: str, sha: str, config: tuple | None = None, batch: dict | None = None) -> str:
    """``config`` = (path, output name) already validated by resolve_config_path; ``batch`` by validate_batch."""
    if batch is not None:
        cfg, out_name = "", "batch"
    else:
        cfg, out_name = config if config is not None else resolve_config(key)
    if not SHA_RE.match(sha):
        raise AutomationError("commit must be a full 40-char lowercase hex SHA")
    script = KERNEL_TEMPLATE
    for token, value in {
        "__REPO_URL__": REPO_URL, "__SHA__": sha, "__CONFIG__": cfg,
        "__OUT_NAME__": out_name, "__KEY__": key, "__BATCH__": batch,
    }.items():
        script = script.replace(token, "None" if value is None else json.dumps(value))
    return script


def build_metadata(username: str, slug: str, code_file: str = "kernel.py", accelerator: str = ACCELERATOR) -> dict:
    if not USER_RE.match(username):
        raise AutomationError("invalid Kaggle username")
    if accelerator not in ACCELERATORS:
        raise AutomationError(f"accelerator must be one of {ACCELERATORS}")
    meta = {
        "id": f"{username}/{slug}",
        "title": slug,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    if accelerator != "default":
        meta["machine_shape"] = accelerator
    return meta


def prepare(key: str, sha: str, username: str, run_id: str, out: Path, accelerator: str = ACCELERATOR,
            config_path: str | None = None, batch: dict | None = None, job_file: Path | None = None) -> str:
    """Write the kernel folder. Optionally records what was requested in ``job_file`` (kept OUT of the pushed folder)."""
    if not RUN_RE.match(run_id):
        raise AutomationError("run id must be numeric")
    if batch is not None and config_path:
        raise AutomationError("choose either a batch or a config path, not both")
    config = None
    if config_path:
        config = resolve_config_path(config_path)
        key = "custom"
    elif batch is None:
        resolve_config(key)
    slug = kernel_slug("batch" if batch is not None else key, sha, run_id)
    out.mkdir(parents=True, exist_ok=True)
    (out / "kernel.py").write_text(build_kernel_script(key, sha, config, batch))
    (out / "kernel-metadata.json").write_text(json.dumps(build_metadata(username, slug, accelerator=accelerator), indent=2))
    if job_file is not None:
        job = {"mode": "batch" if batch is not None else "single", "key": key,
               "output_name": "batch" if batch is not None else (config or resolve_config(key))[1], "batch": batch}
        Path(job_file).write_text(json.dumps(job))
    return f"{username}/{slug}"


# ---------------------------------------------------------------- status / verify

def parse_status(text: str) -> str:
    """Extract e.g. COMPLETE from 'owner/slug has status "KernelWorkerStatus.COMPLETE"'."""
    m = re.search(r'status\s+"?([A-Za-z_.]+)"?', text)
    if not m:
        return "UNKNOWN"
    return m.group(1).split(".")[-1].upper()


def wait(kernel: str, timeout_s: int, interval_s: int, max_queue_s: int = 0) -> str:
    start = time.time()
    deadline = start + timeout_s
    last = ""
    while time.time() < deadline:
        r = subprocess.run(["kaggle", "kernels", "status", kernel], capture_output=True, text=True)
        status = parse_status(r.stdout + r.stderr) if r.returncode == 0 else "UNKNOWN"
        if status != last:
            print(f"[{time.strftime('%H:%M:%S')}] kernel status: {status}", flush=True)
            last = status
        if status in TERMINAL_OK:
            return status
        if max_queue_s and status in ("QUEUED", "UNKNOWN") and time.time() - start > max_queue_s:
            raise AutomationError(
                f"kernel still {status} after {max_queue_s // 60} min (Kaggle has no free GPU for it). "
                f"Stop the kernel on kaggle.com ({kernel}) and retry later or with another accelerator.")
        if status in TERMINAL_BAD:
            raise AutomationError(f"Kaggle kernel ended with status {status}")
        time.sleep(interval_s)
    raise AutomationError(f"timed out after {timeout_s}s waiting for the kernel (last status: {last})")


def expected_result_files(key: str, name: str | None = None) -> set[str]:
    """The only files a single-video kernel run should leave in its result folder."""
    out = name or resolve_config(key)[1]
    return {f"{out}.mp4", "benchmark.json", "run_info.json", "render.log", "metadata.json", "qc_report.json",
            "audio_timeline.json"}


def unexpected_files(out: Path, key: str, name: str | None = None, batch: bool = False) -> list[str]:
    """Names in the result folder that are not part of the expected set (reported as a warning)."""
    if batch:
        manifest = _read(out / "manifest.json") or {}
        ok = {"manifest.json", "run_info.json", "render.log", "library.json"} | {i["name"] for i in manifest.get("items", [])}
        return sorted(p.name for p in out.iterdir() if p.name not in ok)
    return sorted(p.name for p in out.iterdir() if p.name not in expected_result_files(key, name))


def _read(path: Path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def verify_output(out: Path, key: str, name: str | None = None, batch: bool = False) -> None:
    problems = []
    info_p = out / "run_info.json"
    if not info_p.is_file():
        problems.append("run_info.json missing")
    else:
        info = json.loads(info_p.read_text())
        if info.get("status") != "ok":
            problems.append(f"kernel reported status={info.get('status')!r}: {info.get('error', '')[:300]}")
    if batch:
        manifest = _read(out / "manifest.json")
        if not manifest or not manifest.get("items"):
            problems.append("manifest.json missing or empty")
        for item in (manifest or {}).get("items", []):
            d = out / item["name"]
            mp4 = d / f"{item['name']}.mp4"
            if not mp4.is_file() or mp4.stat().st_size == 0:
                problems.append(f"{item['name']}: video missing or empty")
            for f in ("benchmark.json", "metadata.json", "qc_report.json"):
                if not (d / f).is_file():
                    problems.append(f"{item['name']}: {f} missing")
            qc = _read(d / "qc_report.json")
            if qc is not None and not qc.get("passed"):
                problems.append(f"{item['name']}: QC failed")
            if item.get("status") not in ("ok", "skipped_existing"):
                problems.append(f"{item['name']}: status {item.get('status')}")
    else:
        _, name = (None, name) if name else resolve_config(key)
        mp4 = out / f"{name}.mp4"
        if not mp4.is_file() or mp4.stat().st_size == 0:
            problems.append(f"{mp4.name} missing or empty")
        bench = out / "benchmark.json"
        if not bench.is_file():
            problems.append("benchmark.json missing")
        else:
            try:
                if "summary" not in json.loads(bench.read_text()):
                    problems.append("benchmark.json has no 'summary'")
            except json.JSONDecodeError as e:
                problems.append(f"benchmark.json invalid: {e}")
        qc = _read(out / "qc_report.json")
        if qc is not None and not qc.get("passed"):
            problems.append("QC failed: " + ", ".join(c["name"] for c in qc.get("checks", []) if not c.get("ok")))
    if problems:
        raise AutomationError("; ".join(problems))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--test-config", required=True, choices=sorted(ALL_CONFIGS))
    a.add_argument("--config-path", default="", help="repo-relative configs/**.json instead of the key's config")
    a.add_argument("--batch-experiment", default="", help="render a batch of this experiment (or 'auto') instead")
    a.add_argument("--batch-variations", default="0")
    a.add_argument("--batch-seed", default="0")
    a.add_argument("--preset", default="720p", choices=PRESETS)
    a.add_argument("--job-file", type=Path, default=Path("job.json"))
    a.add_argument("--sha", required=True)
    a.add_argument("--username", required=True)
    a.add_argument("--run-id", required=True)
    a.add_argument("--accelerator", default=ACCELERATOR, choices=ACCELERATORS)
    a.add_argument("--out", required=True, type=Path)
    w = sub.add_parser("wait")
    w.add_argument("--kernel", required=True)
    w.add_argument("--timeout", type=int, default=3 * 3600)
    w.add_argument("--interval", type=int, default=60)
    w.add_argument("--max-queue", type=int, default=1500, help="fail if still queued after this many seconds (0=off)")
    v = sub.add_parser("verify")
    v.add_argument("--test-config", choices=sorted(ALL_CONFIGS))
    v.add_argument("--job-file", type=Path, help="job.json written by prepare (overrides --test-config)")
    v.add_argument("--dir", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.cmd == "prepare":
            batch = None
            if args.batch_experiment:
                batch = validate_batch(args.batch_experiment, args.batch_variations, args.batch_seed, args.preset)
            print(prepare(args.test_config, args.sha, args.username, args.run_id, args.out, args.accelerator,
                          args.config_path or None, batch, args.job_file))
        elif args.cmd == "wait":
            wait(args.kernel, args.timeout, args.interval, args.max_queue)
        else:
            if args.job_file:
                job = json.loads(args.job_file.read_text())
                key, name, batch = job["key"], job["output_name"], job["mode"] == "batch"
            elif args.test_config:
                key, name, batch = args.test_config, None, False
            else:
                raise AutomationError("verify needs --job-file or --test-config")
            verify_output(args.dir, key, name, batch)
            extras = unexpected_files(args.dir, key, name, batch)
            if extras:
                print(f"WARNING: unexpected files in the result folder: {extras}")
            print("output verified")
    except AutomationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
