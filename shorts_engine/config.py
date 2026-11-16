"""Config loading and validation.

Pure Python on purpose: this module must never import ``bpy`` so that it can be
unit-tested and used by the orchestrator without Blender installed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

SUPPORTED_SIMULATIONS = ("cloth", "rigid_body")
SUPPORTED_OBJECTS = ("sphere", "cube", "cylinder", "torus", "cone")
SUPPORTED_CLOTH_STYLES = ("wireframe", "solid")
SUPPORTED_ENGINES = ("CYCLES",)
SUPPORTED_DEVICES = ("AUTO", "CPU", "GPU")
SUPPORTED_DENOISERS = ("OPENIMAGEDENOISE", "OPTIX")
SUPPORTED_HOOK_MODES = ("tail", "closeup", "none")
_CAMERA_OVERRIDE_KEYS = ("distance", "height", "target_z", "focal_length")


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
    # Optional per-stage overrides, aligned with `resolutions`; missing entries use the values above.
    # e.g. [{}, {"distance": 10}, {"distance": 9.2}, {"distance": 8.6}]
    per_stage: list = field(default_factory=list)


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
    # Used only when denoise is true. OPTIX needs an OptiX GPU; on any other device the renderer
    # falls back to OPENIMAGEDENOISE and says so.
    denoiser: str = "OPENIMAGEDENOISE"


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
class HookCloseupCfg:
    """Camera push-in over the finished cloth, rendered from the last stage's baked cache."""

    distance_start: float = 7.0
    distance_end: float = 5.5
    height: float = 3.0
    target_z: float = 1.3
    samples: int = 0  # 0 = same as render.samples (close-ups of thin wires may want more)


@dataclass
class HookCfg:
    mode: str = "tail"  # tail = last hook_seconds of the final clip (V1 behaviour) | closeup | none
    # closeup only; "\n" = line break; placeholders {total_ratio} {first} {last}. Empty = no text.
    text: str = ""
    text_size: float = 0.12
    text_y: float = 0.7  # vertical position of the hook text in the frame (camera units)
    closeup: HookCloseupCfg = field(default_factory=HookCloseupCfg)


@dataclass
class CardsCfg:
    """Short title cards between stages showing how much denser the next mesh is."""

    enabled: bool = False
    seconds: float = 0.5
    title: str = "\u00d7{ratio}"  # {ratio} = next faces / this faces, e.g. x16
    subtitle: str = "MORE FACES"
    title_size: float = 0.9
    subtitle_size: float = 0.28
    samples: int = 8


@dataclass
class AudioCfg:
    """Audio layer mixed into the final MP4 by FFmpeg (the video itself is never re-encoded).

    ``enabled`` is the master switch. Background music (``music_enabled``) plays under the whole Short;
    simulation sound effects (``sfx_enabled``) are placed at detected physical events.
    """

    enabled: bool = False
    music_enabled: bool = True
    music: str = "assets/audio/music/default_music.wav"  # relative paths resolve from the project root, then cwd
    volume_db: float = -18.0  # gain applied to the music; keep it subtle, the simulation is the star
    fade_in: float = 0.5  # seconds (music only)
    fade_out: float = 1.0
    sfx_enabled: bool = False
    sfx_volume_db: float = -8.0  # gain of a strength-1.0 effect; weaker events are quieter (amplitude ~ strength)
    sfx_dir: str = "assets/audio/sfx"  # holds <sound>.wav files
    sfx_min_strength: float = 0.15  # events weaker than this are dropped
    sfx_min_gap: float = 0.15  # seconds; same-sound events closer than this are merged (the stronger one stays)
    sfx_max_events: int = 24  # hard cap against sound spam (strongest events are kept)


