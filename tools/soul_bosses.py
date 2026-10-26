"""Mini bosses for Soul Corrupted Mobs: the Soul Corrupted Mutant Skeleton
(blue) and the Soul Corrupted Blade Zombie (red), their summoning items and
the progression items. Used by tools/soul_mobs.py.

How the custom deaths work: Minecraft always plays its own death tilt, so a
boss never really reaches 0 health. It has HP_BUFFER extra health; when it
drops to HP_BUFFER the script makes it invulnerable (eu_sc:state = 2), the
client plays the death animation and the script then removes it, drops the
loot and (skeleton) summons a creeper and a zombie. There is no boss bar, so
the buffer is never visible.
"""
import copy
import json
import math
import os

from PIL import Image

from models import Model
from soul_mobs import (A, NS, PALETTE, ROOT, WHITE, Pal16, fam, hx, immunities, kf, mix_hex)

HP_BUFFER = 500
MUTANT_SRC = os.path.join(ROOT, "sources", "mutant_skeleton")  # model, texture and animations provided by the user
SKELETON_BOSS = "soul_mutant_skeleton"
ZOMBIE_BOSS = "soul_blade_zombie"
STAR = f"{NS}:soul_corrupted_star"
PLANT = f"{NS}:soul_corrupted_plant"
ESSENCE = f"{NS}:soul_essence"
CORE = f"{NS}:soul_core"

BOSSES = {
    SKELETON_BOSS: dict(es="Esqueleto Mutante de Alma Corrupta", en="Soul Corrupted Mutant Skeleton",
                        color="blue", hp=400, dmg=12, speed=0.27, box=(1.4, 3.8), death_ticks=60,
                        egg=("#CEF8F9", "#24C7DD"),
                        loot=[("eu_sc:soul_corrupted_sword", 1, 1), (ESSENCE, 4, 8), ("minecraft:bone", 4, 8)],
                        xp=60, minions=["soul_corrupted_creeper", "soul_corrupted_zombie"]),
    ZOMBIE_BOSS: dict(es="Zombi Cuchilla de Alma Corrupta", en="Soul Corrupted Blade Zombie",
                      color="red", hp=400, dmg=8, speed=0.33, box=(0.6, 1.95), death_ticks=50,
                      egg=("#F4A3A0", "#C7242A"),
                      loot=[(CORE, 1, 1), (ESSENCE, 3, 6), ("minecraft:rotten_flesh", 2, 5)],
                      xp=40, minions=[]),
}


# ================================================================== models
def d_skull():
    def fn(f):
        dark = f.tone(5)
        f.px([(1, 2), (2, 2), (6, 2), (7, 2), (1, 3), (2, 3), (6, 3), (7, 3)], dark)
        f.px([(2, 3), (6, 3)], WHITE)
        f.px([(4, 4), (4, 5)], dark)
        for x in range(1, 8):
            f.put(x, 6, dark if x % 2 else f.tone(0))
    return fn


