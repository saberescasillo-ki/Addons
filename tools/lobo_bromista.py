"""Builds the "Lobo Bromista" add-on: a tameable wolf that is 3 times better than a normal one.

- 3x the health and damage of a wolf (wild 24 / tamed 120 health, 6 / 12 damage), a bit faster,
  regenerates, no fall damage, players can't hurt it and 20 % of its bites are critical.
- It never teleports to its owner: when you get far it trots and then sprints (Speed II / V)
  and leaps towards you until it catches up.
- Reacts to the weather: sunglasses in the sun, an umbrella hat in the rain, it trembles in
  thunderstorms and wears a scarf in the snow.
- 13 meme animations (longdog, plays dead, dab, moonwalk, backflip, sits like a human...).
- Talks in the chat (everyone sees it, with its own name), tells jokes, pulls pranks and
  reacts to what its owner does. The phrases are in tools/lobo_bromista/main.js.

    python3 tools/lobo_bromista.py            # regenerate the packs and the .mcaddon
    python3 tools/lobo_bromista.py --preview  # also refresh docs/lobo_bromista_preview.png
"""
import json
import math
import os
import random
import re
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "tools", "lobo_bromista")
ADDON_NAME = "Lobo Bromista"
BP = os.path.join(ROOT, "LoboBromista_BP")
RP = os.path.join(ROOT, "LoboBromista_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "2.1.0"  # custom commands (/lobo:chiste...)
MIN_ENGINE = [1, 26, 0]
ENTITY_FORMAT = "1.26.0"
UUIDS = dict(bp="5b0f7c1e-2a7d-4f53-9a4e-6c1d2b8e0f31", bp_data="a8e3d2c4-71b9-4c0a-8f62-3e5d9b1a7c40",
             bp_script="c4a1f9e2-3d6b-4e87-b5a0-9f2c7e8d1b52", rp="1e9d4b7a-6c3f-48a2-9d15-b7e0a3c6f283",
             rp_res="f72b5c8e-0d4a-4b91-a6e3-5c8f1d2b9e64")

NS = "lobo"
WOLF = f"{NS}:lobo_bromista"

# A normal wolf has 8 health wild / 40 tamed, 3-4 damage and speed 0.3.
STATS = dict(wild_health=24, tame_health=120, wild_damage=6, tame_damage=12, speed=0.35,
             scale=1.1, tame_chance=0.33, knockback_resistance=0.4)

# Everything the script uses; the values are copied into scripts/main.js.
CONFIG = dict(
    id=WOLF,
    trot_dist=7, sprint_dist=14, calm_dist=4.5,     # blocks from the owner
    trot_speed=1, sprint_speed=4,                   # Speed II / Speed V while catching up
    leap_dist=20, leap_force=0.9, leap_up=0.35, leap_cooldown=3,
    give_up_dist=150,                               # further than this it waits for you
    regen=1, regen_every=2, regen_after_hurt=6,      # +1 health every 2 s, 6 s after being hurt
    crit_chance=0.2, crit_damage=12,
    meme_every=[25, 60], joke_every=[180, 360], chatter_every=[90, 200], prank_every=[300, 600],
    afk_seconds=60, react_radius=40, message_gap=4,
)

# id, animation key, name, length in seconds, what it says when doing it (or None)
MEMES = [
    (1, "vibe", "Vibrando", 4.0, "*vibrando* ♪ nada me afecta ♪"),
    (2, "trompo", "Trompo", 2.0, "¡MODO TROMPO ACTIVADO!"),
    (3, "longdog", "Looooobo", 4.0, "Lo{o}bo."),
    (4, "muerto", "Se hace el muerto", 3.6, "*se muere dramáticamente* ...¿funcionó?"),
    (5, "dab", "Dab", 2.5, "*dab* Sigo siendo tendencia."),
    (6, "moonwalk", "Moonwalk", 2.6, "Hee-hee! *moonwalk*"),
    (7, "humano", "Sentado como humano", 5.0, "Sentado como una persona. Ahora pásame el control remoto."),
    (8, "backflip", "Mortal hacia atrás", 1.1, "¡Mortal hacia atrás! Dime que lo grabaste."),
    (9, "huh", "¿Eh?", 2.5, "¿Eh?"),
    (10, "rofl", "Rodando de risa", 3.0, "JAJAJAJAJA"),
    (11, "gafas", "Asúmelo (gafas)", 3.5, "( •_•)>⌐■-■   (⌐■_■) Asúmelo."),
    (12, "susto", "Susto", 1.6, "¡AAAAH!"),
    (13, "baile", "Baile", 5.0, "Bailo mejor que tú. Y lo sabes."),
]
CONFIG["memes"] = {str(i): dict(key=k, name=n, ticks=round(t * 20), line=line) for i, k, n, t, line in MEMES}

# clima property: what the environment sensor sees where the wolf is
CLIMA = dict(sol=0, lluvia=1, tormenta=2, nieve=3, nada=4)


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) + (255,)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- model
def cube(origin, size, uv, **kw):
    return dict(origin=origin, size=size, uv=uv, **kw)


# name, parent, pivot, cubes, static rotation
BONES = [
    ("root", None, [0, 8, 0], [], None),
    ("body", "root", [0, 10, 1.5], [cube([-3, 7, -4], [6, 6, 11], [0, 0])], None),
    ("mane", "body", [0, 10, -3], [cube([-4, 6.5, -6], [8, 7, 6], [34, 0])], None),
    ("head", "body", [0, 12, -6], [cube([-3, 9.5, -10], [6, 6, 4], [62, 0])], None),
    ("snout", "head", [0, 11.5, -10], [cube([-1.5, 10.5, -13], [3, 2, 3], [82, 0])], None),
    ("jaw", "head", [0, 10.5, -10], [cube([-1.5, 9.5, -13], [3, 1, 3], [82, 5])], None),
    ("lengua", "jaw", [0.5, 9.5, -12], [cube([0, 7.5, -12.5], [1, 2, 1], [94, 4])], None),
    ("earR", "head", [-2, 15.5, -7.5], [cube([-3, 15.5, -8], [2, 3, 1], [94, 0])], None),
    ("earL", "head", [2, 15.5, -7.5], [cube([1, 15.5, -8], [2, 3, 1], [94, 0])], None),
    ("gafas", "head", [0, 13.5, -10.1], [cube([-3.5, 12.5, -10.6], [7, 2, 1], [62, 10])], None),
    ("paraguas", "head", [0, 15.5, -8], [
        cube([-0.5, 15.5, -8.5], [1, 3, 1], [28, 17]),
        cube([-5, 18.5, -13], [10, 1, 10], [32, 17]),
        cube([-3, 19.5, -11], [6, 1, 6], [72, 17]),
        cube([-1, 20.5, -9], [2, 1, 2], [96, 17])], None),
    ("bandana", "body", [0, 9.5, -6], [
        cube([-3.5, 8.5, -7], [7, 2, 2], [78, 10]),
        cube([-1.5, 6.5, -7.1], [3, 2, 1], [100, 10])], None),
    ("bufanda", "body", [0, 10, -6], [
        cube([-3.5, 9, -7.5], [7, 3, 2], [0, 17]),
        cube([1, 5.5, -8], [2, 4, 1], [22, 17])], None),
    ("leg0", "body", [-1.5, 7, 5.5], [cube([-2.5, 0, 4.5], [2, 7, 2], [100, 0])], None),
    ("leg1", "body", [1.5, 7, 5.5], [cube([0.5, 0, 4.5], [2, 7, 2], [100, 0])], None),
    ("leg2", "body", [-1.5, 7, -3.5], [cube([-2.5, 0, -4.5], [2, 7, 2], [100, 0])], None),
    ("leg3", "body", [1.5, 7, -3.5], [cube([0.5, 0, -4.5], [2, 7, 2], [100, 0])], None),
    ("tail", "body", [0, 12, 7], [cube([-1, 11, 7], [2, 2, 7], [108, 0])], [35, 0, 0]),
]
TEX_W, TEX_H = 128, 64


