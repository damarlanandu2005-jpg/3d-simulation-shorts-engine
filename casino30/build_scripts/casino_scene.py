"""casino_scene.py - builds the casino scene (now 30 s, F_END = 900) in Blender (bpy). Run: python casino_scene.py
Everything is real Blender data: meshes, modifiers, materials, armature, shape keys, keyframes, Freestyle outline."""
import bpy, bmesh, math, os, random, sys
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "tex")
FPS, F_END = 30, 900                    # 30 s video
STOOL_TOP = 0.62
CHAR_X, CHAR_Y = -0.30, -0.52          # character seat position


# ------------------------------------------------------------------ helpers


def fcurves_of(idb):
    """All F-curves of an ID's action; works for Blender 4.x (action.fcurves) and 5.x (layers/strips/channelbags)."""
    ad = getattr(idb, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, F_END
    sc.render.fps = FPS
    return sc


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def link(ob, col=None):
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def image(name):
    return bpy.data.images.load(os.path.join(TEX, name), check_existing=True)


def mat(name, color=(0.8, 0.8, 0.8), metallic=0.0, rough=0.5, emit=None, estr=0.0, coat=0.0,
        tex=None, tex_emit=0.0, tex_scale=None, spec=0.5, alpha=1.0, bump_ribs=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Specular IOR Level"].default_value = spec
    bsdf.inputs["Alpha"].default_value = alpha
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit[:3], 1)
        bsdf.inputs["Emission Strength"].default_value = estr
    if tex:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = image(tex)
        t.interpolation = "Smart" if False else "Linear"
        src = t.outputs["Color"]
        if tex_scale:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (tex_scale[0], tex_scale[1], 1)
            nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        nt.links.new(src, bsdf.inputs["Base Color"])
        if tex_emit > 0:
            nt.links.new(src, bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = tex_emit
    if bump_ribs:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        wv = nt.nodes.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = "Z" if False else "X"
        wv.inputs["Scale"].default_value = bump_ribs
        wv.inputs["Distortion"].default_value = 0.0
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = 0.8
        bp.inputs["Distance"].default_value = 0.02
        nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
        nt.links.new(wv.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def finish(ob, m, bevel=0.0, seg=2, smooth=True):
    me = ob.data
    if m is not None:
        me.materials.append(m)
    if bevel:
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width, b.segments = bevel, seg
        b.limit_method = "ANGLE"
        b.harden_normals = True
    if smooth:
        me.shade_smooth()
    return ob


def mesh_ob(name, bm, loc, col=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    link(ob, col)
    return ob


def box(name, w, d, h, loc, m, bevel=0.006, col=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    for v in bm.verts:
        v.co.x *= w; v.co.y *= d; v.co.z *= h
    ob = mesh_ob(name, bm, loc, col)
    if rot:
        ob.rotation_euler = rot
    return finish(ob, m, bevel)


def cyl(name, r, h, loc, m, axis="Z", seg=32, r2=None, bevel=0.0, col=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r,
                          radius2=r if r2 is None else r2, depth=h, calc_uvs=True)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    ob = mesh_ob(name, bm, loc, col)
    return finish(ob, m, bevel)


def ball(name, r, loc, m, scale=(1, 1, 1), seg=32, rings=16, col=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r, calc_uvs=True)
    for v in bm.verts:
        v.co.x *= scale[0]; v.co.y *= scale[1]; v.co.z *= scale[2]
    ob = mesh_ob(name, bm, loc, col)
    return finish(ob, m)


def torus(name, major, minor, loc, m, col=None, seg=48, mseg=10):
    bm = bmesh.new()
    verts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(mseg):
            b = 2 * math.pi * j / mseg
            rr = major + minor * math.cos(b)
            ring.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), minor * math.sin(b))))
        verts.append(ring)
    for i in range(seg):
        for j in range(mseg):
            bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % mseg], verts[i][(j + 1) % mseg]))
    ob = mesh_ob(name, bm, loc, col)
    return finish(ob, m)


