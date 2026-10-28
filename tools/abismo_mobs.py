"""The mutant mobs of "Mazmorras del Abismo": models, textures (mutant style,
see tools/mutant_style.py) and animations. Used by tools/abismo.py.

- Zombi Mutante: hunched brute with huge arms, smashes the ground.
- Arana Mutante: deepslate-plated spider, poisons and leaps.
- Creeper Mutante: four-legged creeper covered in sculk, blasts without dying.
- Esqueleto Mutante Abisal: the user's mutant skeleton model (with its bow and
  its animations) with a deepslate-and-sculk texture painted over its shading.
- Coloso Abisal (boss): a giant of deepslate with a sculk heart.
"""
import json
import os

from PIL import Image

from mutant_style import (Mat, Model, cracks, creeper_face, eyes, glow_core, hx, mouth, ramp, ribs, spots,
                          veins)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUTANT_SRC = os.path.join(ROOT, "sources", "mutant_skeleton")
NS = "abismo"


def brow(y):
    """A dark heavy brow above the eyes."""
    def fn(f):
        for x in range(1, f.w - 1):
            f.darken(x, y, 2)
    return fn


def g(name):
    return f"geometry.{NS}.{name}"


# ================================================================ Zombi Mutante
def zombie():
    m = Model(g("zombi_mutante"), bounds=(3.5, 3.5))
    skin = Mat("rot_skin", streaks=0.45)
    face = Mat("rot_skin", light=0.04).with_deco(front=[eyes(3, [1, 5], "#071a1c", core="#5ff2f2"),
                                                        mouth(6, 1, 7, teeth="#b9b49a")])
    jaw = Mat("rot_skin", light=-0.05).with_deco(front=[mouth(0, 1, 7, teeth="#b9b49a")])
    chest = Mat("rot_skin").with_deco(front=[ribs("deep_bone", 2), cracks(1)], back=[veins(count=2)])
    rag = Mat("rag", fringe=4, streaks=0.3)
    pants = Mat("rag", fringe=3, light=-0.1)
    shard = Mat("deepslate", contrast=1.2, light=0.12).with_deco(sides=[cracks(1, 2)])
    knuckle = Mat("rot_skin", light=-0.08, streaks=0.2).with_deco(bottom=[spots("deepslate", 0.3)])

    m.bone("root", [0, 0, 0])
    m.bone("waist", [0, 12, 0], "root")
    hips = m.bone("hips", [0, 12, 0], "waist")
    m.cube(hips, [-6, 11, -3], [12, 6, 7], skin)
    m.cube(hips, [-6, 10, -3], [12, 6, 7], pants, inflate=0.35)
    for side, x in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}leg", [4 * x, 12, 0], "waist")
        ox = -7 if x < 0 else 1
        m.cube(leg, [ox, 0, -3], [6, 12, 6], skin, mirror=x > 0)
        m.cube(leg, [ox, 5, -3], [6, 7, 6], pants, inflate=0.3, mirror=x > 0)
    body = m.bone("body", [0, 16, 1], "waist", rotation=[38, 0, 0])
    m.cube(body, [-8, 16, -4], [16, 14, 10], chest)
    m.cube(body, [-8, 19, -4], [16, 11, 10], rag, inflate=0.35)
    m.cube(body, [-11, 26, -3], [22, 7, 9], skin)  # the shoulders, wider than the chest
    for i, (o, rot) in enumerate((([-7, 29, 4], [-30, 0, -18]), ([3, 29, 4], [-35, 0, 15]),
                                  ([-2, 24, 6], [-25, 0, 0]), ([-9, 22, 5], [-20, 0, -30]),
                                  ([6, 21, 5], [-20, 0, 25]))):
        m.cube(body, o, [3, 7 - i % 2, 3], shard, pivot=[o[0] + 1.5, o[1], o[2] + 1.5], rotation=rot)
    head = m.bone("head", [0, 29, -3], "body", rotation=[-38, 0, 0])
    m.cube(head, [-4, 26, -10], [8, 8, 8], face)
    jawb = m.bone("jaw", [0, 27, -3], "head")
    m.cube(jawb, [-4, 24, -10], [8, 3, 8], jaw, inflate=0.1)
    for side, x in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}arm", [11 * x, 30, 0], "body", rotation=[-38, 0, 0])
        ox = -17 if x < 0 else 11
        m.cube(arm, [ox, 15, -3.5], [6, 16, 7], skin, mirror=x > 0)
        m.cube(arm, [ox, 22, -3.5], [6, 9, 7], rag, inflate=0.3, mirror=x > 0)
        fore = m.bone(f"{side}arm2", [14 * x, 16, 0], f"{side}arm", rotation=[-8, 0, 0])
        fx = -18.5 if x < 0 else 10.5
        m.cube(fore, [fx, -2, -4.5], [8, 18, 9], knuckle, mirror=x > 0)
        m.cube(fore, [fx + (1 if x < 0 else 5), 8, -2], [2, 5, 2], shard, pivot=[fx + 2, 8, -1],
               rotation=[0, 0, 25 * x])
    return m