@dataclass
class VideoCfg:
    hook_seconds: float = 2.0
    crf: int = 18
    hook: HookCfg = field(default_factory=HookCfg)
    cards: CardsCfg = field(default_factory=CardsCfg)


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
    audio: AudioCfg = field(default_factory=AudioCfg)

    @property
    def frame_count(self) -> int:
        return max(1, round(self.duration * self.fps))

    def stage_frames(self, index: int) -> int:
        """Frames shown for stage ``index`` (every stage has ``frame_count`` frames unless an experiment sets a longer payoff)."""
        return self.frame_count

    @property
    def root_dir(self) -> Path:
        return Path(self.output.dir) / self.name

    def stages(self) -> list["Stage"]:
        return [make_stage(self, i, faces) for i, faces in enumerate(self.resolutions)]

    @property
    def stage_count(self) -> int:
        return len(self.resolutions)

    def final_video_path(self) -> Path:
        return self.root_dir / f"{self.name}.mp4"

    @property
    def experiment_type(self) -> str:
        """Experiment type (derived, so it is not part of the serialised config). A plain ``Config`` is the V1 cloth drape."""
        return "cloth_drape"

    def validate_stages(self) -> None:
        if not self.resolutions:
            raise ConfigError("resolutions must contain at least one face count")
        for faces in self.resolutions:
            faces_to_segments(faces)

    def check_label(self) -> None:
        format_label(self.label.template, 64)

    def check_hook_text(self) -> None:
        try:
            self.video.hook.text.format(total_ratio="256", first="64", last="16,384")
        except (KeyError, IndexError, ValueError) as exc:
            raise ConfigError(f"video.hook.text is invalid (allowed: {{total_ratio}} {{first}} {{last}}): {exc!r}") from exc

    def silent_video_path(self) -> Path:
        """Video before the music is mixed in (only produced when audio is enabled)."""
        return self.root_dir / f"{self.name}_silent.mp4"

    def music_path(self) -> Path:
        return resolve_asset(self.audio.music)

    def stage_events_path(self, index: int) -> Path:
        return self.stages()[index].blend_path.parent / "events.json"

    def sfx_path(self, sound: str) -> Path:
        return resolve_asset(f"{self.audio.sfx_dir}/{sound}.wav")

    def camera_for_stage(self, index: int) -> CameraCfg:
        """Base camera merged with this stage's optional override."""
        override = self.camera.per_stage[index] if index < len(self.camera.per_stage) else {}
        return replace(self.camera, per_stage=[], **override)

    @property
    def hook_frames_dir(self) -> Path:
        return self.root_dir / "hook" / "frames"

    @property
    def hook_clip_path(self) -> Path:
        return self.root_dir / "hook.mp4"

    def hook_frame_range(self) -> tuple[int, int]:
        """Last N frames of the last stage's simulation (used by the closeup hook)."""
        n = min(self.frame_count, max(1, round(self.video.hook_seconds * self.fps)))
        return self.frame_count - n + 1, self.frame_count

    def hook_text(self) -> str:
        """Hook text with {total_ratio}, {first}, {last} filled in from `resolutions`."""
        first, last = self.resolutions[0], self.resolutions[-1]
        return self.video.hook.text.format(total_ratio=format_ratio(first, last), first=f"{first:,}", last=f"{last:,}")

    def cards(self) -> list["Card"]:
        if not self.video.cards.enabled:
            return []
        c = self.video.cards
        out = []
        for i in range(len(self.resolutions) - 1):
            ratio = format_ratio(self.resolutions[i], self.resolutions[i + 1])
            out.append(Card(
                index=i,
                ratio=ratio,
                title=c.title.format(ratio=ratio),
                subtitle=c.subtitle,
                frames=max(1, round(c.seconds * self.fps)),
                frames_dir=self.root_dir / f"card_{i:02d}" / "frames",
                clip_path=self.root_dir / f"card_{i:02d}" / f"card_{i:02d}.mp4",
            ))
        return out


