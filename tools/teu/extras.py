"""TEU Mobs 1.1: vanilla loot, lighter particles, mob fixes, boss arenas and compasses
(used by tools/teu_mobs.py)."""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import dungeons_mobs as dm  # noqa: E402
from dungeons_mobs import load, dump, read  # noqa: E402

# --- vanilla loot -----------------------------------------------------------------------------
# the add-on's items -> a vanilla item, by what their name says (first match wins)
ITEM_RULES = [
    (r"helmet|crown|mask|hood", "iron_helmet"), (r"chestplate|tunic", "iron_chestplate"),
    (r"leggings", "iron_leggings"), (r"boots", "iron_boots"), (r"crossbow", "crossbow"), (r"bow\b|_bow", "bow"),
    (r"arrow|bolt", "arrow"), (r"pickaxe", "iron_pickaxe"), (r"shovel", "iron_shovel"), (r"hoe\b|_hoe", "iron_hoe"),
    (r"axe\b|_axe", "iron_axe"), (r"sword|blade|knife|kunai|dagger|caltrop|pike|spear|scythe|cleaver|hammer|mace|staff",
                                    "iron_sword"),
    (r"tear", "ghast_tear"), (r"pearl", "ender_pearl"), (r"eye", "ender_eye"), (r"slime|goo|gel", "slime_ball"),
    (r"ink", "ink_sac"), (r"bone", "bone"), (r"feather|wing", "feather"), (r"scale|hide|leather|skin|shell", "leather"),
    (r"tentacle|calamari|squid", "ink_sac"), (r"fish|fin|shark", "cod"), (r"egg", "egg"),
    (r"cooked|steak|roast", "cooked_beef"), (r"meat|raw|beef|venison|turkey|drumstick", "beef"),
    (r"crystal|shard|gem|jade|prism|quartz|amethyst", "amethyst_shard"), (r"gold", "gold_ingot"),
    (r"ingot|scrap|metal|molybdenum|steel|tungsten|palladium|plate|gear|cog", "iron_ingot"),
    (r"flame|fire|ember|magma|blaze|infern|pyro|cinder", "blaze_powder"), (r"ice|frost|snow|cryo|winter", "snowball"),
    (r"void|ender|endra|chorus|astral|star|cosmic|lunar|solar", "chorus_fruit"),
    (r"soul|spirit|ghost|specter", "soul_sand"), (r"sculk|echo", "echo_shard"), (r"rad|irradiat|nuclear|toxic", "slime_ball"),
    (r"dust|powder", "glowstone_dust"), (r"string|web|silk", "string"), (r"potion|bottle|elixir", "glass_bottle"),
]
BOSS_EXTRA = {"floral_amalgam": ("spore_blossom", 2, 4), "primordial_wyrm": ("heart_of_the_sea", 1, 1),
              "sculk_boss": ("echo_shard", 3, 6), "pyrogen": ("netherite_ingot", 1, 1), "irradiated_ghast": ("ghast_tear", 4, 8),
              "astrageldon": ("nether_star", 1, 1), "sightful_obelisk_of_ender": ("elytra", 1, 1),
              "void_pope": ("dragon_breath", 4, 8)}


def vanilla_item(ident):
    name = ident.split(":", 1)[1]
    for pat, item in ITEM_RULES:
        if re.search(pat, name):
            return "minecraft:" + item
    return "minecraft:bread" if ident.startswith("food:") else "minecraft:experience_bottle"


def boss_loot(boss):
    extra, lo, hi = BOSS_EXTRA.get(boss, ("experience_bottle", 4, 8))

    def pool(item, a, b, chance=None, functions=()):
        p = {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:" + item, "weight": 1,
                                      "functions": [{"function": "set_count", "count": {"min": a, "max": b}}, *functions]}]}
        if chance:
            p["conditions"] = [{"condition": "random_chance", "chance": chance}]
        return p
    return {"pools": [pool("diamond", 3, 6), pool("emerald", 4, 10), pool("netherite_scrap", 1, 2),
                      pool("experience_bottle", 8, 16), pool(extra, lo, hi),
                      pool("book", 1, 1, functions=[{"function": "enchant_randomly", "treasure": True}]),
                      pool("enchanted_golden_apple", 1, 1, chance=0.35), pool("totem_of_undying", 1, 1, chance=0.5)]}


def vanillize_loot(data, keep):
    """Entries of the add-on's items become a vanilla item (keeping their counts)."""
    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "item":
                n = o.get("name", "")
                if ":" in n and not n.startswith("minecraft:") and n not in keep:
                    o["name"] = vanilla_item(n)
                    o["functions"] = [f for f in o.get("functions", [])
                                      if f.get("function") in ("set_count", "set_data", "looting_enchant", "enchant_randomly",
                                                               "enchant_with_levels", "set_damage")]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return data


