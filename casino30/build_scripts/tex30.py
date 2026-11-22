"""Extra procedural textures for the 30 s casino video (PIL). Run after tex.py: python tex30.py"""
import math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import tex as T

OUT = T.OUT
F, BOLD, BLACK, SYM = T.F, T.BOLD, T.BLACK, T.SYM

ROWS = ["BAR", "BLANK", "CHERRY", "BLANK", "BELL", "BLANK", "BAR", "BLANK", "7 JACKPOT"] + ["BLANK"] * 14 + ["CHERRY", "BLANK", "BAR", "BLANK", "BELL"]
N_ROWS = len(ROWS)          # 28
STRIP_W, STRIP_H, HEAD_H = 1024, 8192, 480
ROW_H = (STRIP_H - HEAD_H) // N_ROWS


def small_symbol(kind, S=120):
    big = T.symbol({"BAR": "bar", "CHERRY": "cherry", "BELL": "bell", "7 JACKPOT": "7"}[kind], 256)
    return big.resize((S, S), Image.LANCZOS)


def strip(name="strip.png"):
    """Tall reel-3 'par sheet': header + 28 rows (#, symbol box, label). Row 9 (7 JACKPOT) highlighted."""
    im = Image.new("RGB", (STRIP_W, STRIP_H), (252, 244, 222))
    d = ImageDraw.Draw(im)
    for y in range(STRIP_H):
        k = 1 - 0.06 * abs(y / STRIP_H - 0.5)
        d.line([(0, y), (STRIP_W, y)], fill=(int(252 * k), int(244 * k), int(222 * k)))
    d.text((70, 60), "LUCKY 7s", font=F(T.BOLD, 34), fill=(120, 100, 80))
    d.text((70, 104), "PAR SHEET  REV B", font=F(T.BOLD, 26), fill=(150, 130, 105))
    d.text((STRIP_W // 2, 280), "REEL 3: EVERY STOP", font=F(T.BLACK, 66), fill=(60, 40, 30), anchor="mm")
    d.line([(60, 380), (STRIP_W - 60, 380)], fill=(190, 170, 140), width=4)
    for x, t in ((110, "ROW"), (270, "STOP"), (520, "SYMBOL")):
        d.text((x, 430), t, font=F(T.BOLD, 26), fill=(150, 130, 105), anchor="mm")
    for i, kind in enumerate(ROWS):
        y0 = HEAD_H + i * ROW_H
        yc = y0 + ROW_H // 2
        hl = kind == "7 JACKPOT"
        if hl:
            d.rectangle((40, y0 + 14, STRIP_W - 40, y0 + ROW_H - 14), fill=(255, 190, 40), outline=(230, 140, 10), width=6)
        d.text((100, yc), f"#{i + 1}", font=F(T.BLACK, 64), fill=(60, 40, 30), anchor="mm")
        d.rounded_rectangle((220, yc - 78, 360, yc + 78), 14, fill=(255, 252, 240), outline=(70, 60, 55), width=6)
        if kind != "BLANK":
            sy = small_symbol(kind, 118)
            im.paste(sy, (230, yc - 59), sy)
        else:
            d.line([(236, yc), (344, yc)], fill=(225, 80, 70), width=4)
        d.text((430, yc), kind, font=F(T.BLACK if hl else T.BOLD, 64 if not hl else 70), fill=(60, 40, 30), anchor="lm")
        d.line([(40, y0 + ROW_H), (STRIP_W - 40, y0 + ROW_H)], fill=(215, 200, 170), width=2)
    im.save(os.path.join(OUT, name))


def stamp(name="stamp.png"):
    im = Image.new("RGBA", (440, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, 436, 146), 18, fill=(230, 40, 30, 255), outline=(255, 235, 210, 255), width=6)
    d.text((220, 52), "ONE CLICK", font=F(T.BLACK, 56), fill=(255, 255, 255, 255), anchor="mm")
    d.text((220, 108), "SHORT", font=F(T.BLACK, 56), fill=(255, 255, 255, 255), anchor="mm")
    im.save(os.path.join(OUT, name))


def wheel(name="wheel.png"):
    """Round 'one click short' wheel: 24 white wedges with tiny symbols, one big red wedge with arc text."""
    S = 1024
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S // 2
    d.ellipse((6, 6, S - 6, S - 6), fill=(150, 25, 20, 255))
    d.ellipse((24, 24, S - 24, S - 24), fill=(250, 238, 205, 255))
    n = 36
    for i in range(n):
        a0, a1 = i * 360 / n, (i + 1) * 360 / n
        col = (250, 238, 205, 255) if i % 2 == 0 else (236, 222, 186, 255)
        d.pieslice((60, 60, S - 60, S - 60), a0 - 90, a1 - 90, fill=col)
    # big red 'one click short' wedge: 100 deg
    d.pieslice((60, 60, S - 60, S - 60), -90 + 25, -90 + 125, fill=(230, 40, 30, 255))
    d.pieslice((60, 60, S - 60, S - 60), -90 + 25, -90 + 125, outline=(255, 235, 210, 255), width=6)
    # arc text along the red wedge
    T.arc_text(im, "ONE CLICK SHORT", F(T.BLACK, 92), c, c, 330, math.radians(90 - 75), (255, 255, 255, 255), (120, 10, 5, 255), 5)
    rnd = random.Random(3)
    for i in range(n):
        if 25 <= i * 360 / n <= 125:
            continue
        a = math.radians((i + 0.5) * 360 / n - 90)
        x, y = c + 410 * math.cos(a), c + 410 * math.sin(a)
        d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=rnd.choice([(215, 20, 40, 255), (250, 190, 30, 255), (40, 40, 40, 255)]))
    d.ellipse((c - 150, c - 150, c + 150, c + 150), fill=(120, 15, 10, 255), outline=(255, 214, 90, 255), width=10)
    d.ellipse((c - 70, c - 70, c + 70, c + 70), fill=(255, 235, 150, 255))
    im.save(os.path.join(OUT, name))


def bill(name="bill.png"):
    W, H = 1024, 440
    im = Image.new("RGB", (W, H), (176, 214, 150))
    d = ImageDraw.Draw(im)
    d.rectangle((14, 14, W - 15, H - 15), outline=(60, 110, 60), width=8)
    d.rectangle((40, 40, W - 41, H - 41), outline=(100, 150, 90), width=3)
    d.ellipse((W // 2 - 130, H // 2 - 130, W // 2 + 130, H // 2 + 130), fill=(210, 232, 190), outline=(60, 110, 60), width=6)
    d.text((W // 2, H // 2), "$", font=F(T.BLACK, 150), fill=(70, 120, 70), anchor="mm")
    for x, y in ((100, 80), (W - 100, 80), (100, H - 80), (W - 100, H - 80)):
        d.text((x, y), "100", font=F(T.BLACK, 54), fill=(60, 110, 60), anchor="mm")
    d.text((W // 2, 62), "THE UNITED STATES OF AMERICA", font=F(T.BOLD, 26), fill=(70, 120, 70), anchor="mm")
    im.save(os.path.join(OUT, name))


def validator_label(name="validator.png"):
    W, H = 512, 256
    im = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(im)
    d.text((W // 2, 60), "BILL VALIDATOR", font=F(T.BOLD, 40), fill=(240, 200, 90), anchor="mm")
    d.text((W // 2, 150), "$20  $50  $100", font=F(T.BLACK, 66), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, 215), "FACE UP", font=F(T.BOLD, 30), fill=(190, 190, 190), anchor="mm")
    im.save(os.path.join(OUT, name))


def led_sign(name="progressive.png"):
    W, H = 2048, 256
    im = Image.new("RGB", (W, H), (30, 6, 6))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = 0.7 + 0.5 * (1 - y / H)
        d.line([(0, y), (W, y)], fill=(int(70 * k), int(12 * k), int(10 * k)))
    d.text((W // 2, 60), "LUCKY 7s PROGRESSIVE", font=F(T.BLACK, 110), fill=(255, 214, 90), anchor="mm")
    d.rectangle((6, 6, W - 7, H - 7), outline=(255, 200, 70), width=10)
    im.save(os.path.join(OUT, name))


def ceiling(name="ceiling.png"):
    S = 512
    im = Image.new("RGB", (S, S), (92, 46, 22))
    d = ImageDraw.Draw(im)
    rnd = random.Random(5)
    for y in range(0, S, 3):
        k = 0.9 + 0.2 * rnd.random()
        d.line([(0, y), (S, y)], fill=(int(96 * k), int(48 * k), int(24 * k)))
    im.save(os.path.join(OUT, name))


if __name__ == "__main__":
    strip(); stamp(); wheel(); bill(); validator_label(); led_sign(); ceiling()
    print("tex30 ok", sorted(os.listdir(OUT)))
