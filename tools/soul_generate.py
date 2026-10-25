"""Builds the Soul Corrupted add-on (behavior pack + resource pack + .mcaddon).

    python3 tools/soul_generate.py            # regenerate everything
    python3 tools/soul_generate.py --preview  # also refresh the images in docs/
"""
import json
import math
import os
import random
import shutil
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import fam, preview, sheet, targets, write  # noqa: E402
from models import Model, creeper, humanoid  # noqa: E402
from textures import SIDES, hx, mix  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "SoulCorrupted_BP")
RP = os.path.join(ROOT, "SoulCorrupted_RP")
DIST = os.path.join(ROOT, "dist")

NS = "soul"
VERSION = [1, 1, 0]
MIN_ENGINE = [1, 21, 90]  # the rideable phantom uses minecraft:input_air_controlled
SCRIPT_API = "1.11.0"
UUID = {
    "bp_header": "c1d2e3f4-0a1b-4c2d-8e3f-a4b5c6d7e8f9",
    "bp_data": "d2e3f405-1b2c-4d3e-9f40-b5c6d7e8f90a",
    "bp_script": "e3f40516-2c3d-4e4f-a051-c6d7e8f90a1b",
    "rp_header": "f4051627-3d4e-4f50-b162-d7e8f90a1b2c",
    "rp_res": "05162738-4e5f-4061-8273-e8f90a1b2c3d",
}

# Tones from lightest to darkest: highlight, base, mid, dark, deep.
# The whole body glows a little (entity_emissive_alpha: lower alpha = brighter),
# highlights and eyes glow fully.
COLORS = {
    "blue": dict(es="Azul", en="Blue", tones=["#effdff", "#a3e6ee", "#6ccfdd", "#2fb2c8", "#178aa6"],
                 glow="#3fe0ff", extra=[["slowness", 60, 0]], ignite=0, fire=False, rgb=(0.3, 0.9, 1.0)),
    "red": dict(es="Roja", en="Red", tones=["#fff0ec", "#f4aea6", "#e9827a", "#cf4a44", "#a32b2e"],
                glow="#ff4a3a", extra=[], ignite=4, fire=True, rgb=(1.0, 0.32, 0.25)),
    "green": dict(es="Verde", en="Green", tones=["#f0fff0", "#ace9b0", "#7bd986", "#3fbd55", "#21923a"],
                  glow="#46ff5a", extra=[["poison", 80, 0]], ignite=0, fire=False, rgb=(0.35, 1.0, 0.42)),
}
TONE_ALPHA = [0, 140, 175, 215, 240]
DARKNESS = ["darkness", 160, 0]

TYPES = {
    "zombie": dict(es="Zombi de Alma Corrupta", en="Soul Corrupted Zombie", hp=26, speed=0.24, dmg=4,
                   emerge=1.2, weight=10, family=["zombie", "undead"], box=(0.6, 1.9),
                   loot=[("rotten_flesh", 0, 2), ("soul_sand", 0, 1)]),
    "creeper": dict(es="Creeper de Alma Corrupta", en="Soul Corrupted Creeper", hp=24, speed=0.23, dmg=3,
                    emerge=0.9, weight=9, family=["creeper", "soul_creeper"], box=(0.6, 1.7), power=3,
                    loot=[("gunpowder", 1, 2), ("soul_sand", 0, 1)]),
    "skeleton": dict(es="Esqueleto de Alma Corrupta", en="Soul Corrupted Skeleton", hp=22, speed=0.26, dmg=3,
                     emerge=1.2, weight=9, family=["skeleton", "undead"], box=(0.6, 1.99), equip="bow",
                     loot=[("bone", 0, 2), ("arrow", 0, 3), ("soul_sand", 0, 1)]),
    "phantom": dict(es="Phantom de Alma Corrupta", en="Soul Corrupted Phantom", hp=34, speed=1.8, dmg=6,
                    emerge=0.8, weight=4, family=["phantom", "undead"], box=(2.0, 1.0),
                    loot=[("phantom_membrane", 0, 2)]),
}
PHANTOM_SCALE = 2.5  # "2.5 players" big
NETHER_BIOME = {"blue": "soul_sand_valley", "red": "crimson_forest", "green": "warped_forest"}
SWORD = f"{NS}:corrupted_soul_sword"
MOUNT = "corrupted_phantom_mount"
ALTAR = "healing_altar"
IMMUNE_TO = ["fire", "fire_tick", "lava", "magma", "freezing", "drowning", "wither"]


# ============================================================ 16x16 painter
class SoulCtx:
    """Paints on one face of a cube. Coordinates in pixels of that face."""

    def __init__(self, img, x0, y0, w, h, mat, name):
        self.img, self.x0, self.y0, self.w, self.h, self.mat, self.name = img, x0, y0, w, h, mat, name

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((self.x0 + x, self.y0 + y), c)

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c)

    def px(self, points, c):
        for x, y in points:
            self.put(x, y, c)

    def tone(self, i):
        return self.mat.tone(i)


WHITE = (255, 255, 255, 0)  # fully emissive white: the eyes