@dataclass
class ExperimentConfig(Config):
    """Config of every experiment other than the V1 cloth drape. Same pipeline, experiment-specific data.

    ``params`` holds the experiment's physical parameters (resolved with defaults from its template),
    ``stage_values`` the progression shown in the video (e.g. 1 -> 10 -> 50 -> 100 balls).
    The V1 cloth drape stays a plain ``Config`` so its serialised form (and the Phase 1 golden snapshot) never changes.
    """

    simulation: str = "rigid_body"
    resolutions: list = field(default_factory=list)   # unused here (cloth_drape's stage parameter)
    experiment: str = "multiple_balls"
    shape: str = "sphere"                             # experiment.object
    params: dict = field(default_factory=dict)
    stage_values: list = field(default_factory=list)
    camera_preset: str = "wide"                       # wide | close | top | side | manual (use camera.* as written)
    camera_motion: str = "static"                     # static | push_in | follow | impact
    hook_window: str = "start"                        # which part of the last stage the hook replays: start | end
    stage_extras: list = field(default_factory=list)  # per-stage overrides of other experiment params (e.g. {"balls": 30})
    payoff_duration: float = 0.0                      # seconds of the final (payoff) stage; 0 = same as ``duration``

    @property
    def frame_count(self) -> int:                     # the simulation is baked for the longest stage (the final one)
        return max(1, round(max(self.duration, self.payoff_duration) * self.fps))

    def stage_frames(self, index: int) -> int:
        if self.payoff_duration > 0 and index == len(self.stage_values) - 1:
            return max(1, round(self.payoff_duration * self.fps))
        return max(1, round(self.duration * self.fps))

    def stage_params(self, index: int) -> dict:
        """Experiment params in force for stage ``index``: the shared params plus that stage's overrides."""
        extra = self.stage_extras[index] if index < len(self.stage_extras) else {}
        return {**self.params, **extra}

    @property
    def template(self):
        from .templates import get_template
        return get_template(self.experiment)

    @property
    def experiment_type(self) -> str:
        return self.experiment

    @property
    def stage_count(self) -> int:
        return len(self.stage_values)

    def validate_stages(self) -> None:
        from .camera_rig import MOTIONS, PRESETS
        t = self.template
        if self.simulation != t.simulation:
            raise ConfigError(f"simulation {self.simulation!r} does not match experiment {t.name!r} ({t.simulation})")
        if not self.stage_values:
            raise ConfigError("stages must contain at least one stage")
        if self.shape not in t.objects:
            raise ConfigError(f"experiment.object {self.shape!r} is not valid for {t.name}; allowed: {list(t.objects)}")
        resolved = t.resolve_params(self.params)
        for i, v in enumerate(self.stage_values):
            t.check_stage_value(v, f"stages[{i}].params.{t.stage_param}")
        if self.stage_extras and len(self.stage_extras) != len(self.stage_values):
            raise ConfigError("stage_extras must have one entry per stage")
        if self.payoff_duration and self.payoff_duration < self.duration:
            raise ConfigError("simulation.payoff_duration must be >= simulation.duration (the final stage is the longest)")
        if t.validate is not None:                      # cross-parameter checks: reject broken scenes instead of rendering them
            for i in range(len(self.stage_values)):
                t.validate(t.resolve_params(self.stage_params(i)), list(self.stage_values), self.shape)
        if self.camera_preset not in PRESETS + ("manual",):
            raise ConfigError(f"camera.preset must be one of {PRESETS + ('manual',)}, got {self.camera_preset!r}")
        if self.hook_window not in ("start", "end", "clue"):
            raise ConfigError(f"hook.window must be 'start', 'end' or 'clue', got {self.hook_window!r}")
        if self.hook_window == "clue" and "reveal_start" not in t.params:
            raise ConfigError(f"hook.window 'clue' needs an experiment with a reveal (not {t.name})")
        if self.camera_motion not in MOTIONS:
            raise ConfigError(f"camera.motion must be one of {MOTIONS}, got {self.camera_motion!r}")

    def stages(self) -> list["Stage"]:
        t, root = self.template, self.root_dir
        out = []
        for i, v in enumerate(self.stage_values):
            tag = f"stage_{i:02d}_{value_tag(v)}"
            out.append(Stage(index=i, faces=0, segments=0, label=self.stage_label(v, i),
                             blend_path=root / tag / f"{tag}.blend", frames_dir=root / tag / "frames",
                             clip_path=root / tag / f"{tag}.mp4", params={**(self.stage_extras[i] if i < len(self.stage_extras) else {}),
                                                                           t.stage_param: v},
                             frames=self.stage_frames(i)))
        return out

    def check_label(self) -> None:
        for i, v in enumerate(self.stage_values):
            self.stage_label(v, i)

    def hook_frame_range(self) -> tuple[int, int]:
        n = min(self.frame_count, max(1, round(self.video.hook_seconds * self.fps)))
        if self.hook_window == "clue":                  # the moments just before the answer is revealed (e.g. the covered sheet)
            end = max(n, round(self.params["reveal_start"] * self.fps) - 1)
            return (end - n + 1, end)
        return (1, n) if self.hook_window == "start" else (self.frame_count - n + 1, self.frame_count)

    def stage_label(self, value, index: int | None = None) -> str:
        t = self.template
        p = {**(self.stage_params(index) if index is not None else self.params), "shape": self.shape}
        return self.label.template.format(**{**p, t.stage_param: value, **t.label_values(p, value)})

    def cards(self) -> list["Card"]:
        return []

    def check_hook_text(self) -> None:
        t = self.template
        text = self.video.hook.text
        if text in ("", "auto"):
            return
        try:
            text.format(**t.hook_values({**t.resolve_params(self.stage_params(len(self.stage_values) - 1)), "shape": self.shape},
                                        self.stage_values or [1]))
        except (KeyError, IndexError, ValueError, ZeroDivisionError) as exc:
            raise ConfigError(f"video.hook.text is invalid for {t.name} (allowed placeholders: "
                              f"{sorted(t.hook_values({**t.resolve_params(self.params), 'shape': self.shape}, [1, 2]))}): {exc!r}") from exc

    def hook_text(self) -> str:
        t = self.template
        vals = t.hook_values({**self.stage_params(len(self.stage_values) - 1), "shape": self.shape}, self.stage_values,
                             {**self.stage_params(0), "shape": self.shape})
        text = self.video.hook.text
        if text == "auto":
            text = t.hooks[self.seed % len(t.hooks)]
        text = text.format(**vals)
        if "\n" not in text:                                   # fit the 9:16 frame: wrap long questions onto lines
            import textwrap
            text = "\n".join(textwrap.wrap(text, 16))
        return text

    def camera_for_stage(self, index: int) -> CameraCfg:
        override = self.camera.per_stage[index] if index < len(self.camera.per_stage) else {}
        if self.camera_preset == "manual":
            return replace(self.camera, per_stage=[], **override)
        from .camera_rig import fit_camera
        t = self.template
        region = t.frame_region(self.stage_params(index), self.stage_values[index])
        fit = fit_camera(region.half_width, region.top, region.bottom, self.camera_preset, self.camera.focal_length,
                         elevation=t.camera_defaults.get("elevation"), half_depth=region.half_depth)
        return replace(self.camera, per_stage=[], **{**fit, **override})


