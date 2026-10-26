"""Builds "Soul Corrupted Mobs" on top of the original add-on in
sources/soul_corrupted_mobs_v1.0.0 (by Euforia), keeping its identifiers,
outline rendering and vanilla animations, and adding:

  - red and green variants of the zombie, creeper and skeleton
  - soul corrupted phantoms (blue/red/green) and a tameable, rideable phantom
  - a healing altar, the corrupted soul sword
  - darkness + colour effects on hit, immunities, spawn animations, particles,
    spawn rules and loot

    python3 tools/soul_mobs.py            # regenerate the packs and the .mcaddon
    python3 tools/soul_mobs.py --preview  # also refresh docs/soul_mobs_preview.png
"""
import colorsys
import copy
import json
import os
import random
import re
import shutil
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import Model  # noqa: E402
from textures import SIDES, hx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources", "soul_corrupted_mobs_v1.0.0")
ADDON_NAME = "The Revamp of the Soul"
BP = os.path.join(ROOT, "TheRevampOfTheSoul_BP")
RP = os.path.join(ROOT, "TheRevampOfTheSoul_RP")
DIST = os.path.join(ROOT, "dist")

NS = "eu_sc"
VERSION = [1, 3, 0]
SCRIPT_API = "2.0.0"  # stable: no "Beta APIs" experiment needed
TEX = "textures/entity/soul_corrupted"
OUTLINE_TEX = f"{TEX}/white_outline"

# Palette of the original textures, light to dark (blue)
PALETTE = ["#ffffff", "#cef8f9", "#9df1f3", "#6deaec", "#3cdae6", "#24c7dd"]
BASE_HUE = colorsys.rgb_to_hsv(*[c / 255 for c in hx("#3cdae6")[:3]])[0]
COLORS = {
    "blue": dict(suffix="", hue=None, es="Azul", en="Blue", rgb=(0.24, 0.86, 0.9),
                 extra=[["slowness", 60, 0]], ignite=0, nether="soul_sand_valley"),
    "red": dict(suffix="_red", hue=0.995, es="Roja", en="Red", rgb=(0.92, 0.25, 0.25),
                extra=[], ignite=4, nether="crimson_forest"),
    "green": dict(suffix="_green", hue=0.35, es="Verde", en="Green", rgb=(0.25, 0.92, 0.32),
                  extra=[["poison", 80, 0]], ignite=0, nether="warped_forest"),
}
DARKNESS = ["darkness", 160, 0]
IMMUNE_TO = ["fire", "fire_tick", "lava", "magma", "freezing", "drowning", "wither"]

BASE_MOBS = {  # original mobs (blue) -> name and spawn tuning
    "zombie": dict(es="Zombi de Alma Corrupta", en="Soul Corrupted Zombie", weight=10, emerge=1.2,
                   loot=[("rotten_flesh", 0, 2), ("soul_sand", 0, 1)]),
    "creeper": dict(es="Creeper de Alma Corrupta", en="Soul Corrupted Creeper", weight=9, emerge=0.9,
                    loot=[("gunpowder", 0, 2), ("soul_sand", 0, 1)]),
    "skeleton": dict(es="Esqueleto de Alma Corrupta", en="Soul Corrupted Skeleton", weight=9, emerge=1.2,
                     loot=[("bone", 0, 2), ("arrow", 0, 2), ("soul_sand", 0, 1)]),
}
PHANTOM = dict(es="Phantom de Alma Corrupta", en="Soul Corrupted Phantom", weight=3, emerge=0.8,
               loot=[("phantom_membrane", 0, 1)])
PHANTOM_SCALE = 2.5
MOUNT = "soul_corrupted_phantom_mount"
ALTAR = "healing_altar"
SWORD = f"{NS}:soul_corrupted_sword"
ESSENCE = f"{NS}:soul_essence"
FLIGHT_BOOST = 1.65  # every phantom flies 1.65x faster
MOB_SPEED_BOOST = 1.12  # soul corrupted mobs walk a little faster than vanilla
HAPPY_GHAST_SPEED = 0.016  # vanilla Bedrock adult happy ghast flying_speed
MOUNT_SPEED = round(0.02 * FLIGHT_BOOST, 4)
PHANTOM_DETECT = 96  # vanilla: 64
ALTAR_RANGE = 12


# ================================================================== helpers
def load(path):
    """Bedrock JSON allows // comments."""
    with open(path, encoding="utf-8") as f:
        return json.loads(re.sub(r"(?<![:\"])//.*", "", f.read()))


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")


def save_png(img, *parts):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def ident(kind, color):
    return f"soul_corrupted_{kind}{COLORS[color]['suffix']}"


def recolor_rgb(rgb, color):
    hue = COLORS[color]["hue"]
    if hue is None:
        return rgb
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb[:3]])
    if s < 0.06:  # whites stay white
        return rgb
    r, g, b = colorsys.hsv_to_rgb((h - BASE_HUE + hue) % 1.0, min(1.0, s * 1.05), v * 0.97)
    return (round(r * 255), round(g * 255), round(b * 255)) + tuple(rgb[3:])


def recolor(img, color):
    out = img.convert("RGBA").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            p = px[x, y]
            if p[3]:
                px[x, y] = recolor_rgb(p, color)
    return out


def soften(img):
    """Less intense, slightly duller colours for the mob textures (whites,
    and so the eyes, stay white; the outline is a separate texture)."""
    out = img.convert("RGBA").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if not a:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s < 0.06:
                continue
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s * 0.6, v * 0.92 + 0.03)
            px[x, y] = (round(r2 * 255), round(g2 * 255), round(b2 * 255), a)
    return out


def mix_hex(a, b, t):
    ca, cb = hx(a), hx(b)
    return "#%02x%02x%02x" % tuple(round(ca[i] * (1 - t) + cb[i] * t) for i in range(3))


def hexcol(rgb):
    return "#%02X%02X%02X" % tuple(rgb[:3])


def walk(node, fn):
    """Calls fn(key, value, parent) on every dict entry, recursively."""
    if isinstance(node, dict):
        for k in list(node):
            fn(k, node[k], node)
            if k in node:
                walk(node[k], fn)
    elif isinstance(node, list):
        for v in node:
            walk(v, fn)


def fam(*names):
    if len(names) == 1:
        return {"test": "is_family", "subject": "other", "value": names[0]}
    return {"any_of": [{"test": "is_family", "subject": "other", "value": n} for n in names]}


def immunities(extra=()):
    return [{"cause": c, "deals_damage": "no"} for c in IMMUNE_TO + list(extra)]


