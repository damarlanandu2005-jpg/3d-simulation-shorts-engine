"""Camera and on-screen label (requires bpy)."""

from __future__ import annotations

import bpy
from mathutils import Vector


def add_camera(scene, cam_cfg, width: int, height: int):
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = cam_cfg.focal_length
    # Vertical output: fit the sensor to the vertical axis so the framing math is simple.
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36.0
    cam_data.clip_end = 200.0
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = Vector((0.0, -cam_cfg.distance, cam_cfg.height))
    scene.collection.objects.link(cam)

    target = bpy.data.objects.new("CameraTarget", None)
    target.location = Vector((0.0, 0.0, cam_cfg.target_z))
    scene.collection.objects.link(target)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    scene.camera = cam
    return cam


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
    obj.location = (0.0, 0.85, -3.0)
    obj.data.materials.append(material)
    return obj
