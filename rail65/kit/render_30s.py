"""render_30s.py - renders frames of casino30.blend with Eevee (Blender 5.x: BLENDER_EEVEE, 4.x: BLENDER_EEVEE_NEXT).
Run inside Blender:  blender -b --factory-startup -P render_30s.py -- --blend F --out DIR --frames 1-900 [--step N] [--pct 100]
                     [--samples N] [--skip-existing] [--report JSON] [--allow-software]
* GPU check: after the FIRST render, Blender's own GL vendor/renderer is read; software GL (llvmpipe...) aborts with exit 2
  unless --allow-software (local debugging only; such timings are NOT GPU results).
* Never saves the .blend. Prints one 'FRAME n seconds ok|MISSING' line per frame, then a RUN_DONE line."""
import bpy, gpu, sys, os, re, json, time, hashlib, statistics, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--blend", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--frames", default="1-900", help="e.g. 1-900 or 1-900:5 (step) or 1,50,100")
ap.add_argument("--pct", type=int, default=100); ap.add_argument("--samples", type=int, default=0)
ap.add_argument("--skip-existing", action="store_true"); ap.add_argument("--report", default="")
ap.add_argument("--allow-software", action="store_true")
ap.add_argument("--no-freestyle-frames", default="", help="frames where outlines are skipped (same syntax as --frames); only use where the character is off-screen")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
a.blend, a.out = os.path.abspath(a.blend), os.path.abspath(a.out)
SOFT = re.compile(r"llvmpipe|softpipe|swrast|software|lavapipe|swiftshader", re.I)


def parse_frames(s):
    out = []
    for part in s.split(","):
        if "-" in part:
            rng, _, step = part.partition(":")
            lo, hi = rng.split("-")
            out += list(range(int(lo), int(hi) + 1, int(step or 1)))
        else:
            out.append(int(part))
    return sorted(set(out))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    h0 = sha(a.blend)
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=a.blend, load_ui=False)
    s = bpy.context.scene
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    s.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in ids else "BLENDER_EEVEE_NEXT"
    s.render.resolution_percentage = a.pct
    s.render.use_file_extension = True
    if a.samples:
        s.eevee.taa_render_samples = a.samples
    frames = parse_frames(a.frames)
    nofs = set(parse_frames(a.no_freestyle_frames)) if a.no_freestyle_frames else set()
    fs_default = s.render.use_freestyle
    print("ENGINE", s.render.engine, "| samples", s.eevee.taa_render_samples, "| res", s.render.resolution_x, s.render.resolution_y, f"{a.pct}%", "| frames", len(frames), flush=True)
    rows, gl, t_all = [], None, time.perf_counter()
    for f in frames:
        p = os.path.join(a.out, "f_%04d.png" % f)
        if a.skip_existing and os.path.isfile(p) and os.path.getsize(p) > 0:
            rows.append({"frame": f, "seconds": None, "output_ok": True, "skipped": True})
            continue
        s.frame_set(f)
        s.render.use_freestyle = fs_default and (f not in nofs)
        s.render.filepath = p
        t = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        dt = time.perf_counter() - t
        if gl is None:
            gl = {"vendor": gpu.platform.vendor_get(), "renderer": gpu.platform.renderer_get(), "version": gpu.platform.version_get(),
                  "backend": gpu.platform.backend_type_get(), "device_type": gpu.platform.device_type_get()}
            print("GL_INFO", json.dumps(gl), flush=True)
            txt = f'{gl["vendor"]} {gl["renderer"]}'
            if (SOFT.search(txt) or "nvidia" not in txt.lower()) and not a.allow_software:
                print("FATAL: GL renderer is '%s' - not NVIDIA hardware. NOT a GPU result." % txt, flush=True)
                if a.report:
                    json.dump({"status": "software_gl", "gl": gl}, open(a.report, "w"), indent=2)
                sys.exit(2)
        ok = os.path.isfile(p) and os.path.getsize(p) > 0
        rows.append({"frame": f, "seconds": round(dt, 3), "output_ok": ok, "skipped": False})
        print("FRAME", f, round(dt, 2), "ok" if ok else "MISSING", flush=True)
    ts = [r["seconds"] for r in rows if r["seconds"] is not None]
    rep = {"status": "ok", "blender": bpy.app.version_string, "engine": s.render.engine, "samples": s.eevee.taa_render_samples, "pct": a.pct, "gl": gl,
           "frames_requested": len(frames), "frames_rendered": len(ts), "frames_skipped": len(rows) - len(ts),
           "missing": [r["frame"] for r in rows if not r["output_ok"]], "total_render_s": round(sum(ts), 2),
           "wall_s": round(time.perf_counter() - t_all, 2), "rows": rows,
           "blend_unchanged": sha(a.blend) == h0}
    if ts:
        rep.update({"avg_s": round(statistics.mean(ts), 4), "median_s": round(statistics.median(ts), 4), "min_s": min(ts), "max_s": max(ts)})
    if a.report:
        json.dump(rep, open(a.report, "w"), indent=2)
    print("RUN_DONE rendered", len(ts), "skipped", rep["frames_skipped"], "missing", len(rep["missing"]), "avg_s", rep.get("avg_s"), "blend_unchanged", rep["blend_unchanged"], flush=True)


try:
    main()
except SystemExit:
    raise
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