# ============================================================= 16x16 painter
class Pal16:
    """Paints cubes in the style of the original textures: light cyan base,
    darker maze-like veins and white highlights, from the original palette.
    kind: skin | deep | stone (altar) | crystal."""

    STONE = ["#6a7182", "#565c6b", "#454b59", "#363b47", "#2a2e38", "#1d2028"]

    def __init__(self, kind="skin", veins=1.0, deco=None):
        self.kind, self.veins, self.deco = kind, veins, deco or {}
        self.tones = [hx(c) for c in (self.STONE if kind == "stone" else PALETTE)]
        self.base_idx = {"deep": 3, "bone": 1}.get(kind, 2)

    def tone(self, i):
        return self.tones[max(0, min(5, i))]

    def with_deco(self, **deco):
        m = Pal16(self.kind, self.veins, {k: list(v) for k, v in self.deco.items()})
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
            ctx = Ctx(img, x0, y0, fw, fh, self, name)
            for k in [name, "all"] + (["sides"] if name in SIDES else []):
                for fn in self.deco.get(k, []):
                    fn(ctx)

    def _face(self, W, H, name, rng):
        if self.kind == "crystal":
            return [[self.tone(0) if (x + y) % 3 else self.tone(1) for x in range(W)] for y in range(H)]
        grid = [[rng.random() for _ in range(W // 2 + 2)] for _ in range(H // 2 + 2)]
        idx = [[self.base_idx] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                t = grid[y // 2][x // 2] * 0.8 + rng.random() * 0.2
                i = self.base_idx + (1 if t < 0.25 else (-1 if t > 0.85 else 0))
                if y == 0 and rng.random() < 0.3:
                    i -= 1
                if H > 3 and y >= H * 0.7 and rng.random() < (y / H - 0.55):
                    i += 1
                if name == "bottom":
                    i += 1
                idx[y][x] = i
        for _ in range(int(W * H * self.veins / 22 + rng.random())):
            x, y = rng.randrange(W), rng.randrange(H)
            dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            for _ in range(rng.randint(3, 6)):
                if not (0 <= x < W and 0 <= y < H):
                    break
                idx[y][x] = self.base_idx + (3 if rng.random() < 0.25 else 2)
                if rng.random() < 0.35:
                    dx, dy = (dy, dx) if rng.random() < 0.5 else (-dy, -dx)
                x, y = x + dx, y + dy
        return [[self.tone(idx[y][x]) for x in range(W)] for y in range(H)]


class Ctx:
    def __init__(self, img, x0, y0, w, h, mat, name):
        self.img, self.x0, self.y0, self.w, self.h, self.mat, self.name = img, x0, y0, w, h, mat, name

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((self.x0 + x, self.y0 + y), c if isinstance(c, tuple) else hx(c))

    def px(self, points, c):
        for x, y in points:
            self.put(x, y, c)

    def tone(self, i):
        return self.mat.tone(i)


WHITE = (255, 255, 255, 255)


def d_phantom_face():
    """White eyes on the sides of the head (the snout covers the middle)."""
    def fn(f):
        f.px([(0, 0), (1, 0), (6, 0), (7, 0), (2, 1), (5, 1)], f.tone(5))
        f.px([(0, 1), (1, 1), (6, 1), (7, 1)], WHITE)
    return fn


def d_snout():
    def fn(f):
        f.px([(x, f.h - 1) for x in range(f.w)], f.tone(5))
    return fn


def d_wing_lines():
    def fn(f):
        for x in range(1, f.w, 3):
            for y in range(f.h):
                f.put(x, y, f.tone(1))
    return fn


def d_wing_edge():
    """Darker trailing edge on the wing tips."""
    def fn(f):
        for x in range(f.w):
            f.put(x, f.h - 1, f.tone(5))
    return fn


def d_saddle():
    def fn(f):
        leather, dark, trim = hx("#5a3826"), hx("#3a2218"), hx("#ffffff")
        cx, cy = f.w // 2, f.h // 2
        for y in range(cy - 3, cy + 3):
            for x in range(cx - 2, cx + 2):
                f.put(x, y, leather if (x + y) % 3 else dark)
        for x in range(cx - 2, cx + 2):
            f.put(x, cy - 3, trim)
            f.put(x, cy + 2, trim)
    return fn


def d_runes():
    def fn(f):
        g = hx(PALETTE[3])
        cx = f.w // 2
        for y in range(1, f.h - 1, 2):
            f.put(cx, y, g)
            if f.w > 6 and y % 4 == 1:
                f.px([(cx - 2, y), (cx + 1, y + 1)], hx(PALETTE[1]))
    return fn


def d_soul_fire():
    def fn(f):
        for y in range(1, f.h - 1):
            for x in range(1, f.w - 1):
                f.put(x, y, hx(PALETTE[4]) if (x * 7 + y * 3) % 4 else hx(PALETTE[0]))
    return fn


# ================================================================ models
def phantom_model(saddle=False):
    """Four wings with pointed tips, pointed snout and horns."""
    m = Model("soul_corrupted_phantom", tex_w=64, bounds=(3.5, 2.0), ns="eu.sc")
    root = m.bone("root", [0, 0, 0])
    body_mat = Pal16("skin")
    if saddle:
        body_mat = body_mat.with_deco(top=d_saddle())
    body = m.bone("body", [0, 8, 0], "root")
    body["locators"] = {"particle_locator": [0, 0, 0]}
    m.cube(body, [-3, 6, -6], [6, 3, 12], body_mat)
    head = m.bone("head", [0, 8, -6], "body")
    m.cube(head, [-4, 6, -10], [8, 3, 4], Pal16("skin").with_deco(front=d_phantom_face()))
    m.cube(head, [-2, 6, -12], [4, 2, 2], Pal16("skin", 0.5).with_deco(front=d_snout()))
    m.cube(head, [-1, 6, -14], [2, 1, 2], Pal16("deep", 0.3))
    for x in (-4, 3):  # swept-back horns
        m.cube(head, [x, 9, -8], [1, 1, 3], Pal16("deep", 0.3), pivot=[x + 0.5, 9, -8], rotation=[20, 0, 0])
    wing = Pal16("deep", 0.7).with_deco(top=d_wing_lines())
    tip = Pal16("skin", 0.7).with_deco(top=[d_wing_lines(), d_wing_edge()])
    # (z, depth, base width, tip width, tip depth, point width, point depth)
    pairs = {"1": (-7, 6, 6, 8, 4, 4, 2), "2": (1, 5, 5, 6, 3, 3, 1)}
    for side in (-1, 1):
        s = "R" if side < 0 else "L"
        for pair, (z, dep, bw, tw, td, pw, pd) in pairs.items():
            pz = z + dep / 2
            wb = m.bone(f"wing{pair}{s}", [3 * side, 8.5, pz], "body")
            m.cube(wb, [-3 - bw if side < 0 else 3, 8, z], [bw, 1, dep], wing)
            e1 = (3 + bw) * side
            wt = m.bone(f"wing{pair}{s}Tip", [e1, 8.5, pz], wb["name"])
            tz = z + (dep - td) / 2
            m.cube(wt, [e1 - tw if side < 0 else e1, 8, tz], [tw, 1, td], tip)
            e2 = e1 + tw * side
            m.cube(wt, [e2 - pw if side < 0 else e2, 8, z + (dep - pd) / 2], [pw, 1, pd], tip)
    tail = m.bone("tail", [0, 7.5, 6], "body")
    m.cube(tail, [-1, 6, 6], [2, 2, 6], Pal16("skin", 0.6))
    tail2 = m.bone("tail2", [0, 7, 12], "tail")
    m.cube(tail2, [-1, 6.5, 12], [2, 1, 4], Pal16("deep", 0.5))
    m.cube(tail2, [-0.5, 6.5, 16], [1, 1, 2], Pal16("deep", 0.3))
    return m


def altar_model():
    m = Model(ALTAR, tex_w=64, bounds=(1.5, 2.5), ns="eu.sc")
    stone = Pal16("stone", 0.6)
    root = m.bone("root", [0, 0, 0])
    root["locators"] = {"particle_locator": [0, 0, 0]}
    m.cube(root, [-7, 0, -7], [14, 3, 14], stone)
    m.cube(root, [-5, 3, -5], [10, 2, 10], stone)
    m.cube(root, [-3, 5, -3], [6, 14, 6], stone.with_deco(sides=d_runes()))
    m.cube(root, [-5, 19, -5], [10, 2, 10], stone)
    m.cube(root, [-6, 21, -6], [12, 3, 12], stone.with_deco(top=d_soul_fire()))
    crystal = m.bone("crystal", [0, 28, 0], "root")
    m.cube(crystal, [-2, 25, -2], [4, 6, 4], Pal16("crystal"))
    return m


def with_outline(geo_json):
    """Adds the '.outline' geometry used by the outline render controller:
    the same bones with every cube inflated by 0.5."""
    out = copy.deepcopy(geo_json)
    extra = []
    for g in out["minecraft:geometry"]:
        o = copy.deepcopy(g)
        o["description"]["identifier"] += ".outline"
        for b in o["bones"]:
            b.pop("locators", None)
            for c in b.get("cubes", []):
                c["inflate"] = c.get("inflate", 0) + 0.5
        extra.append(o)
    out["minecraft:geometry"] += extra
    return out


# ============================================================ behaviour
def patch_mob(src, kind, color):
    """Turns one of the original entity files into a soul corrupted mob of the
    given colour: immunities, darkness, emerge property, loot, no vanilla
    conversions (drowned / stray), coloured creeper blasts."""
    d = copy.deepcopy(src)
    e = d["minecraft:entity"]
    desc = e["description"]
    desc["identifier"] = f"{NS}:{ident(kind, color)}"
    props = desc.setdefault("properties", {})
    props[f"{NS}:emerging"] = {"type": "bool", "default": False, "client_sync": True}
    comps, groups, events = e["components"], e.setdefault("component_groups", {}), e.setdefault("events", {})

    for k in ("minecraft:burns_in_daylight", "minecraft:hurt_on_condition"):
        comps.pop(k, None)
    comps["minecraft:fire_immune"] = {}
    old = comps.get("minecraft:damage_sensor", {}).get("triggers", [])
    comps["minecraft:damage_sensor"] = {"triggers": (old if isinstance(old, list) else [old]) + immunities()}

    def fix(k, v, parent):
        if k == "minecraft:attack":
            v.update({"effect_name": "darkness", "effect_duration": 8})
        elif k == "minecraft:movement" and isinstance(v, dict) and "value" in v:
            v["value"] = round(v["value"] * MOB_SPEED_BOOST, 4)
        elif k == "minecraft:loot":
            v["table"] = f"loot_tables/{NS}/{kind}.json"
        elif k == "minecraft:type_family":
            for f in ["soul_corrupted"] + (["soul_creeper"] if kind == "creeper" else []):
                if f not in v["family"]:
                    v["family"].append(f)
        elif k == "minecraft:environment_sensor":
            trig = v["triggers"] if isinstance(v["triggers"], list) else [v["triggers"]]
            v["triggers"] = [t for t in trig if t.get("event") not in REMOVED_EVENTS]
    walk(e, fix)

    for g in REMOVED_GROUPS:
        groups.pop(g, None)
    for ev in REMOVED_EVENTS:
        events.pop(ev, None)

    def drop_refs(k, v, parent):
        if k in ("add", "remove") and isinstance(v, dict) and "component_groups" in v:
            v["component_groups"] = [g for g in v["component_groups"] if g not in REMOVED_GROUPS]
    walk(events, drop_refs)

    groups[f"{NS}:emerging"] = {"minecraft:timer": {
        "looping": False, "time": BASE_MOBS[kind]["emerge"], "time_down_event": {"event": f"{NS}:emerged"}}}
    spawn_step = {"add": {"component_groups": [f"{NS}:emerging"]}, "set_property": {f"{NS}:emerging": True}}
    ev = events.get("minecraft:entity_spawned")
    if ev is None:
        events["minecraft:entity_spawned"] = spawn_step
    elif "sequence" in ev:
        ev["sequence"].append(spawn_step)
    else:
        events["minecraft:entity_spawned"] = {"sequence": [ev, spawn_step]}
    events[f"{NS}:emerged"] = {"remove": {"component_groups": [f"{NS}:emerging"]},
                               "set_property": {f"{NS}:emerging": False}}

    if kind == "creeper":
        # eu_sc:lit lets the script spawn the coloured explosion particles
        props[f"{NS}:lit"] = {"type": "bool", "default": False}
        for name in ("minecraft:start_exploding", "minecraft:start_exploding_forced"):
            for step in events[name]["sequence"]:
                step["set_property"] = {f"{NS}:lit": True}
        for name in ("minecraft:stop_exploding", "minecraft:become_charged"):
            events[name]["set_property"] = {f"{NS}:lit": False}
    return d


REMOVED_EVENTS = {"minecraft:start_transforming", "minecraft:stop_transforming", "minecraft:convert_to_drowned",
                  "got_in_powder_snow", "got_out_of_powder_snow", "become_stray_event"}
REMOVED_GROUPS = {"minecraft:convert_to_baby_drowned", "minecraft:convert_to_drowned",
                  "minecraft:start_drowned_transformation", "minecraft:look_to_start_drowned_transformation",
                  "become_stray", "in_powder_snow", "got_out_of_powder_snow_environment_sensor"}


def phantom_behavior(color):
    """Vanilla phantom AI (data driven, no navigation, glide movement), bigger,
    swooping much more often and circling much lower."""
    return {"format_version": "1.26.0", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{ident('phantom', color)}", "is_summonable": True,
                        "is_spawnable": True, "spawn_category": "monster",
                        "properties": {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}}},
        "component_groups": {f"{NS}:emerging": {"minecraft:timer": {
            "looping": False, "time": PHANTOM["emerge"], "time_down_event": {"event": f"{NS}:emerged"}}}},
        "components": {
            "minecraft:attack": {"damage": 6, "effect_name": "darkness", "effect_duration": 8},
            "minecraft:behavior.avoid_mob_type": {"ignore_visibility": True, "max_dist": 16,
                                                  "entity_types": [{"filters": fam("ocelot", "cat")}]},
            "minecraft:behavior.circle_around_anchor": {
                "priority": 3, "goal_radius": 1,
                "radius_range": {"min": 3, "max": 8},
                "height_offset_range": {"min": -2, "max": 3},
                "height_above_target_range": {"min": 6, "max": 12}},
            "minecraft:behavior.nearest_attackable_target": {
                "priority": 1, "reselect_targets": True, "scan_interval": 10, "target_search_height": 120,
                "within_radius": PHANTOM_DETECT, "must_see_forget_duration": 0.5,
                "entity_types": [{"filters": fam("player"), "max_dist": PHANTOM_DETECT}]},
            "minecraft:behavior.swoop_attack": {"priority": 2, "damage_reach": 0.5, "speed_multiplier": 1.1,
                                                "delay_range": {"min": 2, "max": 5}},
            "minecraft:breathable": {"breathes_air": True, "breathes_water": True, "suffocate_time": 0,
                                     "total_supply": 15},
            "minecraft:collision_box": {"height": 1.0, "width": 2.0},
            "minecraft:scale": {"value": PHANTOM_SCALE},
            "minecraft:conditional_bandwidth_optimization": {},
            "minecraft:despawn": {"despawn_from_distance": {}},
            "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 8 : 0"},
            "minecraft:follow_range": {"max": PHANTOM_DETECT, "value": PHANTOM_DETECT},
            "minecraft:game_event_movement_tracking": {"emit_flap": True},
            "minecraft:health": {"max": 34, "value": 34},
            "minecraft:fire_immune": {},
            "minecraft:damage_sensor": {"triggers": immunities(["fall"])},
            "minecraft:is_hidden_when_invisible": {},
            "minecraft:loot": {"table": f"loot_tables/{NS}/phantom.json"},
            "minecraft:movement": {"value": round(1.8 * FLIGHT_BOOST, 3)},
            "minecraft:movement.glide": {"speed_when_turning": round(0.2 * FLIGHT_BOOST, 3),
                                         "start_speed": round(0.1 * FLIGHT_BOOST, 3)},
            "minecraft:nameable": {},
            "minecraft:physics": {"has_gravity": False},
            "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
            "minecraft:type_family": {"family": ["phantom", "undead", "monster", "mob", "soul_corrupted"]},
        },
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:emerging"]},
                                         "set_property": {f"{NS}:emerging": True}},
            f"{NS}:emerged": {"remove": {"component_groups": [f"{NS}:emerging"]},
                              "set_property": {f"{NS}:emerging": False}},
        }}}