def wolf_geo():
    bones = []
    for name, parent, pivot, cubes, rot in BONES:
        b = dict(name=name, pivot=pivot)
        if parent:
            b["parent"] = parent
        if rot:
            b["rotation"] = rot
        if cubes:
            b["cubes"] = cubes
        bones.append(b)
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": dict(identifier="geometry.lobo.lobo_bromista", texture_width=TEX_W, texture_height=TEX_H,
                            visible_bounds_width=3, visible_bounds_height=3, visible_bounds_offset=[0, 1, 0]),
        "bones": bones}]}


# ---------------------------------------------------------------- texture
def box_faces(u, v, w, h, d):
    """Box-UV rectangles (x, y, width, height). 'right' is the -x side, 'left' the +x side."""
    return dict(top=(u + d, v, w, d), bottom=(u + d + w, v, w, d),
                right=(u, v + d, d, h), front=(u + d, v + d, w, h),
                left=(u + d + w, v + d, d, h), back=(u + 2 * d + w, v + d, w, h))


def paint(img, rect, fn):
    x0, y0, w, h = rect
    for y in range(h):
        for x in range(w):
            c = fn(x, y, w, h)
            if c is not None:
                img.putpixel((x0 + x, y0 + y), c)


def paint_box(img, u, v, size, fns):
    w, h, d = (int(math.ceil(s)) for s in size)
    for name, rect in box_faces(u, v, w, h, d).items():
        fn = fns.get(name, fns.get("*"))
        if fn:
            paint(img, rect, fn)


PAL = {k: hx(v) for k, v in dict(
    fur="#9c958c", fur2="#8a837a", back="#625c55", back2="#55504a", cream="#ebe3d5", cream2="#d3c8b6",
    nose="#1e1a19", white="#f6f6f6", pupil="#1b1b1b", brow="#3a3430", ear_in="#d99a90", tongue="#ec6f80",
    tongue2="#c84a5e", claw="#3b3531", red="#d8393c", red2="#a82628", dot="#fff4f0", black="#121214",
    shine="#ffffff", glass2="#3a3a44", scarf1="#22a9a6", scarf2="#f2cf45", scarf3="#18817f",
    umb1="#e8403a", umb2="#fbf5ee", stick="#3a2c24", gold="#f0c23a").items()}


