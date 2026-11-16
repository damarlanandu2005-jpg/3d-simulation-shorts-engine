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


SIMULATORS = {
    "cloth_drape": build_cloth_stage,
    "cloth_objects": build_cloth_objects_stage,
    "multiple_balls": build_balls_stage,
    "ball_funnel": build_funnel_stage,
    "ring_toss": build_rings_stage,
}


def bake_for(cfg, scene, handle, frames: int) -> str:
    """Bake the physics of whatever the builder returned (a cloth object or a list of rigid bodies)."""
    if cfg.simulation == "rigid_body":
        return bake_rigid(scene, handle, 1, frames)
    return bake(scene, handle, 1, frames)