def mount_behavior():
    """Tameable with bones, rideable, flies like a happy ghast (same movement
    components) but a bit faster. Never spawns naturally."""
    wild = {
        "minecraft:tameable": {"probability": 0.33, "tame_items": "minecraft:bone",
                               "tame_event": {"event": f"{NS}:on_tame", "target": "self"}},
        "minecraft:behavior.float_tempt": {"priority": 4, "can_tempt_vertically": True, "items": ["minecraft:bone"],
                                           "within_radius": 16, "stop_distance": 5},
    }
    tamed = {
        "minecraft:is_tamed": {},
        "minecraft:rideable": {
            "seat_count": 1, "family_types": ["player"], "dismount_mode": "on_top_center",
            "interact_text": "action.interact.ride.horse",
            "seats": [{"min_rider_count": 0, "max_rider_count": 1, "position": [0.0, 1.45, 0.2],
                       "third_person_camera_radius": 7.0, "camera_relax_distance_smoothing": 6.0}]},
        "minecraft:free_camera_controlled": {"strafe_speed_modifier": 1.0, "backwards_movement_modifier": 0.5},
        "minecraft:vertical_movement_action": {"vertical_velocity": 0.5},
        "minecraft:behavior.player_ride_tamed": {"priority": 1},
        "minecraft:behavior.follow_owner": {"priority": 5, "speed_multiplier": 1.0, "start_distance": 14,
                                            "stop_distance": 5},
        "minecraft:behavior.float_tempt": {"priority": 6, "can_tempt_vertically": True, "items": ["minecraft:bone"],
                                           "within_radius": 16, "stop_distance": 5},
        "minecraft:healable": {"items": [{"item": "minecraft:bone", "heal_amount": 6}]},
    }
    comps = {
        "minecraft:type_family": {"family": ["soul_mount", "phantom", "mob", "soul_corrupted"]},
        "minecraft:health": {"value": 40, "max": 40},
        "minecraft:scale": {"value": PHANTOM_SCALE},
        "minecraft:collision_box": {"width": 2.0, "height": 1.0},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:can_fly": {},
        "minecraft:jump.static": {},
        "minecraft:movement": {"value": MOUNT_SPEED},
        "minecraft:flying_speed": {"value": MOUNT_SPEED},
        "minecraft:navigation.float": {"can_path_over_water": True, "avoid_damage_blocks": True, "avoid_water": True},
        "minecraft:behavior.float_wander": {"priority": 7, "must_reach": True, "random_reselect": True,
                                            "navigate_around_surface": True, "additional_collision_buffer": True,
                                            "allow_navigating_through_liquids": False, "surface_xz_dist": 16,
                                            "surface_y_dist": 8, "float_duration": [2.0, 7.0]},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.look_at_player": {"priority": 9, "look_distance": 8, "probability": 0.05},
        "minecraft:body_rotation_always_follows_head": {},
        "minecraft:follow_range": {"value": 16, "max": 16},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True, "breathes_water": True},
        "minecraft:damage_sensor": {"triggers": immunities(["fall"])},
        "minecraft:pushable_by_entity": {},
        "minecraft:pushable_by_block": {},
        "minecraft:nameable": {},
        "minecraft:persistent": {},
        "minecraft:leashable": {"presets": [{"hard_distance": 10, "max_distance": 14}]},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:loot": {"table": f"loot_tables/{NS}/{MOUNT}.json"},
    }
    return {"format_version": "1.26.0", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{MOUNT}", "is_spawnable": True, "is_summonable": True,
                        "spawn_category": "creature",
                        "properties": {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}}},
        "component_groups": {
            f"{NS}:wild": wild, f"{NS}:tamed": tamed,
            f"{NS}:emerging": {"minecraft:timer": {"looping": False, "time": PHANTOM["emerge"],
                                                    "time_down_event": {"event": f"{NS}:emerged"}}}},
        "components": comps,
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:wild", f"{NS}:emerging"]},
                                         "set_property": {f"{NS}:emerging": True}},
            f"{NS}:emerged": {"remove": {"component_groups": [f"{NS}:emerging"]},
                              "set_property": {f"{NS}:emerging": False}},
            f"{NS}:on_tame": {"remove": {"component_groups": [f"{NS}:wild"]},
                              "add": {"component_groups": [f"{NS}:tamed"]}},
        }}}


def altar_behavior():
    """Immune to all damage and never turns. Sneak + interact picks it up."""
    return {"format_version": "1.26.0", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{ALTAR}", "is_spawnable": True, "is_summonable": True},
        "component_groups": {f"{NS}:picked_up": {"minecraft:instant_despawn": {}}},
        "components": {
            "minecraft:type_family": {"family": ["soul_altar", "inanimate"]},
            "minecraft:health": {"value": 20, "max": 20},
            "minecraft:collision_box": {"width": 0.9, "height": 2.0},
            "minecraft:physics": {},
            "minecraft:knockback_resistance": {"value": 1.0},
            "minecraft:movement": {"value": 0.0},
            "minecraft:body_rotation_blocked": {},
            "minecraft:rotation_axis_aligned": {},
            "minecraft:persistent": {},
            "minecraft:fire_immune": {},
            "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
            "minecraft:interact": {"interactions": [{
                "on_interact": {"filters": {"all_of": [fam("player"),
                                                       {"test": "is_sneak_held", "subject": "other", "value": True}]},
                                "event": f"{NS}:pick_up", "target": "self"},
                "spawn_items": {"table": f"loot_tables/{NS}/{ALTAR}.json"},
                "play_sounds": "break",
                "swing": True,
                "interact_text": f"action.interact.{NS}.pick_up_altar"}]},
        },
        "events": {f"{NS}:pick_up": {"add": {"component_groups": [f"{NS}:picked_up"]}}},
    }}


def altar_recipe():
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": f"{NS}:{ALTAR}"},
        "tags": ["crafting_table"],
        "pattern": ["CLC", "CAC", "CCC"],
        "key": {"C": {"item": "minecraft:cobbled_deepslate"}, "L": {"item": "minecraft:soul_lantern"},
                "A": {"item": "minecraft:golden_apple"}},
        "result": {"item": f"{NS}:{ALTAR}_spawn_egg"}}}


# Blue and red only spawn in the Nether (their biomes); green only in the
# Overworld, in any biome except savannas and cold/frozen ones.
NETHER_BIOMES = {"blue": ["soul_sand_valley", "warped_forest", "basalt_deltas"],
                 "red": ["crimson_forest", "nether_wastes"]}
GREEN_OVERWORLD = {"all_of": [
    {"test": "has_biome_tag", "value": "overworld"},
    {"test": "has_biome_tag", "value": "monster"},
    {"test": "has_biome_tag", "operator": "!=", "value": "savanna"},
    {"test": "has_biome_tag", "operator": "!=", "value": "cold"},
    {"test": "has_biome_tag", "operator": "!=", "value": "frozen"}]}


def spawn_rules(identifier, weight, color, flying=False):
    herd = {"min_size": 1, "max_size": 1 if flying else 2}
    cond = {"minecraft:spawns_on_surface": {},
            "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
            "minecraft:herd": herd}
    if color == "green":
        if not flying:
            cond["minecraft:spawns_underground"] = {}
        cond.update({"minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
                     "minecraft:weight": {"default": weight},
                     "minecraft:biome_filter": GREEN_OVERWORLD})
    else:
        cond.update({"minecraft:spawns_underground": {},
                     "minecraft:weight": {"default": weight * (1 if flying else 2)},
                     "minecraft:biome_filter": {"any_of": [{"test": "has_biome_tag", "value": b}
                                                           for b in NETHER_BIOMES[color]]}})
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": f"{NS}:{identifier}", "population_control": "monster"},
        "conditions": [cond]}}


DROP_RATE = 0.25  # mobs drop items 75% less often


