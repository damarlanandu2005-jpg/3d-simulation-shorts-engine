# CELL 7 - BENCHMARK: 14 frames spread over all shots, full 720x1280 -> projects the 900-frame time (ESTIMATE, from this sample)
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *
SAMPLES = CFG.get("samples", 0)          # 0 = use the .blend's own setting (64). Lower (e.g. 32) if the projection exceeds your time budget.
FS_OFF = CFG.get("fs_off", "")   # frames where the character is off-screen: outlines (Freestyle) skipped; verified pixel-identical locally
BENCH_FRAMES = "32,91,177,248,290,336,382,437"
banner(5, "benchmark")
REPORTS.mkdir(parents=True, exist_ok=True); bdir = BENCH_DIR / "frames"; shutil.rmtree(bdir, ignore_errors=True); bdir.mkdir(parents=True)
smi_csv = LOGS / "smi_bench.csv"; p, f = start_smi(smi_csv)
res = run_blender(RENDER_PY, ["--blend", BLEND, "--out", bdir, "--frames", BENCH_FRAMES, "--pct", 100, "--samples", SAMPLES, "--no-freestyle-frames", FS_OFF,
                              "--report", REPORTS / "bench.json"], log_path=LOGS / "bench.log", timeout=1500,
                  backend=load_state().get("gl_backend"), show=r"GL_|Traceback|Error:|ABORT")
stop_smi(p, f)
secs = [float(m.group(2)) for m in (re.match(r"FRAME (\d+) ([\d.]+) ok", l) for l in res["lines"]) if m]
if res["rc"] != 0 or len(secs) < 10:
    fail(5, "benchmark failed rc=%s frames_ok=%d, see %s" % (res["rc"], len(secs), res["log"]))
import statistics
mean = statistics.mean(secs); s2 = sorted(secs); p90 = s2[int(0.9 * (len(s2) - 1))]
peaks = smi_peaks(smi_csv)
print("measured on %d sampled frames: mean %.2f s | median %.2f | p90 %.2f | max %.2f" % (len(secs), mean, statistics.median(secs), p90, max(secs)))
print("GPU peak: util %.0f%% | mem %.0f MiB" % (peaks["util_pct"], peaks["mem_mib"]))
print("PROJECTION (estimate) for 1956 frames: %.1f min mean | %.1f min at p90" % (1956 * mean / 60, 1956 * p90 / 60))
save_state(bench={"mean": mean, "p90": p90, "n": len(secs)})
passed(5)