class Soul16:
    """Luminous soul body: light base, darker maze-like veins, highlights on top.
    kind: skin | deep (darker, e.g. legs) | bone | stone (altar) | crystal."""

    def __init__(self, pal, kind="skin", veins=1.0, deco=None):
        self.pal, self.kind, self.veins, self.deco = pal, kind, veins, deco or {}
        t = [hx(c) for c in pal["tones"]]
        if kind == "bone":
            t = [t[0], mix(t[0], t[1], 0.55), t[1], t[2], t[3]]
        elif kind == "stone":
            t = [hx("#5b6272"), hx("#454b59"), hx("#363b47"), hx("#2a2e38"), hx("#1d2028")]
        self.tones = t
        self.base_idx = 2 if kind == "deep" else 1

    def tone(self, i):
        i = max(0, min(4, i))
        alpha = 255 if self.kind == "stone" else TONE_ALPHA[i]
        return self.tones[i][:3] + (alpha,)

    def with_deco(self, **deco):
        m = Soul16(self.pal, self.kind, self.veins, {k: list(v) for k, v in self.deco.items()})
        for k, v in deco.items():
            m.deco.setdefault(k, []).extend(v if isinstance(v, list) else [v])
        return m

    def paint(self, img, u, v, w, h, d, rng, res=1):
        regions = {
            "top": (u + d, v, w, d), "bottom": (u + d + w, v, w, d),
            "right": (u, v + d, d, h), "front": (u + d, v + d, w, h),
            "left": (u + d + w, v + d, d, h), "back": (u + 2 * d + w, v + d, w, h),
        }
        for name, (x0, y0, fw, fh) in regions.items():
            if fw <= 0 or fh <= 0:
                continue
            face = self._face(fw, fh, name, rng)
            for y in range(fh):
                for x in range(fw):
                    img.putpixel((x0 + x, y0 + y), face[y][x])
            ctx = SoulCtx(img, x0, y0, fw, fh, self, name)
            for k in [name, "all"] + (["sides"] if name in SIDES else []):
                for fn in self.deco.get(k, []):
                    fn(ctx)

    def _face(self, W, H, name, rng):
        if self.kind == "crystal":
            return [[self.tone(0) if (x + y) % 3 else self.tone(1)[:3] + (0,) for x in range(W)] for y in range(H)]
        grid = [[rng.random() for _ in range(W // 2 + 2)] for _ in range(H // 2 + 2)]
        idx = [[self.base_idx] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                t = grid[y // 2][x // 2] * 0.8 + rng.random() * 0.2
                i = self.base_idx + (1 if t < 0.25 else (-1 if t > 0.86 else 0))
                if y == 0 and rng.random() < 0.3:
                    i -= 1
                if H > 3 and y >= H * 0.7 and rng.random() < (y / H - 0.55):
                    i += 1
                if name == "bottom":
                    i += 1
                idx[y][x] = i
        # Maze-like veins: right-angled lines in the darker tones
        n = int(W * H * self.veins / 22 + rng.random())
        for _ in range(n):
            x, y = rng.randrange(W), rng.randrange(H)
            dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            for _ in range(rng.randint(3, 6)):
                if not (0 <= x < W and 0 <= y < H):
                    break
                idx[y][x] = self.base_idx + (3 if rng.random() < 0.2 else 2)
                if rng.random() < 0.35:
                    dx, dy = (dy, dx) if rng.random() < 0.5 else (-dy, -dx)
                x, y = x + dx, y + dy
        return [[self.tone(idx[y][x]) for x in range(W)] for y in range(H)]


# ---- faces and markings
def d_zombie_face():
    def fn(f):
        sockets = [(1, 2), (2, 2), (5, 2), (6, 2), (0, 3), (3, 3), (4, 3), (7, 3), (1, 4), (2, 4), (5, 4), (6, 4)]
        f.px(sockets, f.tone(3))
        f.rect(1, 3, 2, 1, WHITE)
        f.rect(5, 3, 2, 1, WHITE)
        f.rect(2, 5, 4, 1, f.tone(4))
        f.px([(2, 6), (5, 6)], f.tone(4))
        f.px([(3, 6), (4, 6)], f.tone(0))
    return fn


def d_creeper_face():
    def fn(f):
        f.rect(1, 2, 2, 2, WHITE)
        f.rect(5, 2, 2, 2, WHITE)
        f.rect(3, 4, 2, 1, f.tone(4))
        f.rect(2, 5, 4, 2, f.tone(4))
        f.px([(2, 7), (5, 7)], f.tone(4))
    return fn


def d_skull_face():
    def fn(f):
        f.rect(1, 3, 2, 2, f.tone(4))
        f.rect(5, 3, 2, 2, f.tone(4))
        f.px([(2, 4), (5, 4)], WHITE)
        f.rect(3, 5, 2, 1, f.tone(4))
        for i in range(6):
            f.put(1 + i, 6, f.tone(4) if i % 2 else f.tone(0))
    return fn


def d_ribs():
    def fn(f):
        for y in (2, 5, 8):
            f.rect(1, y, f.w - 2, 1, f.tone(4))
        f.rect(f.w // 2 - 1, 1, 2, 9, f.tone(1))
    return fn


def d_phantom_face():
    def fn(f):
        f.px([(1, 1), (2, 1), (5, 1), (6, 1)], WHITE)
        f.rect(2, 2, 4, 1, f.tone(4))
    return fn


def d_wing_bones():
    """Lighter 'finger' lines across the wing membrane."""
    def fn(f):
        for x in range(1, f.w, 4):
            for y in range(f.h):
                f.put(x, y, f.tone(1))
    return fn


def d_saddle():
    """Saddle painted on the back of the tamed phantom (no extra cubes)."""
    def fn(f):
        leather, trim = (58, 34, 26, 255), (63, 224, 255, 0)
        cx, cy = f.w // 2, f.h // 2
        f.rect(cx - 2, cy - 3, 4, 6, leather)
        f.rect(cx - 2, cy - 3, 4, 1, trim)
        f.rect(cx - 2, cy + 2, 4, 1, trim)
    return fn


def d_runes(glow):
    """Glowing soul runes on the altar stone."""
    def fn(f):
        g = hx(glow)[:3] + (0,)
        cx = f.w // 2
        for y in range(1, f.h - 1, 2):
            f.put(cx, y, g)
            if f.w > 6 and y % 4 == 1:
                f.px([(cx - 2, y), (cx + 1, y + 1)], g)
    return fn


def d_soul_fire(glow):
    def fn(f):
        g = hx(glow)
        for y in range(1, f.h - 1):
            for x in range(1, f.w - 1):
                f.put(x, y, (g if (x * 7 + y * 3) % 4 else (230, 255, 255, 255))[:3] + (0,))
    return fn


# ================================================================ models
def soul_zombie(pal):
    m = Model("corrupted_zombie", tex_w=64, bounds=(2.5, 3.0), ns=NS)
    root = m.bone("root", [0, 0, 0])
    skin = Soul16(pal, "skin")
    B = humanoid(m, skin.with_deco(front=d_zombie_face()), skin, Soul16(pal, "skin", 0.8), Soul16(pal, "deep"))
    B["body"]["parent"] = root["name"]
    return m


def soul_creeper(pal):
    m = Model("corrupted_creeper", tex_w=64, bounds=(2.0, 2.5), ns=NS)
    root = m.bone("root", [0, 0, 0])
    skin = Soul16(pal, "skin", 1.2)
    B = creeper(m, skin.with_deco(front=d_creeper_face()), skin, Soul16(pal, "deep"))
    B["body"]["parent"] = root["name"]
    return m


def soul_skeleton(pal):
    m = Model("corrupted_skeleton", tex_w=64, bounds=(2.5, 3.0), ns=NS)
    root = m.bone("root", [0, 0, 0])
    bone = Soul16(pal, "bone", 0.6)
    B = humanoid(m, bone.with_deco(front=d_skull_face()), bone.with_deco(front=d_ribs(), back=d_ribs()),
                 bone, bone, arm_w=2, leg_w=2)
    B["body"]["parent"] = root["name"]
    return m


def soul_phantom(pal, saddle=False, name="corrupted_phantom"):
    """Phantom with four wings (front and rear pair), each with a tip segment."""
    m = Model(name, tex_w=64, bounds=(3.0, 1.5), ns=NS)
    root = m.bone("root", [0, 0, 0])
    body_mat = Soul16(pal, "skin")
    if saddle:
        body_mat = body_mat.with_deco(top=d_saddle())
    body = m.bone("body", [0, 8, 0], "root")
    m.cube(body, [-3, 6, -6], [6, 3, 12], body_mat)
    head = m.bone("head", [0, 8, -6], "body")
    m.cube(head, [-4, 6, -11], [8, 3, 5], Soul16(pal, "skin").with_deco(front=d_phantom_face()))
    wing = Soul16(pal, "deep", 0.7).with_deco(top=d_wing_bones())
    tipm = Soul16(pal, "skin", 0.7).with_deco(top=d_wing_bones())
    for side in (-1, 1):
        s = "R" if side < 0 else "L"
        for pair, (z, depth, base_w, tip_w) in (("1", (-7, 6, 6, 10)), ("2", (1, 5, 5, 8))):
            pz = z + depth / 2
            wb = m.bone(f"wing{pair}{s}", [3 * side, 8.5, pz], "body")
            x0 = -3 - base_w if side < 0 else 3
            m.cube(wb, [x0, 8, z], [base_w, 1, depth], wing)
            edge = (3 + base_w) * side
            wt = m.bone(f"wing{pair}{s}Tip", [edge, 8.5, pz], wb["name"])
            m.cube(wt, [edge - tip_w if side < 0 else edge, 8, z], [tip_w, 1, depth], tipm)
    tail = m.bone("tail", [0, 7.5, 6], "body")
    m.cube(tail, [-1, 6, 6], [2, 2, 6], Soul16(pal, "skin", 0.6))
    tail2 = m.bone("tail2", [0, 7, 12], "tail")
    m.cube(tail2, [-1, 6.5, 12], [2, 1, 5], Soul16(pal, "deep", 0.5))
    return m


def healing_altar(pal):
    """Two blocks tall: deepslate pedestal with soul runes, basin of soul fire
    and a floating soul crystal."""
    m = Model(ALTAR, tex_w=64, bounds=(1.5, 2.5), ns=NS)
    glow = pal["glow"]
    stone = Soul16(pal, "stone", 0.6)
    runes = stone.with_deco(sides=d_runes(glow))
    root = m.bone("root", [0, 0, 0])
    m.cube(root, [-7, 0, -7], [14, 3, 14], stone)
    m.cube(root, [-5, 3, -5], [10, 2, 10], stone)
    m.cube(root, [-3, 5, -3], [6, 14, 6], runes)
    m.cube(root, [-5, 19, -5], [10, 2, 10], stone)
    m.cube(root, [-6, 21, -6], [12, 3, 12], stone.with_deco(top=d_soul_fire(glow)))
    crystal = m.bone("crystal", [0, 28, 0], "root")
    m.cube(crystal, [-2, 25, -2], [4, 6, 4], Soul16(pal, "crystal"))
    return m


MODELS = {"zombie": soul_zombie, "creeper": soul_creeper, "skeleton": soul_skeleton, "phantom": soul_phantom}


# ============================================================= behaviour
def mob_id(t, c):
    return f"corrupted_{t}_{c}"


def immunities(extra=()):
    return {"triggers": [{"cause": cause, "deals_damage": False} for cause in IMMUNE_TO + list(extra)]}


def behavior(t, c):
    T, C = TYPES[t], COLORS[c]
    ident = mob_id(t, c)
    base = {
        "minecraft:type_family": {"family": T["family"] + ["monster", "mob", "soul_corrupted"]},
        "minecraft:health": {"value": T["hp"], "max": T["hp"]},
        "minecraft:collision_box": {"width": T["box"][0], "height": T["box"][1]},
        "minecraft:movement": {"value": T["speed"]},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:damage_sensor": immunities(),
        "minecraft:attack": {"damage": T["dmg"], "effect_name": "darkness", "effect_duration": 8},
        "minecraft:loot": {"table": f"loot_tables/{NS}/{ident}.json"},
        "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 7 : 0"},
    }
    if t != "phantom":
        base.update({
            "minecraft:movement.basic": {},
            "minecraft:navigation.walk": {"can_pass_doors": True, "avoid_water": True, "can_walk_in_lava": True,
                                          "can_path_over_lava": True, "is_amphibious": True},
            "minecraft:jump.static": {},
            "minecraft:can_climb": {},
        })
    if T.get("equip"):
        base["minecraft:equipment"] = {"table": f"loot_tables/{NS}/equipment/{T['equip']}.json",
                                       "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0.0}]}
    active = {
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": targets(villagers=(t == "zombie")),
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 1.0},
        "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 8, "probability": 0.02},
        "minecraft:behavior.random_look_around": {"priority": 9},
    }
    groups = {
        # Spawn animation: no AI until it has finished appearing
        f"{NS}:emerging": {"minecraft:timer": {"looping": False, "time": T["emerge"],
                                                "time_down_event": {"event": f"{NS}:emerged"}}},
        f"{NS}:active": active,
    }
    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:emerging"]},
                                     "set_property": {f"{NS}:emerging": True}},
        f"{NS}:emerged": {"remove": {"component_groups": [f"{NS}:emerging"]},
                          "add": {"component_groups": [f"{NS}:active"]},
                          "set_property": {f"{NS}:emerging": False}},
    }
    properties = {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}}
    runtime = None
    if t == "zombie":
        active["minecraft:behavior.melee_attack"] = {"priority": 3, "speed_multiplier": 1.0, "track_target": False}
    elif t == "skeleton":
        base["minecraft:shooter"] = {"def": "minecraft:arrow"}
        active["minecraft:behavior.ranged_attack"] = {"priority": 2, "attack_interval_min": 1.0,
                                                      "attack_interval_max": 3.0, "attack_radius": 15.0}
        active["minecraft:behavior.avoid_mob_type"] = {"priority": 4, "entity_types": [
            {"filters": fam("wolf"), "max_dist": 6, "walk_speed_multiplier": 1.2, "sprint_speed_multiplier": 1.2}]}
    elif t == "phantom":
        # Like a vanilla phantom, but swoops far more often and circles lower
        runtime = "minecraft:phantom"
        base["minecraft:scale"] = {"value": PHANTOM_SCALE}
        base["minecraft:physics"] = {"has_gravity": False}
        base["minecraft:movement.glide"] = {"start_speed": 0.1, "speed_when_turning": 0.2}
        base["minecraft:navigation.float"] = {"can_path_over_water": True}
        base["minecraft:follow_range"] = {"value": 64, "max": 64}
        base["minecraft:damage_sensor"] = immunities(["fall"])
        for k in ("minecraft:behavior.float", "minecraft:behavior.random_stroll", "minecraft:behavior.look_at_player",
                  "minecraft:behavior.random_look_around"):
            del active[k]
        tg = targets(radius=64, villagers=False)
        tg.update({"priority": 1, "scan_interval": 10, "target_search_height": 80, "must_see_forget_duration": 0.5})
        active["minecraft:behavior.nearest_attackable_target"] = tg
        active["minecraft:behavior.swoop_attack"] = {"priority": 2, "damage_reach": 0.4, "speed_multiplier": 1.15,
                                                     "delay_range": [2.0, 5.0]}
        active["minecraft:behavior.circle_around_anchor"] = {
            "priority": 3, "radius_change": 1.0, "radius_adjustment_chance": 0.004,
            "height_adjustment_chance": 0.003, "goal_radius": 1.0, "angle_change": 15.0,
            "radius_range": [3.0, 7.0], "height_offset_range": [-2.0, 3.0], "height_above_target_range": [6.0, 12.0]}
        active["minecraft:behavior.avoid_mob_type"] = {"priority": 1, "entity_types": [
            {"filters": fam("ocelot", "cat"), "max_dist": 16, "walk_speed_multiplier": 1, "sprint_speed_multiplier": 1}]}
    else:
        runtime = "minecraft:creeper"
        properties[f"{NS}:lit"] = {"type": "bool", "default": False}
        active["minecraft:behavior.swell"] = {"priority": 2, "start_distance": 2.5, "stop_distance": 6.0}
        active["minecraft:behavior.melee_attack"] = {"priority": 4, "speed_multiplier": 1.25, "track_target": False}
        active["minecraft:behavior.avoid_mob_type"] = {"priority": 3, "entity_types": [
            {"filters": fam("ocelot", "cat"), "max_dist": 6, "walk_speed_multiplier": 1, "sprint_speed_multiplier": 1.2}]}
        active["minecraft:target_nearby_sensor"] = {
            "inside_range": 2.5, "outside_range": 6.0, "must_see": True,
            "on_inside_range": {"event": "minecraft:start_exploding", "target": "self"},
            "on_outside_range": {"event": "minecraft:stop_exploding", "target": "self"},
            "on_vision_lost_inside_range": {"event": "minecraft:stop_exploding", "target": "self"}}
        groups["minecraft:exploding"] = {"minecraft:explode": {
            "fuse_length": 1.5, "fuse_lit": True, "power": T["power"], "causes_fire": C["fire"],
            "destroy_affected_by_griefing": True}}
        not_lit = {"test": "has_component", "operator": "!=", "value": "minecraft:explode"}
        # soul:lit lets the script spawn the coloured explosion particles
        for ev in ("minecraft:start_exploding", "minecraft:start_exploding_forced"):
            events[ev] = {"sequence": [{"filters": not_lit, "add": {"component_groups": ["minecraft:exploding"]},
                                        "set_property": {f"{NS}:lit": True}}]}
        events["minecraft:stop_exploding"] = {"remove": {"component_groups": ["minecraft:exploding"]},
                                              "set_property": {f"{NS}:lit": False}}

    desc = {"identifier": f"{NS}:{ident}", "is_spawnable": True, "is_summonable": True, "is_experimental": False,
            "properties": properties}
    if runtime:
        desc["runtime_identifier"] = runtime
    return {"format_version": "1.20.80", "minecraft:entity": {
        "description": desc, "component_groups": groups, "components": base, "events": events}}


def mount_behavior():
    """Tameable (bones) and rideable blue phantom. Flies like a happy ghast,
    slightly faster (happy ghast: 0.05). Never spawns naturally."""
    no_damage = [{"cause": cause, "deals_damage": "no"} for cause in IMMUNE_TO + ["fall"]]
    wild = {
        "minecraft:tameable": {"probability": 0.33, "tame_items": "bone",
                               "tame_event": {"event": f"{NS}:on_tame", "target": "self"}},
        "minecraft:behavior.tempt": {"priority": 4, "speed_multiplier": 1.2, "items": ["bone"],
                                     "can_tempt_vertically": True, "within_radius": 12},
    }
    tamed = {
        "minecraft:is_tamed": {},
        "minecraft:rideable": {"seat_count": 1, "family_types": ["player"], "interact_text": "action.interact.ride",
                               "pull_in_entities": False, "seats": {"position": [0.0, 1.35, 0.1]}},
        "minecraft:input_air_controlled": {"backwards_movement_modifier": 0.5, "strafe_speed_modifier": 1.0},
        "minecraft:behavior.follow_owner": {"priority": 5, "speed_multiplier": 1.0, "start_distance": 14,
                                            "stop_distance": 5},
        "minecraft:healable": {"items": [{"item": "bone", "heal_amount": 6}]},
    }
    comps = {
        "minecraft:type_family": {"family": ["soul_mount", "phantom", "mob", "soul_corrupted"]},
        "minecraft:health": {"value": 40, "max": 40},
        "minecraft:scale": {"value": PHANTOM_SCALE},
        "minecraft:collision_box": {"width": 2.0, "height": 1.0},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:can_fly": {},
        "minecraft:flying_speed": {"value": 0.065},
        "minecraft:movement": {"value": 0.065},
        "minecraft:movement.hover": {},
        "minecraft:navigation.hover": {"can_path_over_water": True, "can_sink": False, "can_pass_doors": False,
                                       "can_path_from_air": True, "avoid_water": False, "avoid_damage_blocks": True},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:damage_sensor": {"triggers": no_damage},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:persistent": {},
        "minecraft:leashable": {"soft_distance": 4, "hard_distance": 6, "max_distance": 10},
        "minecraft:loot": {"table": f"loot_tables/{NS}/{MOUNT}.json"},
        "minecraft:behavior.random_hover": {"priority": 8, "xz_dist": 10, "y_dist": 5, "y_offset": -1,
                                            "interval": 1, "hover_height": [2, 6]},
        "minecraft:behavior.look_at_player": {"priority": 9, "look_distance": 8, "probability": 0.05},
        "minecraft:timer": {"looping": False, "time": TYPES["phantom"]["emerge"],
                            "time_down_event": {"event": f"{NS}:emerged"}},
    }
    return {"format_version": "1.21.90", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{MOUNT}", "is_spawnable": True, "is_summonable": True,
                        "is_experimental": False,
                        "properties": {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}}},
        "component_groups": {f"{NS}:wild": wild, f"{NS}:tamed": tamed},
        "components": comps,
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:wild"]},
                                         "set_property": {f"{NS}:emerging": True}},
            f"{NS}:emerged": {"set_property": {f"{NS}:emerging": False}},
            f"{NS}:on_tame": {"remove": {"component_groups": [f"{NS}:wild"]},
                              "add": {"component_groups": [f"{NS}:tamed"]}},
        }}}