def loot(items, sword=True):
    rare = {"condition": "random_chance", "chance": DROP_RATE}
    pools = [{"rolls": 1, "conditions": [rare], "entries": [{"type": "item", "name": f"minecraft:{item}", "weight": 1,
                                                            "functions": [
        {"function": "set_count", "count": {"min": max(1, lo), "max": hi}},
        {"function": "looting_enchant", "count": {"min": 0, "max": 1}}]}]} for item, lo, hi in items]
    if sword:  # soul corrupted mobs: essence for the boss items, and the uncraftable sword
        pools.append({"rolls": 1, "conditions": [
            {"condition": "killed_by_player"},
            {"condition": "random_chance_with_looting", "chance": 0.35 * DROP_RATE, "looting_multiplier": 0.025}],
            "entries": [{"type": "item", "name": ESSENCE, "weight": 1, "functions": [
                {"function": "set_count", "count": {"min": 1, "max": 2}}]}]})
        pools.append({"rolls": 1, "conditions": [
            {"condition": "killed_by_player"},
            {"condition": "random_chance_with_looting", "chance": 0.025 * DROP_RATE, "looting_multiplier": 0.0025}],
            "entries": [{"type": "item", "name": SWORD, "weight": 1}]})
    return {"pools": pools}


def sword_item():
    # Only forms used by Microsoft's own item samples (format 1.21.70, icon as
    # a plain string, hand_equipped as a bool): an unrecognised component can
    # stop the whole item from loading.
    return {"format_version": "1.21.70", "minecraft:item": {
        "description": {"identifier": SWORD, "menu_category": {"category": "equipment"}},
        "components": {
            "minecraft:icon": "soul_corrupted_sword",
            "minecraft:display_name": {"value": f"item.{SWORD}.name"},
            "minecraft:max_stack_size": 1,
            "minecraft:hand_equipped": True,
            "minecraft:damage": 9,
            "minecraft:durability": {"max_durability": 2031, "damage_chance": {"min": 100, "max": 100}},
            "minecraft:enchantable": {"slot": "sword", "value": 15},
            "minecraft:repairable": {"repair_items": [{"items": ["minecraft:echo_shard"],
                                                       "repair_amount": "query.max_durability * 0.3"}]},
            # same tag as vanilla swords, so player animation packs treat it as one
            "minecraft:tags": {"tags": ["minecraft:is_sword"]},
        }}}


# ---- soul corrupted wither skeleton: fast, deadly slash, dies in one hit, drops nothing
WITHER = dict(es="Esqueleto Wither de Alma Corrupta", en="Soul Corrupted Wither Skeleton", weight=4,
              speed=0.4, damage=60, scale=1.2)