def texture():
    rng = random.Random(42)
    P = PAL
    im = Image.new("RGBA", (TEX_W, TEX_H), (0, 0, 0, 0))

    def fur(base, alt, p=0.22):
        return lambda x, y, w, h: alt if rng.random() < p else base

    def side_fur(x, y, w, h):
        # darker back on top, cream belly at the bottom
        if y == 0:
            return P["back"] if rng.random() < 0.6 else P["back2"]
        if y >= h - 2:
            return P["cream"] if y == h - 1 else (P["cream2"] if rng.random() < 0.5 else P["fur"])
        return P["fur2"] if rng.random() < 0.22 else P["fur"]

    # body 6x6x11
    paint_box(im, 0, 0, (6, 6, 11), {
        "top": lambda x, y, w, h: P["back2"] if x in (2, 3) and rng.random() < 0.7 else
        (P["back"] if rng.random() < 0.7 else P["fur2"]),
        "bottom": fur(P["cream"], P["cream2"]),
        "right": side_fur, "left": side_fur,
        "front": fur(P["fur"], P["fur2"]), "back": fur(P["fur"], P["fur2"])})

    # mane 8x7x6: fluffy, cream chest at the front
    def chest(x, y, w, h):
        if y >= 2 and 2 <= x <= w - 3 or y >= h - 2 and 1 <= x <= w - 2:
            return P["cream"] if rng.random() < 0.8 else P["cream2"]
        return P["fur"] if rng.random() < 0.75 else P["fur2"]
    paint_box(im, 34, 0, (8, 7, 6), {
        "*": lambda x, y, w, h: (P["back"] if y == 0 else P["fur"]) if rng.random() < 0.75 else P["fur2"],
        "top": fur(P["back"], P["back2"], 0.35), "front": chest,
        "bottom": fur(P["cream"], P["cream2"])})

    # head 6x6x4: smug face, one raised eyebrow
    face = [
        "bbffff",
        "ffffbb",
        "WPffWP",
        "cccccc",
        "cccccc",
        "cccccc",
    ]
    key = dict(f=P["fur"], b=P["brow"], W=P["white"], P=P["pupil"], c=P["cream"])

    def head_front(x, y, w, h):
        ch = face[y][x]
        c = key[ch]
        if ch == "f" and rng.random() < 0.2:
            c = P["fur2"]
        return c
    paint_box(im, 62, 0, (6, 6, 4), {
        "front": head_front, "top": fur(P["back"], P["back2"], 0.3),
        "bottom": fur(P["cream"], P["cream2"]),
        "*": lambda x, y, w, h: (P["cream"] if y >= 4 else (P["fur"] if rng.random() < 0.8 else P["fur2"]))})

    # snout 3x2x3: black nose on top of the front, cream muzzle
    paint_box(im, 82, 0, (3, 2, 3), {
        "front": lambda x, y, w, h: P["nose"] if (y == 0 and x == 1) else (P["cream2"] if y == 0 else P["cream"]),
        "top": lambda x, y, w, h: P["nose"] if y == h - 1 and x == 1 else (P["fur"] if y == 0 else P["cream"]),
        "*": lambda x, y, w, h: P["cream"] if rng.random() < 0.8 else P["cream2"]})
    # jaw 3x1x3: the top is the inside of the mouth
    paint_box(im, 82, 5, (3, 1, 3), {
        "top": lambda x, y, w, h: P["tongue"] if x == 1 else P["tongue2"],
        "*": lambda x, y, w, h: P["cream"] if rng.random() < 0.8 else P["cream2"]})
    # ears 2x3x1, tongue 1x2x1
    paint_box(im, 94, 0, (2, 3, 1), {
        "front": lambda x, y, w, h: P["back"] if y == 0 else P["ear_in"],
        "*": fur(P["back"], P["back2"], 0.3)})
    paint_box(im, 94, 4, (1, 2, 1), {"*": lambda x, y, w, h: P["tongue"] if y == 0 else P["tongue2"]})

    # legs 2x7x2: cream paws with dark claws
    def leg(x, y, w, h):
        if y >= h - 2:
            return P["cream"] if y == h - 2 else (P["claw"] if x % 2 == 0 else P["cream2"])
        return P["fur"] if rng.random() < 0.8 else P["fur2"]
    paint_box(im, 100, 0, (2, 7, 2), {"*": leg, "top": fur(P["fur"], P["fur2"]),
                                       "bottom": lambda *a: P["cream2"]})

    # tail 2x2x7: fluffy, cream tip at the back (+z)
    def tail_side(tip_at_start):
        def fn(x, y, w, h):
            tip = x < 2 if tip_at_start else x >= w - 2
            if tip:
                return P["cream"]
            return P["back"] if y == 0 else P["fur"]
        return fn
    paint_box(im, 108, 0, (2, 2, 7), {
        "right": tail_side(True), "left": tail_side(False),
        "top": lambda x, y, w, h: P["cream"] if y < 2 else P["back"],
        "bottom": lambda x, y, w, h: P["cream"],
        "back": lambda *a: P["cream"], "front": lambda *a: P["fur"]})

    # pixel sunglasses 7x2x1: two black lenses with a shine, bridge on top
    def glasses(x, y, w, h):
        if w == 7 and h == 2:
            if x == 3:
                return P["black"] if y == 0 else None
            if (x, y) in ((1, 0), (5, 0)):
                return P["shine"]
            if (x, y) in ((2, 0), (6, 0)):
                return P["glass2"]
            return P["black"]
        return P["black"]
    paint_box(im, 62, 10, (7, 2, 1), {"*": glasses})

    # bandana: red with white dots, a triangle hanging on the chest
    paint_box(im, 78, 10, (7, 2, 2), {"*": lambda x, y, w, h: P["dot"] if (x + 2 * y) % 4 == 0 else P["red"]})
    paint_box(im, 100, 10, (3, 2, 1), {
        "front": lambda x, y, w, h: (P["red"] if (x, y) != (1, 0) else P["dot"]) if y == 0 or x == 1 else None,
        "back": lambda x, y, w, h: P["red2"] if y == 0 or x == 1 else None,
        "*": lambda *a: P["red2"]})

    # scarf: teal and yellow stripes
    stripe = lambda x, y, w, h: P["scarf2"] if (x // 2) % 2 else P["scarf1"]
    paint_box(im, 0, 17, (7, 3, 2), {"*": stripe, "top": lambda *a: P["scarf3"], "bottom": lambda *a: P["scarf3"]})
    paint_box(im, 22, 17, (2, 4, 1), {
        "*": lambda x, y, w, h: P["scarf2"] if y == h - 1 else (P["scarf1"] if y % 2 == 0 else P["scarf2"])})

    # umbrella hat: red and white wedges, dark stick
    paint_box(im, 28, 17, (1, 3, 1), {"*": lambda *a: P["stick"]})

    def canopy(n):
        def fn(x, y, w, h):
            if w == n and h == n:  # top / bottom: wedges around the centre
                a = math.atan2(y + 0.5 - n / 2, x + 0.5 - n / 2)
                return P["umb1"] if int((a + math.pi) / (math.pi / 4)) % 2 else P["umb2"]
            return P["umb1"] if (x // 2) % 2 else P["umb2"]
        return fn
    paint_box(im, 32, 17, (10, 1, 10), {"*": canopy(10)})
    paint_box(im, 72, 17, (6, 1, 6), {"*": canopy(6)})
    paint_box(im, 96, 17, (2, 1, 2), {"*": lambda *a: P["gold"]})
    return im


# ---------------------------------------------------------------- animations
WALK = "q.modified_distance_moved * 38.17"
A = "animation.lobo.lobo_bromista"


def legs(front_r, front_l, back_r, back_l):
    return {"leg2": {"rotation": front_r}, "leg3": {"rotation": front_l},
            "leg0": {"rotation": back_r}, "leg1": {"rotation": back_l}}


def kf(*pairs):
    """kf(0, v0, 0.5, v1, ...) -> {"0.0": v0, "0.5": v1}"""
    return {f"{pairs[i]:.2f}".rstrip("0").rstrip(".") if pairs[i] else "0.0": pairs[i + 1]
            for i in range(0, len(pairs), 2)}


def base_animations():
    sw = f"math.cos({WALK}) * 45 * q.modified_move_speed"
    return {
        "look": {"loop": True, "bones": {"head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "walk": {"loop": True, "bones": legs([sw, 0, 0], [f"-{sw}", 0, 0], [f"-{sw}", 0, 0], [sw, 0, 0])},
        # wags faster when tamed
        "cola": {"loop": True, "bones": {"tail": {"rotation": [
            0, "math.sin(q.life_time * (250 + q.is_tamed * 350)) * (12 + q.is_tamed * 14)", 0]}}},
        "sentado": {"loop": True, "bones": {
            "root": {"position": [0, -2.5, 0]},
            "body": {"rotation": [-30, 0, 0]}, "head": {"rotation": [30, 0, 0]},
            "tail": {"rotation": [-40, 0, 0]},
            **legs([30, 0, 0], [30, 0, 0], [-45, 0, 0], [-45, 0, 0])}},
        # catching up: ears back, tongue out, long strides
        "carrera": {"loop": True, "bones": {
            "body": {"rotation": [4, 0, "math.sin(q.life_time * 700) * 3"]},
            "head": {"rotation": [-8, 0, 0]},
            "earR": {"rotation": [-60, 0, 0]}, "earL": {"rotation": [-60, 0, 0]},
            "tail": {"rotation": [-30, 0, 0]},
            **legs([f"math.cos({WALK}) * 25", 0, 0], [f"math.cos({WALK}) * 25", 0, 0],
                   [f"-math.cos({WALK}) * 25", 0, 0], [f"-math.cos({WALK}) * 25", 0, 0])}},
        "hablar": {"loop": True, "bones": {"jaw": {"rotation": ["12 + math.sin(q.life_time * 1300) * 12", 0, 0]}}},
        # rain / storm: droopy ears and tail under the umbrella hat
        "lluvia": {"loop": True, "bones": {
            "earR": {"rotation": [20, 0, 25]}, "earL": {"rotation": [20, 0, -25]},
            "tail": {"rotation": [-25, 0, 0]},
            "paraguas": {"rotation": [0, 0, "math.sin(q.life_time * 90) * 4"]}}},
        # thunder: trembling, ears flat, tail between the legs
        "temblor": {"loop": True, "bones": {
            "root": {"rotation": [0, 0, "math.sin(q.life_time * 2800) * 2.5"]},
            "head": {"rotation": [12, 0, 0]},
            "earR": {"rotation": [-55, 0, 0]}, "earL": {"rotation": [-55, 0, 0]},
            "tail": {"rotation": [-55, 0, 0]}}},
        # snow: shivering a little
        "frio": {"loop": True, "bones": {
            "root": {"rotation": [0, 0, "math.sin(q.life_time * 2200) * 1.2"]},
            "head": {"rotation": [8, 0, 0]}, "tail": {"rotation": [-15, 0, 0]}}},
        # sunny: chin up, too cool
        "sol": {"loop": True, "bones": {"head": {"rotation": [-8, 0, 0]}}},
    }


def meme_animations():
    vibe = "math.sin(q.anim_time * 720)"
    kick = "math.sin(q.anim_time * 2000) * 30"
    return {
        # 1 head bobbing to the beat
        "vibe": {"loop": True, "bones": {
            "head": {"rotation": [f"{vibe} * 18", 0, "math.sin(q.anim_time * 360) * 8"]},
            "body": {"rotation": [0, 0, "math.sin(q.anim_time * 360) * 4"]},
            "earR": {"rotation": [f"{vibe} * 20", 0, 0]}, "earL": {"rotation": [f"-{vibe} * 20", 0, 0]},
            "tail": {"rotation": [0, "math.sin(q.anim_time * 1440) * 35", 0]}}},
        # 2 spinning top
        "trompo": {"animation_length": 2.0, "bones": {
            "root": {"rotation": [0, "q.anim_time * 1080", 0],
                     "position": [0, "math.abs(math.sin(q.anim_time * 540)) * 2", 0]},
            **legs([-50, 0, 0], [-50, 0, 0], [50, 0, 0], [50, 0, 0])}},
        # 3 longdog: the body stretches (the head and legs are scaled back)
        "longdog": {"animation_length": 4.0, "bones": {
            "body": {"scale": kf(0, [1, 1, 1], 0.6, [1, 1, 2.6], 3.4, [1, 1, 2.6], 4.0, [1, 1, 1])},
            "head": {"scale": kf(0, [1, 1, 1], 0.6, [1, 1, 0.385], 3.4, [1, 1, 0.385], 4.0, [1, 1, 1])},
            **{f"leg{i}": {"scale": kf(0, [1, 1, 1], 0.6, [1, 1, 0.385], 3.4, [1, 1, 0.385], 4.0, [1, 1, 1])}
               for i in range(4)},
            "tail": {"rotation": [0, "math.sin(q.anim_time * 900) * 30", 0],
                     "scale": kf(0, [1, 1, 1], 0.6, [1, 1, 0.385], 3.4, [1, 1, 0.385], 4.0, [1, 1, 1])}}},
        # 4 plays dead dramatically: staggers, falls on its back, twitches, gets up
        "muerto": {"animation_length": 3.6, "bones": {
            "root": {"rotation": kf(0, [0, 0, 0], 0.2, [0, 0, 12], 0.4, [0, 0, -12], 0.55, [0, 0, 8],
                                    0.85, [0, 0, 180], 3.0, [0, 0, 180], 3.35, [0, 0, 360], 3.6, [0, 0, 360]),
                     "position": kf(0, [0, 0, 0], 0.85, [0, 2, 0], 3.0, [0, 2, 0], 3.2, [0, 6, 0], 3.6, [0, 0, 0])},
            "head": {"rotation": kf(0, [0, 0, 0], 0.4, [-30, 0, 0], 0.85, [20, 0, 30], 3.0, [20, 0, 30],
                                    3.6, [0, 0, 0])},
            "jaw": {"rotation": kf(0, [0, 0, 0], 0.85, [35, 0, 0], 3.0, [35, 0, 0], 3.2, [0, 0, 0])},
            **legs([f"{kick} * (q.anim_time > 0.9 && q.anim_time < 3.0)", 0, 0],
                   [f"-{kick} * (q.anim_time > 0.9 && q.anim_time < 3.0)", 0, 0],
                   [f"-{kick} * (q.anim_time > 0.9 && q.anim_time < 3.0)", 0, 0],
                   [f"{kick} * (q.anim_time > 0.9 && q.anim_time < 3.0)", 0, 0])}},
        # 5 dab
        "dab": {"animation_length": 2.5, "bones": {
            "root": {"position": [0, -1.5, 0]},
            "body": {"rotation": kf(0, [0, 0, 0], 0.25, [-40, 0, 0], 2.2, [-40, 0, 0], 2.5, [0, 0, 0])},
            "head": {"rotation": kf(0, [0, 0, 0], 0.25, [70, 35, -10], 2.2, [70, 35, -10], 2.5, [0, 0, 0])},
            "leg2": {"rotation": kf(0, [0, 0, 0], 0.25, [-130, 0, -35], 2.2, [-130, 0, -35], 2.5, [0, 0, 0])},
            "leg3": {"rotation": kf(0, [0, 0, 0], 0.25, [-50, 30, 55], 2.2, [-50, 30, 55], 2.5, [0, 0, 0])},
            "leg0": {"rotation": kf(0, [0, 0, 0], 0.25, [-20, 0, 0], 2.2, [-20, 0, 0], 2.5, [0, 0, 0])},
            "leg1": {"rotation": kf(0, [0, 0, 0], 0.25, [-20, 0, 0], 2.2, [-20, 0, 0], 2.5, [0, 0, 0])}}},
        # 6 moonwalk: slides backwards while walking forwards, then spins
        "moonwalk": {"animation_length": 2.6, "bones": {
            "root": {"position": kf(0, [0, 0, 0], 2.0, [0, 0, 10], 2.6, [0, 0, 0]),
                     "rotation": kf(0, [0, 0, 0], 2.0, [0, 0, 0], 2.6, [0, 360, 0])},
            "body": {"rotation": [-6, 0, 0]},
            "head": {"rotation": [-15, 0, 0]},
            **legs(["math.sin(q.anim_time * 600) * 35", 0, 0], ["-math.sin(q.anim_time * 600) * 35", 0, 0],
                   ["-math.sin(q.anim_time * 600) * 35", 0, 0], ["math.sin(q.anim_time * 600) * 35", 0, 0])}},
        # 7 sits like a human: upright, legs forward, paws crossed
        "humano": {"animation_length": 5.0, "bones": {
            "root": {"position": kf(0, [0, 0, 0], 0.4, [0, -1.5, 0], 4.6, [0, -1.5, 0], 5.0, [0, 0, 0])},
            "body": {"rotation": kf(0, [0, 0, 0], 0.4, [-75, 0, 0], 4.6, [-75, 0, 0], 5.0, [0, 0, 0])},
            "head": {"rotation": kf(0, [0, 0, 0], 0.4, [75, 0, 0], 4.6, [75, 0, 0], 5.0, [0, 0, 0])},
            "leg0": {"rotation": kf(0, [0, 0, 0], 0.4, [-15, 0, 10], 4.6, [-15, 0, 10], 5.0, [0, 0, 0])},
            "leg1": {"rotation": kf(0, [0, 0, 0], 0.4, [-15, 0, -10], 4.6, [-15, 0, -10], 5.0, [0, 0, 0])},
            "leg2": {"rotation": kf(0, [0, 0, 0], 0.4, [20, 0, -55], 4.6, [20, 0, -55], 5.0, [0, 0, 0])},
            "leg3": {"rotation": kf(0, [0, 0, 0], 0.4, [35, 0, 55], 4.6, [35, 0, 55], 5.0, [0, 0, 0])},
            "tail": {"rotation": [-35, "math.sin(q.anim_time * 200) * 15", 0]}}},
        # 8 backflip
        "backflip": {"animation_length": 1.1, "bones": {
            "root": {"position": kf(0, [0, 0, 0], 0.15, [0, -1, 0], 0.35, [0, 10, 0], 0.55, [0, 14, 0],
                                    0.8, [0, 8, 0], 1.0, [0, 0, 0], 1.1, [0, 0, 0]),
                     "rotation": kf(0, [0, 0, 0], 0.2, [0, 0, 0], 0.95, [-360, 0, 0], 1.1, [-360, 0, 0])},
            **legs(kf(0, [0, 0, 0], 0.3, [-60, 0, 0], 0.9, [-60, 0, 0], 1.1, [0, 0, 0]),
                   kf(0, [0, 0, 0], 0.3, [-60, 0, 0], 0.9, [-60, 0, 0], 1.1, [0, 0, 0]),
                   kf(0, [0, 0, 0], 0.3, [60, 0, 0], 0.9, [60, 0, 0], 1.1, [0, 0, 0]),
                   kf(0, [0, 0, 0], 0.3, [60, 0, 0], 0.9, [60, 0, 0], 1.1, [0, 0, 0]))}},
        # 9 "huh?": head tilt, one ear up and one down
        "huh": {"animation_length": 2.5, "bones": {
            "head": {"rotation": kf(0, [0, 0, 0], 0.2, [-5, 10, 32], 2.2, [-5, 10, 32], 2.5, [0, 0, 0])},
            "earR": {"rotation": kf(0, [0, 0, 0], 0.2, [-10, 0, 0], 2.2, [-10, 0, 0], 2.5, [0, 0, 0])},
            "earL": {"rotation": kf(0, [0, 0, 0], 0.2, [40, 0, -30], 2.2, [40, 0, -30], 2.5, [0, 0, 0])}}},
        # 10 rolling on the floor laughing
        "rofl": {"animation_length": 3.0, "bones": {
            "root": {"rotation": kf(0, [0, 0, 0], 0.3, [0, 0, 180], 2.7, [0, 0, 180], 3.0, [0, 0, 360]),
                     "position": kf(0, [0, 0, 0], 0.3, [0, 2, 0], 2.7, [0, 2, 0], 3.0, [0, 0, 0])},
            "body": {"rotation": [0, 0, "math.sin(q.anim_time * 900) * 18 * (q.anim_time > 0.3)"]},
            "jaw": {"rotation": ["20 + math.sin(q.anim_time * 1800) * 18", 0, 0]},
            **legs([kick, 0, 0], [f"-{kick}", 0, 0], [f"-{kick}", 0, 0], [kick, 0, 0])}},
        # 11 "deal with it": the sunglasses fall onto its face
        "gafas": {"animation_length": 3.5, "bones": {
            "gafas": {"position": kf(0, [0, 18, 0], 1.2, [0, 0, 0], 3.5, [0, 0, 0])},
            "head": {"rotation": kf(0, [0, 0, 0], 1.2, [0, 0, 0], 1.4, [-15, -10, 0], 3.5, [-15, -10, 0])}}},
        # 12 cartoon fright: jumps up with stiff legs and trembles
        "susto": {"animation_length": 1.6, "bones": {
            "root": {"position": kf(0, [0, 0, 0], 0.15, [0, 9, 0], 0.45, [0, 0, 0], 1.6, [0, 0, 0]),
                     "rotation": [0, 0, "math.sin(q.anim_time * 3000) * 3 * (q.anim_time > 0.45)"]},
            "earR": {"rotation": [-10, 0, 20]}, "earL": {"rotation": [-10, 0, -20]},
            "tail": {"rotation": [40, 0, 0]},
            **legs([0, 0, 25], [0, 0, -25], [0, 0, 25], [0, 0, -25])}},
        # 13 dances standing on its hind legs
        "baile": {"loop": True, "bones": {
            "root": {"position": [0, 3, 0], "rotation": [0, 0, "math.sin(q.anim_time * 360) * 12"]},
            "body": {"rotation": [-75, 0, 0]},
            "head": {"rotation": [75, 0, "-math.sin(q.anim_time * 360) * 16"]},
            "leg0": {"rotation": [75, 0, 0]}, "leg1": {"rotation": [75, 0, 0]},
            "leg2": {"rotation": ["40 + math.sin(q.anim_time * 720) * 35", 0, -30]},
            "leg3": {"rotation": ["40 - math.sin(q.anim_time * 720) * 35", 0, 30]},
            "tail": {"rotation": [0, "math.sin(q.anim_time * 1440) * 35", 0]}}},
    }


def animations():
    out = {f"{A}.{k}": v for k, v in base_animations().items()}
    out.update({f"{A}.meme_{k}": v for k, v in meme_animations().items()})
    return {"format_version": "1.8.0", "animations": out}


def controllers():
    states = {"normal": {"transitions": [{f"m{i}": f"q.property('{NS}:meme') == {i}"} for i, *_ in MEMES]}}
    for i, key, *_ in MEMES:
        states[f"m{i}"] = {"animations": [f"meme_{key}"], "blend_transition": 0.15,
                           "transitions": [{"normal": f"q.property('{NS}:meme') != {i}"}]}
    return {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.lobo.lobo_bromista.memes": {"initial_state": "normal", "states": states}}}


# ---------------------------------------------------------------- resource pack
def prop(name):
    return f"q.property('{NS}:{name}')"


CONDITIONS = {
    "sentado": "q.is_sitting",
    "carrera": f"{prop('paso')} == 2",
    "hablar": f"{prop('habla')}",
    "lluvia": f"q.is_tamed && ({prop('clima')} == 1 || {prop('clima')} == 2)",
    "temblor": f"{prop('clima')} == 2",
    "frio": f"{prop('clima')} == 3",
    "sol": f"q.is_tamed && {prop('clima')} == 0",
}

VISIBILITY = {
    "gafas": f"q.is_tamed && ({prop('clima')} == 0 || {prop('meme')} == 11 || {prop('meme')} == 1)",
    "paraguas": f"q.is_tamed && ({prop('clima')} == 1 || {prop('clima')} == 2)",
    "bufanda": f"q.is_tamed && {prop('clima')} == 3",
    "bandana": f"q.is_tamed && {prop('clima')} != 3",
    "lengua": f"{prop('paso')} == 2 || {prop('meme')} == 4 || {prop('meme')} == 10 || {prop('meme')} == 1",
}


def client_entity():
    anims = {k: f"{A}.{k}" for k in base_animations()}
    anims.update({f"meme_{k}": f"{A}.meme_{k}" for k in meme_animations()})
    anims["memes"] = "controller.animation.lobo.lobo_bromista.memes"
    animate = ["look", "walk", "cola"] + [{k: v} for k, v in CONDITIONS.items()] + ["memes"]
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": WOLF,
        "materials": {"default": "entity_alphatest"},
        "textures": {"default": "textures/entity/lobo/lobo_bromista"},
        "geometry": {"default": "geometry.lobo.lobo_bromista"},
        "render_controllers": ["controller.render.lobo.lobo_bromista"],
        "animations": anims,
        "scripts": {"animate": animate},
        "spawn_egg": {"base_color": "#9c958c", "overlay_color": "#d8393c"},
    }}}


def render_controllers():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.lobo.lobo_bromista": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"],
            "part_visibility": [{"*": True}] + [{k: v} for k, v in VISIBILITY.items()]}}}