def altar_behavior():
    """Healing altar: a static, persistent 1x2 'block' entity. Healing and the
    particle beam are done by the script. Only players can break it; it drops
    itself."""
    return {"format_version": "1.20.80", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{ALTAR}", "is_spawnable": True, "is_summonable": True,
                        "is_experimental": False},
        "components": {
            "minecraft:type_family": {"family": ["soul_altar", "inanimate"]},
            "minecraft:health": {"value": 12, "max": 12},
            "minecraft:collision_box": {"width": 0.9, "height": 2.0},
            "minecraft:physics": {},
            "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
            "minecraft:knockback_resistance": {"value": 1.0},
            "minecraft:movement": {"value": 0},
            "minecraft:persistent": {},
            "minecraft:fire_immune": {},
            "minecraft:damage_sensor": {"triggers": [
                {"on_damage": {"filters": fam("player")}, "deals_damage": True},
                {"cause": "all", "deals_damage": False}]},
            "minecraft:loot": {"table": f"loot_tables/{NS}/{ALTAR}.json"},
        }}}


def altar_recipe():
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": f"{NS}:{ALTAR}"},
        "tags": ["crafting_table"],
        "pattern": ["CLC", "CAC", "CCC"],
        "key": {"C": {"item": "minecraft:cobbled_deepslate"}, "L": {"item": "minecraft:soul_lantern"},
                "A": {"item": "minecraft:golden_apple"}},
        "result": {"item": f"{NS}:{ALTAR}_spawn_egg"}}}