def wither_behavior(src_skeleton, color):
    d = patch_mob(src_skeleton, "skeleton", color)
    e = d["minecraft:entity"]
    e["description"]["identifier"] = f"{NS}:{ident('wither_skeleton', color)}"
    comps = e["components"]

    def fix(k, v, parent):
        if k == "minecraft:attack":
            v["damage"] = WITHER["damage"]  # one slash kills through full iron armour
        elif k == "minecraft:movement" and isinstance(v, dict):
            v["value"] = WITHER["speed"]  # vanilla wither skeleton: 0.25
        elif k == "minecraft:collision_box":
            v.update({"width": 0.7, "height": 2.4})
        elif k == "minecraft:type_family" and "soul_wither" not in v["family"]:
            v["family"].append("soul_wither")
        elif k == "minecraft:behavior.melee_box_attack":
            v["speed_multiplier"] = 1.4
    walk(e, fix)

    def strip(node):
        if isinstance(node, dict):
            for key in ("minecraft:loot", "minecraft:shooter"):
                node.pop(key, None)
            for v in node.values():
                strip(v)
    strip(e)
    comps["minecraft:health"] = {"value": 1, "max": 1}
    comps["minecraft:scale"] = {"value": WITHER["scale"]}
    comps["minecraft:experience_reward"] = {"on_death": "0"}
    comps["minecraft:equipment"] = {"table": f"loot_tables/{NS}/equipment/wither_sword.json",
                                    "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0.0}]}
    comps.pop("minecraft:shareables", None)
    comps.pop("minecraft:behavior.pickup_items", None)
    return d


def script(bosses):
    effects, ignite = {}, {}
    for name, B in bosses.BOSSES.items():
        effects[f"{NS}:{name}"] = [DARKNESS] + COLORS[B["color"]]["extra"]
        if COLORS[B["color"]]["ignite"]:
            ignite[f"{NS}:{name}"] = COLORS[B["color"]]["ignite"]
    for color, C in COLORS.items():
        for kind in list(BASE_MOBS) + ["phantom", "wither_skeleton"]:
            mob = f"{NS}:{ident(kind, color)}"
            effects[mob] = [DARKNESS] + C["extra"]
            if C["ignite"]:
                ignite[mob] = C["ignite"]
    skeletons = [f"{NS}:{ident('skeleton', c)}" for c in COLORS]
    return f"""// Soul Corrupted Mobs: effects on hit, lightning arrows, sword, healing altar,
// coloured creeper explosions. Generated by tools/soul_mobs.py.
import {{ GameMode, ItemStack, system, world }} from "@minecraft/server";

// [effect, duration in ticks, amplifier] applied to whatever the mob hurts
// (melee hit, arrow or explosion).
const HIT_EFFECTS = {json.dumps(effects, indent=2)};

// Seconds the red variants set their victims on fire for.
const IGNITE = {json.dumps(ignite, indent=2)};

// Soul corrupted wither skeletons: their slash leaves a burst of soul sparks.
const WITHERS = {json.dumps([f"{NS}:{ident('wither_skeleton', c)}" for c in COLORS])};

// Original add-on: soul corrupted skeleton arrows become lightning (all colours).
const LIGHTNING_SKELETONS = {json.dumps(skeletons)};

const SWORD = "{SWORD}";
const SWORD_AREA = {{ radius: 3, damage: 5 }};
const ALTAR = "{NS}:{ALTAR}";
const ALTAR_RANGE = {ALTAR_RANGE};
const DIMENSIONS = ["overworld", "nether", "the_end"];

function particle(dimension, id, location) {{
  try {{
    dimension.spawnParticle(id, location);
  }} catch {{
    // chunk not loaded
  }}
}}

function summonLightningOnImpact(event) {{
  if (event.projectile?.typeId !== "minecraft:arrow") return;
  if (!LIGHTNING_SKELETONS.includes(event.source?.typeId)) return;
  event.projectile.remove();
  event.dimension.spawnEntity("minecraft:lightning_bolt", event.location);
}}
world.afterEvents.projectileHitEntity.subscribe(summonLightningOnImpact);
world.afterEvents.projectileHitBlock.subscribe(summonLightningOnImpact);

function heldItem(player) {{
  try {{
    return player.getComponent("minecraft:equippable")?.getEquipment("Mainhand");
  }} catch {{
    return undefined;
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
    if (WITHERS.includes(attacker.typeId)) {{
      const at = victim.location;
      particle(victim.dimension, "{NS}:slash", {{ x: at.x, y: at.y + 1, z: at.z }});
    }}
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

// The altar always faces the same way.
world.afterEvents.entitySpawn.subscribe(({{ entity }}) => {{
  try {{
    if (entity.typeId === ALTAR) entity.setRotation({{ x: 0, y: 0 }});
  }} catch {{
    // already gone
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
const COLOR_OF = {json.dumps({f"{NS}:{ident('creeper', c)}": c for c in COLORS})};
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
      info.color = COLOR_OF[creeper.typeId] ?? "blue";
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
""" + boss_script(bosses)


def boss_script(bosses):
    cfg = {f"{NS}:{n}": {"hp": B["hp"], "deathTicks": B["death_ticks"], "color": B["color"],
                         "loot": B["loot"], "xp": B["xp"], "minions": [f"{NS}:{m}" for m in B["minions"]]}
           for n, B in bosses.BOSSES.items()}
    return f"""
// ============================================================ mini bosses
// A boss never really dies: when its health reaches HP_BUFFER it becomes
// invulnerable (state 2), the death animation plays, then it is removed here.
const BOSSES = {json.dumps(cfg, indent=2)};
const SKELETON_BOSS = "{NS}:{bosses.SKELETON_BOSS}";
const ZOMBIE_BOSS = "{NS}:{bosses.ZOMBIE_BOSS}";
const RED_ZOMBIE = "{NS}:{ident('zombie', 'red')}";
const HP_BUFFER = {bosses.HP_BUFFER};
const SUMMON_ITEMS = {{ "{bosses.STAR}": SKELETON_BOSS, "{bosses.PLANT}": ZOMBIE_BOSS }};
const ACTION = {{ none: 0, blast: 1, dash: 2, summon: 3 }};
const NOT_PLAYING = [GameMode.Creative ?? GameMode.creative, GameMode.Spectator ?? GameMode.spectator];
const timers = new Map();
const dying = new Set();

function prop(entity, name) {{
  try {{
    return entity.getProperty(name);
  }} catch {{
    return undefined;
  }}
}}

function setAction(boss, action, ticks) {{
  try {{
    boss.setProperty("{NS}:action", action);
  }} catch {{
    return;
  }}
  system.runTimeout(() => {{
    try {{
      if (boss.getProperty("{NS}:action") === action) boss.setProperty("{NS}:action", ACTION.none);
    }} catch {{
      // gone
    }}
  }}, ticks);
}}

function around(location, radius) {{
  const a = Math.random() * Math.PI * 2;
  return {{ x: location.x + Math.cos(a) * radius, y: location.y, z: location.z + Math.sin(a) * radius }};
}}

function startDying(boss) {{
  const cfg = BOSSES[boss.typeId];
  if (!cfg || dying.has(boss.id)) return;
  dying.add(boss.id);
  boss.triggerEvent("{NS}:start_dying");
  system.runTimeout(() => {{
    dying.delete(boss.id);
    try {{
      const dimension = boss.dimension;
      const location = boss.location;
      particle(dimension, `{NS}:explosion_${{cfg.color}}`, {{ x: location.x, y: location.y + 1, z: location.z }});
      for (const [item, min, max] of cfg.loot) {{
        const amount = min + Math.floor(Math.random() * (max - min + 1));
        if (amount > 0) dimension.spawnItem(new ItemStack(item, amount), location);
      }}
      for (let i = 0; i < Math.ceil(cfg.xp / 10); i++) dimension.spawnEntity("minecraft:xp_orb", around(location, 0.5));
      for (const minion of cfg.minions) dimension.spawnEntity(minion, around(location, 1.5));
      boss.remove();
    }} catch {{
      // unloaded
    }}
  }}, cfg.deathTicks);
}}

world.afterEvents.entityHurt.subscribe(({{ hurtEntity }}) => {{
  if (!BOSSES[hurtEntity.typeId]) return;
  try {{
    const health = hurtEntity.getComponent("minecraft:health");
    if (health && health.currentValue <= HP_BUFFER) startDying(hurtEntity);
  }} catch {{
    // gone
  }}
}});

function blast(boss, effect, amplifier) {{
  setAction(boss, ACTION.blast, 16);
  system.runTimeout(() => {{
    try {{
      const {{ dimension, location }} = boss;
      dimension.createExplosion(location, 2.2, {{ breaksBlocks: false, causesFire: false, source: boss }});
      particle(dimension, `{NS}:explosion_${{BOSSES[boss.typeId].color}}`, {{ x: location.x, y: location.y + 1, z: location.z }});
      for (const player of dimension.getPlayers({{ location, maxDistance: 6 }})) {{
        player.addEffect(effect, 60, {{ amplifier, showParticles: true }});
      }}
    }} catch {{
      // gone
    }}
  }}, 8);
}}

function dash(boss, target) {{
  setAction(boss, ACTION.dash, 16);
  const from = boss.location;
  const dx = target.location.x - from.x, dz = target.location.z - from.z;
  const len = Math.max(0.1, Math.hypot(dx, dz));
  try {{
    boss.applyImpulse({{ x: (dx / len) * 1.6, y: 0.25, z: (dz / len) * 1.6 }});
  }} catch {{
    return;
  }}
  let hit = false;
  for (let t = 2; t <= 14; t += 2) {{
    system.runTimeout(() => {{
      if (hit) return;
      try {{
        const b = boss.location, p = target.location;
        if (Math.hypot(b.x - p.x, b.y - p.y, b.z - p.z) < 2.0) {{
          hit = true;
          target.addEffect("slowness", 20, {{ amplifier: 254, showParticles: true }});
          target.applyDamage(6, {{ cause: "entityAttack", damagingEntity: boss }});
        }}
      }} catch {{
        // gone
      }}
    }}, t);
  }}
}}

function summonMinions(boss) {{
  const nearby = boss.dimension.getEntities({{ type: RED_ZOMBIE, location: boss.location, maxDistance: 16 }}).length;
  if (nearby >= 4) return false;
  setAction(boss, ACTION.summon, 22);
  system.runTimeout(() => {{
    try {{
      for (let i = 0; i < 2; i++) boss.dimension.spawnEntity(RED_ZOMBIE, around(boss.location, 2));
    }} catch {{
      // gone
    }}
  }}, 11);
  return true;
}}

const rand = (min, max) => min + Math.floor(Math.random() * (max - min));

system.runInterval(() => {{
  const now = system.currentTick;
  for (const id of DIMENSIONS) {{
    let dimension;
    try {{
      dimension = world.getDimension(id);
    }} catch {{
      continue;
    }}
    for (const boss of dimension.getEntities({{ families: ["soul_boss"] }})) {{
      if (prop(boss, "{NS}:state") !== 1 || prop(boss, "{NS}:action") !== ACTION.none) continue;
      const target = dimension.getPlayers({{
        location: boss.location, maxDistance: 24, closest: 1, excludeGameModes: NOT_PLAYING,
      }})[0];
      if (!target) continue;
      let t = timers.get(boss.id);
      if (!t) {{
        t = {{ blast: now + rand(100, 200), dash: now + rand(60, 140), summon: now + rand(160, 260) }};
        timers.set(boss.id, t);
      }}
      const b = boss.location, p = target.location;
      const dist = Math.hypot(b.x - p.x, b.y - p.y, b.z - p.z);
      if (boss.typeId === SKELETON_BOSS) {{
        if (now >= t.blast && dist < 6) {{
          blast(boss, "blindness", 0);
          t.blast = now + rand(160, 280);
        }}
      }} else if (boss.typeId === ZOMBIE_BOSS) {{
        if (now >= t.blast && dist < 5) {{
          blast(boss, "slowness", 1);
          t.blast = now + rand(180, 300);
        }} else if (now >= t.dash && dist > 3 && dist < 14) {{
          dash(boss, target);
          t.dash = now + rand(120, 200);
        }} else if (now >= t.summon) {{
          summonMinions(boss);
          t.summon = now + rand(300, 420);
        }}
      }}
    }}
  }}
}}, 10);

// Summoning items: the star drops the Mutant Skeleton from the sky,
// the plant makes the Blade Zombie claw its way out of the ground.
world.afterEvents.itemUse.subscribe(({{ source: player, itemStack }}) => {{
  const boss = SUMMON_ITEMS[itemStack?.typeId];
  if (!boss) return;
  try {{
    const dir = player.getViewDirection();
    const len = Math.max(0.1, Math.hypot(dir.x, dir.z));
    const at = {{
      x: player.location.x + (dir.x / len) * 4,
      y: player.location.y + (boss === SKELETON_BOSS ? 18 : 0),
      z: player.location.z + (dir.z / len) * 4,
    }};
    player.dimension.spawnEntity(boss, at);
    if (player.getGameMode() !== (GameMode.Creative ?? GameMode.creative)) {{
      const equipment = player.getComponent("minecraft:equippable");
      const held = equipment.getEquipment("Mainhand");
      if (held?.typeId === itemStack.typeId) {{
        if (held.amount > 1) {{
          held.amount -= 1;
          equipment.setEquipment("Mainhand", held);
        }} else {{
          equipment.setEquipment("Mainhand", undefined);
        }}
      }}
    }}
  }} catch {{
    // could not summon here
  }}
}});
"""


# ============================================================= resources
def kf(d):
    return {str(k): {"post": v, "lerp_mode": "catmullrom"} for k, v in d.items()}


WALK = "query.modified_distance_moved * 38.17"
SPEED = "variable.s_speed"
TURN = "variable.s_turn"
# No '??' here: it isn't valid Molang for the older client entity formats the
# original files use, and a Molang error makes the mob invisible.
SMOOTHING_INIT = ["variable.s_speed = 0.0;", "variable.s_turn = 0.0;"]
SMOOTHING = [
    "variable.s_speed = math.lerp(variable.s_speed, query.modified_move_speed, 0.1);",
    "variable.s_turn = math.lerp(variable.s_turn, math.clamp(query.yaw_speed, -120.0, 120.0), 0.05);",
]
FLAP = "query.life_time * 300.0"
A = f"animation.{NS}"

ANIMS = {
    "particles": {"loop": True, "animation_length": 0.2,
                  "particle_effects": {"0.0": [{"effect": "wisps"}, {"effect": "drips"}]}},
    # ---- extra life on top of the vanilla animations
    "zombie_life": {"loop": True, "bones": {
        "body": {"rotation": [f"{SPEED} * (query.has_target ? 17.0 : 9.0)", 0.0,
                              f"math.sin({WALK} * 0.5) * 3.5 * {SPEED}"]},
        "head": {"rotation": ["math.sin(query.life_time * 18.0) * 2.5", 0.0, "math.sin(query.life_time * 24.0) * 4.0"]}}},
    "creeper_life": {"loop": True, "bones": {
        "body": {"rotation": [f"{SPEED} * 14.0", 0.0, f"math.clamp({TURN} * 0.1, -9.0, 9.0)"],
                 "position": [0.0, f"math.abs(math.sin({WALK})) * 0.4 * {SPEED}", 0.0]},
        "head": {"rotation": [f"-{SPEED} * 10.0", 0.0, "math.sin(query.life_time * 28.0) * 2.5"]}}},
    "skeleton_life": {"loop": True, "bones": {
        "body": {"rotation": [f"{SPEED} * (query.has_target ? 8.0 : 4.0)", 0.0, 0.0]},
        "head": {"rotation": ["math.sin(query.life_time * 15.0) * 2.0", "math.sin(query.life_time * 12.0) * 8.0",
                              "math.sin(query.life_time * 21.0) * 3.0"]}}},
    # ---- soul corrupted wither skeleton: leaning sprint with the arms swept back, huge slash
    "wither_run": {"loop": True, "bones": {
        "body": {"rotation": [f"{SPEED} * 32.0", f"math.sin({WALK}) * 10.0 * {SPEED}", 0.0]},
        "head": {"rotation": [f"-{SPEED} * 26.0", 0.0, 0.0]},
        "rightArm": {"rotation": [f"{SPEED} * 60.0 + math.cos({WALK}) * -25.0 * {SPEED}", 0.0, f"{SPEED} * 18.0"]},
        "leftArm": {"rotation": [f"{SPEED} * 60.0 + math.cos({WALK}) * 25.0 * {SPEED}", 0.0, f"-{SPEED} * 18.0"]},
        "rightLeg": {"rotation": [f"math.cos({WALK}) * 35.0 * {SPEED} - {SPEED} * 20.0", 0.0, 0.0]},
        "leftLeg": {"rotation": [f"math.cos({WALK}) * -35.0 * {SPEED} - {SPEED} * 20.0", 0.0, 0.0]}}},
    "wither_slash": {"loop": True, "bones": {
        "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 140.0",
                                  "math.sin(variable.attack_time * 360.0) * 40.0", 0.0]},
        "body": {"rotation": ["math.sin(variable.attack_time * 180.0) * 20.0",
                              "math.sin(variable.attack_time * 360.0) * -45.0", 0.0]},
        "leftArm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 45.0", 0.0,
                                 "-math.sin(variable.attack_time * 180.0) * 35.0"]}}},
    # ---- spawn animations
    "zombie_spawn": {"loop": "hold_on_last_frame", "animation_length": 1.2, "bones": {
        "waist": {"position": kf({0.0: [0, -30, 0], 0.35: [0, -20, 0], 0.75: [0, -8, 0], 1.0: [0, -1, 0], 1.2: [0, 0, 0]}),
                  "rotation": kf({0.0: [28, 0, 0], 0.45: [20, 0, -6], 0.85: [8, 0, 4], 1.2: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [-28, 0, 0], 0.6: [-12, 8, 8], 1.0: [3, -4, -4], 1.2: [0, 0, 0]})}}},
    "skeleton_spawn": {"loop": "hold_on_last_frame", "animation_length": 1.2, "bones": {
        "waist": {"position": kf({0.0: [0, -32, 0], 0.4: [0, -21, 0], 0.8: [0, -8, 0], 1.05: [0, -1, 0], 1.2: [0, 0, 0]}),
                  "rotation": kf({0.0: [18, 0, 8], 0.4: [14, 0, -8], 0.8: [8, 0, 6], 1.05: [3, 0, -3], 1.2: [0, 0, 0]})},
        "rightArm": {"rotation": kf({0.0: [-175, 0, 12], 0.4: [-158, 0, 24], 0.8: [-160, 0, 10], 1.05: [-60, 0, 8], 1.2: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [-160, 0, -20], 0.4: [-175, 0, -10], 0.8: [-150, 0, -20], 1.05: [-50, 0, -6], 1.2: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [-35, 0, 0], 0.4: [-18, 18, 10], 0.8: [-8, -18, -10], 1.05: [6, 0, 0], 1.2: [0, 0, 0]})}}},
    "creeper_spawn": {"loop": "hold_on_last_frame", "animation_length": 0.9, "bones": {
        "body": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.35: [0.7, 0.65, 0.7], 0.6: [1.12, 1.1, 1.12],
                              0.75: [0.96, 0.97, 0.96], 0.9: [1, 1, 1]}),
                 "rotation": kf({0.0: [0, -180, 0], 0.6: [0, -12, 0], 0.9: [0, 0, 0]})}}},
    "phantom_spawn": {"loop": "hold_on_last_frame", "animation_length": 0.8, "bones": {
        "root": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.45: [1.1, 1.1, 1.1], 0.65: [0.96, 0.96, 0.96], 0.8: [1, 1, 1]}),
                 "rotation": kf({0.0: [0, -180, 0], 0.5: [0, -10, 0], 0.8: [0, 0, 0]})}}},
    # ---- phantom: pitches with its dive, two wing pairs out of phase
    "phantom_fly": {"loop": True, "animation_length": 1.2, "sound_effects": {"0.6": {"effect": "flap"}},
                    "bones": dict(
        {f"wing{p}{s}": {"rotation": [0.0, 0.0, f"{sg}math.sin({FLAP}{ph}) * 20.0"]}
         for p, ph in (("1", ""), ("2", " - 70.0")) for s, sg in (("R", ""), ("L", "-"))},
        **{f"wing{p}{s}Tip": {"rotation": [0.0, 0.0, f"{sg}math.sin({FLAP}{ph} - 50.0) * 18.0"]}
           for p, ph in (("1", ""), ("2", " - 70.0")) for s, sg in (("R", ""), ("L", "-"))},
        body={"position": [0.0, f"math.sin({FLAP} + 90.0) * 0.6", 0.0],
              "rotation": ["-query.target_x_rotation", 0.0, f"math.clamp({TURN} * 0.12, -15.0, 15.0)"]},
        tail={"rotation": [f"math.sin({FLAP} - 60.0) * 7.0", "math.sin(query.life_time * 90.0) * 5.0", 0.0]},
        tail2={"rotation": [f"math.sin({FLAP} - 110.0) * 9.0", 0.0, 0.0]},
    )},
    # ---- altar: floating, spinning crystal
    "altar_float": {"loop": True, "bones": {
        "crystal": {"rotation": [0.0, "query.life_time * 45.0", 0.0],
                    "position": [0.0, "math.sin(query.life_time * 90.0) * 1.0", 0.0]}}},
    "altar_particles": {"loop": True, "animation_length": 0.25, "particle_effects": {"0.0": [{"effect": "wisps"}]}},
}

