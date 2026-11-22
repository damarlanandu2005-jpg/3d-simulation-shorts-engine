"""tex_rail.py - writes every procedural texture of the railroad kit into tex/ (PIL + numpy only)."""
import os, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tex")
os.makedirs(OUT, exist_ok=True)
FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
rng = np.random.default_rng(7)


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def save(im, name):
    im.convert("RGB").save(os.path.join(OUT, name))


def noise(w, h, scale, seed=0):
    r = np.random.default_rng(seed)
    g = r.random((h // scale + 2, w // scale + 2)).astype(np.float32)
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255.0


def lerp(c0, c1, t):
    return np.array(c0, np.float32) * (1 - t[..., None]) + np.array(c1, np.float32) * t[..., None]


def rock():
    """canyon strata: horizontal bands of orange / red / brown with noise, tileable horizontally"""
    w, h = 1024, 1024
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    n = noise(w, h, 64, 1) * 0.5 + noise(w, h, 16, 2) * 0.3 + noise(w, h, 4, 3) * 0.2
    band = 0.5 + 0.5 * np.sin(y * 38 + n * 4.0) * 0.8 + 0.2 * np.sin(y * 111 + n * 6)
    pal = [(0.62, 0.17, 0.10), (0.86, 0.38, 0.13), (0.96, 0.58, 0.20), (0.72, 0.24, 0.12)]
    t = np.clip(band, 0, 1) * 3
    i = np.clip(t.astype(int), 0, 2)
    f = (t - i)[..., None]
    pa = np.array(pal, np.float32)
    col = pa[i] * (1 - f) + pa[i + 1] * f
    col *= (0.85 + 0.3 * n)[..., None]
    save(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), "rock.png")


def canyon_void():
    """deep blue wall with fine horizontal strata (the bottomless canyon)"""
    w, h = 512, 1024
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    n = noise(w, h, 32, 4) * 0.5 + noise(w, h, 4, 5) * 0.5
    s = 0.5 + 0.5 * np.sin(y * 260 + n * 8)
    top, bot = np.array([0.20, 0.35, 0.80]), np.array([0.03, 0.04, 0.30])
    base = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
    col = base * (0.80 + 0.35 * s[..., None])
    col[..., 0] += 0.07 * s * (0.3 + y)          # purple-ish strata lines
    save(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), "void.png")


def wood():
    w, h = 1024, 1024
    img = np.zeros((h, w, 3), np.float32)
    planks = 8
    for i in range(planks):
        y0, y1 = i * h // planks, (i + 1) * h // planks
        base = np.array([0.55, 0.31, 0.16]) * (0.8 + 0.4 * rng.random())
        n = noise(w, y1 - y0, 40, 20 + i) * 0.5 + noise(w, y1 - y0, 6, 50 + i) * 0.5
        img[y0:y1] = base[None, None, :] * (0.75 + 0.5 * n[..., None])
        img[y0:y0 + 4] *= 0.35
        for _ in range(2):                                  # butt joints
            x = int(rng.integers(0, w))
            img[y0:y1, x:x + 3] *= 0.4
    save(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)), "wood.png")


def ballast():
    w = h = 512
    base = np.ones((h, w, 3), np.float32) * np.array([0.66, 0.44, 0.32])
    n = noise(w, h, 3, 8)
    base *= (0.55 + 0.8 * n)[..., None]
    im = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for _ in range(1500):
        x, y = rng.integers(0, w), rng.integers(0, h)
        r = int(rng.integers(3, 9))
        c = tuple(int(v * 255) for v in np.clip(np.array([0.78, 0.55, 0.40]) * (0.6 + 0.7 * rng.random()), 0, 1))
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=c, outline=(70, 40, 30))
    save(im, "ballast.png")


def sand():
    w = h = 512
    n = noise(w, h, 64, 9) * 0.6 + noise(w, h, 8, 10) * 0.4
    col = lerp((0.96, 0.62, 0.30), (1.0, 0.78, 0.45), n)
    save(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), "sand.png")


