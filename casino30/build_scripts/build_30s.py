"""build_30s.py - builds the 30 s (900 frame) casino video scene and saves casino30.blend.
Usage: python build_30s.py [out.blend] [--engine eevee|cycles]
Runs under the bpy module (4.5 or 5.x). Eevee engine id is chosen from the running Blender version."""
import bpy, math, os, sys
from mathutils import Vector
import casino_scene as cs
import casino_char as ch
import casino30_sets as st

HERE = cs.HERE
F = st.F
CHAR_B_ORIGIN = (-1.40, -0.47, cs.STOOL_TOP)
STOOL2 = (0.85, -0.52)

# (frame, camera, target) for the first 5 s are the proven keys from build_all.py
CAM_FIRST5 = [
    (1,   (0.22, -0.60, 1.27), (0.24, 0.20, 1.34)),
    (14,  (0.17, -0.66, 1.30), (0.20, 0.20, 1.36)),
    (19,  (0.10, -0.78, 1.32), (0.12, 0.20, 1.38)),
    (27,  (0.00, -1.80, 1.42), (0.02, 0.00, 1.40)),
    (35,  (0.02, -3.05, 1.36), (0.06, 0.00, 1.30)),
    (60,  (-0.02, -2.90, 1.36), (0.00, 0.00, 1.30)),
    (105, (-0.20, -2.50, 1.42), (-0.12, 0.00, 1.40)),
    (150, (-0.30, -2.10, 1.44), (-0.20, 0.00, 1.44)),
]
X = st.ROW_X if hasattr(st, "ROW_X") else 0


def strip_cam(row, t):
    """camera + target for looking at sheet row `row` (world coords from the tilted sheet)."""
    tz = st.strip_row_z(row)
    tw = st.strip_world((0.0, 0.0, tz))
    return (tw.x - 0.05, tw.y - 1.55, tw.z - 0.45), (tw.x, tw.y, tw.z)


# SHOTS: (t_start, t_end, [(t, cam, target)], fstop, focus_distance)   t in seconds
def shots():
    S = []
    S.append((0.0, 5.0, [(f_ / 30.0 - 1 / 30.0, c, t) for f_, c, t in CAM_FIRST5], 64, 3.0))
    S.append((5.0, 5.5, [(5.0, (-0.30, -2.10, 1.44), (-0.20, 0.0, 1.44)), (5.47, (-0.34, -2.00, 1.50), (-0.22, 0.0, 1.62))], 64, 3.0))
    S.append((5.5, 8.5, [(5.5, (-0.10, -4.70, 1.75), (-0.10, 0.0, 2.15)), (7.0, (-0.18, -3.90, 1.65), (-0.20, 0.0, 1.95)), (8.47, (-0.30, -3.00, 1.55), (-0.30, 0.0, 1.70))], 64, 3.0))
    S.append((8.5, 11.5, [(8.5, (-0.85, -2.60, 1.00), (-0.85, 0.0, 1.75)), (11.47, (-0.85, -2.35, 1.05), (-0.85, 0.0, 1.80))], 64, 2.0))
    S.append((11.5, 13.5, [(11.5, (st.CU_X - 0.15, -0.95, 0.90), (st.CU_X + 0.05, 0.12, 0.42)), (13.47, (st.CU_X, -0.82, 0.82), (st.CU_X + 0.12, 0.15, 0.50))], 2.8, 0.95))
    S.append((13.5, 14.0, [(13.5, (st.CU_X - 0.5, -0.62, 0.60), (st.CU_X - 0.5, 0.40, 0.60)), (13.97, (st.CU_X - 0.5, -0.55, 0.60), (st.CU_X - 0.5, 0.40, 0.60))], 4.0, 0.75))
    S.append((14.0, 16.5, [(14.0, (0.62, -1.60, 1.30), (0.25, 0.10, 1.30)), (16.47, (0.55, -1.45, 1.30), (0.30, 0.10, 1.32))], 64, 3.0))
    S.append((16.5, 17.5, [(16.5, (0.10, -3.30, 1.25), (0.10, 0.0, 1.30)), (17.47, (0.05, -3.00, 1.30), (0.05, 0.0, 1.30))], 64, 3.0))
    S.append((17.5, 18.0, [(17.5, (0.25, -0.90, 1.35), (0.25, 0.33, 1.35)), (17.97, (0.25, -0.62, 1.35), (0.25, 0.33, 1.35))], 64, 3.0))
    S.append((18.0, 19.0, [(18.0, (st.IN_X - 0.10, -1.35, 1.05), (st.IN_X, 0.40, 1.15)), (18.97, (st.IN_X - 0.05, -1.05, 1.10), (st.IN_X, 0.40, 1.20))], 64, 3.0))
    rows = [(19.0, 4.0), (20.0, 6.0), (21.0, 8.7), (22.5, 9.4), (24.0, 14.0), (25.47, 19.0)]
    S.append((19.0, 25.5, [(t, *strip_cam(r, t)) for t, r in rows], 64, 3.0))
    S.append((25.5, 26.0, [(25.5, (st.WH_X - 0.10, -1.20, 1.00), (st.WH_X, 0.0, 1.00)), (25.97, (st.WH_X - 0.05, -0.90, 1.00), (st.WH_X, 0.0, 1.00))], 64, 3.0))
    S.append((26.0, 30.0, [(26.0, (0.40, -1.50, 1.05), (0.20, 0.10, 1.05)), (30.0 - 1 / 30, (0.32, -1.40, 1.05), (0.22, 0.10, 1.05))], 64, 3.0))
    return S


