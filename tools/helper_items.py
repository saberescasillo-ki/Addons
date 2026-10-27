"""Builds the "Objetos de Ayuda" add-on: four special items that help the player.

- Carga de Relevo (ayuda:carga_de_relevo): launches you ~15 blocks up and gives
  Slow Falling for 15 s. 70 uses, 30 s cooldown, not stackable.
- Estallido (ayuda:estallido): costs 3 hearts (absorption first) and blasts the
  mobs around you away with Slowness II. 2D icon, 3D in the hand (attachable).
  45 s cooldown, not stackable.
- Cabeza de Esqueleto Energica (ayuda:cabeza_esqueleto_energica): a block, so it
  is 3D in the inventory and in the hand. Using it summons an allied
  Esqueleto de Alma (ayuda:esqueleto_de_alma). 45 s cooldown.
- Faro Indeseado (ayuda:faro_indeseado): a glowing block like a froglight. Using
  it gives a random positive effect, level II, for 24 s. It is used up.

The blocks are never left placed: placing one counts as using it.

    python3 tools/helper_items.py            # regenerate the packs and the .mcaddon
    python3 tools/helper_items.py --preview  # also refresh docs/helper_items_preview.png
"""
import json
import math
import os
import random
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_NAME = "Objetos de Ayuda"
BP = os.path.join(ROOT, "HelperItems_BP")
RP = os.path.join(ROOT, "HelperItems_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "2.0.0"
MIN_ENGINE = [1, 21, 90]
UUIDS = dict(bp="ee3c9abb-806b-41b3-8eae-6391ecfaa95c", bp_data="a691e738-33b3-4c38-92e0-999cff9b71a5",
             bp_script="848b1be3-4f6a-4443-9392-f0336073766d", rp="89515645-3bd9-4d7e-b3f3-43a31c4d09bc",
             rp_res="090fe482-73aa-41f3-949d-5383d5a86cd9")

NS = "ayuda"
RELAY = f"{NS}:carga_de_relevo"
BURST = f"{NS}:estallido"
SKULL = f"{NS}:cabeza_esqueleto_energica"
BEACON = f"{NS}:faro_indeseado"
SKELETON = f"{NS}:esqueleto_de_alma"

# Everything the script uses; the values are copied into scripts/main.js.
CONFIG = dict(
    relay=dict(id=RELAY, uses=70, cooldown=30, launch=1.7,   # 1.7 ~ 15 blocks high
               slow_falling=15),
    burst=dict(id=BURST, cooldown=45, cost=6,                 # 6 = 3 hearts
               radius=3, damage=6, push=0.55, lift=0.35,     # push 0.55 ~ 4 blocks
               slowness_amp=1, slowness_time=5),
    skull=dict(id=SKULL, cooldown=45, entity=SKELETON),
    beacon=dict(id=BEACON, duration=24, amplifier=1),
)

# Positive effects without instant ones (no instant_health, no saturation).
EFFECTS = [
    ("speed", "Velocidad"), ("haste", "Prisa minera"), ("strength", "Fuerza"),
    ("jump_boost", "Salto"), ("regeneration", "Regeneración"), ("resistance", "Resistencia"),
    ("fire_resistance", "Resistencia al fuego"), ("water_breathing", "Respiración acuática"),
    ("invisibility", "Invisibilidad"), ("night_vision", "Visión nocturna"),
    ("health_boost", "Vida extra"), ("absorption", "Absorción"), ("conduit_power", "Poder del conducto"),
    ("slow_falling", "Caída lenta"), ("village_hero", "Héroe de la aldea"),
]

SKELETON_STATS = dict(health=80,     # 4 skeletons x 20
                      speed=0.253,   # zombie 0.23 + 10 %
                      damage=6)      # 3 hearts against no armour

# Soul fire colours.
SOUL = dict(hi="#d6fdff", bone="#8eeef7", mid="#55d3e2", deep="#239fb3", dark="#0c4552",
            socket="#062a33", eye="#f2ffff", eye2="#7ff6ff")


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (c[3],)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) + (255,)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- textures
def box_faces(u, v, w, h, d):
    """Box-UV face rectangles (x, y, width, height) of a cube."""
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


def relay_icon():
    """Wind-charge-like ball, but round, with swirling wind lines."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    light, base, dark, line = hx("#f4fbff"), hx("#b9def2"), hx("#6fa7c9"), hx("#38698c")
    c, r = 7.5, 6.6
    for y in range(16):
        for x in range(16):
            dx, dy = x - c, y - c
            d = math.hypot(dx, dy)
            if d > r:
                continue
            if d > r - 1.0:
                im.putpixel((x, y), line)
                continue
            lit = max(0.0, (-dx - dy) / (r * 1.4)) + 0.35 * (1 - d / r)
            col = mix(dark, base, min(1, 0.4 + lit)) if lit < 0.6 else mix(base, light, min(1, lit))
            swirl = math.sin(3 * math.atan2(dy, dx) + d * 1.15)
            if swirl > 0.72:
                col = mix(col, light, 0.75)
            elif swirl < -0.8:
                col = mix(col, dark, 0.55)
            im.putpixel((x, y), col)
    im.putpixel((5, 4), (255, 255, 255, 255))
    im.putpixel((4, 5), (255, 255, 255, 255))
    return im


def burst_icon():
    """Soul-blue rhombus with a heavy-core-like embossed swirl."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    out, edge, mid, light, core = hx("#0b5563"), hx("#1fb6c9"), hx("#4fd8e6"), hx("#bff8fd"), hx("#0e7f90")
    cx, cy = 7.5, 7.5
    for y in range(16):
        for x in range(16):
            dx, dy = x - cx, y - cy
            k = abs(dx) / 5.6 + abs(dy) / 7.6
            if k > 1:
                continue
            if k > 0.82:
                im.putpixel((x, y), out)
                continue
            # four facets: top-left brightest, bottom-right darkest
            if dx <= 0 and dy <= 0:
                col = mix(mid, light, 0.55)
            elif dx > 0 and dy > 0:
                col = edge
            else:
                col = mid
            if k < 0.32:
                col = mix(col, light, 0.6)
            im.putpixel((x, y), col)
    for p in [(7, 6), (8, 6), (8, 7), (8, 8), (7, 9), (6, 8), (6, 7)]:
        im.putpixel(p, core)
    im.putpixel((7, 7), hx("#ffffff"))
    im.putpixel((5, 4), hx("#ffffff"))
    return im