def brick():
    w = h = 512
    im = Image.new("RGB", (w, h), (120, 50, 40))
    d = ImageDraw.Draw(im)
    bh, bw = 32, 64
    for r in range(h // bh):
        for c in range(-1, w // bw + 1):
            x = c * bw + (bw // 2 if r % 2 else 0)
            k = 0.8 + 0.4 * rng.random()
            d.rectangle([x + 2, r * bh + 2, x + bw - 2, r * bh + bh - 2], fill=(int(165 * k), int(70 * k), int(52 * k)))
    save(im, "brick.png")


def stripe_cap():
    """navy / white vertical stripes (the engineer's cap)"""
    im = Image.new("RGB", (256, 64), (240, 240, 245))
    d = ImageDraw.Draw(im)
    for x in range(0, 256, 32):
        d.rectangle([x, 0, x + 15, 64], fill=(40, 60, 120))
    save(im, "stripe_cap.png")


def stripe_chair():
    im = Image.new("RGB", (256, 64), (30, 25, 35))
    d = ImageDraw.Draw(im)
    for x in range(0, 256, 32):
        d.rectangle([x, 0, x + 15, 64], fill=(235, 170, 40))
    save(im, "stripe_chair.png")


def umbrella():
    im = Image.new("RGB", (512, 64), (240, 130, 30))
    d = ImageDraw.Draw(im)
    for x in range(0, 512, 64):
        d.rectangle([x, 0, x + 31, 64], fill=(30, 40, 90))
    save(im, "umbrella.png")


def text_tex(name, size, bg, lines, fg=(255, 255, 255), border=None, fsz=None):
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    if border:
        d.rectangle([6, 6, size[0] - 7, size[1] - 7], outline=border, width=8)
    n = len(lines)
    for i, (txt, sz, col) in enumerate(lines):
        f = font(sz)
        w = d.textlength(txt, font=f)
        d.text(((size[0] - w) / 2, size[1] * (i + 0.5) / n - sz * 0.6), txt, font=f, fill=col or fg)
    save(im, name)


def signs():
    text_tex("banner.png", (1024, 384), (170, 20, 25), [("FIRST LINE IN", 120, (255, 245, 230)), ("GETS IT ALL!", 120, (255, 245, 230))], border=(255, 215, 120))
    text_tex("union.png", (1024, 160), (30, 30, 45), [("UNION", 120, (240, 220, 160))])
    text_tex("allaboard.png", (512, 256), (245, 232, 200), [("ALL ABOARD!", 66, (130, 20, 20))], border=(90, 50, 30))
    text_tex("news.png", (512, 700), (238, 228, 205), [("The Red Mesa Herald", 40, (40, 30, 20)), ("THE CLICKETY", 62, (20, 15, 10)),
                                                         ("CLACK LINE!", 62, (20, 15, 10)), ("~ ~ ~ ~ ~ ~", 40, (90, 80, 70)), ("~ ~ ~ ~ ~ ~", 40, (90, 80, 70)),
                                                         ("~ ~ ~ ~ ~ ~", 40, (90, 80, 70))], border=None)
    text_tex("calendar.png", (512, 640), (250, 246, 236), [("CALENDAR", 40, (30, 30, 40)), ("for the year", 28, (80, 80, 90)), ("1880", 80, (30, 30, 40)),
                                                             ("MAY", 140, (200, 30, 30)), ("1 2 3 4 5 6 7", 40, (60, 60, 70)), ("8 9 10 11 12 13 14", 34, (60, 60, 70))], border=(200, 30, 30))
    text_tex("calendar_jul.png", (512, 640), (250, 246, 236), [("CALENDAR", 40, (30, 30, 40)), ("for the year", 28, (80, 80, 90)), ("1880", 80, (30, 30, 40)),
                                                                 ("JULY", 140, (200, 30, 30)), ("1 2 3 4 5 6 7", 40, (60, 60, 70)), ("8 9 10 11 12 13 14", 34, (60, 60, 70))], border=(200, 30, 30))
    text_tex("vandergold.png", (1024, 160), (20, 35, 60), [("VANDERGOLD", 110, (235, 190, 80))], border=(235, 190, 80))
    text_tex("redcanyon.png", (1024, 128), (20, 70, 50), [("RED CANYON SHORT LINE", 70, (240, 220, 160))])
    text_tex("clock.png", (256, 256), (245, 240, 225), [("XII", 40, (30, 20, 10)), ("", 20, None), ("VI", 40, (30, 20, 10))], border=(60, 40, 20))
    text_tex("ticket.png", (512, 160), (30, 70, 55), [("TICKETS", 90, (240, 220, 160))], border=(200, 160, 80))


def teal_jacket():
    im = Image.new("RGB", (256, 256), (28, 140, 130))
    d = ImageDraw.Draw(im)
    for x in range(0, 256, 64):
        d.rectangle([x, 0, x + 6, 256], fill=(22, 110, 105))
    save(im, "jacket_teal.png")


def money():
    im = Image.new("RGB", (256, 256), (205, 160, 55))
    d = ImageDraw.Draw(im)
    f = font(150)
    d.text((86, 40), "$", font=f, fill=(70, 45, 10))
    save(im, "money.png")


def sky():
    """equirect sky: zenith blue -> pale horizon (middle) -> warm ground below"""
    w, h = 16, 512
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    up = np.clip(y * 2, 0, 1)                 # 0 zenith .. 1 horizon
    col = lerp((0.16, 0.42, 0.92), (0.78, 0.88, 1.0), up ** 1.6)
    dn = np.clip(y * 2 - 1, 0, 1)
    lower = lerp((0.95, 0.80, 0.62), (0.55, 0.32, 0.22), dn)
    col = np.where((y > 0.5)[..., None], lower, col)
    save(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), "sky.png")


def tile():
    w = h = 512
    im = Image.new("RGB", (w, h), (240, 240, 245))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 0:
                d.rectangle([c * 64, r * 64, c * 64 + 63, r * 64 + 63], fill=(70, 110, 190))
    save(im, "tile.png")


def run_all():
    for f in (rock, canyon_void, wood, ballast, sand, brick, stripe_cap, stripe_chair, umbrella, signs, teal_jacket, money, sky, tile):
        f()
    print("textures:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    run_all()
