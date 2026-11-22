"""rail_rocks.py - chunky canyon walls (stacked, rotated rock blocks) + desert clutter (cacti, bushes, boulders)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import casino_scene as cs
from casino_scene import mesh_ob, finish, link, coll, ball, cyl


def canyon_wall(name, base, along, normal, length, height, m_rock, m_dark, col, seed=1, depth=(3.0, 7.0), jitter=1.3, col_w=(3.0, 6.0), tier_h=(3.5, 8.0)):
    """base = point on the wall's inner line at z=0; along = unit vector along the wall; normal = unit vector pointing INTO the canyon.
    Builds columns of stacked rotated blocks whose inner faces jitter in/out (ledges, overhangs). Two meshes (light/dark rock)."""
    r = random.Random(seed)
    along, normal = Vector(along).normalized(), Vector(normal).normalized()
    yaw = math.atan2(along.y, along.x)
    bms = [bmesh.new(), bmesh.new()]
    s = 0.0
    while s < length:
        w = r.uniform(*col_w)
        z = 0.0
        top = height * r.uniform(0.55, 1.0)
        k = 0
        while z < top:
            h = r.uniform(*tier_h)
            d = r.uniform(*depth)
            j = r.uniform(-jitter, jitter) + (0.35 * k if k > 1 else 0.0) * r.choice((-1, 1, 1))
            c = Vector(base) + along * (s + w / 2) + normal * (j - d / 2) + Vector((0, 0, z + h / 2))
            bm = bms[1 if r.random() < 0.22 else 0]
            res = bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
            rot = Matrix.Rotation(yaw + math.radians(r.uniform(-7, 7)), 3, "Z")
            for v in res["verts"]:
                p = Vector((v.co.x * w * 1.04, v.co.y * d, v.co.z * h * 1.02))
                v.co = rot @ p + c
            z += h * r.uniform(0.82, 0.98)
            k += 1
        s += w * r.uniform(0.8, 0.95)
    out = []
    for i, (bm, mm) in enumerate(zip(bms, (m_rock, m_dark))):
        ob = mesh_ob(f"{name}_{i}", bm, (0, 0, 0), col)
        finish(ob, mm, 0.18, seg=2, smooth=False)
        out.append(ob)
    return out


def cactus(name, loc, m, col, scale=1.0, seed=0):
    r = random.Random(seed)
    x, y, z = loc
    h = r.uniform(1.4, 2.4) * scale
    cyl(name + "_T", 0.17 * scale, h, (x, y, z + h / 2), m, seg=10, col=col)
    ball(name + "_Top", 0.17 * scale, (x, y, z + h), m, seg=10, rings=6, col=col)
    for i, sgn in enumerate((-1, 1)):
        if r.random() < 0.75:
            ah = r.uniform(0.5, 0.9) * scale
            az = z + h * r.uniform(0.35, 0.65)
            cyl(f"{name}_A{i}", 0.1 * scale, 0.45 * scale, (x + sgn * 0.3 * scale, y, az), m, axis="X", seg=8, col=col)
            cyl(f"{name}_B{i}", 0.1 * scale, ah, (x + sgn * 0.5 * scale, y, az + ah / 2), m, seg=8, col=col)
            ball(f"{name}_C{i}", 0.1 * scale, (x + sgn * 0.5 * scale, y, az + ah), m, seg=8, rings=5, col=col)


def clutter(name, ox, y0, y1, xs, m_green, m_rock, m_bush, col, seed=3, n_cactus=10, n_bush=26, n_boulder=22):
    """xs = list of (xmin, xmax) bands where objects may stand (keep clear of the rails)"""
    r = random.Random(seed)
    pick = lambda: ox + (lambda b: r.uniform(*b))(r.choice(xs))
    for i in range(n_cactus):
        cactus(f"{name}_Cac{i}", (pick(), r.uniform(y0, y1), 0.0), m_green, col, r.uniform(0.9, 1.6), seed + i)
    for i in range(n_bush):
        x, y, s = pick(), r.uniform(y0, y1), r.uniform(0.25, 0.55)
        ball(f"{name}_Bush{i}", s, (x, y, s * 0.45), m_bush, scale=(1.3, 1.0, 0.7), seg=10, rings=6, col=col)
    for i in range(n_boulder):
        x, y, s = pick(), r.uniform(y0, y1), r.uniform(0.25, 1.1)
        o = ball(f"{name}_Bld{i}", s, (x, y, s * 0.35), m_rock, scale=(1.2, 1.0, 0.75), seg=9, rings=6, col=col)
        o.rotation_euler = (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), r.uniform(0, 6.28))