def d_blade_edges():
    """Side of a flat blade: white cutting edges top and bottom, dark fuller."""
    def fn(f):
        for x in range(f.w):
            f.put(x, 0, WHITE)
            f.put(x, f.h - 1, WHITE)
            if f.h > 4:
                f.put(x, f.h // 2, f.tone(5))
    return fn


def d_white():
    def fn(f):
        for y in range(f.h):
            for x in range(f.w):
                f.put(x, y, WHITE)
    return fn


def d_blade():
    """Blade side: white cutting edge, darker spine."""
    def fn(f):
        for y in range(f.h):
            f.put(0, y, WHITE)
            f.put(f.w - 1, y, f.tone(5))
            if f.w > 2:
                f.put(f.w // 2, y, f.tone(4))
    return fn


def _subtree(bones, root_name):
    names = {root_name}
    changed = True
    while changed:
        changed = False
        for b in bones:
            if b.get("parent") in names and b["name"] not in names:
                names.add(b["name"])
                changed = True
    return names


def mutant_skeleton_assets():
    """The user's mutant skeleton model: the bow is removed, a giant soul
    sword (bone 'rsword', used by the model's own sword animations) is put in
    the right hand, and the grey texture is recoloured to the soul palette
    with white eyes."""
    geo = json.load(open(os.path.join(MUTANT_SRC, "mutant_skeleton.json")))
    g = geo["minecraft:geometry"][0]
    drop = _subtree(g["bones"], "bow_main")
    g["bones"] = [b for b in g["bones"] if b["name"] not in drop]
    g["description"]["identifier"] = f"geometry.eu.sc.{SKELETON_BOSS}"
    for b in g["bones"]:
        if b["name"] == "root":
            b["locators"] = {"particle_locator": [0, 0, 0]}
        elif b["name"] == "topbody":
            b["locators"] = {"slash_point": [0, 34, -18]}

    src = Image.open(os.path.join(MUTANT_SRC, "skeleton.png")).convert("RGBA")
    tex = Image.new("RGBA", src.size, (0, 0, 0, 0))
    px, out = src.load(), tex.load()
    for y in range(src.height):
        for x in range(src.width):
            r, gg, b, a = px[x, y]
            if not a:
                continue
            lum = (0.3 * r + 0.59 * gg + 0.11 * b) / 255
            # light bone -> white/pale cyan, dark crevices -> deep cyan
            t = max(0.0, min(1.0, (1.0 - lum) * 1.5))
            i = min(len(PALETTE) - 2, int(t * (len(PALETTE) - 1)))
            out[x, y] = hx(mix_hex(PALETTE[i], PALETTE[i + 1], t * (len(PALETTE) - 1) - i))[:3] + (a,)
    head = next(b for b in g["bones"] if b["name"] == "head")["cubes"][0]
    u, v = head["uv"]
    for y in range(8):  # white eyes: the dark sockets of the skull's face
        for x in range(8):
            r, gg, b, a = px[u + 8 + x, v + 8 + y]
            if a and (0.3 * r + 0.59 * gg + 0.11 * b) / 255 < 0.42 and 2 <= y <= 5:
                out[u + 8 + x, v + 8 + y] = WHITE

    # A huge greatsword (about 2.4 blocks): wide blade with white edges, a
    # fuller down the middle, pronged crossguard and a pommel
    sword = Model("sword", tex_w=64, ns="eu.sc")
    bone = sword.bone("rsword", [-8, 24, 2], "rightarm2")
    dark = Pal16("deep", 0.4)
    steel = Pal16("skin", 0.25).with_deco(right=d_blade_edges(), left=d_blade_edges(), top=d_white(),
                                          bottom=d_white())
    sword.cube(bone, [-8.5, 22.5, -1], [1, 2, 6], dark)  # grip through the fist
    sword.cube(bone, [-9.5, 22, 5], [3, 3, 2], Pal16("bone"))  # pommel
    sword.cube(bone, [-12.5, 21, -3], [9, 4, 2], dark)  # crossguard
    sword.cube(bone, [-13.5, 22, -5], [2, 2, 3], dark)  # prongs
    sword.cube(bone, [-4.5, 22, -5], [2, 2, 3], dark)
    sword.cube(bone, [-9, 20.5, -15], [2, 7, 12], steel)  # wide base of the blade
    sword.cube(bone, [-9, 21, -31], [2, 6, 16], steel)
    sword.cube(bone, [-9, 22, -36], [2, 4, 5], steel)
    sword.cube(bone, [-9, 23, -39], [2, 2, 3], steel)  # point
    sword_img = sword.build(seed=99)
    tex.alpha_composite(sword_img, (64, 64))  # free area of the original texture
    for b in sword.geos["default"]:
        nb = {k: v for k, v in b.items() if k != "cubes"}
        nb["cubes"] = []
        for c in b["cubes"]:
            j = c.to_json()
            j["uv"] = [j["uv"][0] + 64, j["uv"][1] + 64]
            nb["cubes"].append(j)
        g["bones"].append(nb)
    return geo, tex


# The model's own animations that the boss uses: our name -> original name
MUTANT_ANIMS = {
    "mskel_walk": "animation.mskeleton.walk",
    "mskel_walk_arms": "animation.mskeleton.walk_arms",
    "mskel_idle": "animation.mskeleton.general",
    "mskel_look": "animation.mskeleton.look_at_target",
    "mskel_slash": "animation.mskele.swing_right_sword",
    "mskel_blast": "animation.mskeleton.wither_power",
    "mskel_land": "animation.mskeleton.land",
}


def mutant_animations():
    src = json.load(open(os.path.join(MUTANT_SRC, "mskeleton_anim.json")))["animations"]
    out = {name: copy.deepcopy(src[orig]) for name, orig in MUTANT_ANIMS.items()}
    out["mskel_slash"]["bones"].pop("lsword", None)  # this model only has the right sword
    out["mskel_slash"]["particle_effects"] = {"0.5": [{"effect": "slash", "locator": "slash_point"}]}
    out["mskel_slash"]["sound_effects"] = {"0.48": {"effect": "slash"}}
    out["mskel_land"]["particle_effects"] = {"0.0": [{"effect": "burst"}, {"effect": "land"}]}
    out["mskel_land"]["loop"] = "hold_on_last_frame"
    return out


def blade_zombie_geometry(base_geo, base_tex):
    """The original soul zombie with its arms replaced by long blades. The
    original texture fills the top half, the blades are painted below."""
    blades = Model("blades", tex_w=64, ns="eu.sc")
    skin = Pal16("skin", 0.6)
    steel = Pal16("skin", 0.2).with_deco(right=d_blade(), left=d_blade())
    for s, cx, px in (("rightArm", -6, -5), ("leftArm", 6, 5)):
        b = blades.bone(s, [px, 22, 0], "body")
        b["locators"] = {f"{s}_tip": [cx, -1, 0]}
        m = blades
        m.cube(b, [cx - 2, 18, -2], [4, 6, 4], skin)  # shoulder stump
        m.cube(b, [cx - 2.5, 14, -2.5], [5, 4, 5], Pal16("deep", 0.5))  # fused bracer
        m.cube(b, [cx - 0.5, 3, -2], [1, 11, 4], steel)
        m.cube(b, [cx - 0.5, 0, -1.5], [1, 3, 3], steel)
        m.cube(b, [cx - 0.5, -2, -0.5], [1, 2, 1], steel)
    blade_img = blades.build(seed=31337)
    bones = []
    for b in base_geo["bones"]:
        if b["name"] in ("rightArm", "leftArm", "rightItem", "leftItem"):
            continue
        nb = copy.deepcopy(b)
        bones.append(nb)
    for b in blades.geos["default"]:
        nb = {k: v for k, v in b.items() if k != "cubes"}
        nb["cubes"] = []
        for c in b["cubes"]:
            j = c.to_json()
            j["uv"] = [j["uv"][0], j["uv"][1] + 32]
            nb["cubes"].append(j)
        bones.append(nb)
    h = 32 + blade_img.height
    th = 64 if h <= 64 else 128
    tex = Image.new("RGBA", (64, th), (0, 0, 0, 0))
    tex.paste(base_tex.convert("RGBA"), (0, 0))
    tex.alpha_composite(blade_img, (0, 32))
    geo = {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": f"geometry.eu.sc.{ZOMBIE_BOSS}", "texture_width": 64, "texture_height": th,
                        "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 1.5, 0]},
        "bones": bones}]}
    return geo, tex