def value_tag(v) -> str:
    """File-name-safe tag of a stage value (0.42 -> 0p42)."""
    return (f"{v:g}" if isinstance(v, float) else str(v)).replace(".", "p").replace("-", "m")


@dataclass
class Card:
    index: int  # shown after stage `index`
    ratio: str
    title: str
    subtitle: str
    frames: int
    frames_dir: Path
    clip_path: Path


@dataclass
class Stage:
    index: int
    faces: int
    segments: int
    label: str
    blend_path: Path
    frames_dir: Path
    clip_path: Path
    params: dict = field(default_factory=dict)   # experiment-specific stage parameters (e.g. {"balls": 50})
    frames: int = 0                              # frames shown for this stage (0 = the config's frame_count)


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


def format_ratio(smaller: int, larger: int) -> str:
    r = larger / smaller
    return str(int(r)) if r == int(r) else f"{r:.1f}"


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


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_asset(path: str) -> Path:
    """Absolute paths are used as given; relative ones are looked up from the project root, then the cwd."""
    p = Path(path)
    if p.is_absolute():
        return p
    for base in (PROJECT_ROOT, Path.cwd()):
        if (base / p).exists():
            return base / p
    return PROJECT_ROOT / p


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
    cfg.validate_stages()
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
    if cfg.render.denoiser not in SUPPORTED_DENOISERS:
        raise ConfigError(f"render.denoiser must be one of {SUPPORTED_DENOISERS}")
    _validate_camera(cfg)
    _validate_video(cfg)
    _validate_simulation(cfg)
    try:
        cfg.check_label()
    except (KeyError, IndexError, ValueError) as exc:
        raise ConfigError(f"label.template is invalid: {exc!r}") from exc
    return cfg