def zombie_animations():
    ms = "math.min(1.0, query.modified_move_speed * 3.0)"
    d = "query.modified_distance_moved * 22.0"
    return {
        "zombi.move": {"loop": True, "bones": {
            "rightleg": {"rotation": [f"math.cos({d}) * 26.0 * {ms}", 0, 0]},
            "leftleg": {"rotation": [f"-math.cos({d}) * 26.0 * {ms}", 0, 0]},
            "rightarm": {"rotation": [f"-math.cos({d}) * 20.0 * {ms}", 0, 0]},
            "leftarm": {"rotation": [f"math.cos({d}) * 20.0 * {ms}", 0, 0]},
            "body": {"rotation": [0, f"math.sin({d}) * 6.0 * {ms}", f"math.sin({d}) * 4.0 * {ms}"]}}},
        "zombi.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(query.life_time * 80.0) * 2.0", 0, 0]},
            "rightarm": {"rotation": [0, 0, "math.sin(query.life_time * 60.0) * 2.0 + 3.0"]},
            "leftarm": {"rotation": [0, 0, "-math.sin(query.life_time * 60.0) * 2.0 - 3.0"]},
            "jaw": {"rotation": ["math.max(0.0, math.sin(query.life_time * 45.0)) * 8.0", 0, 0]}}},
        "zombi.look": {"loop": True, "bones": {
            "head": {"rotation": ["query.target_x_rotation * 0.6", "query.target_y_rotation * 0.6", 0]}}},
        "zombi.attack": {"loop": True, "bones": {
            "rightarm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 115.0", 0, 0]},
            "leftarm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 115.0", 0, 0]},
            "body": {"rotation": ["math.sin(variable.attack_time * 180.0) * 12.0", 0, 0]},
            "jaw": {"rotation": ["math.sin(variable.attack_time * 180.0) * 25.0", 0, 0]}}},
        "zombi.slam": {"animation_length": 1.2, "bones": {
            "rightarm": {"rotation": {"0.0": [0, 0, 0], "0.45": [-165, 0, -10], "0.7": [15, 0, 0], "1.2": [0, 0, 0]}},
            "leftarm": {"rotation": {"0.0": [0, 0, 0], "0.45": [-165, 0, 10], "0.7": [15, 0, 0], "1.2": [0, 0, 0]}},
            "body": {"rotation": {"0.0": [0, 0, 0], "0.45": [-22, 0, 0], "0.7": [28, 0, 0], "1.2": [0, 0, 0]}},
            "jaw": {"rotation": {"0.0": [0, 0, 0], "0.45": [30, 0, 0], "0.9": [30, 0, 0], "1.2": [0, 0, 0]}}},
            "sound_effects": {"0.7": {"effect": "slam"}}},
    }


