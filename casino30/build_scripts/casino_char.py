"""Character: modelled meshes, armature with weighted skinning, face with shape keys, toon material."""
import bpy, bmesh, math
from mathutils import Vector, Euler, Matrix
import casino_scene as cs
from casino_scene import mat, link, coll, mesh_ob

O = Vector((cs.CHAR_X, cs.CHAR_Y, cs.STOOL_TOP))      # seat-top centre = rig origin
HEAD_C = Vector((0, 0, 0.93))
HEAD_R = (0.30, 0.27, 0.29)
TORSO_C = Vector((0, 0, 0.38))
TORSO_R = (0.19, 0.135, 0.40)

BONES = {  # name: (head, tail, parent, connected)
    "pelvis": ((0, 0, 0.02), (0, 0, 0.14), None, False),
    "spine": ((0, 0, 0.14), (0, 0, 0.40), "pelvis", True),
    "chest": ((0, 0, 0.40), (0, 0, 0.64), "spine", True),
    "neck": ((0, 0, 0.64), (0, 0, 0.70), "chest", True),
    "head": ((0, 0, 0.70), (0, 0, 1.20), "neck", True),
}
for s, n in ((1, "L"), (-1, "R")):
    BONES[f"upper_arm.{n}"] = ((s * 0.17, 0, 0.60), (s * 0.20, 0, 0.34), "chest", False)
    BONES[f"forearm.{n}"] = ((s * 0.20, 0, 0.34), (s * 0.20, -0.02, 0.09), f"upper_arm.{n}", True)
    BONES[f"hand.{n}"] = ((s * 0.20, -0.02, 0.09), (s * 0.20, -0.04, -0.01), f"forearm.{n}", True)
    BONES[f"thigh.{n}"] = ((s * 0.09, 0, 0.03), (s * 0.09, -0.38, 0.03), "pelvis", False)
    BONES[f"shin.{n}"] = ((s * 0.09, -0.38, 0.03), (s * 0.09, -0.40, -0.52), f"thigh.{n}", True)
    BONES[f"foot.{n}"] = ((s * 0.09, -0.40, -0.52), (s * 0.09, -0.49, -0.56), f"shin.{n}", True)


def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def new_ob(name, bm, m, col, weights, rig, smooth_shade=True):
    ob = mesh_ob(name, bm, O, col)
    ob.data.materials.append(m) if m is not None else None
    if smooth_shade:
        ob.data.shade_smooth()
    skin(ob, weights, rig)
    return ob


def skin(ob, weights_fn, rig):
    """weights_fn(local_co) -> {bone: weight}"""
    for b in BONES:
        ob.vertex_groups.new(name=b)
    for v in ob.data.vertices:
        for b, w in weights_fn(v.co).items():
            if w > 1e-4:
                ob.vertex_groups[b].add([v.index], w, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig


def w_head(co):
    return {"head": 1.0}


def w_torso(co):
    z = co.z
    wp = 1 - smooth((z - 0.08) / 0.2)
    wc = smooth((z - 0.34) / 0.22)
    return {"pelvis": wp, "spine": max(0.0, 1 - wp - wc), "chest": wc}


def ellipsoid(center, radii, seg=40, rings=20):
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0, calc_uvs=True)
    for v in bm.verts:
        v.co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2])) + Vector(center)
    return bm


def torso_decal(pts, off=0.004):
    bm = bmesh.new()
    vs = []
    for x, z in pts:
        t = 1 - (x / TORSO_R[0]) ** 2 - ((z - TORSO_C.z) / TORSO_R[2]) ** 2
        y = -TORSO_R[1] * math.sqrt(max(t, 0.0001)) - off
        vs.append(bm.verts.new((x, y, z)))
    bm.faces.new(vs)
    return bm


