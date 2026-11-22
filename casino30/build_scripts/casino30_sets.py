"""casino30_sets.py - the extra sets for seconds 5-30 of the reference (all real bpy geometry).
Sets are built far apart in X so each shot is a hard camera cut:
  hero casino floor  x ~ 0     (existing)        close-up (bill/validator) x = +20
  machine interior   x = -20                      reel-strip 'par sheet'    x = -40
  one-click-short wheel close-up x = -60
"""
import bpy, math, random
from mathutils import Vector
import casino_scene as cs
import casino_char as ch
from casino_scene import mat, box, cyl, ball, torus, panel, coll, link

FONT_PATH = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FPS = 30
F = lambda t: int(round(1 + t * FPS))
CU_X, IN_X, ST_X, WH_X = 20.0, -20.0, -40.0, -60.0


# ------------------------------------------------------------------ helpers
_font = None
def font():
    global _font
    if _font is None:
        _font = bpy.data.fonts.load(FONT_PATH)
    return _font


def text(name, body, size, loc, m, col, rot=(math.pi / 2, 0, 0), align="CENTER", parent=None):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.font, cu.size, cu.align_x, cu.align_y = body, font(), size, align, "CENTER"
    ob = bpy.data.objects.new(name, cu)
    ob.location, ob.rotation_euler = loc, rot
    cu.materials.append(m)
    link(ob, col)
    if parent:
        ob.parent = parent
    return ob


