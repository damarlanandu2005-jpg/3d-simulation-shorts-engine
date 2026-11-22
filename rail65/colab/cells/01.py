# STEP 0 - BOOTSTRAP: writes ONE shared helper module (all paths, script paths and helpers live there), then imports it.
# Every later cell imports the same constants, so a script is always executed from the exact path it was written to.
from pathlib import Path
import sys

Path("/content/eevee_test/lib").mkdir(parents=True, exist_ok=True)
Path("/content/eevee_test/lib/ee_common.py").write_text(r'''
import os, sys, re, json, time, shutil, hashlib, platform, subprocess, threading, ast
from pathlib import Path

# ---------------- single source of truth for every path ----------------
DATASET = Path("/content/hopeall")
KIT = DATASET / "kaggle_kit"
BLEND = KIT / "rail65.blend"
RENDER_PY = KIT / "render_30s.py"
WORK = Path("/content/eevee_test")
LIB = WORK / "lib"
SCRIPTS = WORK / "scripts"
LOGS = WORK / "logs"
RESULTS = WORK / "results"
PROBE_DIR = WORK / "probe"
BENCH_DIR = WORK / "benchmark"
REPORTS = BENCH_DIR / "reports"
FRAMES_DIR = BENCH_DIR / "frames"
NVGL = WORK / "nvidia_gl"
STATE_FILE = WORK / "state.json"
OUT_FRAMES = WORK / "frames30"
OUT_VIDEO = WORK / "video"
_cp = Path("/content/rail65_cfg.json")
CFG = json.loads(_cp.read_text()) if _cp.is_file() else {}   # written by the GitHub runner; empty when run by hand

BLENDER_VERSION = "5.2.4"
BLENDER_DIST = WORK / "blender_dist"
BLENDER_BIN = BLENDER_DIST / ("blender-" + BLENDER_VERSION + "-linux-x64") / "blender"

# generated Blender scripts: each is written with write_script(X, ...) and executed with run_blender(X, ...)
BLENDER_INFO = SCRIPTS / "blender_info.py"
SCENE_INFO = SCRIPTS / "scene_info.py"
GL_PROBE = SCRIPTS / "gl_probe.py"
BENCH = SCRIPTS / "eevee_bench.py"

ALLOW_NON_T4 = False        # set True to allow a different NVIDIA GPU
MAX_BENCH_FRAMES = 60       # hard guard: this notebook never renders a production-length sequence


class CheckpointFailed(RuntimeError):
    pass


def banner(n, title):
    print("=" * 72)
    print("CHECKPOINT %s - %s" % (n, title))
    print("=" * 72)


def passed(n):
    print("\nCHECKPOINT %s PASSED" % n)


def fail(n, msg):
    print("\nCHECKPOINT %s FAILED: %s" % (n, msg))
    raise CheckpointFailed("CHECKPOINT %s: %s" % (n, msg))


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(**kw):
    s = load_state()
    s.update(kw)
    WORK.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2, default=str))
    return s


def sh(cmd, timeout=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nvidia_query():
    r = sh("nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits")
    if r.returncode != 0:
        return []
    out = []
    for line in r.stdout.strip().splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 4:
            out.append({"index": p[0], "name": p[1], "memory_mib": int(float(p[2])), "driver": p[3]})
    return out


def require_file(path):
    ok = subprocess.run(["test", "-f", str(path)]).returncode == 0
    print("[test -f] %s -> %s" % (path, "OK" if ok else "MISSING"))
    if not ok:
        raise FileNotFoundError(str(path))
    return str(path)


def write_script(path, text):
    path = Path(path)
    if path.parent != SCRIPTS:
        raise ValueError("scripts must live directly in %s, got %s" % (SCRIPTS, path))
    if ("eevee_test" + "/eevee_test") in str(path):
        raise ValueError("nested path: %s" % path)
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    ast.parse(text)  # syntax check before it ever reaches Blender
    path.write_text(text)
    require_file(path)
    print("[script written] %s (%d bytes, syntax OK)" % (path, len(text)))
    return path


def gl_env(backend=None):
    env = os.environ.copy()
    st = load_state()
    if st.get("gl_lib_dir"):
        old = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = st["gl_lib_dir"] + (":" + old if old else "")
    if st.get("egl_vendor_json"):
        env["__EGL_VENDOR_LIBRARY_FILENAMES"] = st["egl_vendor_json"]
    if backend == "vulkan" and st.get("vk_icd_json"):
        env["VK_ICD_FILENAMES"] = st["vk_icd_json"]
    env.pop("LIBGL_ALWAYS_SOFTWARE", None)
    return env


def run_blender(script, script_args=(), log_path=None, timeout=1800, backend=None, show=None, hide=r"EGL Error"):
    """Run Blender headless on `script`. Verifies binary and script with `test -f` first. Full log is saved;
    lines matching `hide` (EGL probe noise) are counted, not printed, never discarded."""
    require_file(BLENDER_BIN)
    if not os.access(BLENDER_BIN, os.X_OK):
        raise PermissionError("not executable: %s" % BLENDER_BIN)
    script = Path(script)
    require_file(script)
    log_path = Path(log_path) if log_path else LOGS / (script.stem + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(BLENDER_BIN), "-b", "--factory-startup", "--python-exit-code", "1"]
    if backend:
        cmd += ["--gpu-backend", backend]
    cmd += ["-P", str(script), "--"] + [str(x) for x in script_args]
    print("[run]", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            errors="replace", bufsize=1, env=gl_env(backend))
    flag = {"timeout": False}

    def _kill():
        flag["timeout"] = True
        proc.kill()

    timer = threading.Timer(timeout, _kill)
    timer.start()
    lines, hidden = [], 0
    with open(log_path, "w") as lf:
        for line in proc.stdout:
            lf.write(line)
            lines.append(line.rstrip("\n"))
            if hide and re.search(hide, line):
                hidden += 1
                continue
            if show and re.search(show, line):
                print(line.rstrip())
    rc = proc.wait()
    timer.cancel()
    return {"rc": rc, "lines": lines, "hidden_noise": hidden, "timed_out": flag["timeout"],
            "log": str(log_path), "cmd": cmd}


def parse_tagged(lines, tag):
    out = None
    for l in lines:
        if l.startswith(tag + " "):
            try:
                out = json.loads(l[len(tag) + 1:])
            except Exception:
                pass
    return out


ERR_RE = re.compile(r"Traceback \(most recent|^Error:|Segmentation fault|Fatal|CUDA error|shader compilation failed|"
                    r"Failed to compile|out of memory|Unable to open a display", re.I)


def scan_errors(lines):
    errs = [l for l in lines if ERR_RE.search(l) and "EGL Error" not in l]
    egl = [l for l in lines if "EGL Error" in l]
    return errs, egl


def start_smi(csv_path):
    f = open(csv_path, "w")
    p = subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,index,utilization.gpu,memory.used",
                          "--format=csv,noheader,nounits", "-lms", "500"], stdout=f, stderr=subprocess.DEVNULL)
    return p, f


def stop_smi(p, f):
    p.terminate()
    try:
        p.wait(5)
    except Exception:
        p.kill()
    f.close()


def smi_peaks(csv_path):
    peak = {"util_pct": 0.0, "mem_mib": 0.0, "samples": 0}
    try:
        for l in open(csv_path):
            x = [t.strip() for t in l.split(",")]
            if len(x) < 4:
                continue
            try:
                peak["util_pct"] = max(peak["util_pct"], float(x[2]))
                peak["mem_mib"] = max(peak["mem_mib"], float(x[3]))
                peak["samples"] += 1
            except ValueError:
                pass
    except FileNotFoundError:
        pass
    return peak


# ---------------- code prepended to every generated Blender script ----------------
BPY_COMMON = r"""
import bpy, sys, os, json, time, traceback

def script_args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

def available_engines():
    return [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]

def pick_eevee(engines):
    cands = [e for e in engines if "EEVEE" in e.upper()]
    if not cands:
        raise RuntimeError("No EEVEE engine in this Blender build. Available: %s" % engines)
    nxt = [e for e in cands if "NEXT" in e.upper()]
    return (nxt or sorted(cands))[0]

def gl_info():
    import gpu
    p = gpu.platform
    d = {"vendor": p.vendor_get(), "renderer": p.renderer_get(), "version": p.version_get()}
    for key, fn in (("backend", "backend_type_get"), ("device_type", "device_type_get")):
        try:
            d[key] = getattr(p, fn)()
        except Exception as e:
            d[key] = "unavailable: %r" % (e,)
    return d

def classify_gl(d):
    text = (str(d.get("vendor")) + " " + str(d.get("renderer"))).lower()
    soft = any(k in text for k in ("llvmpipe", "softpipe", "swrast", "lavapipe", "software", "mesa"))
    if soft or str(d.get("device_type")).upper() == "SOFTWARE":
        return "SOFTWARE"
    if "nvidia" in text:
        return "NVIDIA_GPU"
    return "OTHER_GPU"

def file_ok(p):
    return os.path.isfile(p) and os.path.getsize(p) > 0
"""
''')

sys.path.insert(0, "/content/eevee_test/lib")
import importlib, ee_common
importlib.reload(ee_common)
from ee_common import *

print("helper module:", ee_common.__file__)
print("WORK    :", WORK)
print("KIT     :", KIT)
print("BLEND   :", BLEND)
print("BLENDER :", BLENDER_BIN)
print("SCRIPTS :", [str(p) for p in (BLENDER_INFO, SCENE_INFO, GL_PROBE, BENCH)])