def sounds():
    return {"entity_sounds": {"entities": {WOLF: {"volume": 1.0, "pitch": [0.95, 1.15], "events": {
        "ambient": "mob.wolf.bark", "hurt": "mob.wolf.hurt", "death": "mob.wolf.death",
        "step": {"sound": "mob.wolf.step", "volume": 0.6}}}}}}


# ---------------------------------------------------------------- behavior pack
def fam(value, op=None):
    f = {"test": "is_family", "subject": "other", "value": value}
    if op:
        f["operator"] = op
    return f


HEAL_ITEMS = [("porkchop", 6), ("cooked_porkchop", 16), ("beef", 6), ("cooked_beef", 16), ("chicken", 4),
              ("cooked_chicken", 12), ("mutton", 4), ("cooked_mutton", 12), ("rabbit", 6), ("cooked_rabbit", 10),
              ("rabbit_stew", 20), ("rotten_flesh", 8), ("cod", 4), ("salmon", 4), ("cooked_cod", 10),
              ("cooked_salmon", 12)]


def clima_triggers():
    outside = {"test": "is_underground", "value": False}
    not_nether = {"test": "in_nether", "value": False}

    def t(value, *tests):
        return {"filters": {"all_of": [*tests, {"test": "int_property", "domain": f"{NS}:clima",
                                                "operator": "!=", "value": value}]},
                "event": f"{NS}:clima_{value}"}
    wap = lambda v: {"test": "weather_at_position", "value": v}
    return [
        t(CLIMA["tormenta"], wap("thunderstorm"), outside),
        t(CLIMA["lluvia"], wap("rain"), outside),
        t(CLIMA["nieve"], wap("snow"), outside),
        t(CLIMA["sol"], wap("clear"), outside, not_nether, {"test": "is_daytime", "value": True}),
        t(CLIMA["nada"], {"any_of": [{"test": "is_underground", "value": True}, {"test": "in_nether", "value": True},
                                     {"all_of": [wap("clear"), {"test": "is_daytime", "value": False}]}]}),
    ]