def tube(points, r_start, r_end, ring=10, per=7):
    """thin tube along a polyline; returns bm and arc-length param per vertex."""
    bm = bmesh.new()
    path = []
    for i in range(len(points) - 1):
        a, b = Vector(points[i]), Vector(points[i + 1])
        for k in range(per):
            path.append(a.lerp(b, k / per))
    path.append(Vector(points[-1]))
    n = len(path)
    rings = []
    for i, p in enumerate(path):
        d = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        up = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
        u = d.cross(up).normalized()
        w = d.cross(u).normalized()
        r = r_start + (r_end - r_start) * i / (n - 1)
        rings.append([bm.verts.new(p + (u * math.cos(2 * math.pi * k / ring) + w * math.sin(2 * math.pi * k / ring)) * r) for k in range(ring)])
    for i in range(n - 1):
        for k in range(ring):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % ring], rings[i + 1][(k + 1) % ring], rings[i + 1][k]))
    return bm


def chain_weights(points, names, blend=0.05):
    pts = [Vector(p) for p in points]
    seg = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    lens = [(b - a).length for a, b in seg]
    cum = [0]
    for l in lens:
        cum.append(cum[-1] + l)

    def fn(co):
        # project onto polyline for arc length
        best, bs = 1e9, 0
        for i, (a, b) in enumerate(seg):
            ab = b - a
            t = clamp01((co - a).dot(ab) / ab.length_squared)
            d = (a + ab * t - co).length
            if d < best:
                best, bs = d, cum[i] + t * lens[i]
        out = {n: 0.0 for n in names}
        for j in range(len(names)):
            lo = cum[j] - blend if j > 0 else -1e9
            hi = cum[j + 1] + blend if j < len(names) - 1 else 1e9
            wj = smooth((bs - lo) / (2 * blend)) if j > 0 else 1.0
            wn = 1 - smooth((bs - (cum[j + 1] - blend)) / (2 * blend)) if j < len(names) - 1 else 1.0
            out[names[j]] = wj * wn
        s = sum(out.values()) or 1
        return {k: v / s for k, v in out.items()}
    return fn


# ------------------------------------------------------------------ face
EYE_N, PUP_N, BROW_N, MOUTH_N = 20, 14, 6, 9
FACE_KEYS = {}


def P(**kw):
    base = dict(ex=0.095, ev=0.03, ew=0.040, eh=0.044, pr=0.020, pdx=0.0, pdy=0.0, lid=0.0,
                bl=dict(by=0.105, L=0.085, slope=0.0, curve=0.006, th=0.011),
                br=dict(by=0.105, L=0.085, slope=0.0, curve=0.006, th=0.011),
                mw=0.07, mv=-0.115, smile=0.008, skew=0.0, open=0.0, teeth=0.0, mth=0.008)
    base.update(kw)
    return base


EXPR = {
    "Neutral": P(),
    "Happy": P(ew=0.027, eh=0.032, pr=0.024, pdx=0.004, mw=0.11, smile=0.024, mth=0.011,
               bl=dict(by=0.11, L=0.0, slope=0, curve=0, th=0.0), br=dict(by=0.11, L=0.0, slope=0, curve=0, th=0.0)),
    "Excited": P(ew=0.064, eh=0.066, pr=0.021, pdx=-0.010, pdy=0.012, mw=0.17, mv=-0.105, smile=0.055, open=0.075, teeth=1.0, mth=0.012,
                 bl=dict(by=0.165, L=0.09, slope=-0.15, curve=0.02, th=0.012), br=dict(by=0.165, L=0.09, slope=-0.15, curve=0.02, th=0.012)),
    "Disappointed": P(ew=0.044, eh=0.036, pr=0.030, lid=0.5, mw=0.05, mv=-0.127, smile=-0.006, mth=0.009,
                      bl=dict(by=0.098, L=0.095, slope=0.38, curve=0.0, th=0.015), br=dict(by=0.098, L=0.095, slope=0.38, curve=0.0, th=0.015)),
    "Irritated": P(ew=0.044, eh=0.036, pr=0.030, pdx=0.006, lid=0.45, mw=0.045, mv=-0.13, smile=-0.012, skew=0.01, mth=0.009,
                   bl=dict(by=0.095, L=0.095, slope=0.30, curve=0.0, th=0.015), br=dict(by=0.145, L=0.095, slope=-0.10, curve=0.022, th=0.014)),
    "Sigh": P(ew=0.044, eh=0.012, pr=0.018, lid=0.0, mw=0.055, mv=-0.132, smile=-0.014, mth=0.009,
              bl=dict(by=0.125, L=0.09, slope=-0.12, curve=0.012, th=0.012), br=dict(by=0.125, L=0.09, slope=-0.12, curve=0.012, th=0.012)),
}