def burst_model_texture():
    rng = random.Random(7)
    pal = [hx("#3fcfdd"), hx("#5fe3ee"), hx("#2bb4c6"), hx("#8ef4fa"), hx("#49d6e4")]
    im = Image.new("RGBA", (32, 32))
    for y in range(32):
        for x in range(32):
            c = rng.choice(pal)
            if rng.random() < 0.05:
                c = hx("#e6ffff")
            im.putpixel((x, y), c)
    return im


def skull_face(pal, glow):
    """The 8x8 front of a skeleton head."""
    bone, mid, socket = pal

    def fn(x, y, w, h):
        eye = y in (3, 4) and x in (1, 2, 5, 6)
        if eye:
            inner = (x in (1, 5)) == (y == 3)
            return glow[0] if inner else glow[1]
        if y == 5 and x in (3, 4):
            return socket
        if y == 6 and 1 <= x <= 6:
            return socket if x % 2 == 1 else mid
        if y == 2 and x in (1, 2, 5, 6):
            return mid
        return bone if (x + y * 3) % 7 else mid
    return fn


def noisy(rng, a, b, p):
    return lambda x, y, w, h: b if rng.random() < p else a


def skull_texture():
    """Vanilla-like skeleton skull (gray bone) with cyan eyes, 32x16."""
    rng = random.Random(3)
    bone, mid, dark, socket = hx("#c9c9c9"), hx("#a6a6a6"), hx("#7a7a7a"), hx("#353535")
    im = Image.new("RGBA", (32, 16))
    f = box_faces(0, 0, 8, 8, 8)
    for name in ("top", "bottom", "right", "left", "back"):
        paint(im, f[name], noisy(rng, bone if name != "bottom" else mid, dark if name == "bottom" else mid, 0.25))
    paint(im, f["front"], skull_face((bone, mid, socket), (hx("#c8ffff"), hx("#21cfe3"))))
    return im


def skeleton_texture():
    """Cyan (soul fire) skeleton in the vanilla 64x32 layout, plus its sword."""
    rng = random.Random(11)
    C = {k: hx(v) for k, v in SOUL.items()}
    im = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    # head
    f = box_faces(0, 0, 8, 8, 8)
    for name in ("top", "right", "left", "back"):
        paint(im, f[name], noisy(rng, C["bone"], C["mid"], 0.25))
    paint(im, f["bottom"], noisy(rng, C["mid"], C["deep"], 0.3))
    paint(im, f["front"], skull_face((C["bone"], C["mid"], C["socket"]), (C["eye"], C["eye2"])))

    # body: ribs, spine and pelvis over a dark background
    def ribs(x, y, w, h):
        spine = w >= 8 and x in (3, 4)
        if y == 0:
            return C["hi"]
        if spine:
            return C["bone"] if y % 2 else C["hi"]
        if y in (2, 4, 6) and 0 < x < w - 1:
            return C["bone"]
        if y >= 9:
            return C["mid"] if (x in (3, 4) and y == 10) else C["bone"]
        return C["dark"]
    f = box_faces(16, 16, 8, 12, 4)
    for name in ("front", "back", "right", "left"):
        paint(im, f[name], ribs)
    paint(im, f["top"], noisy(rng, C["hi"], C["bone"], 0.3))
    paint(im, f["bottom"], noisy(rng, C["mid"], C["deep"], 0.3))

    # arms and legs
    def limb(x, y, w, h):
        if y in (0, h - 1, h // 2):
            return C["hi"]
        return C["mid"] if x == w - 1 else C["bone"]
    for u, v in ((40, 16), (0, 16)):
        f = box_faces(u, v, 2, 12, 2)
        for name in ("front", "back", "right", "left"):
            paint(im, f[name], limb)
        paint(im, f["top"], lambda *a: C["hi"])
        paint(im, f["bottom"], lambda *a: C["mid"])

    # sword: blade (48,16) 2x14x1, guard (54,16) 4x1x1, grip (8,16) 1x4x1
    steel, steel2, edge = hx("#e3edf1"), hx("#b5c6cf"), hx("#7ff0fa")

    def blade(x, y, w, h):
        if y == h - 1 and w == 2 and x == 1:
            return None  # pointed tip
        if w == 1:
            return edge
        return steel if x == 0 else steel2
    f = box_faces(48, 16, 2, 14, 1)
    for name in f:
        paint(im, f[name], blade)
    f = box_faces(54, 16, 4, 1, 1)
    for name in f:
        paint(im, f[name], lambda x, y, w, h: hx("#39e8f5") if (w == 4 and x in (1, 2)) else hx("#2f3d47"))
    f = box_faces(8, 16, 1, 4, 1)
    for name in f:
        paint(im, f[name], lambda x, y, w, h: hx("#2bb4c6") if y % 2 else hx("#3a2a22"))
    return im


def beacon_textures():
    """Pearlescent froglight-like faces: side with stripes, top with rings."""
    rng = random.Random(5)
    pastel = [hx("#f6b8e6"), hx("#d9c2ff"), hx("#b4f1ff"), hx("#fff0b3"), hx("#fffaff")]
    frame = hx("#b48ad8")
    side = Image.new("RGBA", (16, 16))
    top = Image.new("RGBA", (16, 16))
    for y in range(16):
        for x in range(16):
            if x in (0, 15) or y in (0, 15):
                side.putpixel((x, y), frame)
            else:
                c = pastel[(x // 2 + (y // 5)) % len(pastel)]
                if rng.random() < 0.18:
                    c = mix(c, hx("#ffffff"), 0.6)
                side.putpixel((x, y), c)
            ring = int(max(abs(x - 7.5), abs(y - 7.5)))
            if ring == 7:
                top.putpixel((x, y), frame)
            else:
                c = pastel[ring % len(pastel)]
                if rng.random() < 0.12:
                    c = mix(c, hx("#ffffff"), 0.6)
                top.putpixel((x, y), c)
    return side, top


# ---------------------------------------------------------------- models
def cube(origin, size, uv, **kw):
    return dict(origin=origin, size=size, uv=uv, **kw)


def geo(identifier, tw, th, bones, **desc):
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": dict(identifier=identifier, texture_width=tw, texture_height=th, **desc),
        "bones": bones}]}


