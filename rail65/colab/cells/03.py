# CHECKPOINT 1 - Blender 5.2.x
import sys, urllib.request
sys.path.insert(0, "/content/eevee_test/lib")
from ee_common import *

banner(1, "Blender")
V = BLENDER_VERSION
MM = ".".join(V.split(".")[:2])

# Runtime libraries Blender needs on a bare Colab image (no NVIDIA driver is installed here).
need = ["libegl1", "libgl1", "libxi6", "libxxf86vm1", "libxfixes3", "libxrender1",
        "libxkbcommon0", "libsm6", "libxext6", "libvulkan1"]
r = sh("apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq " + " ".join(need), timeout=900)
print("apt runtime deps exit code:", r.returncode)
if r.returncode != 0:
    print((r.stderr or r.stdout)[-1500:])

if BLENDER_BIN.is_file() and os.access(BLENDER_BIN, os.X_OK):
    print("Blender already installed at", BLENDER_BIN)
else:
    base = "https://download.blender.org/release/Blender%s" % MM
    tarball = BLENDER_DIST / "blender.tar.xz"
    BLENDER_DIST.mkdir(parents=True, exist_ok=True)
    url = "%s/blender-%s-linux-x64.tar.xz" % (base, V)
    print("downloading", url)
    r = sh("curl -fL --retry 3 -sS -o '%s' '%s'" % (tarball, url), timeout=1800)
    if r.returncode != 0:
        fail(1, "download failed (is internet on?): %s" % r.stderr.strip()[-300:])
    print("downloaded %.0f MB" % (tarball.stat().st_size / 1e6))
    verified = None
    try:
        fetch = lambda u: urllib.request.urlopen(u, timeout=60).read().decode()
        listing = fetch(base + "/")
        m = re.search(r"blender-%s[^\"<>\s]*\.sha256" % re.escape(V), listing)
        sums = fetch(base + "/" + m.group(0))
        expected = [l.split()[0] for l in sums.splitlines() if "linux-x64.tar.xz" in l][0]
        verified = (sha256_file(tarball) == expected)
    except Exception as e:
        print("WARNING: could not fetch checksum (%r) - tarball unverified" % (e,))
    if verified is False:
        fail(1, "SHA256 mismatch for the Blender download")
    print("sha256 verified:", verified)
    r = sh("tar -xf '%s' -C '%s'" % (tarball, BLENDER_DIST), timeout=900)
    if r.returncode != 0:
        fail(1, "tar extraction failed: %s" % r.stderr[-300:])
    tarball.unlink()

require_file(BLENDER_BIN)
if not os.access(BLENDER_BIN, os.X_OK):
    fail(1, "Blender binary is not executable")

missing = sh("ldd '%s' | grep 'not found'" % BLENDER_BIN).stdout.strip()
if missing:
    fail(1, "Blender has unresolved shared libraries:\n" + missing)
print("ldd: all Blender shared libraries resolved")

r = sh("timeout 120 '%s' --version" % BLENDER_BIN)
print(r.stdout.strip())
m = re.search(r"Blender (\d+)\.(\d+)\.(\d+)", r.stdout)
if not m:
    fail(1, "could not parse `blender --version`: %r" % r.stdout[:200])
found = "%s.%s.%s" % m.groups()
if (m.group(1), m.group(2)) != tuple(MM.split(".")):
    fail(1, "wrong Blender version %s (need %s.x)" % (found, MM))
if found != V:
    print("WARNING: expected %s but found %s (still %s.x)" % (V, found, MM))

write_script(BLENDER_INFO, BPY_COMMON + r'''
def s(x):
    return x.decode() if isinstance(x, bytes) else str(x)
engines = available_engines()
info = {"version_string": bpy.app.version_string, "version": list(bpy.app.version),
        "version_cycle": s(bpy.app.version_cycle), "build_hash": s(bpy.app.build_hash),
        "build_date": s(bpy.app.build_date), "build_time": s(bpy.app.build_time),
        "build_branch": s(bpy.app.build_branch), "python": sys.version.split()[0],
        "binary_path": bpy.app.binary_path, "engines": engines}
print("AVAILABLE_ENGINES", engines)
print("BLENDER_INFO_JSON", json.dumps(info, default=str))
''')
res = run_blender(BLENDER_INFO, [], log_path=LOGS / "blender_info.log", timeout=300,
                  show=r"AVAILABLE_ENGINES|BLENDER_INFO_JSON|Traceback|Error")
info = parse_tagged(res["lines"], "BLENDER_INFO_JSON")
if res["rc"] != 0 or not info:
    fail(1, "blender_info.py failed (rc=%s). See %s" % (res["rc"], res["log"]))
print("Blender version :", info["version_string"])
print("Blender build   : hash %s | %s %s | branch %s" % (info["build_hash"], info["build_date"], info["build_time"], info["build_branch"]))
print("Blender Python  :", info["python"])
if tuple(info["version"][:2]) != tuple(int(x) for x in MM.split(".")):
    fail(1, "bpy reports version %s, need %s.x" % (info["version"], MM))
save_state(blender=info)
passed(1)
