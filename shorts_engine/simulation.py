"""Physics scene builders (requires bpy).

Each simulation type registers a builder in ``SIMULATORS``. Adding soft body / rigid body
later means adding a function here, not rewriting the engine.
"""

from __future__ import annotations

import bpy

from . import materials

# (top_z of the object when resting on the ground at z=0)
_OBJECT_TOP = {"sphere": 2.0, "cube": 2.0, "cylinder": 2.0, "cone": 2.0, "torus": 0.8}


def create_ground(scene, color, size: float = 40.0, catcher: bool = False):
    half = size / 2
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("Ground", mesh)
    scene.collection.objects.link(obj)
    obj.modifiers.new("Collision", "COLLISION")
    materials.assign(obj, materials.principled("GroundMat", color, 0.0, 0.8))
    if catcher:                                  # studio look: the floor shows only shadows over the background (no horizon line)
        obj.is_shadow_catcher = True
    return obj


def create_collider(scene, object_type: str, scale: float = 1.0, xy=(0.0, 0.0), name: str = "Collider"):
    """Create the object the cloth falls on. Returns (object, top_z). ``scale``/``xy`` place extra objects."""
    ops = bpy.ops.mesh
    if object_type == "sphere":
        ops.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(0, 0, 1.0))
    elif object_type == "cube":
        ops.primitive_cube_add(size=2.0, location=(0, 0, 1.0))
    elif object_type == "cylinder":
        ops.primitive_cylinder_add(radius=0.9, depth=2.0, vertices=64, location=(0, 0, 1.0))
    elif object_type == "cone":
        ops.primitive_cone_add(radius1=1.0, radius2=0.0, depth=2.0, vertices=64, location=(0, 0, 1.0))
    elif object_type == "torus":
        ops.primitive_torus_add(
            major_radius=1.0, minor_radius=0.4, major_segments=64, minor_segments=24, location=(0, 0, 0.4)
        )
    else:
        raise ValueError(f"unsupported object type: {object_type}")
    obj = bpy.context.active_object
    obj.name = name
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    if scale != 1.0 or xy != (0.0, 0.0):
        obj.scale = (scale, scale, scale)
        obj.location = (xy[0], xy[1], obj.location.z * scale)
    obj.modifiers.new("Collision", "COLLISION")
    obj.collision.thickness_outer = 0.01
    obj.collision.cloth_friction = 5.0
    return obj, _OBJECT_TOP[object_type] * scale


def create_cloth_mesh(scene, segments: int, size: float, z: float):
    """n x n grid of quads (so faces == segments**2), centred at the origin."""
    n = segments
    step = size / n
    half = size / 2
    verts = [(-half + i * step, -half + j * step, z) for j in range(n + 1) for i in range(n + 1)]
    row = n + 1
    faces = [
        (j * row + i, j * row + i + 1, (j + 1) * row + i + 1, (j + 1) * row + i)
        for j in range(n)
        for i in range(n)
    ]
    mesh = bpy.data.meshes.new("Cloth")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Cloth", mesh)
    scene.collection.objects.link(obj)
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    return obj


def add_cloth_physics(obj, physics, frame_end: int):
    mod = obj.modifiers.new("Cloth", "CLOTH")
    s = mod.settings
    s.quality = physics.quality
    s.mass = physics.mass
    s.tension_stiffness = physics.tension
    s.compression_stiffness = physics.compression
    s.shear_stiffness = physics.shear
    s.bending_stiffness = physics.bending
    s.air_damping = physics.air_damping
    c = mod.collision_settings
    c.use_collision = True
    c.distance_min = physics.collision_distance
    c.use_self_collision = physics.self_collision
    c.self_distance_min = physics.collision_distance
    cache = mod.point_cache
    cache.frame_start = 1
    cache.frame_end = frame_end
    return mod


def add_cloth_look(obj, style: str, segments: int, size: float, material):
    """Wireframe look makes the mesh resolution visible; solid is plain cloth."""
    if style == "wireframe":
        wire = obj.modifiers.new("Wire", "WIREFRAME")
        cell = size / segments
        wire.thickness = max(0.003, cell * 0.18)
        wire.use_replace = True
    else:
        solid = obj.modifiers.new("Solidify", "SOLIDIFY")
        solid.thickness = 0.02
    materials.assign(obj, material)


def bake(scene, cloth_obj, frame_start: int, frame_end: int) -> str:
    """Bake the cloth cache. Returns which method succeeded: 'ptcache' or 'frame_step'."""
    mod = cloth_obj.modifiers["Cloth"]
    cache = mod.point_cache
    cache.frame_start = frame_start
    cache.frame_end = frame_end
    cache.use_disk_cache = True  # requires the .blend to be saved first
    try:
        with bpy.context.temp_override(scene=scene, active_object=cloth_obj, point_cache=cache):
            bpy.ops.ptcache.bake(bake=True)
        if cache.is_baked:
            return "ptcache"
    except RuntimeError as exc:
        print(f"ptcache.bake failed ({exc}); falling back to frame stepping")
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
    return "frame_step"


