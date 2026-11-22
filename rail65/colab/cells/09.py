# CELL 9 - encode MP4 (30 fps), contact sheet, results ZIP, MEASURED timing summary
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *
banner(7, "encode + summary")
OUT_VIDEO.mkdir(parents=True, exist_ok=True)
mp4 = OUT_VIDEO / "rail65_eevee.mp4"
r = sh("ffmpeg -y -loglevel error -framerate 30 -start_number %d -i '%s/f_%%04d.png' -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p '%s'" % (CFG.get("frame_start", 1), OUT_FRAMES, mp4), timeout=900)
if r.returncode != 0 or not mp4.is_file(): fail(7, "ffmpeg failed: " + r.stderr[-400:])
pr = sh("ffprobe -v error -show_entries stream=width,height,nb_frames,r_frame_rate,duration -of default=nw=1 '%s'" % mp4).stdout
print(pr)
from PIL import Image
_f0, _f1 = CFG.get("frame_start", 1), CFG.get("frame_end", 1956); sel = list(range(_f0, _f1 + 1, max(1, (_f1 - _f0 + 1) // 20))); th = [Image.open(OUT_FRAMES / ("f_%04d.png" % n)).convert("RGB").resize((180, 320)) for n in sel]
cols = 10; rows = (len(th) + cols - 1) // cols; sheet = Image.new("RGB", (180 * cols, 320 * rows))
for i, im in enumerate(th): sheet.paste(im, ((i % cols) * 180, (i // cols) * 320))
sheet.save(OUT_VIDEO / "contact_sheet.jpg", quality=85)
st = load_state(); rd = st.get("render", {}); pf = list(rd.get("per_frame", {}).values())
import statistics
summary = {"blender": st["blender"]["version_string"], "gpu": st["gpu"], "gl": st["gl_probe"]["gl"], "samples": rd.get("samples"),
           "frames_timed_this_session": len(pf), "mean_s_per_frame": statistics.mean(pf) if pf else None,
           "render_wall_min_this_session": rd.get("wall_s", 0) / 60, "gpu_peaks": rd.get("gpu_peaks"), "bench": st.get("bench")}
(OUT_VIDEO / "timing_summary.json").write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps(summary, indent=2, default=str))
print("\nNOTE: if the render was resumed, wall time covers only the last session; sum the chunk logs for a full total.")
zp = shutil.make_archive("/content/rail65_results", "zip", OUT_VIDEO)
print("results ZIP:", zp)
passed(7)
try:
    from google.colab import files; files.download(str(mp4))
except Exception as e: print("download manually from", mp4)
