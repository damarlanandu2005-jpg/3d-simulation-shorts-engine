"""rail_chars.py - standing cartoon characters (same rig/face as the casino kit) with costumes for the railroad video.
Every character is a hierarchy: Root empty (move/rotate this) -> rig + skinned meshes. Built at the origin, then placed."""
import bpy, bmesh, math
from mathutils import Vector, Matrix
import casino_scene as cs
import casino_char as ch
from casino_scene import mat, link, coll, mesh_ob

# ---- standing legs (the casino rig sits). Hips at z=0.02, feet at z=-0.62.
for s, n in ((1, "L"), (-1, "R")):
    ch.BONES[f"thigh.{n}"] = ((s * 0.09, 0, 0.03), (s * 0.09, 0.0, -0.22), "pelvis", False)
    ch.BONES[f"shin.{n}"] = ((s * 0.09, 0.0, -0.22), (s * 0.09, 0.0, -0.42), f"thigh.{n}", True)
    ch.BONES[f"foot.{n}"] = ((s * 0.09, 0.0, -0.42), (s * 0.09, -0.08, -0.46), f"shin.{n}", True)
FOOT_DROP = 0.48            # root z = ground + FOOT_DROP

SKIN = (0.98, 0.95, 0.87)

COSTUMES = {
    "engineer": dict(jacket=(0.10, 0.55, 0.50), shirt=(0.95, 0.93, 0.88), neck=(0.85, 0.12, 0.10), hat="cap_stripe", hair=(0.35, 0.20, 0.10), limb=(0.10, 0.07, 0.06), tex="jacket_teal.png"),
    "boss": dict(jacket=(0.95, 0.72, 0.10), shirt=(0.95, 0.93, 0.88), hat="bowler", hat_col=(0.04, 0.04, 0.05), cane=True, chain=True, hair=(0.25, 0.25, 0.28), limb=(0.08, 0.06, 0.05)),
    "tycoon": dict(jacket=(0.04, 0.04, 0.05), shirt=(0.97, 0.97, 0.97), bow=(0.85, 0.08, 0.08), hat="tophat", hat_col=(0.04, 0.04, 0.05), hair=(0.2, 0.2, 0.2), limb=(0.05, 0.05, 0.06)),
    "tycoon_robe": dict(jacket=(0.85, 0.65, 0.12), shirt=(0.97, 0.97, 0.97), hat="tophat", hat_col=(0.04, 0.04, 0.05), hair=(0.2, 0.2, 0.2), limb=(0.05, 0.05, 0.06), tex="stripe_chair.png"),
    "worker1": dict(jacket=(0.30, 0.38, 0.25), shirt=(0.9, 0.9, 0.85), hat="flatcap", hat_col=(0.25, 0.28, 0.2), hair=(0.3, 0.2, 0.1), limb=(0.10, 0.07, 0.06)),
    "worker2": dict(jacket=(0.35, 0.55, 0.30), shirt=(0.9, 0.9, 0.85), hat="flatcap", hat_col=(0.4, 0.3, 0.2), hair=(0.3, 0.2, 0.1), limb=(0.10, 0.07, 0.06)),
    "worker3": dict(jacket=(0.55, 0.45, 0.30), shirt=(0.9, 0.9, 0.85), hat="bowler", hat_col=(0.3, 0.28, 0.25), hair=(0.55, 0.55, 0.55), limb=(0.10, 0.07, 0.06), beard=True),
    "worker4": dict(jacket=(0.10, 0.50, 0.47), shirt=(0.9, 0.9, 0.85), hat="cap_stripe", hair=(0.3, 0.2, 0.1), limb=(0.10, 0.07, 0.06), neck=(0.85, 0.12, 0.10)),
    "conductor": dict(jacket=(0.05, 0.10, 0.30), shirt=(0.95, 0.95, 0.95), hat="peaked", hat_col=(0.05, 0.10, 0.30), buttons=True, hair=(0.3, 0.2, 0.1), limb=(0.05, 0.05, 0.08)),
    "clerk": dict(jacket=(0.35, 0.22, 0.12), shirt=(0.95, 0.95, 0.9), hat="bowler", hat_col=(0.42, 0.42, 0.45), glasses=True, hair=(0.2, 0.15, 0.1), limb=(0.10, 0.07, 0.06)),
    "extra1": dict(jacket=(0.45, 0.30, 0.20), shirt=(0.9, 0.9, 0.85), hat="bowler", hat_col=(0.35, 0.3, 0.28), hair=(0.3, 0.2, 0.1), limb=(0.10, 0.07, 0.06)),
    "extra2": dict(jacket=(0.55, 0.25, 0.45), shirt=(0.9, 0.9, 0.85), hat="none", hair=(0.2, 0.1, 0.1), limb=(0.10, 0.07, 0.06)),
    "extra3": dict(jacket=(0.65, 0.5, 0.2), shirt=(0.9, 0.9, 0.85), hat="flatcap", hat_col=(0.3, 0.3, 0.35), hair=(0.3, 0.2, 0.1), limb=(0.10, 0.07, 0.06)),
}


