"""Camera and on-screen label (requires bpy)."""

from __future__ import annotations

import math

import bpy
from mathutils import Vector


LABEL_Y = 0.85  # default label height in camera space


def add_camera(scene, cam_cfg, width: int, height: int):
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = cam_cfg.focal_length
    # Vertical output: fit the sensor to the vertical axis so the framing math is simple.
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36.0
    cam_data.clip_end = 200.0
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)

    target = bpy.data.objects.new("CameraTarget", None)
    scene.collection.objects.link(target)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    scene.camera = cam
    apply_camera(cam_cfg)
    return cam


def apply_camera(cam_cfg, target_xy=(0.0, 0.0)) -> None:
    """Position the existing camera. Called at build AND render time so camera edits in the config
    take effect without re-baking (the camera does not affect the physics)."""
    cam = bpy.data.objects["Camera"]
    cam.location = Vector((0.0, -cam_cfg.distance, cam_cfg.height))
    cam.data.lens = cam_cfg.focal_length
    bpy.data.objects["CameraTarget"].location = Vector((target_xy[0], target_xy[1], cam_cfg.target_z))


def set_label(text: str, size: float, y: float | None = None) -> None:
    """Update the existing label text. Also applied at render time (labels do not affect physics)."""
    obj = bpy.data.objects["Label"]
    obj.data.body = text
    obj.data.size = size
    if y is not None:
        obj.location.y = y


def add_label(scene, cam, text: str, size: float, material):
    """Text parented to the camera, so it stays in a fixed screen position."""
    curve = bpy.data.curves.new("Label", type="FONT")
    curve.body = text
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    obj = bpy.data.objects.new("Label", curve)
    scene.collection.objects.link(obj)
    obj.parent = cam
    # Camera looks down its local -Z. At depth 3 with a 36 mm sensor / 50 mm lens the visible
    # frame is about 2.16 units tall, so y=+0.85 sits near the top of the frame.
    obj.location = (0.0, LABEL_Y, -3.0)
    obj.data.materials.append(material)
    return obj


def add_card_text(scene, text: str, size: float, location, material):
    """World-space text facing the camera (cards are a flat title on a plain background)."""
    curve = bpy.data.curves.new("CardText", type="FONT")
    curve.body = text
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    obj = bpy.data.objects.new("CardText", curve)
    scene.collection.objects.link(obj)
    obj.rotation_euler = (math.pi / 2, 0.0, 0.0)  # text lies in XY by default; stand it up to face -Y
    obj.location = location
    obj.data.materials.append(material)
    return obj
