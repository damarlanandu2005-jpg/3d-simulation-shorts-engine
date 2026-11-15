#!/usr/bin/env bash
# Prepare a Kaggle (or any Linux GPU) notebook for the engine. NOT yet tested on Kaggle.
# Usage (in a notebook cell):  !bash kaggle/setup_kaggle.sh
# Prints the python interpreter to use as the last line:  ENGINE_PYTHON=/path/to/python
set -euo pipefail

BPY_VERSION="${BPY_VERSION:-4.5.16}"

apt-get install -y -qq ffmpeg libxi6 libxxf86vm1 libxfixes3 libxrender1 libsm6 libgl1 >/dev/null 2>&1 || \
  echo "apt-get failed or unavailable; make sure ffmpeg is installed (ffmpeg -version)"

if python3 -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,11) else 1)'; then
  PY=python3
  $PY -m pip install -q "bpy==${BPY_VERSION}" "numpy<2" pytest
else
  echo "Python is $(python3 --version); bpy 4.5 needs 3.11. Creating a 3.11 venv with uv (needs internet)."
  python3 -m pip install -q uv
  uv venv /kaggle/working/venv311 --python 3.11 2>/dev/null || uv venv ./venv311 --python 3.11
  VENV=$( [ -d /kaggle/working/venv311 ] && echo /kaggle/working/venv311 || echo ./venv311 )
  uv pip install --python "$VENV/bin/python" -q "bpy==${BPY_VERSION}" "numpy<2" pytest
  PY="$VENV/bin/python"
fi

$PY -c "import bpy; print('bpy', bpy.app.version_string)"
ffmpeg -version | head -1
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || echo "nvidia-smi: no GPU visible (enable a GPU accelerator in notebook settings)"
echo "ENGINE_PYTHON=$PY"