LIFE = {"zombie": ["zombie_life"], "creeper": ["creeper_life"], "skeleton": ["skeleton_life"],
        "phantom": ["phantom_fly"]}


def controllers():
    prop = f"query.property('{NS}:emerging')"
    out = {}
    for kind, life in LIFE.items():
        out[f"controller.animation.{NS}.{kind}"] = {"initial_state": "start", "states": {
            "start": {"transitions": [{"emerging": prop}, {"alive": f"!{prop}"}]},
            "emerging": {"animations": [f"{kind}_spawn"], "particle_effects": [{"effect": "burst"}],
                         "transitions": [{"alive": f"!{prop}"}], "blend_transition": 0.3},
            "alive": {"animations": life, "blend_transition": 0.3},
        }}
    return {"format_version": "1.10.0", "animation_controllers": out}


def add_soul_extras(desc, kind, color):
    """Adds the spawn animation, extra life, coloured particles to a client entity."""
    scripts = desc.setdefault("scripts", {})
    scripts["initialize"] = scripts.get("initialize", []) + SMOOTHING_INIT
    scripts["pre_animation"] = scripts.get("pre_animation", []) + SMOOTHING
    anims = desc.setdefault("animations", {})
    animate = scripts.setdefault("animate", [])
    # the original skeleton lists its controllers the legacy way (format 1.8.0):
    # move them to "animate", which needs format 1.10.0
    for entry in desc.pop("animation_controllers", []):
        for name, ctrl in entry.items():
            anims[name] = ctrl
            animate.append(name)
    anims[f"{NS}_controller"] = f"controller.animation.{NS}.{kind}"
    anims[f"{NS}_particles"] = f"{A}.particles"
    anims[f"{kind}_spawn"] = f"{A}.{kind}_spawn"
    for name in LIFE[kind]:
        anims[name] = f"{A}.{name}"
    animate += [f"{NS}_controller", f"{NS}_particles"]
    desc.setdefault("particle_effects", {}).update({
        "emitter": f"{NS}:soul_ascending_particle" + COLORS[color]["suffix"],
        "wisps": f"{NS}:wisp_{color}", "drips": f"{NS}:drip_{color}", "burst": f"{NS}:burst_{color}"})


def phantom_client(identifier, texture, color, egg):
    desc = {
        "identifier": f"{NS}:{identifier}",
        "materials": {"default": "outline_base", "outline_main": "outline_main"},
        "textures": {"default": f"{TEX}/{texture}", "outline_main": OUTLINE_TEX},
        "geometry": {"default": "geometry.eu.sc.soul_corrupted_phantom",
                     "outline_main": "geometry.eu.sc.soul_corrupted_phantom.outline"},
        "spawn_egg": egg,
        "scripts": {"animate": ["emitter_particle_controller"], "should_update_effects_offscreen": "1.0"},
        "animations": {"emitter_particle_controller": "controller.animation.eu.emitter_particle"},
        "sound_effects": {"flap": "mob.phantom.flap"},
        "render_controllers": ["controller.render.eu_sc.outline_base.glow", "controller.render.eu_sc.outline_main.glow"],
    }
    add_soul_extras(desc, "phantom", color)
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def altar_client():
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": f"{NS}:{ALTAR}",
        "materials": {"default": "outline_base", "outline_main": "outline_main"},
        "textures": {"default": f"{TEX}/{ALTAR}", "outline_main": OUTLINE_TEX},
        "geometry": {"default": f"geometry.eu.sc.{ALTAR}", "outline_main": f"geometry.eu.sc.{ALTAR}.outline"},
        "animations": {"float": f"{A}.altar_float", "particles": f"{A}.altar_particles"},
        "particle_effects": {"wisps": f"{NS}:altar_wisp"},
        "scripts": {"animate": ["float", "particles"]},
        "render_controllers": ["controller.render.eu_sc.outline_base", "controller.render.eu_sc.outline_main.glow"],
        "spawn_egg": {"texture": "healing_altar_egg"},
    }}}


def my_particle(name, rgb, comps, size=0.14):
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
        "description": {"identifier": f"{NS}:{name}",
                        "basic_render_parameters": {"material": "particles_alpha",
                                                    "texture": "textures/particles/soul_corrupted/soul_spark"}},
        "components": base}}


def once(n):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": 0.1}}