def skeleton_geo():
    bones = [
        dict(name="root", pivot=[0, 0, 0]),
        dict(name="body", parent="root", pivot=[0, 12, 0], cubes=[cube([-4, 12, -2], [8, 12, 4], [16, 16])]),
        dict(name="head", parent="body", pivot=[0, 24, 0], cubes=[cube([-4, 24, -4], [8, 8, 8], [0, 0])]),
        dict(name="rightArm", parent="body", pivot=[-5, 22, 0], cubes=[cube([-6, 12, -1], [2, 12, 2], [40, 16])]),
        dict(name="sword", parent="rightArm", pivot=[-5, 11, 0], cubes=[
            cube([-5.5, 9, -0.5], [1, 4, 1], [8, 16]),
            cube([-7, 8, -0.5], [4, 1, 1], [54, 16]),
            cube([-6, -6, -0.5], [2, 14, 1], [48, 16])]),
        dict(name="leftArm", parent="body", pivot=[5, 22, 0],
             cubes=[cube([4, 12, -1], [2, 12, 2], [40, 16], mirror=True)]),
        dict(name="rightLeg", parent="root", pivot=[-2, 12, 0], cubes=[cube([-3, 0, -1], [2, 12, 2], [0, 16])]),
        dict(name="leftLeg", parent="root", pivot=[2, 12, 0],
             cubes=[cube([1, 0, -1], [2, 12, 2], [0, 16], mirror=True)]),
    ]
    return geo("geometry.ayuda.esqueleto_de_alma", 64, 32, bones,
               visible_bounds_width=3, visible_bounds_height=3, visible_bounds_offset=[0, 1.5, 0])


def gem_cubes():
    sizes = [2, 4, 6, 8, 6, 4, 2]
    step = 1.5
    y0 = -step * len(sizes) / 2
    return [cube([-s / 2, y0 + i * step, -s / 2], [s, step, s], [0, 0]) for i, s in enumerate(sizes)]


def burst_geo():
    bones = [dict(name="estallido", pivot=[0, 0, 0], binding="q.item_slot_to_bone_name(c.item_slot)"),
             dict(name="gem", parent="estallido", pivot=[0, 0, 0], cubes=gem_cubes())]
    return geo("geometry.ayuda.estallido", 32, 32, bones,
               visible_bounds_width=2, visible_bounds_height=2, visible_bounds_offset=[0, 0.5, 0])


def skull_geo():
    # Turned around so the face points south, the side the inventory shows.
    bones = [dict(name="skull", pivot=[0, 0, 0], rotation=[0, 180, 0],
                  cubes=[cube([-4, 0, -4], [8, 8, 8], [0, 0])])]
    return geo("geometry.ayuda.cabeza_esqueleto_energica", 32, 16, bones)


# ---------------------------------------------------------------- animations
WALK = "q.modified_distance_moved * 38.17"


def skeleton_animations():
    idle_arm = lambda side: {"rotation": [-35, 0, -25 * side]}
    anims = {
        "animation.ayuda.esqueleto_de_alma.look": {"loop": True, "bones": {
            "head": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}}},
        "animation.ayuda.esqueleto_de_alma.legs": {"loop": True, "bones": {
            "rightLeg": {"rotation": [f"math.cos({WALK}) * 50 * q.modified_move_speed", 0, 0]},
            "leftLeg": {"rotation": [f"-math.cos({WALK}) * 50 * q.modified_move_speed", 0, 0]}}},
        # Resting: both hands on the pommel, the tip of the sword on the ground.
        "animation.ayuda.esqueleto_de_alma.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(q.life_time * 90) * 1.5", 0, 0]},
            "rightArm": idle_arm(1), "leftArm": idle_arm(-1),
            "sword": {"rotation": [35, 0, 25]}}},
        # Walking: both hands on the sword held ahead, leaning toward where it goes.
        "animation.ayuda.esqueleto_de_alma.walk": {"loop": True, "bones": {
            "body": {"rotation": ["12 + math.sin(" + WALK + " * 2) * 2", 0, 0]},
            "head": {"rotation": [-12, 0, 0]},
            "rightArm": {"rotation": [f"-50 + math.sin({WALK}) * 4", 0, 25]},
            "leftArm": {"rotation": [f"-50 + math.sin({WALK}) * 4", 0, -25]},
            "sword": {"rotation": [-40, 0, 0]}}},
        # Epic thrust: pulls the sword back, lunges forward and stabs.
        "animation.ayuda.esqueleto_de_alma.attack": {"animation_length": 0.65, "bones": {
            "root": {"position": {"0.0": [0, 0, 0], "0.2": [0, 0, 1], "0.35": [0, 0, -4],
                                  "0.5": [0, 0, -4], "0.65": [0, 0, 0]}},
            "body": {"rotation": {"0.0": [12, 0, 0], "0.2": [-6, 25, 0], "0.35": [22, -15, 0],
                                  "0.5": [20, -12, 0], "0.65": [12, 0, 0]}},
            "rightArm": {"rotation": {"0.0": [-50, 0, 25], "0.2": [-20, 0, 10], "0.35": [-95, 0, 10],
                                      "0.5": [-92, 0, 10], "0.65": [-50, 0, 25]}},
            "leftArm": {"rotation": {"0.0": [-50, 0, -25], "0.2": [-25, 0, -20], "0.35": [-95, 0, -20],
                                     "0.5": [-92, 0, -20], "0.65": [-50, 0, -25]}},
            "sword": {"rotation": {"0.0": [-40, 0, 0], "0.2": [-70, 0, 0], "0.35": [5, 0, 0],
                                   "0.5": [5, 0, 0], "0.65": [-40, 0, 0]}},
            "rightLeg": {"rotation": {"0.0": [0, 0, 0], "0.35": [-30, 0, 0], "0.5": [-30, 0, 0],
                                      "0.65": [0, 0, 0]}},
            "leftLeg": {"rotation": {"0.0": [0, 0, 0], "0.35": [25, 0, 0], "0.5": [25, 0, 0],
                                     "0.65": [0, 0, 0]}}}},
        # Crawls out of the ground (0.5 s), clawing with both arms.
        "animation.ayuda.esqueleto_de_alma.emerge": {
            "animation_length": 0.5,
            "particle_effects": {"0.0": {"effect": "soul"}, "0.25": {"effect": "soul"}},
            "bones": {
                "root": {"position": {"0.0": [0, -26, 0], "0.25": [0, -11, 0], "0.5": [0, 0, 0]},
                         "rotation": {"0.0": [35, 0, 0], "0.25": [25, 0, 0], "0.5": [0, 0, 0]}},
                "rightArm": {"rotation": {"0.0": [-135, 0, 0], "0.15": [-60, 0, 0], "0.3": [-120, 0, 0],
                                          "0.5": [0, 0, 0]}},
                "leftArm": {"rotation": {"0.0": [-60, 0, 0], "0.15": [-130, 0, 0], "0.3": [-60, 0, 0],
                                         "0.5": [0, 0, 0]}}}},
        # Dies by shrinking away.
        "animation.ayuda.esqueleto_de_alma.death": {
            "animation_length": 0.9, "loop": "hold_on_last_frame",
            "particle_effects": {"0.0": {"effect": "soul"}, "0.4": {"effect": "soul"}},
            "bones": {"root": {
                "scale": {"0.0": 1, "0.15": 1.1, "0.8": 0.01, "0.9": 0.0},
                "rotation": {"0.0": [0, 0, 0], "0.8": [0, 270, 0]}}}},
    }
    return {"format_version": "1.8.0", "animations": anims}