def cyl_bm(r, h, z, y=0.0, seg=28, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    for v in bm.verts:
        v.co += Vector((0, y, z))
    return bm


def flat(c, e=0.45, rough=0.85, spec=0.05, name=None):
    return mat(name or f"RC_{c[0]:.2f}_{c[1]:.2f}_{c[2]:.2f}", c, rough=rough, emit=c, estr=e, spec=spec)


SKIP_OUTLINE = ("eye", "brow", "mouth", "teeth", "lid", "pupil", "face", "collar", "kerch", "bow", "button", "glass", "chain", "band", "rig_")


def add_outline(objs, thick=0.014):
    """inverted-hull outline: a second material slot + Solidify (flipped normals, back-face culled) = cheap cartoon ink in Eevee, no Freestyle"""
    om = mat("InkOutline", (0.035, 0.012, 0.010), rough=1.0, spec=0.0)
    om.use_backface_culling = True
    for o in objs:
        if o.type != "MESH" or any(k in o.name.lower() for k in SKIP_OUTLINE):
            continue
        if not o.data.materials:
            continue
        o.data.materials.append(om)
        md = o.modifiers.new("Ink", "SOLIDIFY")
        md.thickness, md.offset, md.use_flip_normals = thick, 1.0, True
        md.material_offset = len(o.data.materials) - 1
        md.use_quality_normals = True


def build_rail_char(name, costume, with_hat=True):
    """returns (root, rig, face, objs)"""
    cfg = COSTUMES[costume]
    ch.O = Vector((0, 0, 0))
    col = coll("Character")
    before = set(bpy.data.objects)
    skin_m = mat(f"Skin_{name}", SKIN, rough=1.0, emit=SKIN, estr=0.55, spec=0.0)
    hair_m = flat(cfg.get("hair", (0.1, 0.05, 0.03)), 0.25, name=f"Hair_{name}")
    jacket_m = mat(f"Jacket_{costume}", cfg["jacket"], rough=0.9, emit=cfg["jacket"], estr=0.45, spec=0.05, tex=cfg.get("tex"), tex_emit=0.5 if cfg.get("tex") else 0.0, tex_scale=(1.0, 1.0) if cfg.get("tex") else None)
    shirt_m = flat(cfg["shirt"], 0.4, name=f"Shirt_{costume}")
    limb_m = flat(cfg["limb"], 0.35, name=f"Limb_{costume}")
    white = mat("EyeWhite", (1, 1, 1), rough=1.0, emit=(1, 1, 1), estr=0.7, spec=0.0)
    black = mat("Pupil", (0.02, 0.012, 0.012), rough=0.5, spec=0.2)
    brow_m = mat("Brow", (0.10, 0.05, 0.04), rough=0.8, emit=(0.1, 0.05, 0.04), estr=0.3)
    mouth_m = mat("Mouth", (0.28, 0.04, 0.05), rough=0.8, emit=(0.28, 0.04, 0.05), estr=0.2)
    teeth_m = mat("Teeth", (1, 1, 0.95), rough=0.8, emit=(1, 1, 0.95), estr=0.6)
    gold = mat("RC_Gold", (1.0, 0.72, 0.2), metallic=1.0, rough=0.25, emit=(1.0, 0.65, 0.15), estr=0.25)

    arm = bpy.data.armatures.new(f"RigData_{name}")
    rig = bpy.data.objects.new(f"Rig_{name}", arm)
    link(rig, col)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t, par, con) in ch.BONES.items():
        b = arm.edit_bones.new(n)
        b.head, b.tail = Vector(h), Vector(t)
        if par:
            b.parent = arm.edit_bones[par]
            b.use_connect = con
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = False

    N = lambda nm, bm, m_, w, sm=True: ch.new_ob(f"{name}_{nm}", bm, m_, col, w, rig, sm)
    N("Torso", ch.ellipsoid(ch.TORSO_C, ch.TORSO_R), jacket_m, ch.w_torso)
    N("Collar", ch.torso_decal([(-0.085, 0.665), (0.085, 0.665), (0.0, 0.44)], 0.006), shirt_m, ch.w_torso, False)
    if cfg.get("neck"):
        N("Kerchief", ch.torso_decal([(-0.10, 0.66), (0.10, 0.66), (0.0, 0.50)], 0.012), flat(cfg["neck"], 0.5, name=f"Kerch_{name}"), ch.w_torso, False)
    if cfg.get("bow"):
        N("Bow", ch.ellipsoid((0, -0.12, 0.64), (0.07, 0.03, 0.03), 14, 8), flat(cfg["bow"], 0.5, name=f"Bow_{name}"), ch.w_torso)
    if cfg.get("chain"):
        pts = [(-0.10 + 0.20 * k / 10, -0.13, 0.50 - 0.04 * math.sin(math.pi * k / 10)) for k in range(11)]
        N("WatchChain", ch.tube(pts, 0.008, 0.008, ring=6, per=2), gold, ch.w_torso, True)
    if cfg.get("buttons"):
        for i, z in enumerate((0.56, 0.44, 0.32)):
            N(f"Button{i}", ch.ellipsoid((0.0, -0.138, z), (0.022, 0.012, 0.022), 10, 6), gold, ch.w_torso)
    N("Head", ch.ellipsoid(ch.HEAD_C, ch.HEAD_R, 48, 24), skin_m, ch.w_head)
    # hair tufts so hatless heads read as characters
    for i, (x, y, z, r) in enumerate([(-0.27, 0.04, 0.95, (0.05, 0.07, 0.09)), (0.27, 0.04, 0.95, (0.05, 0.07, 0.09))]):
        N(f"Hair{i}", ch.ellipsoid((x, y, z), r, 12, 8), hair_m, ch.w_head)
    if cfg["hat"] == "none":
        N("HairTop", ch.ellipsoid((0.0, 0.05, 1.12), (0.30, 0.26, 0.17), 28, 14), hair_m, ch.w_head)
    hat = cfg["hat"] if with_hat else "none"
    hc = cfg.get("hat_col", (0.1, 0.1, 0.1))
    hat_m = flat(hc, 0.4, name=f"Hat_{name}")
    if hat == "cap_stripe":
        cap_m = mat("CapStripe", (1, 1, 1), tex="stripe_cap.png", rough=0.8, tex_emit=0.6, tex_scale=(1.0, 1.0))
        N("Cap", ch.ellipsoid((0.0, 0.0, 1.11), (0.325, 0.30, 0.17), 40, 20), cap_m, ch.w_head)
        N("CapBrim", ch.ellipsoid((0.0, -0.25, 1.06), (0.20, 0.16, 0.025), 24, 10), flat((0.15, 0.18, 0.35), 0.4, name="CapBrimC"), ch.w_head)
    elif hat == "bowler":
        N("Bowler", ch.ellipsoid((0.0, 0.0, 1.17), (0.24, 0.22, 0.17), 32, 16), hat_m, ch.w_head)
        N("BowlerBrim", ch.ellipsoid((0.0, -0.02, 1.07), (0.36, 0.33, 0.025), 36, 10), hat_m, ch.w_head)
    elif hat == "tophat":
        N("TopCyl", cyl_bm(0.20, 0.34, 1.34, 0.0, 28), hat_m, ch.w_head)
        N("TopBrim", ch.ellipsoid((0.0, 0.0, 1.17), (0.33, 0.31, 0.022), 36, 10), hat_m, ch.w_head)
        N("TopBand", cyl_bm(0.205, 0.07, 1.22, 0.0, 28), flat((0.85, 0.1, 0.1), 0.4, name="TopBand"), ch.w_head)
    elif hat == "flatcap":
        N("Flat", ch.ellipsoid((0.0, 0.0, 1.12), (0.31, 0.29, 0.12), 32, 14), hat_m, ch.w_head)
        N("FlatBrim", ch.ellipsoid((0.0, -0.24, 1.07), (0.18, 0.14, 0.02), 20, 8), hat_m, ch.w_head)
    elif hat == "peaked":
        N("PeakBody", cyl_bm(0.27, 0.16, 1.17, 0.0, 28, r2=0.29), hat_m, ch.w_head)
        N("PeakBand", cyl_bm(0.272, 0.04, 1.11, 0.0, 28, r2=0.274), gold, ch.w_head)
        N("PeakVisor", ch.ellipsoid((0.0, -0.25, 1.10), (0.20, 0.13, 0.018), 20, 8), flat((0.02, 0.02, 0.03), 0.3, name="Visor"), ch.w_head)
    if cfg.get("glasses"):
        gm = flat((0.05, 0.05, 0.05), 0.2, name="Glasses")
        for i, sx in enumerate((-0.095, 0.095)):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.064, radius2=0.064, depth=0.012)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
            for v in bm.verts:
                v.co += Vector((sx, -0.275, 0.96))
            N(f"Glass{i}", bm, gm, ch.w_head)
    if cfg.get("beard"):
        N("Beard", ch.ellipsoid((0.0, -0.17, 0.72), (0.17, 0.10, 0.13), 20, 10), hair_m, ch.w_head)
    face = ch.build_face(rig, col, white, black, brow_m, mouth_m, teeth_m)
    # limbs + hands + shoes
    for s, n in ((1, "L"), (-1, "R")):
        pts = [ch.BONES[f"upper_arm.{n}"][0], ch.BONES[f"forearm.{n}"][0], ch.BONES[f"hand.{n}"][0]]
        ch.new_ob(f"{name}_Arm.{n}", ch.tube(pts, 0.034, 0.030, per=8), limb_m, col, ch.chain_weights(pts, [f"upper_arm.{n}", f"forearm.{n}", f"hand.{n}"], 0.045), rig)
        hpos = Vector(ch.BONES[f"hand.{n}"][0]) + Vector((0, -0.01, -0.02))
        ch.new_ob(f"{name}_Hand.{n}", ch.ellipsoid(hpos, (0.05, 0.045, 0.055), 14, 8), skin_m, col, lambda co, n=n: {f"hand.{n}": 1.0}, rig)
        lp = [ch.BONES[f"thigh.{n}"][0], ch.BONES[f"shin.{n}"][0], ch.BONES[f"foot.{n}"][0]]
        ch.new_ob(f"{name}_Leg.{n}", ch.tube(lp, 0.052, 0.046, per=8), limb_m, col, ch.chain_weights(lp, [f"thigh.{n}", f"shin.{n}", f"foot.{n}"], 0.05), rig)
        fp = Vector(ch.BONES[f"foot.{n}"][0]) + Vector((0, -0.05, -0.02))
        ch.new_ob(f"{name}_Shoe.{n}", ch.ellipsoid(fp, (0.07, 0.115, 0.05), 14, 8), flat((0.05, 0.04, 0.04), 0.2, name="Shoe"), col, lambda co, n=n: {f"foot.{n}": 1.0}, rig)
    if cfg.get("cane"):
        hp = Vector(ch.BONES["hand.R"][0]) + Vector((0, -0.04, 0.02))
        cp = [hp + Vector((0.0, 0.0, 0.10)), hp + Vector((0, 0.0, -0.20)), hp + Vector((0, 0.0, -0.60)), hp + Vector((0, 0.0, -0.80))]
        ch.new_ob(f"{name}_Cane", ch.tube(cp, 0.014, 0.014, per=2, ring=6), flat((0.30, 0.18, 0.08), 0.3, name="Cane"), col, lambda co: {"hand.R": 1.0}, rig)
        ch.new_ob(f"{name}_CaneKnob", ch.ellipsoid(hp + Vector((0, 0, 0.12)), (0.035, 0.035, 0.035), 10, 6), gold, col, lambda co: {"hand.R": 1.0}, rig)
    objs = list(set(bpy.data.objects) - before)
    add_outline(objs)
    root = bpy.data.objects.new(f"Root_{name}", None)
    link(root, col)
    for o in objs:
        o.parent = root
    for o in objs:                         # children keep their local (origin-based) transforms
        o.matrix_parent_inverse = Matrix.Identity(4)
    return root, rig, face, objs