def wolf_entity():
    s = STATS
    prey = {"any_of": [fam("sheep"), fam("rabbit"), fam("fox"), fam("skeleton")]}
    monsters = {"all_of": [fam("monster"), fam("creeper", "!=")]}
    events = {f"{NS}:clima_{v}": {"set_property": {f"{NS}:clima": v}} for v in CLIMA.values()}
    return {"format_version": ENTITY_FORMAT, "minecraft:entity": {
        "description": {
            "identifier": WOLF, "is_spawnable": True, "is_summonable": True,
            "properties": {
                f"{NS}:meme": {"type": "int", "range": [0, 20], "default": 0, "client_sync": True},
                f"{NS}:clima": {"type": "int", "range": [0, 4], "default": CLIMA["nada"], "client_sync": True},
                f"{NS}:paso": {"type": "int", "range": [0, 2], "default": 0, "client_sync": True},
                f"{NS}:habla": {"type": "bool", "default": False, "client_sync": True},
                f"{NS}:sentado": {"type": "bool", "default": False},
            }},
        "component_groups": {
            f"{NS}:salvaje": {
                "minecraft:health": {"value": s["wild_health"], "max": s["wild_health"]},
                "minecraft:attack": {"damage": s["wild_damage"]},
                "minecraft:tameable": {"probability": s["tame_chance"], "tame_items": "bone",
                                       "tame_event": {"event": f"{NS}:domar", "target": "self"}},
                "minecraft:behavior.hurt_by_target": {"priority": 1},
                "minecraft:behavior.nearest_attackable_target": {
                    "priority": 4, "reselect_targets": True, "must_see": True,
                    "entity_types": [{"filters": prey, "max_dist": 16}]},
                "minecraft:despawn": {"despawn_from_distance": {}},
            },
            f"{NS}:domado": {
                "minecraft:is_tamed": {},
                # kept (it can't tame again) so the script can still read who the owner is
                "minecraft:tameable": {"probability": 0.0, "tame_items": "bone"},
                "minecraft:health": {"value": s["tame_health"], "max": s["tame_health"]},
                "minecraft:attack": {"damage": s["tame_damage"]},
                "minecraft:persistent": {},
                "minecraft:sittable": {"sit_event": {"event": f"{NS}:sentarse", "target": "self"},
                                       "stand_event": {"event": f"{NS}:pararse", "target": "self"}},
                # It never teleports: when you get far it runs after you (the script makes it faster).
                "minecraft:behavior.follow_owner": {"priority": 6, "speed_multiplier": 1.15, "start_distance": 5,
                                                    "stop_distance": 2.5, "can_teleport": False,
                                                    "max_distance": CONFIG["give_up_dist"],
                                                    "ignore_vibration": True},
                "minecraft:behavior.owner_hurt_by_target": {"priority": 1},
                "minecraft:behavior.owner_hurt_target": {"priority": 2},
                "minecraft:behavior.hurt_by_target": {"priority": 1, "entity_types": {
                    "filters": fam("player", "!=")}},
                "minecraft:behavior.nearest_attackable_target": {
                    "priority": 5, "must_see": True, "reselect_targets": True, "within_radius": 12,
                    "entity_types": [{"filters": monsters, "max_dist": 12}]},
            },
        },
        "components": {
            "minecraft:type_family": {"family": ["lobo_bromista", "wolf", "animal", "mob"]},
            "minecraft:collision_box": {"width": 0.6, "height": 0.85},
            "minecraft:scale": {"value": s["scale"]},
            "minecraft:movement": {"value": s["speed"]},
            "minecraft:movement.basic": {},
            "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True,
                                          "avoid_water": True},
            "minecraft:jump.static": {},
            "minecraft:can_climb": {},
            "minecraft:physics": {},
            "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
            "minecraft:nameable": {},
            "minecraft:leashable": {"soft_distance": 4, "hard_distance": 6, "max_distance": 10},
            "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
            "minecraft:knockback_resistance": {"value": s["knockback_resistance"]},
            "minecraft:healable": {"items": [{"item": i, "heal_amount": a * 2} for i, a in HEAL_ITEMS]},
            "minecraft:ambient_sound_interval": {"value": 12, "range": 10, "event_name": "ambient"},
            "minecraft:damage_sensor": {"triggers": [
                {"cause": "fall", "deals_damage": "no"},
                {"on_damage": {"filters": {"all_of": [
                    fam("player"), {"test": "has_component", "subject": "self", "value": "minecraft:is_tamed"}]}},
                 "deals_damage": "no"}]},
            "minecraft:environment_sensor": {"triggers": clima_triggers()},
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.stay_while_sitting": {"priority": 3},
            "minecraft:behavior.leap_at_target": {"priority": 4, "yd": 0.4, "must_be_on_ground": False},
            "minecraft:behavior.melee_attack": {"priority": 5, "speed_multiplier": 1.3, "track_target": True},
            "minecraft:behavior.random_stroll": {"priority": 8, "speed_multiplier": 1.0},
            "minecraft:behavior.beg": {"priority": 9, "look_distance": 8, "look_time": [2, 4],
                                       "items": ["bone"] + [i for i, _ in HEAL_ITEMS]},
            "minecraft:behavior.look_at_player": {"priority": 10, "look_distance": 8},
            "minecraft:behavior.random_look_around": {"priority": 11},
            "minecraft:conditional_bandwidth_optimization": {},
        },
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:salvaje"]}},
            f"{NS}:domar": {"remove": {"component_groups": [f"{NS}:salvaje"]},
                            "add": {"component_groups": [f"{NS}:domado"]}},
            f"{NS}:sentarse": {"set_property": {f"{NS}:sentado": True}},
            f"{NS}:pararse": {"set_property": {f"{NS}:sentado": False}},
            **events,
        },
    }}


