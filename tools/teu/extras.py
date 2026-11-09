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
import arenas  # noqa: E402

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


def vanillize_text(text, items, keep):
    """Names of the add-on's items in commands and components -> vanilla items."""
    return ID.sub(lambda m: vanilla_item(m.group(1)) if m.group(1) in items and m.group(1) not in keep else m.group(1),
                  text)


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


# --- arenas and compasses ------------------------------------------------------------------------
REGION, QUARTER, SPAN, MARGIN, OFFSET, END_SKIP = 128, 64, 48, 8, 4000037, 400
# theme name -> boss, dimension, y of the arena floor, quarter, constants, label, compass item, colour
ARENAS = {
    "floral": ("boss:floral_amalgam", "overworld", -24, (0, 0), (11, 29), "Floral Amalgam", "moss_block", "#6fb04a"),
    "wyrm": ("boss:primordial_wyrm", "overworld", -40, (1, 0), (41, 7), "Primordial Wyrm", "prismarine_shard", "#3fb6c4"),
    "sculk": ("boss:sculk_boss", "overworld", -52, (0, 1), (23, 53), "Sculk Monstrosity", "echo_shard", "#1d6f78"),
    "pyrogen": ("boss:pyrogen", "nether", 34, (0, 0), (17, 61), "Pyrogen", "blaze_powder", "#f08a24"),
    "ghast": ("boss:irradiated_ghast", "nether", 45, (1, 1), (59, 13), "Mutated Nuclear Ghast", "ghast_tear", "#7be04a"),
    "astral": ("boss:astrageldon", "the_end", 60, (0, 0), (31, 43), "Eclipsion Geliath", "amethyst_shard", "#b06cf0"),
    "obelisk": ("boss:sightful_obelisk_of_ender", "the_end", 60, (1, 1), (5, 37), "Sightful Obelisk of Ender",
                "ender_eye", "#3ad6a0"),
}
NOWHERE = {"overworld": -100, "nether": -1, "the_end": -1}     # below the world: nothing is placed
DIM_TAG = {"overworld": "overworld", "nether": "nether", "the_end": "the_end"}
SUMMON_Y = {"wyrm": 4, "ghast": 6, "obelisk": 2}
TITLES = {"floral": "El jardín despierta", "wyrm": "Algo se mueve en el agua", "sculk": "El sculk late",
          "pyrogen": "La forja arde", "ghast": "Un llanto radiactivo", "astral": "Las estrellas se apagan",
          "obelisk": "El vacío te observa"}


def placement(k1, k2, qx, qz, dim, y):
    """Feature rule y: the arena's floor in the one chunk of the region the formula picks,
    below the world (nothing placed) in every other chunk."""
    end = " && (math.abs(v.worldx) > %d || math.abs(v.worldz) > %d)" % (END_SKIP, END_SKIP) if dim == "the_end" else ""
    return ("t.cx = math.floor(v.worldx / 16); t.cz = math.floor(v.worldz / 16); "
            "t.rx = math.floor(t.cx / %d); t.rz = math.floor(t.cz / %d); "
            "t.ox = math.mod(t.rx * 37 + t.rz * 91 + %d, %d) + %d; t.oz = math.mod(t.rx * 71 + t.rz * 29 + %d, %d) + %d; "
            "return (t.cx == t.rx * %d + t.ox && t.cz == t.rz * %d + t.oz%s) ? %d : %d;"
            % (REGION, REGION, k1 + OFFSET, SPAN, MARGIN + qx * QUARTER, k2 + OFFSET, SPAN, MARGIN + qz * QUARTER,
               REGION, REGION, end, y, NOWHERE[dim]))


