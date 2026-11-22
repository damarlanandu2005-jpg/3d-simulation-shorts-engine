"""rail_sets.py - every environment of the railroad video as real Blender geometry (units = metres, track runs along +Y).
Each set lives at its own X offset so hard cuts are free. Builders return a dict of anchors used by build_rail.py."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import casino_scene as cs
from casino_scene import mat, box, cyl, ball, panel, torus, link, coll, mesh_ob, finish

F = lambda t: max(1, int(round(1 + t * cs.FPS)))

# set origins (X) - far apart so sets never overlap in any shot
OX = dict(TRACK=0.0, BRIDGE=-1000.0, DESERT=-2000.0, LEDGE=-3000.0, STATION=1000.0, BEAM=2000.0, DECK=3000.0, CAR=4000.0, GAP=5000.0)
GAUGE = 0.72                                # half track gauge


# ------------------------------------------------------------------ small helpers
def merged_boxes(name, specs, m, col, bevel=0.0):
    """one mesh from many boxes: specs = [(cx, cy, cz, w, d, h), ...]"""
    bm = bmesh.new()
    for cx, cy, cz, w, d, h in specs:
        r = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
        for v in r["verts"]:
            v.co = Vector((v.co.x * w + cx, v.co.y * d + cy, v.co.z * h + cz))
    ob = mesh_ob(name, bm, (0, 0, 0), col)
    return finish(ob, m, bevel, smooth=False)


def keyed_visible(ob, t0, t1):
    """visible only t0..t1 s (render + viewport), CONSTANT interpolation"""
    for state, f in ((True, 1), (False, F(t0)), (True, F(t1))):
        ob.hide_render = state
        ob.keyframe_insert("hide_render", frame=f)
    ob.hide_render = True
    for fc in cs.fcurves_of(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def keyed_emission(m, keys):
    """keys = [(t, (r,g,b), strength)] on the Principled emission of material m"""
    b = m.node_tree.nodes["Principled BSDF"]
    for t, c, s in keys:
        b.inputs["Emission Color"].default_value = (*c, 1)
        b.inputs["Emission Strength"].default_value = s
        b.inputs["Emission Color"].keyframe_insert("default_value", frame=F(t))
        b.inputs["Emission Strength"].keyframe_insert("default_value", frame=F(t))


def keyed_loc(ob, keys, interp="BEZIER"):
    for t, p in keys:
        ob.location = p
        ob.keyframe_insert("location", frame=F(t))
    for fc in cs.fcurves_of(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def keyed_scale(ob, keys, interp="BEZIER"):
    for t, s in keys:
        ob.scale = s if isinstance(s, (tuple, list)) else (s, s, s)
        ob.keyframe_insert("scale", frame=F(t))
    for fc in cs.fcurves_of(ob):
        if fc.data_path == "scale":
            for kp in fc.keyframe_points:
                kp.interpolation = interp


# ------------------------------------------------------------------ materials
def mat_box(name, tex, scale, emit=0.3, rough=0.95, spec=0.1, tint=None):
    """image texture projected in OBJECT space (box projection): no UVs needed, scale = tiles per metre"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = cs.image(tex)
    t.projection = "BOX"
    t.projection_blend = 0.15
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = emit
    return m


