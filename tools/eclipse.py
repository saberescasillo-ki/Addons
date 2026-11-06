"""Builds "El Eclipse", a bullet-hell boss: a figure like a player, completely black,
with a halo, a cape and orbiting shards. Its scripts are in tools/eclipse/scripts.

    python3 tools/eclipse.py            # Eclipse_BP, Eclipse_RP and dist/Eclipse.mcaddon
    python3 tools/eclipse.py --preview  # also docs/eclipse_arena.png

Fight: touch the Altar of the Eclipse (in its arena: /function eclipse/arena or
/place structure eclipse:arena); /scriptevent eclipse:dificultad facil|normal|dificil.
"""
import json
import math
import os
import random
import shutil
import sys
import uuid
import zipfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "eclipse"))
import arena  # noqa: E402

NAME = "Eclipse"
BP = os.path.join(ROOT, f"{NAME}_BP")
RP = os.path.join(ROOT, f"{NAME}_RP")
DIST = os.path.join(ROOT, "dist")
SCRIPTS = os.path.join(HERE, "eclipse", "scripts")
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 90]
BOSS, REMNANT, ALTAR = "eclipse:eclipse", "eclipse:remnant", "eclipse:altar"
HEALTH = 500


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/saberescasillo-ki/addons/{NAME}/{name}"))


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# --- manifests ----------------------------------------------------------------------------
def manifests():
    dump(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "El Eclipse (BP)", "description": "Jefe bullet hell: El Eclipse", "uuid": uid("bp"),
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "data", "uuid": uid("bp-data"), "version": VERSION},
                    {"type": "script", "language": "javascript", "entry": "scripts/main.js", "uuid": uid("bp-script"),
                     "version": VERSION}],
        "dependencies": [{"uuid": uid("rp"), "version": VERSION},
                         {"module_name": "@minecraft/server", "version": "2.0.0"}]})
    dump(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "El Eclipse (RP)", "description": "Jefe bullet hell: El Eclipse", "uuid": uid("rp"),
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": uid("rp-res"), "version": VERSION}],
        "dependencies": [{"uuid": uid("bp"), "version": VERSION}]})


# --- textures -------------------------------------------------------------------------------
def body_texture(path):
    """Completely black, with a barely visible grain so the shape still reads."""
    rng = random.Random(3)
    img = Image.new("RGBA", (64, 64))
    px = img.load()
    for y in range(64):
        for x in range(64):
            v = rng.randint(2, 9)
            px[x, y] = (v, v, v + 2, 255)
    img.save(path)


def particle_atlas(path):
    """64x32: a soft glowing dot (0-31), a four-pointed star (32-47), a spark (48-63)."""
    img = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    px = img.load()
    for y in range(32):
        for x in range(32):
            d = math.hypot(x - 15.5, y - 15.5) / 16
            if d < 1:
                core = 1 if d < 0.38 else max(0.0, 1 - (d - 0.38) / 0.62) ** 1.6
                px[x, y] = (255, 255, 255, int(255 * core))
    for y in range(16):
        for x in range(16):
            dx, dy = abs(x - 7.5), abs(y - 7.5)
            star = max(0.0, 1 - (dx * dy) / 6 - math.hypot(dx, dy) / 9)
            if star > 0.05:
                px[32 + x, y] = (255, 255, 255, int(255 * min(1, star * 1.5)))
            d = math.hypot(dx, dy) / 8
            if d < 1:
                px[48 + x, y] = (255, 255, 255, int(255 * (1 - d) ** 2))
    img.save(path)


def altar_textures(folder):
    def base(active):
        img = Image.new("RGBA", (16, 16))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 15, 15], fill=(14, 12, 20, 255))
        d.rectangle([0, 0, 15, 15], outline=(60, 50, 80, 255))
        d.rectangle([1, 1, 14, 14], outline=(30, 26, 40, 255))
        return img, d

    for active in (False, True):
        glow = (255, 214, 110, 255) if active else (190, 180, 210, 255)
        top, d = base(active)
        d.ellipse([3, 3, 12, 12], outline=glow)                 # the corona
        d.ellipse([5, 5, 10, 10], fill=(0, 0, 0, 255))          # the dark sun
        for p in ((7, 1), (8, 1), (7, 14), (8, 14), (1, 7), (1, 8), (14, 7), (14, 8)):
            d.point(p, fill=glow)
        top.save(os.path.join(folder, f"eclipse_altar_top{'_active' if active else ''}.png"))
        side, d = base(active)
        for x in range(3, 13, 3):
            d.line([x, 4, x + 1, 11], fill=(40, 34, 56, 255))
        d.line([2, 2, 13, 2], fill=glow)
        d.point((7, 8), fill=glow)
        d.point((8, 8), fill=glow)
        side.save(os.path.join(folder, f"eclipse_altar_side{'_active' if active else ''}.png"))


