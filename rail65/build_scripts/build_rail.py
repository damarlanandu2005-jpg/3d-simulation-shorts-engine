"""build_rail.py - builds the 65 s (1956 frame) railroad video scene and saves rail65.blend.
Usage: python build_rail.py [out.blend]     (bpy 5.x; Eevee)"""
import bpy, math, os, sys, json
from mathutils import Vector
import casino_scene as cs
import casino_char as ch
import rail_sets as rs
import rail_chars as rc
from casino_scene import mat, link, coll, box, ball, panel

HERE = cs.HERE
F = rs.F
OX = rs.OX
T, B_, D_, L_, S_, BM_, DK, CR, G_ = OX["TRACK"], OX["BRIDGE"], OX["DESERT"], OX["LEDGE"], OX["STATION"], OX["BEAM"], OX["DECK"], OX["CAR"], OX["GAP"]
IX = CR + 40            # car interior x
TX = CR + 80            # ticket booth x
SUN_X = DK              # deck sunbather x
PLANK = (B_ + 9.0, 45.5, 0.51)

# ------------------------------------------------------------------ SHOTS: (t0, t1, [(t, cam, target)], fstop, focus)
def shots():
    S = []
    S.append((0.0, 2.13, [(0.0, (T - 0.55, -1.5, 0.55), (T + 0.2, 6, 0.95)), (2.1, (T - 0.40, -0.9, 0.60), (T + 0.2, 6, 1.0))], 64, 3.0))
    S.append((2.13, 3.93, [(2.13, (T + 0.1, -0.4, 0.55), (T + 0.7, 6, 1.35)), (3.9, (T + 0.3, 0.2, 0.60), (T + 0.7, 6, 1.35))], 64, 3.0))
    S.append((3.93, 7.83, [(3.93, (B_ - 3, -25, 26), (B_ + 2, 45, 0)), (5.9, (B_ - 2, 12, 15), (B_ + 4, 70, -12)), (7.8, (B_ + 6, 38, 5.5), (B_ + 9, 46, 0.6))], 64, 3.0))
    S.append((7.83, 8.67, [(7.83, (B_ + 9.3, 54, 4.2), (B_ + 9, 46, -8)), (8.64, (B_ + 9.3, 52, 3.4), (B_ + 9, 45, -10))], 64, 3.0))
    S.append((8.67, 10.6, [(8.67, (D_ + 17, 16, 2.4), (D_, 40, 2.4)), (10.57, (D_ + 17, 70, 2.6), (D_, 98, 2.6))], 64, 3.0))
    S.append((10.6, 11.77, [(10.6, (S_, 3.2, 2.2), (S_, 10.6, 3.0)), (11.74, (S_, 5.6, 2.5), (S_, 10.6, 3.0))], 64, 3.0))
    S.append((11.77, 13.63, [(11.77, (BM_ + 0.2, -4.6, -0.4), (BM_, 0, 0.7)), (13.6, (BM_ + 0.6, -3.9, -0.2), (BM_ + 0.2, 0, 0.7))], 64, 3.0))
    S.append((13.63, 15.5, [(13.63, (T + 0.35, 1.3, 0.50), (T + 0.05, 3.4, 0.85)), (15.47, (T + 0.3, 1.9, 0.55), (T, 3.4, 0.9))], 3.5, 2.0))
    S.append((15.5, 17.3, [(15.5, (T + 0.3, -1.0, 0.70), (T, 5.2, 1.5)), (17.27, (T + 0.2, -0.4, 0.75), (T, 5.2, 1.55))], 64, 3.0))
    S.append((17.3, 19.5, [(17.3, (T + 0.1, -2.2, 0.85), (T - 0.4, 5.2, 1.5)), (19.47, (T + 0.1, -1.5, 0.85), (T - 0.4, 5.2, 1.5))], 64, 3.0))
    S.append((19.5, 20.6, [(19.5, (T + 0.2, -3.4, 0.95), (T - 0.3, 5.2, 1.4)), (20.57, (T + 0.2, -2.8, 0.95), (T - 0.3, 5.2, 1.4))], 64, 3.0))
    S.append((20.6, 21.87, [(20.6, (T + 0.4, -0.2, 0.30), (T + 0.6, 4.0, 0.25)), (21.84, (T + 0.4, 0.5, 0.30), (T + 0.6, 4.0, 0.25))], 4.0, 1.5))
    S.append((21.87, 24.23, [(21.87, (DK + 0.3, 6, 1.5), (DK - 0.2, 24, 1.5)), (24.2, (DK + 0.2, 15, 1.4), (DK - 0.7, 24, 1.7))], 64, 3.0))
    S.append((24.23, 26.47, [(24.23, (DK + 0.4, 4, 0.55), (DK, 22, 1.0)), (26.44, (DK + 0.2, 20, 0.7), (DK - 0.5, 36, 1.2))], 64, 3.0))
    S.append((26.47, 27.4, [(26.47, (CR - 9, -8, 2.2), (CR - 2, 0, 2.3)), (27.37, (CR + 8, -8, 2.2), (CR + 2, 0, 2.3))], 64, 3.0))
    S.append((27.4, 28.53, [(27.4, (IX - 0.3, -1.8, 1.65), (IX - 0.6, 1.7, 1.6)), (28.5, (IX - 0.3, -1.3, 1.7), (IX - 0.6, 1.7, 1.6))], 64, 3.0))
    S.append((28.53, 31.37, [(28.53, (TX, -1.4, 2.55), (TX, 4.8, 2.55)), (31.34, (TX, -0.7, 2.6), (TX, 4.8, 2.6))], 64, 3.0))
    S.append((31.37, 33.83, [(31.37, (S_ + 0.2, -8, 1.5), (S_ + 0.2, 0, 1.5)), (33.8, (S_ + 0.2, -5.4, 1.6), (S_ + 0.2, 0, 1.6))], 64, 3.0))
    S.append((33.83, 36.23, [(33.83, (S_ + 1.0, -9, 1.7), (S_ + 2.5, 0, 1.9)), (36.2, (S_ + 1.6, -6.5, 1.75), (S_ + 2.8, 0, 1.9))], 64, 3.0))
    S.append((36.23, 40.17, [(36.23, (G_ + 0.9, 1.9, 0.65), (G_ + 0.85, 3.7, 0.62)), (40.14, (G_ + 0.9, 2.5, 0.65), (G_ + 0.85, 3.7, 0.62))], 64, 3.0))
    S.append((40.17, 44.5, [(40.17, (G_ - 0.35, -0.7, 0.55), (G_, 0, 0.33)), (44.47, (G_ - 0.2, -0.45, 0.45), (G_, 0, 0.33))], 2.8, 0.8))
    S.append((44.5, 48.13, [(44.5, (G_ + 0.2, -1.9, 0.38), (G_ + 0.1, 1.2, 1.0)), (48.1, (G_ + 0.2, -1.3, 0.40), (G_ + 0.1, 1.2, 1.0))], 64, 3.0))
    S.append((48.13, 51.37, [(48.13, (DK + 0.4, -6, 0.55), (DK + 0.4, 6, 0.7)), (51.34, (DK + 0.4, 2, 0.45), (DK + 0.3, 14, 0.5))], 64, 3.0))
    S.append((51.37, 54.53, [(51.37, (SUN_X - 0.3, 38, 0.8), (SUN_X + 0.2, 48, 1.1)), (54.5, (SUN_X - 0.1, 41, 0.95), (SUN_X + 0.4, 48, 1.15))], 64, 3.0))
    S.append((54.53, 57.93, [(54.53, (L_ + 0.1, 0.2, 0.85), (L_, 5.5, 1.1)), (57.9, (L_ + 0.55, 1.5, 0.30), (L_ + 0.45, 8, 0.30))], 64, 3.0))
    S.append((57.93, 59.6, [(57.93, (L_ + 0.1, -0.5, 0.30), (L_, 18, 0.7)), (59.57, (L_ + 0.1, 3.0, 0.40), (L_, 18, 0.7))], 64, 3.0))
    S.append((59.6, 63.13, [(59.6, (B_ - 12, 4, 8), (B_, 95, 4)), (60.9, (B_, 16, 2.4), (B_, 80, 2.5)), (63.1, (B_ + 32, 62, 7.5), (B_, 72, -3))], 64, 3.0))
    S.append((63.13, 64.5, [(63.13, (B_ + 32, 62, 7.5), (B_, 72, -4)), (64.47, (B_ + 22, 66, 3.5), (B_ + 1, 70, 2.0))], 64, 3.0))
    S.append((64.5, 65.17, [(64.5, (B_ - 0.3, 49.5, 1.2), (B_, 60, 4.5)), (65.14, (B_ - 0.3, 50, 1.4), (B_, 60, 5.5))], 64, 3.0))
    return S


