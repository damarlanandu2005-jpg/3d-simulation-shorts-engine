# CELL 6 - scene check: frame range, resolution, engine, objects (no render)
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *
banner(4, "casino30.blend scene check")
write_script(SCENE_INFO, BPY_COMMON + r'''
a = script_args()
bpy.ops.wm.open_mainfile(filepath=a[0], load_ui=False)
s = bpy.context.scene
d = {"frame_start": s.frame_start, "frame_end": s.frame_end, "fps": s.render.fps, "res": [s.render.resolution_x, s.render.resolution_y],
     "pct": s.render.resolution_percentage, "engine": s.render.engine, "samples": getattr(s.eevee, "taa_render_samples", None),
     "objects": len(bpy.data.objects), "cams": len(bpy.data.cameras), "markers": len(s.timeline_markers),
     "packed_images": sum(1 for i in bpy.data.images if i.packed_file), "missing_images": [i.name for i in bpy.data.images if not i.packed_file and i.source == "FILE"]}
print("SCENE_JSON", json.dumps(d))
''')
res = run_blender(SCENE_INFO, [BLEND], log_path=LOGS / "scene_info.log", timeout=300, show=r"SCENE_JSON|Traceback|Error")
d = parse_tagged(res["lines"], "SCENE_JSON")
if res["rc"] != 0 or not d: fail(4, "scene_info failed, see %s" % res["log"])
print(json.dumps(d, indent=1))
if (d["frame_start"], d["frame_end"]) != (1, 900) or d["fps"] != 30 or d["res"] != [720, 1280] or d["pct"] != 100:
    fail(4, "unexpected scene settings: %s" % d)
if d["missing_images"]: fail(4, "unpacked external images: %s" % d["missing_images"])
save_state(scene=d)
passed(4)