# ================================================================ Arana Mutante
def spider():
    m = Model(g("arana_mutante"), bounds=(4.0, 2.5))
    shell = Mat("carapace", contrast=1.1).with_deco(top=[cracks(2), spots("sculk", 0.03)])
    plate = Mat("deepslate", contrast=1.2).with_deco(sides=[cracks(1)], top=[veins(count=1, length=4)])
    hair = Mat("carapace", streaks=0.3, light=0.06).with_deco(sides=[spots("spider_hair", 0.25)])
    head = Mat("carapace", light=0.05).with_deco(front=[
        eyes(2, [1, 7], "#8f1414", core="#ff5a3a"), eyes(4, [2, 6], "#8f1414", core="#ff5a3a"),
        eyes(2, [4], "#b51d1d", core="#ff7a4a")])
    fang = Mat("bone", contrast=0.6, light=-0.1)
    leg = Mat("carapace", streaks=0.5).with_deco(sides=[spots("spider_hair", 0.12)])
    m.bone("root", [0, 0, 0])
    body = m.bone("body", [0, 12, 0], "root")
    m.cube(body, [-6, 8, -6], [12, 9, 12], hair)
    m.cube(body, [-6, 14, -6], [12, 3, 12], shell, inflate=0.3)
    hd = m.bone("head", [0, 12, -6], "body")
    m.cube(hd, [-5, 7, -15], [10, 9, 9], head)
    for x in (-4, 2):
        m.cube(hd, [x, 3, -15], [2, 5, 2], fang, pivot=[x + 1, 7, -14], rotation=[-15, 0, 10 if x < 0 else -10])
    ab = m.bone("abdomen", [0, 13, 6], "body", rotation=[-12, 0, 0])
    m.cube(ab, [-8, 8, 6], [16, 13, 17], hair)
    m.cube(ab, [-7, 19, 7], [14, 3, 15], plate, inflate=0.2)
    m.cube(ab, [-6, 10, 23], [12, 9, 4], hair)
    for i, (x, z) in enumerate(((-4, 9), (2, 9), (-1, 14), (-5, 17), (3, 17))):
        m.cube(ab, [x, 21, z], [2, 4, 2], plate, pivot=[x + 1, 21, z + 1], rotation=[-25, 0, (i % 2 * 2 - 1) * 12])
    fans = (35, 12, -12, -35)
    for side, s in (("right", -1), ("left", 1)):
        for i, z in enumerate((-4, -1, 2, 5)):
            yaw = fans[i] * (-s)
            up = m.bone(f"leg{side}{i}", [6 * s, 12, z], "body", rotation=[0, yaw, -32 * s])
            ox = -20 if s < 0 else 6
            m.cube(up, [ox, 11, z - 1.5], [14, 3, 3], leg, mirror=s > 0)
            low = m.bone(f"leg{side}{i}b", [20 * s, 12, z], f"leg{side}{i}", rotation=[0, 0, 78 * s])
            lx = -36 if s < 0 else 20
            m.cube(low, [lx, 11.5, z - 1], [16, 2, 2], leg, mirror=s > 0)
    return m