def proj(u, v, off):
    zc = HEAD_C.z
    t = 1 - (u / HEAD_R[0]) ** 2 - (v / HEAD_R[2]) ** 2
    y = -HEAD_R[1] * math.sqrt(max(t, 0.0001)) - off
    return Vector((u, y, zc + v))


def face_coords(p):
    out = []
    zc = 0.0
    top = p["ev"] + p["eh"] * (1 - 2 * p["lid"])
    bot = p["ev"] - p["eh"]
    for side in (-1, 1):
        ex = side * p["ex"]
        pts = [(ex, p["ev"])]
        for k in range(EYE_N):
            a = 2 * math.pi * k / EYE_N
            pts.append((ex + p["ew"] * math.cos(a), min(p["ev"] + p["eh"] * math.sin(a), top)))
        out += [proj(u, v, 0.003) for u, v in pts]
        px, pv = ex + p["pdx"] * side * -1 if False else ex + p["pdx"], p["ev"] + p["pdy"]
        pts = [(px, min(max(pv, bot), top))]
        for k in range(PUP_N):
            a = 2 * math.pi * k / PUP_N
            pts.append((px + p["pr"] * math.cos(a), min(max(pv + p["pr"] * math.sin(a), bot), top)))
        out += [proj(u, v, 0.0045) for u, v in pts]
    for side, key in ((-1, "bl"), (1, "br")):
        b = p[key]
        top_r, bot_r = [], []
        for i in range(BROW_N):
            t = i / (BROW_N - 1)
            x = side * (p["ex"] + (t - 0.5) * b["L"] + 0.0)
            v = b["by"] + b["slope"] * (t - 0.5) * b["L"] + b["curve"] * (1 - 4 * (t - 0.5) ** 2)
            # side=-1 (cam-left) has its inner end at larger x -> mirror so t=0 is the inner end
            if side == -1:
                x = -(p["ex"] - (t - 0.5) * b["L"])
            top_r.append((x, v + b["th"] / 2))
            bot_r.append((x, v - b["th"] / 2))
        out += [proj(u, v, 0.003) for u, v in top_r + bot_r]
    tops, bots, tt, tb = [], [], [], []
    for i in range(MOUTH_N):
        u = -p["mw"] / 2 + i * p["mw"] / (MOUTH_N - 1)
        q = 2 * u / p["mw"]
        vt = p["mv"] + p["smile"] * q * q + p["skew"] * q
        vb = vt - p["mth"] - p["open"] * max(1 - q * q, 0) ** 0.75
        tops.append((u, vt)); bots.append((u, vb))
        tt.append((u, vt - 0.003))
        tb.append((u, min(vt - 0.003, max(vb + 0.004, vt - 0.003 - p["teeth"] * 0.034 * max(1 - q * q, 0) ** 0.5))))
    out += [proj(u, v, 0.003) for u, v in tops + bots]
    out += [proj(u, v, 0.0042) for u, v in tt + tb]
    return out


def build_face(rig, col, m_sclera, m_pupil, m_brow, m_mouth, m_teeth):
    bm = bmesh.new()
    coords = face_coords(EXPR["Neutral"])
    vs = [bm.verts.new(c) for c in coords]
    i = 0
    matidx = []

    def add(face, mi):
        f = bm.faces.new([vs[k] for k in face])
        f.material_index = mi

    for side in range(2):
        n = EYE_N
        for k in range(n):
            add((i, i + 1 + k, i + 1 + (k + 1) % n), 0)
        i += n + 1
        n = PUP_N
        for k in range(n):
            add((i, i + 1 + k, i + 1 + (k + 1) % n), 1)
        i += n + 1
    for side in range(2):
        for k in range(BROW_N - 1):
            add((i + k, i + k + 1, i + BROW_N + k + 1, i + BROW_N + k), 2)
        i += 2 * BROW_N
    for k in range(MOUTH_N - 1):
        add((i + k, i + k + 1, i + MOUTH_N + k + 1, i + MOUTH_N + k), 3)
    i += 2 * MOUTH_N
    for k in range(MOUTH_N - 1):
        add((i + k, i + k + 1, i + MOUTH_N + k + 1, i + MOUTH_N + k), 4)
    ob = mesh_ob("Face", bm, O, col)
    for m in (m_sclera, m_pupil, m_brow, m_mouth, m_teeth):
        ob.data.materials.append(m)
    ob.data.shade_smooth()
    # shape keys: each expression stores the full face layout
    ob.shape_key_add(name="Basis")
    for name, p in EXPR.items():
        if name == "Neutral":
            continue
        sk = ob.shape_key_add(name=name, from_mix=False)
        for v, c in zip(sk.data, face_coords(p)):
            v.co = c
    skin(ob, w_head, rig)
    return ob


