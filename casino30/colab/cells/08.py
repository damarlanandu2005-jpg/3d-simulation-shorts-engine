# CELL 8 - FULL RENDER 900 frames, resumable (re-run this cell after any interruption)
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *
SAMPLES = CFG.get("samples", 0)            # 0 = file default (64); must match what you benchmarked
FS_OFF = CFG.get("fs_off", "346-421,541-781")   # see benchmark cell
F0, F1 = CFG.get("frame_start", 1), CFG.get("frame_end", 900)
CHUNK = 100            # frames per Blender session (a crash loses at most one chunk)
banner(6, "full render")
OUT_FRAMES.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
state = load_state(); backend = state.get("gl_backend")
smi_csv = LOGS / "smi_full.csv"; p, f = start_smi(smi_csv)
t0 = time.perf_counter(); per_frame = {}
def done_ok(n):
    q = OUT_FRAMES / ("f_%04d.png" % n); return q.is_file() and q.stat().st_size > 2000
for lo in range(F0, F1 + 1, CHUNK):
    hi = min(lo + CHUNK - 1, F1)
    todo = [n for n in range(lo, hi + 1) if not done_ok(n)]
    if not todo: print("chunk %d-%d already complete" % (lo, hi)); continue
    tc = time.perf_counter()
    res = run_blender(RENDER_PY, ["--blend", BLEND, "--out", OUT_FRAMES, "--frames", "%d-%d" % (lo, hi), "--pct", 100, "--samples", SAMPLES, "--no-freestyle-frames", FS_OFF,
                                  "--skip-existing", "--report", REPORTS / ("chunk_%03d.json" % lo)], log_path=LOGS / ("chunk_%03d.log" % lo),
                      timeout=2400, backend=backend, show=r"RUN_DONE|Traceback|Error:|ABORT")
    for l in res["lines"]:
        m = re.match(r"FRAME (\d+) ([\d.]+) ok", l)
        if m: per_frame[int(m.group(1))] = float(m.group(2))
    ok = sum(done_ok(n) for n in range(lo, hi + 1))
    print("chunk %d-%d: rc=%s frames present %d/%d | %.1f s | total elapsed %.1f min" % (lo, hi, res["rc"], ok, hi - lo + 1, time.perf_counter() - tc, (time.perf_counter() - t0) / 60))
    if res["rc"] == 2: stop_smi(p, f); fail(6, "software GL detected - aborted (not a GPU result)")
stop_smi(p, f)
wall = time.perf_counter() - t0
missing = [n for n in range(F0, F1 + 1) if not done_ok(n)]
save_state(render={"wall_s": wall, "per_frame": per_frame, "missing": missing, "samples": SAMPLES, "gpu_peaks": smi_peaks(smi_csv)})
if missing:
    print("MISSING frames:", missing[:40], "..." if len(missing) > 40 else "")
    fail(6, "%d frames missing - re-run this cell to resume" % len(missing))
print("all %d frames present. wall time this session: %.1f min" % (F1 - F0 + 1, wall / 60))
passed(6)
