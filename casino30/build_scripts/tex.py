"""Procedural textures for the casino test (PIL). Run once: python tex.py"""
import math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tex")
os.makedirs(OUT, exist_ok=True)
BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
SYM = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BLACK = "/usr/share/fonts/truetype/google-fonts/Poppins-ExtraBold.ttf"
if not os.path.exists(BLACK):
    BLACK = BOLD
ITAL = "/usr/share/fonts/truetype/google-fonts/Poppins-BoldItalic.ttf"
if not os.path.exists(ITAL):
    ITAL = BOLD


def F(path, size):
    return ImageFont.truetype(path, size)


def outlined_text(d, xy, text, font, fill, outline, w, anchor="mm"):
    x, y = xy
    for dx in range(-w, w + 1):
        for dy in range(-w, w + 1):
            if dx * dx + dy * dy <= w * w:
                d.text((x + dx, y + dy), text, font=font, fill=outline, anchor=anchor)
    d.text(xy, text, font=font, fill=fill, anchor=anchor)


# ---------------------------------------------------------------- slot symbols
def symbol(kind, S=256):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S // 2
    if kind == "7":
        outlined_text(d, (c, c + 6), "7", F(ITAL, 250), (225, 25, 25, 255), (255, 170, 30, 255), 7)
        d.text((c, c + 6), "7", font=F(ITAL, 250), fill=(225, 25, 25, 255), anchor="mm")
    elif kind == "bar":
        d.rounded_rectangle((20, c - 38, S - 20, c + 38), 16, fill=(30, 30, 30, 255), outline=(255, 200, 60, 255), width=6)
        d.text((c, c + 2), "BAR", font=F(BLACK, 50), fill=(255, 255, 255, 255), anchor="mm")
    elif kind == "cherry":
        d.line((c - 35, c + 20, c - 5, c - 70), fill=(60, 120, 30, 255), width=8)
        d.line((c + 35, c + 25, c - 5, c - 70), fill=(60, 120, 30, 255), width=8)
        for cx in (c - 42, c + 42):
            d.ellipse((cx - 40, c + 5, cx + 40, c + 85), fill=(215, 20, 40, 255), outline=(110, 0, 10, 255), width=5)
            d.ellipse((cx - 22, c + 18, cx - 6, c + 34), fill=(255, 190, 190, 255))
    elif kind == "bell":
        d.pieslice((c - 70, c - 85, c + 70, c + 55), 180, 360, fill=(250, 190, 30, 255), outline=(150, 90, 0, 255), width=5)
        d.polygon([(c - 70, c - 15), (c + 70, c - 15), (c + 95, c + 60), (c - 95, c + 60)], fill=(250, 190, 30, 255), outline=(150, 90, 0, 255))
        d.ellipse((c - 22, c + 50, c + 22, c + 90), fill=(180, 110, 10, 255))
        d.ellipse((c - 38, c - 68, c - 14, c - 40), fill=(255, 245, 170, 255))
    elif kind == "diamond":
        pts = [(c, c - 90), (c + 80, c - 25), (c, c + 90), (c - 80, c - 25)]
        d.polygon(pts, fill=(60, 200, 240, 255), outline=(10, 90, 140, 255))
        d.polygon([(c, c - 90), (c + 80, c - 25), (c - 80, c - 25)], fill=(140, 235, 255, 255))
        d.line([(c - 80, c - 25), (c, c + 90), (c + 80, c - 25)], fill=(10, 90, 140, 255), width=5)
    return im


def reel_strip(order, name):
    S = 256
    W = S * len(order)
    im = Image.new("RGB", (W, S), (250, 240, 215))
    d = ImageDraw.Draw(im)
    # subtle cream gradient across the reel width (v direction = image y)
    for y in range(S):
        k = 1 - abs(y - S / 2) / (S / 2) * 0.12
        d.line([(0, y), (W, y)], fill=(int(252 * k), int(243 * k), int(222 * k)))
    for i, kind in enumerate(order):
        sym = symbol(kind, S).rotate(90, expand=True)   # symbol up -> +u (circumference direction)
        im.paste(sym, (i * S, 0), sym)
        d.line([(i * S, 0), (i * S, S)], fill=(215, 200, 165), width=2)
    im.save(os.path.join(OUT, name))