def spawn_rules():
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": WOLF, "population_control": "animal"},
        "conditions": [{
            "minecraft:spawns_on_surface": {},
            "minecraft:spawns_on_block_filter": ["minecraft:grass_block", "minecraft:snow", "minecraft:snow_layer",
                                                 "minecraft:podzol", "minecraft:coarse_dirt"],
            "minecraft:brightness_filter": {"min": 7, "max": 15, "adjust_for_weather": False},
            "minecraft:weight": {"default": 3},
            "minecraft:herd": {"min_size": 1, "max_size": 1},
            "minecraft:biome_filter": {"any_of": [{"test": "has_biome_tag", "value": "taiga"},
                                                  {"test": "has_biome_tag", "value": "forest"}]}}]}}


LANG = {
    "es": {
        f"entity.{WOLF}.name": "Lobo Bromista",
        f"item.spawn_egg.entity.{WOLF}.name": "Generar Lobo Bromista",
        "pack.name": ADDON_NAME,
        "pack.description": "Un lobo domesticable 3 veces mejor: habla, cuenta chistes y hace memes.",
    },
    "en": {
        f"entity.{WOLF}.name": "Prankster Wolf",
        f"item.spawn_egg.entity.{WOLF}.name": "Spawn Prankster Wolf",
        "pack.name": "Prankster Wolf",
        "pack.description": "A tameable wolf 3 times better: it talks, tells jokes and does memes.",
    },
}


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