# --- geometry -------------------------------------------------------------------------------
def geometry():
    def cube(o, s, uv, **kw):
        return {"origin": o, "size": s, "uv": uv, **kw}

    halo = []
    for k in range(16):
        a = 2 * math.pi * k / 16
        halo.append(cube([round(5.2 * math.cos(a) - 0.7, 3), 35, round(5.2 * math.sin(a) - 0.7, 3)], [1.4, 0.7, 1.4], [56, 0]))
    shards = []
    for k in range(3):
        a = 2 * math.pi * k / 3
        shards.append(cube([round(13 * math.cos(a) - 1, 3), 17 + 3 * k, round(13 * math.sin(a) - 1, 3)], [2, 3, 2], [56, 4]))
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "waist", "parent": "root", "pivot": [0, 12, 0]},
        {"name": "body", "parent": "waist", "pivot": [0, 12, 0], "cubes": [cube([-4, 12, -2], [8, 12, 4], [16, 16])]},
        {"name": "head", "parent": "body", "pivot": [0, 24, 0], "cubes": [
            cube([-4, 24, -4], [8, 8, 8], [0, 0]), cube([-4, 24, -4], [8, 8, 8], [32, 0], inflate=0.5)]},
        {"name": "halo", "parent": "head", "pivot": [0, 35.3, 0], "cubes": halo},
        {"name": "rightArm", "parent": "body", "pivot": [-5, 22, 0], "cubes": [cube([-8, 12, -2], [4, 12, 4], [40, 16])]},
        {"name": "leftArm", "parent": "body", "pivot": [5, 22, 0], "cubes": [cube([4, 12, -2], [4, 12, 4], [32, 48])]},
        {"name": "rightLeg", "parent": "waist", "pivot": [-1.9, 12, 0], "cubes": [cube([-3.9, 0, -2], [4, 12, 4], [0, 16])]},
        {"name": "leftLeg", "parent": "waist", "pivot": [1.9, 12, 0], "cubes": [cube([-0.1, 0, -2], [4, 12, 4], [16, 48])]},
        {"name": "cape", "parent": "body", "pivot": [0, 24, 2], "cubes": [cube([-5, 5, 2], [10, 19, 1], [0, 32])]},
        {"name": "shards", "parent": "root", "pivot": [0, 18, 0], "cubes": shards},
    ]
    dump(os.path.join(RP, "models", "entity", "eclipse.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.eclipse", "texture_width": 64, "texture_height": 64,
                            "visible_bounds_width": 4, "visible_bounds_height": 5, "visible_bounds_offset": [0, 1.5, 0]},
            "bones": bones}]})


# --- animations -----------------------------------------------------------------------------
def tremble(base, k=3, f=900):
    return f"{base} + math.sin(q.life_time * {f}) * {k}"


def bob(base=1, k=1.2):
    return f"{base} + math.sin(q.life_time * 90) * {k}"


def anim(length, bones, loop=True):
    a = {"loop": loop if loop is True else "hold_on_last_frame", "bones": bones}
    if length:
        a["animation_length"] = length
    return a


def mirror(rot):
    """Right arm/leg rotation -> left (y and z flip)."""
    def neg(v):
        if isinstance(v, str):
            return f"-({v})"
        return -v
    if isinstance(rot, dict):
        return {k: mirror(v) for k, v in rot.items()}
    return [rot[0], neg(rot[1]), neg(rot[2])]


def arms(right, left=None):
    return {"rightArm": {"rotation": right}, "leftArm": {"rotation": left if left is not None else mirror(right)}}


def legs(right, left=None):
    return {"rightLeg": {"rotation": right}, "leftLeg": {"rotation": left if left is not None else mirror(right)}}