# ============================================================== animations
WALK = "query.modified_distance_moved * 38.17"
SPD = "query.modified_move_speed"
STATE = f"query.property('{NS}:state')"
ACTION = f"query.property('{NS}:action')"

ANIMS = {
    # ---------------- mutant skeleton (the rest come from the model's own animations)
    # Spawn part 1: falling from the sky, flailing
    "mskel_fall": {"loop": True, "bones": {
        "rightarm": {"rotation": ["-150.0 + math.sin(query.life_time * 500.0) * 15.0", 0.0, 25.0]},
        "leftarm": {"rotation": ["-150.0 - math.sin(query.life_time * 500.0) * 15.0", 0.0, -25.0]},
        "rightleg": {"rotation": ["math.sin(query.life_time * 400.0) * 20.0", 0.0, 0.0]},
        "leftleg": {"rotation": ["-math.sin(query.life_time * 400.0) * 20.0", 0.0, 0.0]},
        "head": {"rotation": [-30.0, 0.0, 0.0]}}},
    # Death: drops to its knees, slumps forward, the sword falls
    "mskel_death": {"loop": "hold_on_last_frame", "animation_length": 2.8,
                    "particle_effects": {"2.4": [{"effect": "burst"}]}, "bones": {
        "waist": {"position": kf({0.0: [0, 0, 0], 0.8: [0, -12, 0], 2.8: [0, -12, 0]})},
        "rightleg": {"rotation": kf({0.0: [0, 0, 0], 0.8: [-85, 0, 0], 2.8: [-85, 0, 0]})},
        "rightleg2": {"rotation": kf({0.0: [0, 0, 0], 0.8: [85, 0, 0], 2.8: [85, 0, 0]})},
        "leftleg2": {"rotation": kf({0.0: [0, 0, 0], 0.8: [85, 0, 0], 2.8: [85, 0, 0]})},
        "body": {"rotation": kf({0.0: [0, 0, 0], 0.8: [10, 0, 0], 1.6: [30, 0, 4], 2.8: [38, 0, 6]})},
        "topbody": {"rotation": kf({0.0: [0, 0, 0], 1.0: [-10, 0, 0], 1.8: [25, 0, 0], 2.8: [30, 0, 0]})},
        "head": {"rotation": kf({0.0: [0, 0, 0], 1.0: [-25, 0, 0], 1.8: [35, 0, 10], 2.8: [40, 0, 12]})},
        "rightarm": {"rotation": kf({0.0: [0, 0, 0], 0.8: [-25, 0, 10], 1.6: [15, 0, 5], 2.8: [20, 0, 4]})},
        "leftarm": {"rotation": kf({0.0: [0, 0, 0], 0.8: [-35, 0, -10], 1.6: [10, 0, -5], 2.8: [15, 0, -4]})},
        "rsword": {"rotation": kf({0.0: [0, 0, 0], 1.4: [0, 0, 0], 1.8: [70, 0, 20], 2.8: [80, 0, 25]})}}},

    # ---------------- blade zombie
    "bzombie_walk": {"loop": True, "bones": {
        "rightLeg": {"rotation": [f"math.cos({WALK}) * 50.0 * {SPD}", 0.0, 0.0]},
        "leftLeg": {"rotation": [f"math.cos({WALK}) * -50.0 * {SPD}", 0.0, 0.0]},
        "body": {"rotation": [f"{SPD} * 10.0", 0.0, f"math.sin({WALK} * 0.5) * 4.0 * {SPD}"]}}},
    "bzombie_blades": {"loop": True, "bones": {
        "rightArm": {"rotation": ["-85.0 + math.sin(query.life_time * 60.0) * 3.0", "-8.0",
                                  "math.sin(query.life_time * 45.0) * 2.0 + 4.0"]},
        "leftArm": {"rotation": ["-85.0 - math.sin(query.life_time * 60.0) * 3.0", "8.0",
                                 "-math.sin(query.life_time * 45.0) * 2.0 - 4.0"]},
        "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation",
                              "math.sin(query.life_time * 24.0) * 4.0"]}}},
    # Normal attack: pull both blades back, thrust them forward, return
    "bzombie_thrust": {"animation_length": 0.7, "bones": {
        "rightArm": {"rotation": kf({0.0: [0, 0, 0], 0.2: [75, 0, 25], 0.32: [-40, 0, -12], 0.45: [-35, 0, -10],
                                     0.7: [0, 0, 0]}),
                     "position": kf({0.0: [0, 0, 0], 0.2: [0, 1, 4], 0.32: [0, 0, -7], 0.45: [0, 0, -6], 0.7: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [0, 0, 0], 0.2: [75, 0, -25], 0.32: [-40, 0, 12], 0.45: [-35, 0, 10],
                                    0.7: [0, 0, 0]}),
                    "position": kf({0.0: [0, 0, 0], 0.2: [0, 1, 4], 0.32: [0, 0, -7], 0.45: [0, 0, -6], 0.7: [0, 0, 0]})},
        "body": {"rotation": kf({0.0: [0, 0, 0], 0.2: [-20, 0, 0], 0.32: [35, 0, 0], 0.45: [32, 0, 0], 0.7: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [0, 0, 0], 0.2: [-20, 0, 0], 0.32: [-25, 0, 0], 0.7: [0, 0, 0]})},
        "waist": {"position": kf({0.0: [0, 0, 0], 0.2: [0, 0, 2], 0.32: [0, 1.5, -4], 0.45: [0, 0, -3], 0.7: [0, 0, 0]})}}},
    "bzombie_dash": {"animation_length": 0.8, "particle_effects": {"0.0": [{"effect": "burst"}]}, "bones": {
        "body": {"rotation": kf({0.0: [0, 0, 0], 0.15: [35, 0, 0], 0.6: [35, 0, 0], 0.8: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [0, 0, 0], 0.15: [-15, 20, 0], 0.6: [-15, 20, 0], 0.8: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [0, 0, 0], 0.15: [-15, -20, 0], 0.6: [-15, -20, 0], 0.8: [0, 0, 0]})},
        "rightLeg": {"rotation": ["math.sin(query.anim_time * 1500.0) * 60.0", 0.0, 0.0]},
        "leftLeg": {"rotation": ["-math.sin(query.anim_time * 1500.0) * 60.0", 0.0, 0.0]}}},
    # Summon: raises both blades and stabs them into the ground
    "bzombie_summon": {"animation_length": 1.1, "particle_effects": {"0.55": [{"effect": "burst"}]}, "bones": {
        "rightArm": {"rotation": kf({0.0: [0, 0, 0], 0.4: [-85, 0, 15], 0.55: [75, 0, 5], 0.9: [75, 0, 5],
                                     1.1: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [0, 0, 0], 0.4: [-85, 0, -15], 0.55: [75, 0, -5], 0.9: [75, 0, -5],
                                    1.1: [0, 0, 0]})},
        "body": {"rotation": kf({0.0: [0, 0, 0], 0.4: [-15, 0, 0], 0.55: [25, 0, 0], 0.9: [25, 0, 0], 1.1: [0, 0, 0]})}}},
    "bzombie_blast": {"animation_length": 0.7, "bones": {
        "rightArm": {"rotation": kf({0.0: [0, 0, 0], 0.3: [40, 0, 70], 0.55: [40, 0, 70], 0.7: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [0, 0, 0], 0.3: [40, 0, -70], 0.55: [40, 0, -70], 0.7: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [0, 0, 0], 0.3: [-35, 0, 0], 0.55: [-30, 0, 0], 0.7: [0, 0, 0]})}}},
    # Entrance: claws its way out of the ground
    "bzombie_emerge": {"loop": "hold_on_last_frame", "animation_length": 2.0,
                       "particle_effects": {"0.0": [{"effect": "burst"}], "1.0": [{"effect": "burst"}]}, "bones": {
        "waist": {"position": kf({0.0: [0, -32, 0], 0.6: [0, -24, 0], 1.3: [0, -10, 0], 1.75: [0, -1, 0], 2.0: [0, 0, 0]}),
                  "rotation": kf({0.0: [30, 0, 0], 0.8: [22, 0, -8], 1.5: [8, 0, 5], 2.0: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-90, 0, 10], 0.5: [-75, 0, 25], 1.0: [-95, 0, 10], 1.5: [-60, 0, 10],
                                     2.0: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [-75, 0, -20], 0.5: [-95, 0, -10], 1.0: [-70, 0, -25], 1.5: [-55, 0, -10],
                                    2.0: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [-30, 0, 0], 1.0: [-15, 10, 10], 1.6: [5, -5, -5], 2.0: [0, 0, 0]})}}},
    # Death: something drags it down into the ground while it fights back
    "bzombie_death": {"loop": "hold_on_last_frame", "animation_length": 2.5,
                      "particle_effects": {"0.0": [{"effect": "burst"}], "1.2": [{"effect": "burst"}],
                                           "2.0": [{"effect": "burst"}]}, "bones": {
        "waist": {"position": kf({0.0: [0, 0, 0], 0.4: [0, -2, 0], 0.9: [0, -6, 0], 1.6: [0, -16, 0],
                                  2.1: [0, -30, 0], 2.5: [0, -40, 0]}),
                  "rotation": kf({0.0: [0, 0, 0], 0.5: [-15, 0, 10], 1.0: [-20, 0, -12], 1.6: [-10, 0, 8],
                                  2.5: [-5, 0, 0]})},
        "rightArm": {"rotation": ["-150.0 + math.sin(query.anim_time * 900.0) * 30.0", 0.0, 20.0]},
        "leftArm": {"rotation": ["-150.0 - math.sin(query.anim_time * 900.0) * 30.0", 0.0, -20.0]},
        "rightLeg": {"rotation": ["math.sin(query.anim_time * 700.0) * 25.0", 0.0, 0.0]},
        "leftLeg": {"rotation": ["-math.sin(query.anim_time * 700.0) * 25.0", 0.0, 0.0]},
        "head": {"rotation": kf({0.0: [0, 0, 0], 0.5: [-35, 0, 0], 2.5: [-45, 0, 0]})}}},
}


