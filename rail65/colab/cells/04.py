# CHECKPOINT 3 (part A) - locate / provision the NVIDIA EGL userspace libraries
import sys
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *

banner(3, "GPU / GL diagnosis - part A: NVIDIA EGL userspace libraries")
# Colab exposes nvidia-smi / CUDA but often NOT the graphics (EGL/GLX) libraries, so Blender cannot reach the T4 via GL.
# If they are missing we extract EXACTLY the libraries matching the running kernel driver from NVIDIA's installer.
# This is --extract-only into a private folder: nothing is installed system-wide and the driver is not touched.
PROVISION_NVIDIA_GL_USERSPACE = True

gpus = nvidia_query()
if not gpus:
    fail(3, "nvidia-smi sees no GPU")
drv = gpus[0]["driver"]
save_state(gpu=gpus[0])
print("kernel driver version:", drv)

roots = [d for d in ["/usr/lib", "/usr/lib64", "/lib", "/usr/local/nvidia", "/usr/local/cuda", "/opt",
                     "/usr/share/glvnd", "/usr/share/vulkan", "/etc/vulkan", "/etc/glvnd"] if os.path.isdir(d)]
found = {}
for pat in ("libEGL_nvidia.so*", "libGLX_nvidia.so*", "libnvidia-glcore.so*", "nvidia_icd.json", "10_nvidia.json"):
    r = sh("find %s -name '%s' 2>/dev/null | head -20" % (" ".join(roots), pat))
    found[pat] = [x for x in r.stdout.split() if x]
    print("%-24s %s" % (pat, found[pat]))
print("ldconfig NVIDIA/EGL entries:\n" + (sh("ldconfig -p | grep -i -E 'nvidia|libEGL|libGLX' | head -20").stdout or "  (none)\n"))

matches = lambda p: os.path.realpath(p).endswith("." + drv)
system_egl = [p for p in found["libEGL_nvidia.so*"] if matches(p)]
lib_dir, source = None, None

if system_egl:
    lib_dir, source = os.path.dirname(system_egl[0]), "system"
    print("Found system NVIDIA EGL matching driver %s: %s" % (drv, system_egl[0]))
else:
    stale = found["libEGL_nvidia.so*"]
    print("No libEGL_nvidia matching driver %s on this system%s." % (drv, (" (version-mismatched copies: %s)" % stale) if stale else ""))
    if not PROVISION_NVIDIA_GL_USERSPACE:
        fail(3, "NVIDIA EGL libraries unavailable and PROVISION_NVIDIA_GL_USERSPACE is False.")
    NVGL.mkdir(parents=True, exist_ok=True)   # curl -o fails with error 23 if this folder is missing
    run_file = NVGL / ("NVIDIA-Linux-x86_64-%s.run" % drv)
    extract = NVGL / "extract"
    libdir = NVGL / "lib"
    urls = ["https://us.download.nvidia.com/tesla/%s/NVIDIA-Linux-x86_64-%s.run" % (drv, drv),
            "https://us.download.nvidia.com/XFree86/Linux-x86_64/%s/NVIDIA-Linux-x86_64-%s.run" % (drv, drv)]
    ok = run_file.is_file() and run_file.stat().st_size > 100e6
    for u in ([] if ok else urls):
        print("downloading", u)
        r = sh("curl -fL --retry 2 -sS -o '%s' '%s'" % (run_file, u), timeout=1800)
        if r.returncode == 0 and run_file.is_file() and run_file.stat().st_size > 100e6:
            ok = True
            break
        print("  failed:", r.stderr.strip()[-200:])
    if not ok:
        fail(3, "could not download the NVIDIA %s userspace package; Blender cannot reach the T4 through GL without it." % drv)
    if extract.exists():
        shutil.rmtree(extract)
    r = sh("sh '%s' --extract-only --target '%s'" % (run_file, extract), timeout=900)
    if r.returncode != 0:
        fail(3, "extract-only failed: %s" % (r.stderr or r.stdout)[-300:])
    if not list(extract.glob("libEGL_nvidia.so.*")):
        fail(3, "the NVIDIA package for %s ships no libEGL_nvidia - GL cannot use this GPU here." % drv)
    if libdir.exists():
        shutil.rmtree(libdir)
    libdir.mkdir(parents=True)
    keep = ("libEGL_nvidia.so", "libGLX_nvidia.so", "libGLESv1_CM_nvidia.so", "libGLESv2_nvidia.so",
            "libnvidia-eglcore.so", "libnvidia-glcore.so", "libnvidia-glsi.so", "libnvidia-tls.so",
            "libnvidia-glvkspirv.so", "libnvidia-gpucomp.so", "libnvidia-rtcore.so")
    for f in extract.iterdir():
        if f.name.startswith(keep) and f.is_file():
            shutil.copy2(f, libdir / f.name)
    for base, so in (("libEGL_nvidia", "0"), ("libGLX_nvidia", "0"), ("libGLESv2_nvidia", "2"), ("libGLESv1_CM_nvidia", "1")):
        tgt = libdir / ("%s.so.%s" % (base, drv))
        lnk = libdir / ("%s.so.%s" % (base, so))
        if tgt.exists() and not lnk.exists():
            lnk.symlink_to(tgt.name)
    if (extract / "nvidia_icd.json").is_file():
        shutil.copy2(extract / "nvidia_icd.json", libdir / "nvidia_icd.json")
    shutil.rmtree(extract, ignore_errors=True)
    run_file.unlink()
    lib_dir, source = str(libdir), "extracted-from-nvidia-installer"
    print("Copied matching GL userspace libraries to", lib_dir)

egl_lib = Path(lib_dir) / "libEGL_nvidia.so.0"
if not egl_lib.exists():
    cands = sorted(Path(lib_dir).glob("libEGL_nvidia.so.*"))
    if not cands:
        fail(3, "libEGL_nvidia not found in %s" % lib_dir)
    egl_lib = cands[0]
unres = sh("LD_LIBRARY_PATH='%s' ldd '%s' | grep 'not found'" % (lib_dir, egl_lib)).stdout.strip()
if unres:
    print("WARNING: libEGL_nvidia has unresolved dependencies:\n" + unres)

# This JSON points at the REAL library found/extracted above (not a fabricated config).
egl_json = WORK / "egl_nvidia.json"
egl_json.write_text(json.dumps({"file_format_version": "1.0.0", "ICD": {"library_path": str(egl_lib)}}))
vk_icd = Path(lib_dir) / "nvidia_icd.json"
save_state(gl_lib_dir=str(lib_dir), egl_vendor_json=str(egl_json), gl_source=source,
           vk_icd_json=str(vk_icd) if vk_icd.is_file() else None, nvidia_egl_lib=str(egl_lib))
print("GL source: %s | EGL lib: %s | vendor json: %s" % (source, egl_lib, egl_json))
print("(setup step only - CHECKPOINT 3 is decided by the Blender probe in the next cell)")