def keyed_visible(ob, t0, t1):
    """Render-visible only for t0 <= t < t1 (seconds). t1=None keeps it visible to the end."""
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    if t0 > 0:
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=F(t0))
    if t1 is not None:
        ob.hide_render = True
        ob.keyframe_insert("hide_render", frame=F(t1))
    if t0 <= 0:   # visible from frame 1
        ob.hide_render = False
        ob.keyframe_insert("hide_render", frame=1)
    for fc in cs.fcurves_of(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def key_loc(ob, pts):
    """pts: list of (t seconds, (x,y,z)); smooth interpolation."""
    for t, p in pts:
        ob.location = p
        ob.keyframe_insert("location", frame=F(t))


def key_rot(ob, axis, pts, linear=False):
    for t, a in pts:
        ob.rotation_euler[axis] = a
        ob.keyframe_insert("rotation_euler", index=axis, frame=F(t))
    if linear:
        for fc in cs.fcurves_of(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def area(name, loc, target_loc, energy, size, color, col):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = energy, size, color
    ob = bpy.data.objects.new(name, d)
    ob.location = loc
    link(ob, col)
    tg = bpy.data.objects.new(name + "_T", None)
    tg.location = target_loc
    link(tg, col)
    c = ob.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = tg, "TRACK_NEGATIVE_Z", "UP_Y"
    return ob


def tube_curve(name, pts, r, m, col):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", r, 2
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    cu.materials.append(m)
    link(ob, col)
    return ob


# ------------------------------------------------------------------ main casino floor additions
def build_ceiling_and_sign(env):
    wood = mat("WoodDark", (0.22, 0.085, 0.035), rough=0.5, coat=0.2)
    fl = panel("Ceiling", 20, 14, (0, 1.5, 5.0), mat("CeilingMat", tex="ceiling.png", rough=0.6, tex_emit=0.15, tex_scale=(4, 3)), env, rot=(math.radians(-90), 0, 0))
    for i, y in enumerate((-3.6, -1.8, 0.0, 1.8, 3.6, 5.4)):
        box(f"CeilBeamX{i}", 18, 0.14, 0.18, (0, y, 4.91), wood, 0.01, env)
    for i, x in enumerate([-7.2 + 1.8 * k for k in range(9)]):
        box(f"CeilBeamY{i}", 0.14, 12.0, 0.18, (x, 1.5, 4.91), wood, 0.01, env)
    lamp = mat("CeilLamp", (1.0, 0.72, 0.35), emit=(1.0, 0.7, 0.3), estr=6.0)
    for xi in range(8):
        for yi in range(5):
            x, y = -6.3 + 1.8 * xi, -2.7 + 1.8 * yi
            cyl(f"CeilLamp{xi}_{yi}", 0.2, 0.03, (x, y, 4.93), lamp, seg=24, col=env)
    # progressive jackpot sign hung over the front row
    dark = mat("SignBody", (0.07, 0.015, 0.012), rough=0.4)
    gold = mat("Gold", (1.0, 0.68, 0.18), metallic=1.0, rough=0.22)
    box("SignBody", 3.7, 0.16, 0.95, (0.1, 1.15, 3.55), dark, 0.012, env)
    box("SignFrame", 3.8, 0.12, 1.05, (0.1, 1.2, 3.55), gold, 0.012, env)
    for sx in (-1.6, 1.6):
        box(f"SignRod{sx}", 0.03, 0.03, 1.3, (0.1 + sx, 1.15, 4.35), dark, 0, env)
    panel("SignTitle", 3.4, 0.425, (0.1, 1.06, 3.80), mat("MatSign", tex="progressive.png", tex_emit=0.5, rough=0.4), env)
    led = mat("LEDRed", (1.0, 0.08, 0.05), emit=(1.0, 0.1, 0.05), estr=6.0)
    for k, t in enumerate([4.0 + 0.5 * i for i in range(10)]):
        val = 1284531.86 + (t - 5.5) * 3.38
        s = "${:,.2f}".format(val)
        ob = text(f"SignDigits{k}", s, 0.30, (0.1, 1.05, 3.40), led, env)
        keyed_visible(ob, t, t + 0.5)


# ------------------------------------------------------------------ close-up: bill into validator, CREDITS LED
def build_closeup(sc):
    col = coll("SetCloseup")
    red = mat("MachineRed", (0.62, 0.015, 0.02), rough=0.22, coat=0.8, spec=0.6)
    dark = mat("MachineDark", (0.05, 0.015, 0.015), rough=0.5)
    black = mat("Validator", (0.025, 0.025, 0.03), rough=0.35, coat=0.4)
    chrome = mat("Chrome", (0.9, 0.9, 0.92), metallic=1.0, rough=0.12)
    green = mat("SlotGreen", (0.2, 1.0, 0.3), emit=(0.2, 1.0, 0.3), estr=5.0)
    limb = mat("Limb", (0.15, 0.075, 0.06), rough=0.8, emit=(0.15, 0.075, 0.06), estr=0.35, spec=0.05)
    X = CU_X
    box("CU_Wall", 6, 0.1, 3.0, (X, 1.4, 1.2), dark, 0, col)
    box("CU_Floor", 6, 4, 0.1, (X, 0.0, -0.1), mat("CU_FloorMat", (0.12, 0.02, 0.025), rough=0.5), 0, col)
    box("CU_Deck", 1.6, 0.9, 0.12, (X, 0.0, 0.30), red, 0.015, col, rot=(math.radians(-12), 0, 0))
    box("CU_DeckEdge", 1.62, 0.03, 0.05, (X, -0.46, 0.20), chrome, 0.005, col)
    # SPIN button
    spin = mat("SpinRed", (1, 0.05, 0.05), emit=(1, 0.05, 0.03), estr=2.0, coat=0.8, rough=0.2)
    cyl("CU_SpinBase", 0.13, 0.04, (X - 0.12, 0.10, 0.395), chrome, seg=40, bevel=0.01, col=col)
    cyl("CU_Spin", 0.10, 0.07, (X - 0.12, 0.10, 0.435), spin, seg=40, bevel=0.02, col=col)
    text("CU_SpinText", "SPIN", 0.05, (X - 0.12, 0.10, 0.474), mat("TextWhite", (1, 1, 1), emit=(1, 1, 1), estr=1.2), col, rot=(0, 0, math.radians(60)))
    # bill validator (right) with a green slot facing the bill
    box("CU_Validator", 0.34, 0.44, 0.30, (X + 0.55, 0.30, 0.50), black, 0.012, col)
    box("CU_SlotGlow", 0.03, 0.24, 0.05, (X + 0.372, 0.30, 0.56), green, 0, col)
    panel("CU_ValLabel", 0.30, 0.15, (X + 0.55, 0.30, 0.652), mat("MatVal", tex="validator.png", tex_emit=0.5, rough=0.4), col, rot=(math.radians(90), 0, 0))
    # bill
    bill = panel("CU_Bill", 0.62, 0.264, (X - 0.40, 0.30, 0.575), mat("MatBill", tex="bill.png", tex_emit=0.35, rough=0.55), col, rot=(math.radians(90), 0, 0))
    key_loc(bill, [(11.5, (X - 0.55, 0.30, 0.575)), (12.4, (X - 0.30, 0.30, 0.575)), (13.4, (X + 0.04, 0.30, 0.575))])
    hand = ball("CU_Hand", 0.10, (X - 0.95, 0.30, 0.60), limb, scale=(1.1, 1, 0.8), col=col)
    arm = cyl("CU_Arm", 0.045, 1.4, (X - 1.65, 0.30, 0.62), limb, axis="X", seg=16, col=col)
    for ob, dx in ((hand, -0.95), (arm, -1.65)):
        key_loc(ob, [(11.5, (X + dx - 0.15, 0.30, ob.location.z)), (12.4, (X + dx + 0.10, 0.30, ob.location.z)), (13.4, (X + dx + 0.44, 0.30, ob.location.z))])
    # CREDITS display (13.5-14.0)
    box("CU_LedBox", 0.60, 0.16, 0.36, (X - 0.50, 0.55, 0.62), black, 0.01, col)
    dim = mat("LEDDim", (0.3, 0.03, 0.02), emit=(1.0, 0.1, 0.05), estr=0.35)
    lit = mat("LEDLit", (1.0, 0.08, 0.05), emit=(1.0, 0.1, 0.05), estr=7.0)
    text("CU_LedDim", "88", 0.24, (X - 0.50, 0.465, 0.60), dim, col)
    text("CU_LedLit", "82", 0.24, (X - 0.50, 0.46, 0.60), lit, col)
    text("CU_LedTitle", "CREDITS", 0.055, (X - 0.50, 0.465, 0.76), mat("TextOrange", (1, 0.5, 0.1), emit=(1, 0.5, 0.1), estr=2.0), col)
    area("CU_Key", (X - 0.2, -1.4, 1.7), (X, 0.2, 0.45), 160, 1.6, (1.0, 0.78, 0.55), col)
    area("CU_Fill", (X + 0.9, -0.9, 0.9), (X, 0.3, 0.5), 45, 1.2, (1.0, 0.45, 0.30), col)
    area("CU_Green", (X + 0.2, -0.3, 0.9), (X + 0.4, 0.3, 0.5), 10, 0.5, (0.4, 1.0, 0.5), col)


# ------------------------------------------------------------------ inside the machine: reel drums + PCB + label
def build_inside(sc):
    col = coll("SetInside")
    X = IN_X
    card = mat("Cardboard", (0.78, 0.58, 0.38), rough=0.9, emit=(0.78, 0.58, 0.38), estr=0.3, spec=0.05)
    card2 = mat("Cardboard2", (0.9, 0.72, 0.5), rough=0.9, emit=(0.9, 0.72, 0.5), estr=0.35, spec=0.05)
    pcb = mat("PCB", (0.08, 0.5, 0.22), rough=0.45, emit=(0.08, 0.5, 0.22), estr=0.35)
    chip = mat("Chip", (0.03, 0.03, 0.035), rough=0.4)
    wire = mat("WireOrange", (1.0, 0.4, 0.05), rough=0.4, emit=(1.0, 0.4, 0.05), estr=1.0)
    yel = mat("LabelYellow", (1.0, 0.82, 0.15), rough=0.5, emit=(1.0, 0.8, 0.1), estr=0.8)
    panel("IN_Back", 3.2, 2.8, (X, 0.75, 1.2), card, col)
    panel("IN_Left", 2.0, 2.8, (X - 1.5, -0.2, 1.2), card, col, rot=(0, 0, math.radians(90)))
    panel("IN_Top", 3.2, 2.0, (X, -0.1, 2.35), card, col, rot=(math.radians(90), 0, 0))
    panel("IN_Door", 1.2, 2.4, (X + 1.25, -0.35, 1.2), card2, col, rot=(0, 0, math.radians(-62)))
    box("IN_Shelf", 1.5, 0.7, 0.05, (X - 0.05, 0.4, 1.15), card2, 0.004, col)
    box("IN_LabelBase", 1.32, 0.02, 0.1, (X - 0.05, 0.045, 1.09), yel, 0.002, col)
    text("IN_Label", "LUCKY 7s REEL UNIT", 0.05, (X - 0.05, 0.032, 1.09), mat("TextBlack", (0.05, 0.03, 0.02), rough=0.8), col)
    for i, (rx, tx) in enumerate(((-0.40, "reel_a.png"), (0.0, "reel_b.png"), (0.40, "reel_c.png"))):
        r = cs.make_reel(f"IN_Reel{i}", (X + rx, 0.38, 1.46), tx, col, r=0.19, width=0.34)
        r.scale = (1.0, 1.0, 1.0)
        r.rotation_euler[0] = math.radians(35 * i + 10)
    panel("IN_PCB", 1.3, 0.95, (X - 0.1, 0.72, 0.55), pcb, col)
    rnd = random.Random(11)
    for i in range(9):
        box(f"IN_Chip{i}", rnd.uniform(0.07, 0.16), 0.02, rnd.uniform(0.05, 0.1), (X - 0.1 + rnd.uniform(-0.5, 0.5), 0.70, 0.55 + rnd.uniform(-0.32, 0.32)), chip, 0.002, col)
    for i, x0 in enumerate((-0.35, -0.15, 0.05, 0.25)):
        tube_curve(f"IN_Wire{i}", [(X + x0, 0.68, 0.95), (X + x0 + 0.06, 0.52, 1.05), (X + x0 - 0.02, 0.42, 1.14)], 0.012, wire, col)
    area("IN_Key", (X - 0.2, -1.3, 2.0), (X, 0.4, 1.2), 140, 1.8, (1.0, 0.85, 0.6), col)
    area("IN_Back", (X + 0.0, 0.2, 1.6), (X, 0.5, 1.4), 60, 1.2, (1.0, 0.8, 0.4), col)


# ------------------------------------------------------------------ the reel-strip par sheet, stamps, counter, plunger
STRIP_N = 28
HEAD_FRAC, STRIP_ZH = 480 / 8192, 8.0


def strip_row_z(k):
    """local z of row k's centre on the tall sheet (sheet is 8 m tall, local origin at its centre)."""
    row_h = (8192 - 480) // STRIP_N / 8192
    return STRIP_ZH / 2 - (HEAD_FRAC + (k - 0.5) * row_h) * STRIP_ZH


def strip_world(local):
    a = math.radians(-14)
    return Vector((ST_X + local[0], local[2] * -math.sin(a) + local[1] * math.cos(a), 4.2 + local[1] * math.sin(a) + local[2] * math.cos(a)))


def build_strip(sc):
    col = coll("SetStrip")
    X = ST_X
    root = bpy.data.objects.new("ST_Root", None)
    root.location, root.rotation_euler = (X, 0, 4.2), (math.radians(-14), 0, 0)
    link(root, col)
    paper = panel("ST_Paper", 1.0, STRIP_ZH, (0, 0, 0), mat("MatStrip", tex="strip.png", tex_emit=0.55, rough=0.9, spec=0.0), col)
    paper.parent = root
    card = mat("Cardboard", (0.78, 0.58, 0.38), rough=0.9, emit=(0.78, 0.58, 0.38), estr=0.3, spec=0.05)
    pcb = mat("PCB", (0.08, 0.5, 0.22), rough=0.45, emit=(0.08, 0.5, 0.22), estr=0.35)
    black = mat("Validator", (0.025, 0.025, 0.03), rough=0.35, coat=0.4)
    green = mat("SlotGreen", (0.2, 1.0, 0.3), emit=(0.2, 1.0, 0.3), estr=5.0)
    wire = mat("WireOrange", (1.0, 0.4, 0.05), rough=0.4, emit=(1.0, 0.4, 0.05), estr=1.0)
    panel("ST_Back", 9, 12, (X, 1.2, 4.5), card, col)
    panel("ST_PCB", 1.4, 4.5, (X - 1.1, 0.9, 3.0), pcb, col)
    for i in range(4):
        tube_curve(f"ST_Wire{i}", [(X - 0.8 - 0.1 * i, 0.8, 1.0), (X - 0.78 - 0.1 * i, 0.75, 3.0), (X - 0.82 - 0.1 * i, 0.7, 5.0)], 0.012, wire, col)
    box("ST_Validator", 0.5, 0.35, 0.6, (X - 1.3, 0.2, 1.4), black, 0.01, col)
    box("ST_Slot", 0.34, 0.02, 0.05, (X - 1.3, 0.017, 1.5), green, 0, col)
    text("ST_Dollar", "$", 0.14, (X - 1.3, 0.012, 1.25), mat("TextGreen", (0.2, 1, 0.3), emit=(0.2, 1, 0.3), estr=3.0), col)
    # stamps on rows 10-27, revealed 23.0 -> 25.4 s
    st_m = mat("MatStamp", tex="stamp.png", tex_emit=0.9, rough=0.6)
    for k in range(10, STRIP_N):
        ob = panel(f"ST_Stamp{k}", 0.30, 0.102, (0.26, -0.004, strip_row_z(k)), st_m, col)
        ob.parent = root
        keyed_visible(ob, 23.0 + (k - 10) * 0.14, None)
    # jackpot multiplier badge on row 9, appears with the first stamp
    ob = text("ST_X1", "x1", 0.09, (0.43, -0.006, strip_row_z(9)), mat("TextRedBold", (0.85, 0.05, 0.03), emit=(0.85, 0.05, 0.03), estr=1.5), col, parent=root)
    # counter x00..x14
    cbox = box("ST_CounterBox", 0.34, 0.1, 0.17, (-0.78, 0.1, strip_row_z(13)), mat("CounterCream", (0.95, 0.92, 0.82), rough=0.6), 0.008, col)
    cbox.parent = root
    steps = [(22.9, "x00"), (23.5, "x01"), (23.9, "x03"), (24.3, "x07"), (24.7, "x10"), (25.0, "x12"), (25.35, "x14")]
    for i, (t, s) in enumerate(steps):
        o = text(f"ST_Count{i}", s, 0.085, (-0.78, 0.04, strip_row_z(13)), mat("TextBlack", (0.05, 0.03, 0.02), rough=0.8), col, parent=root)
        keyed_visible(o, t, steps[i + 1][0] if i + 1 < len(steps) else None)
    # red plunger beside the sheet
    pbox = box("ST_PlungerBox", 0.4, 0.2, 0.3, (0.78, 0.0, strip_row_z(11)), mat("PlungerBox", (0.85, 0.2, 0.1), rough=0.4, coat=0.5), 0.01, col)
    pbox.parent = root
    knob = ball("ST_PlungerKnob", 0.07, (0.78, -0.17, strip_row_z(11)), mat("PlungerRed", (0.9, 0.05, 0.03), emit=(0.9, 0.05, 0.03), estr=1.0, coat=0.8, rough=0.2), col=col)
    knob.parent = root
    stem = cyl("ST_PlungerStem", 0.02, 0.2, (0.78, -0.1, strip_row_z(11)), mat("Chrome", (0.9, 0.9, 0.92), metallic=1.0, rough=0.12), axis="Y", seg=12, col=col)
    stem.parent = root
    for t in (23.0, 23.5, 23.9, 24.3, 24.7, 25.0, 25.35):
        for dy in (0.0, 0.04):
            knob.location = (0.78, -0.17 + dy, strip_row_z(11))
            knob.keyframe_insert("location", frame=F(t) + (0 if dy == 0 else 3))
    area("ST_Key", (X + 0.4, -2.2, 6.0), (X, 0.0, 4.2), 380, 4.0, (1.0, 0.82, 0.6), col)
    area("ST_Low", (X + 0.4, -2.0, 1.5), (X, 0.0, 2.0), 160, 3.0, (1.0, 0.8, 0.55), col)
    return root


# ------------------------------------------------------------------ wheel close-up and the hero x-ray overlay
def build_wheel(sc):
    col = coll("SetWheel")
    X = WH_X
    card = mat("Cardboard", (0.78, 0.58, 0.38), rough=0.9, emit=(0.78, 0.58, 0.38), estr=0.3, spec=0.05)
    pcb = mat("PCB", (0.08, 0.5, 0.22), rough=0.45, emit=(0.08, 0.5, 0.22), estr=0.35)
    red = mat("MachineRed", (0.62, 0.015, 0.02), rough=0.22, coat=0.8, spec=0.6)
    panel("WH_Back", 6, 4, (X, 0.9, 1.0), card, col)
    panel("WH_PCB", 1.4, 1.2, (X - 0.2, 0.7, 2.0), pcb, col)
    torus("WH_Ring", 0.60, 0.035, (X, 0.0, 1.0), red, col=col)
    ring = bpy.data.objects["WH_Ring"]
    ring.rotation_euler = (math.radians(90), 0, 0)
    wheel_m = mat("MatWheel", tex="wheel.png", tex_emit=0.35, rough=0.5)
    w = panel("WH_Wheel", 1.14, 1.14, (X, -0.02, 1.0), wheel_m, col)
    key_rot(w, 1, [(25.5, 0.0), (26.0, math.radians(-110))], linear=True)
    area("WH_Key", (X - 0.3, -1.6, 2.2), (X, 0.0, 1.0), 140, 1.6, (1.0, 0.85, 0.65), col)
    # hero overlay: wheel on the lower body + cyan wire cage ("x-ray"), visible 26.0 s -> end
    ov = coll("HeroXray")
    hw = panel("XR_Wheel", 0.80, 0.80, (0.25, -0.05, 0.50), wheel_m, ov)
    key_rot(hw, 1, [(26.0, 0.0), (30.0, math.radians(-460))], linear=True)
    keyed_visible(hw, 26.0, None)
    cage = box("XR_Cage", 1.0, 0.82, 1.98, (0.25, 0.36, 0.99), mat("CageCyan", (0.1, 0.7, 1.0), emit=(0.1, 0.7, 1.0), estr=3.5), 0.0, ov)
    wf = cage.modifiers.new("Wire", "WIREFRAME")
    wf.thickness, wf.use_replace = 0.012, True
    keyed_visible(cage, 26.0, None)
    return hw