def build_camera(sc):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = 32
    cd.dof.use_dof = True
    cam = bpy.data.objects.new("Camera", cd)
    cs.link(cam)
    sc.camera = cam
    tgt = bpy.data.objects.new("CamTarget", None)
    cs.link(tgt)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    cut_frames = []
    for ts, te, keys, fstop, focus in shots():
        for t, loc, tg in keys:
            f = max(1, int(round(1 + t * 30)))
            cam.location, tgt.location = loc, tg
            cam.keyframe_insert("location", frame=f)
            tgt.keyframe_insert("location", frame=f)
            cd.dof.aperture_fstop, cd.dof.focus_distance = fstop, focus
            cd.dof.keyframe_insert("aperture_fstop", frame=f)
            cd.dof.keyframe_insert("focus_distance", frame=f)
        cut_frames.append(max(1, int(round(1 + keys[-1][0] * 30))))
    # hard cut after the last key of every shot: CONSTANT interpolation on those keys
    for owner in (cam, tgt, cd):
        for fc in cs.fcurves_of(owner):
            for kp in fc.keyframe_points:
                if int(round(kp.co[0])) in cut_frames[:-1]:
                    kp.interpolation = "CONSTANT"
    return cam


WORDS = [  # (t, text): 0-5 s from the earlier test; 5-30 s read from the reference frames (see shot_breakdown_30s.md)
    (0.0, "You"), (0.25, "just"), (0.5, "watched"), (0.75, "two"), (1.25, "jackpot"), (1.75, "symbols"), (2.0, "land."),
    (2.5, "And the"), (2.75, "third"), (3.0, "one"), (3.25, "stopped"), (3.5, "one"), (3.75, "click"), (4.0, "short."), (4.5, "So"),
    (5.0, "move to"), (5.5, "machine"), (6.0, "next door,"), (6.5, "the exact"), (7.0, "same"), (7.5, "thing"), (8.0, "happens."),
    (8.4, "Your buddy"), (8.75, "leans"), (9.0, "over"), (9.25, "and"), (9.4, "says,"), (9.75, "Bro,"), (10.25, "it's"), (10.5, "just"),
    (10.9, "warming"), (11.25, "up."), (11.5, "So I"), (12.0, "put in"), (12.4, "a"), (12.6, "hundred,"), (13.0, "but"), (13.3, "it's"),
    (13.6, "starting"), (14.0, "like"), (14.3, "the"), (14.5, "machine"), (14.8, "is"), (15.0, "teasing"), (15.5, "purpose."),
    (16.5, "So"), (16.8, "I"), (17.0, "crack"), (17.5, "open."), (17.9, "Inside"), (18.4, "a list"), (19.0, "every place"),
    (20.0, "last"), (20.5, "stop."), (21.0, "The"), (21.5, "jackpot"), (22.0, "that"), (22.5, "Once"), (23.0, "one"), (23.5, "short"),
    (24.0, "on there"), (24.5, "over"), (25.0, "and over."), (26.0, "every time"), (26.5, "spin,"), (27.0, "the"), (27.5, "is way"),
    (28.0, "more"), (28.5, "to stop"), (29.0, "one"), (29.5, "short."),
]
WORD_END = 30.0