def controllers():
    alive_to_dying = {"dying": f"{STATE} == 2"}
    special = lambda name, cond, back: {  # noqa: E731
        "animations": [name], "blend_transition": 0.15,
        "transitions": [alive_to_dying, {"alive": back}]}
    skel = {"initial_state": "start", "states": {
        "start": {"transitions": [{"alive": f"{STATE} == 1"}, alive_to_dying,
                                  {"land": "query.is_on_ground"}, {"fall": "!query.is_on_ground"}]},
        "fall": {"animations": ["mskel_fall"], "transitions": [{"land": "query.is_on_ground"}]},
        "land": {"animations": ["mskel_land"], "transitions": [{"alive": f"{STATE} == 1"}],
                 "blend_transition": 0.3},
        "alive": {"animations": [{"mskel_walk": "math.clamp(query.modified_move_speed * 3.0, 0.0, 1.0)"},
                                 {"mskel_walk_arms": "math.clamp(query.modified_move_speed * 3.0, 0.0, 1.0)"},
                                 "mskel_idle", "mskel_look"], "blend_transition": 0.3,
                  "transitions": [alive_to_dying, {"slash": "variable.attack_time > 0.0"},
                                  {"blast": f"{ACTION} == 1"}]},
        "slash": dict(special("mskel_slash", None, "query.all_animations_finished"),
                      animations=["mskel_look", "mskel_slash"]),
        "blast": dict(special("mskel_blast", None, f"{ACTION} != 1 && query.all_animations_finished"),
                      animations=["mskel_idle", "mskel_blast"]),
        "dying": {"animations": ["mskel_death"], "blend_transition": 0.3},
    }}
    zom = {"initial_state": "start", "states": {
        "start": {"transitions": [{"alive": f"{STATE} == 1"}, alive_to_dying, {"emerge": f"{STATE} == 0"}]},
        "emerge": {"animations": ["bzombie_emerge"], "transitions": [{"alive": f"{STATE} == 1"}],
                   "blend_transition": 0.3},
        "alive": {"animations": ["bzombie_walk", "bzombie_blades"], "blend_transition": 0.2,
                  "transitions": [alive_to_dying, {"dash": f"{ACTION} == 2"}, {"summon": f"{ACTION} == 3"},
                                  {"blast": f"{ACTION} == 1"}, {"thrust": "variable.attack_time > 0.0"}]},
        "thrust": {"animations": ["bzombie_walk", "bzombie_blades", "bzombie_thrust"], "blend_transition": 0.1,
                   "transitions": [alive_to_dying, {"alive": "query.all_animations_finished"}]},
        "dash": special("bzombie_dash", None, f"{ACTION} != 2 && query.all_animations_finished"),
        "summon": special("bzombie_summon", None, f"{ACTION} != 3 && query.all_animations_finished"),
        "blast": special("bzombie_blast", None, f"{ACTION} != 1 && query.all_animations_finished"),
        "dying": {"animations": ["bzombie_death"], "blend_transition": 0.2},
    }}
    # the zombie keeps its blades out during specials
    for st in ("dash", "summon", "blast"):
        zom["states"][st]["animations"] = ["bzombie_walk", "bzombie_blades"] + zom["states"][st]["animations"]
    return {f"controller.animation.{NS}.{SKELETON_BOSS}": skel, f"controller.animation.{NS}.{ZOMBIE_BOSS}": zom}