def build_cloth_stage(scene, cfg, stage):
    """Collider + ground + cloth. Returns the cloth object."""
    scene.gravity = (0.0, 0.0, -cfg.physics.gravity)
    create_ground(scene, cfg.material.ground_color)
    collider, top_z = create_collider(scene, cfg.object.type)
    materials.assign(
        collider, materials.principled("ObjectMat", cfg.material.object_color, 0.0, cfg.material.object_roughness)
    )
    cloth = create_cloth_mesh(scene, stage.segments, cfg.object.cloth_size, top_z + cfg.object.cloth_drop_height)
    add_cloth_physics(cloth, cfg.physics, cfg.frame_count)
    cloth_mat = materials.principled(
        "ClothMat", cfg.material.cloth_color, cfg.material.cloth_metallic, cfg.material.cloth_roughness
    )
    add_cloth_look(cloth, cfg.material.cloth_style, stage.segments, cfg.object.cloth_size, cloth_mat)
    return cloth


# ---------------------------------------------------------------------------------------------- rigid bodies
_PALETTE = [(0.92, 0.26, 0.21, 1), (0.98, 0.65, 0.12, 1), (0.25, 0.70, 0.35, 1), (0.16, 0.50, 0.90, 1),
            (0.58, 0.32, 0.82, 1), (0.95, 0.95, 0.95, 1)]


def _activate(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def make_rigid(obj, kind: str, shape: str, friction: float, restitution: float, mass: float = 1.0, margin: float = 0.0):
    """Give ``obj`` a rigid body ('ACTIVE' moves, 'PASSIVE' is a fixed collider)."""
    _activate(obj)
    bpy.ops.rigidbody.object_add(type=kind)
    rb = obj.rigid_body
    rb.collision_shape = shape
    if shape == "MESH":
        rb.mesh_source = "BASE"
    rb.friction, rb.restitution, rb.mass = friction, restitution, mass
    rb.use_margin = True
    rb.collision_margin = margin
    return rb


def translucent(name: str, color, alpha: float = 0.18):
    mat = materials.principled(name, color, 0.0, 0.2)
    mat.node_tree.nodes.get("Principled BSDF").inputs["Alpha"].default_value = alpha
    return mat


def setup_rigid_world(scene, cfg, frames: int, substeps: int = 30, iterations: int = 40):
    scene.gravity = (0.0, 0.0, -cfg.physics.gravity)
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rw = scene.rigidbody_world
    rw.substeps_per_frame, rw.solver_iterations = substeps, iterations
    rw.point_cache.frame_start, rw.point_cache.frame_end = 1, frames
    return rw


def create_floor_and_wall(scene, cfg, radius: float, wall_height: float, friction: float, restitution: float):
    """Floor plane plus an optional translucent wall (open cylinder) that keeps objects inside the frame."""
    floor = create_ground(scene, cfg.material.ground_color, catcher=hasattr(cfg, 'experiment'))
    floor.modifiers.clear()
    make_rigid(floor, "PASSIVE", "BOX", friction, restitution)
    wall = None
    if wall_height > 0:
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=wall_height, vertices=64, end_fill_type="NOTHING",
                                            location=(0, 0, wall_height / 2))
        wall = bpy.context.active_object
        wall.name = "Wall"
        sol = wall.modifiers.new("Thick", "SOLIDIFY")
        sol.thickness = 0.12
        sol.offset = 1.0
        _activate(wall)
        bpy.ops.object.modifier_apply(modifier="Thick")
        make_rigid(wall, "PASSIVE", "MESH", friction, restitution)
        materials.assign(wall, translucent("WallMat", [0.75, 0.8, 0.85, 1.0]))
    return floor, wall


def _primitive(shape: str, radius: float):
    ops = bpy.ops.mesh
    if shape == "cube":
        ops.primitive_cube_add(size=2 * radius)
        return "BOX"
    if shape == "cylinder":
        ops.primitive_cylinder_add(radius=radius, depth=2 * radius, vertices=24)
        return "CYLINDER"
    ops.primitive_uv_sphere_add(radius=radius, segments=24, ring_count=12)
    return "SPHERE"


def _smooth(obj):
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))


def build_balls_stage(scene, cfg, stage):
    from .templates import spawn_positions
    p = {**cfg.params, **stage.params}
    n = p["balls"]
    setup_rigid_world(scene, cfg, cfg.frame_count)
    create_floor_and_wall(scene, cfg, p["arena_radius"], p["wall_height"], p["friction"], p["restitution"])
    r = p["ball_radius"]
    mats = [materials.principled(f"BallMat{i}", c, 0.0, 0.25) for i, c in enumerate(_PALETTE)]
    protos = {}                                   # one mesh per colour (objects of a colour share it)
    actives = []
    for i, (x, y, z) in enumerate(spawn_positions(n, r, p["spread"], r + p["drop_height"], cfg.seed)):
        ci = i % len(mats)
        if ci not in protos:
            _primitive(cfg.shape, r)
            obj = bpy.context.active_object
            if cfg.shape == "sphere":
                _smooth(obj)
            protos[ci] = obj.data
            materials.assign(obj, mats[ci])
        else:
            obj = bpy.data.objects.new("Ball", protos[ci])
            scene.collection.objects.link(obj)
        obj.name = f"Ball_{i:03d}"
        obj.location = (x, y, z)
        shape_kind = {"cube": "BOX", "cylinder": "CYLINDER"}.get(cfg.shape, "SPHERE")
        make_rigid(obj, "ACTIVE", shape_kind, p["friction"], p["restitution"], margin=0.0 if shape_kind == "SPHERE" else 0.001)
        actives.append(obj)
    return actives