def compass_icon(path, color):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([1, 1, 14, 14], fill=(70, 70, 78, 255), outline=(30, 30, 34, 255))
    d.ellipse([3, 3, 12, 12], fill=(200, 196, 182, 255))
    c = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    d.polygon([(8, 3), (10, 8), (8, 9), (6, 8)], fill=c)
    d.polygon([(8, 12), (6, 8), (8, 9), (10, 8)], fill=(90, 90, 96, 255))
    d.point((8, 8), fill=(255, 255, 255, 255))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def write_arenas(bp, rp, compass_js, keep_entities):
    """Arena structures and their loaders, features, rules, functions, compass items,
    recipes and icons, and the compass script. Returns the compass items and the arenas.

    World generation places a 1-block loader (a command block): when a player comes near
    it loads the whole arena round it (any size works, and /place feature does the same)."""
    cmds = {n: f"execute if entity @p[r=12,m=!spectator] run function teu_mobs/arena/{n}" for n in ARENAS}
    built = arenas.build(os.path.join(bp, "structures"), cmds)
    compass_data, items = {}, []
    item_tex = os.path.join(rp, "textures", "item_texture.json")
    atlas = load(item_tex) if os.path.isfile(item_tex) else {"resource_pack_name": "teu_mobs",
                                                           "texture_name": "atlas.items", "texture_data": {}}
    for name, (boss, dim, y, (qx, qz), (k1, k2), label, mat, color) in ARENAS.items():
        assert boss in keep_entities, boss
        path, size, (cx, fy, cz) = built[name]
        struct = os.path.splitext(os.path.basename(path))[0]
        # the loader: where the middle of the floor goes (the arena overwrites it once loaded)
        loader = arenas.Arena((1, 1, 1))
        arenas.command_block(loader, 0, 0, 0, f"execute if entity @p[r=48] run function teu_mobs/arena_load/{name}")
        loader.save(os.path.join(bp, "structures", struct + "_loader.mcstructure"))
        fn = os.path.join(bp, "functions", "teu_mobs", "arena_load", name + ".mcfunction")
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"structure load mystructure:{struct} ~-{cx} ~-{fy - 1} ~-{cz}\n")
        ident = f"teu_mobs:arena_{name}"
        dump(os.path.join(bp, "features", "teu_mobs", f"arena_{name}.json"), {
            "format_version": "1.13.0", "minecraft:structure_template_feature": {
                "description": {"identifier": ident}, "structure_name": f"mystructure:{struct}_loader",
                "facing_direction": "north"}})
        dump(os.path.join(bp, "feature_rules", "teu_mobs", f"arena_{name}.json"), {
            "format_version": "1.13.0", "minecraft:feature_rules": {
                "description": {"identifier": f"teu_mobs:arena_{name}_rule", "places_feature": ident},
                "conditions": {"placement_pass": "final_pass",
                               "minecraft:biome_filter": [{"test": "has_biome_tag", "operator": "==", "value": DIM_TAG[dim]}]},
                "distribution": {"iterations": 1, "coordinate_eval_order": "xzy", "x": 0, "z": 0,
                                 "y": placement(k1, k2, qx, qz, dim, y)}}})
        under = {"floral": "minecraft:moss_block", "wyrm": "minecraft:dark_prismarine", "sculk": "minecraft:deepslate_tiles",
                 "pyrogen": "minecraft:polished_blackstone", "ghast": "minecraft:smooth_basalt",
                 "astral": "minecraft:calcite", "obelisk": "minecraft:obsidian"}[name]
        fn = os.path.join(bp, "functions", "teu_mobs", "arena", name + ".mcfunction")
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join([
                f"summon {boss} ~ ~{SUMMON_Y.get(name, 3)} ~",
                f"title @a[r=48] title §c{label}",
                f"title @a[r=48] subtitle §7{TITLES[name]}",
                "playsound mob.wither.spawn @a[r=48] ~ ~ ~ 1 0.8",
                "camerashake add @a[r=32] 0.5 1.5",
                f"setblock ~ ~ ~ {under}", ""]))
        item = f"teu_mobs:compass_{name}"
        items.append(item)
        icon = f"teu_compass_{name}"
        compass_icon(os.path.join(rp, "textures", "items", "teu_mobs", icon + ".png"), color)
        atlas["texture_data"][icon] = {"textures": f"textures/items/teu_mobs/{icon}"}
        dump(os.path.join(bp, "items", "teu_mobs", f"compass_{name}.json"), {
            "format_version": "1.21.40", "minecraft:item": {
                "description": {"identifier": item, "menu_category": {"category": "equipment"}},
                "components": {"minecraft:icon": icon, "minecraft:max_stack_size": 1, "minecraft:glint": True,
                               "minecraft:display_name": {"value": f"Brújula: {label}\n§7Llévala en la mano: te guía\n"
                                                                   f"§7a la arena de este jefe"}}}})
        dump(os.path.join(bp, "recipes", "teu_mobs", f"compass_{name}.json"), {
            "format_version": "1.20.10", "minecraft:recipe_shaped": {
                "description": {"identifier": f"teu_mobs:compass_{name}"}, "tags": ["crafting_table"],
                "pattern": [" A ", "ABA", " A "],
                "key": {"A": {"item": "minecraft:" + mat}, "B": {"item": "minecraft:compass"}},
                "result": {"item": item, "count": 1}}})
        compass_data[item] = {"label": label, "dim": "minecraft:" + dim, "k1": k1, "k2": k2, "qx": qx * QUARTER,
                              "qz": qz * QUARTER, "cx": 0, "cz": 0, "y": y}
    dump(item_tex, atlas)
    js = read(compass_js)
    for k, v in (("__REGION__", REGION), ("__QUARTER__", QUARTER), ("__SPAN__", SPAN), ("__MARGIN__", MARGIN),
                 ("__OFFSET__", OFFSET), ("__END_SKIP__", END_SKIP),
                 ("__ARENAS__", json.dumps(compass_data, ensure_ascii=False))):
        js = js.replace(k, str(v))
    with open(os.path.join(bp, "scripts", "teu_compass.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    return items, {n: b[0] for n, b in built.items()}


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