def animations():
    A = {}
    t = "q.life_time"
    A["idle"] = anim(4, {
        "root": {"position": [0, bob(), 0]},
        "body": {"rotation": [f"4 + math.sin({t} * 90) * 2", 0, 0]},
        **arms([f"-8 + math.sin({t} * 90 + 40) * 5", 0, f"14 + math.sin({t} * 70) * 3"]),
        "rightLeg": {"rotation": [f"16 + math.sin({t} * 90 + 80) * 6", 0, 4]},
        "leftLeg": {"rotation": [f"6 + math.sin({t} * 90 + 120) * 6", 0, -4]}})
    A["always"] = anim(None, {
        "halo": {"rotation": [0, f"{t} * 70", 0], "position": [0, f"math.sin({t} * 120) * 0.5", 0]},
        "shards": {"rotation": [0, f"-{t} * 110", 0], "position": [0, f"math.sin({t} * 80) * 2", 0]},
        "cape": {"rotation": [f"12 + math.sin({t} * 130) * 7", 0, f"math.sin({t} * 60) * 3"]}})
    A["point"] = anim(0.45, {
        "root": {"position": [0, bob(1.5, 0.8), 0]},
        "body": {"rotation": [0, -16, 0]},
        "rightArm": {"rotation": {"0.0": [-95, -8, 0], "0.12": [-76, -8, 0], "0.45": [-95, -8, 0]}},
        "leftArm": {"rotation": [-25, 0, -28]},
        **legs([14, 0, 5], [4, 0, -5])})
    A["raise"] = anim(1, {
        "root": {"position": [0, bob(3, 1), 0]},
        "body": {"rotation": [-12, 0, 0]}, "head": {"rotation": [-22, 0, 0]},
        **arms([tremble(-170, 3, 400), 0, 12]),
        **legs([6, 0, 2])})
    A["spin"] = anim(0.5, {
        "root": {"rotation": [0, "q.anim_time * -720", 0], "position": [0, 2, 0]},
        "body": {"rotation": [-5, 0, 0]},
        **arms([0, 0, 95]), **legs([0, 0, 6])})
    A["cross"] = anim(1.5, {
        "root": {"position": [0, bob(2.5, 1), 0]},
        "head": {"rotation": [-14, 0, 0]},
        **arms([0, 0, f"92 + math.sin({t} * 200) * 3"]), **legs([4, 0, 1])})
    A["summon"] = anim(1.2, {
        "root": {"position": [0, 2, 0]},
        "body": {"rotation": [-6, 0, 0]}, "head": {"rotation": [-8, 0, 0]},
        **arms({"0.0": [-100, 0, 40], "0.6": [-100, 0, 8], "1.2": [-100, 0, 40]}), **legs([8, 0, 3])})
    A["charge"] = anim(1, {
        "root": {"position": [0, tremble(2, 0.4), 0]},
        "body": {"rotation": [22, 0, 0]}, "head": {"rotation": [12, 0, 0]},
        **arms([-75, 0, -35]), **legs([-50, 0, 6], [-60, 0, -6])})
    A["release"] = anim(0.6, {
        "root": {"position": {"0.0": [0, 2, 0], "0.1": [0, 4, 0], "0.6": [0, 3, 0]}},
        "body": {"rotation": {"0.0": [22, 0, 0], "0.1": [-25, 0, 0], "0.6": [-18, 0, 0]}},
        "head": {"rotation": {"0.0": [12, 0, 0], "0.1": [-30, 0, 0], "0.6": [-20, 0, 0]}},
        **arms({"0.0": [-75, 0, -35], "0.1": [-30, 0, 120], "0.6": [-20, 0, 105]}),
        **legs({"0.0": [-50, 0, 6], "0.1": [10, 0, 25], "0.6": [8, 0, 20]})}, loop=False)
    A["vanish"] = anim(0.4, {
        "root": {"rotation": {"0.0": [0, 0, 0], "0.4": [0, 540, 0]},
                 "scale": {"0.0": [1, 1, 1], "0.15": [1.15, 1.15, 1.15], "0.4": [0.01, 0.01, 0.01]}},
        **arms([0, 0, 60])}, loop=False)
    A["appear"] = anim(0.5, {
        "root": {"rotation": {"0.0": [0, -360, 0], "0.5": [0, 0, 0]},
                 "scale": {"0.0": [0.01, 0.01, 0.01], "0.3": [1.2, 1.2, 1.2], "0.5": [1, 1, 1]}},
        **arms({"0.0": [0, 0, 90], "0.5": [-8, 0, 14]})}, loop=False)
    A["phase"] = anim(3.5, {
        "root": {"position": {"0.0": [0, 0, 0], "1.0": [0, 10, 0], "3.5": [0, 10, 0]},
                 "rotation": [tremble(0, 1.5, 1300), 0, tremble(0, 1.5, 1100)]},
        "body": {"rotation": {"0.0": [0, 0, 0], "1.0": [-15, 0, 0], "3.1": [5, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "1.0": [-35, 0, 0], "3.1": [-10, 0, 0]}},
        **arms({"0.0": [0, 0, 15], "1.0": [-140, 0, 50], "2.8": [-150, 0, 45], "3.1": [-30, 0, 110], "3.5": [-20, 0, 100]}),
        **legs({"0.0": [10, 0, 2], "1.0": [5, 0, 8], "3.1": [10, 0, 22]})}, loop=False)
    A["ult_charge"] = anim(2, {
        "root": {"position": [0, tremble(0, 0.3, 1000), 0]},
        "body": {"rotation": [-10, 0, 0]}, "head": {"rotation": [-30, 0, 0]},
        "halo": {"scale": [f"1.8 + math.sin({t} * 300) * 0.15"] * 3},
        **arms([tremble(-175, 2), 0, -8]), **legs([5, 0, 3])})
    A["ult_release"] = anim(1, {
        "root": {"position": {"0.0": [0, 0, 0], "0.15": [0, -2, 0], "1.0": [0, 0, 0]}},
        "body": {"rotation": {"0.0": [-10, 0, 0], "0.15": [25, 0, 0], "1.0": [15, 0, 0]}},
        "head": {"rotation": {"0.0": [-30, 0, 0], "0.15": [20, 0, 0]}},
        "halo": {"scale": {"0.0": [1.8, 1.8, 1.8], "0.2": [2.6, 2.6, 2.6], "1.0": [1, 1, 1]}},
        **arms({"0.0": [-175, 0, -8], "0.15": [-20, 0, 70], "1.0": [-15, 0, 60]})}, loop=False)
    A["exhausted"] = anim(3, {
        "root": {"position": [0, -5, 0]},
        "body": {"rotation": [f"26 + math.sin({t} * 60) * 3", 0, 0]}, "head": {"rotation": [35, 0, 0]},
        **arms([10, 0, 8]), **legs([-80, 0, 4], [12, 0, -2])})
    A["slam"] = anim(0.8, {
        "root": {"position": {"0.0": [0, 1, 0], "0.4": [0, 8, 0], "0.55": [0, -4, 0], "0.8": [0, -3, 0]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.4": [-15, 0, 0], "0.55": [30, 0, 0], "0.8": [25, 0, 0]}},
        **arms({"0.0": [0, 0, 10], "0.4": [-175, 0, 10], "0.55": [-30, 0, 10], "0.8": [-25, 0, 10]}),
        **legs({"0.0": [10, 0, 3], "0.55": [-40, 0, 6], "0.8": [-35, 0, 6]})}, loop=False)
    A["death"] = anim(3.6, {
        "root": {"position": {"0.0": [0, 0, 0], "3.0": [0, 24, 0]},
                 "rotation": ["math.sin(q.life_time * 1500) * q.anim_time * 1.5", 0,
                              "math.cos(q.life_time * 1400) * q.anim_time * 1.5"],
                 "scale": {"0.0": [1, 1, 1], "3.0": [1, 1, 1], "3.4": [1.3, 1.3, 1.3], "3.6": [0.01, 0.01, 0.01]}},
        "body": {"rotation": {"0.0": [0, 0, 0], "0.8": [-20, 0, 0]}},
        "head": {"rotation": {"0.0": [0, 0, 0], "0.8": [-40, 0, 0]}},
        "halo": {"scale": {"0.0": [1, 1, 1], "3.0": [2.2, 2.2, 2.2]}},
        **arms({"0.0": [0, 0, 15], "0.8": [-30, 0, 110], "3.0": [-40, 0, 120]}),
        **legs({"0.0": [10, 0, 2], "0.8": [5, 0, 14]})}, loop=False)
    dump(os.path.join(RP, "animations", "eclipse.animation.json"), {
        "format_version": "1.8.0",
        "animations": {f"animation.eclipse.{k}": v for k, v in A.items()}})
    return list(A)


# the order of eclipse:anim values (tools/eclipse/scripts/attacks.js ANIM)
POSES = ["idle", "point", "raise", "spin", "cross", "summon", "charge", "release", "vanish", "appear", "phase",
         "ult_charge", "ult_release", "exhausted", "slam"]


def controllers():
    states = {"idle": {"animations": ["idle"], "blend_transition": 0.15,
                       "transitions": [{p: f"q.property('eclipse:anim') == {i}"} for i, p in enumerate(POSES) if i]}}
    for i, p in enumerate(POSES):
        if i:
            states[p] = {"animations": [p], "blend_transition": 0.12,
                         "transitions": [{"idle": f"q.property('eclipse:anim') != {i}"}]}
    visible = "!q.property('eclipse:hidden') && q.is_alive"
    aura = {"off": {"transitions": [{f"p{n}": f"{visible} && q.property('eclipse:phase') == {n}"} for n in (1, 2, 3)]}}
    for n in (1, 2, 3):
        aura[f"p{n}"] = {"particle_effects": [{"effect": f"aura{n}"}],
                         "transitions": [{"off": f"!({visible}) || q.property('eclipse:phase') != {n}"}]}
    dump(os.path.join(RP, "animation_controllers", "eclipse.animation_controllers.json"), {
        "format_version": "1.10.0",
        "animation_controllers": {
            "controller.animation.eclipse.pose": {"initial_state": "idle", "states": states},
            "controller.animation.eclipse.aura": {"initial_state": "off", "states": aura}}})


# --- particles ----------------------------------------------------------------------------------
TEX = "textures/eclipse/particle/atlas"
GLOW = {"texture_width": 64, "texture_height": 32, "uv": [0, 0], "uv_size": [32, 32]}
STAR = {"texture_width": 64, "texture_height": 32, "uv": [32, 0], "uv_size": [16, 16]}
SPARK = {"texture_width": 64, "texture_height": 32, "uv": [48, 0], "uv_size": [16, 16]}
FADE = "v.color.a * math.clamp((1 - v.particle_age / v.particle_lifetime) * 4, 0, 1)"
TINT = {"color": ["v.color.r", "v.color.g", "v.color.b", FADE]}


def particle(name, components, material="particles_blend"):
    dump(os.path.join(RP, "particles", f"{name}.particle.json"), {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {"identifier": f"eclipse:{name}",
                            "basic_render_parameters": {"material": material, "texture": TEX}},
            "components": components}})


def once(n):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": 0.05}}


def board(size, uv=GLOW):
    return {"size": [size, size], "facing_camera_mode": "lookat_xyz", "uv": uv}


def particles():
    particle("orb", {
        **once(1),
        "minecraft:emitter_shape_point": {"direction": ["v.dir.direction_x", "v.dir.direction_y", "v.dir.direction_z"]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "v.life"},
        "minecraft:particle_initial_speed": "v.dir.speed",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": ["v.acc.x", "v.acc.y", "v.acc.z"]},
        "minecraft:particle_appearance_billboard": board("v.size"),
        "minecraft:particle_appearance_tinting": {"color": ["v.color.r", "v.color.g", "v.color.b", "v.color.a"]}})
    for name, surface, alpha in (("ring", True, 1), ("disc", False, 0.5)):
        particle(name, {
            **once("v.count"),
            "minecraft:emitter_shape_disc": {"radius": "v.radius", "surface_only": surface, "plane_normal": [0, 1, 0],
                                             "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "v.life"},
            "minecraft:particle_initial_speed": "v.speed" if surface else 0,
            "minecraft:particle_motion_dynamic": {},
            "minecraft:particle_appearance_billboard": board("v.size"),
            "minecraft:particle_appearance_tinting": {"color": ["v.color.r", "v.color.g", "v.color.b", f"({FADE}) * {alpha}"]}})
    particle("dot", {
        **once(1), "minecraft:emitter_shape_point": {},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "v.life"},
        "minecraft:particle_appearance_billboard": board("v.size"),
        "minecraft:particle_appearance_tinting": TINT})
    particle("beam", {
        **once("math.min(80, v.height * 2.5)"),
        "minecraft:emitter_shape_box": {"offset": [0, "v.height / 2", 0], "half_dimensions": [0.18, "v.height / 2", 0.18],
                                        "direction": [0, -1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.25, 0.5)"},
        "minecraft:particle_initial_speed": "math.random(2, 6)",
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_appearance_billboard": board("0.45 - 0.4 * v.particle_age / v.particle_lifetime"),
        "minecraft:particle_appearance_tinting": {"color": [
            "math.lerp(1, v.color.r, v.particle_age / v.particle_lifetime)",
            "math.lerp(1, v.color.g, v.particle_age / v.particle_lifetime)",
            "math.lerp(1, v.color.b, v.particle_age / v.particle_lifetime)", 1]}}, "particles_add")
    particle("burst", {
        **once("v.count"),
        "minecraft:emitter_shape_sphere": {"radius": 0.3, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.4, 0.8)"},
        "minecraft:particle_initial_speed": "v.speed * math.random(0.4, 1)",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 2.5},
        "minecraft:particle_appearance_billboard": board("0.14 - 0.12 * v.particle_age / v.particle_lifetime", SPARK),
        "minecraft:particle_appearance_tinting": {"color": ["v.color.r", "v.color.g", "v.color.b", 1]}}, "particles_add")
    particle("charge", {
        **once("v.count"),
        "minecraft:emitter_shape_sphere": {"radius": "v.radius", "surface_only": True, "direction": "inwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "v.life"},
        "minecraft:particle_initial_speed": "v.speed",
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_appearance_billboard": board("0.08 + 0.12 * v.particle_age / v.particle_lifetime", SPARK),
        "minecraft:particle_appearance_tinting": {"color": ["v.color.r", "v.color.g", "v.color.b", 1]}}, "particles_add")
    particle("pillar", {
        **once("v.count"),
        "minecraft:emitter_shape_box": {"offset": [0, "v.height / 2", 0], "half_dimensions": [0.45, "v.height / 2", 0.45],
                                        "direction": [0, 1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "v.life"},
        "minecraft:particle_initial_speed": 1,
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_appearance_billboard": board("0.13", STAR),
        "minecraft:particle_appearance_tinting": TINT})
    for n, rgb, rate in ((1, (1, 0.92, 0.7), 8), (2, (0.72, 0.5, 1), 10), (3, (1, 0.3, 0.38), 14)):
        dump(os.path.join(RP, "particles", f"aura{n}.particle.json"), {
            "format_version": "1.10.0",
            "particle_effect": {
                "description": {"identifier": f"eclipse:aura{n}",
                                "basic_render_parameters": {"material": "particles_add", "texture": TEX}},
                "components": {
                    "minecraft:emitter_rate_steady": {"spawn_rate": rate, "max_particles": rate * 3},
                    "minecraft:emitter_lifetime_looping": {"active_time": 1},
                    "minecraft:emitter_shape_box": {"offset": [0, 1.2, 0], "half_dimensions": [0.5, 1.1, 0.5],
                                                    "direction": [0, 1, 0]},
                    "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(1, 1.6)"},
                    "minecraft:particle_initial_speed": 0.35,
                    "minecraft:particle_motion_dynamic": {},
                    "minecraft:particle_appearance_billboard": board(
                        "0.1 * math.sin(v.particle_age / v.particle_lifetime * 180)", STAR),
                    "minecraft:particle_appearance_tinting": {"color": [*rgb, 1]}}}})


# --- entities -------------------------------------------------------------------------------------
def entities():
    props = {"eclipse:anim": {"type": "int", "range": [0, 20], "default": 0, "client_sync": True},
             "eclipse:phase": {"type": "int", "range": [1, 3], "default": 1, "client_sync": True},
             "eclipse:hidden": {"type": "bool", "default": False, "client_sync": True},
             "eclipse:shield": {"type": "bool", "default": False, "client_sync": True}}
    no = [{"cause": c, "deals_damage": "no"} for c in ("fall", "suffocation", "lightning", "fire", "fire_tick", "lava",
                                                      "drowning", "fly_into_wall", "entity_explosion", "block_explosion")]
    dump(os.path.join(BP, "entities", "eclipse.json"), {
        "format_version": "1.21.50",
        "minecraft:entity": {
            "description": {"identifier": BOSS, "is_spawnable": True, "is_summonable": True, "properties": props},
            "components": {
                "minecraft:type_family": {"family": ["eclipse", "boss", "monster", "mob"]},
                "minecraft:health": {"value": HEALTH, "max": HEALTH},
                "minecraft:boss": {"hud_range": 64, "should_darken_sky": True},
                "minecraft:collision_box": {"width": 0.7, "height": 2.0},
                "minecraft:physics": {"has_gravity": False, "has_collision": True},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:knockback_resistance": {"value": 1},
                "minecraft:fire_immune": {},
                "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
                "minecraft:damage_sensor": {"triggers": [
                    {"on_damage": {"filters": {"any_of": [
                        {"test": "bool_property", "domain": "eclipse:hidden"},
                        {"test": "bool_property", "domain": "eclipse:shield"}]}}, "deals_damage": "no"}, *no]},
                "minecraft:loot": {"table": "loot_tables/empty.json"},
                "minecraft:persistent": {},
                "minecraft:nameable": {"always_show": False}}}})
    dump(os.path.join(BP, "entities", "remnant.json"), {
        "format_version": "1.21.50",
        "minecraft:entity": {
            "description": {"identifier": REMNANT, "is_spawnable": False, "is_summonable": True},
            "components": {
                "minecraft:type_family": {"family": ["eclipse", "inanimate"]},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:collision_box": {"width": 0.1, "height": 0.1},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                "minecraft:loot": {"table": "loot_tables/empty.json"}}}})
    common = {"materials": {"default": "entity_alphatest"},
              "textures": {"default": "textures/eclipse/entity/eclipse"},
              "geometry": {"default": "geometry.eclipse"}}
    poses = {p: f"animation.eclipse.{p}" for p in POSES}
    dump(os.path.join(RP, "entity", "eclipse.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": BOSS, **common,
            "animations": {**poses, "always": "animation.eclipse.always", "look": "animation.common.look_at_target",
                           "pose": "controller.animation.eclipse.pose", "aura": "controller.animation.eclipse.aura"},
            "particle_effects": {f"aura{n}": f"eclipse:aura{n}" for n in (1, 2, 3)},
            "scripts": {"animate": ["pose", "always", "look", "aura"]},
            "render_controllers": ["controller.render.eclipse"],
            "spawn_egg": {"base_color": "#050507", "overlay_color": "#ffd46e"}}}})
    dump(os.path.join(RP, "entity", "remnant.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": REMNANT, **common,
            "animations": {"death": "animation.eclipse.death", "always": "animation.eclipse.always"},
            "scripts": {"animate": ["death", "always"]},
            "render_controllers": ["controller.render.eclipse_remnant"]}}})
    rc = {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]}
    dump(os.path.join(RP, "render_controllers", "eclipse.render_controllers.json"), {
        "format_version": "1.8.0",
        "render_controllers": {
            "controller.render.eclipse": {**rc, "part_visibility": [{"*": "!q.property('eclipse:hidden') && q.is_alive"}]},
            "controller.render.eclipse_remnant": rc}})


# --- the altar, loot, recipe, functions, arena ----------------------------------------------------
def altar():
    def mats(active):
        s = "_active" if active else ""
        return {"*": {"texture": f"eclipse_altar_side{s}", "render_method": "opaque"},
                "up": {"texture": f"eclipse_altar_top{s}", "render_method": "opaque"}}
    dump(os.path.join(BP, "blocks", "altar.json"), {
        "format_version": "1.21.80",
        "minecraft:block": {
            "description": {"identifier": ALTAR, "menu_category": {"category": "items"},
                            "states": {"eclipse:active": [False, True]}},
            "components": {
                "minecraft:material_instances": mats(False),
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 4},
                "minecraft:destructible_by_explosion": {"explosion_resistance": 1200},
                "minecraft:light_emission": 7,
                "minecraft:map_color": "#141018",
                "minecraft:custom_components": ["eclipse:altar"]},
            "permutations": [{"condition": "q.block_state('eclipse:active')",
                              "components": {"minecraft:material_instances": mats(True), "minecraft:light_emission": 15}}]}})
    tex = os.path.join(RP, "textures", "eclipse", "blocks")
    os.makedirs(tex, exist_ok=True)
    altar_textures(tex)
    dump(os.path.join(RP, "textures", "terrain_texture.json"), {
        "resource_pack_name": "eclipse", "texture_name": "atlas.terrain",
        "texture_data": {n: {"textures": f"textures/eclipse/blocks/{n}"} for n in (
            "eclipse_altar_top", "eclipse_altar_side", "eclipse_altar_top_active", "eclipse_altar_side_active")}})
    dump(os.path.join(RP, "blocks.json"), {"format_version": "1.21.40", ALTAR: {"sound": "stone"}})
    dump(os.path.join(BP, "recipes", "altar.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "eclipse:altar"},
            "tags": ["crafting_table"],
            "pattern": ["OAO", "AEA", "OAO"],
            "key": {"O": {"item": "minecraft:crying_obsidian"}, "A": {"item": "minecraft:amethyst_shard"},
                    "E": {"item": "minecraft:ender_eye"}},
            "unlock": [{"item": "minecraft:ender_eye"}],
            "result": {"item": ALTAR}}})


