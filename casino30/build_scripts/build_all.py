"""build_all.py - builds the complete 5 s casino test scene and saves casino_test.blend.
Usage: python build_all.py [out.blend]"""
import bpy, math, os, sys
from mathutils import Vector
import casino_scene as cs
import casino_char as ch

HERE = cs.HERE
CAM_KEYS = [  # frame, camera location, look-at target
    (1,   (0.22, -0.60, 1.27), (0.24, 0.20, 1.34)),
    (14,  (0.17, -0.66, 1.30), (0.20, 0.20, 1.36)),
    (19,  (0.10, -0.78, 1.32), (0.12, 0.20, 1.38)),
    (27,  (0.00, -1.80, 1.42), (0.02, 0.00, 1.40)),
    (35,  (0.02, -3.05, 1.36), (0.06, 0.00, 1.30)),
    (60,  (-0.02, -2.90, 1.36), (0.00, 0.00, 1.30)),
    (105, (-0.20, -2.50, 1.42), (-0.12, 0.00, 1.40)),
    (150, (-0.30, -2.10, 1.44), (-0.20, 0.00, 1.44)),
]
WORDS = [(0.0, "You"), (0.25, "just"), (0.5, "watched"), (0.75, "two"), (1.25, "jackpot"), (1.75, "symbols"), (2.0, "land."),
         (2.5, "And the"), (2.75, "third"), (3.0, "one"), (3.25, "stopped"), (3.5, "one"), (3.75, "click"), (4.0, "short."), (4.5, "So")]


def build_camera(sc):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 32
    cam = bpy.data.objects.new("Camera", cd)
    cs.link(cam)
    sc.camera = cam
    tgt = bpy.data.objects.new("CamTarget", None)
    cs.link(tgt)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    for f, loc, t in CAM_KEYS:
        cam.location, tgt.location = loc, t
        cam.keyframe_insert("location", frame=f)
        tgt.keyframe_insert("location", frame=f)
    return cam


def build_captions(sc, cam):
    col = cs.coll("Captions")
    font = bpy.data.fonts.load("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
    white = cs.mat("CapWhite", (1, 1, 1), emit=(1, 1, 1), estr=1.4)
    shadow = cs.mat("CapShadow", (0.02, 0.01, 0.01), rough=1.0)
    for i, (t, w) in enumerate(WORDS):
        start = ch.fr(t)
        end = ch.fr(WORDS[i + 1][0]) if i + 1 < len(WORDS) else cs.F_END + 2
        for layer, (m, off) in enumerate([(shadow, (0.0025, -0.0025, -0.001)), (white, (0, 0, 0))]):
            cu = bpy.data.curves.new(f"Cap{i}_{layer}", "FONT")
            cu.body, cu.font, cu.size = w, font, 0.062
            cu.align_x = "CENTER"
            cu.extrude = 0.0
            ob = bpy.data.objects.new(f"Cap{i}_{layer}", cu)
            cs.link(ob, col)
            cu.materials.append(m)
            ob.parent = cam
            ob.location = (off[0], -0.23 + off[1], -1.0 + off[2])
            ob.hide_render = start > 1
            ob.keyframe_insert("hide_render", frame=1)
            if start > 1:
                ob.hide_render = False
                ob.keyframe_insert("hide_render", frame=start)
            ob.hide_render = True
            ob.keyframe_insert("hide_render", frame=end)
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def setup_render(sc, scale=1.0, samples=32):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = 720, 1280
    sc.render.resolution_percentage = int(100 * scale)
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.75
    sc.render.use_freestyle = True
    vl = sc.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(125)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    ls = fs.linesets.new("Ink")
    ls.select_by_visibility = True
    ls.select_by_collection = True
    ls.collection = bpy.data.collections["Character"]
    ls.select_silhouette = True
    ls.select_border = True
    ls.select_crease = True
    ls.select_edge_mark = False
    ls.linestyle.color = (0.07, 0.03, 0.02)
    ls.linestyle.thickness = 5.5 * scale ** 0.5 * (1.0 if scale >= 0.5 else 0.7)


def build(out=None, scale=1.0, samples=32):
    sc = cs.reset()
    hero = cs.build_environment(sc)
    cs.animate_reels(hero)
    cs.build_lights(sc)
    rig, face = ch.build_character()
    ch.animate_character(rig, face)
    cam = build_camera(sc)
    build_captions(sc, cam)
    setup_render(sc, scale, samples)
    sc.frame_set(1)
    bpy.ops.file.pack_all()
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=out)
    return sc


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "casino_test.blend")
    build(out)
    print("BUILD OK", out)
