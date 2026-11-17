"""Materials and world lighting (requires bpy)."""

from __future__ import annotations

import bpy


def principled(name: str, color, metallic: float = 0.0, roughness: float = 0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(color)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def emission(name: str, color, strength: float = 1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = tuple(color)
    emit.inputs["Strength"].default_value = strength
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def assign(obj, mat) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def setup_world(scene, color, look: str = "classic") -> None:
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs["Color"].default_value = tuple(color)
    bg.inputs["Strength"].default_value = 1.0
    if look == "studio":                    # screen-space gradient: lighter glow behind the action, darker at the edges
        coord = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        nt.links.new(coord.outputs["Window"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
        c = tuple(color)
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (c[0] * 0.35, c[1] * 0.35, c[2] * 0.4, 1.0)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color = (c[0] * 1.5, c[1] * 1.5, c[2] * 1.6, 1.0)
        nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.8
    scene.world = world


def add_lights(scene, look: str = "classic") -> None:
    """Soft key light + fill so metal and glossy surfaces have something to reflect."""
    if look == "studio":
        _studio_lights(scene)
        return
    key_data = bpy.data.lights.new("Key", type="AREA")
    key_data.energy = 650.0
    key_data.size = 6.0
    key = bpy.data.objects.new("Key", key_data)
    key.location = (-4.0, -5.0, 8.0)
    key.rotation_euler = (0.9, 0.0, -0.5)
    scene.collection.objects.link(key)

    fill_data = bpy.data.lights.new("Fill", type="AREA")
    fill_data.energy = 250.0
    fill_data.size = 8.0
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.location = (5.0, -4.0, 4.0)
    fill.rotation_euler = (1.2, 0.0, 0.8)
    scene.collection.objects.link(fill)


def _studio_lights(scene) -> None:
    """Warm key from the front-left, cool rim from behind, soft top fill: depth and highlights on glossy objects."""
    def area(name, energy, size, loc, rot, color):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy, data.size, data.color = energy, size, color
        obj = bpy.data.objects.new(name, data)
        obj.location, obj.rotation_euler = loc, rot
        scene.collection.objects.link(obj)

    area("Key", 1500.0, 5.0, (-5.0, -6.0, 9.0), (0.85, 0.0, -0.5), (1.0, 0.95, 0.88))
    area("Rim", 1100.0, 4.0, (5.0, 7.0, 5.0), (-1.1, 0.0, 2.6), (0.55, 0.75, 1.0))
    area("Top", 500.0, 10.0, (0.0, 0.0, 12.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    area("Fill", 300.0, 8.0, (6.0, -4.0, 3.0), (1.3, 0.0, 0.9), (0.9, 0.95, 1.0))