def spawn_rules(t, c):
    T = TYPES[t]
    w = T["weight"] if c == "blue" else max(1, T["weight"] // 2)
    surface = {"minecraft:spawns_on_surface": {}}
    if t != "phantom":
        surface["minecraft:spawns_underground"] = {}
    conds = [
        dict(surface, **{"minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
                         "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
                         "minecraft:weight": {"default": w}, "minecraft:herd": {"min_size": 1, "max_size": 2 if t != "phantom" else 1},
                         "minecraft:biome_filter": {"test": "has_biome_tag", "value": "monster"}}),
        # Each colour also haunts its Nether biome
        dict(surface, **{"minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
                         "minecraft:weight": {"default": 20 if t != "phantom" else 4},
                         "minecraft:herd": {"min_size": 1, "max_size": 3 if t != "phantom" else 1},
                         "minecraft:biome_filter": {"test": "has_biome_tag", "value": NETHER_BIOME[c]}}),
    ]
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": f"{NS}:{mob_id(t, c)}", "population_control": "monster"}, "conditions": conds}}


def loot(items, sword=True):
    pools = [{"rolls": 1, "entries": [{"type": "item", "name": f"minecraft:{item}", "weight": 1, "functions": [
        {"function": "set_count", "count": {"min": lo, "max": hi}},
        {"function": "looting_enchant", "count": {"min": 0, "max": 1}}]}]} for item, lo, hi in items]
    if sword:  # the corrupted soul sword can't be crafted: it only drops from these mobs
        pools.append({"rolls": 1, "conditions": [
            {"condition": "killed_by_player"},
            {"condition": "random_chance_with_looting", "chance": 0.025, "looting_multiplier": 0.01}],
            "entries": [{"type": "item", "name": SWORD, "weight": 1}]})
    return {"pools": pools}


def sword_item():
    # Current item format: the old {"texture": ...} icon form shows up invisible
    return {"format_version": "1.21.40", "minecraft:item": {
        "description": {"identifier": SWORD,
                        "menu_category": {"category": "equipment", "group": "itemGroup.name.sword"}},
        "components": {
            "minecraft:icon": {"textures": {"default": "corrupted_soul_sword"}},
            "minecraft:display_name": {"value": f"item.{SWORD}.name"},
            "minecraft:max_stack_size": {"value": 1},
            "minecraft:hand_equipped": {"value": True},
            "minecraft:damage": {"value": 9},
            "minecraft:durability": {"max_durability": 2031},
            "minecraft:enchantable": {"slot": "sword", "value": 15},
            "minecraft:repairable": {"repair_items": [{"items": ["minecraft:echo_shard"], "repair_amount": 600}]},
            # Same tag as vanilla swords, so animation packs treat it as a sword
            "minecraft:tags": {"tags": ["minecraft:is_sword"]},
            "minecraft:can_destroy_in_creative": {"value": False},
            "minecraft:digger": {"use_efficiency": True, "destroy_speeds": [{"block": "minecraft:web", "speed": 15}]},
        }}}


def script():
    effects, ignite = {}, {}
    for t in TYPES:
        for c, C in COLORS.items():
            effects[f"{NS}:{mob_id(t, c)}"] = [DARKNESS] + C["extra"]
            if C["ignite"]:
                ignite[f"{NS}:{mob_id(t, c)}"] = C["ignite"]
    return f"""// Soul Corrupted: darkness on hit, soul sword, healing altar, coloured creeper blasts.
// Generated by tools/soul_generate.py, edit it there instead.
import {{ system, world }} from "@minecraft/server";

// [effect, duration in ticks, amplifier] applied to whatever the mob hurts
// (melee hit, arrow or explosion).
const HIT_EFFECTS = {json.dumps(effects, indent=2)};

// Seconds the red variants set their victims on fire for.
const IGNITE = {json.dumps(ignite, indent=2)};

const SWORD = "{SWORD}";
const SWORD_AREA = {{ radius: 3, damage: 5 }};
const ALTAR = "{NS}:{ALTAR}";
const ALTAR_RANGE = 10;
const DIMENSIONS = ["overworld", "nether", "the_end"];

function heldItem(player) {{
  try {{
    return player.getComponent("minecraft:equippable")?.getEquipment("Mainhand");
  }} catch {{
    return undefined;
  }}
}}

function particle(dimension, id, location) {{
  try {{
    dimension.spawnParticle(id, location);
  }} catch {{
    // chunk not loaded
  }}
}}

// Sweeping hit: nearby mobs take damage and wither too.
function swordArea(player, victim) {{
  const dimension = victim.dimension;
  const center = victim.location;
  particle(dimension, "{NS}:sweep", {{ x: center.x, y: center.y + 0.8, z: center.z }});
  const nearby = dimension.getEntities({{
    location: center,
    maxDistance: SWORD_AREA.radius,
    excludeFamilies: ["player", "soul_mount", "soul_altar", "inanimate"],
    excludeTypes: ["minecraft:item", "minecraft:xp_orb", "minecraft:arrow"],
  }});
  for (const entity of nearby) {{
    if (entity.id === victim.id || !entity.getComponent("minecraft:health")) continue;
    if (entity.getComponent("minecraft:is_tamed")) continue;
    try {{
      // "magic" so this damage doesn't trigger another sweep
      entity.applyDamage(SWORD_AREA.damage, {{ cause: "magic", damagingEntity: player }});
      entity.addEffect("wither", 60, {{ amplifier: 0, showParticles: true }});
    }} catch {{
      // entity gone
    }}
  }}
}}

world.afterEvents.entityHurt.subscribe((event) => {{
  const attacker = event.damageSource.damagingEntity;
  if (!attacker) return;
  const victim = event.hurtEntity;
  try {{
    const effects = HIT_EFFECTS[attacker.typeId];
    if (effects) {{
      for (const [id, ticks, amplifier] of effects) {{
        victim.addEffect(id, ticks, {{ amplifier, showParticles: true }});
      }}
      if (IGNITE[attacker.typeId]) victim.setOnFire(IGNITE[attacker.typeId], true);
      return;
    }}
    if (attacker.typeId === "minecraft:player" && event.damageSource.cause === "entityAttack" &&
        heldItem(attacker)?.typeId === SWORD) {{
      victim.addEffect("wither", 100, {{ amplifier: 1, showParticles: true }});
      victim.setOnFire(5, true);
      swordArea(attacker, victim);
    }}
  }} catch {{
    // victim died or cannot receive effects
  }}
}});

// Healing altar: beam of particles to every player within range, +1 health per second.
let altarTick = 0;
system.runInterval(() => {{
  altarTick += 4;
  const heal = altarTick % 20 === 0;
  for (const id of DIMENSIONS) {{
    let dimension;
    try {{
      dimension = world.getDimension(id);
    }} catch {{
      continue;
    }}
    for (const altar of dimension.getEntities({{ type: ALTAR }})) {{
      const from = {{ x: altar.location.x, y: altar.location.y + 1.75, z: altar.location.z }};
      for (const player of dimension.getPlayers({{ location: altar.location, maxDistance: ALTAR_RANGE }})) {{
        const to = {{ x: player.location.x, y: player.location.y + 1.0, z: player.location.z }};
        const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
        const steps = Math.max(1, Math.floor(Math.hypot(dx, dy, dz) / 0.35));
        for (let i = 0; i <= steps; i++) {{
          const t = i / steps;
          particle(dimension, "{NS}:heal_beam", {{ x: from.x + dx * t, y: from.y + dy * t, z: from.z + dz * t }});
        }}
        if (!heal) continue;
        try {{
          const health = player.getComponent("minecraft:health");
          if (health && health.currentValue > 0 && health.currentValue < health.effectiveMax) {{
            health.setCurrentValue(Math.min(health.effectiveMax, health.currentValue + 1));
            particle(dimension, "{NS}:heal_spark", to);
          }}
        }} catch {{
          // player left
        }}
      }}
    }}
  }}
}}, 4);

// Coloured explosion particles: a lit creeper that disappears has exploded.
const litCreepers = new Map();
let scan = 0;
system.runInterval(() => {{
  scan++;
  for (const id of DIMENSIONS) {{
    let dimension;
    try {{
      dimension = world.getDimension(id);
    }} catch {{
      continue;
    }}
    for (const creeper of dimension.getEntities({{ families: ["soul_creeper"] }})) {{
      let lit = false;
      try {{
        lit = creeper.getProperty("{NS}:lit") === true;
      }} catch {{
        // not ours
      }}
      if (!lit) {{
        litCreepers.delete(creeper.id);
        continue;
      }}
      const info = litCreepers.get(creeper.id) ?? {{ ticks: 0 }};
      info.ticks += 2;
      info.scan = scan;
      info.dimension = dimension;
      info.location = creeper.location;
      info.color = creeper.typeId.split("_").pop();
      litCreepers.set(creeper.id, info);
    }}
  }}
  for (const [key, info] of litCreepers) {{
    if (info.scan === scan) continue;
    if (info.ticks >= 20) {{
      const {{ x, y, z }} = info.location;
      particle(info.dimension, `{NS}:explosion_${{info.color}}`, {{ x, y: y + 0.8, z }});
    }}
    litCreepers.delete(key);
  }}
}}, 2);
"""


# ============================================================= resources
def kf(d):
    """Keyframes with smooth (catmull-rom) interpolation."""
    return {str(k): {"post": v, "lerp_mode": "catmullrom"} for k, v in d.items()}


WALK = "query.modified_distance_moved * 38.17"
SPEED = "variable.s_speed"
TURN = "variable.s_turn"
SMOOTHING = [
    "variable.s_speed = math.lerp(variable.s_speed ?? 0.0, query.modified_move_speed, 0.1);",
    "variable.s_turn = math.lerp(variable.s_turn ?? 0.0, math.clamp(query.yaw_speed, -120.0, 120.0), 0.05);",
    "variable.s_attack = math.lerp(variable.s_attack ?? 0.0, math.sin(variable.attack_time * 180.0), 0.35);",
]
FLAP = "query.life_time * 300.0"

ANIMS = {
    "look_at_target": {"loop": True, "bones": {
        "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0.0]}}},
    "soul_particles": {"loop": True, "animation_length": 0.2,
                       "particle_effects": {"0.0": [{"effect": "wisps"}, {"effect": "drips"}]}},

    "zombie_walk": {"loop": True, "bones": {
        "rightLeg": {"rotation": [f"math.cos({WALK}) * 45.0 * {SPEED}", 0.0, 0.0]},
        "leftLeg": {"rotation": [f"math.cos({WALK}) * -45.0 * {SPEED}", 0.0, 0.0]},
        "body": {"rotation": [f"{SPEED} * 6.0", 0.0, f"math.sin({WALK} * 0.5) * 3.5 * {SPEED}"]},
        "root": {"position": [0.0, f"math.abs(math.sin({WALK})) * 0.5 * {SPEED}", 0.0]}}},
    "zombie_arms": {"loop": True, "bones": {
        "rightArm": {"rotation": [f"-85.0 + math.sin(query.life_time * 60.0) * 2.5 + math.cos({WALK}) * 6.0 * {SPEED}",
                                  "-6.0", "math.sin(query.life_time * 45.0) * 2.0 + 4.0"]},
        "leftArm": {"rotation": [f"-85.0 - math.sin(query.life_time * 60.0) * 2.5 - math.cos({WALK}) * 6.0 * {SPEED}",
                                 "6.0", "-math.sin(query.life_time * 45.0) * 2.0 - 4.0"]}}},
    "zombie_idle": {"loop": True, "bones": {
        "head": {"rotation": ["math.sin(query.life_time * 18.0) * 2.5", 0.0, "math.sin(query.life_time * 24.0) * 4.0"]},
        "body": {"scale": ["1.0 + math.sin(query.life_time * 80.0) * 0.01", "1.0", "1.0 + math.sin(query.life_time * 80.0) * 0.01"]}}},
    "zombie_attack": {"loop": True, "bones": {
        "rightArm": {"rotation": ["-variable.s_attack * 40.0", 0.0, 0.0]},
        "leftArm": {"rotation": ["-variable.s_attack * 30.0", 0.0, 0.0]},
        "root": {"rotation": ["variable.s_attack * 8.0", 0.0, 0.0]}}},
    "zombie_emerge": {"loop": "hold_on_last_frame", "animation_length": 1.2, "bones": {
        "root": {"position": kf({0.0: [0, -30, 0], 0.35: [0, -20, 0], 0.75: [0, -8, 0], 1.0: [0, -1, 0], 1.2: [0, 0, 0]}),
                 "rotation": kf({0.0: [28, 0, 0], 0.45: [20, 0, -6], 0.85: [8, 0, 4], 1.2: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-170, 0, 10], 0.35: [-150, 0, 18], 0.7: [-160, 0, 8], 1.0: [-115, 0, 6],
                                     1.2: [-85, -6, 4]})},
        "leftArm": {"rotation": kf({0.0: [-150, 0, -16], 0.35: [-170, 0, -8], 0.7: [-145, 0, -18], 1.0: [-110, 0, -6],
                                    1.2: [-85, 6, -4]})},
        "head": {"rotation": kf({0.0: [-28, 0, 0], 0.6: [-12, 8, 8], 1.0: [3, -4, -4], 1.2: [0, 0, 0]})}}},

    "creeper_walk": {"loop": True, "bones": {
        "leg0": {"rotation": [f"math.cos({WALK}) * 50.0 * {SPEED}", 0.0, 0.0]},
        "leg1": {"rotation": [f"math.cos({WALK}) * -50.0 * {SPEED}", 0.0, 0.0]},
        "leg2": {"rotation": [f"math.cos({WALK}) * -50.0 * {SPEED}", 0.0, 0.0]},
        "leg3": {"rotation": [f"math.cos({WALK}) * 50.0 * {SPEED}", 0.0, 0.0]},
        "body": {"rotation": [f"{SPEED} * 14.0", 0.0, f"math.clamp({TURN} * 0.1, -9.0, 9.0)"],
                 "position": [0.0, f"math.abs(math.sin({WALK})) * 0.4 * {SPEED}", 0.0]},
        "head": {"rotation": [f"-{SPEED} * 10.0 + math.sin({WALK}) * 2.5 * {SPEED}", 0.0,
                              f"math.clamp({TURN} * 0.05, -5.0, 5.0)"]}}},
    "creeper_idle": {"loop": True, "bones": {
        "body": {"scale": ["1.0 + math.sin(query.life_time * 80.0) * 0.02", "1.0 + math.sin(query.life_time * 80.0 + 90.0) * 0.012",
                           "1.0 + math.sin(query.life_time * 80.0) * 0.02"]},
        "head": {"rotation": [0.0, 0.0, "math.sin(query.life_time * 28.0) * 2.5"]}}},
    "creeper_spawn": {"loop": "hold_on_last_frame", "animation_length": 0.9, "bones": {
        "root": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.35: [0.7, 0.65, 0.7], 0.6: [1.12, 1.1, 1.12],
                              0.75: [0.96, 0.97, 0.96], 0.9: [1, 1, 1]}),
                 "rotation": kf({0.0: [0, -180, 0], 0.6: [0, -12, 0], 0.9: [0, 0, 0]})}}},

    "skeleton_walk": {"loop": True, "bones": {
        "rightLeg": {"rotation": [f"math.cos({WALK}) * 40.0 * {SPEED}", 0.0, 0.0]},
        "leftLeg": {"rotation": [f"math.cos({WALK}) * -40.0 * {SPEED}", 0.0, 0.0]},
        "body": {"rotation": [f"{SPEED} * 4.0", f"math.sin({WALK}) * 4.0 * {SPEED}", 0.0]}}},
    "skeleton_arms": {"loop": True, "bones": {
        "rightArm": {"rotation": [f"math.cos({WALK}) * -32.0 * {SPEED}", 0.0, "math.cos(query.life_time * 70.0) * 2.0 + 3.0"]},
        "leftArm": {"rotation": [f"math.cos({WALK}) * 32.0 * {SPEED}", 0.0, "-math.cos(query.life_time * 70.0) * 2.0 - 3.0"]}}},
    "skeleton_aim": {"loop": True, "bones": {
        "rightArm": {"rotation": ["query.target_x_rotation - 90.0", "query.target_y_rotation - 5.73", 0.0]},
        "leftArm": {"rotation": ["query.target_x_rotation - 90.0", "query.target_y_rotation + 28.65", 0.0]}}},
    "skeleton_idle": {"loop": True, "bones": {
        "head": {"rotation": ["math.sin(query.life_time * 15.0) * 2.0", "math.sin(query.life_time * 12.0) * 10.0",
                              "math.sin(query.life_time * 21.0) * 3.0"]}}},
    "skeleton_emerge": {"loop": "hold_on_last_frame", "animation_length": 1.2, "bones": {
        "root": {"position": kf({0.0: [0, -32, 0], 0.4: [0, -21, 0], 0.8: [0, -8, 0], 1.05: [0, -1, 0], 1.2: [0, 0, 0]}),
                 "rotation": kf({0.0: [18, 0, 8], 0.4: [14, 0, -8], 0.8: [8, 0, 6], 1.05: [3, 0, -3], 1.2: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-175, 0, 12], 0.4: [-158, 0, 24], 0.8: [-160, 0, 10], 1.05: [-60, 0, 8], 1.2: [0, 0, 3]})},
        "leftArm": {"rotation": kf({0.0: [-160, 0, -20], 0.4: [-175, 0, -10], 0.8: [-150, 0, -20], 1.05: [-50, 0, -6], 1.2: [0, 0, -3]})},
        "head": {"rotation": kf({0.0: [-35, 0, 0], 0.4: [-18, 18, 10], 0.8: [-8, -18, -10], 1.05: [6, 0, 0], 1.2: [0, 0, 0]})}}},

    # ---- phantom: two pairs of wings flapping out of phase, tips lag behind
    "phantom_fly": {"loop": True, "bones": dict(
        {f"wing{p}{s}": {"rotation": [0.0, 0.0, f"{sg}math.sin({FLAP}{ph}) * 20.0"]}
         for p, ph in (("1", ""), ("2", " - 70.0")) for s, sg in (("R", ""), ("L", "-"))},
        **{f"wing{p}{s}Tip": {"rotation": [0.0, 0.0, f"{sg}math.sin({FLAP}{ph} - 50.0) * 18.0"]}
           for p, ph in (("1", ""), ("2", " - 70.0")) for s, sg in (("R", ""), ("L", "-"))},
        body={"position": [0.0, f"math.sin({FLAP} + 90.0) * 0.6", 0.0],
              "rotation": [f"math.clamp(-query.vertical_speed * 4.0, -20.0, 20.0)", 0.0,
                           f"math.clamp({TURN} * 0.12, -15.0, 15.0)"]},
        tail={"rotation": [f"math.sin({FLAP} - 60.0) * 7.0", f"math.sin(query.life_time * 90.0) * 5.0", 0.0]},
        tail2={"rotation": [f"math.sin({FLAP} - 110.0) * 9.0", 0.0, 0.0]},
    )},
    "phantom_spawn": {"loop": "hold_on_last_frame", "animation_length": 0.8, "bones": {
        "root": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.45: [1.1, 1.1, 1.1], 0.65: [0.96, 0.96, 0.96], 0.8: [1, 1, 1]}),
                 "rotation": kf({0.0: [0, -180, 0], 0.5: [0, -10, 0], 0.8: [0, 0, 0]})}}},

    # ---- healing altar: floating, spinning soul crystal + rising soul wisps
    "altar_float": {"loop": True, "bones": {
        "crystal": {"rotation": [0.0, "query.life_time * 45.0", 0.0],
                    "position": [0.0, "math.sin(query.life_time * 90.0) * 1.0", 0.0]}}},
    "altar_particles": {"loop": True, "animation_length": 0.25,
                        "particle_effects": {"0.0": [{"effect": "wisps"}]}},
}

