import bpy, math
from mathutils import Vector
import casino_scene as cs

def setup(sc, samples=8, pct=30):
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in ids else "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = samples
    if hasattr(sc.eevee, "use_raytracing"): sc.eevee.use_raytracing = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 720, 1280, pct
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.render.use_freestyle = False

def camera(sc, lens=32):
    cd = bpy.data.cameras.new("PCam"); cd.lens = lens
    cam = bpy.data.objects.new("PCam", cd); cs.link(cam); sc.camera = cam
    return cam

def aim(cam, loc, tgt):
    cam.location = loc
    d = Vector(tgt) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def shot(sc, cam, path, loc, tgt, lens=32):
    cam.data.lens = lens
    aim(cam, loc, tgt)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)

def sheet(paths, out, h=420):
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in paths]
    s = Image.new("RGB", (sum(int(i.width * h / i.height) for i in ims), h))
    x = 0
    for i in ims:
        w = int(i.width * h / i.height); s.paste(i.resize((w, h)), (x, 0)); x += w
    s.save(out)
