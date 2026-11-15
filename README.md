# 3d-simulation-shorts-engine

Generates vertical (9:16) "satisfying simulation" Shorts from a JSON config using Blender's built-in
cloth physics and FFmpeg. V1 makes one video format:

```
HOOK (last seconds of the best clip) -> 64 FACE -> 1024 FACE -> 4096 FACE -> 16K FACE
```

Each stage is a full-screen clip of the same cloth dropping on an object, simulated at a different
mesh density, with a text label. Clips are joined with FFmpeg. Everything is driven by a config file,
so changing the object, resolutions, physics, camera or label does not need code changes.

Not in V1 (on purpose): AI agents, Ollama, YouTube upload, a render farm, audio.

## SimMorph: the physics experiment generator (Phases 3-13)

The same pipeline (Blender physics bake -> Cycles render -> FFmpeg -> music + physics SFX -> quality check) now
drives several experiments. An experiment is a *template* (`shorts_engine/templates.py`): parameters with valid
ranges, the stage progression, labels, hook questions, camera framing, plus a Blender scene builder
(`shorts_engine/simulation.py`). Nothing else is duplicated. An experiment is registered only after it has run in
real Blender (`tests/test_experiments_blender.py`).

| experiment | physics | stage progression | hook examples |
| --- | --- | --- | --- |
| `cloth_drape` (V1.1 reference, frozen) | Blender cloth | mesh resolution 64 -> 16384 faces | "WHAT HAPPENS WHEN WE ADD 256x MORE FACES?" |
| `multiple_balls` | rigid bodies (sphere / cube / cylinder) in an arena | 1 -> 10 -> 50 -> 100 objects | "WHAT HAPPENS WHEN WE DROP 100 BALLS?" |
| `ball_funnel` | rigid bodies through a funnel | hole 5x -> 1.7x ball size (jams) | "HOW SMALL CAN THE HOLE GET?" |
| `ring_toss` | rigid-body torus rings over a pole | ring hole 2.5x -> 0.85x pole radius | "WHAT HAPPENS WHEN THE RING GETS SMALLER?" |
| `cloth_objects` | cloth over several objects (spheres, cubes, rings...) | 1 -> 4 objects | "WHAT HAPPENS WHEN THE CLOTH MEETS 4 OBJECTS?" |

`python -m shorts_engine.library experiments` lists them; `python -m shorts_engine.experiment list` shows parameters.

### Configuration (schema v2, see also "Experiment configuration" below)

```json
{ "schema_version": 2, "name": "balls_demo", "seed": 3,
  "experiment": {"type": "multiple_balls", "object": "sphere", "params": {"restitution": 0.7, "drop_height": 3.0}},
  "simulation": {"fps": 30, "duration": 3.0},
  "stages": [{"params": {"balls": 1}}, {"params": {"balls": 10}}, {"params": {"balls": 100}, "camera": {"distance": 15}}],
  "camera": {"preset": "wide", "motion": "push_in"},
  "hook": {"mode": "closeup", "seconds": 2.0, "window": "start", "text": "auto"},
  "render": {"samples": 16, "denoise": false}, "output": {"width": 720, "height": 1280},
  "audio": {"enabled": true, "music_enabled": true, "sfx_enabled": true} }
```

Examples: `configs/experiments/*.json`. Old flat configs (`configs/v1_1_a_baseline.json`) still work unchanged.

* **Stages** carry the experiment's own parameter (`balls`, `hole_radius`, `hole_ratio`, `objects`, `faces`) and an
  optional camera override. Labels come from the template (`"{balls} {ball_word}"`) or `label.template`.
* **Hooks**: `hook.text` may use `{first} {last} {total_ratio} {things}` and any experiment parameter, or `"auto"`
  (a template question chosen by the seed). `hook.window` picks which part of the last stage is replayed (`start` = the
  action for rigid bodies, `end` = the settled cloth).
