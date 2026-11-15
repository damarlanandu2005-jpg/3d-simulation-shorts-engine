"""Config loading and validation.

Pure Python on purpose: this module must never import ``bpy`` so that it can be
unit-tested and used by the orchestrator without Blender installed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

SUPPORTED_SIMULATIONS = ("cloth",)
SUPPORTED_OBJECTS = ("sphere", "cube", "cylinder", "torus", "cone")
SUPPORTED_CLOTH_STYLES = ("wireframe", "solid")
SUPPORTED_ENGINES = ("CYCLES",)
SUPPORTED_DEVICES = ("AUTO", "CPU", "GPU")


class ConfigError(ValueError):
    """Raised when a config file is invalid."""


@dataclass
class PhysicsCfg:
    gravity: float = 9.81
    mass: float = 0.3
    tension: float = 15.0
    compression: float = 15.0
    shear: float = 15.0
    bending: float = 0.5
    air_damping: float = 1.0
    quality: int = 7  # Blender "quality steps" per frame
    self_collision: bool = True
    collision_distance: float = 0.015


@dataclass
class CameraCfg:
    distance: float = 11.0
    height: float = 4.8
    target_z: float = 1.0
    focal_length: float = 50.0


@dataclass
class MaterialCfg:
    object_color: list = field(default_factory=lambda: [0.05, 0.55, 0.1, 1.0])
    object_roughness: float = 0.15
    cloth_color: list = field(default_factory=lambda: [0.8, 0.8, 0.85, 1.0])
    cloth_metallic: float = 1.0
    cloth_roughness: float = 0.25
    cloth_style: str = "wireframe"  # "wireframe" shows the mesh density; "solid" is plain cloth
    ground_color: list = field(default_factory=lambda: [0.45, 0.45, 0.47, 1.0])
    background_color: list = field(default_factory=lambda: [0.72, 0.72, 0.74, 1.0])


@dataclass
class RenderCfg:
    engine: str = "CYCLES"
    samples: int = 32
    max_bounces: int = 4
    denoise: bool = True
    device: str = "AUTO"  # AUTO tries OPTIX -> CUDA -> CPU


@dataclass
class OutputCfg:
    width: int = 720
    height: int = 1280
    dir: str = "output"


@dataclass
class LabelCfg:
    # {faces} = exact count, {faces_short} = 64 / 1024 / 4096 / 16K / 1 M
    template: str = "{faces_short} FACE"
    size: float = 0.2
    color: list = field(default_factory=lambda: [0.08, 0.08, 0.08, 1.0])


@dataclass
class VideoCfg:
    hook_seconds: float = 2.0
    crf: int = 18


@dataclass
class ObjectCfg:
    type: str = "sphere"
    cloth_size: float = 4.4
    cloth_drop_height: float = 1.3  # metres above the top of the object


@dataclass
class Config:
    name: str = "cloth_sphere"
    simulation: str = "cloth"
    seed: int = 0
    resolutions: list = field(default_factory=lambda: [64, 1024, 4096, 16384])
    fps: int = 30
    duration: float = 4.0  # seconds per stage
    object: ObjectCfg = field(default_factory=ObjectCfg)
    physics: PhysicsCfg = field(default_factory=PhysicsCfg)
    camera: CameraCfg = field(default_factory=CameraCfg)
    material: MaterialCfg = field(default_factory=MaterialCfg)
    render: RenderCfg = field(default_factory=RenderCfg)
    output: OutputCfg = field(default_factory=OutputCfg)
    label: LabelCfg = field(default_factory=LabelCfg)
    video: VideoCfg = field(default_factory=VideoCfg)

    @property
    def frame_count(self) -> int:
        return max(1, round(self.duration * self.fps))

    @property
    def root_dir(self) -> Path:
        return Path(self.output.dir) / self.name

    def stages(self) -> list["Stage"]:
        return [make_stage(self, i, faces) for i, faces in enumerate(self.resolutions)]

    def final_video_path(self) -> Path:
        return self.root_dir / f"{self.name}.mp4"


@dataclass
class Stage:
    index: int
    faces: int
    segments: int
    label: str
    blend_path: Path
    frames_dir: Path
    clip_path: Path


def faces_to_segments(faces: int) -> int:
    """Cloth is an n x n grid of quads, so the face count must be a perfect square."""
    if not isinstance(faces, int) or isinstance(faces, bool):
        raise ConfigError(f"resolution must be an integer face count, got {faces!r}")
    n = math.isqrt(faces) if faces > 0 else 0
    if n < 2 or n * n != faces:
        raise ConfigError(
            f"resolution {faces} is not a perfect square >= 4 (cloth is an n x n grid; "
            "use e.g. 64, 1024, 4096, 16384)"
        )
    return n


def short_face_label(faces: int) -> str:
    if faces >= 1_000_000:
        return f"{round(faces / 1_000_000)} M"
    if faces >= 16384:
        return f"{faces // 1024}K" if faces % 1024 == 0 else f"{round(faces / 1000)}K"
    return str(faces)


def format_label(template: str, faces: int) -> str:
    return template.format(faces=faces, faces_short=short_face_label(faces))


def make_stage(cfg: Config, index: int, faces: int) -> Stage:
    seg = faces_to_segments(faces)
    root = cfg.root_dir
    tag = f"stage_{index:02d}_{faces}"
    return Stage(
        index=index,
        faces=faces,
        segments=seg,
        label=format_label(cfg.label.template, faces),
        blend_path=root / tag / f"{tag}.blend",
        frames_dir=root / tag / "frames",
        clip_path=root / tag / f"{tag}.mp4",
    )


def _build(cls, data: dict, path: str):
    """Build a dataclass from a dict, rejecting unknown keys (catches typos)."""
    if not isinstance(data, dict):
        raise ConfigError(f"'{path}' must be an object, got {type(data).__name__}")
    known = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(known)
    if unknown:
        raise ConfigError(f"unknown key(s) in '{path}': {sorted(unknown)}")
    kwargs = {}
    for key, value in data.items():
        default = getattr(cls(), key)
        if is_dataclass(default):
            kwargs[key] = _build(type(default), value, f"{path}.{key}" if path else key)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def _check_color(name: str, value: Any) -> None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in value)
    ):
        raise ConfigError(f"{name} must be [r, g, b, a] with values in 0..1, got {value!r}")


def validate(cfg: Config) -> Config:
    if cfg.simulation not in SUPPORTED_SIMULATIONS:
        raise ConfigError(
            f"simulation '{cfg.simulation}' is not implemented yet; supported: {SUPPORTED_SIMULATIONS}"
        )
    if cfg.object.type not in SUPPORTED_OBJECTS:
        raise ConfigError(f"object.type must be one of {SUPPORTED_OBJECTS}, got {cfg.object.type!r}")
    if not cfg.name or any(c in cfg.name for c in "/\\ "):
        raise ConfigError("name must be non-empty and contain no spaces or slashes")
    if not cfg.resolutions:
        raise ConfigError("resolutions must contain at least one face count")
    for faces in cfg.resolutions:
        faces_to_segments(faces)
    if cfg.fps < 1 or cfg.fps > 120:
        raise ConfigError("fps must be between 1 and 120")
    if cfg.duration <= 0 or cfg.duration > 60:
        raise ConfigError("duration must be > 0 and <= 60 seconds")
    if cfg.output.width < 16 or cfg.output.height < 16:
        raise ConfigError("output width/height are too small")
    if cfg.output.width % 2 or cfg.output.height % 2:
        raise ConfigError("output width/height must be even (H.264 requirement)")
    if cfg.output.height <= cfg.output.width:
        raise ConfigError("output must be vertical (height > width) for Shorts")
    if cfg.render.engine not in SUPPORTED_ENGINES:
        raise ConfigError(f"render.engine must be one of {SUPPORTED_ENGINES}")
    if cfg.render.device not in SUPPORTED_DEVICES:
        raise ConfigError(f"render.device must be one of {SUPPORTED_DEVICES}")
    if cfg.render.samples < 1:
        raise ConfigError("render.samples must be >= 1")
    if cfg.material.cloth_style not in SUPPORTED_CLOTH_STYLES:
        raise ConfigError(f"material.cloth_style must be one of {SUPPORTED_CLOTH_STYLES}")
    for name in ("object_color", "cloth_color", "ground_color", "background_color"):
        _check_color(f"material.{name}", getattr(cfg.material, name))
    _check_color("label.color", cfg.label.color)
    if cfg.physics.quality < 1:
        raise ConfigError("physics.quality must be >= 1")
    try:
        format_label(cfg.label.template, 64)
    except (KeyError, IndexError, ValueError) as exc:
        raise ConfigError(f"label.template is invalid: {exc!r}") from exc
    return cfg


def from_dict(data: dict) -> Config:
    return validate(_build(Config, data, ""))


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file is not valid JSON: {exc}") from exc
    return from_dict(data)