def spider_animations():
    ms = "math.min(1.0, query.modified_move_speed * 4.0)"
    d = "query.modified_distance_moved * 30.0"
    bones = {}
    for side, s in (("right", -1), ("left", 1)):
        for i in range(4):
            ph = (i % 2) * 180 + (90 if side == "left" else 0)
            bones[f"leg{side}{i}"] = {"rotation": [
                0, f"math.cos({d} + {ph}) * 18.0 * {ms}",
                f"math.max(0.0, math.sin({d} + {ph})) * {14 * s}.0 * {ms}"]}
    return {
        "arana.move": {"loop": True, "bones": bones},
        "arana.idle": {"loop": True, "bones": {
            "abdomen": {"rotation": ["math.sin(query.life_time * 70.0) * 3.0", 0, 0]},
            "body": {"position": [0, "math.sin(query.life_time * 70.0) * 0.3", 0]}}},
        "arana.look": {"loop": True, "bones": {
            "head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.5", 0]}}},
        "arana.attack": {"loop": True, "bones": {
            "head": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 25.0", 0, 0]},
            "legright0": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 40.0", 0, 0]},
            "legleft0": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 40.0", 0, 0]}}},
        "arana.leap": {"animation_length": 0.8, "bones": {
            "body": {"rotation": {"0.0": [0, 0, 0], "0.25": [12, 0, 0], "0.5": [-18, 0, 0], "0.8": [0, 0, 0]}},
            "abdomen": {"rotation": {"0.0": [0, 0, 0], "0.25": [-15, 0, 0], "0.8": [0, 0, 0]}}}},
    }


# ================================================================ Creeper Mutante
def creeper():
    m = Model(g("creeper_mutante"), bounds=(3.0, 3.5))
    skin = Mat("creeper", streaks=0.35).with_deco(sides=[spots("sculk", 0.04)], back=[veins(count=2)])
    face = Mat("creeper", light=0.05).with_deco(front=[creeper_face("#06110b", glow="#3fd3db")])
    moss = Mat("sculk", fringe=3, contrast=1.1).with_deco(top=[veins(count=3, length=4)])
    spine = Mat("deepslate", contrast=1.2, light=0.12)
    foot = Mat("creeper", light=-0.1, streaks=0.6)
    m.bone("root", [0, 0, 0])
    body = m.bone("body", [0, 13, 0], "root")
    m.cube(body, [-7, 13, -5], [14, 17, 10], skin)
    m.cube(body, [-7, 26, -5], [14, 4, 10], moss, inflate=0.4)
    for i, y in enumerate((16, 21, 26)):
        m.cube(body, [-1.5, y, 4], [3, 5, 3], spine, pivot=[0, y, 5], rotation=[-35, 0, 0])
    hd = m.bone("head", [0, 30, 0], "body")
    m.cube(hd, [-7, 30, -7], [14, 14, 14], face)
    m.cube(hd, [-7, 41, -7], [14, 3, 14], moss, inflate=0.45)
    for i, (x, z, zr) in enumerate(((-5, -2, 20), (3, -1, -20), (-1, 3, 0))):
        m.cube(hd, [x, 44, z], [2, 4, 2], spine, pivot=[x + 1, 44, z + 1], rotation=[-10, 0, zr])
    for name, x, z in (("legfr", -4, -4), ("legfl", 4, -4), ("legbr", -4, 4), ("legbl", 4, 4)):
        lg = m.bone(name, [x, 13, z], "body", rotation=[18 if z < 0 else -18, 0, 14 if x > 0 else -14])
        m.cube(lg, [x - 3, -1, z - 3], [6, 14, 6], foot, mirror=x > 0)
    return m


def creeper_animations():
    ms = "math.min(1.0, query.modified_move_speed * 3.0)"
    d = "query.modified_distance_moved * 26.0"
    return {
        "creeper.move": {"loop": True, "bones": {
            "legfr": {"rotation": [f"math.cos({d}) * 30.0 * {ms}", 0, 0]},
            "legbl": {"rotation": [f"math.cos({d}) * 30.0 * {ms}", 0, 0]},
            "legfl": {"rotation": [f"-math.cos({d}) * 30.0 * {ms}", 0, 0]},
            "legbr": {"rotation": [f"-math.cos({d}) * 30.0 * {ms}", 0, 0]}}},
        "creeper.idle": {"loop": True, "bones": {
            "head": {"rotation": [0, 0, "math.sin(query.life_time * 50.0) * 2.0"]},
            "body": {"scale": [1, "1.0 + math.sin(query.life_time * 90.0) * 0.01", 1]}}},
        "creeper.look": {"loop": True, "bones": {
            "head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.5", 0]}}},
        "creeper.swell": {"animation_length": 1.5, "bones": {
            "body": {"scale": {"0.0": [1, 1, 1], "1.3": [1.25, 1.12, 1.25], "1.4": [1.35, 1.2, 1.35], "1.5": [1, 1, 1]}},
            "head": {"scale": {"0.0": [1, 1, 1], "1.3": [1.15, 1.15, 1.15], "1.5": [1, 1, 1]}}}},
    }