# ------------------------------------------------------------------ captions (OCR of the reference's burned-in captions, 6 fps sampling)
WORDS = [
    (0.0, "He sawed"), (0.5, "gaps"), (1.0, "into a"), (1.17, "railroad"), (1.83, "every 39"), (2.83, "feet."), (3.33, "See,"), (3.67, "two"), (4.0, "companies"),
    (4.5, "racing"), (5.17, "to build"), (5.5, "a railroad"), (6.0, "along"), (6.17, "a canyon"), (6.67, "so deep"), (7.5, "you can't"), (7.83, "see the"),
    (8.17, "bottom."), (8.5, "And"), (8.67, "whoever"), (9.0, "finishes"), (9.33, "first"), (9.83, "gets the"), (10.17, "whole"), (10.5, "country's"),
    (11.0, "business."), (11.67, "He's"), (11.83, "the youngest"), (12.33, "engineer"), (12.67, "on the job."), (13.33, "And"), (13.5, "when"),
    (13.67, "his boss"), (14.33, "finds a finger"), (14.67, "wide"), (15.0, "gap"), (15.33, "between"), (15.83, "every"), (16.0, "single"), (16.33, "rail,"),
    (17.0, "his face"), (17.33, "goes"), (17.67, "purple."), (18.17, "You're"), (18.33, "wrecking"), (18.67, "my railroad."), (19.7, "He wants to"),
    (20.5, "close a"), (20.83, "single"), (21.33, "one."), (21.67, "The other"), (22.17, "company"), (22.33, "lays"), (22.67, "their"), (22.83, "rails"),
    (23.17, "end"), (23.33, "to end,"), (24.0, "perfectly"), (24.33, "smooth"), (24.83, "and"), (25.0, "finishes"), (25.5, "first."), (26.0, "Their"),
    (26.17, "trains"), (26.5, "glide"), (27.0, "across"), (27.33, "canyon"), (27.67, "without a sound"), (28.67, "while"), (28.83, "his go"), (29.33, "clickety"),
    (29.83, "clack"), (30.33, "every gap."), (31.17, "The"), (31.33, "newspapers"), (32.0, "calling it"), (33.0, "the clickety"), (33.5, "clack line"),
    (33.83, "and"), (34.0, "everyone"), (34.33, "switches"), (34.83, "to the quiet"), (35.33, "trains."), (35.83, "Then"), (36.17, "summer"), (36.67, "comes"),
    (37.33, "and"), (37.67, "something"), (38.0, "weird"), (38.33, "happens."), (38.67, "His"), (38.83, "gaps"), (39.33, "start"), (39.67, "shrinking"),
    (40.17, "in May."), (40.83, "You can fit"), (41.17, "a coin"), (41.67, "in them"), (41.83, "by"), (42.0, "July."), (44.5, "His"), (44.67, "boss is"),
    (45.17, "thrilled."), (46.17, "Even"), (46.5, "though"), (46.67, "your gaps"), (47.17, "were"), (47.67, "wrong."), (47.83, "Meanwhile,"), (48.5, "on the"),
    (48.67, "perfect"), (49.33, "railroad,"), (49.67, "the rails"), (50.17, "started"), (50.5, "groaning"), (51.17, "in the"), (51.33, "afternoon"), (51.83, "sun,"),
    (52.17, "pushing"), (52.5, "against"), (52.83, "each other"), (53.33, "like"), (53.5, "they want to"), (53.83, "get"), (54.0, "out."), (54.33, "On"),
    (54.5, "the hottest"), (55.0, "day"), (55.5, "anyone"), (56.0, "can"), (56.17, "remember."), (57.0, "His"), (57.67, "finally"), (58.0, "close."), (58.33, "Rail"),
    (58.8, "touching"), (59.33, "And"), (59.5, "halfway"), (59.83, "across"), (60.17, "the canyon,"), (60.67, "the perfect"), (61.33, "railroad"), (61.67, "kicks"),
    (62.17, "sideways"), (62.5, "like"), (62.67, "a snake,"), (63.33, "right"), (63.67, "as a"), (63.83, "train"), (64.17, "rolls"), (64.5, "onto"), (64.83, "it."),
]
WORD_END = 65.17


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
            f = max(1, F(t))
            cam.location, tgt.location = loc, tg
            cam.keyframe_insert("location", frame=f)
            tgt.keyframe_insert("location", frame=f)
            cd.dof.aperture_fstop, cd.dof.focus_distance = fstop, focus
            cd.dof.keyframe_insert("aperture_fstop", frame=f)
            cd.dof.keyframe_insert("focus_distance", frame=f)
        cut_frames.append(max(1, F(keys[-1][0])))
    for owner in (cam, tgt, cd):
        for fc in cs.fcurves_of(owner):
            for kp in fc.keyframe_points:
                if int(round(kp.co[0])) in cut_frames[:-1]:
                    kp.interpolation = "CONSTANT"
    return cam


