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
  benchmark.json      wall time, bake/render seconds, device, peak memory per job
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
python -m pytest -q            # 37 tests: config, planning, ffmpeg commands (no Blender needed)
pip install "bpy==4.5.16"      # Python 3.11; enables the 4 real Blender tests
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