def skeleton_controllers():
    p = "controller.animation.ayuda.esqueleto_de_alma"
    return {"format_version": "1.10.0", "animation_controllers": {
        f"{p}.pose": {"initial_state": "idle", "states": {
            "idle": {"animations": ["idle"], "blend_transition": 0.2,
                     "transitions": [{"attack": "v.attack_time > 0"}, {"walk": "q.modified_move_speed > 0.1"}]},
            "walk": {"animations": ["walk"], "blend_transition": 0.2,
                     "transitions": [{"attack": "v.attack_time > 0"}, {"idle": "q.modified_move_speed <= 0.1"}]},
            "attack": {"animations": ["attack"], "blend_transition": 0.1,
                       "transitions": [{"idle": "q.all_animations_finished"}]}}},
        f"{p}.emerge": {"initial_state": "check", "states": {
            "check": {"transitions": [{"emerge": f"!q.property('{NS}:emerged')"},
                                      {"done": f"q.property('{NS}:emerged')"}]},
            "emerge": {"animations": ["emerge"], "transitions": [{"done": "q.all_animations_finished"}]},
            "done": {}}},
        f"{p}.death": {"initial_state": "alive", "states": {
            "alive": {"transitions": [{"dead": "!q.is_alive"}]},
            "dead": {"animations": ["death"]}}},
    }}


def burst_animations():
    return {"format_version": "1.8.0", "animations": {
        "animation.ayuda.estallido.first_person": {"loop": True, "bones": {
            "estallido": {"rotation": [-10, 40, 0], "position": [0, 3, -2], "scale": 0.6}}},
        "animation.ayuda.estallido.third_person": {"loop": True, "bones": {
            "estallido": {"position": [0, 0, -2], "scale": 0.7}}},
        "animation.ayuda.estallido.spin": {"loop": True, "bones": {
            "gem": {"rotation": [0, "q.life_time * 60", 0], "position": [0, "math.sin(q.life_time * 120) * 0.4", 0]}}},
    }}


# ---------------------------------------------------------------- behavior pack
def item(identifier, icon, components, category="equipment"):
    comps = {"minecraft:icon": icon,
             "minecraft:display_name": {"value": f"item.{identifier}.name"}}
    comps.update(components)
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": identifier, "menu_category": {"category": category}},
        "components": comps}}


def items():
    r, b = CONFIG["relay"], CONFIG["burst"]
    use = {"minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0}}
    return {
        "carga_de_relevo": item(RELAY, "ayuda_carga_de_relevo", {
            "minecraft:max_stack_size": 1,
            "minecraft:durability": {"max_durability": r["uses"], "damage_chance": {"min": 0, "max": 0}},
            "minecraft:cooldown": {"category": RELAY, "duration": r["cooldown"]},
            **use}),
        "estallido": item(BURST, "ayuda_estallido", {
            "minecraft:max_stack_size": 1,
            "minecraft:glint": True,
            "minecraft:cooldown": {"category": BURST, "duration": b["cooldown"]},
            **use}),
    }


def blocks():
    return {
        "cabeza_esqueleto_energica": {"format_version": "1.21.90", "minecraft:block": {
            "description": {"identifier": SKULL, "menu_category": {"category": "equipment"}},
            "components": {
                "minecraft:geometry": "geometry.ayuda.cabeza_esqueleto_energica",
                "minecraft:material_instances": {"*": {"texture": "ayuda_cabeza_energica",
                                                       "render_method": "alpha_test"}},
                "minecraft:collision_box": {"origin": [-4, 0, -4], "size": [8, 8, 8]},
                "minecraft:selection_box": {"origin": [-4, 0, -4], "size": [8, 8, 8]},
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.5},
                "minecraft:light_dampening": 0,
                "minecraft:map_color": "#c9c9c9"}}},
        "faro_indeseado": {"format_version": "1.21.90", "minecraft:block": {
            "description": {"identifier": BEACON, "menu_category": {"category": "items"}},
            "components": {
                "minecraft:geometry": "minecraft:geometry.full_block",
                "minecraft:material_instances": {
                    "*": {"texture": "ayuda_faro_lado", "render_method": "opaque"},
                    "up": {"texture": "ayuda_faro_arriba", "render_method": "opaque"},
                    "down": {"texture": "ayuda_faro_arriba", "render_method": "opaque"}},
                "minecraft:light_emission": 15,
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 0.3},
                "minecraft:map_color": "#e6c8f5"}}},
    }