def particles(ascending):
    out = {}
    body = {"offset": [0, 0.9, 0], "half_dimensions": [0.3, 0.7, 0.3]}
    for color, C in COLORS.items():
        rgb = C["rgb"]
        if C["suffix"]:  # recoloured copy of the original ascending soul particle
            p = copy.deepcopy(ascending)
            p["particle_effect"]["description"]["identifier"] += C["suffix"]
            hi, lo = "variable.particle_random_3 * 0.5 + 0.5", "variable.particle_random_3 * 0.25 + 0.12"
            tint = p["particle_effect"]["components"]["minecraft:particle_appearance_tinting"]["color"]
            tint[:3] = [hi, lo, lo] if color == "red" else [lo, hi, lo]
            out[f"soul_ascending_particle{C['suffix']}"] = p
        out[f"wisp_{color}"] = my_particle(f"wisp_{color}", rgb, dict(once(2), **{
            "minecraft:emitter_shape_box": dict(body, direction=[0, 1, 0]),
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.4)"},
            "minecraft:particle_initial_speed": "math.random(0.2, 0.5)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.8, 0], "linear_drag_coefficient": 0.8}}))
        out[f"drip_{color}"] = my_particle(f"drip_{color}", rgb, dict(once(1), **{
            "minecraft:emitter_shape_box": dict(body, direction="outwards"),
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.6, 1.0)"},
            "minecraft:particle_initial_speed": "math.random(0.3, 0.8)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -6.0, 0], "linear_drag_coefficient": 1.0},
            "minecraft:particle_motion_collision": {"collision_radius": 0.05, "coefficient_of_restitution": 0.2,
                                                    "collision_drag": 4.0}}), size=0.1)
        out[f"burst_{color}"] = my_particle(f"burst_{color}", rgb, dict(once(45), **{
            "minecraft:emitter_shape_disc": {"offset": [0, 0.1, 0], "radius": 0.8, "plane_normal": "y",
                                             "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.4)"},
            "minecraft:particle_initial_speed": "math.random(1.0, 2.5)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 2.0, 0], "linear_drag_coefficient": 2.0}}),
            size=0.18)
        out[f"explosion_{color}"] = my_particle(f"explosion_{color}", rgb, dict(once(160), **{
            "minecraft:emitter_shape_sphere": {"radius": 0.6, "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.9, 1.8)"},
            "minecraft:particle_initial_speed": "math.random(3.0, 9.0)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -1.5, 0], "linear_drag_coefficient": 2.2}}),
            size=0.3)
    blue = COLORS["blue"]["rgb"]
    out["heal_beam"] = my_particle("heal_beam", (0.55, 1.0, 0.85), dict(once(1), **{
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.3},
        "minecraft:particle_initial_speed": 0.0}), size=0.11)
    out["heal_spark"] = my_particle("heal_spark", (0.55, 1.0, 0.7), dict(once(6), **{
        "minecraft:emitter_shape_sphere": {"radius": 0.4, "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.7},
        "minecraft:particle_initial_speed": 0.6,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.0, 0], "linear_drag_coefficient": 1.5}}),
        size=0.14)
    out["sweep"] = my_particle("sweep", blue, dict(once(36), **{
        "minecraft:emitter_shape_disc": {"radius": 0.3, "plane_normal": "y", "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": 0.45},
        "minecraft:particle_initial_speed": 7.0,
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 5.0}}), size=0.16)
    out["slash"] = my_particle("slash", (0.75, 0.97, 1.0), dict(once(60), **{
        "minecraft:emitter_shape_disc": {"radius": 0.6, "plane_normal": [0.4, 1, 0], "direction": "outwards"},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.25, 0.45)"},
        "minecraft:particle_initial_speed": "math.random(6.0, 9.0)",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 6.0}}), size=0.22)
    out["altar_wisp"] = my_particle("altar_wisp", blue, dict(once(2), **{
        "minecraft:emitter_shape_disc": {"offset": [0, 1.5, 0], "radius": 0.35, "plane_normal": "y",
                                         "direction": [0, 1, 0]},
        "minecraft:particle_lifetime_expression": {"max_lifetime": "math.random(0.8, 1.3)"},
        "minecraft:particle_initial_speed": "math.random(0.3, 0.6)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.6, 0], "linear_drag_coefficient": 0.8}}),
        size=0.12)
    return out


SOUNDS = {
    "zombie": {"events": {"ambient": "mob.zombie.say", "hurt": "mob.zombie.hurt", "death": "mob.zombie.death",
                          "step": {"sound": "mob.zombie.step", "volume": 0.15}}, "pitch": [0.8, 1.2], "volume": 1.0},
    "skeleton": {"events": {"ambient": "mob.skeleton.say", "hurt": "mob.skeleton.hurt",
                            "death": "mob.skeleton.death", "step": {"sound": "mob.skeleton.step", "volume": 1.0},
                            "shoot": {"sound": "random.bow", "volume": 1.0}}, "pitch": [0.8, 1.2], "volume": 1.0},
    "phantom": {"events": {"ambient": "mob.phantom.idle", "hurt": "mob.phantom.hurt", "death": "mob.phantom.death",
                           "swoop": {"sound": "mob.phantom.swoop", "volume": 1.0}, "attack": "mob.phantom.bite"},
                "pitch": [0.7, 0.9], "volume": 2.0},
}


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
SWORD_COLORS = {"O": "#0d1b28", "W": "#ffffff", "L": "#9df1f3", "B": "#24c7dd", "D": "#3cdae6",
                "C": "#6deaec", "H": "#2a3a4a", "P": "#cef8f9"}
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
ALTAR_EGG_COLORS = {"C": "#3cdae6", "W": "#ffffff", "S": "#454b59", "T": "#2a2e38", "F": "#9df1f3", "R": "#6deaec"}
SPARK_ROWS = ["...##...", "..####..", ".######.", "########", "########", ".######.", "..####..", "...##..."]


def preview_geo(geo, img, path, view="front", scale=8):
    """Orthographic view of a geometry JSON (rotations ignored), with the white
    outline drawn behind like in game."""
    bones = geo.get("bones")
    if bones is None:
        g = [v for k, v in geo.items() if k.startswith("geometry")]
        bones = g[0]["bones"] if g else geo["minecraft:geometry"][0]["bones"]
    tw, th = img.size
    desc_w = geo.get("texturewidth") or tw
    k = tw / desc_w
    cubes = [c for b in bones for c in b.get("cubes", [])]
    ax = 2 if view == "top" else 1  # vertical axis of the picture
    xs = [c["origin"][0] for c in cubes] + [c["origin"][0] + c["size"][0] for c in cubes]
    vs = [c["origin"][ax] for c in cubes] + [c["origin"][ax] + c["size"][ax] for c in cubes]
    minx, maxx, minv, maxv = min(xs) - 1, max(xs) + 1, min(vs) - 1, max(vs) + 1
    out = Image.new("RGBA", (int((maxx - minx) * scale), int((maxv - minv) * scale)), (40, 46, 60, 255))

    def place(c, grow=0.0):
        x0 = c["origin"][0] - minx - grow
        if view == "top":
            y0 = c["origin"][2] - minv - grow
            h = c["size"][2] + 2 * grow
        else:
            y0 = maxv - (c["origin"][1] + c["size"][1]) - grow
            h = c["size"][1] + 2 * grow
        return int(x0 * scale), int(y0 * scale), int((c["size"][0] + 2 * grow) * scale), int(h * scale)

    for c in cubes:  # outline
        x, y, w, h = place(c, 0.5 + c.get("inflate", 0))
        out.paste((255, 255, 255, 255), (x, y, x + w, y + h))
    order = sorted(cubes, key=lambda c: (c["origin"][1] + c["size"][1]) if view == "top" else -c["origin"][2])
    for c in order:
        w, h, d = c["size"]
        u, v = c["uv"]
        if view == "top":
            box = (u + d, v, u + d + w, v + d)
            fh = d
        else:
            box = (u + d, v + d, u + d + w, v + d + h)
            fh = h
        face = img.crop(tuple(int(round(b * k)) for b in box))
        x, y, pw, ph = place(c)
        out.alpha_composite(face.resize((int(w * scale), int(fh * scale)), Image.NEAREST), (x, y))
    out.save(path)


# ================================================================== build
def lang(es):
    lines = [f"pack.name={ADDON_NAME}", "pack.description=Have fun!", ""]

    def add(identifier, name, egg_prefix=True):
        lines.append(f"entity.{NS}:{identifier}.name={name}")
        prefix = ("Generar " if es else "Spawn ") if egg_prefix else ""
        lines.append(f"item.spawn_egg.entity.{NS}:{identifier}.name={prefix}{name}")

    for kind, M in list(BASE_MOBS.items()) + [("phantom", PHANTOM)]:
        for color, C in COLORS.items():
            base = M["es"] if es else M["en"]
            add(ident(kind, color), base if color == "blue" else f"{base} ({C['es'] if es else C['en']})")
    for color, C in COLORS.items():
        base = WITHER["es"] if es else WITHER["en"]
        add(ident("wither_skeleton", color), base if color == "blue" else f"{base} ({C['es'] if es else C['en']})")
    add(MOUNT, "Phantom de Alma Domable" if es else "Tameable Soul Phantom")
    add(ALTAR, "Altar de Curación" if es else "Healing Altar", egg_prefix=False)
    lines += [f"item.{SWORD}.name={'Espada de Alma Corrupta' if es else 'Soul Corrupted Sword'}",
              f"action.interact.{NS}.pick_up_altar={'Recoger altar' if es else 'Pick up altar'}"]
    return "\n".join(lines) + "\n"


def main():
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(os.path.join(SRC, os.path.basename(d).split("_")[-1]), d)
    prev = "--preview" in sys.argv
    prev_dir = os.path.join(ROOT, "previews", "soul_mobs")
    if prev:
        shutil.rmtree(prev_dir, ignore_errors=True)
        os.makedirs(prev_dir)
    previews = []

    # ---- original mobs + red/green variants
    sounds = load(os.path.join(SRC, "RP/sounds.json"))
    ent_sounds = sounds["entity_sounds"]["entities"]
    for kind in BASE_MOBS:
        src_bp = load(os.path.join(SRC, f"BP/entities/soul_corrupted_{kind}.json"))
        src_rp = load(os.path.join(SRC, f"RP/entity/soul_corrupted_{kind}.entity.json"))
        src_tex = Image.open(os.path.join(SRC, f"RP/{TEX}/soul_corrupted_{kind}.png"))
        geo = load(os.path.join(SRC, f"RP/models/entity/soul_corrupted_{kind}.geo.json"))
        write(os.path.join(BP, f"loot_tables/{NS}/{kind}.json"), loot(BASE_MOBS[kind]["loot"]))
        for color in COLORS:
            mob = ident(kind, color)
            write(os.path.join(BP, f"entities/{mob}.json"), patch_mob(src_bp, kind, color))
            write(os.path.join(BP, f"spawn_rules/{mob}.json"), spawn_rules(mob, BASE_MOBS[kind]["weight"], color))
            client = copy.deepcopy(src_rp)
            desc = client["minecraft:client_entity"]["description"]
            desc["identifier"] = f"{NS}:{mob}"
            desc["textures"]["default"] = f"{TEX}/{mob}"
            egg = desc["spawn_egg"]
            for key in ("base_color", "overlay_color"):
                egg[key] = hexcol(recolor_rgb(hx(egg[key]), color))
            add_soul_extras(desc, kind, color)
            if client["format_version"] == "1.8.0":  # "animate" needs 1.10.0 (hotfix: invisible skeletons)
                client["format_version"] = "1.10.0"
            write(os.path.join(RP, f"entity/{mob}.entity.json"), client)
            tex = soften(recolor(src_tex, color))
            save_png(tex, RP, TEX, f"{mob}.png")
            if kind == "creeper":
                ent_sounds[f"{NS}:{mob}"] = copy.deepcopy(ent_sounds[f"{NS}:soul_corrupted_creeper"])
            else:
                ent_sounds[f"{NS}:{mob}"] = SOUNDS[kind]
            if prev:
                preview_geo(geo, tex, os.path.join(prev_dir, f"{mob}.png"))
                previews.append(mob)

    # ---- soul corrupted wither skeletons
    src_skel_bp = load(os.path.join(SRC, "BP/entities/soul_corrupted_skeleton.json"))
    src_skel_rp = load(os.path.join(SRC, "RP/entity/soul_corrupted_skeleton.entity.json"))
    src_skel_tex = Image.open(os.path.join(SRC, f"RP/{TEX}/soul_corrupted_skeleton.png"))
    skel_geo = load(os.path.join(SRC, "RP/models/entity/soul_corrupted_skeleton.geo.json"))
    write(os.path.join(BP, f"loot_tables/{NS}/equipment/wither_sword.json"),
          {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": "minecraft:stone_sword", "weight": 1}]}]})
    for color in COLORS:
        mob = ident("wither_skeleton", color)
        write(os.path.join(BP, f"entities/{mob}.json"), wither_behavior(src_skel_bp, color))
        write(os.path.join(BP, f"spawn_rules/{mob}.json"), spawn_rules(mob, WITHER["weight"], color))
        client = copy.deepcopy(src_skel_rp)
        client["format_version"] = "1.10.0"
        desc = client["minecraft:client_entity"]["description"]
        desc["identifier"] = f"{NS}:{mob}"
        desc["textures"]["default"] = f"{TEX}/{mob}"
        desc["spawn_egg"] = {"base_color": hexcol(recolor_rgb(hx("#2E5F66"), color)),
                             "overlay_color": hexcol(recolor_rgb(hx("#CEF8F9"), color))}
        add_soul_extras(desc, "skeleton", color)
        desc["animations"].update({"wither_run": f"{A}.wither_run", "wither_slash": f"{A}.wither_slash"})
        desc["scripts"]["animate"] += ["wither_run", "wither_slash"]
        desc["scripts"]["scale"] = str(WITHER["scale"])
        write(os.path.join(RP, f"entity/{mob}.entity.json"), client)
        # darker, wither-like version of the soul skeleton (whites, so the eyes, stay white)
        tex = recolor(src_skel_tex, color)
        dark = tex.load()
        for y in range(tex.height):
            for x in range(tex.width):
                r, g, b, a = dark[x, y]
                if a and not (r > 240 and g > 240 and b > 240):
                    dark[x, y] = (int(r * 0.5), int(g * 0.5), int(b * 0.5), a)
        tex = soften(tex)
        save_png(tex, RP, TEX, f"{mob}.png")
        ent_sounds[f"{NS}:{mob}"] = dict(SOUNDS["skeleton"], pitch=[0.55, 0.65])
        if prev:
            preview_geo(skel_geo, tex, os.path.join(prev_dir, f"{mob}.png"))
            previews.append(mob)

    # ---- phantoms
    pm = phantom_model()
    ptex = pm.build(seed=2024)
    write(os.path.join(RP, "models/entity/soul_corrupted_phantom.geo.json"), with_outline(pm.geometry_json()))
    write(os.path.join(BP, f"loot_tables/{NS}/phantom.json"), loot(PHANTOM["loot"]))
    for color in COLORS:
        mob = ident("phantom", color)
        tex = soften(recolor(ptex, color))
        save_png(tex, RP, TEX, f"{mob}.png")
        write(os.path.join(BP, f"entities/{mob}.json"), phantom_behavior(color))
        write(os.path.join(BP, f"spawn_rules/{mob}.json"), spawn_rules(mob, PHANTOM["weight"], color, flying=True))
        egg = {"base_color": hexcol(recolor_rgb(hx("#9DF2FF"), color)),
               "overlay_color": hexcol(recolor_rgb(hx("#1EA6BB"), color))}
        write(os.path.join(RP, f"entity/{mob}.entity.json"), phantom_client(mob, mob, color, egg))
        ent_sounds[f"{NS}:{mob}"] = SOUNDS["phantom"]
        if prev:
            preview_geo(pm.geometry_json()["minecraft:geometry"][0], tex,
                        os.path.join(prev_dir, f"{mob}.png"), view="top", scale=6)
            previews.append(mob)

    # ---- rideable phantom (blue, saddle painted on its back, same geometry)
    mm = phantom_model(saddle=True)
    mtex = mm.build(seed=2024)
    save_png(mtex, RP, TEX, f"{MOUNT}.png")
    write(os.path.join(BP, f"entities/{MOUNT}.json"), mount_behavior())
    write(os.path.join(BP, f"loot_tables/{NS}/{MOUNT}.json"), loot([("phantom_membrane", 1, 2)], sword=False))
    write(os.path.join(RP, f"entity/{MOUNT}.entity.json"),
          phantom_client(MOUNT, MOUNT, "blue", {"base_color": "#CEF8F9", "overlay_color": "#5A3826"}))
    ent_sounds[f"{NS}:{MOUNT}"] = {k: v for k, v in SOUNDS["phantom"].items()}
    if prev:
        preview_geo(mm.geometry_json()["minecraft:geometry"][0], mtex,
                    os.path.join(prev_dir, f"{MOUNT}.png"), view="top", scale=6)
        previews.append(MOUNT)

    # ---- healing altar
    am = altar_model()
    atex = am.build(seed=4242)
    save_png(atex, RP, TEX, f"{ALTAR}.png")
    write(os.path.join(RP, f"models/entity/{ALTAR}.geo.json"), with_outline(am.geometry_json()))
    write(os.path.join(RP, f"entity/{ALTAR}.entity.json"), altar_client())
    write(os.path.join(BP, f"entities/{ALTAR}.json"), altar_behavior())
    write(os.path.join(BP, f"loot_tables/{NS}/{ALTAR}.json"),
          {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": f"{NS}:{ALTAR}_spawn_egg", "weight": 1}]}]})
    write(os.path.join(BP, f"recipes/{ALTAR}.json"), altar_recipe())
    if prev:
        preview_geo(am.geometry_json()["minecraft:geometry"][0], atex, os.path.join(prev_dir, f"{ALTAR}.png"))
        previews.append(ALTAR)

    # ---- mini bosses
    import soul_bosses as bosses
    zgeo = load(os.path.join(SRC, "RP/models/entity/soul_corrupted_zombie.geo.json"))
    zgeo = zgeo["geometry.eu.sc.soul_corrupted_zombie"]
    bz_geo, bz_tex = bosses.blade_zombie_geometry(zgeo, Image.open(os.path.join(SRC, f"RP/{TEX}/soul_corrupted_zombie.png")))
    bz_tex = soften(recolor(bz_tex, "red"))
    sk_geo, sk_tex = bosses.mutant_skeleton_assets()
    boss_assets = {bosses.SKELETON_BOSS: (sk_geo, soften(sk_tex)),
                   bosses.ZOMBIE_BOSS: (bz_geo, bz_tex)}
    for name, (geo_json, tex) in boss_assets.items():
        save_png(tex, RP, TEX, f"{name}.png")
        write(os.path.join(RP, f"models/entity/{name}.geo.json"), with_outline(geo_json))
        write(os.path.join(RP, f"entity/{name}.entity.json"), bosses.client_entity(name))
        write(os.path.join(BP, f"entities/{name}.json"), bosses.behavior(name))
        ent_sounds[f"{NS}:{name}"] = bosses.SOUNDS[name]
        if prev:
            preview_geo(geo_json["minecraft:geometry"][0], tex, os.path.join(prev_dir, f"{name}.png"),
                        scale=6 if name == bosses.SKELETON_BOSS else 8)
            previews.append(name)
    item_icons = {}
    for name, data in bosses.items().items():
        write(os.path.join(BP, f"items/{name}.json"), data)
    for name, img in bosses.item_textures().items():
        save_png(img, RP, f"textures/items/{name}.png")
        item_icons[name] = {"textures": f"textures/items/{name}"}
    for name, data in bosses.recipes().items():
        write(os.path.join(BP, f"recipes/{name}.json"), data)
    ANIMS.update(bosses.ANIMS)
    ANIMS.update(bosses.mutant_animations())

    # ---- sword
    write(os.path.join(BP, "items/soul_corrupted_sword.json"), sword_item())
    sword = pixel_art(SWORD_ROWS, SWORD_COLORS)
    save_png(sword, RP, "textures/items/soul_corrupted_sword.png")
    save_png(pixel_art(ALTAR_EGG_ROWS, ALTAR_EGG_COLORS), RP, "textures/items/healing_altar_egg.png")
    items = load(os.path.join(SRC, "RP/textures/item_texture.json"))
    items["texture_data"].update({
        "soul_corrupted_sword": {"textures": "textures/items/soul_corrupted_sword"},
        "healing_altar_egg": {"textures": "textures/items/healing_altar_egg"}})
    items["texture_data"].update(item_icons)
    write(os.path.join(RP, "textures/item_texture.json"), items)

    # ---- shared resources
    ascending = load(os.path.join(SRC, "RP/particles/soul_ascending_particle.particle.json"))
    for name, effect in particles(ascending).items():
        write(os.path.join(RP, f"particles/{name}.particle.json"), effect)
    save_png(pixel_art(SPARK_ROWS, {"#": "#ffffff"}), RP, "textures/particles/soul_corrupted/soul_spark.png")
    write(os.path.join(RP, f"animations/{NS}.animation.json"), {"format_version": "1.8.0", "animations": {
        f"{A}.{n}": a for n, a in ANIMS.items()}})
    ctrls = controllers()
    ctrls["animation_controllers"].update(bosses.controllers())
    write(os.path.join(RP, f"animation_controllers/{NS}.animation_controllers.json"), ctrls)
    write(os.path.join(RP, "sounds.json"), sounds)
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["en_US", "es_ES", "es_MX"])
        write(os.path.join(pack, "texts/en_US.lang"), lang(False) + "\n".join(bosses.lang(False)) + "\n")
        write(os.path.join(pack, "texts/es_ES.lang"), lang(True) + "\n".join(bosses.lang(True)) + "\n")
        write(os.path.join(pack, "texts/es_MX.lang"), lang(True) + "\n".join(bosses.lang(True)) + "\n")

    # ---- scripts + manifests
    for f in ("main.js", "entities/index.js", "entities/soulCorruptedSkeleton.js"):
        try:
            os.remove(os.path.join(BP, "scripts", f))
        except FileNotFoundError:
            pass
    shutil.rmtree(os.path.join(BP, "scripts", "entities"), ignore_errors=True)
    write(os.path.join(BP, "scripts/main.js"), script(bosses))
    for pack, other in ((BP, "RP"), (RP, "BP")):
        man = load(os.path.join(pack, "manifest.json"))
        man["header"]["version"] = VERSION
        man["header"]["name"] = ADDON_NAME
        for mod in man["modules"]:
            mod["version"] = VERSION
        for dep in man["dependencies"]:
            if "uuid" in dep:
                dep["version"] = VERSION
            if dep.get("module_name") == "@minecraft/server":
                dep["version"] = SCRIPT_API
        write(os.path.join(pack, "manifest.json"), man)

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "TheRevampOfTheSoul.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    if prev:
        sheet(prev_dir, previews, os.path.join(ROOT, "docs", "soul_mobs_preview.png"))
        names = ["soul_corrupted_sword", "soul_essence", "soul_core", "soul_corrupted_plant",
                 "soul_corrupted_star", "healing_altar_egg"]
        strip = Image.new("RGBA", (len(names) * 136, 136), (50, 55, 70, 255))
        for i, n in enumerate(names):
            icon = Image.open(os.path.join(RP, f"textures/items/{n}.png")).resize((128, 128), Image.NEAREST)
            strip.alpha_composite(icon, (i * 136 + 4, 4))
        strip.save(os.path.join(ROOT, "docs", "soul_mobs_items.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


def sheet(prev_dir, names, path, cols=4):
    ims = [Image.open(os.path.join(prev_dir, f"{n}.png")) for n in names]
    cw, ch = max(i.width for i in ims), max(i.height for i in ims)
    out = Image.new("RGBA", (cw * cols, ch * ((len(ims) + cols - 1) // cols)), (28, 32, 42, 255))
    for k, im in enumerate(ims):
        out.paste(im, ((k % cols) * cw + (cw - im.width) // 2, (k // cols) * ch + ch - im.height))
    out.thumbnail((1600, 2400))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)


if __name__ == "__main__":
    main()
