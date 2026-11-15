"""Physics scene builders (requires bpy).

Each simulation type registers a builder in ``SIMULATORS``. Adding soft body / rigid body
later means adding a function here, not rewriting the engine.
"""

from __future__ import annotations

import bpy

from . import materials

# (top_z of the object when resting on the ground at z=0)
_OBJECT_TOP = {"sphere": 2.0, "cube": 2.0, "cylinder": 2.0, "cone": 2.0, "torus": 0.8}


def create_ground(scene, color, size: float = 40.0):
    half = size / 2
    mesh = bpy.data.meshes.new("Ground")
    mesh.from_pydata([(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("Ground", mesh)
    scene.collection.objects.link(obj)
    obj.modifiers.new("Collision", "COLLISION")
    materials.assign(obj, materials.principled("GroundMat", color, 0.0, 0.8))
    return obj


def create_collider(scene, object_type: str):
    """Create the object the cloth falls on. Returns (object, top_z)."""
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
    obj.name = "Collider"
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    obj.modifiers.new("Collision", "COLLISION")
    obj.collision.thickness_outer = 0.01
    obj.collision.cloth_friction = 5.0
    return obj, _OBJECT_TOP[object_type]


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


SIMULATORS = {"cloth": build_cloth_stage}