CONTROLLERS = {
    "zombie": (["zombie_emerge"], ["zombie_walk", "zombie_arms", "zombie_idle", "zombie_attack"]),
    "creeper": (["creeper_spawn"], ["creeper_walk", "creeper_idle"]),
    "skeleton": (["skeleton_emerge"], ["skeleton_walk", "skeleton_idle",
                                       {"skeleton_arms": "1.0 - variable.s_aim"}, {"skeleton_aim": "variable.s_aim"}]),
    "phantom": (["phantom_spawn"], ["phantom_fly"]),
}


def controllers():
    prop = f"query.property('{NS}:emerging')"
    out = {}
    for t, (spawn, alive) in CONTROLLERS.items():
        out[f"controller.animation.{NS}.{t}"] = {"initial_state": "start", "states": {
            "start": {"transitions": [{"emerging": prop}, {"alive": f"!{prop}"}]},
            "emerging": {"animations": spawn, "particle_effects": [{"effect": "burst"}],
                         "transitions": [{"alive": f"!{prop}"}], "blend_transition": 0.3},
            "alive": {"animations": alive, "blend_transition": 0.3},
        }}
    return {"format_version": "1.10.0", "animation_controllers": out}


def particle_effect(ident, rgb, comps, size=0.14):
    fade = f"{size} * (1.0 - math.pow(variable.particle_age / variable.particle_lifetime, 2.0))"
    base = {
        "minecraft:emitter_local_space": {"position": False, "rotation": False},
        "minecraft:particle_appearance_tinting": {"color": list(rgb) + [1.0]},
        "minecraft:particle_appearance_billboard": {
            "size": [fade, fade], "facing_camera_mode": "rotate_xyz",
            "uv": {"texture_width": 8, "texture_height": 8, "uv": [0, 0], "uv_size": [8, 8]}},
    }
    base.update(comps)
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": f"{NS}:{ident}",
                        "basic_render_parameters": {"material": "particles_alpha",
                                                    "texture": "textures/particle/soul_spark"}},
        "components": base}}