def skeleton_entity():
    s = SKELETON_STATS
    monster = {"all_of": [{"test": "is_family", "subject": "other", "value": "monster"},
                          {"test": "is_family", "subject": "other", "operator": "!=", "value": "creeper"}]}
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": SKELETON, "is_spawnable": True, "is_summonable": True,
                        "properties": {f"{NS}:emerged": {"type": "bool", "default": False, "client_sync": True}}},
        "component_groups": {
            f"{NS}:emerging": {
                "minecraft:movement": {"value": 0},
                "minecraft:timer": {"time": 0.5, "looping": False,
                                    "time_down_event": {"event": f"{NS}:emerged", "target": "self"}}},
            f"{NS}:active": {"minecraft:movement": {"value": s["speed"]}},
            f"{NS}:tamed": {
                "minecraft:is_tamed": {},
                "minecraft:behavior.follow_owner": {"priority": 5, "speed_multiplier": 1.0,
                                                    "start_distance": 10, "stop_distance": 3},
                "minecraft:behavior.owner_hurt_by_target": {"priority": 1},
                "minecraft:behavior.owner_hurt_target": {"priority": 2}},
        },
        "components": {
            "minecraft:type_family": {"family": [f"{NS}_soul_skeleton", "undead", "mob"]},
            "minecraft:health": {"value": s["health"], "max": s["health"]},
            "minecraft:attack": {"damage": s["damage"]},
            "minecraft:collision_box": {"width": 0.6, "height": 1.99},
            "minecraft:movement.basic": {},
            "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_damage_blocks": True,
                                          "can_open_doors": True},
            "minecraft:jump.static": {},
            "minecraft:can_climb": {},
            "minecraft:physics": {},
            "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
            "minecraft:nameable": {},
            "minecraft:persistent": {},
            "minecraft:fire_immune": True,
            "minecraft:knockback_resistance": {"value": 0.3},
            "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
            "minecraft:damage_sensor": {"triggers": [
                {"cause": "fall", "deals_damage": "no"},
                {"on_damage": {"filters": {"test": "is_family", "subject": "other",
                                           "value": f"{NS}_soul_skeleton"}}, "deals_damage": "no"}]},
            "minecraft:tameable": {"probability": 0.0, "tame_items": "bone",
                                   "tame_event": {"event": f"{NS}:tame", "target": "self"}},
            "minecraft:behavior.float": {"priority": 0},
            "minecraft:behavior.melee_attack": {"priority": 3, "speed_multiplier": 1.2, "track_target": True},
            "minecraft:behavior.hurt_by_target": {"priority": 1, "entity_types": {
                "filters": {"test": "is_family", "subject": "other", "operator": "!=", "value": "player"}}},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 3, "must_see": True, "reselect_targets": True, "within_radius": 16,
                "entity_types": [{"filters": monster, "max_dist": 16}]},
            "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.8},
            "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 8},
            "minecraft:behavior.random_look_around": {"priority": 9},
            "minecraft:conditional_bandwidth_optimization": {},
        },
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:emerging"]}},
            f"{NS}:emerged": {"remove": {"component_groups": [f"{NS}:emerging"]},
                              "add": {"component_groups": [f"{NS}:active"]},
                              "set_property": {f"{NS}:emerged": True}},
            f"{NS}:tame": {"add": {"component_groups": [f"{NS}:tamed"]}},
        },
    }}


# ---------------------------------------------------------------- resource pack
def skeleton_client():
    a = "animation.ayuda.esqueleto_de_alma"
    c = "controller.animation.ayuda.esqueleto_de_alma"
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": SKELETON,
        "materials": {"default": "skeleton"},
        "textures": {"default": "textures/entity/ayuda/esqueleto_de_alma"},
        "geometry": {"default": "geometry.ayuda.esqueleto_de_alma"},
        "render_controllers": ["controller.render.ayuda.esqueleto_de_alma"],
        "particle_effects": {"soul": "minecraft:soul_particle"},
        "animations": {
            "look": f"{a}.look", "legs": f"{a}.legs", "idle": f"{a}.idle", "walk": f"{a}.walk",
            "attack": f"{a}.attack", "emerge": f"{a}.emerge", "death": f"{a}.death",
            "pose": f"{c}.pose", "emerge_ctrl": f"{c}.emerge", "death_ctrl": f"{c}.death"},
        "scripts": {"animate": ["look", "legs", "pose", "emerge_ctrl", "death_ctrl"]},
        "spawn_egg": {"base_color": "#8eeef7", "overlay_color": "#0c4552"},
    }}}


def burst_attachable():
    return {"format_version": "1.10.0", "minecraft:attachable": {"description": {
        "identifier": BURST,
        "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
        "textures": {"default": "textures/entity/ayuda/estallido",
                     "enchanted": "textures/misc/enchanted_item_glint"},
        "geometry": {"default": "geometry.ayuda.estallido"},
        "animations": {"first_person": "animation.ayuda.estallido.first_person",
                       "third_person": "animation.ayuda.estallido.third_person",
                       "spin": "animation.ayuda.estallido.spin"},
        "scripts": {"animate": [{"first_person": "c.is_first_person"},
                                {"third_person": "!c.is_first_person"}, "spin"]},
        "render_controllers": ["controller.render.item_default"],
    }}}