def loot():
    dump(os.path.join(BP, "loot_tables", "empty.json"), {"pools": []})
    item = lambda name, lo, hi, w=1: {"type": "item", "name": name, "weight": w,  # noqa: E731
                                       "functions": [{"function": "set_count", "count": {"min": lo, "max": hi}}]}
    dump(os.path.join(BP, "loot_tables", "eclipse", "boss.json"), {"pools": [
        {"rolls": 1, "entries": [item("minecraft:nether_star", 1, 1)]},
        {"rolls": 1, "entries": [item("minecraft:diamond", 4, 8)]},
        {"rolls": 1, "entries": [item("minecraft:amethyst_shard", 6, 14)]},
        {"rolls": 1, "entries": [item("minecraft:echo_shard", 1, 3)]},
        {"rolls": 1, "entries": [item("minecraft:experience_bottle", 4, 9)]},
        {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.5}],
         "entries": [item("minecraft:totem_of_undying", 1, 1)]},
        {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.25}],
         "entries": [item("minecraft:enchanted_golden_apple", 1, 1)]}]})


def structure(preview):
    os.makedirs(os.path.join(BP, "structures", "eclipse"), exist_ok=True)
    s = arena.build()
    s.save(os.path.join(BP, "structures", "eclipse", "arena.mcstructure"))
    half, F = arena.C, arena.FLOOR
    write(os.path.join(BP, "functions", "eclipse", "arena.mcfunction"),
          "# The Celestial Sanctuary: its floor ends up at your feet, the altar where you stand.\n"
          f"structure load eclipse:arena ~-{half} ~-{F} ~-{half}\n"
          "tellraw @s {\"rawtext\":[{\"text\":\"§8[Eclipse] §7El Santuario Celeste se alza. Toca el §fAltar del Eclipse§7 "
          "para invocarlo.\"}]}\n")
    write(os.path.join(BP, "functions", "eclipse", "altar.mcfunction"), "give @s eclipse:altar\n")
    # /place structure eclipse:arena: one piece, no structure set (never generates by itself)
    wg = os.path.join(BP, "worldgen")
    dump(os.path.join(wg, "processors", "arena.json"), {
        "format_version": "1.21.20",
        "minecraft:processor_list": {"description": {"identifier": "eclipse:arena"}, "processors": []}})
    dump(os.path.join(wg, "template_pools", "arena.json"), {
        "format_version": "1.21.20",
        "minecraft:template_pool": {"description": {"identifier": "eclipse:arena"}, "elements": [{
            "element": {"element_type": "minecraft:single_pool_element", "location": "eclipse/arena",
                        "processors": "eclipse:arena"}, "weight": 1}]}})
    dump(os.path.join(wg, "structures", "arena.json"), {
        "format_version": "1.21.20",
        "minecraft:jigsaw": {
            "description": {"identifier": "eclipse:arena"},
            "biome_filters": [{"test": "has_biome_tag", "operator": "!=", "value": "eclipse_never"}],
            "heightmap_projection": "world_surface",
            "max_depth": 1,
            "start_height": {"type": "constant", "value": {"absolute": -F}},
            "start_pool": "eclipse:arena",
            "step": "surface_structures",
            "terrain_adaptation": "beard_thin"}})
    if preview:
        import render_structure
        render_structure.render(s, os.path.join(ROOT, "docs", "eclipse_arena.png"), 3)