* **Camera**: `preset` = `wide | close | top | side` (distance/height are *computed* so the experiment's region is
  never clipped; verified by projecting the region corners) or `manual`; `motion` = `static | push_in | follow | impact`.
* **Audio**: music + SFX as before. Events come from the simulation: cloth contact distances (cloth experiments) or
  velocity impulses of every rigid body (`events.detect_impulses`: bounce, landing, ball-ball/wall/funnel collisions),
  so many simultaneous impacts become a bounded set of cues (`sfx_max_events`).
* **Presets**: `720p` is the fast production/testing preset, `1080p` the quality preset. No-denoise is the default;
  OptiX denoising is never required (it failed on the tested Kaggle T4).

### Run locally

```
pip install -r requirements.txt                      # bpy 4.5 needs Python 3.11; FFmpeg on PATH
python -m shorts_engine.render --config configs/experiments/multiple_balls_100.json --use-bpy
# -> output/multiple_balls_100/multiple_balls_100.mp4 + benchmark.json + metadata.json + qc_report.json
```

### Batch generation

```
python -m shorts_engine.batch --experiment multiple_balls --variations 10 --seed auto --out output/batches --run --use-bpy
python -m shorts_engine.batch --experiment auto --variations 8 --out output/batches        # configs + manifest only
```

Each video gets a unique name, seed and config (`<experiment>_s<seed>_<index>`), a *physical* variation record (object
count/size, bounciness, friction, drop height, hole size, shape, stage progression, mesh density - never just a colour;
`shorts_engine/variation.py`), a benchmark, metadata and a QC report. `auto` balances experiment types and stays
physically far from videos already in the library (`diversity.py`, `library.py`). One failing video never stops the
batch; finished identical videos are skipped on re-run; a different config is never overwritten.
`python -m shorts_engine.library index output/batches` builds `library.json`.

### Quality control

`render` runs `shorts_engine/qc.py` after every full render (also `python -m shorts_engine.qc --config CFG`): video
exists, valid H.264 stream, resolution, 9:16 aspect, fps, duration vs the planned timeline, every frame present,
clean decode, audio stream when enabled, audio/video duration match, benchmark.json and metadata.json. Exit code 3 on failure.

### Run through Kaggle

Actions > `kaggle-gpu-test` > Run workflow, branch `v1.1`. `test_config` = `baseline | optix | 1080p` (V1.1, unchanged)
or `multiple_balls | ball_funnel | ring_toss | cloth_objects`; optional `config_path` (a validated
`configs/**.json`); or batch mode: `batch_variations` (1-12), `batch_experiment`, `batch_seed`, `preset`.
Secrets stay `KAGGLE_USERNAME` / `KAGGLE_API_TOKEN` (via env only; never in the kernel or the logs).

### Limitations

* Rigid-body experiments use Blender's Bullet engine, baked once to keyframes; there is no initial-velocity
  parameter (drop height is the energy knob) and no fluid/particle experiment.
* Ring and funnel meshes use Bullet's triangle-mesh shape; very thin or very fast objects can tunnel (the defaults and
  ranges were chosen so they do not; substeps are raised for rings).
* Multiplier cards exist only for `cloth_drape`. Labels are template-based (no per-stage free text).
* `follow` camera tracks the centroid of balls/rings only; the closeup hook for rigid bodies replays the first seconds.
* Automatic YouTube/Instagram upload, AI/LLM generation and agents are deliberately not built (Phase 14).

## Requirements

- Python 3.11 (needed for the `bpy` module) **or** a normal Blender 4.5 LTS install
- FFmpeg on your PATH
- Blender is not bundled. Pick one:
  - **bpy module:** `pip install -r requirements.txt` (Python 3.11 only; ~300 MB)
  - **Blender binary:** download Blender 4.5 LTS and pass `--blender /path/to/blender` or set `BLENDER_BIN`

## Quick start