def render_controllers():
    return {"format_version": "1.8.0", "render_controllers": {
        "controller.render.ayuda.esqueleto_de_alma": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"]}}}


LANG = {
    "es": {
        f"item.{RELAY}.name": "Carga de Relevo",
        f"item.{BURST}.name": "Estallido",
        f"tile.{SKULL}.name": "Cabeza de Esqueleto Enérgica",
        f"tile.{BEACON}.name": "Faro Indeseado",
        f"entity.{SKELETON}.name": "Esqueleto de Alma",
        f"item.spawn_egg.entity.{SKELETON}.name": "Generar Esqueleto de Alma",
        "pack.name": ADDON_NAME,
        "pack.description": "Objetos especiales que ayudan al jugador.",
    },
    "en": {
        f"item.{RELAY}.name": "Relay Charge",
        f"item.{BURST}.name": "Burst",
        f"tile.{SKULL}.name": "Energetic Skeleton Skull",
        f"tile.{BEACON}.name": "Unwanted Beacon",
        f"entity.{SKELETON}.name": "Soul Skeleton",
        f"item.spawn_egg.entity.{SKELETON}.name": "Spawn Soul Skeleton",
        "pack.name": "Helper Items",
        "pack.description": "Special items that help the player.",
    },
}


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


def sounds():
    return {"entity_sounds": {"entities": {SKELETON: {"volume": 1.0, "pitch": [0.9, 1.1], "events": {
        "ambient": "mob.skeleton.say", "hurt": "mob.skeleton.hurt", "death": "mob.skeleton.death",
        "step": {"sound": "mob.skeleton.step", "volume": 0.6}}}}}}


# ---------------------------------------------------------------- script
SCRIPT = r"""// Objetos de Ayuda: what each special item does when used.
// Generated by tools/helper_items.py (change the values there).
import { EntityDamageCause, EquipmentSlot, ItemStack, system, world } from "@minecraft/server";

const CFG = __CONFIG__;
const EFFECTS = __EFFECTS__;
const SECOND = 20;

// ------------------------------------------------------------ helpers
const cooldowns = new Map(); // "player:item" -> tick when it is ready again
const lastUse = new Map();   // "player:item" -> tick of the last use (double events)

function isCreative(player) {
  return String(player.getGameMode()).toLowerCase() === "creative";
}

function say(player, text) {
  player.onScreenDisplay.setActionBar(text);
}

// Some uses arrive twice (item use + block placement): ignore the repeat.
function repeated(player, id) {
  const key = `${player.id}:${id}`;
  const last = lastUse.get(key);
  if (last !== undefined && system.currentTick - last <= 4) return true;
  lastUse.set(key, system.currentTick);
  return false;
}

// true while on cooldown (and tells the player how long is left)
function onCooldown(player, id, name) {
  const left = (cooldowns.get(`${player.id}:${id}`) ?? 0) - system.currentTick;
  if (left <= 0) return false;
  say(player, `§7${name}: recargando §f${Math.ceil(left / SECOND)} s`);
  return true;
}

function startCooldown(player, id, seconds) {
  cooldowns.set(`${player.id}:${id}`, system.currentTick + seconds * SECOND);
  try {
    player.startItemCooldown(id, seconds * SECOND);
  } catch {}
}

function equip(player) {
  return player.getComponent("minecraft:equippable");
}

function consumeHand(player, id) {
  if (isCreative(player)) return;
  const eq = equip(player);
  const it = eq.getEquipment(EquipmentSlot.Mainhand);
  if (!it || it.typeId !== id) return;
  if (it.amount > 1) {
    it.amount -= 1;
    eq.setEquipment(EquipmentSlot.Mainhand, it);
  } else eq.setEquipment(EquipmentSlot.Mainhand, undefined);
}

function giveBack(player, id) {
  if (isCreative(player)) return;
  const eq = equip(player);
  const hand = eq.getEquipment(EquipmentSlot.Mainhand);
  if (!hand) return eq.setEquipment(EquipmentSlot.Mainhand, new ItemStack(id, 1));
  if (hand.typeId === id && hand.amount < hand.maxAmount) {
    hand.amount += 1;
    return eq.setEquipment(EquipmentSlot.Mainhand, hand);
  }
  const left = player.getComponent("minecraft:inventory").container.addItem(new ItemStack(id, 1));
  if (left) player.dimension.spawnItem(left, player.location);
}

// applyKnockback changed its arguments in @minecraft/server 2.0.0
function knock(entity, x, z, horizontal, vertical) {
  try {
    entity.applyKnockback({ x: x * horizontal, z: z * horizontal }, vertical);
  } catch {
    entity.applyKnockback(x, z, horizontal, vertical);
  }
}

function particles(dim, id, at, count = 1, spread = 0) {
  for (let i = 0; i < count; i++) {
    const p = { x: at.x + (Math.random() * 2 - 1) * spread, y: at.y + Math.random() * spread,
                z: at.z + (Math.random() * 2 - 1) * spread };
    try {
      dim.spawnParticle(id, p);
    } catch {}
  }
}

// ------------------------------------------------------------ Carga de Relevo
function useRelay(player) {
  const c = CFG.relay;
  if (repeated(player, c.id) || onCooldown(player, c.id, "Carga de Relevo")) return;
  startCooldown(player, c.id, c.cooldown);
  const dim = player.dimension;
  const at = player.location;
  knock(player, 0, 0, 0, c.launch);
  particles(dim, "minecraft:wind_explosion_emitter", at);
  dim.playSound("wind_charge.burst", at, { volume: 1, pitch: 1.1 });

  // Slow Falling starts at the top of the jump, so the climb stays the same.
  const start = system.currentTick;
  const run = system.runInterval(() => {
    if (!player.isValid) return system.clearRun(run);
    const t = system.currentTick - start;
    if ((t > 3 && player.getVelocity().y <= 0) || t > 3 * SECOND) {
      player.addEffect("slow_falling", c.slow_falling * SECOND, { amplifier: 0, showParticles: true });
      system.clearRun(run);
    }
  }, 1);

  // one use less
  if (isCreative(player)) return;
  const eq = equip(player);
  const it = eq.getEquipment(EquipmentSlot.Mainhand);
  if (!it || it.typeId !== c.id) return;
  const dur = it.getComponent("minecraft:durability");
  if (!dur) return;
  if (dur.damage + 1 >= dur.maxDurability) {
    eq.setEquipment(EquipmentSlot.Mainhand, undefined);
    player.playSound("random.break");
    return;
  }
  dur.damage += 1;
  eq.setEquipment(EquipmentSlot.Mainhand, it);
  say(player, `§bCarga de Relevo: §f${dur.maxDurability - dur.damage} usos`);
}

// ------------------------------------------------------------ Estallido
function useBurst(player) {
  const c = CFG.burst;
  if (repeated(player, c.id) || onCooldown(player, c.id, "Estallido")) return;
  const creative = isCreative(player);
  const health = player.getComponent("minecraft:health");
  // Absorption (golden hearts) pays first; without it, never kill the player.
  if (!creative && !player.getEffect("absorption") && health.currentValue <= c.cost) {
    say(player, "§cNo tienes vida suficiente para el Estallido");
    return;
  }
  startCooldown(player, c.id, c.cooldown);
  if (!creative) player.applyDamage(c.cost, { cause: EntityDamageCause.magic });

  const dim = player.dimension;
  const at = player.location;
  particles(dim, "minecraft:huge_explosion_emitter", at);
  particles(dim, "minecraft:blue_flame_particle", { x: at.x, y: at.y + 0.2, z: at.z }, 30, c.radius);
  particles(dim, "minecraft:soul_particle", { x: at.x, y: at.y + 0.2, z: at.z }, 20, c.radius);
  dim.playSound("random.explode", at, { volume: 1, pitch: 1.2 });

  const hit = [];
  for (const e of dim.getEntities({ location: at, maxDistance: c.radius,
                                    excludeFamilies: ["player", "inanimate", "ayuda_soul_skeleton"] })) {
    if (!e.getComponent("minecraft:health")) continue;
    if (e.getComponent("minecraft:tameable")?.isTamed) continue; // spare pets
    e.applyDamage(c.damage, { cause: EntityDamageCause.entityExplosion, damagingEntity: player });
    e.addEffect("slowness", c.slowness_time * SECOND, { amplifier: c.slowness_amp });
    hit.push(e);
  }
  // Push next tick so the hit's own knockback doesn't cancel it.
  system.run(() => {
    for (const e of hit) {
      if (!e.isValid) continue;
      const dx = e.location.x - at.x;
      const dz = e.location.z - at.z;
      const len = Math.hypot(dx, dz) || 1;
      knock(e, dx / len, dz / len, c.push, c.lift);
    }
  });
}

// ------------------------------------------------------------ Cabeza de Esqueleto Enérgica
function frontOf(player) {
  const p = player.location;
  const v = player.getViewDirection();
  const len = Math.hypot(v.x, v.z) || 1;
  const at = { x: p.x + (v.x / len) * 2, y: p.y, z: p.z + (v.z / len) * 2 };
  try {
    const b = player.dimension.getBlock(at);
    if (b && !b.isAir && !b.isLiquid) return p;
  } catch {}
  return at;
}

function useSkull(player, at) {
  const c = CFG.skull;
  if (repeated(player, c.id) || onCooldown(player, c.id, "Cabeza de Esqueleto Enérgica")) return;
  startCooldown(player, c.id, c.cooldown);
  const dim = player.dimension;
  const where = at ?? frontOf(player);
  const sk = dim.spawnEntity(c.entity, where);
  sk.setRotation({ x: 0, y: player.getRotation().y });
  try {
    sk.getComponent("minecraft:tameable")?.tame(player);
  } catch {}
  sk.triggerEvent("ayuda:tame");
  particles(dim, "minecraft:soul_particle", where, 12, 0.7);
  dim.playSound("dig.soul_sand", where, { volume: 1, pitch: 0.8 });
  dim.playSound("mob.skeleton.say", where, { volume: 1, pitch: 0.7 });
}

// ------------------------------------------------------------ Faro Indeseado
function useBeacon(player, consume) {
  const c = CFG.beacon;
  if (repeated(player, c.id)) return false;
  const [effect, name] = EFFECTS[Math.floor(Math.random() * EFFECTS.length)];
  player.addEffect(effect, c.duration * SECOND, { amplifier: c.amplifier, showParticles: true });
  say(player, `§d${name} II §fdurante ${c.duration} s`);
  player.dimension.playSound("beacon.activate", player.location, { volume: 1, pitch: 1.3 });
  particles(player.dimension, "minecraft:totem_particle", player.location, 10, 0.8);
  if (consume) consumeHand(player, c.id);
  return true;
}

// ------------------------------------------------------------ events
world.afterEvents.itemUse.subscribe(({ source: player, itemStack }) => {
  if (player?.typeId !== "minecraft:player" || !itemStack) return;
  switch (itemStack.typeId) {
    case CFG.relay.id: return useRelay(player);
    case CFG.burst.id: return useBurst(player);
    case CFG.skull.id: return useSkull(player);
    case CFG.beacon.id: return useBeacon(player, true);
  }
});

// The skull and the beacon are blocks (so they look 3D): placing one is using it.
const BLOCK_ITEMS = [CFG.skull.id, CFG.beacon.id];

function useByPlacing(player, id, block) {
  const at = { x: block.x + 0.5, y: block.y, z: block.z + 0.5 };
  if (id === CFG.skull.id) useSkull(player, at);
  else useBeacon(player, true);
}

const placeBefore = world.beforeEvents.playerPlaceBlock;
if (placeBefore) {
  // Cancel the placement: the item stays in the hand.
  placeBefore.subscribe((ev) => {
    const id = ev.permutationToPlace?.type.id;
    if (!BLOCK_ITEMS.includes(id)) return;
    ev.cancel = true;
    const { player, block } = ev;
    const loc = block.location;
    system.run(() => useByPlacing(player, id, loc));
  });
} else {
  // Older API: remove the placed block and undo what the placement spent.
  world.afterEvents.playerPlaceBlock.subscribe(({ player, block }) => {
    const id = block.typeId;
    if (!BLOCK_ITEMS.includes(id)) return;
    const loc = block.location;
    block.setType("minecraft:air");
    giveBack(player, id);
    useByPlacing(player, id, loc);
  });
}
"""


def script():
    out = SCRIPT
    for key, value in dict(CONFIG=CONFIG, EFFECTS=EFFECTS).items():
        out = out.replace(f"__{key}__", json.dumps(value, ensure_ascii=False))
    return out


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Objetos especiales que ayudan al jugador.",
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
        "header": {"name": ADDON_NAME, "description": "Texturas, modelos y animaciones de los objetos de ayuda.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


# ---------------------------------------------------------------- preview
def iso_block(side, top, size, right_side=None):
    """Simple isometric cube from a side (left face), a top and an optional right face."""
    s = size
    out = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    big_top = top.resize((s, s), Image.NEAREST).rotate(45, expand=True, resample=Image.NEAREST)
    big_top = big_top.resize((s * 2, s), Image.NEAREST)
    left = side.resize((s, s), Image.NEAREST).transform(
        (s, s * 3 // 2), Image.AFFINE, (1, 0, 0, -0.5, 1, 0), Image.NEAREST)
    right = shade_img((right_side or side).resize((s, s), Image.NEAREST), 0.75).transform(
        (s, s * 3 // 2), Image.AFFINE, (1, 0, 0, 0.5, 1, -s / 2), Image.NEAREST)
    out.alpha_composite(left, (0, s // 2))
    out.alpha_composite(right, (s, s // 2))
    out.alpha_composite(big_top, (0, 0))
    return out


def shade_img(im, f):
    px = im.load()
    out = im.copy()
    po = out.load()
    for y in range(im.height):
        for x in range(im.width):
            po[x, y] = shade(px[x, y], f)
    return out


def skeleton_front(tex, scale):
    """Front view of the soul skeleton in its idle pose (arms straight)."""
    parts = [((0, 0, 8, 8, 8), (4, 0)), ((16, 16, 8, 12, 4), (4, 8)), ((40, 16, 2, 12, 2), (12, 8)),
             ((40, 16, 2, 12, 2), (2, 8)), ((0, 16, 2, 12, 2), (5, 20)), ((0, 16, 2, 12, 2), (9, 20))]
    out = Image.new("RGBA", (16 * scale, 34 * scale), (0, 0, 0, 0))
    for (u, v, w, h, d), (x, y) in parts:
        fx, fy, fw, fh = box_faces(u, v, w, h, d)["front"]
        face = tex.crop((fx, fy, fx + fw, fy + fh)).resize((fw * scale, fh * scale), Image.NEAREST)
        out.alpha_composite(face, (x * scale, y * scale))
    fx, fy, fw, fh = box_faces(48, 16, 2, 14, 1)["front"]
    blade = tex.crop((fx, fy, fx + fw, fy + fh)).resize((fw * scale, fh * scale), Image.NEAREST)
    out.alpha_composite(blade, (12 * scale, 20 * scale))
    return out


def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    # textures
    tex = dict(
        relay=relay_icon(), burst=burst_icon(), gem=burst_model_texture(), skull=skull_texture(),
        skeleton=skeleton_texture())
    tex["beacon_side"], tex["beacon_top"] = beacon_textures()
    paths = {
        "relay": "textures/items/ayuda/carga_de_relevo", "burst": "textures/items/ayuda/estallido",
        "gem": "textures/entity/ayuda/estallido", "skeleton": "textures/entity/ayuda/esqueleto_de_alma",
        "skull": "textures/blocks/ayuda/cabeza_energica", "beacon_side": "textures/blocks/ayuda/faro_lado",
        "beacon_top": "textures/blocks/ayuda/faro_arriba"}
    for k, p in paths.items():
        full = os.path.join(RP, p + ".png")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        tex[k].save(full)
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "ayuda", "texture_name": "atlas.items", "texture_data": {
            "ayuda_carga_de_relevo": {"textures": paths["relay"]},
            "ayuda_estallido": {"textures": paths["burst"]}}})
    write(os.path.join(RP, "textures/terrain_texture.json"), {
        "resource_pack_name": "ayuda", "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4,
        "texture_data": {
            "ayuda_cabeza_energica": {"textures": paths["skull"]},
            "ayuda_faro_lado": {"textures": paths["beacon_side"]},
            "ayuda_faro_arriba": {"textures": paths["beacon_top"]}}})
    write(os.path.join(RP, "blocks.json"), {
        "format_version": "1.1.0", SKULL: {"sound": "bone_block"}, BEACON: {"sound": "froglight"}})

    # resource pack
    write(os.path.join(RP, "models/entity/esqueleto_de_alma.geo.json"), skeleton_geo())
    write(os.path.join(RP, "models/entity/estallido.geo.json"), burst_geo())
    write(os.path.join(RP, "models/blocks/cabeza_esqueleto_energica.geo.json"), skull_geo())
    write(os.path.join(RP, "animations/esqueleto_de_alma.animation.json"), skeleton_animations())
    write(os.path.join(RP, "animations/estallido.animation.json"), burst_animations())
    write(os.path.join(RP, "animation_controllers/esqueleto_de_alma.animation_controllers.json"),
          skeleton_controllers())
    write(os.path.join(RP, "entity/esqueleto_de_alma.entity.json"), skeleton_client())
    write(os.path.join(RP, "attachables/estallido.attachable.json"), burst_attachable())
    write(os.path.join(RP, "render_controllers/ayuda.render_controllers.json"), render_controllers())
    write(os.path.join(RP, "sounds.json"), sounds())
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    # behavior pack
    for name, data in items().items():
        write(os.path.join(BP, f"items/{name}.json"), data)
    for name, data in blocks().items():
        write(os.path.join(BP, f"blocks/{name}.json"), data)
    write(os.path.join(BP, "entities/esqueleto_de_alma.json"), skeleton_entity())
    write(os.path.join(BP, "scripts/main.js"), script())
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon: the four items on a dark background
    icon = Image.new("RGBA", (128, 128), (28, 34, 46, 255))
    icon.alpha_composite(tex["relay"].resize((56, 56), Image.NEAREST), (4, 4))
    icon.alpha_composite(tex["burst"].resize((56, 56), Image.NEAREST), (68, 4))
    skull_side = tex["skull"].crop((8, 8, 16, 16))
    skull_top = tex["skull"].crop((8, 0, 16, 8))
    skull_right = tex["skull"].crop((0, 8, 8, 16))
    icon.alpha_composite(iso_block(skull_side, skull_top, 28, skull_right), (4, 68))
    icon.alpha_composite(iso_block(tex["beacon_side"], tex["beacon_top"], 28), (68, 68))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "HelperItems.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev:
        sheet = Image.new("RGBA", (720, 300), (28, 34, 46, 255))
        d = ImageDraw.Draw(sheet)
        cells = [("Carga de Relevo", tex["relay"].resize((128, 128), Image.NEAREST)),
                 ("Estallido", tex["burst"].resize((128, 128), Image.NEAREST)),
                 ("Cabeza Energica", iso_block(skull_side, skull_top, 64, skull_right)),
                 ("Faro Indeseado", iso_block(tex["beacon_side"], tex["beacon_top"], 64))]
        for i, (name, im) in enumerate(cells):
            x = 10 + i * 140
            sheet.alpha_composite(im, (x + (128 - im.width) // 2, 40 + (128 - im.height) // 2))
            d.text((x + 64, 190), name, fill=(230, 240, 255, 255), anchor="mm")
        sk = skeleton_front(tex["skeleton"], 8)
        sheet.alpha_composite(sk, (580, 10))
        d.text((644, 290), "Esqueleto de Alma", fill=hx(SOUL["bone"]), anchor="mm")
        sheet.save(os.path.join(ROOT, "docs", "helper_items_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