def once(n):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": 0.1}}


def particles():
    out = {}
    body = {"offset": [0, 0.9, 0], "half_dimensions": [0.3, 0.7, 0.3]}
    for c, C in COLORS.items():
        rgb = C["rgb"]
        out[f"wisp_{c}"] = particle_effect(f"wisp_{c}", rgb, dict(once(2), **{
            "minecraft:emitter_shape_box": dict(body, direction=[0, 1, 0]),
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.4)"},
            "minecraft:particle_initial_speed": "math.random(0.2, 0.5)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.8, 0], "linear_drag_coefficient": 0.8}}))
        out[f"drip_{c}"] = particle_effect(f"drip_{c}", rgb, dict(once(1), **{
            "minecraft:emitter_shape_box": dict(body, direction="outwards"),
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.6, 1.0)"},
            "minecraft:particle_initial_speed": "math.random(0.3, 0.8)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -6.0, 0], "linear_drag_coefficient": 1.0},
            "minecraft:particle_motion_collision": {"collision_radius": 0.05, "coefficient_of_restitution": 0.2,
                                                    "collision_drag": 4.0}}), size=0.1)
        out[f"burst_{c}"] = particle_effect(f"burst_{c}", rgb, dict(once(45), **{
            "minecraft:emitter_shape_disc": {"offset": [0, 0.1, 0], "radius": 0.8, "plane_normal": "y",
                                             "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.4)"},
            "minecraft:particle_initial_speed": "math.random(1.0, 2.5)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 2.0, 0], "linear_drag_coefficient": 2.0}}),
            size=0.18)
        out[f"explosion_{c}"] = particle_effect(f"explosion_{c}", rgb, dict(once(160), **{
            "minecraft:emitter_shape_sphere": {"radius": 0.6, "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.9, 1.8)"},
            "minecraft:particle_initial_speed": "math.random(3.0, 9.0)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -1.5, 0], "linear_drag_coefficient": 2.2}}),
            size=0.3)
    blue = COLORS["blue"]["rgb"]
    out["heal_beam"] = particle_effect("heal_beam", (0.55, 1.0, 0.85), dict(once(1), **{
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.3},
        "minecraft:particle_initial_speed": 0.0}), size=0.11)
    out["heal_spark"] = particle_effect("heal_spark", (0.55, 1.0, 0.7), dict(once(6), **{
        "minecraft:emitter_shape_sphere": {"radius": 0.4, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.7},
        "minecraft:particle_initial_speed": 0.6,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.0, 0], "linear_drag_coefficient": 1.5}}),
        size=0.14)
    out["sweep"] = particle_effect("sweep", blue, dict(once(36), **{
        "minecraft:emitter_shape_disc": {"radius": 0.3, "plane_normal": "y", "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.45},
        "minecraft:particle_initial_speed": 7.0,
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5.0}}), size=0.16)
    out["altar_wisp"] = particle_effect("altar_wisp", blue, dict(once(2), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 1.5, 0], "radius": 0.35, "plane_normal": "y",
                                         "direction": [0, 1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.3)"},
        "minecraft:particle_initial_speed": "math.random(0.3, 0.6)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.6, 0], "linear_drag_coefficient": 0.8}}),
        size=0.12)
    return out


CREEPER_SWELL = [
    "variable.wobble = Math.sin(query.swell_amount * 5730) * query.swell_amount * 0.01 + 1.0;",
    "variable.swelled = Math.pow(Math.clamp(query.swell_amount, 0.0, 1.0), 4.0);",
    "variable.scale_xz = (1.0 + variable.swelled * 0.4) * variable.wobble;",
    "variable.scale_y = (1.0 + variable.swelled * 0.1) / variable.wobble;",
    "variable.flash = math.mod(math.round(query.swell_amount * 10.0), 2.0) * 0.5;",
]


def client_entity(ident, t, c, texture=None, egg=None):
    pre = list(SMOOTHING)
    if t == "skeleton":
        pre.append("variable.s_aim = math.lerp(variable.s_aim ?? 0.0, query.has_target ? 1.0 : 0.0, 0.08);")
    scripts = {"pre_animation": pre, "animate": ["look", "controller", "soul_particles"]}
    rc = "controller.render.soul.default"
    if t == "creeper":
        rc = "controller.render.soul.creeper"
        scripts["pre_animation"] += CREEPER_SWELL
        scripts.update({"scalex": "variable.scale_xz", "scaley": "variable.scale_y", "scalez": "variable.scale_xz"})
    anims = {"look": f"animation.{NS}.look_at_target", "controller": f"controller.animation.{NS}.{t}",
             "soul_particles": f"animation.{NS}.soul_particles"}
    spawn, alive = CONTROLLERS[t]
    for entry in spawn + alive:
        for name in ([entry] if isinstance(entry, str) else entry):
            anims[name] = f"animation.{NS}.{name}"
    tones = COLORS[c]["tones"]
    desc = {
        "identifier": f"{NS}:{ident}",
        "materials": {"default": "entity_emissive_alpha"},
        "textures": {"default": f"textures/entity/{NS}/{texture or ident}"},
        "geometry": {"default": f"geometry.{NS}.corrupted_{t}"},
        "animations": anims,
        "particle_effects": {"wisps": f"{NS}:wisp_{c}", "drips": f"{NS}:drip_{c}", "burst": f"{NS}:burst_{c}"},
        "scripts": scripts,
        "render_controllers": [rc],
        "spawn_egg": egg or {"base_color": tones[1], "overlay_color": tones[4]},
    }
    if TYPES.get(t, {}).get("equip"):
        desc["enable_attachables"] = True
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def altar_client():
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": f"{NS}:{ALTAR}",
        "materials": {"default": "entity_emissive_alpha"},
        "textures": {"default": f"textures/entity/{NS}/{ALTAR}"},
        "geometry": {"default": f"geometry.{NS}.{ALTAR}"},
        "animations": {"float": f"animation.{NS}.altar_float", "particles": f"animation.{NS}.altar_particles"},
        "particle_effects": {"wisps": f"{NS}:altar_wisp"},
        "scripts": {"animate": ["float", "particles"]},
        "render_controllers": ["controller.render.soul.default"],
        "spawn_egg": {"texture": "healing_altar_egg"},
    }}}