# ------------------------------------------------------------------ build
def build_character(origin=None, style="A"):
    """style 'A' = the original teal-jacket character; 'B' = red cap + sunglasses on the cap, beige hoodie, gold chain."""
    global O
    if origin is not None:
        O = Vector(origin)
    isB = style == "B"
    col = coll("Character")
    skin_m = mat("Skin", (0.98, 0.95, 0.87), rough=1.0, emit=(0.98, 0.95, 0.87), estr=0.55, spec=0.0)
    hair_m = mat("Hair", (0.02, 0.008, 0.006), rough=0.55, emit=(0.03, 0.012, 0.01), estr=0.1, spec=0.25)
    jacket_m = mat("Hoodie", (0.80, 0.72, 0.58), rough=0.9, emit=(0.80, 0.72, 0.58), estr=0.45, spec=0.05) if isB else \
        mat("Jacket", tex="jacket.png", rough=0.9, tex_emit=0.45, spec=0.05, tex_scale=(1.0, 0.75))
    lapel_m = mat("Lapel", (0.05, 0.38, 0.35), rough=0.9, emit=(0.05, 0.38, 0.35), estr=0.4, spec=0.05)
    shirt_m = mat("Shirt", (0.95, 0.93, 0.88), rough=1.0, emit=(0.95, 0.93, 0.88), estr=0.4, spec=0.0)
    tie_m = mat("Tie", (0.95, 0.30, 0.08), rough=0.7, emit=(0.95, 0.3, 0.08), estr=0.5, spec=0.1)
    badge_m = mat("Badge", (0.92, 0.92, 0.9), rough=0.6, emit=(0.9, 0.9, 0.88), estr=0.4)
    limb_m = mat("Limb", (0.15, 0.075, 0.06), rough=0.8, emit=(0.15, 0.075, 0.06), estr=0.35, spec=0.05)
    white = mat("EyeWhite", (1, 1, 1), rough=1.0, emit=(1, 1, 1), estr=0.7, spec=0.0)
    black = mat("Pupil", (0.02, 0.012, 0.012), rough=0.5, spec=0.2)
    brow_m = mat("Brow", (0.10, 0.05, 0.04), rough=0.8, emit=(0.1, 0.05, 0.04), estr=0.3)
    mouth_m = mat("Mouth", (0.28, 0.04, 0.05), rough=0.8, emit=(0.28, 0.04, 0.05), estr=0.2)
    teeth_m = mat("Teeth", (1, 1, 0.95), rough=0.8, emit=(1, 1, 0.95), estr=0.6)

    # armature
    arm = bpy.data.armatures.new("RigData")
    rig = bpy.data.objects.new("Rig", arm)
    rig.location = O
    link(rig, col)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t, par, con) in BONES.items():
        b = arm.edit_bones.new(n)
        b.head, b.tail = Vector(h), Vector(t)
        if par:
            b.parent = arm.edit_bones[par]
            b.use_connect = con
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True

    # torso (skinned), head, hair, decals
    new_ob("Torso", ellipsoid(TORSO_C, TORSO_R), jacket_m, col, w_torso, rig)
    if not isB:
        new_ob("Collar", torso_decal([(-0.085, 0.665), (0.085, 0.665), (0.0, 0.44)], 0.006), shirt_m, col, w_torso, rig, False)
        new_ob("LapelL", torso_decal([(0.012, 0.455), (0.095, 0.68), (0.165, 0.60), (0.085, 0.36)], 0.008), lapel_m, col, w_torso, rig, False)
        new_ob("LapelR", torso_decal([(-0.012, 0.455), (-0.095, 0.68), (-0.165, 0.60), (-0.085, 0.36)], 0.008), lapel_m, col, w_torso, rig, False)
        new_ob("Tie", torso_decal([(-0.022, 0.655), (0.022, 0.655), (0.032, 0.60), (0.058, 0.30), (0.0, 0.20), (-0.058, 0.30), (-0.032, 0.60)], 0.012), tie_m, col, w_torso, rig, False)
        new_ob("Badge", torso_decal([(0.045, 0.40), (0.105, 0.40), (0.105, 0.27), (0.045, 0.27)], 0.014), badge_m, col, w_torso, rig, False)
        new_ob("Lanyard", torso_decal([(0.03, 0.66), (0.045, 0.66), (0.085, 0.40), (0.07, 0.40)], 0.013), tie_m, col, w_torso, rig, False)
    new_ob("Head", ellipsoid(HEAD_C, HEAD_R, 48, 24), skin_m, col, w_head, rig)
    if not isB:
        new_ob("HairCap", ellipsoid((0.0, 0.05, 1.045), (0.325, 0.30, 0.25), 40, 20), hair_m, col, w_head, rig)
        for i, (c, r) in enumerate([((0.07, -0.205, 1.135), (0.17, 0.085, 0.075)), ((-0.10, -0.20, 1.12), (0.12, 0.075, 0.07)),
                                    ((0.20, -0.14, 1.11), (0.10, 0.09, 0.07))]):
            new_ob(f"Fringe{i}", ellipsoid(c, r, 20, 10), hair_m, col, w_head, rig)
        for i, (x, y, tilt, h) in enumerate([(0.06, -0.02, 28, 0.27), (-0.07, 0.02, -8, 0.20), (0.15, 0.04, 55, 0.20), (-0.17, 0.05, -35, 0.17)]):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=14, radius1=0.085, radius2=0.0, depth=h)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(tilt), 3, "Y"))
            for v in bm.verts:
                v.co += Vector((x, y, 1.20 + h / 2 - 0.02))
            new_ob(f"Tuft{i}", bm, hair_m, col, w_head, rig)
    else:
        cap_m = mat("CapRed", (0.85, 0.06, 0.05), rough=0.6, emit=(0.85, 0.06, 0.05), estr=0.45, spec=0.1)
        shade_m = mat("Shades", (0.02, 0.02, 0.025), rough=0.25, spec=0.6)
        gold_m = mat("GoldChain", (1.0, 0.72, 0.2), metallic=1.0, rough=0.25, emit=(1.0, 0.65, 0.15), estr=0.25)
        new_ob("HairBack", ellipsoid((0.0, 0.10, 1.00), (0.30, 0.26, 0.22), 32, 16), hair_m, col, w_head, rig)
        new_ob("Cap", ellipsoid((0.0, 0.0, 1.10), (0.325, 0.30, 0.215), 40, 20), cap_m, col, w_head, rig)
        new_ob("CapBrim", ellipsoid((0.0, -0.27, 1.065), (0.24, 0.20, 0.03), 32, 12), cap_m, col, w_head, rig)
        for i, sx in enumerate((-0.095, 0.095)):
            new_ob(f"ShadeLens{i}", ellipsoid((sx, -0.265, 1.12), (0.07, 0.022, 0.05), 20, 10), shade_m, col, w_head, rig)
        pts = []
        for k in range(15):
            x = -0.13 + 0.26 * k / 14
            z = 0.66 - 0.14 * (1 - (x / 0.13) ** 2)
            tq = 1 - (x / TORSO_R[0]) ** 2 - ((z - TORSO_C.z) / TORSO_R[2]) ** 2
            pts.append((x, -TORSO_R[1] * math.sqrt(max(tq, 0.0001)) - 0.012, z))
        new_ob("Chain", tube(pts, 0.011, 0.011, ring=8, per=2), gold_m, col, w_torso, rig, True)

    face = build_face(rig, col, white, black, brow_m, mouth_m, teeth_m)

    # limbs (skinned tubes) + hands + shoes
    for s, n in ((1, "L"), (-1, "R")):
        pts = [BONES[f"upper_arm.{n}"][0], BONES[f"forearm.{n}"][0], BONES[f"hand.{n}"][0]]
        new_ob(f"Arm.{n}", tube(pts, 0.019, 0.017, per=8), limb_m, col, chain_weights(pts, [f"upper_arm.{n}", f"forearm.{n}", f"hand.{n}"], 0.045), rig)
        hpos = Vector(BONES[f"hand.{n}"][0]) + Vector((0, -0.01, -0.02))
        bm = ellipsoid(hpos, (0.034, 0.03, 0.04), 14, 8)
        new_ob(f"Hand.{n}", bm, limb_m, col, lambda co, n=n: {f"hand.{n}": 1.0}, rig)
        lp = [BONES[f"thigh.{n}"][0], BONES[f"shin.{n}"][0], BONES[f"foot.{n}"][0]]
        new_ob(f"Leg.{n}", tube(lp, 0.024, 0.02, per=8), limb_m, col, chain_weights(lp, [f"thigh.{n}", f"shin.{n}", f"foot.{n}"], 0.05), rig)
        fp = Vector(BONES[f"foot.{n}"][0]) + Vector((0, -0.04, -0.015))
        new_ob(f"Shoe.{n}", ellipsoid(fp, (0.045, 0.085, 0.035), 14, 8), limb_m, col, lambda co, n=n: {f"foot.{n}": 1.0}, rig)
    return rig, face