def panel(name, w, h, loc, m, col=None, rot=None):
    """Quad in the XZ plane facing -Y (towards the camera), UV 0..1."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for l, c in zip(me.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[l.index].uv = c
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    link(ob, col)
    me.materials.append(m)
    return ob


def arch_outline(w, sh, grow=0.0, n=36):
    R = w / 2 + grow
    pts = [(-R, -grow), (R, -grow), (R, sh)]
    for k in range(1, n):
        a = math.pi * k / n
        pts.append((R * math.cos(a), sh + R * math.sin(a)))
    pts.append((-R, sh))
    return pts


def arch_panel(name, w, sh, loc, m, col=None, grow=0.0, solid=0.0):
    pts = arch_outline(w, sh, grow)
    H = sh + w / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, 0, z) for x, z in pts], [], [tuple(range(len(pts)))])
    uv = me.uv_layers.new()
    for l, vi in zip(me.loops, me.polygons[0].vertices):
        x, z = pts[vi]
        uv.data[l.index].uv = ((x + w / 2) / w, z / H)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    link(ob, col)
    me.materials.append(m)
    if solid:
        s = ob.modifiers.new("Solid", "SOLIDIFY")
        s.thickness, s.offset = solid, -1
    return ob


# ------------------------------------------------------------------ casino pieces
def stool(x, y, col):
    red = mat("StoolRed", (0.55, 0.02, 0.03), rough=0.55, coat=0.3, bump_ribs=34.0)
    chrome = mat("Chrome", (0.9, 0.9, 0.92), metallic=1.0, rough=0.12)
    seat = cyl("StoolSeat", 0.21, 0.11, (x, y, STOOL_TOP - 0.055), red, seg=48, bevel=0.025, col=col)
    cyl("StoolPole", 0.028, 0.52, (x, y, 0.30), chrome, col=col)
    cyl("StoolCollar", 0.07, 0.04, (x, y, 0.56), chrome, col=col)
    cyl("StoolBase", 0.27, 0.035, (x, y, 0.0175), chrome, seg=48, bevel=0.01, col=col)
    torus("StoolRing", 0.20, 0.011, (x, y, 0.26), chrome, col=col)
    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        cyl(f"StoolStrut{i}", 0.008, 0.16, (x + 0.1 * math.cos(a), y + 0.1 * math.sin(a), 0.26), chrome, axis="Z", seg=8, col=col)


def slot_machine(cx, name, marq, reels, hero=False, col=None, y0=0.0, scale=1.0):
    before = set(bpy.data.objects)
    red = mat("MachineRed", (0.62, 0.015, 0.02), rough=0.22, coat=0.8, spec=0.6)
    dark = mat("MachineDark", (0.05, 0.015, 0.015), rough=0.5)
    gold = mat("Gold", (1.0, 0.68, 0.18), metallic=1.0, rough=0.22)
    chrome = mat("Chrome", (0.9, 0.9, 0.92), metallic=1.0, rough=0.12)
    bulb = mat("Bulb", (1, 0.9, 0.6), emit=(1.0, 0.82, 0.45), estr=8.0)
    P = lambda x, y, z: (cx + x, y0 + y, z)

    box(f"{name}_Lower", 0.92, 0.70, 0.92, P(0, 0.35, 0.46), red, 0.01, col)
    box(f"{name}_Kick", 0.92, 0.03, 0.10, P(0, -0.006, 0.05), chrome, 0.004, col)
    box(f"{name}_Vent", 0.46, 0.02, 0.17, P(0.02, -0.004, 0.30), dark, 0.004, col)
    for i in (-0.455, 0.455):
        box(f"{name}_Trim", 0.03, 0.03, 0.94, P(i, -0.005, 0.47), gold, 0.006, col)
    panel(f"{name}_Paytable", 0.46, 0.40, P(-0.12, -0.012, 0.67), mat("MatPay", tex="paytable.png", tex_emit=0.3, rough=0.3), col)
    for j, (c, e) in enumerate([((0.1, 0.9, 0.2), 3), ((0.2, 0.5, 1.0), 4), ((1, 0.15, 0.1), 4)]):
        panel(f"{name}_Ind{j}", 0.10, 0.05 + 0.01 * j, P(0.31, -0.012, 0.80 - 0.1 * j), mat(f"Ind{j}", c, emit=c, estr=e), col)
    # deck with buttons
    deck = box(f"{name}_Deck", 0.94, 0.30, 0.10, P(0, -0.03, 1.0), red, 0.012, col, rot=(math.radians(-10), 0, 0))
    deck.name = f"{name}_Deck"
    orange = mat("BtnOrange", (1.0, 0.45, 0.05), rough=0.3, emit=(1.0, 0.4, 0.05), estr=1.0, coat=0.5)
    ylw = mat("BtnYellow", (1.0, 0.8, 0.1), rough=0.3, emit=(1.0, 0.75, 0.05), estr=0.8, coat=0.5)
    tilt = (math.radians(-10), 0, 0)
    for k, (bx, mm) in enumerate([(-0.20, ylw), (-0.03, orange)]):
        b = box(f"{name}_Btn{k}", 0.15, 0.075, 0.035, P(bx, -0.095, 1.06), mm, 0.01, col, rot=tilt)
        panel(f"{name}_BtnLbl{k}", 0.13, 0.055, P(bx, -0.1055, 1.082), mat("MatMax", tex="max_bet.png", tex_emit=0.4), col,
              rot=(math.radians(-100), 0, 0))
    cyl(f"{name}_Spin", 0.04, 0.04, P(0.31, -0.095, 1.065), mat("SpinRed", (1, 0.05, 0.05), emit=(1, 0.05, 0.03), estr=2.0, coat=0.8, rough=0.2),
        bevel=0.012, col=col)
    # upper housing built around the reel window
    box(f"{name}_Back", 0.92, 0.50, 0.80, P(0, 0.80, 1.43), dark, 0.0, col)
    box(f"{name}_WinBottom", 0.92, 0.06, 0.09, P(0, 0.12, 1.095), red, 0.006, col)
    box(f"{name}_Header", 0.92, 0.06, 0.20, P(0, 0.12, 1.66), red, 0.006, col)
    for sx in (-0.41, 0.41):
        box(f"{name}_Post", 0.10, 0.06, 0.42, P(sx, 0.12, 1.35), red, 0.006, col)
    panel(f"{name}_HeaderTex", 0.72, 0.18, P(0, 0.087, 1.66), mat("MatHeader", tex="header.png", tex_emit=0.4, rough=0.3), col)
    # window frame
    for nm, (w, h, x, z) in {"T": (0.76, 0.025, 0, 1.567), "B": (0.76, 0.025, 0, 1.133), "L": (0.025, 0.46, -0.372, 1.35), "R": (0.025, 0.46, 0.372, 1.35)}.items():
        box(f"{name}_Fr{nm}", w, 0.03, h, P(x, 0.095, z), gold if hero else chrome, 0.006, col)
    # reels
    reel_objs = []
    for i, rx in enumerate((-0.24, 0.0, 0.24)):
        reel_objs.append(make_reel(f"{name}_Reel{i}", P(rx, 0.33, 1.35), reels[i], col))
    for rx in (-0.12, 0.12):
        box(f"{name}_Div", 0.012, 0.06, 0.41, P(rx, 0.12, 1.35), chrome, 0.002, col)
    box(f"{name}_Payline", 0.72, 0.004, 0.007, P(0, 0.108, 1.35), mat("Payline", (1, 0.1, 0.05), emit=(1, 0.12, 0.05), estr=9.0), 0.0, col)
    # marquee
    arch_panel(f"{name}_MarqueeBezel", 0.86, 0.16, P(0, 0.135, 1.76), gold, col, grow=0.045, solid=0.06)
    arch_panel(f"{name}_Marquee", 0.86, 0.16, P(0, 0.118, 1.76), mat("Marq_" + marq, tex=marq, tex_emit=0.3, rough=0.4), col)
    R = 0.43 + 0.058
    if hero:
        # ring of bulbs
        pts = []
        for k in range(0, 31):
            a = math.pi * k / 30
            pts.append((R * math.cos(a), 1.76 + 0.16 + R * math.sin(a) - 0.045 + 0.0))
        for z in (1.76 + 0.02, 1.76 + 0.08):
            pts.append((R, z)); pts.append((-R, z))
        for i, (x, z) in enumerate(pts):
            ball(f"{name}_Bulb{i}", 0.016, P(x, 0.09, z), bulb, seg=12, rings=8, col=col)
    if scale != 1.0:
        emp = bpy.data.objects.new(f"{name}_Scale", None)
        emp.location = (cx, y0, 0)
        link(emp, col)
        bpy.context.view_layer.update()
        inv = emp.matrix_world.inverted()
        for ob in set(bpy.data.objects) - before - {emp}:
            ob.parent = emp
            ob.matrix_parent_inverse = inv
        emp.scale = (scale, scale, scale)
    return reel_objs


def make_reel(name, loc, tex, col, r=0.19, width=0.215, n=8):
    bm = bmesh.new()
    seg = 64
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for xi in (0, 1):
        x = (xi - 0.5) * width
        rings.append([bm.verts.new((x, r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg))) for k in range(seg + 1)])
    for k in range(seg):
        f = bm.faces.new((rings[0][k], rings[0][k + 1], rings[1][k + 1], rings[1][k]))
        for l, (xi, kk) in zip(f.loops, [(0, k), (0, k + 1), (1, k + 1), (1, k)]):
            # u runs against theta so that a symbol's "up" is up on the front of the reel
            l[uvl].uv = (kk / seg, xi)   # verified by render: upright, not mirrored
    # flip normals outward (-Y side is the camera side)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_ob(name, bm, loc, col)
    finish(ob, mat("Reel_" + tex, tex=tex, tex_emit=0.22, rough=0.35, spec=0.4))
    ob.rotation_mode = "XYZ"
    return ob


def reel_front_angle(index, n=8):
    """rotation_x that brings strip cell `index` to the front, facing the camera (-Y)."""
    theta = 2 * math.pi * ((index + 0.5) / n)
    return math.pi - theta


def build_environment(sc):
    env = coll("Environment")
    chrome = mat("Chrome", (0.9, 0.9, 0.92), metallic=1.0, rough=0.12)
    # carpet floor
    fl = panel("Floor", 20, 20, (0, 0, 0), mat("Carpet", tex="carpet.png", rough=0.38, tex_scale=(5, 5), spec=0.6), env, rot=(math.radians(-90), 0, 0))
    fl.rotation_euler = (0, 0, 0)
    # panel() faces -Y; rotate to face +Z (up)
    fl.rotation_euler = (math.radians(90), 0, 0)
    fl.location = (0, 3, 0)
    # back wall
    wall = panel("Wall", 24, 8, (0, 4.5, 3.5), mat("Wall", (0.18, 0.03, 0.05), rough=0.6, emit=(0.5, 0.08, 0.1), estr=0.04), env)
    # sparkle / bokeh lights deep in the casino
    rnd = random.Random(7)
    cols = [(1, 0.7, 0.25), (1, 0.25, 0.15), (1, 0.9, 0.6), (0.4, 0.6, 1)]
    for i in range(60):
        c = rnd.choice(cols)
        ball(f"Bokeh{i}", rnd.uniform(0.04, 0.09), (rnd.uniform(-5, 5), rnd.uniform(3.6, 4.3), rnd.uniform(0.4, 3.2)),
             mat(f"Bk{c}", c, emit=c, estr=8), col=env, seg=8, rings=6)
    # main machine + neighbours
    reels_hero = ["reel_a.png", "reel_b.png", "reel_c.png"]
    hero = slot_machine(0.25, "Hero", "marq_lucky.png", reels_hero, hero=True, col=env)
    slot_machine(1.22, "NbrR", "marq_lucky.png", ["reel_b.png", "reel_c.png", "reel_a.png"], col=env)
    slot_machine(-0.72, "NbrL", "marq_gold.png", ["reel_c.png", "reel_a.png", "reel_b.png"], col=env)
    slot_machine(2.19, "NbrR2", "marq_gold.png", ["reel_a.png", "reel_c.png", "reel_b.png"], col=env)
    slot_machine(-1.69, "NbrL2", "marq_lucky.png", ["reel_b.png", "reel_a.png", "reel_c.png"], col=env)
    # second row, deeper
    for i, bx in enumerate((-3.6, -1.85, -0.1, 1.65, 3.4)):
        slot_machine(bx, f"Back{i}", "marq_gold.png" if i % 2 else "marq_lucky.png",
                     ["reel_a.png", "reel_b.png", "reel_c.png"], col=env, y0=2.4, scale=1.9)
    # ceiling light beam + bulb row
    gold = mat("Gold", (1.0, 0.68, 0.18), metallic=1.0, rough=0.22)
    box("CeilBeam", 16, 0.4, 0.22, (0, 1.6, 4.6), gold, 0.02, env)
    bulb = mat("Bulb", (1, 0.9, 0.6), emit=(1.0, 0.82, 0.45), estr=8.0)
    for i in range(48):
        ball(f"CeilBulb{i}", 0.03, (-7 + i * 0.3, 1.38, 4.47), bulb, seg=10, rings=6, col=env)
    stool(CHAR_X, CHAR_Y, env)
    stool(0.85, CHAR_Y, env)
    stool(-1.4, CHAR_Y + 0.05, env)
    return hero


def animate_reels(hero):
    """Reels 0 and 1 stop on a 7; reel 2 stops one click short (the 7 one cell above the payline)."""
    plan = [
        dict(stop=30, cell=0, w=0.105, start=0.4),
        dict(stop=42, cell=1, w=0.115, start=2.0),
        dict(stop=86, cell=2, w=0.100, start=1.1, short=True),
    ]
    for ob, p in zip(hero, plan):
        final = reel_front_angle(p["cell"])
        if p.get("short"):
            final -= 2 * math.pi / 8            # one cell up
        s = p["stop"]
        a_end_lin = final + 2 * math.pi * 3
        f_lin = s - 10
        ob.rotation_euler[0] = a_end_lin - p["w"] * (s - 10 - 1) - 0.0
        ob.rotation_euler[0] = final - p["w"] * (s - 1)
        ob.keyframe_insert("rotation_euler", index=0, frame=1)
        ob.rotation_euler[0] = final - p["w"] * 10
        ob.keyframe_insert("rotation_euler", index=0, frame=s - 10)
        ob.rotation_euler[0] = final
        ob.keyframe_insert("rotation_euler", index=0, frame=s)
        ob.rotation_euler[0] = final
        ob.keyframe_insert("rotation_euler", index=0, frame=F_END)
        # keep the long part linear, ease the last frames
        for c in fcurves_of(ob):
            for k, kp in enumerate(c.keyframe_points):
                kp.interpolation = "LINEAR" if k in (0, 2) else "BEZIER"


def build_lights(sc):
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.09, 0.03, 0.02, 1)
    bg.inputs["Strength"].default_value = 1.0
    li = coll("Lights")

    def area(name, loc, target, energy, size, color):
        d = bpy.data.lights.new(name, "AREA")
        d.energy, d.size, d.color = energy, size, color
        ob = bpy.data.objects.new(name, d)
        ob.location = loc
        link(ob, li)
        c = ob.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        return ob

    tgt = bpy.data.objects.new("LightTarget", None)
    tgt.location = (0.1, 0, 1.3)
    link(tgt, li)
    area("Key", (0.8, -3.0, 3.0), tgt, 230, 2.5, (1.0, 0.78, 0.55))
    area("Fill", (-2.5, -3.0, 1.6), tgt, 55, 3.0, (1.0, 0.6, 0.45))
    area("Close", (0.2, -1.0, 1.6), tgt, 14, 0.8, (1.0, 0.85, 0.7))
    area("Top", (0.0, -1.0, 3.6), tgt, 35, 3.0, (1.0, 0.7, 0.5))