def client_entity(name):
    B = BOSSES[name]
    anim_names = [n for n in ANIMS if n.startswith("bzombie")] if name == ZOMBIE_BOSS else \
        [n for n in ANIMS if n.startswith("mskel")] + list(MUTANT_ANIMS)
    desc = {
        "identifier": f"{NS}:{name}",
        "materials": {"default": "outline_base", "outline_main": "outline_main"},
        "textures": {"default": f"textures/entity/soul_corrupted/{name}",
                     "outline_main": "textures/entity/soul_corrupted/white_outline"},
        "geometry": {"default": f"geometry.eu.sc.{name}", "outline_main": f"geometry.eu.sc.{name}.outline"},
        "spawn_egg": {"base_color": B["egg"][0], "overlay_color": B["egg"][1]},
        "scripts": {"animate": ["controller", "emitter_particle_controller", "particles"],
                    "should_update_effects_offscreen": "1.0"},
        "animations": dict({n: f"{A}.{n}" for n in anim_names},
                           controller=f"controller.animation.{NS}.{name}",
                           particles=f"{A}.particles",
                           emitter_particle_controller="controller.animation.eu.emitter_particle"),
        "particle_effects": {
            "emitter": f"{NS}:soul_ascending_particle" + ("" if B["color"] == "blue" else "_red"),
            "wisps": f"{NS}:wisp_{B['color']}", "drips": f"{NS}:drip_{B['color']}",
            "burst": f"{NS}:burst_{B['color']}", "slash": f"{NS}:slash", "land": f"{NS}:explosion_blue"},
        "sound_effects": {"slash": "mob.irongolem.throw"},
        "render_controllers": ["controller.render.eu_sc.outline_base.glow", "controller.render.eu_sc.outline_main.glow"],
    }
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