```bash
# 1. Check the plan without running anything
python -m shorts_engine.render --config configs/example_cloth.json --dry-run --blender blender

# 2. Tiny end-to-end test (about 30 s on 2 CPU cores): 180x320, two resolutions
python -m shorts_engine.render --config configs/ci_smoke.json --use-bpy
#    -> output/ci_smoke/ci_smoke.mp4  and  output/ci_smoke/benchmark.json

# 3. The real example (720x1280, 4 resolutions) - see "Render time" first
python -m shorts_engine.render --config configs/example_cloth.json --use-bpy
#    or with a Blender install:
python -m shorts_engine.render --config configs/example_cloth.json --blender /path/to/blender
```

Run the Blender script directly if you want a single stage:

```bash
blender --background --python shorts_engine/generate_scene.py -- \
  --config configs/example_cloth.json --stage 0 --mode build      # build + bake
blender --background --python shorts_engine/generate_scene.py -- \
  --config configs/example_cloth.json --stage 0 --mode render --frame-start 1 --frame-end 30
```

## Output layout

```
output/<name>/
  stage_00_64/        stage_00_64.blend + blendcache_*/ (baked physics) + frames/frame_0001.png ... + stage_00_64.mp4
  stage_01_1024/ ...
  hook.mp4  concat.txt
  <name>.mp4          final video
  benchmark.json      summary (totals, settings actually used, GPU) + per-job wall time, bake/render seconds, memory
```