def script():
    with open(os.path.join(HERE, "main.js"), encoding="utf-8") as f:
        src = f.read()
    return src.replace("__CONFIG__", json.dumps(CONFIG, ensure_ascii=False))


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": LANG["es"]["pack.description"],
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SCRIPT_API}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Modelo, textura y animaciones del Lobo Bromista.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


# ---------------------------------------------------------------- preview renderer
# A tiny software renderer: evaluates the same animations (Molang -> Python) and draws every
# texel of the model as a shaded quad, so the preview shows the real poses.
def molang(expr, ctx):
    if isinstance(expr, (int, float)):
        return float(expr)
    s = expr
    s = re.sub(r"q\.property\('([^']+)'\)", lambda m: f"P[{m.group(1)!r}]", s)
    s = s.replace("math.sin(", "_sin(").replace("math.cos(", "_cos(").replace("math.abs(", "abs(")
    s = re.sub(r"\bq\.([a-z_]+)", r"Q['\1']", s)
    s = s.replace("&&", " and ").replace("||", " or ").replace("!=", "~~")
    s = s.replace("!", " not ").replace("~~", "!=")
    env = dict(_sin=lambda a: math.sin(math.radians(a)), _cos=lambda a: math.cos(math.radians(a)),
               P=ctx["P"], Q=ctx["Q"], abs=abs)
    return float(eval(s, {"__builtins__": {}}, env))


def channel(value, t, ctx):
    """Value of a rotation/position/scale channel at anim time t."""
    def vec(v):
        if isinstance(v, (int, float)):
            return [float(v)] * 3
        return [molang(c, ctx) for c in v]
    if isinstance(value, dict):
        keys = sorted((float(k), v) for k, v in value.items())
        if t <= keys[0][0]:
            return vec(keys[0][1])
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                a, b = vec(v0), vec(v1)
                f = (t - t0) / (t1 - t0) if t1 > t0 else 1
                return [a[i] + (b[i] - a[i]) * f for i in range(3)]
        return vec(keys[-1][1])
    return vec(value)