# =============================================================== behaviour
def behavior(name):
    B = BOSSES[name]
    hp = B["hp"] + HP_BUFFER
    skeleton = name == SKELETON_BOSS
    active = {
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 32,
            "entity_types": [{"filters": fam("player"), "max_dist": 40}, {"filters": fam("irongolem"), "max_dist": 32}]},
        "minecraft:behavior.melee_attack": {"priority": 3, "speed_multiplier": 1.15, "track_target": True,
                                            "require_complete_path": False},
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.8},
        "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 16, "probability": 0.05},
        "minecraft:behavior.random_look_around": {"priority": 9},
    }
    groups = {
        f"{NS}:active": active,
        f"{NS}:dying": {"minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                        "minecraft:movement": {"value": 0.0}, "minecraft:knockback_resistance": {"value": 1.0}},
    }
    events = {
        f"{NS}:activate": {"remove": {"component_groups": [f"{NS}:intro", f"{NS}:landing"]},
                           "add": {"component_groups": [f"{NS}:active"]}, "set_property": {f"{NS}:state": 1}},
        f"{NS}:start_dying": {"remove": {"component_groups": [f"{NS}:active", f"{NS}:intro", f"{NS}:landing"]},
                              "add": {"component_groups": [f"{NS}:dying"]}, "set_property": {f"{NS}:state": 2},
                              "reset_target": {}},
    }
    if skeleton:
        # falls from the sky: when it touches the ground it plays the landing animation, then fights
        groups[f"{NS}:intro"] = {"minecraft:environment_sensor": {"triggers": [
            {"filters": {"test": "on_ground", "value": True}, "event": f"{NS}:landed"}]}}
        groups[f"{NS}:landing"] = {"minecraft:timer": {"looping": False, "time": 1.6,
                                                       "time_down_event": {"event": f"{NS}:activate"}}}
        events[f"{NS}:landed"] = {"remove": {"component_groups": [f"{NS}:intro"]},
                                  "add": {"component_groups": [f"{NS}:landing"]}}
    else:
        groups[f"{NS}:intro"] = {"minecraft:timer": {"looping": False, "time": 2.0,
                                                     "time_down_event": {"event": f"{NS}:activate"}}}
    events["minecraft:entity_spawned"] = {"add": {"component_groups": [f"{NS}:intro"]},
                                          "set_property": {f"{NS}:state": 0, f"{NS}:action": 0}}
    family = ["soul_boss", "monster", "mob", "soul_corrupted", "undead"] + (["skeleton"] if skeleton else ["zombie"])
    comps = {
        "minecraft:type_family": {"family": family},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:collision_box": {"width": B["box"][0], "height": B["box"][1]},
        "minecraft:movement": {"value": B["speed"]},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_pass_doors": True, "avoid_water": True, "can_walk_in_lava": True,
                                      "can_path_over_lava": True, "is_amphibious": True},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable_by_entity": {},
        "minecraft:pushable_by_block": {},
        "minecraft:knockback_resistance": {"value": 0.85 if skeleton else 0.6},
        "minecraft:attack": {"damage": B["dmg"], "effect_name": "darkness", "effect_duration": 2},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True, "breathes_water": True},
        # immune to its own blasts and to the fall from the sky
        "minecraft:damage_sensor": {"triggers": immunities(["fall", "entity_explosion", "block_explosion"])},
        "minecraft:follow_range": {"value": 40, "max": 40},
        "minecraft:nameable": {},
        "minecraft:persistent": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:conditional_bandwidth_optimization": {},
    }
    return {"format_version": "1.26.0", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{name}", "is_spawnable": True, "is_summonable": True,
                        "spawn_category": "monster",
                        "properties": {
                            f"{NS}:state": {"type": "int", "range": [0, 2], "default": 0, "client_sync": True},
                            f"{NS}:action": {"type": "int", "range": [0, 3], "default": 0, "client_sync": True}}},
        "component_groups": groups, "components": comps, "events": events}}