def _lathe_cone(scene, name: str, r_top: float, r_bottom: float, height: float, z0: float, thickness: float, seg: int = 64):
    import math
    verts = [(r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z)
             for r, z in ((r_top, z0 + height), (r_bottom, z0)) for i in range(seg)]
    faces = [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    _activate(obj)
    sol = obj.modifiers.new("Thick", "SOLIDIFY")
    sol.thickness = thickness
    bpy.ops.object.modifier_apply(modifier="Thick")
    _smooth(obj)
    return obj


def build_funnel_stage(scene, cfg, stage):
    from .templates import spawn_positions
    p = {**cfg.params, **stage.params}
    hole = p["hole_radius"]
    setup_rigid_world(scene, cfg, cfg.frame_count)
    create_floor_and_wall(scene, cfg, p["funnel_radius"] * 1.12, p["funnel_z"] * 0.55, p["friction"], p["restitution"])
    funnel = _lathe_cone(scene, "Funnel", p["funnel_radius"], hole, p["funnel_height"], p["funnel_z"], 0.1)
    make_rigid(funnel, "PASSIVE", "MESH", p["friction"], p["restitution"])
    materials.assign(funnel, materials.principled("FunnelMat", cfg.material.object_color, 0.1, 0.3))
    r, top = p["ball_radius"], p["funnel_z"] + p["funnel_height"]
    mats = [materials.principled(f"BallMat{i}", c, 0.0, 0.25) for i, c in enumerate(_PALETTE)]
    actives = []
    for i, (x, y, z) in enumerate(spawn_positions(p["balls"], r, p["funnel_radius"] * 0.7, top + p["drop_height"], cfg.seed)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=24, ring_count=12, location=(x, y, z))
        obj = bpy.context.active_object
        obj.name = f"Ball_{i:03d}"
        _smooth(obj)
        make_rigid(obj, "ACTIVE", "SPHERE", p["friction"], p["restitution"])
        materials.assign(obj, mats[i % len(mats)])
        actives.append(obj)
    return actives


def build_rings_stage(scene, cfg, stage):
    import math
    import random
    p = {**cfg.params, **stage.params}
    ratio = p["hole_ratio"]
    setup_rigid_world(scene, cfg, cfg.frame_count, substeps=40, iterations=50)
    create_floor_and_wall(scene, cfg, p["arena_radius"], p["wall_height"], p["friction"], p["restitution"])
    bpy.ops.mesh.primitive_cylinder_add(radius=p["pole_radius"], depth=p["pole_height"], vertices=32,
                                        location=(0, 0, p["pole_height"] / 2))
    pole = bpy.context.active_object
    pole.name = "Pole"
    _smooth(pole)
    make_rigid(pole, "PASSIVE", "CONVEX_HULL", p["friction"], p["restitution"])
    materials.assign(pole, materials.principled("PoleMat", cfg.material.object_color, 0.1, 0.3))
    rnd = random.Random(cfg.seed * 104729 + 17)
    minor = p["ring_minor"]
    major = p["pole_radius"] * ratio + minor
    mats = [materials.principled(f"RingMat{i}", c, 0.2, 0.25) for i, c in enumerate(_PALETTE)]
    actives = []
    for i in range(p["rings"]):
        off = p["pole_radius"] * 0.5
        loc = (rnd.uniform(-off, off), rnd.uniform(-off, off), p["pole_height"] + minor + p["drop_height"] + i * minor * 3.2)
        tilt = math.radians(p["tilt_degrees"])
        rot = (rnd.uniform(-tilt, tilt), rnd.uniform(-tilt, tilt), rnd.uniform(0, math.pi))
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=48, minor_segments=14,
                                         location=loc, rotation=rot)
        obj = bpy.context.active_object
        obj.name = f"Ring_{i:02d}"
        _smooth(obj)
        make_rigid(obj, "ACTIVE", "MESH", p["friction"], p["restitution"], mass=0.5)
        materials.assign(obj, mats[i % len(mats)])
        actives.append(obj)
    return actives