# ================================================================ Coloso Abisal (boss)
def colossus():
    m = Model(g("coloso_abisal"), bounds=(5.0, 5.5))
    stone = Mat("deepslate", contrast=1.15, streaks=0.4).with_deco(sides=[cracks(2, 4)])
    plate = Mat("deep_bone", contrast=1.0, light=-0.18).with_deco(sides=[cracks(1)], top=[spots("sculk", 0.05)])
    sculk = Mat("sculk", contrast=1.1).with_deco(all=[veins(count=3, length=5)])
    heart = Mat("deepslate", contrast=1.0).with_deco(front=[glow_core(r=4), veins(count=4, length=6)])
    face = Mat("deepslate", light=0.05).with_deco(front=[brow(3), eyes(4, [2, 8], "#0f8f9a", core="#c2fbfc"),
                                                         mouth(8, 2, 10, dark="#03181c", teeth="#56565e", gap=3)])
    horn = Mat("deep_bone", contrast=0.9, light=0.05)
    moss = Mat("sculk", fringe=4)
    m.bone("root", [0, 0, 0])
    m.bone("waist", [0, 26, 0], "root")
    hips = m.bone("hips", [0, 26, 0], "waist")
    m.cube(hips, [-9, 24, -5], [18, 8, 10], stone)
    m.cube(hips, [-9, 22, -5], [18, 8, 10], moss, inflate=0.4)
    for side, x in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}leg", [5 * x, 26, 0], "waist")
        ox = -10 if x < 0 else 2
        m.cube(leg, [ox, 0, -4], [8, 26, 8], stone, mirror=x > 0)
        m.cube(leg, [ox, 12, -4], [8, 8, 8], plate, inflate=0.5, mirror=x > 0)
    body = m.bone("body", [0, 32, 0], "waist", rotation=[12, 0, 0])
    m.cube(body, [-12, 32, -6], [24, 20, 13], stone)
    m.cube(body, [-5, 38, -6.5], [10, 10, 1], heart)
    m.cube(body, [-12, 44, -6], [24, 8, 13], plate, inflate=0.5)
    m.cube(body, [-9, 32, 6], [18, 18, 3], sculk)
    for i, (o, rot) in enumerate((([-9, 50, 3], [-20, 0, -20]), ([5, 51, 2], [-25, 0, 18]),
                                  ([-2, 52, 0], [-10, 0, 0]), ([-11, 44, 6], [-40, 0, -10]),
                                  ([7, 43, 6], [-40, 0, 10]))):
        m.cube(body, o, [4, 9, 4], plate, pivot=[o[0] + 2, o[1], o[2] + 2], rotation=rot)
    head = m.bone("head", [0, 52, -1], "body", rotation=[-12, 0, 0])
    m.cube(head, [-6, 51, -10], [12, 11, 11], face)
    jaw = m.bone("jaw", [0, 53, -1], "head")
    m.cube(jaw, [-6, 48, -10], [12, 4, 10], Mat("deepslate").with_deco(front=[mouth(0, 2, 10, dark="#03181c",
                                                                                     teeth="#56565e", gap=3)]))
    for x, r in ((-8, -25), (6, 25)):
        m.cube(head, [x, 58, -5], [2, 9, 2], horn, pivot=[x + 1, 58, -4], rotation=[-20, 0, r])
    for side, x in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}arm", [14 * x, 48, 0], "body", rotation=[-12, 0, 0])
        ox = -22 if x < 0 else 12
        m.cube(arm, [ox, 30, -5], [10, 20, 10], stone, mirror=x > 0)
        m.cube(arm, [ox, 42, -5], [10, 8, 10], plate, inflate=0.6, mirror=x > 0)
        fore = m.bone(f"{side}arm2", [17 * x, 31, 0], f"{side}arm", rotation=[-15, 0, 0])
        fx = -23 if x < 0 else 11
        m.cube(fore, [fx, 10, -6], [12, 22, 12], stone, mirror=x > 0)
        m.cube(fore, [fx, 10, -6], [12, 10, 12], plate, inflate=0.5, mirror=x > 0)
        m.cube(fore, [fx + 4, 18, -2], [4, 6, 4], sculk, pivot=[fx + 6, 18, 0], rotation=[0, 0, 30 * -x])
    return m


