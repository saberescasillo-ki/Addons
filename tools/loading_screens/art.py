"""Pixel art for the loading screens (drawn in code, 256x144, scaled up x4).

ignis(): Ignis, a horned knight of fire, swings its blazing sword at two players
in a burning temple: one charges with a sword, the other holds up a shield.
"""
import math
import random

from PIL import Image, ImageDraw

W, H = 256, 144

# palette
SKY_TOP, SKY_LOW = (24, 8, 22), (92, 22, 18)
LAVA = [(255, 236, 140), (255, 188, 60), (240, 110, 24), (180, 52, 16)]
STONE = [(22, 20, 26), (34, 31, 38), (48, 44, 54), (64, 60, 70)]
BRICK = [(44, 16, 22), (66, 24, 30), (92, 36, 40)]
GOLD = [(120, 72, 16), (200, 140, 30), (255, 210, 80)]
FIRE = [(255, 250, 200), (255, 214, 90), (255, 150, 40), (220, 70, 20), (140, 30, 14)]


def _px(d, x, y, c):
    if 0 <= x < W and 0 <= y < H:
        d.point((x, y), fill=c)


def _rect(d, x0, y0, x1, y1, c):
    d.rectangle((x0, y0, x1, y1), fill=c)


def _outline_rect(d, x0, y0, x1, y1, fill, edge):
    _rect(d, x0, y0, x1, y1, edge)
    _rect(d, x0 + 1, y0 + 1, x1 - 1, y1 - 1, fill)