def mat_strata(name, freq, stops, distort=2.5, noise_scale=0.25, emit=0.3, rough=0.95):
    """horizontal rock bands from OBJECT z (works on every face): sin(z*freq + noise*distort) -> colour ramp"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.08
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = noise_scale
    nz.inputs["Detail"].default_value = 5.0
    mulz = nt.nodes.new("ShaderNodeMath"); mulz.operation = "MULTIPLY"; mulz.inputs[1].default_value = freq
    muln = nt.nodes.new("ShaderNodeMath"); muln.operation = "MULTIPLY"; muln.inputs[1].default_value = distort
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
    sn = nt.nodes.new("ShaderNodeMath"); sn.operation = "SINE"
    ma = nt.nodes.new("ShaderNodeMath"); ma.operation = "MULTIPLY_ADD"; ma.inputs[1].default_value = 0.5; ma.inputs[2].default_value = 0.5
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (p, c) in zip(els, stops):
        e.position, e.color = p, (*c, 1)
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mulz.inputs[0])
    nt.links.new(nz.outputs["Fac"], muln.inputs[0])
    nt.links.new(mulz.outputs["Value"], add.inputs[0])
    nt.links.new(muln.outputs["Value"], add.inputs[1])
    nt.links.new(add.outputs["Value"], sn.inputs[0])
    nt.links.new(sn.outputs["Value"], ma.inputs[0])
    nt.links.new(ma.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = emit
    return m


def M():
    d = {}
    ROCK = [(0.0, (0.55, 0.14, 0.08)), (0.35, (0.85, 0.36, 0.12)), (0.65, (0.97, 0.60, 0.22)), (1.0, (0.70, 0.22, 0.12))]
    d["rock"] = mat_strata("Rock", 9.0, ROCK, 3.0, 0.8, emit=0.28)
    d["rock_big"] = mat_strata("RockBig", 3.2, ROCK, 3.5, 0.12, emit=0.32)
    d["void"] = mat_strata("Void", 2.4, [(0.0, (0.03, 0.05, 0.38)), (0.5, (0.12, 0.22, 0.75)), (0.8, (0.30, 0.28, 0.80)), (1.0, (0.10, 0.12, 0.55))], 2.0, 0.05, emit=0.9, rough=1.0)
    d["ballast"] = mat_box("Ballast", "ballast.png", 0.9, emit=0.1, rough=1.0, spec=0.05)
    d["sand"] = mat_box("Sand", "sand.png", 0.08, emit=0.3, rough=1.0, spec=0.0)
    d["wood"] = mat_box("Wood", "wood.png", 0.6, emit=0.12, rough=0.8, spec=0.2)
    d["wood_flat"] = mat("WoodFlat", (0.45, 0.26, 0.13), rough=0.8, emit=(0.45, 0.26, 0.13), estr=0.1)
    d["tie"] = mat("Tie", (0.28, 0.16, 0.10), rough=0.9, spec=0.1)
    d["steel"] = mat("Steel", (0.5, 0.5, 0.55), metallic=1.0, rough=0.35)
    d["rail"] = mat("Rail", (0.62, 0.62, 0.66), metallic=1.0, rough=0.3, emit=(0.5, 0.5, 0.55), estr=0.0)
    d["rail_hot"] = mat("RailHot", (0.62, 0.62, 0.66), metallic=0.6, rough=0.3, emit=(0.5, 0.5, 0.55), estr=0.0)
    d["black"] = mat("Black", (0.03, 0.03, 0.035), rough=0.55, spec=0.3)
    d["iron"] = mat("Iron", (0.10, 0.10, 0.12), metallic=0.8, rough=0.45)
    d["dark_blue"] = mat("NavyCar", (0.04, 0.08, 0.20), rough=0.35, spec=0.6)
    d["gold"] = mat("Gold", (1.0, 0.68, 0.18), metallic=1.0, rough=0.25, emit=(1.0, 0.6, 0.1), estr=0.15)
    d["green"] = mat("LocoGreen", (0.05, 0.38, 0.20), rough=0.4, emit=(0.05, 0.38, 0.2), estr=0.2)
    d["red"] = mat("RedPaint", (0.75, 0.08, 0.06), rough=0.5, emit=(0.75, 0.08, 0.06), estr=0.25)
    d["velvet"] = mat("Velvet", (0.65, 0.04, 0.05), rough=1.0, emit=(0.65, 0.04, 0.05), estr=0.45)
    d["brick"] = mat_box("Brick", "brick.png", 0.5, emit=0.2, spec=0.05)
    d["tile"] = mat_box("Tile", "tile.png", 0.4, emit=0.18, rough=0.4, spec=0.4)
    d["glass"] = mat("DomeGlass", (0.8, 0.9, 1.0), rough=0.1, emit=(0.75, 0.88, 1.0), estr=0.5, alpha=0.45)
    d["light"] = mat("LampLight", (1, 0.9, 0.6), emit=(1.0, 0.85, 0.5), estr=9.0)
    d["head_lamp"] = mat("HeadLamp", (1, 1, 0.9), emit=(1.0, 0.95, 0.8), estr=25.0)
    d["smoke"] = mat("Smoke", (0.12, 0.09, 0.08), rough=1.0, emit=(0.12, 0.09, 0.08), estr=0.35)
    d["steam"] = mat("Steam", (1, 1, 1), rough=1.0, emit=(1, 1, 1), estr=0.9)
    d["fire"] = mat("Fire", (1.0, 0.45, 0.05), emit=(1.0, 0.42, 0.03), estr=7.0)
    d["fire2"] = mat("FireYellow", (1.0, 0.8, 0.2), emit=(1.0, 0.75, 0.15), estr=10.0)
    d["fireDark"] = mat("FireBrown", (0.35, 0.12, 0.05), emit=(0.5, 0.18, 0.05), estr=2.0)
    d["banner"] = mat("Banner", (1, 1, 1), tex="banner.png", rough=0.9, tex_emit=0.7)
    d["union"] = mat("UnionSign", (1, 1, 1), tex="union.png", rough=0.9, tex_emit=0.7)
    d["allaboard"] = mat("AllAboard", (1, 1, 1), tex="allaboard.png", rough=0.9, tex_emit=0.6)
    d["vander"] = mat("VanderSign", (1, 1, 1), tex="vandergold.png", rough=0.5, tex_emit=0.7)
    d["redcanyon"] = mat("RedCanyonSign", (1, 1, 1), tex="redcanyon.png", rough=0.5, tex_emit=0.7)
    d["ticket"] = mat("TicketSign", (1, 1, 1), tex="ticket.png", rough=0.5, tex_emit=0.7)
    d["news"] = mat("News", (1, 1, 1), tex="news.png", rough=1.0, tex_emit=0.75)
    d["cal_may"] = mat("CalMay", (1, 1, 1), tex="calendar.png", rough=1.0, tex_emit=0.8)
    d["cal_jul"] = mat("CalJul", (1, 1, 1), tex="calendar_jul.png", rough=1.0, tex_emit=0.8)
    d["crate"] = mat("Crate", (0.1, 0.5, 0.3), rough=0.7, emit=(0.1, 0.5, 0.3), estr=0.3)
    d["umb"] = mat("Umbrella", (1, 1, 1), tex="umbrella.png", rough=0.8, tex_emit=0.5)
    d["flag"] = mat("BlueFlag", (0.1, 0.35, 0.95), rough=0.8, emit=(0.1, 0.35, 0.95), estr=0.9)
    d["bag"] = mat("MoneyBag", (1, 1, 1), tex="money.png", rough=0.9, tex_emit=0.5)
    d["white"] = mat("WhitePaint", (0.95, 0.95, 0.95), rough=0.6, emit=(0.95, 0.95, 0.95), estr=0.3)
    d["coin"] = mat("Coin", (1.0, 0.8, 0.25), metallic=1.0, rough=0.2, emit=(1.0, 0.7, 0.15), estr=0.4)
    d["yellow"] = mat("SteelYellow", (0.95, 0.75, 0.05), rough=0.5, emit=(0.95, 0.75, 0.05), estr=0.3)
    d["merc"] = mat("Mercury", (0.9, 0.05, 0.05), emit=(0.95, 0.05, 0.05), estr=1.5)
    return d


# ------------------------------------------------------------------ world + lights
def build_world(sc):
    w = bpy.data.worlds.new("Sky")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = cs.image("sky.png")
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return bg


def build_lights(sc):
    col = coll("Lights")
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy, sun.angle = 4.2, math.radians(3)
    sun.color = (1.0, 0.93, 0.82)
    o = bpy.data.objects.new("Sun", sun)
    o.rotation_euler = (math.radians(52), math.radians(8), math.radians(-35))
    link(o, col)
    fill = bpy.data.lights.new("Fill", "SUN")
    fill.energy, fill.angle = 0.9, math.radians(20)
    fill.color = (0.65, 0.75, 1.0)
    f = bpy.data.objects.new("Fill", fill)
    f.rotation_euler = (math.radians(65), math.radians(-10), math.radians(140))
    link(f, col)
    return sun


# ------------------------------------------------------------------ track pieces
def track(name, ox, y0, y1, z, m, col, x=0.0, gauge=GAUGE, ties=True, rail_mats=None):
    """sleepers + two rails + ballast along Y from y0..y1. returns (railL, railR)"""
    length = y1 - y0
    ymid = (y0 + y1) / 2
    box(name + "_Bed", 3.4, length, 0.12, (ox + x, ymid, z - 0.06), m["ballast"], 0, col)
    if ties:
        specs = [(ox + x, y0 + 0.3 + i * 0.6, z + 0.07, 2.5, 0.22, 0.14) for i in range(int(length / 0.6))]
        merged_boxes(name + "_Ties", specs, m["tie"], col)
    rails = []
    for s, n in ((-1, "L"), (1, "R")):
        mm = (rail_mats or {}).get(n, m["rail"])
        base = box(f"{name}_Base{n}", 0.17, length, 0.04, (ox + x + s * gauge, ymid, z + 0.16), mm, 0, col)
        head = box(f"{name}_Rail{n}", 0.075, length, 0.17, (ox + x + s * gauge, ymid, z + 0.27), mm, 0.01, col)
        rails.append(head)
    return rails


def telegraph_poles(name, ox, x, y0, y1, step, z, col, m):
    specs, arms = [], []
    for y in range(int(y0), int(y1), step):
        specs.append((ox + x, y, z + 3.5, 0.16, 0.16, 7.0))
        arms.append((ox + x, y, z + 6.6, 1.5, 0.1, 0.1))
    merged_boxes(name + "_Poles", specs, m["wood_flat"], col)
    merged_boxes(name + "_Arms", arms, m["wood_flat"], col)


def locomotive(name, loc, m, col, facing_neg_y=True, scale=1.0, body=None):
    """steam locomotive: boiler, cab, stack, headlamp, wheels. Front faces -Y when facing_neg_y."""
    root = bpy.data.objects.new(name, None)
    link(root, col)
    root.location = loc
    root.scale = (scale, scale, scale)
    if not facing_neg_y:
        root.rotation_euler = (0, 0, math.pi)
    parts = []
    bm = body or m["black"]
    parts.append(cyl(name + "_Boiler", 0.85, 5.2, (0, -0.2, 1.75), bm, axis="Y", seg=28, col=col))
    parts.append(box(name + "_Cab", 2.3, 1.9, 2.6, (0, 2.9, 2.2), m["green"], 0.04, col))
    parts.append(box(name + "_Roof", 2.6, 2.3, 0.18, (0, 2.9, 3.6), m["iron"], 0.02, col))
    parts.append(cyl(name + "_Stack", 0.32, 1.1, (0, -2.0, 3.25), m["iron"], seg=18, r2=0.5, col=col))
    parts.append(cyl(name + "_Dome", 0.38, 0.5, (0, 0.2, 2.75), m["gold"], seg=18, col=col))
    parts.append(cyl(name + "_Lamp", 0.34, 0.25, (0, -2.95, 2.1), m["head_lamp"], axis="Y", seg=18, col=col))
    parts.append(box(name + "_Catcher", 2.0, 1.2, 0.8, (0, -3.2, 0.7), m["iron"], 0.03, col, rot=(math.radians(-25), 0, 0)))
    parts.append(box(name + "_Frame", 1.9, 6.4, 0.45, (0, 0.2, 0.75), m["iron"], 0.03, col))
    for i, y in enumerate((-1.6, -0.2, 1.2)):
        for s in (-1, 1):
            parts.append(cyl(f"{name}_Wheel{i}{s}", 0.62, 0.14, (s * 0.98, y, 0.62), m["red"], axis="X", seg=24, col=col))
    for s in (-1, 1):
        parts.append(cyl(f"{name}_SWheel{s}", 0.4, 0.14, (s * 0.98, -2.5, 0.42), m["red"], axis="X", seg=20, col=col))
    for p in parts:
        p.parent = root
    return root


def railcar(name, loc, m, col, length=6.0, body=None):
    root = bpy.data.objects.new(name, None)
    link(root, col)
    root.location = loc
    b = body or m["dark_blue"]
    parts = [box(name + "_Body", 2.6, length, 2.5, (0, 0, 1.9), b, 0.05, col),
             box(name + "_Roof", 2.8, length + 0.2, 0.2, (0, 0, 3.25), m["iron"], 0.03, col),
             box(name + "_Chassis", 2.0, length, 0.4, (0, 0, 0.7), m["iron"], 0.03, col)]
    for i in range(3):
        for s in (-1, 1):
            parts.append(cyl(f"{name}_W{i}{s}", 0.55, 0.12, (s * 0.98, -length / 2 + 1 + i * (length - 2) / 2, 0.55), m["iron"], axis="X", seg=20, col=col))
    for p in parts:
        p.parent = root
    return root


def puff(name, loc, r, m, col):
    return ball(name, r, loc, m, seg=14, rings=8, col=col)


def smoke_puffs(prefix, base, col, m, t0, t1, n=14, life=2.6, drift=(0.6, 0.0, 0.0), rise=7.0, r0=0.35, r1=1.7):
    """rolling smoke: n puffs spawned in turn, each rising/growing/fading (shrinks away) for `life` s; repeats t0..t1"""
    out = []
    for i in range(n):
        o = puff(f"{prefix}{i}", base, r0, m, col)
        o.scale = (0, 0, 0)
        o.keyframe_insert("scale", frame=1)
        out.append(o)
        k = 0
        t = t0 + (life / n) * i
        while t < t1:
            sp = base
            keyed = [(t, (0, 0, 0), sp), (t + 0.15 * life, (1.0, 1.0, 1.0), sp + Vector((drift[0] * 0.15, drift[1] * 0.15, rise * 0.12))),
                     (t + 0.7 * life, (r1 / r0 * 0.8,) * 3, sp + Vector((drift[0] * 0.7, drift[1] * 0.7, rise * 0.6))),
                     (t + life, (0, 0, 0), sp + Vector((drift[0], drift[1], rise)))]
            for tt, sc_, p in keyed:
                o.scale, o.location = sc_, p
                o.keyframe_insert("scale", frame=F(tt))
                o.keyframe_insert("location", frame=F(tt))
            t += life
            k += 1
        for fc in cs.fcurves_of(o):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    return out


# ------------------------------------------------------------------ oriented beams (trusses, arches, scaffolding)
def beams_mesh(name, segs, m, col):
    """segs = [(p0, p1, w, h)] -> one mesh of oriented boxes"""
    bm = bmesh.new()
    for p0, p1, w, h in segs:
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-5:
            continue
        f = d.normalized()
        up = Vector((0, 0, 1)) if abs(f.z) < 0.99 else Vector((1, 0, 0))
        r_ = f.cross(up).normalized()
        u2 = r_.cross(f)
        c = (p0 + p1) / 2
        r = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
        for v in r["verts"]:
            v.co = c + r_ * (v.co.x * w) + f * (v.co.y * L) + u2 * (v.co.z * h)
    ob = mesh_ob(name, bm, (0, 0, 0), col)
    return finish(ob, m, 0.0, smooth=False)


def lattice_tower(name, cx, cy, z0, z1, w, m, col, levels=None):
    """square steel lattice tower"""
    n = levels or max(3, int((z1 - z0) / 2.0))
    segs = []
    hz = [z0 + (z1 - z0) * i / n for i in range(n + 1)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            segs.append(((cx + sx * w / 2, cy + sy * w / 2, z0), (cx + sx * w / 2, cy + sy * w / 2, z1), 0.12, 0.12))
    for i in range(n):
        za, zb = hz[i], hz[i + 1]
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            segs.append(((cx + a[0] * w / 2, cy + a[1] * w / 2, za), (cx + b[0] * w / 2, cy + b[1] * w / 2, zb), 0.07, 0.07))
            segs.append(((cx + a[0] * w / 2, cy + a[1] * w / 2, zb), (cx + b[0] * w / 2, cy + b[1] * w / 2, za), 0.07, 0.07))
        segs.append(((cx - w / 2, cy - w / 2, zb), (cx + w / 2, cy - w / 2, zb), 0.08, 0.08))
        segs.append(((cx - w / 2, cy + w / 2, zb), (cx + w / 2, cy + w / 2, zb), 0.08, 0.08))
    return beams_mesh(name, segs, m, col)


# ------------------------------------------------------------------ SET: TRACK (canyon floor, two walls)
def build_track_set(m, ledge=False, ox=None):
    ox = OX["TRACK"] if ox is None else ox
    col = coll("Env_Track" if not ledge else "Env_Ledge")
    L0, L1 = -14.0, 170.0
    ym = (L0 + L1) / 2
    box("TK_Ground", 16, L1 - L0, 0.3, (ox, ym, -0.15), m["sand"], 0, col)
    track("TK_Main", ox, L0, L1, 0.0, m, col)
    # second track on the left (green locomotive passes there)
    track("TK_Side", ox, L0, L1, 0.0, m, col, x=-3.9)
    box("TK_WallL", 3, L1 - L0, 60, (ox - 7.6, ym, 29.5), m["rock_big"], 0, col)
    if not ledge:
        box("TK_WallR", 3, L1 - L0, 60, (ox + 7.6, ym, 29.5), m["rock_big"], 0, col)
    else:
        box("TK_LedgeFar", 3, L1 - L0, 80, (ox + 70, ym, -10), m["void"], 0, col)
        box("TK_VoidFloor", 140, L1 - L0, 1, (ox + 36, ym, -48), m["void"], 0, col)
        box("TK_GroundR", 20, L1 - L0, 0.3, (ox + 18, ym, -0.15), m["sand"], 0, col)
    telegraph_poles("TK_Pole", ox, -6.0, 0, 160, 18, 0.0, col, m)
    # cacti / rocks for scale
    r = random.Random(4)
    for i in range(14):
        x = ox + r.choice((-1, 1)) * r.uniform(3.4, 6.2) - (0 if not ledge else 0)
        y = r.uniform(0, 150)
        ball(f"TK_Rock{i}", r.uniform(0.15, 0.4), (x, y, 0.05), m["rock"], scale=(1, 1, 0.7), seg=10, rings=6, col=col)
    # blue sky behind the far end is the world; mesa silhouettes
    return {"ox": ox, "cx": ox}


# ------------------------------------------------------------------ SET: BRIDGE (canyon crossing along Y; void y in [20,120])
def build_bridge_set(m):
    ox = OX["BRIDGE"]
    col = coll("Env_Bridge")
    Y0, Y1 = 20.0, 120.0
    # land on both sides
    box("BR_LandNear", 400, 60, 6, (ox, Y0 - 30, -3), m["rock_big"], 0, col)
    box("BR_LandFar", 400, 60, 6, (ox, Y1 + 30, -3), m["rock_big"], 0, col)
    # cliff faces (strata) and the deep blue void below
    panel("BR_CliffNear", 400, 90, (ox, Y0, -48), m["void"], col, rot=(math.radians(90), 0, math.radians(180)))
    panel("BR_CliffFar", 400, 90, (ox, Y1, -48), m["void"], col, rot=(math.radians(90), 0, 0))
    box("BR_RimNear", 400, 1.2, 9, (ox, Y0 - 0.6, -4.5), m["rock_big"], 0, col)
    box("BR_RimFar", 400, 1.2, 9, (ox, Y1 + 0.6, -4.5), m["rock_big"], 0, col)
    box("BR_Floor", 400, Y1 - Y0 + 4, 1, (ox, (Y0 + Y1) / 2, -92), m["void"], 0, col)
    # deck (wooden), rails and side trusses
    box("BR_Deck", 3.6, 190, 0.4, (ox, 70, -0.2), m["wood"], 0.01, col)
    rails = track("BR_Track", ox, -20, 160, 0.0, m, col)
    side = []
    for s in (-1, 1):
        for i in range(0, 100, 5):
            y = Y0 + i
            side.append(((ox + s * 1.9, y, 0.0), (ox + s * 1.9, y, 1.5), 0.1, 0.1))
        side.append(((ox + s * 1.9, Y0, 1.5), (ox + s * 1.9, Y1, 1.5), 0.12, 0.12))
        for i in range(0, 100, 5):
            y = Y0 + i
            side.append(((ox + s * 1.9, y, 1.5), (ox + s * 1.9, y + 5, 0.0), 0.07, 0.07))
    beams_mesh("BR_Trusses", side, m["steel"], col)
    # steel arch below the deck with hangers
    arch, hang = [], []
    pts = []
    for k in range(0, 41):
        y = Y0 + 100 * k / 40
        z = -1.2 - 44 * (1 - ((y - 70) / 50) ** 2)
        pts.append((ox, y, z))
    for a, b in zip(pts[:-1], pts[1:]):
        for dx in (-1.4, 1.4):
            arch.append(((a[0] + dx, a[1], a[2]), (b[0] + dx, b[1], b[2]), 0.55, 0.55))
    for k in range(2, 39, 3):
        p = pts[k]
        for dx in (-1.4, 1.4):
            hang.append(((p[0] + dx, p[1], p[2]), (p[0] + dx, p[1], -0.3), 0.12, 0.12))
    beams_mesh("BR_Arch", arch, m["iron"], col)
    beams_mesh("BR_Hangers", hang, m["steel"], col)
    # half-built scaffolding tower with a plank (the engineer on the plank, shot 3-4)
    lattice_tower("BR_Scaffold", ox + 9.0, 48.0, -88, 0.4, 3.0, m["steel"], col, levels=18)
    box("BR_Plank", 0.9, 5.5, 0.12, (ox + 9.0, 45.5, 0.45), m["wood_flat"], 0.01, col)
    return {"ox": ox, "deck_z": 0.0, "plank": (ox + 9.0, 46.0, 0.52)}


# ------------------------------------------------------------------ SET: DESERT plain
def build_desert_set(m):
    ox = OX["DESERT"]
    col = coll("Env_Desert")
    box("DS_Sand", 600, 600, 1, (ox, 200, -0.5), m["sand"], 0, col)
    r = random.Random(9)
    for i in range(18):
        x, y = ox + r.uniform(-220, 220), r.uniform(120, 360)
        box(f"DS_Mesa{i}", r.uniform(12, 40), r.uniform(10, 30), r.uniform(6, 22), (x, y, 5), m["rock_big"], 0, col)
    box("DS_Trail", 6, 600, 0.05, (ox, 200, 0.02), m["ballast"], 0, col)
    return {"ox": ox}


# ------------------------------------------------------------------ SET: STATION (hall, brick facade, glass dome, steps, banner)
def arch_surface(name, cx, y0, y1, radius, zc, m, col, n=24, ny=6):
    bm = bmesh.new()
    rows = []
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        rows.append([bm.verts.new((cx + radius * math.cos(math.pi * k / n), y, zc + radius * 0.62 * math.sin(math.pi * k / n))) for k in range(n + 1)])
    for j in range(ny):
        for k in range(n):
            bm.faces.new((rows[j][k], rows[j][k + 1], rows[j + 1][k + 1], rows[j + 1][k]))
    ob = mesh_ob(name, bm, (0, 0, 0), col)
    return finish(ob, m, 0.0)


def build_station_set(m):
    ox = OX["STATION"]
    col = coll("Env_Station")
    box("ST_Floor", 80, 80, 0.3, (ox, 10, -0.15), m["tile"], 0, col)
    # back facade with arched windows + clock tower
    box("ST_Facade", 60, 1.6, 15, (ox, 32, 7.5), m["brick"], 0, col)
    wins = []
    for i in range(-6, 7):
        wins.append((ox + i * 4.2, 31.1, 5.5, 2.0, 0.1, 5.0))
    merged_boxes("ST_Windows", wins, mat("WinGlass", (0.1, 0.2, 0.4), emit=(0.25, 0.45, 0.8), estr=0.9), col)
    box("ST_Tower", 5, 5, 13, (ox + 9, 31, 20), m["brick"], 0, col)
    panel("ST_Clock", 3.2, 3.2, (ox + 9, 28.35, 21.5), mat("ClockFace", (1, 1, 1), tex="clock.png", emit=(1, 1, 1), estr=0.2, tex_emit=0.7), col, rot=(math.radians(90), 0, 0))
    box("ST_TowerCap", 5.6, 5.6, 1.2, (ox + 9, 31, 27), m["iron"], 0, col)
    # glass dome with ribs
    arch_surface("ST_Dome", ox, -30, 32, 30.0, 4.0, m["glass"], col, 28, 8)
    ribs = []
    for yy in range(-30, 33, 7):
        pts = [(ox + 30 * math.cos(math.pi * k / 28), yy, 4.0 + 30 * 0.62 * math.sin(math.pi * k / 28)) for k in range(29)]
        for a, b in zip(pts[:-1], pts[1:]):
            ribs.append((a, b, 0.25, 0.25))
    beams_mesh("ST_Ribs", ribs, m["steel"], col)
    # gold steps with red carpet (the tycoon's stage) + banner + union sign + money bags
    box("ST_Step1", 7.0, 3.2, 0.5, (ox, 10, 0.25), m["gold"], 0.02, col)
    box("ST_Step2", 5.2, 2.4, 0.5, (ox, 10.3, 0.75), m["gold"], 0.02, col)
    box("ST_Step3", 3.4, 1.8, 0.5, (ox, 10.6, 1.25), m["gold"], 0.02, col)
    box("ST_Carpet", 2.2, 5.0, 0.04, (ox, 8.2, 0.52), m["velvet"], 0, col)
    panel("ST_Banner", 9.0, 3.4, (ox, 14.5, 7.5), m["banner"], col, rot=(math.radians(90), 0, 0))
    panel("ST_Union", 9.0, 1.4, (ox, 14.5, 10.2), m["union"], col, rot=(math.radians(90), 0, 0))
    for i, sx in enumerate((-2.6, 2.6)):
        ball(f"ST_Bag{i}", 0.7, (ox + sx, 9.2, 0.55), m["bag"], scale=(1, 1, 1.15), col=col)
    # lamps + benches for depth
    for i, sx in enumerate((-14, -7, 7, 14)):
        cyl(f"ST_LampPost{i}", 0.08, 4.2, (ox + sx, 18, 2.1), m["iron"], seg=10, col=col)
        ball(f"ST_Lamp{i}", 0.28, (ox + sx, 18, 4.3), m["light"], seg=12, rings=8, col=col)
    # train shed: two tracks + cars at the left, for the background of the concourse shots
    track("ST_Track", ox, 12, 62, 0.0, m, col, x=-16)
    railcar("ST_Car", (ox - 16, 30, 0.0), m, col, 12.0, m["dark_blue"])
    panel("ST_AllAboard", 1.5, 0.75, (ox + 0.0, 2.0, 3.3), m["allaboard"], col, rot=(math.radians(90), 0, 0))
    return {"ox": ox}


# ------------------------------------------------------------------ SET: BEAM (workers sit on a girder over the canyon)
def build_beam_set(m):
    ox = OX["BEAM"]
    col = coll("Env_Beam")
    panel("BM_Back", 160, 70, (ox, 18, 8), m["rock_big"], col, rot=(math.radians(90), 0, 0))
    panel("BM_Void", 160, 90, (ox, 17.8, -62), m["void"], col, rot=(math.radians(90), 0, 0))
    box("BM_Girder", 12.0, 0.6, 0.45, (ox, 0, 0.0), m["steel"], 0.02, col)
    box("BM_GirderTop", 12.0, 0.9, 0.08, (ox, 0, 0.27), m["steel"], 0, col)
    box("BM_GirderBot", 12.0, 0.9, 0.08, (ox, 0, -0.27), m["steel"], 0, col)
    rivets = [(ox + i * 0.5 - 5.5, -0.32, 0.0, 0.06, 0.04, 0.06) for i in range(23)]
    merged_boxes("BM_Rivets", rivets, m["iron"], col)
    for i, sx in enumerate((-6.0, 6.0)):
        lattice_tower(f"BM_Tower{i}", ox + sx, 0.0, -40, -0.3, 1.6, m["steel"], col, levels=10)
    box("BM_Floor", 200, 100, 1, (ox, 40, -92), m["void"], 0, col)
    return {"ox": ox, "seat_z": 0.28}


# ------------------------------------------------------------------ SET: DECK (wooden bridge deck, one long seamless rail, crane, umbrella)
def build_deck_set(m, hot):
    ox = OX["DECK"]
    col = coll("Env_Deck")
    L0, L1 = -20.0, 220.0
    ym = (L0 + L1) / 2
    box("DK_Deck", 6.4, L1 - L0, 0.5, (ox, ym, -0.25), m["wood"], 0.01, col)
    # boards read as stripes across the deck
    specs = [(ox, y, 0.02, 6.4, 0.06, 0.03) for y in range(int(L0), int(L1), 1)]
    merged_boxes("DK_Seams", specs, m["tie"], col)
    for s, n in ((-1, "L"), (1, "R")):
        box(f"DK_Rail{n}", 0.075, L1 - L0, 0.17, (ox + s * GAUGE, ym, 0.1), hot[n], 0.01, col)
        box(f"DK_Base{n}", 0.17, L1 - L0, 0.05, (ox + s * GAUGE, ym, 0.03), hot[n], 0, col)
    ties = [(ox, y, 0.04, 2.4, 0.2, 0.08) for y in [L0 + 0.5 + i * 0.6 for i in range(int((L1 - L0) / 0.6))]]
    merged_boxes("DK_Ties", ties, m["tie"], col)
    # side railings + bunting
    posts, rails_ = [], []
    for s in (-1, 1):
        for y in range(int(L0), int(L1), 4):
            posts.append((ox + s * 3.1, y, 0.65, 0.12, 0.12, 1.3))
        rails_.append((ox + s * 3.1, ym, 1.25, 0.1, L1 - L0, 0.1))
    merged_boxes("DK_Posts", posts, m["iron"], col)
    merged_boxes("DK_Handrail", rails_, m["iron"], col)
    # canyon below + far cliffs
    box("DK_Floor", 600, 400, 1, (ox, ym, -90), m["void"], 0, col)
    panel("DK_CliffL", 400, 160, (ox - 60, ym, -40), m["void"], col, rot=(math.radians(90), 0, math.radians(90)))
    panel("DK_CliffR", 400, 160, (ox + 60, ym, -40), m["void"], col, rot=(math.radians(90), 0, math.radians(-90)))
    r = random.Random(12)
    for i in range(14):
        box(f"DK_Mesa{i}", r.uniform(10, 30), r.uniform(10, 25), r.uniform(8, 25), (ox + r.choice((-1, 1)) * r.uniform(70, 160), r.uniform(60, 300), 0), m["rock_big"], 0, col)
    # crane (yellow lattice) near the deck start
    lattice_tower("DK_Crane", ox - 4.2, 18, 0, 14, 1.6, m["yellow"], col, levels=7)
    beams_mesh("DK_Boom", [((ox - 4.2, 18, 14), (ox + 1.5, 24, 17.5), 0.2, 0.2), ((ox - 4.2, 18, 14), (ox - 4.2, 12, 12), 0.2, 0.2),
                           ((ox + 1.5, 24, 17.5), (ox + 1.5, 24, 9), 0.05, 0.05)], m["yellow"], col)
    for i in range(6):                              # bunting along the left rail
        panel(f"DK_Flag{i}", 0.5, 0.5, (ox - 3.1, 20 + i * 0.9, 1.1), mat(f"Flag{i % 3}", [(0.1, 0.7, 0.3), (0.95, 0.5, 0.05), (0.1, 0.3, 0.9)][i % 3], emit=[(0.1, 0.7, 0.3), (0.95, 0.5, 0.05), (0.1, 0.3, 0.9)][i % 3], estr=0.6), col, rot=(math.radians(90), 0, math.radians(90)))
    # sunbather: umbrella, deck chair, table (the character is added by build_rail.py)
    ux, uy = ox + 0.0, 48.0
    cyl("DK_UmbPole", 0.04, 2.6, (ux + 1.0, uy, 1.3), m["iron"], seg=8, col=col)
    cyl("DK_Umbrella", 1.5, 0.5, (ux + 1.0, uy, 2.7), m["umb"], seg=16, r2=0.1, col=col)
    box("DK_ChairSeat", 0.8, 0.8, 0.08, (ux, uy, 0.28), mat("ChairStripe", (1, 1, 1), tex="stripe_chair.png", rough=0.9, tex_emit=0.6), 0.01, col)
    box("DK_ChairBack", 0.8, 0.08, 0.9, (ux, uy + 0.4, 0.7), mat("ChairStripe2", (1, 1, 1), tex="stripe_chair.png", rough=0.9, tex_emit=0.6), 0.01, col, rot=(math.radians(-20), 0, 0))
    cyl("DK_Table", 0.4, 0.05, (ux + 1.8, uy, 0.7), m["iron"], seg=18, col=col)
    cyl("DK_TableLeg", 0.04, 0.7, (ux + 1.8, uy, 0.35), m["iron"], seg=8, col=col)
    cyl("DK_Drink", 0.07, 0.2, (ux + 1.8, uy, 0.83), mat("Drink", (0.95, 0.75, 0.1), emit=(0.95, 0.65, 0.05), estr=0.8), seg=12, col=col)
    return {"ox": ox, "sun": (ux, uy)}


# ------------------------------------------------------------------ SET: CAR (Vandergold interior + exterior, ticket booth with green car)
def build_car_set(m):
    ox = OX["CAR"]
    col = coll("Env_Car")
    # exterior: long navy car seen from the side, track along X
    box("CR_Floor", 120, 60, 1, (ox, 5, -0.5), m["sand"], 0, col)
    box("CR_Bed", 90, 3.2, 0.12, (ox, 0, 0.06), m["ballast"], 0, col)
    body = box("CR_Body", 22, 3.0, 3.4, (ox, 0, 2.5), m["dark_blue"], 0.06, col)
    box("CR_Roof", 22.4, 3.2, 0.3, (ox, 0, 4.3), m["iron"], 0.04, col)
    box("CR_Skirt", 22, 3.1, 0.4, (ox, 0, 0.9), m["iron"], 0.03, col)
    box("CR_Stripe", 22.02, 3.02, 0.12, (ox, 0, 3.6), m["gold"], 0.01, col)
    panel("CR_Sign", 9.0, 1.4, (ox - 2.0, -1.52, 3.0), m["vander"], col, rot=(math.radians(90), 0, 0))
    for i in range(5):
        wx = ox - 8 + i * 4
        box(f"CR_WinFrame{i}", 2.2, 0.1, 1.9, (wx, -1.52, 2.1), m["gold"], 0.02, col)
        box(f"CR_Win{i}", 1.9, 0.12, 1.6, (wx, -1.55, 2.1), mat("CarWin", (1, 0.7, 0.3), emit=(1.0, 0.65, 0.3), estr=1.4), 0.01, col)
    for i in range(4):
        for s in (-1, 1):
            cyl(f"CR_Wheel{i}{s}", 0.6, 0.14, (ox - 7.5 + i * 5, s * 1.1, 0.6), m["iron"], axis="Y", seg=22, col=col)
    # interior (x offset 30): red velvet room, orange ceiling, round table, lamps, window to the canyon
    ix = ox + 40
    box("IN_Floor", 7, 6, 0.2, (ix, 0, 0), mat("CarFloor", (0.25, 0.04, 0.05), emit=(0.25, 0.04, 0.05), estr=0.5), 0, col)
    box("IN_Back", 7, 0.3, 4, (ix, 3.0, 2.1), m["velvet"], 0.02, col)
    box("IN_Ceil", 7, 6, 0.2, (ix, 0, 4.1), mat("CarCeil", (0.85, 0.4, 0.15), emit=(0.85, 0.4, 0.15), estr=0.7), 0, col)
    box("IN_WallR", 0.3, 6, 4, (ix + 3.5, 0, 2.1), m["velvet"], 0.02, col)
    box("IN_WallL", 0.3, 6, 4, (ix - 3.5, 0, 2.1), m["velvet"], 0.02, col)
    box("IN_TrimBack", 6.6, 0.1, 0.25, (ix, 2.82, 3.2), m["gold"], 0.01, col)
    box("IN_Chair", 1.6, 0.9, 0.5, (ix - 0.6, 1.5, 0.45), m["velvet"], 0.05, col)
    box("IN_ChairBack", 1.6, 0.25, 1.6, (ix - 0.6, 1.95, 1.0), m["velvet"], 0.06, col)
    cyl("IN_Table", 0.45, 0.06, (ix + 1.6, 0.7, 0.85), m["gold"], seg=20, col=col)
    cyl("IN_TableLeg", 0.05, 0.85, (ix + 1.6, 0.7, 0.42), m["gold"], seg=8, col=col)
    for i, lx in enumerate((-2.3, 2.3)):
        ball(f"IN_Lamp{i}", 0.2, (ix + lx, 2.5, 3.2), m["light"], seg=12, rings=8, col=col)
    panel("IN_Window", 2.8, 2.2, (ix + 3.34, 0.5, 2.1), m["void"], col, rot=(math.radians(90), 0, math.radians(90)))
    # ticket booth with a green "Red Canyon Short Line" car behind (x offset 80)
    tx = ox + 80
    box("TB_Floor", 14, 14, 0.2, (tx, 0, -0.1), m["wood"], 0, col)
    wm = mat("BoothWood", (0.45, 0.22, 0.1), rough=0.8, emit=(0.45, 0.22, 0.1), estr=0.18)
    box("TB_WallL", 2.9, 0.5, 5.0, (tx - 2.65, 2.6, 2.5), wm, 0.03, col)       # wall around a window opening x +-1.2, z 1.5..3.3
    box("TB_WallR", 2.9, 0.5, 5.0, (tx + 2.65, 2.6, 2.5), wm, 0.03, col)
    box("TB_WallLow", 2.4, 0.5, 1.5, (tx, 2.6, 0.75), wm, 0.03, col)
    box("TB_WallTop", 2.4, 0.5, 1.7, (tx, 2.6, 4.15), wm, 0.03, col)
    box("TB_Arch", 2.6, 0.55, 0.14, (tx, 2.55, 3.35), m["gold"], 0.01, col)
    box("TB_FloorIn", 4, 4, 0.7, (tx, 4.8, 0.35), m["wood"], 0, col)     # clerk stands on this
    box("TB_Back", 14, 0.4, 7, (tx, 7, 3.5), m["green"], 0.05, col)
    panel("TB_CarSign", 8.0, 0.9, (tx, 6.75, 5.6), m["redcanyon"], col, rot=(math.radians(90), 0, 0))
    panel("TB_Sign", 3.4, 1.06, (tx, 2.3, 4.0), m["ticket"], col, rot=(math.radians(90), 0, 0))
    box("TB_Shelf", 8, 0.9, 0.12, (tx, 2.1, 1.35), m["wood_flat"], 0.01, col)
    return {"ox": ox, "int": (ix, 1.5), "booth": (tx, 3.6)}


# ------------------------------------------------------------------ SET: GAP (expansion gap close-up, calendar crate, flag)
def build_gap_set(m, hot):
    ox = OX["GAP"]
    col = coll("Env_Gap")
    box("GP_Bed", 40, 14, 0.3, (ox, 2, -0.15), m["ballast"], 0, col)
    box("GP_Ground", 120, 80, 0.3, (ox, 10, -0.4), m["sand"], 0, col)
    panel("GP_Wall", 120, 40, (ox, 16, 17), m["rock_big"], col, rot=(math.radians(90), 0, 0))
    specs = [(ox + x * 0.62, 0.0, 0.03, 0.2, 2.2, 0.12) for x in range(-10, 11)]
    merged_boxes("GP_Ties", specs, m["tie"], col)
    railA = box("GP_RailA", 3.0, 0.075, 0.17, (ox - 1.5, 0.0, 0.2), hot["L"], 0.01, col)
    railB = box("GP_RailB", 3.0, 0.075, 0.17, (ox + 1.5, 0.0, 0.2), hot["L"], 0.01, col)
    box("GP_BaseA", 3.0, 0.17, 0.04, (ox - 1.5, 0.0, 0.1), hot["L"], 0, col)
    baseB = box("GP_BaseB", 3.0, 0.17, 0.04, (ox + 1.5, 0.0, 0.1), hot["L"], 0, col)
    # calipers laid across the gap + coin standing in it
    cal = box("GP_Calipers", 0.28, 0.02, 0.012, (ox, -0.05, 0.31), m["steel"], 0, col)
    coin = cyl("GP_Coin", 0.13, 0.02, (ox, 0.0, 0.34), m["coin"], axis="Y", seg=24, col=col)
    # crate with calendar + thermometer + flag
    box("GP_Crate", 1.4, 0.9, 1.0, (ox + 0.6, 4.2, 0.5), m["crate"], 0.03, col)
    for k in range(4):
        box(f"GP_Slat{k}", 1.42, 0.02, 0.07, (ox + 0.6, 3.74, 0.18 + k * 0.24), mat("SlatDark", (0.04, 0.3, 0.17), emit=(0.04, 0.3, 0.17), estr=0.2), 0, col)
    calm = panel("GP_CalMay", 0.5, 0.62, (ox + 1.05, 3.72, 0.62), m["cal_may"], col, rot=(math.radians(90), 0, 0))
    calj = panel("GP_CalJul", 0.5, 0.62, (ox + 1.05, 3.72, 0.62), m["cal_jul"], col, rot=(math.radians(90), 0, 0))
    box("GP_ThermoBack", 0.2, 0.03, 0.8, (ox + 0.2, 3.72, 0.62), m["white"], 0.01, col)
    merc = box("GP_Mercury", 0.05, 0.034, 0.5, (ox + 0.2, 3.7, 0.4), m["merc"], 0, col)
    cyl("GP_FlagPole", 0.02, 1.6, (ox - 0.6, 4.6, 1.3), m["iron"], seg=8, col=col)
    panel("GP_Flag", 0.7, 0.45, (ox - 0.25, 4.6, 1.85), m["flag"], col, rot=(math.radians(90), 0, 0))
    return {"ox": ox, "railB": railB, "baseB": baseB, "coin": coin, "calm": calm, "calj": calj, "merc": merc, "cal": cal}