RENDER_CONTROLLERS = {"format_version": "1.8.0", "render_controllers": {
    "controller.render.soul.default": {
        "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
    "controller.render.soul.creeper": {
        "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
        "overlay_color": {"r": "variable.flash", "g": "variable.flash", "b": "variable.flash", "a": "variable.flash"}},
}}


# ================================================================ images
def pixel_art(rows, palette):
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                img.putpixel((x, y), hx(palette[ch]))
    return img


SWORD_ROWS = [
    "..............OO",
    ".............OWO",
    "............OWLO",
    "...........OWLBO",
    "..........OWLBO.",
    ".........OWLDO..",
    "........OWLBO...",
    ".......OWLBO....",
    "..OO..OWLDO.....",
    "..OCOOWLBO......",
    "...OCCWBO.......",
    "....OHCCO.......",
    "...OHOOCCO......",
    "..OHO...OCO.....",
    ".OPO.....OO.....",
    "..O.............",
]
SWORD_COLORS = {"O": "#0d1b28", "W": "#f0feff", "L": "#7fe8f7", "B": "#2a8fb0", "D": "#3fe0ff",
                "C": "#3fe0ff", "H": "#3a2747", "P": "#a6f4ff"}

ALTAR_EGG_ROWS = [
    "................",
    ".......CC.......",
    "......CWWC......",
    ".......CC.......",
    "....SSSSSSSS....",
    "....SFFFFFFS....",
    ".....SSSSSS.....",
    "......SRRS......",
    "......SRRS......",
    "......SRRS......",
    "......SRRS......",
    ".....SSSSSS.....",
    "....SSSSSSSS....",
    "...SSSSSSSSSS...",
    "...TTTTTTTTTT...",
    "................",
]
ALTAR_EGG_COLORS = {"C": "#3fe0ff", "W": "#effdff", "S": "#454b59", "T": "#2a2e38", "F": "#7fe8f7", "R": "#3fe0ff"}

SPARK_ROWS = ["...##...", "..####..", ".######.", "########", "########", ".######.", "..####..", "...##..."]


def pack_icon():
    rows = ["................",
            "....AAAAAAAA....",
            "...ABBBBBBBBA...",
            "..ABBCBBBBCBBA..",
            "..ABWWBBBBWWBA..",
            "..ABBBBBBBBBBA..",
            "..ABBBDDDDBBBA..",
            "..ABBBDWWDBBBA..",
            "..ABBBBBBBBBBA..",
            "...ABBBBBBBBA...",
            "....ABBCCBBA....",
            ".....ABBBBA.....",
            "......ABBA......",
            ".......AA.......",
            "................",
            "................"]
    return pixel_art(rows, {"A": "#178aa6", "B": "#a3e6ee", "C": "#2fb2c8", "W": "#ffffff",
                            "D": "#178aa6"}).resize((128, 128), Image.NEAREST)


def opaque(img):
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, al = px[x, y]
            if al < 255 and (al > 0 or r or g or b):
                px[x, y] = (r, g, b, 255)
    return out


def top_preview(model, img, path, scale=8):
    """Top-down view (for the phantom)."""
    cubes = [c for b in model.geos["default"] for c in b["cubes"]]
    xs = [c.origin[0] for c in cubes] + [c.origin[0] + c.size[0] for c in cubes]
    zs = [c.origin[2] for c in cubes] + [c.origin[2] + c.size[2] for c in cubes]
    minx, minz = min(xs) - 1, min(zs) - 1
    W, H = int(max(xs) - minx + 1), int(max(zs) - minz + 1)
    out = Image.new("RGBA", (W * scale, H * scale), (60, 70, 90, 255))
    for c in sorted(cubes, key=lambda c: c.origin[1] + c.size[1]):
        w, h, d = c.size
        u, v = c.uv
        face = img.crop((u + d, v, u + d + w, v + d)).resize((w * scale, d * scale), Image.NEAREST)
        out.alpha_composite(face, (int((c.origin[0] - minx) * scale), int((c.origin[2] - minz) * scale)))
    out.save(path)


# ================================================================== build
def lang(es):
    lines = ["pack.name=Soul Corrupted", "pack.description=Mobs de alma corrupta", ""]
    for t, T in TYPES.items():
        for c, C in COLORS.items():
            name = f"{T['es']} ({C['es']})" if es else f"{T['en']} ({C['en']})"
            lines.append(f"entity.{NS}:{mob_id(t, c)}.name={name}")
            lines.append(f"item.spawn_egg.entity.{NS}:{mob_id(t, c)}.name={'Generar ' if es else 'Spawn '}{name}")
    mount = "Phantom de Alma Domable" if es else "Tameable Soul Phantom"
    altar = "Altar de Curación" if es else "Healing Altar"
    lines += [f"entity.{NS}:{MOUNT}.name={mount}",
              f"item.spawn_egg.entity.{NS}:{MOUNT}.name={'Generar ' if es else 'Spawn '}{mount}",
              f"entity.{NS}:{ALTAR}.name={altar}",
              f"item.spawn_egg.entity.{NS}:{ALTAR}.name={altar}",
              f"item.{SWORD}.name={'Espada de Alma Corrupta' if es else 'Corrupted Soul Sword'}",
              f"action.interact.ride={'Montar' if es else 'Ride'}"]
    return "\n".join(lines) + "\n"


def manifest(kind):
    if kind == "bp":
        return {"format_version": 2, "header": {
            "name": "Soul Corrupted (Behavior)",
            "description": "Mobs de alma corrupta, phantom montable, altar de curación y espada.",
            "uuid": UUID["bp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "data", "uuid": UUID["bp_data"], "version": VERSION},
                        {"type": "script", "language": "javascript", "uuid": UUID["bp_script"], "version": VERSION,
                         "entry": "scripts/main.js"}],
            "dependencies": [{"uuid": UUID["rp_header"], "version": VERSION},
                             {"module_name": "@minecraft/server", "version": SCRIPT_API}]}
    return {"format_version": 2, "header": {
        "name": "Soul Corrupted (Resources)", "description": "Modelos, texturas 16x16 y animaciones.",
        "uuid": UUID["rp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUID["bp_header"], "version": VERSION}]}


def save_png(img, *parts):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def main():
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    prev = "--preview" in sys.argv
    prev_dir = os.path.join(ROOT, "previews", "soul")
    if prev:
        shutil.rmtree(prev_dir, ignore_errors=True)
        os.makedirs(prev_dir)
    tex_dir = os.path.join(RP, f"textures/entity/{NS}")
    names = []
    for ti, t in enumerate(TYPES):
        for ci, (c, C) in enumerate(COLORS.items()):
            model = MODELS[t](C)
            img = model.build(seed=101 + ti * 31 + ci)
            ident = mob_id(t, c)
            save_png(img, tex_dir, f"{ident}.png")
            if ci == 0:  # all colours share one geometry
                write(os.path.join(RP, "models/entity", f"corrupted_{t}.geo.json"), model.geometry_json())
            write(os.path.join(RP, "entity", f"{ident}.entity.json"), client_entity(ident, t, c))
            write(os.path.join(BP, "entities", f"{ident}.json"), behavior(t, c))
            write(os.path.join(BP, "spawn_rules", f"{ident}.json"), spawn_rules(t, c))
            write(os.path.join(BP, f"loot_tables/{NS}", f"{ident}.json"), loot(TYPES[t]["loot"]))
            if prev:
                if t == "phantom":
                    top_preview(model, opaque(img), os.path.join(prev_dir, f"{ident}.png"))
                else:
                    preview(model, opaque(img), os.path.join(prev_dir, f"{ident}.png"))
                names.append(ident)

    # Rideable phantom (blue, saddle painted on its back)
    blue = COLORS["blue"]
    mount_model = soul_phantom(blue, saddle=True, name="corrupted_phantom")
    mount_img = mount_model.build(seed=777)
    save_png(mount_img, tex_dir, f"{MOUNT}.png")
    write(os.path.join(RP, "entity", f"{MOUNT}.entity.json"),
          client_entity(MOUNT, "phantom", "blue", egg={"base_color": blue["tones"][0], "overlay_color": "#3a221a"}))
    write(os.path.join(BP, "entities", f"{MOUNT}.json"), mount_behavior())
    write(os.path.join(BP, f"loot_tables/{NS}", f"{MOUNT}.json"), loot([("phantom_membrane", 1, 2)], sword=False))

    # Healing altar
    altar = healing_altar(blue)
    altar_img = altar.build(seed=4242)
    save_png(altar_img, tex_dir, f"{ALTAR}.png")
    write(os.path.join(RP, "models/entity", f"{ALTAR}.geo.json"), altar.geometry_json())
    write(os.path.join(RP, "entity", f"{ALTAR}.entity.json"), altar_client())
    write(os.path.join(BP, "entities", f"{ALTAR}.json"), altar_behavior())
    write(os.path.join(BP, f"loot_tables/{NS}", f"{ALTAR}.json"),
          {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": f"{NS}:{ALTAR}_spawn_egg", "weight": 1}]}]})
    write(os.path.join(BP, "recipes", f"{ALTAR}.json"), altar_recipe())
    if prev:
        top_preview(mount_model, opaque(mount_img), os.path.join(prev_dir, f"{MOUNT}.png"))
        preview(altar, opaque(altar_img), os.path.join(prev_dir, f"{ALTAR}.png"))
        names += [MOUNT, ALTAR]

    write(os.path.join(BP, f"loot_tables/{NS}/equipment/bow.json"),
          {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:bow", "weight": 1}]}]})
    for name, effect in particles().items():
        write(os.path.join(RP, "particles", f"{name}.json"), effect)
    save_png(pixel_art(SPARK_ROWS, {"#": "#ffffff"}), RP, "textures/particle/soul_spark.png")
    write(os.path.join(RP, "animations/soul.animation.json"), {"format_version": "1.8.0", "animations": {
        f"animation.{NS}.{n}": a for n, a in ANIMS.items()}})
    write(os.path.join(RP, "animation_controllers/soul.animation_controllers.json"), controllers())
    write(os.path.join(RP, "render_controllers/soul.render_controllers.json"), RENDER_CONTROLLERS)

    # Sword + item atlas
    write(os.path.join(BP, "items/corrupted_soul_sword.json"), sword_item())
    sword = pixel_art(SWORD_ROWS, SWORD_COLORS)
    save_png(sword, RP, "textures/items/corrupted_soul_sword.png")
    save_png(pixel_art(ALTAR_EGG_ROWS, ALTAR_EGG_COLORS), RP, "textures/items/healing_altar_egg.png")
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "soul_corrupted", "texture_name": "atlas.items",
        "texture_data": {"corrupted_soul_sword": {"textures": "textures/items/corrupted_soul_sword"},
                         "healing_altar_egg": {"textures": "textures/items/healing_altar_egg"}}})

    write(os.path.join(BP, "scripts/main.js"), script())
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["en_US", "es_ES", "es_MX"])
        write(os.path.join(pack, "texts/en_US.lang"), lang(False))
        write(os.path.join(pack, "texts/es_ES.lang"), lang(True))
        write(os.path.join(pack, "texts/es_MX.lang"), lang(True))
        save_png(pack_icon(), pack, "pack_icon.png")
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(RP, "manifest.json"), manifest("rp"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "SoulCorrupted.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    if prev:
        sheet(prev_dir, os.path.join(ROOT, "docs", "soul_preview.png"), cols=3, names=names)
        sword.resize((256, 256), Image.NEAREST).save(os.path.join(ROOT, "docs", "soul_sword.png"))
    print("Built", len(TYPES) * len(COLORS), "soul mobs + mount + altar + sword ->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