def place(root, loc, yaw_deg=0.0, scale=1.0):
    """loc = ground position of the feet; yaw 0 faces -Y (towards the usual camera)"""
    root.location = (loc[0], loc[1], loc[2] + FOOT_DROP * scale)
    root.rotation_euler = (0, 0, math.radians(yaw_deg))
    root.scale = (scale, scale, scale)


def fr(t):
    return int(round(1 + t * cs.FPS))


def pose(rig, t, **bones):
    """degrees about armature axes (X = tip forward... see casino_char.key_pose); keys with bezier"""
    for b, e in bones.items():
        ch.key_pose(rig, b.replace("_L", ".L").replace("_R", ".R"), e, fr(t))


REST_ARMS = dict(upper_arm_L=(0, 4, 0), forearm_L=(-10, 0, 0), upper_arm_R=(0, -4, 0), forearm_R=(-10, 0, 0))
STAND = dict(thigh_L=(0, 0, 0), thigh_R=(0, 0, 0), shin_L=(0, 0, 0), shin_R=(0, 0, 0))


def face_keys(face, spec):
    """spec = {key_name: [(t, value), ...]}"""
    keys = face.data.shape_keys.key_blocks
    for name, pts in spec.items():
        for t, v in pts:
            keys[name].value = v
            keys[name].keyframe_insert("value", frame=fr(t))