def build_captions(sc, cam):
    col = cs.coll("Captions")
    fnt = bpy.data.fonts.load("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
    white = cs.mat("CapWhite", (1, 1, 1), emit=(1, 1, 1), estr=1.4)
    shadow = cs.mat("CapShadow", (0.02, 0.01, 0.01), rough=1.0)
    for i, (t, w) in enumerate(WORDS):
        start = F(t)
        end = F(min(WORDS[i + 1][0], WORD_END)) if i + 1 < len(WORDS) else F(WORD_END)
        if i + 1 < len(WORDS) and WORDS[i + 1][0] - t > 0.8:
            end = F(t + 0.8)
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


def setup_render(sc, samples=64):
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
    sc.view_settings.exposure = -0.3
    sc.render.use_freestyle = False          # outlines are inverted-hull meshes now (rail_chars.add_outline): fast, no Freestyle
    return
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
    ls.linestyle.thickness = 4.5


# ------------------------------------------------------------------ helpers
FAR = (0, 0, -600)


def hop(ob, keys):
    """teleport keys (CONSTANT): keys = [(t, (x,y,z))]"""
    for t, p in keys:
        ob.location = p
        ob.keyframe_insert("location", frame=F(t))
    for fc in cs.fcurves_of(ob):
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def expr(face, seq):
    """seq = [(t, 'Happy'), ...] smooth blend between face shape keys"""
    kb = face.data.shape_keys.key_blocks
    names = [k.name for k in kb if k.name != "Basis"]
    for t, e in seq:
        for n in names:
            kb[n].value = 1.0 if n == e else 0.0
            kb[n].keyframe_insert("value", frame=F(t))


def actor(name, costume, loc, yaw=0.0, sc_=1.0, windows=None, mode="stand", seat_z=None):
    """build + place a character. windows=[(t0,t1)] when it is on set (else teleported far away).
    mode: stand | sit"""
    root, rig, face, objs = rc.build_rail_char(name, costume)
    rc.place(root, loc, yaw, sc_)
    if mode == "sit":
        root.location = (loc[0], loc[1], seat_z)
    on = tuple(root.location)
    if windows:
        keys = [(0.0, FAR)]
        for t0, t1 in windows:
            keys += [(t0, on), (t1, FAR)]
        hop(root, keys)
    expr(face, [(0.0, "Happy")])
    rc.idle(rig, 0.0, 66.0, amp=1.0) if mode == "stand" else rc.sit_dangling(rig, 0.0, 66.0)
    return root, rig, face


def notch(name, x, y, z, m, col):
    box(name, 0.09, 0.07, 0.30, (x, y, z), m["black"], 0, col)


def snake_rails(m, ox, y0, y1, t0, t1, amp):
    """segmented rails + ties that buckle sideways over the canyon (visible t0..t1); returns segments"""
    col = coll("Env_Snake")
    segs = []
    n = 40
    L = (y1 - y0) / n
    for i in range(n):
        y = y0 + (i + 0.5) * L
        e = bpy.data.objects.new(f"SN_{i}", None)
        link(e, col)
        e.location = (ox, y, 0.0)
        for s in (-1, 1):
            r_ = box(f"SN_R{i}_{s}", 0.075, L + 0.04, 0.17, (0, 0, 0.27), m["rail"], 0.01, col)
            r_.location = (s * rs.GAUGE, 0, 0.27)
            r_.parent = e
        t_ = box(f"SN_T{i}", 2.5, 0.22, 0.14, (0, 0, 0.07), m["tie"], 0, col)
        t_.location = (0, 0, 0.07)
        t_.parent = e
        segs.append((e, y))
    for e, y in segs:
        ph = (y - 70) / 50.0
        keys = [(0.0, FAR)]
        keys_loc = [(t0 - 0.01, (ox, y, 0.0)), (t0, (ox, y, 0.0))]
        e.location = FAR
        e.keyframe_insert("location", frame=1)
        e.location = (ox, y, 0.0)
        e.keyframe_insert("location", frame=F(t0 - 0.02))
        for tt, k in ((t0 + 0.8, 0.0), (t0 + 2.4, 0.6), (t1, 1.0)):
            e.location = (ox + amp * k * math.sin(ph * math.pi * 2.2 + 0.7) * (1 - abs(ph) * 0.6), y, 0.0)
            e.rotation_euler = (0, 0, -amp * k * 0.5 * math.cos(ph * math.pi * 2.2 + 0.7))
            e.keyframe_insert("location", frame=F(tt))
            e.keyframe_insert("rotation_euler", frame=F(tt))
    for e, y in segs:     # on t<t0 the real track shows instead; segments hidden far below until t0
        pass
    return segs


# ------------------------------------------------------------------ main assembly
def build_all():
    sc = cs.reset()
    m = rs.M()
    rs.build_world(sc)
    sun = rs.build_lights(sc)
    hot = {"L": mat("RailHotL", (0.62, 0.62, 0.66), metallic=0.6, rough=0.3, emit=(0.5, 0.5, 0.55), estr=0.0),
           "R": mat("RailHotR", (0.62, 0.62, 0.66), metallic=0.6, rough=0.3, emit=(0.5, 0.5, 0.55), estr=0.0)}
    rs.build_track_set(m)
    rs.build_bridge_set(m)
    rs.build_desert_set(m)
    rs.build_track_set(m, ledge=True, ox=L_)
    rs.build_station_set(m)
    rs.build_beam_set(m)
    rs.build_deck_set(m, hot)
    rs.build_car_set(m)
    g = rs.build_gap_set(m, hot)
    col = coll("Props")
    # gap notches on the first track (the 'sawn gaps')
    for y in (3.4, 6.0, 18.0, 30.0):
        for s in (-1, 1):
            notch(f"Notch_{y}_{s}", T + s * rs.GAUGE, y, 0.28, m, col)
    # ---- hot rails (summer): glow ramps up on the deck set, 48 s -> 57 s
    for k in hot.values():
        rs.keyed_emission(k, [(0.0, (0.9, 0.2, 0.05), 0.0), (48.0, (0.9, 0.2, 0.05), 0.0), (51.3, (1.0, 0.35, 0.06), 1.6), (54.0, (1.0, 0.45, 0.08), 3.2), (66.0, (1.0, 0.45, 0.08), 3.2)])
    # ---- gap set animation: heat shrinks the gap; calendar May -> July; mercury rises; coin fits
    for tt, dx in ((0.0, 0.18), (40.17, 0.18), (41.6, 0.10), (42.8, 0.03), (44.4, 0.0)):
        for ob in (g["railB"], g["baseB"]):
            ob.location.x = G_ + 1.5 + dx
            ob.keyframe_insert("location", frame=F(tt), index=0)
    rs.keyed_visible(g["calm"], 0.0, 38.6)
    rs.keyed_visible(g["calj"], 38.6, 66.0)
    for tt, sz in ((36.2, 0.5), (39.0, 0.9), (42.0, 1.35), (44.4, 1.35)):
        g["merc"].scale.z = sz / 0.5
        g["merc"].location.z = 0.15 + sz / 2
        g["merc"].keyframe_insert("scale", frame=F(tt))
        g["merc"].keyframe_insert("location", frame=F(tt))
    rs.keyed_visible(g["coin"], 41.0, 43.0)
    rs.keyed_visible(g["cal"], 40.1, 44.5)
    # ---- trains
    loco_a = rs.locomotive("LocoA", (B_, 0, 0), m, col, facing_neg_y=False)
    rs.keyed_loc(loco_a, [(0.0, (B_, -60, 0)), (3.93, (B_, -60, 0)), (3.94, (B_, 8, 0)), (7.83, (B_, 105, 0)), (7.84, (B_, -60, 0))], "LINEAR")
    rs.smoke_puffs("SmA", Vector((B_, 12, 4.6)), col, m["smoke"], 3.9, 7.9, n=10, life=2.2, drift=(0.0, 3.0, 0.0), rise=6.0)
    loco_g = rs.locomotive("LocoG", (D_ - 3, 0, 0), m, col, facing_neg_y=False, body=m["green"])
    loco_r = rs.locomotive("LocoR", (D_ + 3, 0, 0), m, col, facing_neg_y=False, body=m["red"])
    rs.keyed_loc(loco_g, [(0.0, (D_ - 3, -60, 0)), (8.65, (D_ - 3, -60, 0)), (8.67, (D_ - 3, 22, 0)), (10.6, (D_ - 3, 120, 0)), (10.62, (D_ - 3, -60, 0))], "LINEAR")
    rs.keyed_loc(loco_r, [(0.0, (D_ + 3, -60, 0)), (8.65, (D_ + 3, -60, 0)), (8.67, (D_ + 3, 18, 0)), (10.6, (D_ + 3, 118, 0)), (10.62, (D_ + 3, -60, 0))], "LINEAR")
    rs.smoke_puffs("SmG", Vector((D_ - 3, 40, 4.6)), col, m["smoke"], 8.6, 10.6, n=8, life=1.6, drift=(0.0, -2.0, 0.0), rise=5.0)
    rs.smoke_puffs("SmR", Vector((D_ + 3, 40, 4.6)), col, m["smoke"], 8.6, 10.6, n=8, life=1.6, drift=(0.0, -2.0, 0.0), rise=5.0)
    # silent smooth trains pass the car window (26.5-27.4 s): navy car is static, the camera pans along it
    # final train rolling onto the kinking rails (63.1 -> 65.17 s)
    loco_f = rs.locomotive("LocoF", (B_, -60, 0), m, col, facing_neg_y=True)
    rs.keyed_loc(loco_f, [(0.0, (B_, -60, 0)), (63.1, (B_, -60, 0)), (63.12, (B_, 118, 0)), (65.17, (B_, 68, 0))], "LINEAR")
    loco_f.rotation_euler = (0, 0, 0)
    for tt, rz in ((63.12, 0.0), (64.3, 0.03), (65.17, 0.12)):
        loco_f.rotation_euler = (0, 0, rz)
        loco_f.keyframe_insert("rotation_euler", frame=F(tt))
    rs.smoke_puffs("SmF", Vector((B_, 85, 4.6)), col, m["smoke"], 63.1, 65.2, n=6, life=1.6, drift=(0.0, -2.0, 0.0), rise=5.0)
    # ---- the saw + sparks (0-3.9 s on the first track)
    saw = box("Saw", 0.04, 0.55, 0.08, (T, 6.0, 0.55), m["steel"], 0, col)
    for tt, dy in ((0.0, 0.0), (0.2, -0.18), (0.4, 0.0), (0.6, -0.18), (0.8, 0.0), (1.0, -0.18), (1.2, 0.0), (1.4, -0.18), (1.6, 0.0), (1.8, -0.18), (2.0, 0.0), (2.2, -0.18), (2.4, 0.0), (2.6, -0.18), (2.8, 0.0), (3.0, -0.18), (3.2, 0.0), (3.4, -0.18), (3.6, 0.0), (3.9, 0.0)):
        saw.location = (T + 0.35, 6.0 + dy, 0.45)
        saw.keyframe_insert("location", frame=F(tt))
    for i in range(6):
        sp = ball(f"Spark{i}", 0.05, (T + 0.35, 6.0, 0.35), m["fire2"], seg=8, rings=6, col=col)
        t = 0.1 + i * 0.12
        while t < 3.9:
            for tt, s_, p in ((t, 0.0, (T + 0.35, 6.0, 0.35)), (t + 0.06, 1.0, (T + 0.35 + 0.15 * math.cos(i), 6.0 - 0.1, 0.5)), (t + 0.3, 0.0, (T + 0.35 + 0.45 * math.cos(i * 2.1), 5.8, 0.15))):
                sp.scale, sp.location = (s_,) * 3, p
                sp.keyframe_insert("scale", frame=F(tt))
                sp.keyframe_insert("location", frame=F(tt))
            t += 0.72
    # ---- steam over hot rails (deck set, 48-54.5 s)
    rs.smoke_puffs("HeatA", Vector((DK - 0.7, 9, 0.5)), col, m["steam"], 48.2, 51.4, n=8, life=1.8, drift=(0.0, 0.0, 0.0), rise=2.2, r0=0.2, r1=0.6)
    rs.smoke_puffs("HeatB", Vector((SUN_X - 0.7, 40, 0.5)), col, m["steam"], 51.4, 54.6, n=8, life=1.8, drift=(0.0, 0.0, 0.0), rise=2.2, r0=0.2, r1=0.6)
    # ---- the perfect railroad buckles (59.6-65.17 s) on the bridge
    segs = snake_rails(m, B_, 20.0, 120.0, 60.0, 65.2, 3.2)
    # ---- shake: camera handled by build_camera; no extra
    # ---- characters (windows = time ranges a character is on set; elsewhere teleported away)
    W = lambda *r: list(r)
    A = {}
    A["eng_saw"] = actor("engA", "worker4", (T - 0.4, 6.0, 0), 0, 1.0, W((0.0, 3.93)))
    A["wk_saw"] = actor("wkA", "worker1", (T + 0.8, 6.0, 0), -10, 1.0, W((0.0, 3.93)))
    A["engineer_plank"] = actor("engP", "engineer", (B_ + 9.0, 45.0, 0.51), 0, 1.0, W((7.83, 8.67)))
    A["tycoon_steps"] = actor("tycS", "tycoon", (S_, 10.6, 1.5), 0, 1.0, W((10.6, 11.77)))
    A["beam1"] = actor("bm1", "worker4", (BM_ - 0.5, 0.0, 0), 0, 1.0, W((11.77, 13.63)), mode="sit", seat_z=0.36)
    A["beam2"] = actor("bm2", "worker1", (BM_ + 0.55, 0.0, 0), 0, 1.0, W((11.77, 13.63)), mode="sit", seat_z=0.36)
    A["beam3"] = actor("bm3", "worker2", (BM_ + 1.6, 0.0, 0), 0, 1.0, W((11.77, 13.63)), mode="sit", seat_z=0.36)
    A["boss1"] = actor("boss", "boss", (T + 0.05, 5.2, 0), 0, 1.0, W((13.63, 15.5)))
    A["boss2"] = actor("boss2", "boss", (T, 5.2, 0), 0, 1.0, W((15.5, 20.6)))
    A["eng_t"] = actor("engT", "engineer", (T + 0.9, 3.0, 0), 20, 1.0, W((17.3, 20.6)))
    A["tycoon_car"] = actor("tycC", "tycoon_robe", (IX - 0.6, 0.9, 0.1), 0, 1.0, W((27.4, 28.53)))
    A["clerk"] = actor("clerk", "clerk", (TX, 4.8, 0.7), 0, 1.0, W((28.53, 31.37)))
    A["news1"] = actor("nw1", "conductor", (S_ + 0.5, 1.5, 0), 0, 1.0, W((31.37, 33.83)))
    A["news2"] = actor("nw2", "extra1", (S_ - 0.9, 3.2, 0), 15, 1.0, W((31.37, 33.83)))
    A["crowd1"] = actor("cr1", "extra2", (S_ + 0.6, 0.6, 0), 0, 1.0, W((33.83, 36.23)))
    A["crowd2"] = actor("cr2", "extra3", (S_ + 2.6, 1.5, 0), -10, 1.0, W((33.83, 36.23)))
    A["crowd3"] = actor("cr3", "extra1", (S_ + 4.2, 2.6, 0), -20, 1.0, W((33.83, 36.23)))
    A["boss3"] = actor("boss3", "boss", (G_ + 0.1, 1.2, 0), 0, 1.0, W((44.5, 48.13)))
    A["wk_hot"] = actor("wkH", "worker3", (DK - 1.4, 7.5, 0), 0, 1.0, W((48.13, 51.37)))
    A["sun"] = actor("sun", "tycoon_robe", (SUN_X, 48.0, 0), 0, 1.0, W((51.37, 54.53)), mode="sit", seat_z=0.36)
    A["eng_l"] = actor("engL", "engineer", (L_ + 0.2, 5.5, 0), 0, 1.0, W((54.53, 59.6)))
    A["boss4"] = actor("boss4", "boss", (L_ - 0.8, 7.0, 0), 0, 1.0, W((54.53, 59.6)))
    # facial acting (t, expression)
    expr(A["eng_saw"][2], [(0.0, "Neutral"), (2.0, "Happy")])
    expr(A["engineer_plank"][2], [(7.8, "Neutral"), (8.2, "Excited")])
    expr(A["tycoon_steps"][2], [(10.6, "Happy"), (11.2, "Excited")])
    expr(A["boss2"][2], [(15.5, "Irritated"), (17.0, "Excited"), (19.0, "Irritated")])
    expr(A["boss3"][2], [(44.5, "Happy"), (45.2, "Excited"), (47.0, "Happy")])
    expr(A["eng_l"][2], [(54.5, "Excited"), (57.9, "Happy")])
    expr(A["boss4"][2], [(54.5, "Happy"), (57.9, "Excited")])
    expr(A["sun"][2], [(51.4, "Happy")])
    expr(A["clerk"][2], [(28.5, "Neutral"), (29.5, "Happy")])
    # boss face turns purple at 17.0 (angry): keyed skin colour
    sk = bpy.data.materials.get("Skin_boss2")
    if sk:
        b = sk.node_tree.nodes["Principled BSDF"]
        for t, c in ((15.5, (0.98, 0.95, 0.87)), (16.9, (0.98, 0.95, 0.87)), (17.6, (0.55, 0.12, 0.75)), (20.6, (0.55, 0.12, 0.75))):
            for inp in ("Base Color", "Emission Color"):
                b.inputs[inp].default_value = (*c, 1)
                b.inputs[inp].keyframe_insert("default_value", frame=F(t))
    # held props: newspapers (31.4-33.8 s)
    for i, (x, y) in enumerate(((S_ + 0.5, 1.5), (S_ - 0.9, 3.2))):
        p = panel(f"Paper{i}", 0.55, 0.7, (x, y - 0.35, 1.15), m["news"], col, rot=(math.radians(90), 0, 0))
        rs.keyed_visible(p, 31.37, 33.83)
    cam = build_camera(sc)
    build_captions(sc, cam)
    setup_render(sc)
    sc.frame_start, sc.frame_end = 1, 1956
    return sc


def fs_off_frames():
    """frames with no character on screen (outlines are skipped there). Character shot windows from the cast above."""
    chars = [(0.0, 3.93), (7.83, 8.67), (10.6, 11.77), (11.77, 13.63), (13.63, 20.6), (27.4, 31.37), (31.37, 36.23), (44.5, 48.13), (48.13, 51.37), (51.37, 54.53), (54.53, 59.6)]
    on = set()
    for a, b in chars:
        on |= set(range(F(a), F(b) + 1))
    off = [f for f in range(1, F(WORD_END) + 1) if f not in on]
    out, s = [], None
    for f in off:
        if s is None:
            s = p = f
        elif f == p + 1:
            p = f
        else:
            out.append(f"{s}-{p}")
            s = p = f
    if s is not None:
        out.append(f"{s}-{p}")
    return ",".join(out)


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else (sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "rail65.blend"))
    sc = build_all()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("SAVED", out, "frames", sc.frame_end, "fs_off", fs_off_frames())
