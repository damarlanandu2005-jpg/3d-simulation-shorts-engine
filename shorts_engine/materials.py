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


def setup_world(scene, color) -> None:
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = tuple(color)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world


def add_lights(scene) -> None:
    """Soft key light + fill so metal and glossy surfaces have something to reflect."""
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