def colossus_animations():
    ms = "math.min(1.0, query.modified_move_speed * 3.0)"
    d = "query.modified_distance_moved * 16.0"
    return {
        "coloso.move": {"loop": True, "bones": {
            "rightleg": {"rotation": [f"math.cos({d}) * 22.0 * {ms}", 0, 0]},
            "leftleg": {"rotation": [f"-math.cos({d}) * 22.0 * {ms}", 0, 0]},
            "rightarm": {"rotation": [f"-math.cos({d}) * 16.0 * {ms}", 0, 0]},
            "leftarm": {"rotation": [f"math.cos({d}) * 16.0 * {ms}", 0, 0]},
            "body": {"rotation": [0, f"math.sin({d}) * 5.0 * {ms}", 0]}}},
        "coloso.idle": {"loop": True, "bones": {
            "body": {"rotation": ["math.sin(query.life_time * 60.0) * 1.5", 0, 0]},
            "jaw": {"rotation": ["math.max(0.0, math.sin(query.life_time * 30.0)) * 6.0", 0, 0]}}},
        "coloso.look": {"loop": True, "bones": {
            "head": {"rotation": ["query.target_x_rotation * 0.5", "query.target_y_rotation * 0.5", 0]}}},
        "coloso.attack": {"loop": True, "bones": {
            "rightarm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 100.0", 0, 0]},
            "body": {"rotation": [0, "math.sin(variable.attack_time * 180.0) * 20.0", 0]}}},
        "coloso.slam": {"animation_length": 1.4, "bones": {
            "rightarm": {"rotation": {"0.0": [0, 0, 0], "0.6": [-170, 0, -15], "0.85": [20, 0, 0], "1.4": [0, 0, 0]}},
            "leftarm": {"rotation": {"0.0": [0, 0, 0], "0.6": [-170, 0, 15], "0.85": [20, 0, 0], "1.4": [0, 0, 0]}},
            "body": {"rotation": {"0.0": [0, 0, 0], "0.6": [-20, 0, 0], "0.85": [25, 0, 0], "1.4": [0, 0, 0]}}},
            "sound_effects": {"0.85": {"effect": "slam"}}},
        "coloso.roar": {"animation_length": 2.0, "bones": {
            "head": {"rotation": {"0.0": [0, 0, 0], "0.4": [-35, 0, 0], "1.6": [-35, 0, 0], "2.0": [0, 0, 0]}},
            "jaw": {"rotation": {"0.0": [0, 0, 0], "0.4": [40, 0, 0], "1.6": [40, 0, 0], "2.0": [0, 0, 0]}},
            "rightarm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-20, 0, -40], "1.6": [-20, 0, -40], "2.0": [0, 0, 0]}},
            "leftarm": {"rotation": {"0.0": [0, 0, 0], "0.4": [-20, 0, 40], "1.6": [-20, 0, 40], "2.0": [0, 0, 0]}}},
            "sound_effects": {"0.4": {"effect": "roar"}}},
    }