def background(img, rng):
    d = ImageDraw.Draw(img)
    for y in range(H):  # sky gradient, dithered in 2-pixel bands
        t = min(1, y / 100)
        for x in range(W):
            tt = t + (0.04 if (x + y) % 2 else 0)
            c = tuple(int(SKY_TOP[i] + (SKY_LOW[i] - SKY_TOP[i]) * min(1, tt)) for i in range(3))
            _px(d, x, y, c)
    # far temple: pillars and a broken arch in silhouette
    for x0 in (8, 40, 196, 228):
        h = rng.randint(58, 74)
        _rect(d, x0, 112 - h, x0 + 14, 112, STONE[0])
        _rect(d, x0 - 2, 112 - h, x0 + 16, 112 - h + 4, STONE[1])
        for y in range(112 - h + 8, 112, 9):
            _rect(d, x0 + 2, y, x0 + 12, y, STONE[1])
    d.arc((34, 20, 222, 150), 200, 340, fill=STONE[1], width=6)
    # glowing windows
    for x0 in (14, 46, 202, 234):
        _rect(d, x0, 60, x0 + 2, 66, LAVA[2])
    # floor: blackstone bricks, lava cracks
    for y in range(112, H):
        for x in range(W):
            row = (y - 112) // 6
            edge = (y - 112) % 6 == 0 or (x + row * 7) % 14 == 0
            c = STONE[1] if edge else STONE[2 if (x * 7 + y * 3) % 11 else 3]
            _px(d, x, y, c)
    for _ in range(14):
        x, y = rng.randrange(0, W), rng.randrange(116, H)
        for k in range(rng.randint(4, 10)):
            _px(d, x + k, y + (k % 3 == 0), LAVA[1 + (k % 2)])
    # light from the fight on the floor
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r, a in ((70, 40), (50, 50), (32, 60)):
        gd.ellipse((150 - r, 124 - r // 4, 150 + r, 124 + r // 4), fill=(255, 120, 30, a))
    img.alpha_composite(glow)


def fire_sigil(img, cx, cy):
    """The burning rune on the floor under Ignis."""
    d = ImageDraw.Draw(img)
    for rx, ry, c in ((46, 9, LAVA[3]), (44, 8, LAVA[1]), (34, 6, LAVA[2]), (22, 4, LAVA[1])):
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=c)
    for i in range(8):
        a = i * math.pi / 4
        x0, y0 = cx + math.cos(a) * 22, cy + math.sin(a) * 4
        x1, y1 = cx + math.cos(a) * 44, cy + math.sin(a) * 8
        d.line((x0, y0, x1, y1), fill=LAVA[2])


def flames(d, rng, x0, x1, base, height):
    """A curtain of flames rising from `base`, `height` tall."""
    for x in range(x0, x1):
        h = int(height * (0.55 + 0.45 * abs(math.sin(x * 0.7))) + rng.randint(-3, 3))
        for k in range(h):
            t = k / max(1, h)
            c = FIRE[min(4, int((1 - t) * 1 + t * 4.4))] if k else FIRE[0]
            if t > 0.75 and rng.random() < 0.4:
                continue
            _px(d, x, base - k, c)


def ignis(img, rng):
    d = ImageDraw.Draw(img)
    cx = 168  # Ignis' centre line
    # flaming lower body (it floats on fire)
    flames(d, rng, cx - 18, cx + 18, 118, 30)
    flames(d, rng, cx - 12, cx + 12, 112, 18)
    # skirt plates
    for i, x in enumerate(range(cx - 16, cx + 16, 8)):
        _outline_rect(d, x, 84, x + 7, 96 + (i % 2) * 3, BRICK[1], STONE[0])
        _rect(d, x + 1, 85, x + 6, 85, GOLD[1])
    # torso
    _outline_rect(d, cx - 17, 52, cx + 17, 86, BRICK[1], STONE[0])
    for y in range(56, 84, 5):
        _rect(d, cx - 15, y, cx + 15, y, BRICK[0])
    _outline_rect(d, cx - 6, 60, cx + 6, 72, FIRE[2], GOLD[1])   # the burning core
    _rect(d, cx - 3, 63, cx + 3, 69, FIRE[1])
    _rect(d, cx - 1, 65, cx + 1, 67, FIRE[0])
    _rect(d, cx - 17, 52, cx + 17, 53, GOLD[1])
    # pauldrons with spikes
    for side in (-1, 1):
        px0 = cx + side * 17
        _outline_rect(d, min(px0, px0 + side * 14), 46, max(px0, px0 + side * 14), 58, BRICK[2], STONE[0])
        _rect(d, min(px0, px0 + side * 14) + 1, 47, max(px0, px0 + side * 14) - 1, 47, GOLD[2])
        tip = px0 + side * 16
        d.polygon([(px0 + side * 4, 46), (tip, 34), (px0 + side * 10, 46)], fill=STONE[2], outline=STONE[0])
    # head: horned helmet, glowing eyes
    _outline_rect(d, cx - 9, 30, cx + 9, 50, BRICK[1], STONE[0])
    _rect(d, cx - 7, 38, cx + 7, 42, STONE[0])
    _rect(d, cx - 6, 39, cx - 3, 40, (255, 40, 30))
    _rect(d, cx + 3, 39, cx + 6, 40, (255, 40, 30))
    _rect(d, cx - 9, 30, cx + 9, 31, GOLD[1])
    for side in (-1, 1):  # curved horns
        pts = [(cx + side * 8, 32), (cx + side * 16, 24), (cx + side * 20, 12), (cx + side * 18, 4)]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d.line((x0, y0, x1, y1), fill=STONE[3], width=3)
        _px(d, pts[-1][0], pts[-1][1] - 1, GOLD[2])
    flames(d, rng, cx - 6, cx + 6, 30, 10)  # crown of fire
    # left arm (its right side of the picture) bent down to the shield
    d.line((cx + 24, 54, cx + 36, 70), fill=STONE[0], width=9)
    d.line((cx + 24, 54, cx + 36, 70), fill=BRICK[2], width=7)
    d.polygon([(cx + 34, 60), (cx + 52, 60), (cx + 52, 84), (cx + 43, 94), (cx + 34, 84)],
              fill=STONE[2], outline=GOLD[1])
    d.line((cx + 43, 62, cx + 43, 90), fill=GOLD[1])
    _rect(d, cx + 41, 70, cx + 45, 74, FIRE[2])
    # sword arm raised over the head towards the players
    d.line((cx - 30, 56, cx - 42, 30), fill=STONE[0], width=9)
    d.line((cx - 30, 56, cx - 42, 30), fill=BRICK[2], width=7)
    _outline_rect(d, cx - 47, 22, cx - 37, 32, STONE[3], STONE[0])  # gauntlet
    # the great sword: from the fist up and over, blazing, sweeping down
    hilt = (cx - 42, 26)
    tip = (cx - 108, 56)
    blade = math.degrees(math.atan2(tip[1] - hilt[1], tip[0] - hilt[0]))
    trail = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(trail)
    # a crescent where the blade has just been (it comes down from above)
    length = math.hypot(tip[0] - hilt[0], tip[1] - hilt[1])
    for k in range(0, 60):
        a = blade + k
        t = k / 60                             # 0 at the blade, 1 at the end of the trail
        r_out, r_in = length + 4 - t * 16, length * 0.62 - t * 2
        for r in range(int(r_in), int(r_out)):
            u = (r - r_in) / max(1, r_out - r_in)
            col = FIRE[0] if u > 0.75 else FIRE[1] if u > 0.4 else FIRE[2]
            x = hilt[0] + math.cos(math.radians(a)) * r
            y = hilt[1] + math.sin(math.radians(a)) * r
            td.point((round(x), round(y)), fill=col + (int(210 * (1 - t) ** 1.3),))
    img.alpha_composite(trail)
    d.line((hilt[0] + 6, hilt[1] + 6, hilt[0] - 6, hilt[1] - 6), fill=GOLD[1], width=3)  # guard
    for w, c in ((9, FIRE[3]), (7, FIRE[2]), (4, FIRE[1]), (2, FIRE[0])):
        d.line((hilt[0] - 4, hilt[1] - 2, tip[0], tip[1]), fill=c, width=w)
    d.line((hilt[0] - 4, hilt[1] - 2, tip[0] + 6, tip[1] + 1), fill=STONE[0], width=1)  # dark fuller
    # embers trailing off the blade
    for _ in range(40):
        t = rng.random()
        x = hilt[0] + (tip[0] - hilt[0]) * t + rng.randint(-4, 4)
        y = hilt[1] + (tip[1] - hilt[1]) * t + rng.randint(2, 14)
        _px(d, int(x), int(y), FIRE[rng.randint(0, 3)])


def player(img, x, y, armour, trim, weapon, rng, mirror=False):
    """A blocky player in a full suit of armour (no face shown), 34 px tall."""
    d = ImageDraw.Draw(img)
    dark = tuple(max(0, c - 40) for c in armour)
    light = tuple(min(255, c + 40) for c in armour)
    s = -1 if mirror else 1
    # legs, mid-stride
    _outline_rect(d, x - 5, y - 12, x - 1, y, dark, STONE[0])
    _outline_rect(d, x + 1, y - 12, x + 5, y - 1, dark, STONE[0])
    _rect(d, x - 6 + s * -2, y - 1, x - 1 + s * -2, y, STONE[1])
    # body
    _outline_rect(d, x - 6, y - 24, x + 6, y - 12, armour, STONE[0])
    _rect(d, x - 5, y - 23, x + 5, y - 23, light)
    _rect(d, x - 6, y - 14, x + 6, y - 13, trim)
    # helmet with visor slit
    _outline_rect(d, x - 5, y - 34, x + 5, y - 24, armour, STONE[0])
    _rect(d, x - 4, y - 33, x + 4, y - 33, light)
    _rect(d, x - 3 + s, y - 29, x + 3 + s, y - 28, STONE[0])
    _rect(d, x - 5, y - 26, x + 5, y - 26, trim)
    if weapon == "sword":
        # back arm, front arm raised with a glowing sword
        _outline_rect(d, x - 9, y - 23, x - 6, y - 13, dark, STONE[0])
        d.line((x + 6, y - 22, x + 13, y - 30), fill=armour, width=3)
        blade = [(x + 13, y - 30), (x + 30, y - 44)]
        d.line(blade, fill=(150, 240, 255), width=3)
        d.line(blade, fill=(235, 255, 255), width=1)
        d.line((x + 10, y - 32, x + 16, y - 27), fill=trim, width=2)
    else:
        # shield raised in front, sword low behind
        _outline_rect(d, x + 6, y - 30, x + 17, y - 10, (96, 64, 34), STONE[0])
        _rect(d, x + 7, y - 29, x + 16, y - 29, trim)
        _rect(d, x + 11, y - 27, x + 12, y - 13, trim)
        d.line((x - 7, y - 16, x - 18, y - 8), fill=(200, 200, 210), width=2)
        # the shield takes the heat: sparks
        for _ in range(14):
            _px(d, x + 18 + rng.randint(0, 6), y - 30 + rng.randint(0, 20), FIRE[rng.randint(0, 2)])


def fireballs(img, rng):
    d = ImageDraw.Draw(img)
    for x, y, r in ((136, 84, 4), (128, 100, 3)):
        for k in range(12):  # trail
            _px(d, x + k * 2 + rng.randint(0, 1), y - k // 2 + rng.randint(-1, 1), FIRE[min(4, 1 + k // 3)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=FIRE[2], outline=FIRE[3])
        _px(d, x - 1, y - 1, FIRE[0])


def embers(img, rng, n=70):
    d = ImageDraw.Draw(img)
    for _ in range(n):
        _px(d, rng.randrange(W), rng.randrange(H - 30), FIRE[rng.randint(0, 3)])


def vignette(img):
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = v.load()
    for y in range(H):
        for x in range(W):
            dx, dy = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
            a = max(0, min(1, (dx * dx + dy * dy - 0.55) * 0.9))
            px[x, y] = (8, 2, 6, int(a * 170))
    img.alpha_composite(v)


def ignis_screen(scale=4, seed=3):
    rng = random.Random(seed)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    background(img, rng)
    fire_sigil(img, 168, 122)
    embers(img, rng)
    ignis(img, rng)
    fireballs(img, rng)
    player(img, 78, 116, (70, 200, 220), (40, 120, 150), "sword", rng)          # diamond armour, leaping in
    player(img, 112, 125, (66, 58, 64), GOLD[1], "shield", rng)                # netherite armour, shield up
    vignette(img)
    return img.resize((W * scale, H * scale), Image.NEAREST)


if __name__ == "__main__":
    import sys
    ignis_screen().save(sys.argv[1] if len(sys.argv) > 1 else "ignis_loading.png")