ID = re.compile(r"\b([a-z_]+:[a-z0-9_]+)\b")


def vanillize_text(text, items, keep, entities=()):
    """Names of the add-on's items in commands and components -> vanilla items (not the
    ids that are also entities: a thrown weapon's entity shares its item's id)."""
    return ID.sub(lambda m: vanilla_item(m.group(1)) if m.group(1) in items and m.group(1) not in keep
                  and m.group(1) not in entities else m.group(1), text)


TRIAL = {"key": "loot_tables/spawners/trial_chamber/key.json",
         "consumables": "loot_tables/spawners/trial_chamber/consumables.json",
         "ominous": "loot_tables/spawners/ominous/trial_chamber/consumables.json",
         "drops": "loot_tables/spawners/trial_chamber/items_to_drop_when_ominous.json"}


def structure_loot(name, dim):
    """The vanilla chest loot of a structure, by where it is."""
    if name.startswith(("cryo",)):
        return "loot_tables/chests/igloo_chest.json"
    if name.startswith(("sky", "star")):
        return "loot_tables/chests/simple_dungeon.json"
    if dim == "nether":
        return "loot_tables/chests/bastion_other.json"
    return "loot_tables/chests/end_city_treasure.json"


def loot_path_for(path, chest):
    if "ominous" in path:
        return TRIAL["drops"] if "weapon" in path else TRIAL["ominous"]
    if "weapon" in path:
        return TRIAL["drops"]
    if "trial" in path:
        return TRIAL["consumables"]
    if "key" in path:
        return TRIAL["key"]
    return chest


# --- particles --------------------------------------------------------------------------------
PART_FACTOR = 0.35


def _less(v):
    if isinstance(v, (int, float)):
        return v if v <= 3 else max(2, int(round(v * PART_FACTOR)))
    if isinstance(v, str):
        return f"math.max(1, ({v}) * {PART_FACTOR})"
    return v


def lighten_particle(data):
    """Fewer particles per burst and per second, no block collisions, shorter lives."""
    comps = data.get("particle_effect", {}).get("components", {})
    inst = comps.get("minecraft:emitter_rate_instant")
    if isinstance(inst, dict) and "num_particles" in inst:
        inst["num_particles"] = _less(inst["num_particles"])
    st = comps.get("minecraft:emitter_rate_steady")
    if isinstance(st, dict):
        for k in ("spawn_rate", "max_particles"):
            if k in st:
                st[k] = _less(st[k])
    comps.pop("minecraft:particle_motion_collision", None)
    life = comps.get("minecraft:particle_lifetime_expression")
    if isinstance(life, dict) and isinstance(life.get("max_lifetime"), (int, float)) and life["max_lifetime"] > 2.5:
        life["max_lifetime"] = 2.5
    return data


def slow_particle_timers(ent):
    """Looping timers of a tick or two that only spawn particles: every 0.25 s."""
    e = ent["minecraft:entity"]
    events = e.get("events", {})
    n = 0
    for holder in [e.get("components", {})] + list(e.get("component_groups", {}).values()):
        t = holder.get("minecraft:timer")
        if not isinstance(t, dict) or not t.get("looping"):
            continue
        tm = t.get("time")
        hi = max(tm) if isinstance(tm, list) else tm
        if not isinstance(hi, (int, float)) or hi > 0.1:
            continue
        ev = events.get((t.get("time_down_event") or {}).get("event"), {})
        cmds = []

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("add", "remove", "trigger", "randomize", "set_property", "emit_vibration"):
                        cmds.append("other")
                    if k == "queue_command":
                        c = v.get("command")
                        cmds.extend([c] if isinstance(c, str) else c)
                    elif k == "sequence":
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(ev)
        if cmds and all(isinstance(c, str) and c.lstrip("/").startswith("particle") for c in cmds):
            t["time"] = [0.25, 0.25]
            n += 1
    return n


# --- client fixes -------------------------------------------------------------------------------
def fix_case(rp):
    """Client entities naming a geometry/animation with other capitals than its definition
    (the Prismider's "geometry.prismider" is "geometry.Prismider"): the game does not
    find it and the mob is invisible."""
    rpi = dm.RPIndex(rp)
    low = {}
    for k in rpi.defs:
        low.setdefault(k.lower(), k)
    fixed = []
    for files in rpi.client.values():
        for rel in files:
            path = os.path.join(rp, rel)
            d = load(path)
            desc = d["minecraft:client_entity"]["description"]
            changed = False
            for key in ("geometry", "animations"):
                for k, v in (desc.get(key) or {}).items():
                    if isinstance(v, str) and v not in rpi.defs and v.lower() in low:
                        desc[key][k] = low[v.lower()]
                        changed = True
            if changed:
                dump(path, d)
                fixed.append(desc["identifier"])
    return fixed