def build_cloth_objects_stage(scene, cfg, stage):
    from .templates import collider_layout
    p = {**cfg.params, **stage.params}
    n = p["objects"]
    scene.gravity = (0.0, 0.0, -cfg.physics.gravity)
    create_ground(scene, cfg.material.ground_color, catcher=hasattr(cfg, 'experiment'))
    top = 0.0
    for i, xy in enumerate(collider_layout(n, p["spacing"])):
        collider, top_z = create_collider(scene, cfg.shape, p["object_scale"], xy, f"Collider_{i}")
        materials.assign(collider, materials.principled(f"ObjectMat{i}", _PALETTE[i % len(_PALETTE)], 0.0, cfg.material.object_roughness))
        top = max(top, top_z)
    segments = faces_segments(p["faces"])
    cloth = create_cloth_mesh(scene, segments, p["cloth_size"], top + p["drop_height"])
    add_cloth_physics(cloth, cfg.physics, cfg.frame_count)
    cloth_mat = materials.principled("ClothMat", cfg.material.cloth_color, cfg.material.cloth_metallic, cfg.material.cloth_roughness)
    add_cloth_look(cloth, cfg.material.cloth_style, segments, p["cloth_size"], cloth_mat)
    return cloth


def faces_segments(faces: int) -> int:
    from .config import faces_to_segments
    return faces_to_segments(faces)


def bake_rigid(scene, objects, frame_start: int, frame_end: int) -> str:
    """Run the rigid-body simulation once and store the result as plain keyframes.

    Keyframes make every frame random-access (workers can render any frame range from the saved .blend) and let
    the event detector read trajectories without re-simulating. The rigid-body world is removed afterwards.
    """
    scene.frame_set(frame_start)
    traj = {o.name: [] for o in objects}
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        for o in objects:
            ev = o.evaluated_get(dg)
            traj[o.name].append((ev.matrix_world.translation.copy(), ev.matrix_world.to_euler()))
    bpy.ops.rigidbody.world_remove()
    for o in objects:
        o.animation_data_clear()
        for i, (loc, rot) in enumerate(traj[o.name]):
            o.location, o.rotation_euler = loc, rot
            o.keyframe_insert("location", frame=frame_start + i)
            o.keyframe_insert("rotation_euler", frame=frame_start + i)
    scene.frame_set(frame_start)
    return "rigid_keyframes"


# ---------------------------------------------------------------------------------------------- story experiments
# Race / mystery / packing. They share three small reusable pieces:
#   * release_at(): hold a rigid body still (kinematic) until a frame, then let physics take over (a fair, physical start)
#   * emissive pads / label schedule: visual feedback derived from the BAKED result (nothing is scripted)
#   * sim_markers: facts about the baked simulation (release frame, winner, ...) saved in the .blend for the
#     event detector and the label schedule
import json
import math


def release_at(obj, frame: int) -> None:
    """Keep ``obj`` fixed until ``frame``; from then on it is an ordinary dynamic rigid body."""
    rb = obj.rigid_body
    rb.kinematic = True
    rb.keyframe_insert("kinematic", frame=1)
    rb.kinematic = False
    rb.keyframe_insert("kinematic", frame=max(2, int(frame)))


def set_markers(scene, markers: dict) -> None:
    scene["sim_markers"] = json.dumps(markers)


def get_markers(scene) -> dict:
    raw = scene.get("sim_markers")
    return json.loads(raw) if raw else {}


def _color_mat(name, color, metallic=0.0, roughness=0.35):
    return materials.principled(name, color, metallic, roughness)


def _glow_material(name: str, color):
    """Dark pad that can be lit by keyframing its emission strength."""
    mat = materials.principled(name, (0.62, 0.66, 0.74, 1.0), 0.0, 0.5)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Emission Color"].default_value = tuple(color)
    bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat, bsdf.inputs["Emission Strength"]


def _box(scene, name, size, location, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)   # keep the origin: collision shapes are centred on it
    return obj


def _wedge(scene, name, width, run, rise):
    """Solid ramp: a triangular prism that meets the floor at its low end (no step, nothing underneath)."""
    import bmesh
    hw, y0, y1 = width / 2, -run / 2, run / 2
    verts = [(-hw, y0, 0.0), (-hw, y1, 0.0), (-hw, y1, rise), (hw, y0, 0.0), (hw, y1, 0.0), (hw, y1, rise)]
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (0, 2, 5, 3)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def _racer(shape: str, r: float):
    """(object, rigid-body collision shape, mass) of one racer; every racer fits a lane and rolls along +/-y."""
    ops = bpy.ops.mesh
    half_pi = math.pi / 2
    if shape == "sphere":
        ops.primitive_uv_sphere_add(radius=r, segments=32, ring_count=16)
        return bpy.context.active_object, "SPHERE", 1.0, r
    if shape == "ring":                      # a fat tyre standing on its edge, axis along x
        ops.primitive_torus_add(major_radius=r * 0.74, minor_radius=r * 0.26, major_segments=48, minor_segments=14)
        obj = bpy.context.active_object
        obj.scale = (1.0, 1.0, 1.7)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.rotation_euler = (0.0, half_pi, 0.0)
        return obj, "MESH", 0.6, r
    if shape == "can":                       # solid cylinder lying on its side
        ops.primitive_cylinder_add(radius=r, depth=r * 2.0, vertices=48, rotation=(0.0, half_pi, 0.0))
        return bpy.context.active_object, "CYLINDER", 1.0, r
    if shape == "prism":                     # hexagonal prism: it can only roll with a bump at every sixth turn
        ops.primitive_cylinder_add(radius=r * 1.05, depth=r * 2.0, vertices=6, rotation=(0.0, half_pi, 0.0))
        return bpy.context.active_object, "CONVEX_HULL", 1.0, r * 1.05
    if shape == "cone":                      # lying on its side, so it rolls in an arc
        ops.primitive_cone_add(radius1=r * 1.05, radius2=0.0, depth=r * 2.2, vertices=48, rotation=(0.0, half_pi, 0.0))
        return bpy.context.active_object, "CONE", 1.0, r * 1.05
    ops.primitive_cube_add(size=r * 1.7)
    return bpy.context.active_object, "BOX", 1.0, r * 0.85


