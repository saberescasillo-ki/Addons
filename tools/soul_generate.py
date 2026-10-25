"""Builds the Soul Corrupted add-on (behavior pack + resource pack + .mcaddon).

    python3 tools/soul_generate.py            # regenerate everything
    python3 tools/soul_generate.py --preview  # also write docs/soul_preview.png
"""
import json
import math
import os
import random
import shutil
import sys
import zipfile

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import fam, preview, sheet, targets, write  # noqa: E402
from models import Model, creeper, humanoid  # noqa: E402
from textures import FACE_SHADE, SIDES, hx, mix, shade  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "SoulCorrupted_BP")
RP = os.path.join(ROOT, "SoulCorrupted_RP")
DIST = os.path.join(ROOT, "dist")

NS = "soul"
RES = 1  # 1 texel per model pixel, like vanilla (16x16-style) mob textures
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 0]
SCRIPT_API = "1.11.0"
UUID = {
    "bp_header": "c1d2e3f4-0a1b-4c2d-8e3f-a4b5c6d7e8f9",
    "bp_data": "d2e3f405-1b2c-4d3e-9f40-b5c6d7e8f90a",
    "bp_script": "e3f40516-2c3d-4e4f-a051-c6d7e8f90a1b",
    "rp_header": "f4051627-3d4e-4f50-b162-d7e8f90a1b2c",
    "rp_res": "05162738-4e5f-4061-8273-e8f90a1b2c3d",
}

# Glow colours. Glowing texels are written with a low alpha: the
# entity_emissive_alpha material renders them at full brightness.
COLORS = {
    "blue": dict(es="Azul", en="Blue", glow="#3fe0ff", core="#e6fdff", flesh="#2c5470", flesh2="#3d7396",
                 cloth="#1c2a44", cloth2="#2a3d63", pants="#121827", pants2="#1d283b", bone="#9db6c8", bone2="#c9dbe6",
                 extra=[["slowness", 60, 0]], ignite=0, fire=False, rgb=(0.25, 0.88, 1.0)),
    "red": dict(es="Roja", en="Red", glow="#ff3d2e", core="#ffe6dc", flesh="#5a2630", flesh2="#7d3540",
                cloth="#2a1420", cloth2="#45202e", pants="#1a0d13", pants2="#2a151d", bone="#c3a29d", bone2="#e3cbc5",
                extra=[], ignite=4, fire=True, rgb=(1.0, 0.25, 0.18)),
    "green": dict(es="Verde", en="Green", glow="#46ff5a", core="#e6ffe0", flesh="#28503a", flesh2="#3a7050",
                  cloth="#16281e", cloth2="#22402e", pants="#0e1812", pants2="#17261d", bone="#a3c4a3", bone2="#cfe6cc",
                  extra=[["poison", 80, 0]], ignite=0, fire=False, rgb=(0.3, 1.0, 0.36)),
}
DARKNESS = ["darkness", 160, 0]

TYPES = {
    "zombie": dict(es="Zombi de Alma Corrupta", en="Soul Corrupted Zombie", hp=26, speed=0.24, dmg=4,
                   emerge=2.2, weight=10, family=["zombie", "undead"], box=(0.6, 1.9),
                   loot=[("rotten_flesh", 0, 2), ("soul_sand", 0, 1)]),
    "creeper": dict(es="Creeper de Alma Corrupta", en="Soul Corrupted Creeper", hp=24, speed=0.23, dmg=3,
                    emerge=1.8, weight=9, family=["creeper"], box=(0.6, 1.7), power=3,
                    loot=[("gunpowder", 1, 2), ("soul_sand", 0, 1)]),
    "skeleton": dict(es="Esqueleto de Alma Corrupta", en="Soul Corrupted Skeleton", hp=22, speed=0.26, dmg=3,
                     emerge=2.2, weight=9, family=["skeleton", "undead"], box=(0.6, 1.99), equip="bow",
                     loot=[("bone", 0, 2), ("arrow", 0, 3), ("soul_sand", 0, 1)]),
}
NETHER_BIOME = {"blue": "soul_sand_valley", "red": "crimson_forest", "green": "warped_forest"}
SWORD = f"{NS}:corrupted_soul_sword"
IMMUNE_TO = ["fire", "fire_tick", "lava", "magma", "freezing", "drowning", "wither"]


# =========================================================== HD soul painter
def a(c, alpha):
    return c[:3] + (alpha,)