# --- 1.2 fixes -----------------------------------------------------------------------------------
LOW_RING = re.compile(r"^(\s*)summon (mechanic:(?:pyrogen_fireballs|homing_obelisk)) ~([^~\s]*)~([^~\s]*)~([^\s]*)\s*$", re.M)


def projectiles_at_player(fn_name, text):
    """The Pyrogen and the Obelisk fire from a ring round themselves, high in the air: the
    ring now forms round the nearest player, at their height, and aims at them."""
    def near(v):     # 35 blocks away would be inside the walls of a closed arena: 12
        return v.replace("35", "12")
    text = LOW_RING.sub(lambda m: f"{m.group(1)}execute at @p[r=60] run summon {m.group(2)} "
                                  f"~{near(m.group(3))} ~1.2 ~{near(m.group(5))}", text)
    return text.replace("facing @e[c=1,type=boss:pyrogen]", "facing @p[r=60]")


INVALID_SOUND_EVENTS = {"scream", "guardian.flop"}


def fix_sounds(sounds):
    for v in sounds.get("entity_sounds", {}).get("entities", {}).values():
        ev = v.get("events", {})
        for k in [k for k in ev if k in INVALID_SOUND_EVENTS]:
            del ev[k]
    return sounds


def fix_controller(data):
    """Transitions with an empty condition ("No tokens found in expression") -> never."""
    n = 0
    for ac in data.get("animation_controllers", {}).values():
        for st in ac.get("states", {}).values():
            for t in st.get("transitions", []) or []:
                for k, v in list(t.items()):
                    if isinstance(v, str) and not v.strip():
                        t[k] = "0"
                        n += 1
    return n


def fix_baby_locators(data):
    """Baby models repeating the adult's neck locator with other values (content log error)."""
    n = 0
    geos = [g for g in data.get("minecraft:geometry", []) or []
            if g.get("description", {}).get("identifier", "").startswith("geometry.baby_")]
    geos += [v for k, v in data.items() if k.startswith("geometry.baby_") and isinstance(v, dict)]
    for g in geos:
        if True:
            for b in g.get("bones", []):
                loc = b.get("locators")
                if isinstance(loc, dict) and "armor_offset.default_neck" in loc:
                    del loc["armor_offset.default_neck"]
                    n += 1
    return n


def fix_guardian_client(data):
    """controller.render.guardian also asks for texture.elder and material.ghost."""
    d = data["minecraft:client_entity"]["description"]
    if any((r if isinstance(r, str) else next(iter(r))) == "controller.render.guardian" for r in d.get("render_controllers", [])):
        d.setdefault("textures", {}).setdefault("elder", d["textures"].get("default"))
        d.setdefault("materials", {}).setdefault("ghost", d["materials"].get("default", "guardian"))
    return data


def clearer_particle_texture(path):
    """Brighter colours and firmer edges: soft, dark particle textures read badly."""
    from PIL import Image, ImageEnhance
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return False
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = ImageEnhance.Brightness(rgb).enhance(1.35)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.15)
    rgb = ImageEnhance.Color(rgb).enhance(1.2)
    a = a.point(lambda v: 0 if v < 24 else min(255, int(v * 1.6)))
    out = Image.merge("RGBA", (*rgb.split(), a))
    out.save(path)
    return True


def particle_textures(rp):
    """Texture files the particles use."""
    out = set()
    for dirpath, _, fs in os.walk(os.path.join(rp, "particles")):
        for name in fs:
            if not name.endswith(".json"):
                continue
            d = load(os.path.join(dirpath, name))
            t = d.get("particle_effect", {}).get("description", {}).get("basic_render_parameters", {}).get("texture")
            if isinstance(t, str):
                for ext in (".png", ".tga"):
                    if os.path.isfile(os.path.join(rp, t + ext)):
                        out.add(os.path.join(rp, t + ext))
    return out


