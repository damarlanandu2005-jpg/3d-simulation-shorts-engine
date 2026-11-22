# casino30 - Blender 5.2.4 Eevee 30 s test, driven from GitHub
Branch `casino30-kit`: `kit/` (prebuilt casino30.blend + render_30s.py), `build_scripts/` (regenerate the .blend), `colab/` (runner), `run_config.json`.
Branch `casino30-results`: one folder per Colab run under `runs/` (status, timing, contact sheet, log tails).
Flow: edit/push the kit + run_config.json -> in Colab run `colab/casino30_launcher.ipynb` (one cell) -> results land on `casino30-results`.
GitHub cannot start a Colab session by itself; the one manual step is pressing run in Colab.