_RACE_COLORS = [(0.92, 0.26, 0.21, 1), (0.98, 0.72, 0.12, 1), (0.25, 0.70, 0.35, 1),
                (0.16, 0.50, 0.90, 1), (0.58, 0.32, 0.82, 1), (0.12, 0.78, 0.76, 1)]


def build_roll_off_stage(scene, cfg, stage):
    from mathutils import Euler, Matrix, Vector

    from .templates import RACE_SHAPES, race_geometry
    p = {**cfg.params, **stage.params}
    g = race_geometry(p)
    th, run, rise, width = g["theta"], g["run"], g["rise"], g["width"]
    lane, r, L = p["lane_width"], p["shape_size"], p["ramp_length"]
    setup_rigid_world(scene, cfg, cfg.frame_count, substeps=60, iterations=80)
    create_floor_and_wall(scene, cfg, 1.0, 0.0, 0.8, p["restitution"])
    d = Vector((0.0, math.cos(th), math.sin(th)))          # down-slope reversed: along the slope, upwards
    n = Vector((0.0, -math.sin(th), math.cos(th)))         # slope normal
    centre = Vector((0.0, 0.0, rise / 2))                  # middle of the sloping surface

    ramp = _wedge(scene, "Ramp", width + 0.3, run, rise)
    make_rigid(ramp, "PASSIVE", "CONVEX_HULL", p["ramp_friction"], p["restitution"])
    icy = p["ramp_friction"] * p["friction"] < 0.01          # a frictionless ramp looks like ice
    materials.assign(ramp, materials.principled("RampMat", (0.45, 0.72, 0.9, 1.0) if icy else (0.20, 0.24, 0.34, 1.0), 0.0,
                                                0.06 if icy else 0.5))
    rail_h = 0.2
    rail_mat = materials.principled("RailMat", (0.88, 0.90, 0.95, 1.0), 0.0, 0.4)
    for i in range(len(RACE_SHAPES) + 1):                  # 5 dividers + 2 outer rails
        x = (i - len(RACE_SHAPES) / 2) * lane
        rail = _box(scene, f"Rail_{i}", (0.05, L, rail_h), tuple(centre + n * (rail_h / 2) + Vector((x, 0, 0))), (th, 0.0, 0.0))
        make_rigid(rail, "PASSIVE", "BOX", p["ramp_friction"], p["restitution"])
        materials.assign(rail, rail_mat)
    y_low = -run / 2
    stop = _box(scene, "Stop", (width + 0.8, 0.3, 0.7), (0.0, y_low - 1.5, 0.35))
    make_rigid(stop, "PASSIVE", "BOX", 0.9, 0.05)
    materials.assign(stop, rail_mat)

    u_finish = -L / 2 + 0.9                                 # finish line, slope coordinate from the middle
    release = max(2, round(p["release_delay"] * cfg.fps))
    u_start = L / 2 - 1.0
    racers, pads = [], []
    for i, shape in enumerate(RACE_SHAPES):
        x = (i + 0.5 - len(RACE_SHAPES) / 2) * lane
        obj, coll, mass, clearance = _racer(shape, r)
        obj.name = f"Ball_{i:03d}"
        obj["shape"] = shape
        if shape in ("sphere", "ring", "can", "cone"):
            _smooth(obj)
        obj.rotation_mode = "XYZ"
        local = obj.rotation_euler.to_matrix()
        obj.rotation_euler = (Matrix.Rotation(th, 3, "X") @ local).to_euler()
        obj.location = centre + d * u_start + n * (0.004 + clearance) + Vector((x, 0, 0))
        make_rigid(obj, "ACTIVE", coll, p["friction"], p["restitution"], mass=mass, margin=0.0 if coll == "SPHERE" else 0.001)
        obj.rigid_body.linear_damping, obj.rigid_body.angular_damping = 0.08, 0.1
        release_at(obj, release)
        materials.assign(obj, _color_mat(f"Racer{i}", _RACE_COLORS[i], 0.15, 0.28))
        racers.append(obj)
        pad_mat, strength = _glow_material(f"Pad{i}", _RACE_COLORS[i])           # this lane's piece of the finish line
        pad = _box(scene, f"FinishLine_{i}", (lane * 0.9, 0.34, 0.012),
                   tuple(centre + d * u_finish + n * 0.008 + Vector((x, 0, 0))), (th, 0.0, 0.0))
        materials.assign(pad, pad_mat)
        pads.append((pad, strength))
    return {"racers": racers, "pads": pads, "release": release, "u_finish": u_finish, "centre": tuple(centre),
            "dir": tuple(d), "shapes": RACE_SHAPES}