# --- 1.3 -----------------------------------------------------------------------------------------
WHISTLE_JS = """import { world } from "@minecraft/server";

// The Inferno Death Whistle wakes the sleeping Nuclear Ghast of the irradiated home (held
// for a moment); it says so when no ghast sleeps nearby.
world.afterEvents.itemUse.subscribe((e) => {
    const p = e.source;
    if (e.itemStack?.typeId !== "item:inferno_death_whistle") return;
    let near = [];
    try {
        near = p.dimension.getEntities({ type: "boss:irradiated_ghast_sleeping", location: p.location, maxDistance: 30 });
    } catch {
        // ignore
    }
    try {
        p.runCommand("function infernodeathwhistle");
        if (!near.length) p.onScreenDisplay.setActionBar("§cNo hay ningún Ghast dormido a menos de 30 bloques");
    } catch {
        // ignore
    }
});
"""
DAMAGE = 0.85
TITLE = re.compile(r"^\s*/?(?:title|titleraw)\b|\brun\s+/?(?:title|titleraw)\b")
DAMAGE_CMD = re.compile(r"(\bdamage\s+(?:@[a-z](?:\[[^\]]*\])?|[A-Za-z_]+)\s+)(\d+(?:\.\d+)?)")


def _less_damage(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return round(v * DAMAGE, 2)
    if isinstance(v, list):
        return [_less_damage(x) for x in v]
    if isinstance(v, dict) and set(v) <= {"range_min", "range_max", "min", "max"}:
        return {k: _less_damage(x) for k, x in v.items()}
    return v


def command_text(cmd):
    """-15 % on damage commands; None for a title (removed)."""
    if TITLE.search(cmd):
        return None
    return DAMAGE_CMD.sub(lambda m: m.group(1) + f"{max(1, round(float(m.group(2)) * DAMAGE)):g}", cmd)


def function_text(text):
    out = []
    for line in text.splitlines():
        c = command_text(line)
        if c is not None:
            out.append(c)
    return "\n".join(out) + "\n"


def balance_entity(data):
    """-15 % damage (attacks, projectile hits, area attacks, damage commands); no titles."""
    def walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k in ("minecraft:attack", "minecraft:area_attack") and isinstance(v, dict) and "damage" in v:
                    v["damage"] = _less_damage(v["damage"])
                elif k == "impact_damage" and isinstance(v, dict) and "damage" in v:
                    v["damage"] = _less_damage(v["damage"])
                elif k == "queue_command" and isinstance(v, dict):
                    c = v.get("command")
                    cmds = [c] if isinstance(c, str) else list(c or [])
                    cmds = [x for x in (command_text(x) for x in cmds) if x is not None]
                    if cmds:
                        v["command"] = cmds
                    else:
                        del o[k]
                        continue
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return data


def fix_block(data):
    """Boxes out of the allowed range (the doors) and invalid fields."""
    c_all = [data["minecraft:block"].get("components", {})] + \
        [p.get("components", {}) for p in data["minecraft:block"].get("permutations", [])]
    for c in c_all:
        for k, top in (("minecraft:selection_box", 16), ("minecraft:collision_box", 24)):
            b = c.get(k)
            if not isinstance(b, dict) or "origin" not in b:
                continue
            o, sz = list(b["origin"]), list(b.get("size", [16, 16, 16]))
            lo, hi = [-8, 0, -8], [8, top, 8]
            for i in range(3):
                o[i] = max(lo[i], min(hi[i], o[i]))
                sz[i] = max(0, min(hi[i] - o[i], sz[i]))
            b["origin"], b["size"] = o, sz
    return data


def fix_entity_fields(data):
    """Fields of the add-on that the game rejects (the Shulk's)."""
    for h in [data["minecraft:entity"].get("components", {})] + list(data["minecraft:entity"].get("component_groups", {}).values()):
        ma = h.get("minecraft:behavior.melee_attack")
        if isinstance(ma, dict):
            ma.pop("target_dist", None)
        h.pop("minecraft:fall_damage", None)
        la = h.get("minecraft:looked_at")
        if isinstance(la, dict):
            if "searchRadius" in la:
                la["search_radius"] = la.pop("searchRadius")
            if "setTarget" in la:
                v = la.pop("setTarget")
                la["set_target"] = "once_and_stop_scanning" if v is True else v
    return data


def fix_particle(data):
    box = data.get("particle_effect", {}).get("components", {}).get("minecraft:emitter_shape_box")
    if isinstance(box, dict):
        box.setdefault("offset", [0, 0, 0])
        box.setdefault("half_dimensions", [0.5, 0.5, 0.5])
    return data


def drop_missing_animations(data, defined):
    """scripts.animate entries whose animation is defined nowhere ("can't find animation")."""
    d = data["minecraft:client_entity"]["description"]
    anims = d.get("animations", {})
    gone = {k for k, v in anims.items() if v not in defined and not v.startswith(("animation.", "controller."))}
    sc = d.get("scripts", {})
    if isinstance(sc.get("animate"), list):
        keep = []
        for e in sc["animate"]:
            name = e if isinstance(e, str) else next(iter(e))
            if name in anims and name not in gone:
                keep.append(e)
        sc["animate"] = keep
    for k in gone:
        del anims[k]
    return data