def lang():
    text = ("entity.eclipse:eclipse.name=El Eclipse\n"
            "entity.eclipse:remnant.name=Eco del Eclipse\n"
            "item.spawn_egg.entity.eclipse:eclipse.name=Generar El Eclipse\n"
            "tile.eclipse:altar.name=Altar del Eclipse\n"
            "pack.name=El Eclipse\npack.description=Jefe bullet hell: El Eclipse\n")
    for code in ("en_US", "es_ES", "es_MX"):
        write(os.path.join(RP, "texts", f"{code}.lang"), text)
    dump(os.path.join(RP, "texts", "languages.json"), ["en_US", "es_ES", "es_MX"])


def icon(path):
    img = Image.new("RGBA", (128, 128), (14, 10, 24, 255))
    d = ImageDraw.Draw(img)
    for r in range(56, 30, -2):
        c = int(255 * (1 - (r - 30) / 26) ** 2)
        d.ellipse([64 - r, 64 - r, 64 + r, 64 + r], outline=(c, int(c * 0.82), int(c * 0.45), 255), width=2)
    d.ellipse([34, 34, 94, 94], fill=(0, 0, 0, 255))
    img.save(path)


def build(preview=False):
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    manifests()
    shutil.copytree(SCRIPTS, os.path.join(BP, "scripts"))
    os.makedirs(os.path.join(RP, "textures", "eclipse", "entity"), exist_ok=True)
    os.makedirs(os.path.join(RP, "textures", "eclipse", "particle"), exist_ok=True)
    body_texture(os.path.join(RP, "textures", "eclipse", "entity", "eclipse.png"))
    particle_atlas(os.path.join(RP, "textures", "eclipse", "particle", "atlas.png"))
    geometry()
    animations()
    controllers()
    particles()
    entities()
    altar()
    loot()
    structure(preview)
    lang()
    icon(os.path.join(BP, "pack_icon.png"))
    shutil.copy(os.path.join(BP, "pack_icon.png"), os.path.join(RP, "pack_icon.png"))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"{NAME}.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, files in os.walk(pack):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, ROOT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    print(f"OK -> {os.path.relpath(out, ROOT)} ({os.path.getsize(out) / 1e3:.0f} KB)")


if __name__ == "__main__":
    build("--preview" in sys.argv)
