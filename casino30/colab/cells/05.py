# CHECKPOINT 3 (part B) - GPU / EEVEE smoke test via Blender itself
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *

banner(3, "GPU / EEVEE smoke test (64x64, scene casino30.blend)")
require_file(BLEND)
if "gpu" not in load_state():
    save_state(gpu=nvidia_query()[0])
write_script(GL_PROBE, BPY_COMMON + r'''
a = script_args()
blend, out_png, report = a[0], a[1], a[2]
def main():
    engines = available_engines()
    print("AVAILABLE_ENGINES", engines)
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    s = bpy.context.scene
    eng = pick_eevee(engines)
    print("SELECTED_EEVEE_ENGINE", eng)
    s.render.engine = eng
    s.render.resolution_x = 64
    s.render.resolution_y = 64
    s.render.resolution_percentage = 100
    if hasattr(s.eevee, "taa_render_samples"):
        s.eevee.taa_render_samples = 4
    s.render.image_settings.file_format = "PNG"
    s.render.use_file_extension = False
    s.render.filepath = out_png
    s.frame_set(s.frame_start)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t
    info = gl_info()
    verdict = classify_gl(info)
    rep = {"blender": bpy.app.version_string, "available_engines": engines, "selected_eevee_engine": eng,
           "gl": info, "gl_verdict": verdict, "render_s": round(dt, 3), "output_ok": file_ok(out_png), "output": out_png}
    with open(report, "w") as f:
        json.dump(rep, f, indent=2, default=str)
    print("GL_INFO", json.dumps(info))
    print("GL_VERDICT", verdict)
    if verdict != "NVIDIA_GPU":
        print("NOT AN NVIDIA GPU RENDERER:", verdict)
        sys.exit(2)
    if not rep["output_ok"]:
        print("probe render produced no output file")
        sys.exit(3)
try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
''')

chosen, attempts = None, []
for backend in ("opengl", "vulkan"):
    rep_path = PROBE_DIR / ("gl_probe_%s.json" % backend)
    png_path = PROBE_DIR / ("probe_%s.png" % backend)
    for p in (rep_path, png_path):
        if p.exists():
            p.unlink()
    print("\n--- trying GPU backend: %s ---" % backend)
    res = run_blender(GL_PROBE, [BLEND, png_path, rep_path], log_path=LOGS / ("gl_probe_%s.log" % backend),
                      timeout=300, backend=backend,
                      show=r"AVAILABLE_ENGINES|SELECTED_EEVEE_ENGINE|GL_INFO|GL_VERDICT|Traceback|Error|NOT AN NVIDIA")
    rep = json.loads(rep_path.read_text()) if rep_path.is_file() else None
    ok = bool(res["rc"] == 0 and rep and rep["gl_verdict"] == "NVIDIA_GPU" and rep["output_ok"] and png_path.is_file())
    attempts.append({"backend": backend, "rc": res["rc"], "verdict": rep["gl_verdict"] if rep else None,
                     "log": res["log"], "egl_noise_lines": res["hidden_noise"]})
    print("backend %s -> rc=%s verdict=%s EGL-noise-lines=%s" % (backend, res["rc"], rep["gl_verdict"] if rep else "no report", res["hidden_noise"]))
    if ok:
        chosen = (backend, rep)
        break

if not chosen:
    print("\nAttempts:", json.dumps(attempts, indent=2))
    for a in attempts:
        print("\n--- last 25 lines of %s ---" % a["log"])
        print("\n".join(Path(a["log"]).read_text(errors="replace").splitlines()[-25:]))
    reason = "Blender could not render EEVEE on the NVIDIA T4 with the OpenGL or Vulkan backend."
    if any(a["verdict"] == "SOFTWARE" for a in attempts):
        reason = "Blender fell back to SOFTWARE rendering (llvmpipe/Mesa) - this is not a GPU result."
    fail(3, reason + " See logs above. Benchmark stopped on purpose.")

backend, rep = chosen
st = load_state()
print("\n================ GPU / EEVEE SUMMARY ================")
print("Blender version : ", rep["blender"])
print("GPU (nvidia-smi): ", st["gpu"]["name"], "|", st["gpu"]["memory_mib"], "MiB | driver", st["gpu"]["driver"])
print("GL vendor       : ", rep["gl"]["vendor"])
print("GL renderer     : ", rep["gl"]["renderer"])
print("GL version      : ", rep["gl"]["version"])
print("GPU backend     : ", backend, "(Blender reports %s)" % rep["gl"].get("backend"))
print("AVAILABLE_ENGINES", rep["available_engines"])
print("EEVEE engine    : ", rep["selected_eevee_engine"])
print("Rendering on    : ", "NVIDIA GPU (hardware)" if rep["gl_verdict"] == "NVIDIA_GPU" else "NOT NVIDIA")
print("GL libs source  : ", st.get("gl_source"))
save_state(gl_backend=backend, gl_probe=rep)
passed(3)