SOUNDS = {
    SKELETON_BOSS: {"events": {"ambient": "mob.skeleton.say", "hurt": "mob.skeleton.hurt",
                               "death": "mob.skeleton.death", "step": {"sound": "mob.skeleton.step", "volume": 1.0}},
                    "pitch": [0.45, 0.55], "volume": 1.5},
    ZOMBIE_BOSS: {"events": {"ambient": "mob.zombie.say", "hurt": "mob.zombie.hurt", "death": "mob.zombie.death",
                             "step": {"sound": "mob.zombie.step", "volume": 0.3}}, "pitch": [0.65, 0.75],
                  "volume": 1.2},
}


# ================================================================== items
def item(identifier, texture, lang_key, stack=64, extra=None):
    comps = {
        "minecraft:icon": texture,
        "minecraft:display_name": {"value": lang_key},
        "minecraft:max_stack_size": stack,
    }
    comps.update(extra or {})
    return {"format_version": "1.21.70", "minecraft:item": {
        "description": {"identifier": identifier, "menu_category": {"category": "items"}},
        "components": comps}}


def items():
    summon = {"minecraft:cooldown": {"category": f"{NS}:boss_summon", "duration": 3.0},
              "minecraft:glint": True}
    return {
        "soul_essence": item(ESSENCE, "soul_essence", f"item.{ESSENCE}.name"),
        "soul_core": item(CORE, "soul_core", f"item.{CORE}.name", 16, {"minecraft:glint": True}),
        "soul_corrupted_plant": item(PLANT, "soul_corrupted_plant", f"item.{PLANT}.name", 16, summon),
        "soul_corrupted_star": item(STAR, "soul_corrupted_star", f"item.{STAR}.name", 16, summon),
    }