REEL_ORDER = ["7", "cherry", "bar", "bell", "7", "diamond", "cherry", "bar"]

# ---------------------------------------------------------------- marquee
def arc_text(im, text, font, cx, cy, radius, ang_center, fill, outline, ow):
    d = ImageDraw.Draw(im)
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths)
    ang_span = total / radius
    a = ang_center + ang_span / 2
    for ch, w in zip(text, widths):
        a_mid = a - (w / 2) / radius
        x = cx + radius * math.cos(a_mid)
        y = cy - radius * math.sin(a_mid)
        layer = Image.new("RGBA", (260, 260), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        outlined_text(ld, (130, 130), ch, font, fill, outline, ow)
        rot = layer.rotate(math.degrees(a_mid) - 90, resample=Image.BICUBIC)
        im.paste(rot, (int(x - 130), int(y - 130)), rot)
        a -= w / radius


def marquee(name, top="LUCKY", big="7s", base=(235, 70, 20)):
    S = 1024
    im = Image.new("RGB", (S, S), (120, 10, 10))
    d = ImageDraw.Draw(im)
    cx, cy = S // 2, S * 0.78
    # sunburst
    for i in range(36):
        a0, a1 = i * 10, i * 10 + 5
        col = (240, 105, 25) if i % 2 == 0 else (175, 25, 18)
        d.pieslice((cx - 1200, cy - 1200, cx + 1200, cy + 1200), a0, a1, fill=col)
    # radial glow
    glow = Image.new("L", (S, S), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - 420, cy - 520, cx + 420, cy + 120), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(Image.new("RGB", (S, S), (255, 170, 50)), im, glow.point(lambda p: int(p * 0.45)))
    d = ImageDraw.Draw(im)
    arc_text(im, top, F(BLACK, 175), cx, cy + 30, 345, math.pi / 2, (255, 214, 60, 255), (110, 8, 5, 255), 10)
    d = ImageDraw.Draw(im)
    # big 7s
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    outlined_text(ld, (cx - 90, cy - 20), "7", F(ITAL, 540), (225, 20, 20, 255), (255, 225, 90, 255), 16)
    outlined_text(ld, (cx + 175, cy + 70), "s", F(ITAL, 300), (255, 190, 40, 255), (150, 20, 10, 255), 12)
    im.paste(layer, (0, 0), layer)
    im.save(os.path.join(OUT, name))


def sign(name, text, bg, fg, size=1024, aspect=0.5, font=None):
    W, H = size, int(size * aspect)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = 1 - 0.25 * abs(y - H / 2) / (H / 2)
        d.line([(0, y), (W, y)], fill=tuple(int(c * k) for c in bg))
    outlined_text(d, (W // 2, H // 2), text, font or F(BLACK, int(H * 0.5)), fg, (90, 30, 0), 5)
    d.rectangle((6, 6, W - 7, H - 7), outline=(255, 200, 70), width=8)
    im.save(os.path.join(OUT, name))


def header_panel(name):
    W, H = 1024, 256
    im = Image.new("RGB", (W, H), (70, 15, 10))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = 0.7 + 0.5 * (1 - y / H)
        d.line([(0, y), (W, y)], fill=(int(100 * k), int(22 * k), int(14 * k)))
    d.text((W - 60, 78), "PLAY 3 CREDITS", font=F(BLACK, 66), fill=(255, 205, 90), anchor="rm")
    d.text((W - 60, 168), "★ 1 LINE · $1 GAME ★", font=F(SYM, 38), fill=(255, 235, 200), anchor="rm")
    # WIN LED
    d.rectangle((24, 40, 150, 200), fill=(20, 5, 5), outline=(190, 190, 190), width=6)
    d.text((115, 132), "0", font=F("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 120), fill=(255, 40, 30), anchor="mm")
    d.text((22, 20), "WIN", font=F(BOLD, 30), fill=(255, 225, 190), anchor="lm")
    d.line([(0, H - 8), (W, H - 8)], fill=(255, 190, 60), width=10)
    im.save(os.path.join(OUT, name))


def paytable(name):
    W, H = 1024, 1024
    im = Image.new("RGB", (W, H), (150, 20, 15))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = 0.85 + 0.3 * (1 - y / H)
        d.line([(0, y), (W, y)], fill=(int(165 * k), int(25 * k), int(18 * k)))
    d.text((W // 2, 50), "★ LUCKY 7s PAYS ★", font=F(SYM, 40), fill=(255, 215, 140), anchor="mm")
    rows = [("7 7 7", "JACKPOT", (255, 220, 70)), ("♦ ♦ ♦", "$100", (150, 235, 255)), ("♠ ♠ ♠", "$50", (255, 215, 120)), ("BAR BAR BAR", "$25", (255, 255, 255))]
    y = 190
    for a, b, col in rows:
        d.rounded_rectangle((90, y - 50, 560, y + 50), 12, fill=(250, 240, 215), outline=(255, 200, 70), width=5)
        d.text((325, y), a, font=F(SYM if a[0] in "♦♠" else BLACK, 62), fill=(210, 25, 25), anchor="mm")
        d.text((610, y), "=", font=F(BOLD, 60), fill=(255, 230, 200), anchor="mm")
        d.text((830, y), b, font=F(BLACK, 62), fill=col, anchor="mm")
        y += 190
    for i in range(6):
        d.text((60 + i * 160, 960), "$" + str(2 ** (i % 3 + 1)), font=F(BOLD, 38), fill=(255, 235, 210), anchor="mm")
    d.rectangle((6, 6, W - 7, H - 7), outline=(255, 200, 70), width=10)
    im.save(os.path.join(OUT, name))


def jacket(name):
    S = 1024
    im = Image.new("RGB", (S, S), (28, 150, 140))
    d = ImageDraw.Draw(im)
    rnd = random.Random(4)
    for i in range(30):
        x, y = rnd.randint(0, S), rnd.randint(0, S)
        s = rnd.randint(52, 78)
        a = rnd.uniform(0, 6.28)
        for k in range(3):
            aa = a + (k - 1) * 0.55
            ex, ey = x + math.cos(aa) * s, y + math.sin(aa) * s
            d.polygon([(x, y), (x + math.cos(aa + 0.4) * s * 0.55, y + math.sin(aa + 0.4) * s * 0.55), (ex, ey), (x + math.cos(aa - 0.4) * s * 0.55, y + math.sin(aa - 0.4) * s * 0.55)], fill=(250, 220, 40))
    im.save(os.path.join(OUT, name))


def carpet(name):
    S = 1024
    im = Image.new("RGB", (S, S), (50, 15, 20))
    d = ImageDraw.Draw(im)
    rnd = random.Random(9)
    for i in range(900):
        x, y = rnd.randint(0, S), rnd.randint(0, S)
        r = rnd.randint(4, 12)
        col = rnd.choice([(140, 50, 30), (200, 150, 50), (90, 20, 50), (60, 90, 120)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    im.save(os.path.join(OUT, name))


if __name__ == "__main__":
    reel_strip(REEL_ORDER, "reel_a.png")
    reel_strip(["cherry", "7", "bar", "bell", "diamond", "7", "bar", "cherry"], "reel_b.png")
    reel_strip(["bar", "cherry", "7", "diamond", "bell", "cherry", "7", "bar"], "reel_c.png")
    marquee("marq_lucky.png")
    marquee("marq_gold.png", "GOLD", "RUSH")
    header_panel("header.png")
    paytable("paytable.png")
    jacket("jacket.png")
    carpet("carpet.png")
    sign("max_bet.png", "MAX BET", (240, 140, 40), (255, 245, 220), 512, 0.5)
    print("textures ok", os.listdir(OUT))
