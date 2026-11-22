# CELL 2 - get the kit (rail65.blend + render_30s.py) into /content/hopeall/kaggle_kit
import sys, zipfile
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *
DATASET_SLUG = "narasimhadamarla/seewhat"   # your Kaggle dataset holding rail65_kit/
KAGGLE_KIT = Path("/kaggle/input/datasets/narasimhadamarla/seewhat/rail65_kit")   # path when the dataset is attached (Kaggle)

FORCE_REFRESH = True   # True = always re-copy the kit from the dataset/upload (so an updated rail65.blend replaces an old copy)
if FORCE_REFRESH:
    for _n in ("rail65.blend", "render_30s.py"): (KIT / _n).unlink(missing_ok=True)
def have(): return BLEND.is_file() and RENDER_PY.is_file()
def adopt(folder):
    folder = Path(folder); KIT.mkdir(parents=True, exist_ok=True)
    for n in ("rail65.blend", "render_30s.py"):
        hit = sorted(folder.rglob(n), key=lambda p: len(p.parts))   # shallowest match = kit root copy
        if hit: shutil.copy2(hit[0], KIT / n)
if not have() and KAGGLE_KIT.is_dir():
    adopt(KAGGLE_KIT)
if not have() and Path("/kaggle/input").is_dir():
    adopt("/kaggle/input")
if not have():
    for z in Path("/content").glob("*.zip"):                      # a zip uploaded to /content
        if "rail65" in z.name:
            d = WORK / "kit_unzip"; shutil.rmtree(d, ignore_errors=True)
            zipfile.ZipFile(z).extractall(d); adopt(d)
    if not have():
        adopt("/content")                                          # loose files uploaded to /content
if not have():
    try:
        try: import kagglehub
        except ImportError:
            sh("pip install -q kagglehub", timeout=300); import kagglehub
        adopt(kagglehub.dataset_download(DATASET_SLUG))
    except Exception as e:
        print("kagglehub restore failed:", repr(e))
if not have():
    raise CheckpointFailed("Missing rail65.blend / render_30s.py. Upload rail65_kit.zip to /content (Files panel) or add them "
                           "to the Kaggle dataset %s, then re-run this cell." % DATASET_SLUG)
print("OK:", BLEND, "%.1f MB" % (BLEND.stat().st_size/1e6), "| sha256", sha256_file(BLEND)[:16])
print("OK:", RENDER_PY)