Rendering skips frames that already exist, so an interrupted run can simply be re-run.
The hook is the last `video.hook_seconds` of the final clip (capped at that clip's length).

## Config

See `configs/example_cloth.json`. Unknown keys are rejected so typos fail loudly. The main ones:

| Key | Meaning |
| --- | --- |
| `resolutions` | cloth face counts; each must be a perfect square (64, 1024, 4096, 16384 ...) |
| `object.type` | `sphere`, `cube`, `cylinder`, `cone`, `torus` |
| `duration`, `fps` | seconds per stage clip, frames per second |
| `physics.*` | gravity, mass, tension, compression, shear, bending, air_damping, quality, self_collision |
| `material.cloth_style` | `wireframe` (shows the mesh density) or `solid` |
| `camera.*`, `material.*colour`, `label.*` | framing, colours, label template (`{faces}`, `{faces_short}`) |
| `render.samples`, `render.device` | Cycles samples; `AUTO` tries OptiX, then CUDA, then CPU |

`simulation` currently accepts only `cloth`. New simulation types are added as a builder function in
`shorts_engine/simulation.py` (`SIMULATORS`).

## Splitting the work (for later Kaggle / multiple machines)

Physics is baked once; rendering is independent per frame. So work can be split without any
machine recomputing the cloth:

```bash
python -m shorts_engine.render --config C --use-bpy --bake-only                       # machine A: bake
python -m shorts_engine.render --config C --use-bpy --render-only --stages 3 \
       --frame-start 1 --frame-end 60 --no-assemble                                    # worker 1
python -m shorts_engine.render --config C --use-bpy --render-only --stages 3 \
       --frame-start 61 --frame-end 120 --no-assemble                                  # worker 2
python -m shorts_engine.render --config C --use-bpy --render-only                      # renders any missing frames (existing ones are skipped), then encodes
```

Copy the whole `output/<name>/stage_*/` folder (the `.blend` **and** its `blendcache_*` folder) to
each worker. `--chunks N` turns one frame range into N separate render jobs.

## Render time (measured, 2 CPU cores, no GPU)

| Step | Result |
| --- | --- |
| Bake 64 / 1024 / 4096 / 16384 faces (120 frames) | 0.7 s / 5.9 s / 22.6 s / 154.5 s |
| Baked cache size, 16384 faces | about 73 MB |
| Render one 16384-face frame, 720x1280, 32 samples | about 31 s |
| Full example (4 stages x 120 frames = 480 frames) | roughly 4 hours on this CPU (estimate: 480 x ~30 s) |

GPU rendering has **not** been measured. `render.device: AUTO` is implemented but untested on real
hardware. Lower `samples`, `fps`, `duration` or the output size to cut render time.

## Kaggle GPU benchmark (kit written; NOT yet run on Kaggle)

Goal: find out how many seconds one 16384-face frame takes on a Kaggle GPU, because that decides
whether one Kaggle session is enough or the work must be split across workers.

In a new Kaggle notebook: turn **Internet on** and pick a **GPU accelerator** (Settings panel), then:

```python
!git clone https://github.com/damarlanandu2005-jpg/3d-simulation-shorts-engine
%cd 3d-simulation-shorts-engine
!bash kaggle/setup_kaggle.sh          # installs ffmpeg + bpy 4.5; last line prints ENGINE_PYTHON=...
!python kaggle/gpu_benchmark.py       # add --python <ENGINE_PYTHON> if setup created a venv
```

It prints the GPU, the Cycles devices, bake time, GPU seconds/frame (after a warm-up frame), CPU
seconds/frame for comparison, and writes `output/gpu_bench/benchmark_result.json`. Send that file back.
Use `--faces 1024` for a quick sanity run first. If the output says Cycles fell back to CPU, the
device list shows why (empty `CUDA`/`OPTIX` lists mean no usable GPU backend was found).

Run locally the script was only tested on a CPU-only machine (it correctly reports "no GPU").
`setup_kaggle.sh` and everything GPU-related are untested. Never commit credentials; if you later
automate Kaggle from GitHub Actions, keep the token in a GitHub Secret (e.g. `KAGGLE_API_TOKEN`).

### Settings for the first Kaggle production test

`configs/example_cloth.json` uses **16 samples with denoising OFF** (Cycles, device AUTO). This choice is
based on the Kaggle quality sweep (16384 faces, 720x1280, OptiX), as reported by the project owner and
checked by eye on the montage:

| Variant | s/frame | SSIM vs reference |
| --- | --- | --- |
| 32 samples + denoise | 10.59 | 0.986 |
| 16 samples + denoise | 10.47 | 0.980 |
| 32 samples raw | 2.00 | 0.934 |
| **16 samples raw (chosen)** | **1.89** | **0.871** |
| 8 samples raw | 1.82 | 0.755 |

16 raw is a speed-first choice with visibly more noise than the denoised variants (the denoised runs
took about 8 s/frame longer here). Revisit it if the final video looks too grainy. Physics, camera,
materials, object, labels, stage list (64 / 1024 / 4096 / 16384), 4 s stages and 30 fps are unchanged.

## V1.1 video template (branch `v1.1`)

V1.1 changes the *video*, not the physics. Everything below is optional in the config and off by default, so
`configs/example_cloth.json` still produces exactly the V1 video.

| Feature | Config | What it does |
| --- | --- | --- |
| Shorter stages | `duration` | 3 s per stage instead of 4 |
| Nicer labels | `label.template` | `"{faces:,} FACES"` gives `16,384 FACES` |
| Multiplier cards | `video.cards` | 0.5 s `x16 / MORE FACES` cards between stages (ratio computed from `resolutions`) |
| Real hook | `video.hook.mode = "closeup"` | camera push-in over the finished 16K cloth with a question on screen, instead of repeating the last clip |
| Hook text | `video.hook.text` | placeholders `{total_ratio}` (256), `{first}`, `{last}`; `\n` = line break |
| Per-stage camera | `camera.per_stage` | list aligned with `resolutions`, e.g. `[{}, {"distance": 10.4}, ...]` |
| Denoiser choice | `render.denoiser` | `OPENIMAGEDENOISE` (default) or `OPTIX`; OptiX falls back to OIDN, with a warning, if no OptiX GPU is enabled |

Sequence: `hook -> stage 0 -> card -> stage 1 -> card -> stage 2 -> card -> stage 3` (about 15.5 s).

**What needs a re-bake and what doesn't.** Physics, geometry and materials are fixed when a stage is built.
Render settings (samples, denoise, resolution), the camera and the label text are re-applied at render time, so
editing them never needs a re-bake. The closeup hook reuses the last stage's baked cache (no extra simulation);
cards need no bake at all.

Useful commands:

```bash
python -m shorts_engine.render --config configs/v1_1_a_baseline.json --use-bpy                  # full video
python -m shorts_engine.render --config configs/v1_1_a_baseline.json --use-bpy --only-extras   # re-render just hook + cards, then assemble
python -m shorts_engine.render --config configs/v1_1_a_baseline.json --use-bpy --skip-extras   # plain V1 structure (no cards, tail hook)
```

Before encoding, every clip's frames are checked; a missing frame stops the run with the frame numbers
(FFmpeg would otherwise silently cut the clip short).

### The three comparison configs

| Config | Output | Samples / denoise | Purpose |
| --- | --- | --- | --- |
| `v1_1_a_baseline.json` | 720x1280 | 16, no denoise | new template, same render settings as V1 |
| `v1_1_b_optix.json` | 720x1280 | 16, OptiX denoise | cost/quality of the GPU denoiser |
| `v1_1_c_1080p.json` | 1080x1920 | 16, no denoise | cost of full-HD output |

They differ only in those fields, so time, quality and file size are directly comparable. Each writes to
its own folder (`output/v1_1_a`, `v1_1_b`, `v1_1_c`).

**Known trade-off:** the 64-face sheet is 4.4 units wide, which already fills the frame at the default camera
distance, so the closer stage cameras clip the sheet's edges for the first ~0.3 s of a stage, until it falls and
narrows. The V1.1 zoom is therefore gentle (11 -> 10.4 -> 9.8 -> 9.2).

`benchmark.json` is now `{"summary": {...}, "jobs": [...]}`. The summary holds total wall-clock time, time per job
kind, frames rendered, bake seconds, devices, samples, denoiser and resolution actually used (read back from
Blender), and the GPU name from `nvidia-smi` when available. GPU utilisation is not measured.

### Sample-count / denoising sweep

After the benchmark, find the cheapest Cycles settings that still look good:

```python
!python kaggle/quality_sweep.py     # samples 32/16/8, each with and without denoising, vs a 128-sample reference
```

It bakes once, renders the same frames for every variant, prints seconds per frame plus PSNR/SSIM
against the reference, and saves `output/quality_sweep/compare/montage.png` (reference, then each
variant left to right). Treat the scores as a rough guide and look at the images. Locally this was
run on a tiny CPU scene only, not on a GPU.

## GitHub Actions

`.github/workflows/render.yml` is a manually triggered pipeline check (tests + tiny CPU render +
artifact upload). It has **not been run yet**. GitHub's free runners have no GPU, so it is not meant for
production renders.

## Tests

```bash
pip install pytest
python -m pytest -q            # 70 tests: config, planning, ffmpeg commands (no Blender needed)
pip install "bpy==4.5.16"      # Python 3.11; enables the 9 real Blender tests (79 total)
python -m pytest -q
```

## Layout

```
shorts_engine/
  config.py          config schema + validation (no bpy)
  generate_scene.py  Blender entry point: build / render modes
  simulation.py      ground, collider, cloth physics, bake
  camera.py          camera + on-screen label
  materials.py       materials, world, lights
  render.py          plans and runs bake -> render -> ffmpeg, writes benchmark.json
  assemble.py        FFmpeg command builders (no bpy)
configs/             example_cloth.json, ci_smoke.json
kaggle/              setup_kaggle.sh, gpu_benchmark.py, quality_sweep.py
tests/
```

## Licenses

See `LICENSES.md`. No third-party code is copied. Add your own `LICENSE` file before sharing the repo.

## Experiment configuration (schema v2)

Configs can be written in a general, experiment-oriented format (the old flat format keeps working). Both resolve to
the same internal `Config`; the V1.1 reference in the new format is `configs/experiments/cloth_drape_reference.json`
and is tested to be identical to `configs/v1_1_a_baseline.json` (same name on purpose, so do not render both into one output dir).

```json
{
  "schema_version": 2, "name": "...", "seed": 0,
  "experiment": {"type": "cloth_drape", "object": "sphere", "params": {"cloth_size": 4.4, "drop_height": 1.3}},
  "simulation": {"fps": 30, "duration": 3.0, "physics": {"gravity": 9.81}},
  "stages": [{"params": {"faces": 64}}, {"params": {"faces": 1024}, "camera": {"distance": 10.4}}],
  "camera": {...}, "render": {...}, "output": {...}, "label": {...}, "hook": {...}, "video": {...}, "audio": {...}
}
```

* `experiment.type` selects the experiment; only `cloth_drape` exists (roadmap names such as `multiple_balls` are rejected
  with a clear "not implemented yet" error until their Blender simulation is built and tested).
* `stages` is generic: each stage has experiment-specific `params` (for `cloth_drape`: `faces`, the mesh resolution) and an
  optional `camera` override. `hook` is top-level (`hook.seconds` replaces `video.hook_seconds`).
* Strict validation with path-qualified errors: unknown keys, experiment type/object, stage definitions, physics ranges
  (gravity, mass, stiffness...), fps/duration, render/output settings.
* Tools: `python -m shorts_engine.experiment list | describe CONFIG | migrate CONFIG` (`migrate` prints any config in the new format).
* Code: `shorts_engine/experiment.py` (schema, registry, translator). `Config.experiment_type` is derived, so the
  serialised config, and therefore the golden snapshots, are unchanged.

## Reference pipeline (frozen)

`configs/v1_1_a_baseline.json` (cloth draping over a sphere, 720x1280, 16 samples, no denoise, closeup hook,
stage labels, no multiplier cards, music + physics SFX, 14 s) is the **production reference**. Every later
experiment must leave it working. It is protected by:

* `tests/golden/reference_config.json` and `reference_plan.json`: exact snapshots of the resolved config and of the job
  plan (job kinds, concat order, durations). Intentional change: `python tools/update_golden.py`, review the diff.
* `tests/test_reference_pipeline.py`: explicit production facts (9:16, labels, no cards, audio on, OptiX never mandatory),
  Kaggle workflow input checks (fixed config mapping, no secrets printed), result-folder allow-list, and a **real
  Blender + FFmpeg end-to-end run** on a tiny scene (needs `bpy`; checks aspect ratio, fps, video + audio streams and
  durations, every frame present, no card output, concat order, `benchmark.json`, `audio_timeline.json`, an impact cue).

Kaggle result folder contract: only `<name>.mp4`, `benchmark.json`, `run_info.json`, `render.log` (the verify step warns
about anything else). Last verified on Kaggle: run 43753321122, 14.000 s, 720x1280 H.264 + AAC.

## V1.1 update: no multiplier cards, background music

* **Multiplier cards** (`x16 MORE` etc.) are now off in the V1.1 configs via `video.cards.enabled = false`.
  The feature still exists; set it to `true` to get them back. The final sequence is
  `hook -> 64 -> 1,024 -> 4,096 -> 16,384 FACES`. Turning cards off needs no re-bake.
* **Background music** is a reusable layer mixed in by FFmpeg after the clips are joined (the video stream is
  copied, not re-encoded). Config (top level):

  ```json
  "audio": {"enabled": true, "music": "assets/audio/music/default_music.wav", "volume_db": -18, "fade_in": 0.5, "fade_out": 1.0}
  ```

  The track loops if shorter than the video and is trimmed if longer, with fades; the audio never outlasts the
  picture. A missing music file fails at planning time with a clear error. The video before mixing is kept as
  `<name>_silent.mp4`. Relative music paths resolve from the project root. The default track is original
  (see `LICENSES.md`, regenerate with `python tools/make_default_music.py`).

## Simulation sound effects (SFX)

Audio layout: `assets/audio/music/` (background tracks) and `assets/audio/sfx/<sound>.wav` (effects).
Config (extends the `audio` block; `enabled` is the master switch, `music_enabled` / `sfx_enabled` are independent):

```json
"audio": {"enabled": true, "music": "assets/audio/music/default_music.wav", "volume_db": -18,
          "sfx_enabled": true, "sfx_volume_db": -8, "sfx_min_strength": 0.15, "sfx_min_gap": 0.15, "sfx_max_events": 24}
```

How it works:

1. **Events** are a simulation-independent list: `{"type": "impact", "frame": 18.65, "strength": 0.74}` with types
   `impact collision bounce contact landing roll whoosh splash` (each maps to a sound in `events.SOUND_FOR_TYPE`;
   an event may name its own `sound`). A new simulation (ball, ring, paper...) only has to emit events.
2. **Detection (cloth)**: after a stage is baked, `generate_scene.py --mode events` steps through the baked cache,
   measures how close the cloth gets to the collider and to the ground, and turns approaches into events
   (`events.detect_contacts`): the first contact is an `impact` (cloth on object) or `landing` (cloth on ground), later
   re-contacts after real separation are `bounce`. Strength = peak closing speed just before contact / free-fall speed
   over the drop height. Written to `<stage dir>/events.json`. Physics and rendering are untouched.
3. **Timeline**: `shorts_engine/timeline.py` places each stage's events on the FINAL video (hook, stage offsets, cards),
   using `t = (frame - first_frame_of_clip) / fps`. Events inside the replayed hook range also play in the hook.
4. **Anti-spam**: events below `sfx_min_strength` are dropped, same-sound events closer than `sfx_min_gap` seconds merge
   (the stronger stays), and at most `sfx_max_events` (strongest) survive.
5. **Mix** (`python -m shorts_engine.audio_mix`, run automatically as the last job): volume = `sfx_volume_db + 20*log10(strength)`,
   music stays continuous at `volume_db`, FFmpeg writes the final MP4 (video copied, not re-encoded) and
   `audio_timeline.json` (the final cue list, for checking sync).

SFX assets are original (generated by `tools/make_sfx.py`, CC0; see `LICENSES.md`).

## GitHub -> Kaggle GPU test automation (experimental, V1.1 tests)

Two manual workflows (Actions tab > Run workflow, branch `v1.1`). Needs repo secrets
`KAGGLE_USERNAME` and `KAGGLE_API_TOKEN` (never committed, never printed).

1. **kaggle-auth-check** - authenticates and makes harmless API calls. No GPU.
2. **kaggle-gpu-test** - input `test_config`: `baseline` (`configs/v1_1_a_baseline.json`),
   `optix` (`v1_1_b_optix.json`) or `1080p` (`v1_1_c_1080p.json`). It pushes a private Kaggle GPU
   script kernel that clones the exact commit, runs `kaggle/setup_kaggle.sh`, checks `import bpy`,
   runs `python -m shorts_engine.render --config <cfg> --use-bpy`, and returns the `.mp4`,
   `benchmark.json` and `run_info.json`. The workflow downloads them into the artifact
   `kaggle-<test_config>-<run_id>`. Any failure (auth, no GPU, setup, render, missing outputs) fails the run.

Helper: `kaggle/kaggle_automation.py` (tests in `tests/test_kaggle_automation.py`). The manual
notebook flow (`!bash kaggle/setup_kaggle.sh` + render command) is unchanged. The kernel clones the
public repo, so the commit must be pushed to GitHub before running.

## Verified Kaggle batch (T4 x2, 720p, seed 31)

GitHub Actions run 43764859046 (artifact `kaggle-baseline-43764859046`): 6 videos rendered, all passed QC (h264 + aac, 720x1280, 14-17 s), 4110 s wall time, 54.9 MB total.
cloth_drape, multiple_balls, ball_funnel (x2), ring_toss, cloth_objects. Per-video times were 585-812 s.
Invalid parameter combinations are rejected at config load; a failed video is retried once with a safe (cheaper, static-camera) configuration and both attempts are recorded in `manifest.json`.