def after_bake_roll_off(scene, cfg, stage, handle) -> dict:
    """Read the BAKED trajectories: who crossed the line when. Lights the finish pads; announces the winner."""
    from mathutils import Vector

    from .templates import RACE_NAMES
    racers, pads = handle["racers"], handle["pads"]
    centre, d = Vector(handle["centre"]), Vector(handle["dir"])
    frames = cfg.stage_frames(stage.index)
    finish = {}
    prev = {}
    for f in range(1, frames + 1):
        scene.frame_set(f)
        for o in racers:
            u = (o.location - centre).dot(d)
            if o.name not in finish and u <= handle["u_finish"]:
                u0 = prev.get(o.name, u)
                frac = 0.0 if u0 == u else (u0 - handle["u_finish"]) / (u0 - u)
                finish[o.name] = round(f - 1 + frac, 2)
            prev[o.name] = u
    order = sorted(finish, key=finish.get)
    if not order:
        raise RuntimeError("no racer crossed the finish line within the simulated time; lengthen simulation.duration")
    win_obj = bpy.data.objects[order[0]]
    winner = win_obj["shape"]
    win_frame = finish[order[0]]
    spread = finish[order[-1]] - win_frame
    tie = len(order) == len(racers) and spread < 2.0           # everyone crossed within two frames: a dead heat, not a winner
    for o, (pad, strength) in zip(racers, pads):
        if o.name in finish:
            f = int(math.ceil(finish[o.name]))
            strength.default_value = 0.0
            strength.keyframe_insert("default_value", frame=max(1, f - 1))
            strength.default_value = 9.0 if (o.name == order[0] or tie) else 3.0
            strength.keyframe_insert("default_value", frame=f + 2)
    scene.frame_set(1)
    names = {o.name: o["shape"] for o in racers}
    announce = int(math.ceil(win_frame)) + 4
    icy = cfg.stage_params(stage.index)["ramp_friction"] * cfg.stage_params(stage.index)["friction"] < 0.01
    first = "NOW ON\nICE" if icy else "WHICH ONE\nWINS?"
    schedule = [[1, first], [announce, "ALL TIE!" if tie else f"{RACE_NAMES[winner]}\nWINS!"]]
    result = {"winner": None if tie else winner, "dead_heat": tie, "finish_spread_frames": round(spread, 2), "finish_frames": {names[k]: v for k, v in finish.items()}, "order": [names[k] for k in order],
              "did_not_finish": [names[o.name] for o in racers if o.name not in finish], "release_frame": handle["release"],
              "incline": cfg.stage_params(stage.index).get("incline", None) or stage.params.get("incline")}
    set_markers(scene, {"release": handle["release"], "winner_frame": win_frame, "label_schedule": schedule, **result})
    return result


