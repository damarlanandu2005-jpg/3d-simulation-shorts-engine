# rail65 kit - "Why Perfect Railroads Don't Work" (65.2 s, 1956 frames, 720x1280, Eevee)

## How it runs
1. Colab: Runtime > T4 GPU, paste `colab/launcher_cell.py` (or open `colab/rail65_launcher.ipynb`) and run the one cell.
2. It clones branch `rail65-kit`, installs Blender 5.2.4 + NVIDIA EGL, checks the scene, benchmarks 14 frames, renders all 1956 frames in chunks of 100 (resumable), encodes `rail65_eevee.mp4`.
3. Optional: Colab Secret `GITHUB_TOKEN` pushes a small result bundle to branch `rail65-results`.
`run_config.json` controls mode (benchmark|full), samples, frame range, Freestyle-off frames.

## What Blender draws here (everything is procedural geometry + painted textures, nothing downloaded)
| Reference element | Built as |
|---|---|
| Cartoon people (engineer, boss, tycoon, workers, conductor, clerk, crowd) | one shared rigged character (casino rig + face shape keys), 13 costumes: hats (top, bowler, flat cap, striped cap, peaked), bow tie, kerchief, cane, watch chain, glasses, beard |
| Facial acting, purple-angry boss | face shape keys (Happy/Excited/Irritated/...) keyed; skin colour keyed to purple |
| Canyon, mesas, strata cliffs, blue void | procedural strata material on boxes (no UVs) |
| Rails, ties, ballast, telegraph poles, trusses, arch bridge, scaffold tower, crane, deck | box/beam meshes |
| Steam locomotives, navy Vandergold car, green Red Canyon car | box/cylinder models, moving by keyed location |
| Station hall, glass dome, clock tower, gold steps, banners, newspapers | meshes + textures (`build_scripts/tex`) |
| Heat: rails glow orange, steam, mercury rising, calendar May->July, gap shrinking, coin in gap | keyed emission / scale / visibility |
| Rails buckling like a snake | 40 rail segments keyed sideways |
| Saw + sparks, smoke puffs | keyed small meshes |
| Burned-in captions | 3D text parented to the camera, one object per word, timed from OCR of the reference |

## Approximations (be aware)
- The reference has 22 segments with dissolves/warps; this kit uses 29 hard-cut camera shots (CONSTANT keys). No dissolves.
- Smoke/steam/sparks are stylised blobs, not simulations. No real water, fire or physics.
- Caption timing is OCR-based, not audio-synced; there is no audio track.
- Sets were checked by one low-resolution test frame per shot on software GL, not on a GPU.
- Render time on a T4 is NOT measured; run the benchmark cell (the cell prints a projection).

## Editing
`build_scripts/` rebuilds the .blend: `python build_rail.py out.blend` (bpy 5.x). `build_rail.py` has the shot list (`shots()`), captions (`WORDS`), cast (`build_all`). After changes, recompute `fs_off` (printed on save) into `run_config.json`, and `git add -f rail65/kit/rail65.blend`.

## Update: look pass (first 15 s)
Canyon walls are stacked rock blocks (`rail_rocks.py`), characters have stubby proportions and mesh outlines (inverted hull) instead of Freestyle (Freestyle was the main render cost). `run_config.json` is set to frames 1-451 (first 15 s) for the test run; set `frame_end` back to 1956 for the full video.