def recipes():
    def shaped(name, pattern, key, result):
        return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
            "description": {"identifier": f"{NS}:{name}"}, "tags": ["crafting_table"],
            "pattern": pattern, "key": {k: {"item": v} for k, v in key.items()}, "result": {"item": result}}}
    return {
        # progression: soul mobs -> essence -> plant -> Blade Zombie -> core -> star -> Mutant Skeleton -> sword
        "soul_corrupted_plant": shaped("soul_corrupted_plant", ["E E", " F ", "ESE"],
                                       {"E": ESSENCE, "F": "minecraft:crimson_fungus", "S": "minecraft:soul_soil"},
                                       PLANT),
        "soul_corrupted_star": shaped("soul_corrupted_star", ["EEE", "ECE", "EDE"],
                                      {"E": ESSENCE, "C": CORE, "D": "minecraft:diamond"}, STAR),
    }


def _shape_icon(inside, colors, outline="#0d1b28"):
    """16x16 icon from a function inside(x, y) -> shade 0..1 or None."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    filled = {}
    for y in range(16):
        for x in range(16):
            t = inside(x, y)
            if t is not None:
                filled[(x, y)] = colors[min(len(colors) - 1, int(t * len(colors)))]
    for (x, y), c in filled.items():
        img.putpixel((x, y), hx(c))
    for y in range(16):
        for x in range(16):
            if (x, y) not in filled and any((x + dx, y + dy) in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                img.putpixel((x, y), hx(outline))
    return img


def item_textures():
    blue = ["#ffffff", "#cef8f9", "#9df1f3", "#6deaec", "#3cdae6", "#24c7dd"]
    red = ["#ffffff", "#f9d0cf", "#f39e9d", "#ec6d6e", "#e63c40", "#c7242a"]

    def essence(x, y):  # soul teardrop
        cx, cy = 7.5, 9.0
        r = math.hypot(x - cx, y - cy)
        top = y < cy and abs(x - cx) <= (y - 2) * 0.55
        if r <= 4.6 or top:
            return min(0.99, math.hypot(x - 6, y - 7.5) / 6.5)
        return None

    def star(x, y):  # four-pointed star
        dx, dy = abs(x - 7.5), abs(y - 7.5)
        if dx ** 0.7 + dy ** 0.7 <= 7.5 ** 0.7:
            return min(0.99, (dx + dy) / 8.5)
        return None

    def core(x, y):  # crystal heart / gem
        dx, dy = abs(x - 7.5), y - 7.5
        if dx + abs(dy) * (0.8 if dy > 0 else 1.6) <= 6.5:
            return min(0.99, (dx + abs(dy - 2)) / 8)
        return None

    plant = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    rows = ["......ORRO......",
            ".....ORWRRO.....",
            ".....ORRRRO.....",
            "......ORRO......",
            ".......GO.......",
            "..OO...G...OO...",
            ".OLLO..G..OLLO..",
            "..OLLO.G.OLLO...",
            "...OLLOGOLLO....",
            ".....OLGLO......",
            ".......G........",
            "......OGO.......",
            "...OSSSSSSSO....",
            "...OSPSSSPSO....",
            "....OSSSSSO.....",
            ".....OOOOO......"]
    pal = {"O": "#1a0d10", "R": "#e63c40", "W": "#ffffff", "G": "#7a1f26", "L": "#c7242a", "S": "#4a3428",
           "P": "#ec6d6e"}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                plant.putpixel((x, y), hx(pal[ch]))
    return {
        "soul_essence": _shape_icon(essence, blue[:5]),
        "soul_core": _shape_icon(core, red[:6]),
        "soul_corrupted_star": _shape_icon(star, blue),
        "soul_corrupted_plant": plant,
    }


def lang(es):
    lines = []
    for name, B in BOSSES.items():
        n = B["es"] if es else B["en"]
        lines += [f"entity.{NS}:{name}.name={n}",
                  f"item.spawn_egg.entity.{NS}:{name}.name={'Generar ' if es else 'Spawn '}{n}"]
    lines += [
        f"item.{ESSENCE}.name={'Esencia de Alma' if es else 'Soul Essence'}",
        f"item.{CORE}.name={'Núcleo de Alma' if es else 'Soul Core'}",
        f"item.{PLANT}.name={'Planta de Alma Corrupta' if es else 'Soul Corrupted Plant'}",
        f"item.{STAR}.name={'Estrella de Alma Corrupta' if es else 'Soul Corrupted Star'}",
    ]
    return lines