# ---- sheet reveal
def _static_collider(scene, kind: str, name: str, location, size, color, rotation=(0.0, 0.0, 0.0), roughness=0.45):
    ops = bpy.ops.mesh
    if kind == "sphere":
        ops.primitive_uv_sphere_add(radius=size, segments=64, ring_count=32, location=location)
    elif kind == "cube":
        ops.primitive_cube_add(size=size, location=location, rotation=rotation)
    elif kind == "cylinder":
        ops.primitive_cylinder_add(radius=size[0], depth=size[1], vertices=64, location=location)
    elif kind == "cone":
        ops.primitive_cone_add(radius1=size[0], radius2=0.0, depth=size[1], vertices=48, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.polygons.foreach_set("use_smooth", [kind in ("sphere", "cone", "cylinder")] * len(obj.data.polygons))
    obj.modifiers.new("Collision", "COLLISION")
    obj.collision.thickness_outer = 0.01
    obj.collision.cloth_friction = 5.0
    materials.assign(obj, _color_mat(name + "Mat", color, 0.0, roughness))
    return obj


def hidden_layout(scene, hidden: str) -> tuple:
    """Build the hidden object out of static colliders. Returns (objects, top_z)."""
    objs = []
    white, hat_c, nose = (0.97, 0.97, 1.0, 1), (0.08, 0.08, 0.1, 1), (0.98, 0.45, 0.1, 1)
    if hidden == "snowman":
        radii = (0.9, 0.62, 0.4)
        z = radii[0]
        centres = [z]
        for a, b in zip(radii, radii[1:]):
            z += (a + b) * 0.78
            centres.append(z)
        for i, (rr, zc) in enumerate(zip(radii, centres)):
            objs.append(_static_collider(scene, "sphere", f"Collider_{i}", (0, 0, zc), rr, white))
        head_top = centres[-1] + radii[-1]
        objs.append(_static_collider(scene, "cylinder", "Collider_hat", (0, 0, head_top - 0.1 + 0.21), (0.3, 0.42), hat_c))
        objs.append(_static_collider(scene, "cylinder", "Collider_brim", (0, 0, head_top - 0.1 + 0.03), (0.52, 0.06), hat_c))
        objs.append(_static_collider(scene, "cone", "Collider_nose", (0, -(radii[-1] + 0.2), centres[-1] - 0.02), (0.09, 0.5), nose,
                                     rotation=(math.pi / 2, 0.0, 0.0)))
        return objs, head_top - 0.1 + 0.42
    if hidden == "pyramid":
        s = 1.25
        rows = [(i, j) for j in range(3) for i in range(3 - j)]
        colors = [_RACE_COLORS[(i + j) % 6] for i, j in rows]
        for k, ((i, j), c) in enumerate(zip(rows, colors)):
            x = (i - (2 - j) / 2) * s
            objs.append(_static_collider(scene, "cube", f"Collider_{k}", (x, 0, s / 2 + j * s), s, c))
        return objs, 3 * s
    heights = (1.0, 1.0, 1.0, 1.0)
    z = 0.0
    for k, (sx, dx) in enumerate(((1.7, 0.0), (1.4, 0.15), (1.1, -0.12), (0.8, 0.1))):
        objs.append(_static_collider(scene, "cube", f"Collider_{k}", (dx, 0, z + sx / 2), sx, _RACE_COLORS[k]))
        z += sx
    return objs, z


def _dissolve_from_top(mat, z_from: float, z_to: float, start: int, end: int, band: float = 0.35) -> None:
    """Make the sheet vanish from the top down: everything above a sinking height becomes transparent.

    A render-time reveal only; the cloth simulation is untouched. ``band`` is the soft edge height in metres.
    """
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf, out = nodes.get("Principled BSDF"), nodes.get("Material Output")
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    thr = nodes.new("ShaderNodeValue")
    sub = nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 1.0 / band
    mul.use_clamp = True
    clear = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(geo.outputs["Position"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], sub.inputs[0])
    links.new(thr.outputs["Value"], sub.inputs[1])
    links.new(sub.outputs["Value"], mul.inputs[0])
    links.new(mul.outputs["Value"], mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(clear.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    thr.outputs["Value"].default_value = z_from
    thr.outputs["Value"].keyframe_insert("default_value", frame=max(1, start - 1))
    thr.outputs["Value"].default_value = z_to
    thr.outputs["Value"].keyframe_insert("default_value", frame=end)


def build_sheet_reveal_stage(scene, cfg, stage):
    p = {**cfg.params, **stage.params}
    hidden = p["hidden"]
    scene.gravity = (0.0, 0.0, -cfg.physics.gravity)
    create_ground(scene, cfg.material.ground_color, catcher=True)
    objs, top = hidden_layout(scene, hidden)
    segments = faces_segments(p["faces"])
    cloth = create_cloth_mesh(scene, segments, p["cloth_size"], top + p["drop_height"])
    add_cloth_physics(cloth, cfg.physics, cfg.frame_count)
    mat = materials.principled("ClothMat", cfg.material.cloth_color, cfg.material.cloth_metallic, cfg.material.cloth_roughness)
    add_cloth_look(cloth, cfg.material.cloth_style, segments, p["cloth_size"], mat)
    # The hidden object is never drawn while the sheet is falling: the viewer only sees what the CLOTH does over it.
    # (Collision is unaffected by render visibility.) At the reveal the sheet turns transparent.
    start = max(2, round(p["reveal_start"] * cfg.fps))
    end = start + max(2, round(p["reveal_seconds"] * cfg.fps))
    for o in objs:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=1)
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=start - 1)
    _dissolve_from_top(mat, top + 0.7, -0.4, start, end)
    names = {"snowman": "A SNOWMAN!", "pyramid": "A PYRAMID!", "tower": "A TOWER!"}
    first = "WHAT'S UNDER\nTHE SHEET?"
    set_markers(scene, {"reveal_start": start, "reveal_end": end, "hidden": hidden, "top": top,
                        "label_schedule": [[1, first], [start + 4, names[hidden].replace(" ", "\n", 1)]]})
    return cloth


# ---- jar packing
_POUR_COLORS = [(0.20, 0.23, 0.34, 1), (0.88, 0.40, 0.22, 1), (0.98, 0.76, 0.20, 1), (0.22, 0.80, 0.78, 1)]


def build_jar_stage(scene, cfg, stage):
    from .templates import jar_pours, spawn_positions
    p = {**cfg.params, **stage.params}
    pours = jar_pours(p)[:p["pours"]]
    R, H = p["jar_radius"], p["jar_height"]
    setup_rigid_world(scene, cfg, cfg.frame_count, substeps=60, iterations=80)
    floor, wall = create_floor_and_wall(scene, cfg, R, H, p["friction"], p["restitution"])
    wall.data.materials.clear()
    wall.data.materials.append(translucent("JarMat", [0.78, 0.9, 0.95, 1.0], 0.14))
    bpy.ops.mesh.primitive_torus_add(major_radius=R + 0.06, minor_radius=0.035, major_segments=64, minor_segments=12,
                                     location=(0, 0, H))
    rim = bpy.context.active_object
    rim.name = "Rim"
    materials.assign(rim, materials.principled("RimMat", (0.85, 0.92, 0.97, 1.0), 0.0, 0.1))
    far = R * 14                       # later pours wait far to the side and are moved into place just before they are released
    actives, schedule, starts = [], [], []
    ball_index = 0
    for k, (rad, count) in enumerate(pours):
        if count <= 0:
            starts.append(None)
            continue
        start = round((0.9 + k * p["pour_gap"]) * cfg.fps)
        starts.append(start)
        batch = max(2, count // 12)
        mat = materials.principled(f"Pour{k}", _POUR_COLORS[k], 0.0, 0.32)
        proto = None
        z0 = H + 1.5 + rad
        for i, (x, y, z) in enumerate(spawn_positions(count, rad, R * 0.7, z0, cfg.seed + k)):
            if proto is None:
                bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, segments=24, ring_count=12)
                obj = bpy.context.active_object
                _smooth(obj)
                proto = obj.data
                materials.assign(obj, mat)
            else:
                obj = bpy.data.objects.new("Ball", proto)
                scene.collection.objects.link(obj)
            obj.name = f"Ball_{ball_index:03d}"
            obj["pour"] = k
            obj["radius"] = rad
            obj.location = (x, y, z)
            make_rigid(obj, "ACTIVE", "SPHERE", p["friction"], p["restitution"], mass=(rad / pours[0][0]) ** 3 + 0.001)
            obj.rigid_body.linear_damping, obj.rigid_body.angular_damping = 0.04, 0.12
            release = start + (i // batch) * 3
            if k > 0:                      # waits out of sight, hops into the holding stack two frames before the first release
                obj.location = (far, y, z)
                obj.keyframe_insert("location", frame=1)
                obj.keyframe_insert("location", frame=max(2, start - 4))
                obj.location = (x, y, z)
                obj.keyframe_insert("location", frame=max(3, start - 3))
            release_at(obj, release)
            actives.append(obj)
            ball_index += 1
    set_markers(scene, {"pour_starts": starts, "jar_height": H, "jar_radius": R, "pours": len(pours)})
    return actives


def after_bake_jar(scene, cfg, stage, handle) -> dict:
    """Fill level after every pour (from the baked positions) and how many stones ended above the rim."""
    markers = get_markers(scene)
    frames = cfg.stage_frames(stage.index)
    starts = [s for s in markers["pour_starts"] if s is not None]
    cuts = [s - 1 for s in starts[1:]] + [frames]
    levels = []
    for k, cut in enumerate(cuts):
        f = max(4, min(frames, cut))
        scene.frame_set(f - 3)
        before = {o.name: o.location.z for o in handle}
        scene.frame_set(f)
        resting = [o for o in handle if o["pour"] <= k and abs(o.location.z - before[o.name]) < 0.01
                   and math.hypot(o.location.x, o.location.y) < markers["jar_radius"]]
        zs = sorted(o.location.z + o["radius"] for o in resting)
        levels.append(round(zs[int(len(zs) * 0.97)] if zs else 0.0, 3))          # settled surface: 97th percentile of resting stones
    scene.frame_set(frames)
    over = sum(1 for o in handle if o.location.z - o["radius"] > markers["jar_height"] * 1.0)
    outside = sum(1 for o in handle if math.hypot(o.location.x, o.location.y) > markers["jar_radius"] + 0.05)
    scene.frame_set(1)
    final_settle = min(frames, int(frames * 0.0) + frames)
    schedule = [[1, "IS IT REALLY\nFULL?"]]
    if len(starts) > 1:
        schedule.append([starts[1] - 2, ""])
    schedule.append([max(1, frames - round(cfg.fps * 2.0)), "NOW IT'S\nFULL"])
    result = {"fill_levels": levels, "jar_height": markers["jar_height"], "above_rim": over, "outside_jar": outside}
    markers.update(result)
    markers["label_schedule"] = schedule
    set_markers(scene, markers)
    return result


POST_BAKE = {"roll_off": after_bake_roll_off, "jar_packing": after_bake_jar}


SIMULATORS = {
    "cloth_drape": build_cloth_stage,
    "cloth_objects": build_cloth_objects_stage,
    "multiple_balls": build_balls_stage,
    "ball_funnel": build_funnel_stage,
    "ring_toss": build_rings_stage,
    "roll_off": build_roll_off_stage,
    "sheet_reveal": build_sheet_reveal_stage,
    "jar_packing": build_jar_stage,
}


def bake_for(cfg, scene, handle, frames: int) -> str:
    """Bake the physics of whatever the builder returned (a cloth object or a list of rigid bodies)."""
    if cfg.simulation == "rigid_body":
        bodies = handle["racers"] if isinstance(handle, dict) else handle
        return bake_rigid(scene, bodies, 1, frames)
    return bake(scene, handle, 1, frames)