# ------------------------------------------------------------------ animation
def fr(t):
    return int(round(1 + t * cs.FPS))


def key_pose(rig, bone, eul, frame):
    pb = rig.pose.bones[bone]
    pb.rotation_mode = "QUATERNION"
    R = Euler([math.radians(a) for a in eul], "XYZ").to_quaternion()
    rest = rig.data.bones[bone].matrix_local.to_quaternion()
    pb.rotation_quaternion = rest.inverted() @ R @ rest
    pb.keyframe_insert("rotation_quaternion", frame=frame)


def animate_character(rig, face):
    """All angles are degrees about armature axes: X = tip forward(+), Y = lean toward character's left(+), Z = turn."""
    def pose(t, **bones):
        for b, e in bones.items():
            key_pose(rig, b.replace("_L", ".L").replace("_R", ".R"), e, fr(t))

    # --- body acting beats (t in seconds)
    sway = lambda t, a: dict(spine=(a * 0.5, a, 0), chest=(0, -a * 0.6, a))
    arm_fold = dict(upper_arm_L=(-34, 10, 0), forearm_L=(-80, 0, -62), upper_arm_R=(-34, -10, 0), forearm_R=(-80, 0, 62))
    arm_rest = dict(upper_arm_L=(0, 4, 0), forearm_L=(-10, 0, 0), upper_arm_R=(0, -4, 0), forearm_R=(-10, 0, 0))
    
    # 0.0  neutral, off screen
    pose(0.0, head=(0, 0, 0), spine=(0, 0, 0), chest=(0, 0, 0), pelvis=(0, 0, 0), **arm_rest,
         thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(0, 0, 0), shin_R=(0, 0, 0))
    # 1.0 relaxed, small smile, looking toward the machine
    pose(1.0, head=(-2, 0, -12), spine=(-2, 2, 0), chest=(0, -1, 3), **arm_rest,
         thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(0, 0, 0), shin_R=(0, 0, 0))
    pose(1.5, head=(-3, 3, -8), spine=(-3, 3, 0), chest=(0, -2, 2), **arm_rest,
         thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(4, 0, 0), shin_R=(-3, 0, 0))
    # 1.75-2.4 excited: hands up at chest, bouncing
    for i, t in enumerate([1.75, 1.92, 2.08, 2.24, 2.40]):
        up = 1 if i % 2 == 0 else -1
        pose(t, head=(4 + up * 5, up * 4, -4 + up * 3), spine=(-4 + up * 3, up * 2, 0), chest=(up * 2, 0, up * 3), **arm_fold,
             thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(10 * up, 0, 0), shin_R=(-10 * up, 0, 0))
    # 2.6 deflate: head back toward camera, arms drop, shoulders sink
    pose(2.62, head=(2, -2, 4), spine=(6, 0, 0), chest=(4, 0, 0), **dict(
        upper_arm_L=(-14, 6, 0), forearm_L=(-30, 0, -10), upper_arm_R=(-14, -6, 0), forearm_R=(-30, 0, 10)),
        thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(2, 0, 0), shin_R=(-2, 0, 0))
    pose(3.1, head=(4, -4, 8), spine=(5, -1, 0), chest=(3, -1, 0), **dict(
        upper_arm_L=(-10, 6, 0), forearm_L=(-24, 4, 0), upper_arm_R=(-18, -6, 0), forearm_R=(-40, -6, 0)),
        thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(3, 0, 0), shin_R=(-2, 0, 0))
    # 3.6 irritated, head tilt, one brow up
    pose(3.6, head=(2, -9, 10), spine=(4, -2, 0), chest=(2, -2, 0), **dict(
        upper_arm_L=(-8, 6, 0), forearm_L=(-20, 4, 0), upper_arm_R=(-40, -8, 0), forearm_R=(-85, 0, 30)),
        thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(5, 0, 0), shin_R=(-4, 0, 0))
    # 4.3 hand to chin, head tipping back, sigh
    pose(4.3, head=(-8, -12, 6), spine=(2, -2, 0), chest=(0, -2, 0), **dict(
        upper_arm_L=(-8, 6, 0), forearm_L=(-20, 4, 0), upper_arm_R=(-52, -8, 0), forearm_R=(-122, 0, 38)),
        thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(4, 0, 0), shin_R=(-3, 0, 0))
    pose(5.0, head=(-10, -13, 7), spine=(2, -2, 0), chest=(0, -2, 0), **dict(
        upper_arm_L=(-8, 6, 0), forearm_L=(-20, 4, 0), upper_arm_R=(-54, -8, 0), forearm_R=(-124, 0, 40)),
        thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(4, 0, 0), shin_R=(-3, 0, 0))

    # --- 5-30 s extension (reference beats; deadpan watching, then looking at the friend, smirk, gritted teeth, sigh)
    rest_legs = dict(thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(4, 0, 0), shin_R=(-3, 0, 0))
    chin = dict(upper_arm_L=(-8, 6, 0), forearm_L=(-20, 4, 0), upper_arm_R=(-54, -8, 0), forearm_R=(-124, 0, 40))
    pose(5.6, head=(-8, -11, 6), spine=(2, -2, 0), chest=(0, -2, 0), **chin, **rest_legs)
    pose(6.8, head=(-5, -9, 4), spine=(2, -2, 0), chest=(0, -2, 0), **chin, **rest_legs)
    pose(7.6, head=(0, -4, 2), spine=(2, -1, 0), chest=(0, -1, 0), **arm_rest, **rest_legs)
    pose(8.4, head=(0, 0, 0), spine=(1, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(9.2, head=(0, -3, 13), spine=(2, 0, 3), chest=(0, 0, 2), **arm_rest, **rest_legs)       # turns toward the friend (camera-left)
    pose(10.6, head=(1, -2, 11), spine=(2, 0, 3), chest=(0, 0, 2), **arm_rest, **rest_legs)
    pose(11.6, head=(0, 0, 0), spine=(1, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(13.9, head=(0, 0, 8), spine=(1, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(14.8, head=(-3, 3, 10), spine=(1, 1, 0), chest=(0, 0, 2), **arm_rest, **rest_legs)       # smirk, watching the machine
    pose(15.8, head=(3, -4, 9), spine=(2, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(16.5, head=(4, -2, 0), spine=(3, 0, 0), chest=(0, 0, 0), **dict(
        upper_arm_L=(-20, 8, 0), forearm_L=(-60, 0, -30), upper_arm_R=(-20, -8, 0), forearm_R=(-60, 0, 30)), **rest_legs)   # gritted teeth, fists up
    pose(17.5, head=(5, 0, -3), spine=(3, 0, 0), chest=(0, 0, 0), **dict(
        upper_arm_L=(-20, 8, 0), forearm_L=(-60, 0, -30), upper_arm_R=(-20, -8, 0), forearm_R=(-60, 0, 30)), **rest_legs)
    pose(18.5, head=(0, 0, 0), spine=(1, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(25.8, head=(0, 0, 0), spine=(1, 0, 0), chest=(0, 0, 0), **arm_rest, **rest_legs)
    pose(26.5, head=(5, -7, 9), spine=(3, -2, 0), chest=(2, -1, 0), **arm_rest, **rest_legs)
    pose(28.0, head=(7, -9, 6), spine=(3, -2, 0), chest=(2, -1, 0), **arm_rest, **rest_legs)
    pose(30.0, head=(8, -10, 4), spine=(3, -2, 0), chest=(2, -1, 0), **arm_rest, **rest_legs)

    # --- face: shape key weights (cross-fades)
    keys = face.data.shape_keys.key_blocks
    wp = {
        "Happy": [(0.9, 0), (1.05, 1), (1.55, 1), (1.78, 0), (13.8, 0), (14.1, 1), (15.0, 1), (15.3, 0)],
        "Excited": [(1.5, 0), (1.76, 1), (2.45, 1), (2.62, 0), (16.4, 0), (16.6, 0.55), (17.4, 0.55), (17.7, 0)],
        "Disappointed": [(2.4, 0), (2.62, 1), (3.05, 1), (3.35, 0), (25.9, 0), (26.2, 0.8), (27.8, 0.8), (28.1, 0)],
        "Irritated": [(3.0, 0), (3.35, 1), (4.05, 1), (4.35, 0), (8.3, 0), (8.7, 1), (11.6, 1), (12.0, 0), (15.2, 0), (15.5, 1), (16.3, 1), (16.5, 0.8),
                      (17.5, 0.8), (17.9, 0), (28.2, 0), (28.6, 1), (30.0, 1)],
        "Sigh": [(4.0, 0), (4.4, 1), (5.0, 1), (7.4, 1), (7.9, 0), (25.8, 0), (26.1, 1), (28.0, 1), (28.4, 0)],
    }
    for name, pts in wp.items():
        for t, v in pts:
            keys[name].value = v
            keys[name].keyframe_insert("value", frame=fr(t))
    # the neutral face before 0.9 s is the basis; keys start at 0


def animate_friend(rig, face, t_in=8.4, t_out=11.6):
    """Friend (style B): visible only t_in..t_out. Relaxed body, grin, wink, head tilts."""
    def pose(t, **bones):
        for b, e in bones.items():
            key_pose(rig, b.replace("_L", ".L").replace("_R", ".R"), e, fr(t))
    leg = dict(thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(4, 0, 0), shin_R=(-3, 0, 0))
    arm_rest = dict(upper_arm_L=(0, 4, 0), forearm_L=(-10, 0, 0), upper_arm_R=(0, -4, 0), forearm_R=(-10, 0, 0))
    pose(t_in - 0.4, head=(0, 0, 0), spine=(0, 0, 0), chest=(0, 0, 0), **arm_rest, **leg)
    pose(t_in + 0.5, head=(-2, 4, -9), spine=(-2, 2, 0), chest=(0, 0, -3), **arm_rest, **leg)       # leans toward A (camera-right)
    pose(9.6, head=(-3, 5, -10), spine=(-3, 3, 0), chest=(0, 0, -3), **dict(arm_rest, forearm_R=(-60, 0, 20)), **leg)
    pose(10.4, head=(-2, 3, -9), spine=(-2, 2, 0), chest=(0, 0, -3), **dict(arm_rest, forearm_R=(-50, 0, 15)), **leg)
    pose(t_out, head=(0, 0, -6), spine=(0, 0, 0), chest=(0, 0, 0), **arm_rest, **leg)
    keys = face.data.shape_keys.key_blocks
    wpB = {"Happy": [(t_in - 0.3, 0), (t_in + 0.1, 0.6), (9.7, 0.6), (9.9, 0), (10.6, 0), (10.8, 1), (11.4, 1), (t_out, 0)],
           "Excited": [(9.0, 0), (9.2, 0.8), (9.9, 0.8), (10.1, 0)]}
    for name, pts in wpB.items():
        for t, v in pts:
            keys[name].value = v
            keys[name].keyframe_insert("value", frame=fr(t))
