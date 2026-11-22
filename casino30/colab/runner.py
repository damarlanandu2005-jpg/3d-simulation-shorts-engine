"""Runs the whole casino30 test on a Colab T4 from the checked-out repo, then pushes a small results bundle to GitHub.
Started by the launcher cell:  exec(open('/content/repo/casino30/colab/runner.py').read())
Config comes from casino30/run_config.json (mode: benchmark | full)."""
import json, os, sys, time, shutil, subprocess, traceback, base64, datetime, gzip
from pathlib import Path

REPO_DIR = Path("/content/repo")
ROOT = REPO_DIR / "casino30"
CELLS = ROOT / "colab" / "cells"
REPO_SLUG = os.environ.get("CASINO_REPO", "damarlanandu2005-jpg/3d-simulation-shorts-engine")
RESULTS_BRANCH = "casino30-results"

cfg = json.loads((ROOT / "run_config.json").read_text())
Path("/content/casino30_cfg.json").write_text(json.dumps(cfg))
print("run_config:", json.dumps(cfg))
commit = subprocess.run(["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
print("kit commit:", commit)

G = {"__name__": "__main__"}
status = {"commit": commit, "config": cfg, "started": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z", "steps": [], "status": "running"}

def run_cell(n):
    src = (CELLS / ("%02d.py" % n)).read_text()
    t = time.time()
    exec(compile(src, "cell%02d" % n, "exec"), G)
    status["steps"].append({"cell": n, "seconds": round(time.time() - t, 1)})

def tail(p, n=120):
    try:
        return "\n".join(Path(p).read_text(errors="replace").splitlines()[-n:])
    except Exception:
        return ""

def push_results():
    work = Path("/content/eevee_test")
    bundle = Path("/content/results_bundle"); shutil.rmtree(bundle, ignore_errors=True); bundle.mkdir()
    (bundle / "run_status.json").write_text(json.dumps(status, indent=2, default=str))
    for src, name in ((work / "video" / "timing_summary.json", "timing_summary.json"), (work / "video" / "contact_sheet.jpg", "contact_sheet.jpg"),
                      (work / "state.json", "state.json"), (work / "benchmark" / "reports" / "bench.json", "bench.json")):
        if src.is_file(): shutil.copy2(src, bundle / name)
    logs = work / "logs"
    if logs.is_dir():
        (bundle / "logs").mkdir()
        for lg in sorted(logs.glob("*.log")):
            (bundle / "logs" / (lg.name + ".tail.txt")).write_text(tail(lg, 150))
    try:
        from google.colab import userdata
        token = userdata.get("GITHUB_TOKEN")
    except Exception:
        token = None
    if not token:
        print("No GITHUB_TOKEN in Colab Secrets - results NOT pushed. Local copy:", bundle)
        return
    auth = "AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode()
    url = "https://github.com/%s" % REPO_SLUG
    g = lambda *a, cwd=None: subprocess.run(["git", "-c", "http.extraheader=" + auth, *a], cwd=cwd, capture_output=True, text=True)
    d = Path("/content/results_repo"); shutil.rmtree(d, ignore_errors=True)
    has = g("ls-remote", "--heads", url, RESULTS_BRANCH).stdout.strip()
    if has:
        g("clone", "--depth", "1", "-b", RESULTS_BRANCH, url, str(d))
    else:
        d.mkdir(); g("init", "-q", cwd=d); g("checkout", "-q", "--orphan", RESULTS_BRANCH, cwd=d); g("remote", "add", "origin", url, cwd=d)
    run_id = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y%m%d-%H%M%S") + "-" + commit
    shutil.copytree(bundle, d / "runs" / run_id)
    (d / "LATEST.txt").write_text(run_id + "\n")
    g("-c", "user.name=colab-runner", "-c", "user.email=colab-runner@users.noreply.github.com", "add", "-A", cwd=d)
    g("-c", "user.name=colab-runner", "-c", "user.email=colab-runner@users.noreply.github.com", "commit", "-q", "-m", "casino30 run %s (%s)" % (run_id, status["status"]), cwd=d)
    r = g("push", "origin", "HEAD:" + RESULTS_BRANCH, cwd=d)
    print("results push:", "OK -> branch %s, runs/%s" % (RESULTS_BRANCH, run_id) if r.returncode == 0 else "FAILED " + r.stderr[-300:])

try:
    run_cell(1)                                              # helper module
    kit = Path("/content/hopeall/kaggle_kit"); kit.mkdir(parents=True, exist_ok=True)
    for n in ("casino30.blend", "render_30s.py"):
        shutil.copy2(ROOT / "kit" / n, kit / n)              # the kit always comes from this commit
    print("kit copied from commit", commit)
    for n in (3, 4, 5, 6):                                   # blender, NVIDIA EGL, GPU probe, scene check
        run_cell(n)
    if not cfg.get("skip_benchmark"):
        run_cell(7)
    if cfg.get("mode", "full") == "full":
        run_cell(8); run_cell(9)
    status["status"] = "passed"
except BaseException as e:
    status["status"] = "failed"
    status["error"] = repr(e)
    status["traceback"] = traceback.format_exc()[-3000:]
    print("RUN FAILED:", repr(e))
    print(status["traceback"])
finally:
    status["finished"] = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z"
    push_results()
    if status["status"] != "passed":
        raise SystemExit("casino30 run failed: " + status.get("error", ""))
