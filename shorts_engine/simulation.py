"""Physics scene builders (requires bpy).

Each simulation type registers a builder in ``SIMULATORS``. Adding soft body / rigid body
later means adding a function here, not rewriting the engine.
"""

from __future__ import annotations

import bpy

from . import materials

# (top_z of the object when resting on the ground at z=0)
_OBJECT_TOP = {"sphere": 2.0, "cube": 2.0, "cylinder": 2.0, "cone": 2.0, "torus": 0.8}


def create_ground(scene, color, size: float = 40.0, catcher: bool = False, look: str = "classic"):
    half = size / 2
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("Ground", mesh)
    scene.collection.objects.link(obj)
    obj.modifiers.new("Collision", "COLLISION")
    materials.assign(obj, materials.principled("GroundMat", color, 0.0, 0.8 if look != "studio" else 0.16))
    if look == "studio":                          # glossy, visible floor that mirrors the objects (depth)
        catcher = False
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
    floor = create_ground(scene, cfg.material.ground_color, catcher=hasattr(cfg, 'experiment'), look=cfg.material.look)
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
    """Six shapes share ONE ramp that runs out into a long arena: who rolls farthest?"""
    from mathutils import Matrix, Vector

    from .templates import RACE_SHAPES, race_geometry
    p = {**cfg.params, **stage.params}
    g = race_geometry(p)
    th, run, rise, width = g["theta"], g["run"], g["rise"], g["width"]
    lane, r, L, arena = p["lane_width"], p["shape_size"], p["ramp_length"], p["arena_length"]
    setup_rigid_world(scene, cfg, cfg.frame_count, substeps=60, iterations=80)
    create_floor_and_wall(scene, cfg, 1.0, 0.0, p["floor_friction"], p["restitution"])
    d = Vector((0.0, math.cos(th), math.sin(th)))          # along the slope, upwards
    n = Vector((0.0, -math.sin(th), math.cos(th)))         # slope normal
    centre = Vector((0.0, 0.0, rise / 2))                  # middle of the sloping surface
    y_low = -run / 2                                       # where the ramp meets the floor
    pad = 0.15

    ramp = _wedge(scene, "Ramp", width + 0.3, run, rise)
    make_rigid(ramp, "PASSIVE", "CONVEX_HULL", p["ramp_friction"], p["restitution"])
    materials.assign(ramp, materials.principled("RampMat", (0.20, 0.25, 0.42, 1.0), 0.0, 0.4))
    rail_mat = materials.principled("RailMat", (0.85, 0.92, 1.0, 1.0), 0.0, 0.2)
    rail_h = 0.22
    for sx in (-1, 1):                                     # two low side rails: no dividers, the shapes share the surface
        x = sx * (width / 2 + 0.12)
        rail = _box(scene, f"Rail_{sx}", (0.07, L, rail_h), tuple(centre + n * (rail_h / 2) + Vector((x, 0, 0))), (th, 0.0, 0.0))
        make_rigid(rail, "PASSIVE", "BOX", p["ramp_friction"], p["restitution"])
        materials.assign(rail, rail_mat)
        wall = _box(scene, f"ArenaRail_{sx}", (0.07, arena, 0.32), (x, y_low - arena / 2, 0.16))
        make_rigid(wall, "PASSIVE", "BOX", 0.3, 0.3)
        materials.assign(wall, rail_mat)
    stop = _box(scene, "EndWall", (width + 0.5, 0.3, 0.7), (0.0, y_low - arena - 0.15, 0.35))
    make_rigid(stop, "PASSIVE", "BOX", 0.9, 0.05)
    materials.assign(stop, rail_mat)
    for k in range(1, int(arena // 2) + 1):               # distance lines across the arena, every two metres
        mat, strength = _glow_material(f"Mark{k}", (0.25, 0.85, 0.95, 1.0))
        strength.default_value = 1.4 if k % 5 else 3.0
        line = _box(scene, f"Mark_{k}", (width, 0.07, 0.008), (0.0, y_low - 2.0 * k, 0.005))
        materials.assign(line, mat)

    release = max(2, round(p["release_delay"] * cfg.fps))
    u_start = L / 2 - 1.0
    racers = []
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
        obj.rigid_body.linear_damping = obj.rigid_body.angular_damping = p["damping"]
        release_at(obj, release)
        mat = _color_mat(f"Racer{i}", _RACE_COLORS[i], 0.1, 0.2)
        mat.node_tree.nodes.get("Principled BSDF").inputs["Coat Weight"].default_value = 0.5
        materials.assign(obj, mat)
        racers.append(obj)
    halo_mat, halo_strength = _glow_material("Halo", (1.0, 0.95, 0.4, 1.0))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.95, minor_radius=0.06, major_segments=48, minor_segments=10, location=(0, 0, -5))
    halo = bpy.context.active_object
    halo.name = "Halo"
    materials.assign(halo, halo_mat)
    return {"racers": racers, "halo": (halo, halo_strength), "release": release, "y_low": y_low, "centre": tuple(centre),
            "dir": tuple(d), "shapes": RACE_SHAPES, "width": width, "arena": arena,
            "start": (0.0, centre[1] + d[1] * u_start, centre[2] + d[2] * u_start)}


def _smooth_series(values, window: int):
    """Zero-phase moving average (forward and backward exponential pass): a camera that never jerks."""
    a = 2.0 / (window + 1)
    out = list(values)
    for i in range(1, len(out)):
        out[i] = out[i - 1] + a * (values[i] - out[i - 1])
    back = list(out)
    for i in range(len(back) - 2, -1, -1):
        back[i] = back[i + 1] + a * (out[i] - back[i + 1])
    return back


def _race_camera(cfg, handle, tracks, frames, stop_frame, win_pos, win_frame, finals) -> list:
    """Camera in FRONT of the pack: line-up, a chase that stays tight on the three leaders, a high wide shot of where every
    shape came to rest, then an orbit around the winner."""
    focal = cfg.camera.focal_length
    W = handle["width"]
    d_ready = fit_distance(W / 2 * 0.98, focal)
    n = frames
    ys = [[t[f][1] for t in tracks] for f in range(n)]
    xs = [[t[f][0] for t in tracks] for f in range(n)]
    zs = [[t[f][2] for t in tracks] for f in range(n)]
    cy, cz, cd = [], [], []
    for i in range(n):
        order = sorted(range(len(tracks)), key=lambda k: ys[i][k])[:3]             # the three leaders
        cy.append(sum(ys[i][k] for k in order) / 3)
        cz.append(sum(zs[i][k] for k in order) / 3)
        y_span = max(ys[i][k] for k in order) - min(ys[i][k] for k in order)
        x_half = max(abs(xs[i][k]) for k in order) + 0.9
        cd.append(max(7.0, fit_distance(x_half, focal, 1.0), 1.7 * y_span + 6.5))
    cy, cz, cd = _smooth_series(cy, 16), _smooth_series(cz, 16), _smooth_series(cd, 30)
    release = handle["release"]
    sx, sy, sz = handle["start"]
    y_low = handle["y_low"]
    far = max(finals)
    res_start = max(release + 30, min(win_frame - 30, stop_frame - 40))
    res_t = (0.0, y_low - far * 0.62, 0.3)
    res_dist = max(15.0, 1.25 * ((far + 3.0) * math.sin(math.radians(56)) + 1.5) / 0.61)
    keys = []
    for f in range(1, n + 1):
        i = f - 1
        w_chase = smoothstep((f - (release - 6)) / 36.0)
        w_res = smoothstep((f - res_start) / 44.0)
        w_win = smoothstep((f - (win_frame + 26)) / 40.0)
        tgt = [a + (b - a) * w_chase for a, b in zip((0.0, sy, sz * 0.85), (0.0, cy[i], cz[i] + 0.3))]
        dist = d_ready + (cd[i] - d_ready) * w_chase
        elev, az = 26 + 12 * w_chase, 10 * w_chase
        tgt = [a + (b - a) * w_res for a, b in zip(tgt, res_t)]
        dist = dist + (res_dist - dist) * w_res
        elev, az = elev + (56 - elev) * w_res, az + (8 - az) * w_res
        if w_win > 0:
            t_o = (f - (win_frame + 26)) / max(1, n - (win_frame + 26))
            tgt = [a + (b - a) * w_win for a, b in zip(tgt, (win_pos[0], win_pos[1], 0.45))]
            dist = dist + ((7.4 - 2.2 * t_o) - dist) * w_win
            elev = elev + (30 - elev) * w_win
            az = az + ((8 + 42 * smoothstep(t_o * 1.1)) - az) * w_win
        keys.append(orbit_key(f, tgt, dist, elev, az))
    return keys


def smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def after_bake_roll_off(scene, cfg, stage, handle) -> dict:
    """Read the BAKED trajectories: where each shape came to rest. Lights a halo on the winner; plans the camera."""
    from .templates import RACE_NAMES
    racers = handle["racers"]
    frames = cfg.stage_frames(stage.index)
    tracks = [[] for _ in racers]
    for f in range(1, frames + 1):
        scene.frame_set(f)
        for t, o in zip(tracks, racers):
            t.append((o.location.x, o.location.y, o.location.z))
    y_low = handle["y_low"]
    final = [y_low - t[-1][1] for t in tracks]                             # metres past the foot of the ramp
    stops = []
    for t in tracks:                                                      # frame from which the shape never moves more than ~12 cm/s
        stop = frames
        for f in range(frames - 1, 0, -1):
            if math.dist(t[f], t[f - 1]) > 0.004:
                break
            stop = f
        stops.append(stop + 1)
    names = [o["shape"] for o in racers]
    order = sorted(range(len(racers)), key=lambda i: -final[i])
    win = order[0]
    margin = final[order[0]] - final[order[1]]
    all_stop = max(stops)
    moving = [names[i] for i in range(len(racers)) if stops[i] >= frames]
    announce = min(frames - 20, all_stop + 8)
    halo, strength = handle["halo"]
    halo.location = (tracks[win][-1][0], tracks[win][-1][1], 0.03)
    halo.keyframe_insert("location", frame=1)
    strength.default_value = 0.0
    strength.keyframe_insert("default_value", frame=max(1, announce - 2))
    strength.default_value = 6.0
    strength.keyframe_insert("default_value", frame=announce + 6)
    win_pos = tracks[win][-1]
    path = _race_camera(cfg, handle, tracks, frames, all_stop, win_pos, announce, final)
    scene.frame_set(1)
    schedule = [[1, "WHICH ROLLS\nFARTHEST?"], [announce, f"{RACE_NAMES[names[win]]}\nWINS!"]]
    result = {"winner": names[win], "winner_margin_m": round(margin, 2), "distances_m": {names[i]: round(final[i], 2) for i in order},
              "order": [names[i] for i in order], "all_stopped_frame": all_stop, "still_moving": moving,
              "release_frame": handle["release"], "incline": stage.params.get("incline")}
    set_markers(scene, {"release": handle["release"], "winner_frame": announce, "label_schedule": schedule,
                        "camera_path": path, **result})
    return result


# ---- sheet reveal: what is moving under the cloth?
def _dissolve_wipe(mat, a_from: float, a_to: float, start: int, end: int, band: float = 0.35, axis: str = "Z") -> None:
    """Make the sheet vanish along an axis: everything beyond a moving coordinate becomes transparent.

    A render-time reveal only; the cloth simulation is untouched. ``band`` is the soft edge width in metres.
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
    links.new(sep.outputs[axis], sub.inputs[0])
    links.new(thr.outputs["Value"], sub.inputs[1])
    links.new(sub.outputs["Value"], mul.inputs[0])
    links.new(mul.outputs["Value"], mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(clear.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    thr.outputs["Value"].default_value = a_from
    thr.outputs["Value"].keyframe_insert("default_value", frame=max(1, start - 1))
    thr.outputs["Value"].default_value = a_to
    thr.outputs["Value"].keyframe_insert("default_value", frame=end)


# What hides under the sheet: (kind, size, colour, waypoints). A waypoint is (second, x, y); a shape glides between waypoints
# (smooth start and stop), rolling (spheres) or sliding and turning (cube). The sheet's reaction to them is real cloth physics.
HIDDEN_LAYOUTS = {
    "mixed": [("sphere", 0.75, (0.95, 0.22, 0.18, 1), [(0, -1.0, 1.0), (2.4, -1.0, 1.0), (4.6, 0.0, 1.0), (9.8, 0.0, 1.0), (11.4, 0.3, 0.4)]),
              ("sphere", 0.50, (1.0, 0.80, 0.10, 1), [(0, 1.2, -1.0), (4.4, 1.2, -1.0), (6.4, -0.2, -0.8)]),
              ("sphere", 0.36, (0.15, 0.80, 0.90, 1), [(0, 1.2, 1.2), (6.2, 1.2, 1.2), (8.4, 1.5, 0.2)]),
              ("cube", 0.70, (0.60, 0.35, 0.95, 1), [(0, -1.2, -1.2), (8.2, -1.2, -1.2), (10.4, -1.5, 0.1)])],
    "trio": [("sphere", 0.75, (0.95, 0.22, 0.18, 1), [(0, -1.0, 1.0), (2.4, -1.0, 1.0), (4.6, 0.0, 1.0), (9.8, 0.0, 1.0), (11.4, 0.3, 0.4)]),
             ("sphere", 0.50, (1.0, 0.80, 0.10, 1), [(0, 1.2, -1.0), (4.4, 1.2, -1.0), (6.4, -0.2, -0.8)]),
             ("sphere", 0.36, (0.15, 0.80, 0.90, 1), [(0, 1.2, 1.2), (6.2, 1.2, 1.2), (8.4, 1.5, 0.2)])],
}
HIDDEN_REVEAL_TEXT = {"mixed": "3 BALLS\nAND A CUBE!", "trio": "THREE\nBALLS!"}


def _glide(waypoints, t: float):
    """Position at second ``t``: smoothstep between waypoints (zero speed at every waypoint)."""
    prev = waypoints[0]
    for w in waypoints:
        if w[0] >= t:
            if w[0] == prev[0]:
                return w[1], w[2]
            u = smoothstep((t - prev[0]) / (w[0] - prev[0]))
            return prev[1] + (w[1] - prev[1]) * u, prev[2] + (w[2] - prev[2]) * u
        prev = w
    return waypoints[-1][1], waypoints[-1][2]


def build_sheet_reveal_stage(scene, cfg, stage):
    from mathutils import Matrix, Vector
    p = {**cfg.params, **stage.params}
    hidden = p["hidden"]
    layout = HIDDEN_LAYOUTS[hidden]
    fps, frames = cfg.fps, cfg.frame_count
    scene.gravity = (0.0, 0.0, -cfg.physics.gravity)
    floor = create_ground(scene, cfg.material.ground_color, catcher=True, look=cfg.material.look)
    start = max(2, round(p["reveal_start"] * fps))
    # Keyframed (kinematic) shapes: the sheet collides with their motion; they never collide with each other, so the
    # layout is checked for clearance instead.
    shapes, tracks = [], []
    for i, (kind, size, color, wps) in enumerate(layout):
        if kind == "sphere":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=size, segments=48, ring_count=24)
            r = size
        else:
            bpy.ops.mesh.primitive_cube_add(size=size)
            r = size * 0.5 * math.sqrt(2)                              # circumradius for the clearance check
        obj = bpy.context.active_object
        obj.name = f"Ball_{i:03d}"
        if kind == "sphere":
            _smooth(obj)
        materials.assign(obj, _color_mat(f"Hidden{i}", color, 0.0, 0.22))
        rot, travelled, prev = Matrix.Identity(3), 0.0, None
        track = []
        for f in range(1, frames + 1):
            x, y = _glide(wps, (f - 1) / fps)
            if prev is not None:
                dx, dy = x - prev[0], y - prev[1]
                d = math.hypot(dx, dy)
                travelled += d
                if d > 1e-9:
                    if kind == "sphere":                                # roll without slipping
                        rot = Matrix.Rotation(d / size, 3, Vector((-dy, dx, 0.0)).normalized()) @ rot
                    else:                                               # slide and turn
                        rot = Matrix.Rotation(0.9 * d, 3, "Z") @ rot
            prev = (x, y)
            obj.location = (x, y, size if kind == "sphere" else size / 2)
            obj.rotation_euler = rot.to_euler()
            obj.keyframe_insert("location", frame=f)
            obj.keyframe_insert("rotation_euler", frame=f)
            track.append((x, y))
        tracks.append((track, r))
        shapes.append(obj)
    worst = min(math.dist(a[0][f], b[0][f]) - a[1] - b[1] for ia, a in enumerate(tracks) for b in tracks[ia + 1:] for f in range(frames))
    if worst < 0.02:
        raise RuntimeError(f"hidden shapes would overlap while moving (clearance {worst:.2f} m): fix the waypoints")
    for o in shapes:                                                    # the sheet collides with the shapes' motion
        o.modifiers.new("Collision", "COLLISION")
        o.collision.thickness_outer = 0.01
        o.collision.cloth_friction = 1.0
    floor.modifiers.new("Collision", "COLLISION")
    top = max(2 * l[1] if l[0] == "sphere" else l[1] for l in layout)
    segments = faces_segments(p["faces"])
    cloth = create_cloth_mesh(scene, segments, p["cloth_size"], top + p["drop_height"])
    from dataclasses import replace as _replace
    add_cloth_physics(cloth, _replace(cfg.physics, quality=max(cfg.physics.quality, 10), collision_distance=0.02), frames)   # moving colliders need finer steps
    mat = materials.principled("ClothMat", cfg.material.cloth_color, cfg.material.cloth_metallic, cfg.material.cloth_roughness)
    add_cloth_look(cloth, cfg.material.cloth_style, segments, p["cloth_size"], mat)
    # Nothing shows through the falling sheet: the shapes are drawn once it has landed, and the sheet hides them until the reveal.
    cover = round(2.0 * fps)
    for o in shapes:
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=1)
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=cover)
    end = start + max(2, round(p["reveal_seconds"] * fps))
    _dissolve_wipe(mat, p["cloth_size"] / 2 + 0.6, -p["cloth_size"] / 2 - 0.6, start, end, band=1.0, axis="X")
    markers = {"reveal_start": start, "reveal_end": end, "hidden": hidden, "clearance_m": round(worst, 2),
               "label_schedule": [[1, "WHAT'S MOVING\nUNDER THE CLOTH?"], [start + 6, HIDDEN_REVEAL_TEXT[hidden]]]}
    wide = fit_distance(2.5, cfg.camera.focal_length)
    keyed = {1: (1.3, 42, 0), round(2.4 * fps): (1.0, 38, 6), round(7 * fps): (0.82, 40, 14),
             start - round(1.2 * fps): (0.76, 36, 18), start + round(1.0 * fps): (0.86, 32, 12), frames: (0.84, 26, 6)}
    marks = sorted(keyed)
    path = []
    for f in range(1, frames + 1):
        i = max(m for m in marks if m <= f)
        j = min((m for m in marks if m >= f), default=marks[-1])
        t = 0.0 if i == j else smoothstep((f - i) / (j - i))
        d, e, az = [keyed[i][q] + (keyed[j][q] - keyed[i][q]) * t for q in range(3)]
        path.append(orbit_key(f, (0.0, 0.0, 0.5), wide * d, e, az))
    markers["camera_path"] = path
    set_markers(scene, markers)
    return cloth


# ---- jar packing
_POUR_COLORS = [(0.10, 0.32, 0.95, 1), (1.0, 0.38, 0.08, 1), (1.0, 0.84, 0.10, 1), (0.04, 0.85, 0.75, 1)]


def orbit_key(frame, target, dist, elev_deg, az_deg=0.0):
    """One camera-path key: camera on a sphere around ``target`` (az 0 = camera in front at -y, 180 = behind)."""
    e, a = math.radians(elev_deg), math.radians(az_deg)
    cam = [target[0] + dist * math.cos(e) * math.sin(a), target[1] - dist * math.cos(e) * math.cos(a), target[2] + dist * math.sin(e)]
    return [int(frame), [round(c, 4) for c in cam], [round(t, 4) for t in target]]


def fit_distance(half_width: float, focal: float = 50.0, margin: float = 1.12) -> float:
    """Camera distance at which ``half_width`` metres fill the 9:16 frame's width."""
    return margin * half_width / ((18.0 / focal) * (9 / 16))


def build_jar_stage(scene, cfg, stage):
    from .templates import jar_pours, spawn_positions
    p = {**cfg.params, **stage.params}
    pours = jar_pours(p)[:p["pours"]]
    R, H = p["jar_radius"], p["jar_height"]
    setup_rigid_world(scene, cfg, cfg.frame_count, substeps=60, iterations=80)
    floor, wall = create_floor_and_wall(scene, cfg, R, H, p["friction"], p["restitution"])
    wall.data.materials.clear()
    wall.data.materials.append(translucent("JarMat", [0.80, 0.92, 1.0, 1.0], 0.16))
    bpy.ops.mesh.primitive_cylinder_add(radius=R, depth=2.2, vertices=64, end_fill_type="NOTHING", location=(0, 0, H + 1.1))
    guard = bpy.context.active_object                 # invisible collar above the rim: a stone that bounces up cannot leave the jar
    guard.name = "Guard"
    sol = guard.modifiers.new("Thick", "SOLIDIFY")
    sol.thickness, sol.offset = 0.12, 1.0
    _activate(guard)
    bpy.ops.object.modifier_apply(modifier="Thick")
    make_rigid(guard, "PASSIVE", "MESH", p["friction"], p["restitution"])
    guard.hide_render = True
    rim_mat = materials.principled("RimMat", (0.9, 0.96, 1.0, 1.0), 0.0, 0.08)
    parts = [wall, guard]
    bpy.ops.mesh.primitive_cylinder_add(radius=R, depth=0.2, vertices=64, location=(0, 0, -0.1))
    disk = bpy.context.active_object                  # the jar's own bottom: lets the whole jar be tapped without moving the floor
    disk.name = "JarBase"
    make_rigid(disk, "PASSIVE", "BOX", p["friction"], p["restitution"])
    disk.hide_render = True
    parts.append(disk)
    for name, z in (("Rim", H), ("Base", 0.02)):
        bpy.ops.mesh.primitive_torus_add(major_radius=R + 0.06, minor_radius=0.04, major_segments=64, minor_segments=12, location=(0, 0, z))
        ring = bpy.context.active_object
        ring.name = name
        materials.assign(ring, rim_mat)
        parts.append(ring)
    far = R * 14                       # later pours wait far to the side and are moved into place just before they are released
    actives, starts, ends = [], [], []
    ball_index = 0
    for k, (rad, count) in enumerate(pours):
        if count <= 0:
            starts.append(None)
            continue
        start = round((0.9 + k * p["pour_gap"] + (p["full_hold"] if k > 0 else 0.0)) * cfg.fps)
        starts.append(start)
        batch = max(2, count // 12)
        ends.append(start + ((count - 1) // batch) * 3)
        mat = materials.principled(f"Pour{k}", _POUR_COLORS[k], 0.0, 0.16)
        mat.node_tree.nodes.get("Principled BSDF").inputs["Coat Weight"].default_value = 0.6
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
    if p["tap"] > 0:                       # tap the jar after every pour: real rigid-body settling (vertical hops + a little sway)
        for part in parts:
            if part.rigid_body is not None:
                part.rigid_body.kinematic = True
        base = {id(part): tuple(part.location) for part in parts}
        taps = []
        for k in range(len(ends)):
            taps.append((ends[k] + 8, ends[k] + 8 + round(p["tap_seconds"] * cfg.fps)))
        for t0, t1 in taps:
            for f in range(t0, min(t1, cfg.frame_count - 2), 2):
                up = ((f - t0) // 2) % 2 == 0
                for part in parts:
                    x, y, z = base[id(part)]
                    part.location = (x + (0.25 * p["tap"] if up else -0.25 * p["tap"]), y, z + (p["tap"] if up else 0.0))
                    part.keyframe_insert("location", frame=f)
            for part in parts:                               # back to rest after the taps
                part.location = base[id(part)]
                part.keyframe_insert("location", frame=min(t1, cfg.frame_count - 1))
        for part in parts:
            if part.animation_data and part.animation_data.action:
                for fc in part.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
    set_markers(scene, {"pour_starts": starts, "pour_ends": ends, "jar_height": H, "jar_radius": R, "pours": len(pours),
                        "added": sum(c for _, c in pours[1:])})
    return actives


def _jar_camera(cfg, markers, frames) -> list:
    """Wide on the first pour, a push into the 'looks full' gaps, close and high for the small pours, then a low close-up
    of the packed jar. Keys are in frames."""
    R, H = markers["jar_radius"], markers["jar_height"]
    wide = fit_distance(R + 0.35, cfg.camera.focal_length)
    starts = [s for s in markers["pour_starts"] if s is not None]
    ends = markers["pour_ends"]
    full = (ends[0] + int(cfg.fps * 1.4)) if len(ends) else frames // 4      # the large rocks have settled: it looks full
    last = (ends[-1] + int(cfg.fps * 2.2)) if ends else frames - 90           # the last pour has settled
    last = min(last, frames - int(cfg.fps * 2.6))
    s1 = starts[1] if len(starts) > 1 else full + 30
    zt = H * 0.5
    keys = [orbit_key(1, (0, 0, zt), wide, 9, 0),
            orbit_key(ends[0] if ends else 40, (0, 0, zt), wide * 0.97, 9, 4),
            orbit_key(full, (0, 0, H * 0.72), wide * 0.74, 24, 10),            # push in, look down into the gaps
            orbit_key(s1 + int(cfg.fps * 0.5), (0, 0, H * 0.72), wide * 0.7, 26, 14),
            orbit_key(last, (0, 0, H * 0.55), wide * 0.76, 15, 22),
            orbit_key(frames - int(cfg.fps * 1.8), (0, 0, H * 0.5), wide * 0.7, 7, 16),    # the whole packed jar, label on
            orbit_key(frames, (0, 0, H * 0.46), wide * 0.58, 5, 26)]           # then a steady, sharp look through the glass at the packing
    return sorted({k[0]: k for k in keys}.values(), key=lambda k: k[0])


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
    heap = sum(1 for o in handle if o.location.z > markers["jar_height"] - 0.02)        # centres at or above the rim: sitting on top
    outside = sum(1 for o in handle if math.hypot(o.location.x, o.location.y) > markers["jar_radius"] + 0.05)
    scene.frame_set(1)
    path = _jar_camera(cfg, markers, frames)
    final_at = max(1, frames - round(cfg.fps * 3.2))
    schedule = [[1, "IS THIS JAR\nREALLY FULL?"]]
    if len(starts) > 1:
        schedule.append([starts[1] - 2, ""])
        schedule.append([final_at, f"{markers['added']} MORE\nFIT INSIDE"])
        schedule.append([frames - round(cfg.fps * 1.5), ""])               # the last close-up is left to the picture
    result = {"fill_levels": levels, "jar_height": markers["jar_height"], "above_rim": over, "heap_on_top": heap, "outside_jar": outside}
    markers.update(result)
    markers["label_schedule"] = schedule
    markers["camera_path"] = path
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