# ================================================================ Esqueleto Mutante Abisal
def abyss_skeleton():
    """The user's mutant skeleton (bow version) with a new texture: its own
    shading kept, recoloured to deepslate bone, sculk veins and glowing eyes."""
    geo = json.load(open(os.path.join(MUTANT_SRC, "mutant_skeleton.json")))
    gg = geo["minecraft:geometry"][0]
    gg["description"]["identifier"] = g("esqueleto_mutante_abisal")
    src = Image.open(os.path.join(MUTANT_SRC, "skeleton.png")).convert("RGBA")
    tex = Image.new("RGBA", src.size, (0, 0, 0, 0))
    bone_r, wood_r, glow = ramp("deep_bone"), ramp("deepslate")[2:], ramp("sculk_glow")
    px, out = src.load(), tex.load()
    for y in range(src.height):
        for x in range(src.width):
            r, gr, b, a = px[x, y]
            if not a:
                continue
            lum = (0.3 * r + 0.59 * gr + 0.11 * b) / 255
            woody = r > gr + 18  # the bow and the shoulder pads are brown
            rr = wood_r if woody else bone_r
            lo, span = (0.05, 0.4) if woody else (0.42, 0.62)
            i = max(0, min(len(rr) - 1, round((lum - lo) / span * (len(rr) - 1))))
            out[x, y] = rr[i][:3] + (a,)
    # glowing eyes in the dark sockets of the skull's face, and sculk veins over the bones
    head = next(b for b in gg["bones"] if b["name"] == "head")["cubes"][0]
    u, v = head["uv"]
    for y in range(8):
        for x in range(8):
            r, gr, b, a = px[u + 8 + x, v + 8 + y]
            if a and (0.3 * r + 0.59 * gr + 0.11 * b) / 255 < 0.42 and 2 <= y <= 5:
                out[u + 8 + x, v + 8 + y] = glow[3] if x in (2, 5) else glow[1]
    import random
    rng = random.Random(41)
    for _ in range(14):
        x, y = rng.randrange(src.width), rng.randrange(64)
        for i in range(rng.randint(3, 6)):
            if 0 <= x < src.width and 0 <= y < src.height and out[x, y][3] and (x, y) not in ():
                out[x, y] = glow[min(len(glow) - 1, i % 3)][:3] + (255,)
            if rng.random() < 0.5:
                x += rng.choice((-1, 1))
            else:
                y += rng.choice((-1, 1))
    return geo, tex


SKELETON_ANIMS = {
    "esqueleto.move": "animation.mskeleton.walk",
    "esqueleto.move_arms": "animation.mskeleton.walk_arms",
    "esqueleto.idle": "animation.mskeleton.general",
    "esqueleto.look": "animation.mskeleton.look_at_target",
    "esqueleto.charge": "animation.mskeleton.bow_charging",
    "esqueleto.shoot": "animation.mskeleton.bow_shoot",
    "esqueleto.no_arrow": "animation.mskeleton.hidden_arrow",
}


def skeleton_animations():
    src = json.load(open(os.path.join(MUTANT_SRC, "mskeleton_anim.json")))["animations"]
    return {ours: src[orig] for ours, orig in SKELETON_ANIMS.items()}


# ================================================================ all
MOBS = {
    "zombi_mutante": (zombie, zombie_animations),
    "arana_mutante": (spider, spider_animations),
    "creeper_mutante": (creeper, creeper_animations),
    "coloso_abisal": (colossus, colossus_animations),
}


def build_all(seed=7):
    """name -> (geometry json, texture image, animations dict)"""
    out = {}
    for i, (name, (fn, anims)) in enumerate(MOBS.items()):
        m = fn()
        tex = m.build(seed + i)
        out[name] = (m.geometry(), tex, anims())
    geo, tex = abyss_skeleton()
    out["esqueleto_mutante_abisal"] = (geo, tex, skeleton_animations())
    return out


if __name__ == "__main__":
    import sys
    from mutant_style import render
    out_dir = sys.argv[1]
    for name, (geo, tex, _) in build_all().items():
        tex.save(os.path.join(out_dir, f"{name}.png"))
        ims = [render(geo, tex, yaw=y, pitch=12, scale=4) for y in (25, 160)]
        sheet = Image.new("RGBA", (sum(i.width for i in ims) + 10, max(i.height for i in ims)), (40, 40, 50, 255))
        x = 0
        for i in ims:
            sheet.alpha_composite(i, (x, 0))
            x += i.width + 10
        sheet.save(os.path.join(out_dir, f"{name}_render.png"))
        print(name, tex.size)