def build_captions(sc, cam):
    col = cs.coll("Captions")
    fnt = bpy.data.fonts.load("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
    white = cs.mat("CapWhite", (1, 1, 1), emit=(1, 1, 1), estr=1.4)
    shadow = cs.mat("CapShadow", (0.02, 0.01, 0.01), rough=1.0)
    for i, (t, w) in enumerate(WORDS):
        start = ch.fr(t)
        end = ch.fr(min(WORDS[i + 1][0], WORD_END) if i + 1 < len(WORDS) else WORD_END) + 0
        if i + 1 < len(WORDS) and WORDS[i + 1][0] - t > 0.7:
            end = ch.fr(t + 0.7)      # a word is never held longer than 0.7 s
        for layer, (m, off) in enumerate([(shadow, (0.0025, -0.0025, -0.001)), (white, (0, 0, 0))]):
            cu = bpy.data.curves.new(f"Cap{i}_{layer}", "FONT")
            cu.body, cu.font, cu.size = w, fnt, 0.062
            cu.align_x = "CENTER"
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
            for fc in cs.fcurves_of(ob):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def move_character(objs, offsets):
    """Meshes are skinned but not parented, so cut-moves must key every object (and the rig) together.
    offsets: list of (t seconds, (dx,dy,dz)); first key at frame 1 = 0 offset."""
    for ob in objs:
        base = ob.location.copy()
        ob.location = base
        ob.keyframe_insert("location", frame=1)
        for t, d in offsets:
            ob.location = base + Vector(d)
            ob.keyframe_insert("location", frame=F(t))
        for fc in cs.fcurves_of(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def set_visible_window(objs, t0, t1):
    for ob in objs:
        st.keyed_visible(ob, t0, t1)


def setup_render(sc, engine="eevee", samples=64):
    if engine == "cycles":
        sc.render.engine = "CYCLES"
        sc.cycles.device, sc.cycles.samples = "CPU", 32
        sc.cycles.use_denoising, sc.cycles.denoiser = True, "OPENIMAGEDENOISE"
    else:
        ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
        sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in ids else "BLENDER_EEVEE_NEXT"
        e = sc.eevee
        e.taa_render_samples = samples
        if hasattr(e, "use_raytracing"):
            e.use_raytracing = False
        if hasattr(e, "use_shadows"):
            e.use_shadows = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 720, 1280, 100
    sc.render.fps = 30
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
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
    ls.select_silhouette = ls.select_border = ls.select_crease = True
    ls.select_edge_mark = False
    ls.linestyle.color = (0.07, 0.03, 0.02)
    ls.linestyle.thickness = 5.5


def build(out=None, engine="eevee", samples=64):
    sc = cs.reset()
    hero = cs.build_environment(sc)
    st.build_ceiling_and_sign(bpy.data.collections["Environment"])
    cs.animate_reels(hero)
    cs.build_lights(sc)
    before = set(bpy.data.objects)
    rigA, faceA = ch.build_character()
    objsA = [o for o in set(bpy.data.objects) - before]
    ch.animate_character(rigA, faceA)
    before = set(bpy.data.objects)
    rigB, faceB = ch.build_character(origin=CHAR_B_ORIGIN, style="B")
    objsB = [o for o in set(bpy.data.objects) - before]
    ch.animate_friend(rigB, faceB)
    set_visible_window(objsB, 8.35, 11.55)
    # A sits on the right-hand stool for the over-the-shoulder shots (14-16.4 s and 26-30 s)
    dx, dy = STOOL2[0] - cs.CHAR_X, STOOL2[1] - cs.CHAR_Y
    move_character(objsA, [(14.0, (dx, dy, 0)), (16.4, (0, 0, 0)), (25.9, (dx, dy, 0))])
    st.build_closeup(sc)
    st.build_inside(sc)
    st.build_strip(sc)
    st.build_wheel(sc)
    cam = build_camera(sc)
    build_captions(sc, cam)
    sc.frame_start, sc.frame_end = 1, cs.F_END
    setup_render(sc, engine, samples)
    sc.frame_set(1)
    bpy.ops.file.pack_all()
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=out)
    return sc


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    eng = "cycles" if "--engine" in sys.argv and sys.argv[sys.argv.index("--engine") + 1] == "cycles" else "eevee"
    out = args[0] if args and args[0].endswith(".blend") else os.path.join(HERE, "casino30.blend")
    build(out, eng)
    print("BUILD OK", out, bpy.app.version_string)