def idle(rig, t0, t1, amp=1.0, arms=None, step=0.9, look=0.0, legs=None):
    """gentle breathing/sway keys between t0 and t1"""
    arms = arms or REST_ARMS
    legs = legs or STAND
    k, t = 0, t0
    while t <= t1 + 1e-6:
        a = amp * (1 if k % 2 == 0 else -1)
        pose(rig, t, head=(1.5 * a, 2.0 * a, look + 2.0 * a), spine=(1.0 * a, 0.8 * a, 0), chest=(0, -0.6 * a, 0.8 * a), pelvis=(0, 0, 0), **arms, **legs)
        t += step
        k += 1


def sit_dangling(rig, t0, t1, step=0.8, amp=1.0):
    """seated on a girder: thighs forward (-Y), shins hanging, small swing"""
    k, t = 0, t0
    while t <= t1 + 1e-6:
        sw = amp * (6 if k % 2 == 0 else -6)
        pose(rig, t, head=(0, 0, 3 * (1 if k % 2 == 0 else -1)), spine=(0, 0, 0), chest=(0, 0, 0), pelvis=(0, 0, 0), **REST_ARMS,
             thigh_L=(-88, 0, 0), thigh_R=(-88, 0, 0), shin_L=(88 + sw, 0, 0), shin_R=(88 - sw, 0, 0))
        t += step
        k += 1