def _positive(name: str, value: Any, upper: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0 or (upper is not None and value > upper):
        raise ConfigError(f"{name} must be a number > 0" + (f" and <= {upper}" if upper is not None else "") + f", got {value!r}")


def _validate_simulation(cfg: Config) -> None:
    ph = cfg.physics
    _positive("physics.gravity", ph.gravity, 100)
    _positive("physics.mass", ph.mass)
    for name in ("tension", "compression", "shear"):
        _positive(f"physics.{name}", getattr(ph, name))
    for name in ("bending", "air_damping"):
        value = getattr(ph, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ConfigError(f"physics.{name} must be a number >= 0, got {value!r}")
    if not isinstance(ph.quality, int) or isinstance(ph.quality, bool) or ph.quality < 1:
        raise ConfigError("physics.quality must be an integer >= 1")
    _positive("physics.collision_distance", ph.collision_distance, 1)
    _positive("object.cloth_size", cfg.object.cloth_size)
    _positive("object.cloth_drop_height", cfg.object.cloth_drop_height)
    if not isinstance(cfg.seed, int) or isinstance(cfg.seed, bool) or cfg.seed < 0:
        raise ConfigError("seed must be an integer >= 0")
    if cfg.render.max_bounces < 0:
        raise ConfigError("render.max_bounces must be >= 0")


def _validate_camera(cfg: Config) -> None:
    if len(cfg.camera.per_stage) > cfg.stage_count:
        raise ConfigError("camera.per_stage has more entries than stages")
    for i, override in enumerate(cfg.camera.per_stage):
        if not isinstance(override, dict):
            raise ConfigError(f"camera.per_stage[{i}] must be an object")
        bad = set(override) - set(_CAMERA_OVERRIDE_KEYS)
        if bad:
            raise ConfigError(f"camera.per_stage[{i}] has unknown key(s) {sorted(bad)}; allowed: {_CAMERA_OVERRIDE_KEYS}")
        for key, value in override.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ConfigError(f"camera.per_stage[{i}].{key} must be a number")
            if key in ("distance", "focal_length") and value <= 0:
                raise ConfigError(f"camera.per_stage[{i}].{key} must be > 0")


def _validate_video(cfg: Config) -> None:
    v = cfg.video
    if v.hook_seconds < 0:
        raise ConfigError("video.hook_seconds must be >= 0")
    if v.hook.mode not in SUPPORTED_HOOK_MODES:
        raise ConfigError(f"video.hook.mode must be one of {SUPPORTED_HOOK_MODES}")
    cfg.check_hook_text()
    if v.hook.mode == "closeup":
        c = v.hook.closeup
        if v.hook_seconds <= 0:
            raise ConfigError("video.hook_seconds must be > 0 for the closeup hook")
        if c.distance_start <= 0 or c.distance_end <= 0:
            raise ConfigError("video.hook.closeup distances must be > 0")
        if c.samples < 0:
            raise ConfigError("video.hook.closeup.samples must be >= 0")
    if v.cards.enabled:
        c = v.cards
        if cfg.experiment_type != "cloth_drape":
            raise ConfigError("video.cards (multiplier cards) are only available for cloth_drape")
        if len(cfg.resolutions) < 2:
            raise ConfigError("video.cards needs at least two resolutions")
        if any(b <= a for a, b in zip(cfg.resolutions, cfg.resolutions[1:])):
            raise ConfigError("video.cards needs strictly increasing resolutions (the card shows a multiplier)")
        if not 0 < c.seconds <= 3:
            raise ConfigError("video.cards.seconds must be > 0 and <= 3")
        if c.samples < 1:
            raise ConfigError("video.cards.samples must be >= 1")
        try:
            c.title.format(ratio="16")
        except (KeyError, IndexError, ValueError) as exc:
            raise ConfigError(f"video.cards.title is invalid: {exc!r}") from exc
    a = cfg.audio
    if a.enabled:
        if a.music_enabled and (not isinstance(a.music, str) or not a.music):
            raise ConfigError("audio.music must be a file path when audio.music_enabled is true")
        if not -60 <= a.volume_db <= 6:
            raise ConfigError("audio.volume_db must be between -60 and 6")
        if a.fade_in < 0 or a.fade_out < 0:
            raise ConfigError("audio.fade_in / audio.fade_out must be >= 0")
        if not a.music_enabled and not a.sfx_enabled:
            raise ConfigError("audio.enabled needs audio.music_enabled and/or audio.sfx_enabled")
        if not -60 <= a.sfx_volume_db <= 6:
            raise ConfigError("audio.sfx_volume_db must be between -60 and 6")
        if not 0 <= a.sfx_min_strength <= 1:
            raise ConfigError("audio.sfx_min_strength must be within 0..1")
        if a.sfx_min_gap < 0 or a.sfx_max_events < 0:
            raise ConfigError("audio.sfx_min_gap and audio.sfx_max_events must be >= 0")


def from_dict(data: dict) -> Config:
    """Build a validated Config from either the flat (V1/V1.1) format or the experiment format (see experiment.py)."""
    if isinstance(data, dict) and ("experiment" in data or "schema_version" in data):
        from .experiment import experiment_to_legacy  # lazy: experiment.py imports this module
        data = experiment_to_legacy(data)
    cls = ExperimentConfig if isinstance(data, dict) and "experiment" in data else Config
    return validate(_build(cls, data, ""))


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config file is not valid JSON: {exc}") from exc
    return from_dict(data)