def pose(active, ctx):
    """active: list of (animation, anim_time). Returns bone -> (rot, pos, scale)."""
    out = {}
    for anim, t in active:
        ctx["Q"]["anim_time"] = t
        for bone, chans in anim["bones"].items():
            r, p, s = out.setdefault(bone, ([0, 0, 0], [0, 0, 0], [1, 1, 1]))
            if "rotation" in chans:
                v = channel(chans["rotation"], t, ctx)
                for i in range(3):
                    r[i] += v[i]
            if "position" in chans:
                v = channel(chans["position"], t, ctx)
                for i in range(3):
                    p[i] += v[i]
            if "scale" in chans:
                v = channel(chans["scale"], t, ctx)
                for i in range(3):
                    s[i] *= v[i]
    return out


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_t(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def mat_s(x, y, z):
    return [[x, 0, 0, 0], [0, y, 0, 0], [0, 0, z, 0], [0, 0, 0, 1]]


def mat_r(rx, ry, rz):
    # Bedrock: a positive X rotation tips the front (-Z) down, so X is negated here.
    ax, ay, az = math.radians(-rx), math.radians(ry), math.radians(rz)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    X = [[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]]
    Y = [[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]]
    Z = [[cz, -sz, 0, 0], [sz, cz, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return mat_mul(Z, mat_mul(Y, X))


def apply(m, p):
    return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3)]


def render(tex, poses, visible, size=220, yaw=-35, pitch=18, scale=6.0, center_y=9):
    world = {}
    for name, parent, pivot, cubes, rot in BONES:
        r, p, s = poses.get(name, ([0, 0, 0], [0, 0, 0], [1, 1, 1]))
        base = rot or [0, 0, 0]
        local = mat_mul(mat_t(p[0], p[1], p[2]), mat_t(*pivot))
        local = mat_mul(local, mat_r(base[0] + r[0], base[1] + r[1], base[2] + r[2]))
        local = mat_mul(local, mat_s(*s))
        local = mat_mul(local, mat_t(-pivot[0], -pivot[1], -pivot[2]))
        world[name] = mat_mul(world[parent], local) if parent else local
    view = mat_mul(mat_r(pitch, 0, 0), mat_r(0, yaw, 0))
    px = tex.load()
    quads = []
    hidden = set()
    for name, parent, *_ in BONES:
        if name in hidden or (parent in hidden) or not visible.get(name, True):
            hidden.add(name)
    for name, parent, pivot, cubes, rot in BONES:
        if name in hidden:
            continue
        m = mat_mul(view, world[name])
        for c in cubes:
            (x0, y0, z0), (w, h, d), (u, v) = c["origin"], c["size"], c["uv"]
            x1, y1, z1 = x0 + w, y0 + h, z0 + d
            W, H, D = (int(math.ceil(k)) for k in (w, h, d))
            r = box_faces(u, v, W, H, D)
            faces = [  # rect, start corner, u axis, v axis
                (r["front"], (x0, y1, z0), (w, 0, 0), (0, -h, 0)),
                (r["back"], (x1, y1, z1), (-w, 0, 0), (0, -h, 0)),
                (r["right"], (x0, y1, z1), (0, 0, -d), (0, -h, 0)),
                (r["left"], (x1, y1, z0), (0, 0, d), (0, -h, 0)),
                (r["top"], (x0, y1, z1), (w, 0, 0), (0, 0, -d)),
                (r["bottom"], (x0, y0, z0), (w, 0, 0), (0, 0, d)),
            ]
            for (fx, fy, fw, fh), o, ua, va in faces:
                if fw == 0 or fh == 0:
                    continue
                p0 = apply(m, o)
                pu = apply(m, [o[0] + ua[0], o[1] + ua[1], o[2] + ua[2]])
                pv = apply(m, [o[0] + va[0], o[1] + va[1], o[2] + va[2]])
                du = [pu[i] - p0[i] for i in range(3)]
                dv = [pv[i] - p0[i] for i in range(3)]
                n = [du[1] * dv[2] - du[2] * dv[1], du[2] * dv[0] - du[0] * dv[2], du[0] * dv[1] - du[1] * dv[0]]
                ln = math.sqrt(sum(k * k for k in n)) or 1
                light = 0.55 + 0.45 * abs((n[0] * -0.4 + n[1] * 0.8 + n[2] * -0.45) / ln)
                for j in range(fh):
                    for i in range(fw):
                        col = px[fx + i, fy + j]
                        if col[3] == 0:
                            continue
                        pts = []
                        for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                            pts.append([p0[k] + du[k] * a / fw + dv[k] * b / fh for k in range(3)])
                        depth = sum(q[2] for q in pts) / 4
                        shaded = tuple(min(255, int(ch * light)) for ch in col[:3]) + (255,)
                        quads.append((depth, [(size / 2 + q[0] * scale, size * 0.62 - (q[1] - center_y) * scale)
                                              for q in pts], shaded))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for depth, pts, col in sorted(quads, key=lambda q: -q[0]):
        d.polygon(pts, fill=col)
    return img


def preview_frame(tex, clima=CLIMA["nada"], meme=0, t=0.0, paso=0, sitting=False, habla=False, walk=0.0,
                  tamed=True, **kw):
    P = {f"{NS}:clima": clima, f"{NS}:meme": meme, f"{NS}:paso": paso, f"{NS}:habla": habla}
    Q = dict(is_tamed=tamed, is_sitting=sitting, life_time=t, anim_time=t, target_x_rotation=0,
             target_y_rotation=0, modified_distance_moved=walk, modified_move_speed=1.0 if walk else 0.0)
    ctx = dict(P=P, Q=Q)
    base = base_animations()
    active = [(base["look"], t), (base["walk"], t), (base["cola"], t)]
    for k, cond in CONDITIONS.items():
        if molang(cond, ctx):
            active.append((base[k], t))
    if meme:
        key = next(k for i, k, *_ in MEMES if i == meme)
        active.append((meme_animations()[key], t))
    visible = {k: bool(molang(v, ctx)) for k, v in VISIBILITY.items()}
    return render(tex, pose(active, ctx), visible, **kw)


PREVIEW = [
    ("Salvaje", dict(tamed=False)),
    ("Domado", dict()),
    ("Sol", dict(clima=0)),
    ("Lluvia", dict(clima=1)),
    ("Tormenta", dict(clima=2, t=0.13)),
    ("Nieve", dict(clima=3)),
    ("Corriendo", dict(paso=2, walk=1.4)),
    ("Sentado", dict(sitting=True)),
    ("Longdog", dict(meme=3, t=2.0)),
    ("Se hace el muerto", dict(meme=4, t=1.6)),
    ("Dab", dict(meme=5, t=1.0)),
    ("Como humano", dict(meme=7, t=2.0)),
    ("Mortal", dict(meme=8, t=0.55)),
    ("Baile", dict(meme=13, t=0.25)),
    ("ROFL", dict(meme=10, t=1.2, habla=True)),
    ("Trompo", dict(meme=2, t=0.15)),
    ("¿Eh?", dict(meme=9, t=1.0)),
    ("Susto", dict(meme=12, t=0.15)),
]


def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    tex = texture()
    path = os.path.join(RP, "textures/entity/lobo/lobo_bromista.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tex.save(path)

    # resource pack
    write(os.path.join(RP, "models/entity/lobo_bromista.geo.json"), wolf_geo())
    write(os.path.join(RP, "animations/lobo_bromista.animation.json"), animations())
    write(os.path.join(RP, "animation_controllers/lobo_bromista.animation_controllers.json"), controllers())
    write(os.path.join(RP, "entity/lobo_bromista.entity.json"), client_entity())
    write(os.path.join(RP, "render_controllers/lobo_bromista.render_controllers.json"), render_controllers())
    write(os.path.join(RP, "sounds.json"), sounds())
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    # behavior pack
    write(os.path.join(BP, "entities/lobo_bromista.json"), wolf_entity())
    write(os.path.join(BP, "spawn_rules/lobo_bromista.json"), spawn_rules())
    write(os.path.join(BP, "scripts/main.js"), script())
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon: the wolf with its sunglasses
    icon = Image.new("RGBA", (128, 128), (64, 150, 205, 255))
    dr = ImageDraw.Draw(icon)
    dr.rectangle([0, 92, 128, 128], fill=(92, 168, 70, 255))
    wolf = preview_frame(tex, clima=0, size=200, scale=7.5, yaw=-40)
    icon.alpha_composite(wolf.crop((36, 30, 164, 158)))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "LoboBromista.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev:
        cols, cell = 6, 200
        rows = (len(PREVIEW) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * cell, rows * (cell + 24)), (34, 40, 52, 255))
        d = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 15)
        except OSError:
            font = ImageFont.load_default()
        for n, (name, kw) in enumerate(PREVIEW):
            x, y = (n % cols) * cell, (n // cols) * (cell + 24)
            sheet.alpha_composite(preview_frame(tex, size=cell, **kw), (x, y))
            d.text((x + cell // 2, y + cell + 8), name, fill=(235, 240, 250, 255), anchor="mm", font=font)
        sheet.save(os.path.join(ROOT, "docs", "lobo_bromista_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