class SoulCtx:
    """Face painter in model-pixel units (x, y, w, h); *_t methods use texels."""

    def __init__(self, img, x0, y0, w, h, res, mat, name):
        self.img, self.x0, self.y0, self.w, self.h, self.res = img, x0, y0, w, h, res
        self.mat, self.name = mat, name

    def put_t(self, x, y, c):
        if 0 <= x < self.w * self.res and 0 <= y < self.h * self.res:
            self.img.putpixel((self.x0 + x, self.y0 + y), c)

    def rect_t(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put_t(xx, yy, c)

    def rect(self, x, y, w, h, c):
        r = self.res
        self.rect_t(int(x * r), int(y * r), int(w * r), int(h * r), c)

    def glow_rect(self, x, y, w, h, c, halo=None):
        """Emissive block (full brightness in game)."""
        self.rect(x, y, w, h, a(c, 0))

    def px(self, points, c):
        for x, y in points:
            self.rect(x, y, 1, 1, c)


class SoulMat:
    """16x16-style pixel art. kind: flesh | cloth | bone | crystal.
    cracks = density of glowing veins (emissive pixels)."""

    def __init__(self, pal, kind="flesh", cracks=0.5, deco=None, key=None):
        self.pal, self.kind, self.cracks, self.deco, self.key = pal, kind, cracks, deco or {}, key
        key = key or {"flesh": "flesh", "cloth": "cloth", "bone": "bone", "crystal": "glow"}[kind]
        self.base = hx(pal[key])
        self.base2 = hx(pal[key + "2"]) if key + "2" in pal else hx(pal["core"])
        self.glow, self.core = hx(pal["glow"]), hx(pal["core"])

    def with_deco(self, **deco):
        m = SoulMat(self.pal, self.kind, self.cracks, {k: list(v) for k, v in self.deco.items()}, self.key)
        for k, v in deco.items():
            m.deco.setdefault(k, []).extend(v if isinstance(v, list) else [v])
        return m

    def paint(self, img, u, v, w, h, d, rng, res=1):
        assert res == 1, "soul textures are 1:1 like vanilla mobs"
        regions = {
            "top": (u + d, v, w, d), "bottom": (u + d + w, v, w, d),
            "right": (u, v + d, d, h), "front": (u + d, v + d, w, h),
            "left": (u + d + w, v + d, d, h), "back": (u + 2 * d + w, v + d, w, h),
        }
        for name, (x0, y0, fw, fh) in regions.items():
            if fw <= 0 or fh <= 0:
                continue
            face = self._face(fw, fh, name, rng, clean=name == "front" and "front" in self.deco
                              and self.deco.get("face"))
            for y in range(fh):
                for x in range(fw):
                    img.putpixel((x0 + x, y0 + y), face[y][x])
            ctx = SoulCtx(img, x0, y0, fw, fh, 1, self, name)
            keys = [name, "all"] + (["sides"] if name in SIDES else [])
            for k in keys:
                for fn in self.deco.get(k, []):
                    fn(ctx)

    def _face(self, W, H, name, rng, clean=False):
        # Clustered two-tone mottling, like vanilla mob skins
        grid = [[rng.random() for _ in range(W // 2 + 2)] for _ in range(H // 2 + 2)]
        out = [[None] * W for _ in range(H)]
        fs = FACE_SHADE[name]
        dark = shade(self.base, 0.78)
        for y in range(H):
            grad = 1.08 - 0.22 * (y / max(1, H - 1))
            for x in range(W):
                if self.kind == "crystal":
                    edge = x in (0, W - 1) and W > 1
                    tip = y == 0
                    c = self.core if (tip or (not edge and y < H // 2)) else (shade(self.glow, 0.8) if edge else self.glow)
                    out[y][x] = a(c, 0 if not edge else 60)
                    continue
                t = (grid[y // 2][x // 2] * 2 + rng.random()) / 3
                c = dark if t < 0.22 else (self.base2 if t > 0.76 else self.base)
                if self.kind == "cloth" and y % 4 == 3:
                    c = shade(c, 0.85)
                if self.kind == "bone" and rng.random() < 0.04:
                    c = shade(c, 0.72)
                out[y][x] = a(shade(c, grad * fs * (1 + (rng.random() - 0.5) * 0.06)), 255)
        if self.kind == "crystal" or self.cracks <= 0 or clean:
            return out
        # Glowing veins: short 1px lines, a few dim pixels next to them
        n = int(W * H * self.cracks / 40 + rng.random() * self.cracks * 1.5)
        mask = set()
        for _ in range(n):
            x, y = rng.randrange(W), rng.randrange(H)
            dx, dy = rng.choice([(1, 0), (0, 1), (1, 1), (-1, 1)])
            for _ in range(rng.randint(2, 5)):
                if not (0 <= x < W and 0 <= y < H):
                    break
                mask.add((x, y))
                if rng.random() < 0.35:
                    dx, dy = rng.choice([(1, 0), (0, 1), (1, 1), (-1, 1), (-1, 0)])
                x, y = x + dx, y + dy
        for (x, y) in mask:
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + ox, y + oy
                if 0 <= xx < W and 0 <= yy < H and (xx, yy) not in mask and rng.random() < 0.3:
                    out[yy][xx] = a(mix(out[yy][xx], self.glow, 0.35), 255)
        for (x, y) in mask:
            out[y][x] = a(self.core if rng.random() < 0.15 else self.glow, 0)
        return out


WHITE = hx("#ffffff")
DARK = hx("#06080b")


def d_zombie_face(pal):
    """Dungeons-style zombie face: heavy brows, white eyes, open jaw."""
    def fn(f):
        glow = hx(pal["glow"])
        brow = a(shade(f.mat.base, 0.55), 255)
        f.rect(1, 2, 2, 1, brow)
        f.rect(5, 2, 2, 1, brow)
        f.glow_rect(1, 3, 2, 1, WHITE)
        f.glow_rect(5, 3, 2, 1, WHITE)
        f.rect(1, 4, 2, 1, a(shade(f.mat.base, 0.7), 255))
        f.rect(5, 4, 2, 1, a(shade(f.mat.base, 0.7), 255))
        f.rect(3, 4, 2, 1, a(shade(f.mat.base, 0.8), 255))
        f.rect(3, 5, 2, 1, a(DARK, 255))
        f.rect(2, 6, 4, 1, a(DARK, 255))
    return fn


def d_creeper_face(pal):
    def fn(f):
        glow = hx(pal["glow"])
        f.glow_rect(1, 2, 2, 2, WHITE)
        f.glow_rect(5, 2, 2, 2, WHITE)
        f.rect(3, 4, 2, 1, a(DARK, 255))
        f.rect(2, 5, 4, 2, a(DARK, 255))
        f.rect(2, 7, 1, 1, a(DARK, 255))
        f.rect(5, 7, 1, 1, a(DARK, 255))
    return fn


def d_skull_face(pal):
    def fn(f):
        f.rect(1, 3, 2, 2, a(DARK, 255))
        f.rect(5, 3, 2, 2, a(DARK, 255))
        f.glow_rect(2, 4, 1, 1, WHITE)
        f.glow_rect(5, 4, 1, 1, WHITE)
        f.rect(3, 5, 2, 1, a(DARK, 255))
        for i in range(6):
            f.rect(1 + i, 6, 1, 1, a(DARK if i % 2 else shade(f.mat.base, 0.85), 255))
    return fn


def d_ribs(pal):
    def fn(f):
        glow = hx(pal["glow"])
        for y in (2, 5, 8):
            f.rect(1, y, f.w - 2, 1, a(DARK, 255))
            f.px([(f.w // 2 - 1, y), (f.w // 2, y)], a(glow, 0))
        f.rect(f.w // 2 - 1, 0, 2, 2, a(shade(f.mat.base, 1.1), 255))
    return fn


def d_soul_core(pal):
    """Torn shirt: skin and a glowing soul wound show through."""
    def fn(f):
        glow, core = hx(pal["glow"]), hx(pal["core"])
        skin = hx(pal["flesh"])
        f.rect(2, 3, 4, 4, a(skin, 255))
        f.px([(1, 4), (6, 5), (3, 2)], a(skin, 255))
        f.glow_rect(3, 4, 2, 2, core)
        f.px([(2, 4), (5, 5), (3, 6), (4, 3), (1, 3), (6, 6)], a(glow, 0))
    return fn


def d_tatters(pal, key="flesh", rows=2):
    """Torn hem: the colour underneath shows through the bottom rows."""
    def fn(f):
        under = a(hx(pal[key]), 255)
        rng = random.Random(f.w * 31 + f.h + sum(map(ord, f.name)))
        for x in range(f.w):
            depth = rng.choice([0, 1, 1, 2][:rows + 2])
            for y in range(f.h - depth, f.h):
                f.rect(x, y, 1, 1, under)
    return fn


def d_sleeve(pal, rows):
    """Paints a torn cloth sleeve over the top rows of an arm."""
    def fn(f):
        cloth = hx(pal["cloth2"])
        rng = random.Random(rows * 7 + sum(map(ord, f.name)))
        for x in range(f.w):
            for y in range(rows + rng.choice([0, 0, 1])):
                f.rect(x, y, 1, 1, a(shade(cloth, 0.9 if y % 4 == 3 else 1.0), 255))
    return fn


# ================================================================ models
def crystal(m, bone, origin, size, pal, pivot, rotation):
    m.cube(bone, origin, size, SoulMat(pal, "crystal"), pivot=pivot, rotation=rotation)


def soul_zombie(pal):
    m = Model("corrupted_zombie", tex_w=64, bounds=(2.5, 3.0), ns=NS)
    root = m.bone("root", [0, 0, 0])
    flesh = SoulMat(pal, "flesh", 0.6)
    shirt = SoulMat(pal, "cloth", 0.3).with_deco(front=d_soul_core(pal), sides=d_tatters(pal))
    pants = SoulMat(pal, "cloth", 0.2, key="pants").with_deco(sides=d_tatters(pal, "flesh", 1))
    B = humanoid(m, flesh.with_deco(front=d_zombie_face(pal), face=True), shirt, flesh, pants,
                 arm_mats=(flesh.with_deco(sides=d_sleeve(pal, 3), top=d_sleeve(pal, 4)),
                           flesh.with_deco(sides=d_sleeve(pal, 5), top=d_sleeve(pal, 4))))
    B["body"]["parent"] = root["name"]
    crystal(m, B["body"], [-7.5, 23, -1], [2, 5, 2], pal, [-6.5, 23, 0], [0, 0, 25])
    crystal(m, B["body"], [-5.5, 23.5, 0.5], [1, 3, 1], pal, [-5, 23.5, 1], [-20, 0, 10])
    crystal(m, B["body"], [-2, 17, 1.5], [2, 6, 2], pal, [-1, 17, 2.5], [-35, 0, -10])
    crystal(m, B["body"], [1, 15, 1.5], [1, 4, 1], pal, [1.5, 15, 2], [-45, 0, 20])
    crystal(m, B["body"], [-3.5, 20, 1.5], [1, 3, 1], pal, [-3, 20, 2], [-30, 0, -30])
    crystal(m, B["head"], [1.5, 31, -0.5], [1, 3, 1], pal, [2, 31, 0], [0, 0, -20])
    crystal(m, B["head"], [-3, 31.5, 1], [1, 2, 1], pal, [-2.5, 31.5, 1.5], [15, 0, 25])
    return m


def soul_creeper(pal):
    m = Model("corrupted_creeper", tex_w=64, bounds=(2.0, 2.5), ns=NS)
    root = m.bone("root", [0, 0, 0])
    skin = SoulMat(pal, "flesh", 0.75)
    B = creeper(m, skin.with_deco(front=d_creeper_face(pal), face=True), skin, SoulMat(pal, "flesh", 0.35))
    B["body"]["parent"] = root["name"]
    crystal(m, B["body"], [-1.5, 12, 1.5], [2, 6, 2], pal, [-0.5, 12, 2.5], [-30, 0, 10])
    crystal(m, B["body"], [1, 9, 1.5], [1, 4, 1], pal, [1.5, 9, 2], [-40, 0, -15])
    crystal(m, B["body"], [-3, 15, 1.5], [1, 3, 1], pal, [-2.5, 15, 2], [-25, 0, 25])
    crystal(m, B["head"], [-2.5, 26, -1], [2, 4, 2], pal, [-1.5, 26, 0], [0, 0, 20])
    crystal(m, B["head"], [1.5, 26, 1], [1, 3, 1], pal, [2, 26, 1.5], [15, 0, -25])
    return m


def soul_skeleton(pal):
    m = Model("corrupted_skeleton", tex_w=64, bounds=(2.5, 3.0), ns=NS)
    root = m.bone("root", [0, 0, 0])
    bone = SoulMat(pal, "bone", 0.45)
    B = humanoid(m, bone.with_deco(front=d_skull_face(pal), face=True), bone.with_deco(front=d_ribs(pal), back=d_ribs(pal)),
                 bone, bone, arm_w=2, leg_w=2)
    B["body"]["parent"] = root["name"]
    m.cube(B["body"], [-4.5, 21, -2.5], [9, 3, 5], SoulMat(pal, "cloth", 0.2))  # torn scarf
    crystal(m, B["body"], [4.5, 23, -1], [2, 4, 2], pal, [5.5, 23, 0], [0, 0, -25])
    crystal(m, B["body"], [-1, 16, 1.5], [2, 5, 2], pal, [0, 16, 2.5], [-35, 0, 0])
    crystal(m, B["body"], [-3, 13, 1.5], [1, 3, 1], pal, [-2.5, 13, 2], [-40, 0, -20])
    crystal(m, B["head"], [-2, 31, -1], [1, 3, 1], pal, [-1.5, 31, -0.5], [0, 0, 15])
    return m


MODELS = {"zombie": soul_zombie, "creeper": soul_creeper, "skeleton": soul_skeleton}


# ============================================================= behaviour
def mob_id(t, c):
    return f"corrupted_{t}_{c}"


def behavior(t, c):
    T, C = TYPES[t], COLORS[c]
    ident = mob_id(t, c)
    base = {
        "minecraft:type_family": {"family": T["family"] + ["monster", "mob", "soul_corrupted"]},
        "minecraft:health": {"value": T["hp"], "max": T["hp"]},
        "minecraft:collision_box": {"width": T["box"][0], "height": T["box"][1]},
        "minecraft:movement": {"value": T["speed"]},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_pass_doors": True, "avoid_water": True, "can_walk_in_lava": True,
                                      "can_path_over_lava": True, "is_amphibious": True},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_water": True},
        "minecraft:damage_sensor": {"triggers": [{"cause": cause, "deals_damage": False} for cause in IMMUNE_TO]},
        "minecraft:attack": {"damage": T["dmg"], "effect_name": "darkness", "effect_duration": 8},
        "minecraft:loot": {"table": f"loot_tables/{NS}/{ident}.json"},
        "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 7 : 0"},
    }
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
        # Rising out of the ground / growing: no AI until the animation ends
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
    runtime = None
    if t == "zombie":
        active["minecraft:behavior.melee_attack"] = {"priority": 3, "speed_multiplier": 1.0, "track_target": False}
    elif t == "skeleton":
        base["minecraft:shooter"] = {"def": "minecraft:arrow"}
        active["minecraft:behavior.ranged_attack"] = {"priority": 2, "attack_interval_min": 1.0,
                                                      "attack_interval_max": 3.0, "attack_radius": 15.0}
        active["minecraft:behavior.avoid_mob_type"] = {"priority": 4, "entity_types": [
            {"filters": fam("wolf"), "max_dist": 6, "walk_speed_multiplier": 1.2, "sprint_speed_multiplier": 1.2}]}
    else:
        runtime = "minecraft:creeper"
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
        for ev in ("minecraft:start_exploding", "minecraft:start_exploding_forced"):
            events[ev] = {"sequence": [{"filters": not_lit, "add": {"component_groups": ["minecraft:exploding"]}}]}
        events["minecraft:stop_exploding"] = {"remove": {"component_groups": ["minecraft:exploding"]}}

    desc = {"identifier": f"{NS}:{ident}", "is_spawnable": True, "is_summonable": True, "is_experimental": False,
            "properties": {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}}}
    if runtime:
        desc["runtime_identifier"] = runtime
    return {"format_version": "1.20.80", "minecraft:entity": {
        "description": desc, "component_groups": groups, "components": base, "events": events}}


def spawn_rules(t, c):
    T = TYPES[t]
    w = T["weight"] if c == "blue" else max(1, T["weight"] // 2)
    conds = [
        {"minecraft:spawns_on_surface": {}, "minecraft:spawns_underground": {},
         "minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
         "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
         "minecraft:weight": {"default": w}, "minecraft:herd": {"min_size": 1, "max_size": 2},
         "minecraft:biome_filter": {"test": "has_biome_tag", "value": "monster"}},
        # Each colour also haunts its Nether biome
        {"minecraft:spawns_on_surface": {}, "minecraft:spawns_underground": {},
         "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
         "minecraft:weight": {"default": 20}, "minecraft:herd": {"min_size": 1, "max_size": 3},
         "minecraft:biome_filter": {"test": "has_biome_tag", "value": NETHER_BIOME[c]}},
    ]
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": f"{NS}:{mob_id(t, c)}", "population_control": "monster"}, "conditions": conds}}


def loot(t):
    pools = [{"rolls": 1, "entries": [{"type": "item", "name": f"minecraft:{item}", "weight": 1, "functions": [
        {"function": "set_count", "count": {"min": lo, "max": hi}},
        {"function": "looting_enchant", "count": {"min": 0, "max": 1}}]}]} for item, lo, hi in TYPES[t]["loot"]]
    # The corrupted soul sword can't be crafted: it only drops from these mobs
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
    return f"""// Soul Corrupted - darkness on every hit and the corrupted soul sword.
// Generated by tools/soul_generate.py, edit it there instead.
import {{ world }} from "@minecraft/server";

// [effect, duration in ticks, amplifier] applied to whatever the mob hurts
// (melee hit, arrow or explosion).
const HIT_EFFECTS = {json.dumps(effects, indent=2)};

// Seconds the red variants set their victims on fire for.
const IGNITE = {json.dumps(ignite, indent=2)};

const SWORD = "{SWORD}";

function heldItem(player) {{
  try {{
    return player.getComponent("minecraft:equippable")?.getEquipment("Mainhand");
  }} catch {{
    return undefined;
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
    }}
  }} catch {{
    // victim died or cannot receive effects
  }}
}});
"""


# ============================================================= resources
def kf(d):
    """Keyframes with smooth (catmull-rom) interpolation."""
    return {str(k): {"post": v, "lerp_mode": "catmullrom"} for k, v in d.items()}


WALK = "query.modified_distance_moved * 38.17"
# Smoothed speed / turn rate (see SMOOTHING): no snapping when the mob starts,
# stops or turns.
SPEED = "variable.s_speed"
TURN = "variable.s_turn"
SMOOTHING = [
    "variable.s_speed = math.lerp(variable.s_speed ?? 0.0, query.modified_move_speed, 0.1);",
    "variable.s_turn = math.lerp(variable.s_turn ?? 0.0, math.clamp(query.yaw_speed, -120.0, 120.0), 0.05);",
    "variable.s_attack = math.lerp(variable.s_attack ?? 0.0, math.sin(variable.attack_time * 180.0), 0.35);",
]

ANIMS = {
    "look_at_target": {"loop": True, "bones": {
        "head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0.0]}}},

    # Soul particles: a few rising wisps and falling drops every 0.2 s
    "soul_particles": {"loop": True, "animation_length": 0.2,
                       "particle_effects": {"0.0": [{"effect": "wisps"}, {"effect": "drips"}]}},

    # ---- zombie: slow shamble with a soft sway, arms out, gentle head tilt
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
    "zombie_emerge": {"loop": "hold_on_last_frame", "animation_length": 2.2, "bones": {
        "root": {"position": kf({0.0: [0, -30, 0], 0.6: [0, -23, 0], 1.3: [0, -11, 0], 1.9: [0, -2, 0], 2.2: [0, 0, 0]}),
                 "rotation": kf({0.0: [30, 0, 0], 0.8: [24, 0, -6], 1.5: [12, 0, 4], 2.2: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-170, 0, 10], 0.6: [-150, 0, 18], 1.2: [-165, 0, 8],
                                     1.8: [-120, 0, 6], 2.2: [-85, -6, 4]})},
        "leftArm": {"rotation": kf({0.0: [-150, 0, -16], 0.6: [-170, 0, -8], 1.2: [-148, 0, -18],
                                    1.8: [-115, 0, -6], 2.2: [-85, 6, -4]})},
        "head": {"rotation": kf({0.0: [-30, 0, 0], 1.1: [-14, 8, 8], 1.8: [3, -4, -4], 2.2: [0, 0, 0]})}}},

    # ---- creeper: leans into where it walks and into turns, soft bob, breathing
    "creeper_walk": {"loop": True, "bones": {
        "leg0": {"rotation": [f"math.cos({WALK}) * 50.0 * {SPEED}", 0.0, 0.0]},
        "leg1": {"rotation": [f"math.cos({WALK}) * -50.0 * {SPEED}", 0.0, 0.0]},
        "leg2": {"rotation": [f"math.cos({WALK}) * -50.0 * {SPEED}", 0.0, 0.0]},
        "leg3": {"rotation": [f"math.cos({WALK}) * 50.0 * {SPEED}", 0.0, 0.0]},
        "body": {"rotation": [f"{SPEED} * 14.0", 0.0, f"math.clamp({TURN} * 0.1, -9.0, 9.0)"],
                 "position": [0.0, f"math.abs(math.sin({WALK})) * 0.4 * {SPEED}", 0.0]},
        "head": {"rotation": [f"-{SPEED} * 10.0 + math.sin({WALK}) * 2.5 * {SPEED}", 0.0, f"math.clamp({TURN} * 0.05, -5.0, 5.0)"]}}},
    "creeper_idle": {"loop": True, "bones": {
        "body": {"scale": ["1.0 + math.sin(query.life_time * 80.0) * 0.02", "1.0 + math.sin(query.life_time * 80.0 + 90.0) * 0.012",
                           "1.0 + math.sin(query.life_time * 80.0) * 0.02"]},
        "head": {"rotation": [0.0, 0.0, "math.sin(query.life_time * 28.0) * 2.5"]}}},
    "creeper_spawn": {"loop": "hold_on_last_frame", "animation_length": 1.8, "bones": {
        "root": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.7: [0.65, 0.6, 0.65], 1.15: [1.12, 1.1, 1.12],
                              1.45: [0.96, 0.97, 0.96], 1.8: [1, 1, 1]}),
                 "rotation": kf({0.0: [0, -200, 0], 1.15: [0, -15, 0], 1.8: [0, 0, 0]})}}},

    # ---- skeleton: loose walk, slow glances around, aims the bow
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
    "skeleton_emerge": {"loop": "hold_on_last_frame", "animation_length": 2.2, "bones": {
        "root": {"position": kf({0.0: [0, -32, 0], 0.7: [0, -23, 0], 1.4: [0, -11, 0], 1.9: [0, -2, 0], 2.2: [0, 0, 0]}),
                 "rotation": kf({0.0: [18, 0, 8], 0.7: [14, 0, -8], 1.4: [8, 0, 6], 1.9: [3, 0, -3], 2.2: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-175, 0, 12], 0.7: [-158, 0, 24], 1.4: [-165, 0, 10], 1.9: [-60, 0, 8], 2.2: [0, 0, 3]})},
        "leftArm": {"rotation": kf({0.0: [-160, 0, -20], 0.7: [-175, 0, -10], 1.4: [-150, 0, -20], 1.9: [-50, 0, -6], 2.2: [0, 0, -3]})},
        "head": {"rotation": kf({0.0: [-35, 0, 0], 0.7: [-18, 18, 10], 1.4: [-8, -18, -10], 1.9: [6, 0, 0], 2.2: [0, 0, 0]})}}},
}

CONTROLLERS = {
    "zombie": (["zombie_emerge"], ["zombie_walk", "zombie_arms", "zombie_idle", "zombie_attack"]),
    "creeper": (["creeper_spawn"], ["creeper_walk", "creeper_idle"]),
    "skeleton": (["skeleton_emerge"], ["skeleton_walk", "skeleton_idle",
                                       {"skeleton_arms": "1.0 - variable.s_aim"}, {"skeleton_aim": "variable.s_aim"}]),
}


def controllers():
    prop = f"query.property('{NS}:emerging')"
    out = {}
    for t, (spawn, alive) in CONTROLLERS.items():
        out[f"controller.animation.{NS}.{t}"] = {"initial_state": "start", "states": {
            "start": {"transitions": [{"emerging": prop}, {"alive": f"!{prop}"}]},
            "emerging": {"animations": spawn, "particle_effects": [{"effect": "burst"}],
                         "transitions": [{"alive": f"!{prop}"}], "blend_transition": 0.5},
            "alive": {"animations": alive, "blend_transition": 0.5},
        }}
    return {"format_version": "1.10.0", "animation_controllers": out}


def particles(c):
    """Soul particles tinted with the mob's colour. Alpha-blended and unlit so
    they show up in daylight too."""
    r, g, b = COLORS[c]["rgb"]
    tex = {"material": "particles_alpha", "texture": "textures/particle/soul_spark"}

    def billboard(size):
        fade = f"{size} * (1.0 - math.pow(variable.particle_age / variable.particle_lifetime, 2.0))"
        return {"size": [fade, fade], "facing_camera_mode": "rotate_xyz",
                "uv": {"texture_width": 8, "texture_height": 8, "uv": [0, 0], "uv_size": [8, 8]}}

    def effect(name, comps):
        return {"format_version": "1.10.0", "particle_effect": {
            "description": {"identifier": f"{NS}:{name}_{c}", "basic_render_parameters": tex},
            "components": dict({
                "minecraft:emitter_local_space": {"position": False, "rotation": False},
                "minecraft:particle_appearance_tinting": {"color": [r, g, b, 1.0]},
            }, **comps)}}

    body = {"offset": [0, 0.9, 0], "half_dimensions": [0.3, 0.7, 0.3]}
    wisps = effect("wisp", {
        "minecraft:emitter_rate_instant": {"num_particles": 2},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_box": dict(body, direction=[0, 1, 0]),
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.4)"},
        "minecraft:particle_initial_speed": "math.random(0.2, 0.5)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.8, 0], "linear_drag_coefficient": 0.8},
        "minecraft:particle_appearance_billboard": billboard(0.14),
    })
    drips = effect("drip", {
        "minecraft:emitter_rate_instant": {"num_particles": 1},
        "minecraft:emitter_lifetime_once": {"active_time": 0.1},
        "minecraft:emitter_shape_box": dict(body, direction="outwards"),
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.6, 1.0)"},
        "minecraft:particle_initial_speed": "math.random(0.3, 0.8)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -6.0, 0], "linear_drag_coefficient": 1.0},
        "minecraft:particle_motion_collision": {"collision_radius": 0.05, "coefficient_of_restitution": 0.2,
                                                "collision_drag": 4.0},
        "minecraft:particle_appearance_billboard": billboard(0.1),
    })
    burst = effect("burst", {
        "minecraft:emitter_rate_instant": {"num_particles": 45},
        "minecraft:emitter_lifetime_once": {"active_time": 0.2},
        "minecraft:emitter_shape_disc": {"offset": [0, 0.1, 0], "radius": 0.8, "plane_normal": "y",
                                         "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(1.0, 1.8)"},
        "minecraft:particle_initial_speed": "math.random(1.0, 2.5)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 2.0, 0], "linear_drag_coefficient": 2.0},
        "minecraft:particle_appearance_billboard": billboard(0.18),
    })
    return {"wisp": wisps, "drip": drips, "burst": burst}


def client_entity(t, c):
    ident = mob_id(t, c)
    pre = list(SMOOTHING)
    if t == "skeleton":
        pre.append("variable.s_aim = math.lerp(variable.s_aim ?? 0.0, query.has_target ? 1.0 : 0.0, 0.08);")
    scripts = {"pre_animation": pre, "animate": ["look", "controller", "soul_particles"]}
    rc = "controller.render.soul.default"
    if t == "creeper":
        rc = "controller.render.soul.creeper"
        scripts["pre_animation"] += [
            "variable.wobble = Math.sin(query.swell_amount * 5730) * query.swell_amount * 0.01 + 1.0;",
            "variable.swelled = Math.pow(Math.clamp(query.swell_amount, 0.0, 1.0), 4.0);",
            "variable.scale_xz = (1.0 + variable.swelled * 0.4) * variable.wobble;",
            "variable.scale_y = (1.0 + variable.swelled * 0.1) / variable.wobble;",
            "variable.flash = math.mod(math.round(query.swell_amount * 10.0), 2.0) * 0.5;",
        ]
        scripts.update({"scalex": "variable.scale_xz", "scaley": "variable.scale_y", "scalez": "variable.scale_xz"})
    anims = {"look": f"animation.{NS}.look_at_target", "controller": f"controller.animation.{NS}.{t}",
             "soul_particles": f"animation.{NS}.soul_particles"}
    spawn, alive = CONTROLLERS[t]
    for entry in spawn + alive:
        for name in ([entry] if isinstance(entry, str) else entry):
            anims[name] = f"animation.{NS}.{name}"
    desc = {
        "identifier": f"{NS}:{ident}",
        "materials": {"default": "entity_emissive_alpha"},
        "textures": {"default": f"textures/entity/{NS}/{ident}"},
        "geometry": {"default": f"geometry.{NS}.corrupted_{t}"},
        "animations": anims,
        "particle_effects": {"wisps": f"{NS}:wisp_{c}", "drips": f"{NS}:drip_{c}", "burst": f"{NS}:burst_{c}"},
        "scripts": scripts,
        "render_controllers": [rc],
        "spawn_egg": {"base_color": COLORS[c]["flesh2"], "overlay_color": COLORS[c]["glow"]},
    }
    if TYPES[t].get("equip"):
        desc["enable_attachables"] = True
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


RENDER_CONTROLLERS = {"format_version": "1.8.0", "render_controllers": {
    "controller.render.soul.default": {
        "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
    "controller.render.soul.creeper": {
        "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
        "overlay_color": {"r": "variable.flash", "g": "variable.flash", "b": "variable.flash", "a": "variable.flash"}},
}}


# ================================================================ images
def sword_icon():
    """32x32 sword: dark soul-steel blade with a glowing core, winged guard."""
    S = 32
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow, core = hx("#3fe0ff"), hx("#e6fdff")
    steel, steel2 = hx("#26344a"), hx("#4a6382")
    gold, grip = hx("#8a6a3a"), hx("#2a1d2e")
    L = math.sqrt(2) * (S - 4)
    px = {}
    for y in range(S):
        for x in range(S):
            # u: along the blade (0 at pommel, bottom-left), v: across it
            u = ((x - 2) + (S - 3 - y)) / math.sqrt(2) / L
            v = ((x - 2) - (S - 3 - y)) / math.sqrt(2)
            av = abs(v)
            c = None
            if -0.03 <= u < 0.05 and av < 1.7:
                c = gold if av < 1.0 else shade(gold, 0.7)
            elif 0.05 <= u < 0.23 and av < 1.0:
                c = grip if int(u * 60) % 2 else shade(grip, 1.5)
            elif 0.23 <= u < 0.31 and av < 5.2 - abs(u - 0.27) * 25:
                c = shade(gold, 1.25) if abs(u - 0.27) < 0.02 else gold
                if av < 1.2:
                    c = core
                elif 3.0 < av < 4.2:
                    c = glow
            elif 0.30 <= u < 0.98:
                width = 2.6 * (1 - ((u - 0.30) / 0.68) ** 2.2) + 0.4
                if av < width:
                    edge = av > width - 0.9
                    c = steel2 if edge else steel
                    if av < 0.55:
                        c = core if (u - 0.30) % 0.12 < 0.06 else glow
                    elif av < 1.1:
                        c = mix(steel, glow, 0.45)
            if c:
                px[(x, y)] = c
    for (x, y), c in px.items():
        img.putpixel((x, y), c)
    # dark outline like vanilla items
    outline = hx("#0b0f18")
    for y in range(S):
        for x in range(S):
            if (x, y) not in px and any((x + dx, y + dy) in px for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                img.putpixel((x, y), outline)
    return img


def spark_texture():
    """8x8 white soul spark (tinted per colour by the particle)."""
    rows = ["...##...",
            "..####..",
            ".######.",
            "########",
            "########",
            ".######.",
            "..####..",
            "...##..."]
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                d = math.hypot(x - 3.5, y - 3.5)
                v = 255 if d < 2 else 200
                img.putpixel((x, y), (v, v, v, 255 if d < 2.6 else 170))
    return img


def pack_icon():
    img = Image.new("RGBA", (64, 64), hx("#070b12"))
    rng = random.Random(3)
    glow = hx("#3fe0ff")
    for y in range(64):
        for x in range(64):
            d = math.hypot(x - 32, (y - 36) * 0.8)
            flame = 22 - abs(math.sin(y * 0.25 + x * 0.05)) * 4 - max(0, 30 - y) * 0.4
            if d < flame:
                t = d / flame
                img.putpixel((x, y), mix(hx("#e6fdff"), glow, min(1, t * 1.4)) if rng.random() > 0.03 else glow)
    for x0 in (22, 36):
        for yy in range(30, 37):
            for xx in range(x0, x0 + 6):
                img.putpixel((xx, yy), (255, 255, 255, 255))
    img = img.filter(ImageFilter.SMOOTH)
    return img.resize((128, 128), Image.NEAREST)


def opaque(img):
    """Preview helper: show emissive texels as solid colour."""
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, al = px[x, y]
            if 0 < al < 255 or (al == 0 and (r or g or b)):
                px[x, y] = (r, g, b, 255)
    return out


# ================================================================== build
def lang(es):
    lines = ["pack.name=Soul Corrupted", "pack.description=Mobs de alma corrupta", ""]
    for t, T in TYPES.items():
        for c, C in COLORS.items():
            name = f"{T['es']} ({C['es']})" if es else f"{T['en']} ({C['en']})"
            lines.append(f"entity.{NS}:{mob_id(t, c)}.name={name}")
            lines.append(f"item.spawn_egg.entity.{NS}:{mob_id(t, c)}.name={'Generar ' if es else 'Spawn '}{name}")
    lines.append(f"item.{SWORD}.name={'Espada de Alma Corrupta' if es else 'Corrupted Soul Sword'}")
    return "\n".join(lines) + "\n"


def manifest(kind):
    if kind == "bp":
        return {"format_version": 2, "header": {
            "name": "Soul Corrupted (Behavior)", "description": "Zombis, creepers y esqueletos de alma corrupta + espada.",
            "uuid": UUID["bp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [{"type": "data", "uuid": UUID["bp_data"], "version": VERSION},
                        {"type": "script", "language": "javascript", "uuid": UUID["bp_script"], "version": VERSION,
                         "entry": "scripts/main.js"}],
            "dependencies": [{"uuid": UUID["rp_header"], "version": VERSION},
                             {"module_name": "@minecraft/server", "version": SCRIPT_API}]}
    return {"format_version": 2, "header": {
        "name": "Soul Corrupted (Resources)", "description": "Modelos, texturas brillantes y animaciones.",
        "uuid": UUID["rp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUID["bp_header"], "version": VERSION}]}


def main():
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    prev = "--preview" in sys.argv
    prev_dir = os.path.join(ROOT, "previews", "soul")
    if prev:
        os.makedirs(prev_dir, exist_ok=True)
    names = []
    for ti, t in enumerate(TYPES):
        for ci, (c, C) in enumerate(COLORS.items()):
            model = MODELS[t](C)
            img = model.build(seed=101 + ti * 31 + ci, res=RES)
            ident = mob_id(t, c)
            os.makedirs(os.path.join(RP, f"textures/entity/{NS}"), exist_ok=True)
            img.save(os.path.join(RP, f"textures/entity/{NS}/{ident}.png"))
            if ci == 0:  # all colours share one geometry
                write(os.path.join(RP, "models/entity", f"corrupted_{t}.geo.json"), model.geometry_json())
            write(os.path.join(RP, "entity", f"{ident}.entity.json"), client_entity(t, c))
            write(os.path.join(BP, "entities", f"{ident}.json"), behavior(t, c))
            write(os.path.join(BP, "spawn_rules", f"{ident}.json"), spawn_rules(t, c))
            write(os.path.join(BP, f"loot_tables/{NS}", f"{ident}.json"), loot(t))
            if prev:
                preview(model, opaque(img), os.path.join(prev_dir, f"{ident}.png"), scale=8, res=RES)
                names.append(ident)
    write(os.path.join(BP, f"loot_tables/{NS}/equipment/bow.json"),
          {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:bow", "weight": 1}]}]})

    for c in COLORS:
        for name, effect in particles(c).items():
            write(os.path.join(RP, "particles", f"{name}_{c}.json"), effect)
    os.makedirs(os.path.join(RP, "textures/particle"), exist_ok=True)
    spark_texture().save(os.path.join(RP, "textures/particle/soul_spark.png"))

    write(os.path.join(RP, "animations/soul.animation.json"), {"format_version": "1.8.0", "animations": {
        f"animation.{NS}.{n}": a for n, a in ANIMS.items()}})
    write(os.path.join(RP, "animation_controllers/soul.animation_controllers.json"), controllers())
    write(os.path.join(RP, "render_controllers/soul.render_controllers.json"), RENDER_CONTROLLERS)

    # Sword
    write(os.path.join(BP, "items/corrupted_soul_sword.json"), sword_item())
    os.makedirs(os.path.join(RP, "textures/items"), exist_ok=True)
    sword_icon().save(os.path.join(RP, "textures/items/corrupted_soul_sword.png"))
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "soul_corrupted", "texture_name": "atlas.items",
        "texture_data": {"corrupted_soul_sword": {"textures": "textures/items/corrupted_soul_sword"}}})

    write(os.path.join(BP, "scripts/main.js"), script())
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["en_US", "es_ES", "es_MX"])
        write(os.path.join(pack, "texts/en_US.lang"), lang(False))
        write(os.path.join(pack, "texts/es_ES.lang"), lang(True))
        write(os.path.join(pack, "texts/es_MX.lang"), lang(True))
        pack_icon().save(os.path.join(pack, "pack_icon.png"))
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
        sword_icon().resize((256, 256), Image.NEAREST).save(os.path.join(ROOT, "docs", "soul_sword.png"))
    print("Built", len(TYPES) * len(COLORS), "soul mobs + sword ->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
