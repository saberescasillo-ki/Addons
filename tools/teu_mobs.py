"""Extracts some mobs and the bosses of The Everything Update Remastered (v1.6.5 Hotfix 1)
into "TEU Mobs", made to blend into normal Minecraft. For personal use: the packs go to
the git-ignored private/ folder (the add-on is not ours to share).

    python3 tools/teu_mobs.py RES.mcpack BEH.mcpack      (or one .mcaddon, or a folder)

Kept:
  * the mobs of MOBS and every boss of BOSSES (not the vanilla ones the add-on changes,
    nor the queen bee), with what they need: projectiles, attack entities, minions,
    functions, BP animations, loot, models, textures, animations, particles, sounds;
  * the structures they live in (STRUCTURES), with the blocks they are built of (and the
    block scripts those blocks use), generated in vanilla biomes (the End ones rarely);
    their spawners spawn the chosen mobs of each structure;
  * each boss's summoning item or block, with a recipe of vanilla materials.
Versions 1.1 and 1.2 (tools/teu/extras.py, arenas.py, torpendo.js, compass.js):
  * every boss has its own flat arena (flower, circle, octagon, hexagon, star, pentagon; a
    one-block loader placed by world generation or /place feature loads it) generated very
    rarely, where a formula puts it; a craftable compass per boss shows the way there;
    the boss appears when a player walks into the hall;
  * vanilla loot instead of the add-on's items (chests, trial spawners, drops, gear);
  * lighter particles; no Wanderer, Evupul, Illager Airforcer, Shulk Jouster;
  * Eternal Iris: -25 % health, no teleport on each shot; Torpendo: -15 % health and
    damage, it lunges at its target every 2 seconds;
  * the mobs that were invisible (a model named with other capitals) are seen again.
Left out: the add-on's biomes and world generation, the other mobs, blocks and items,
the overrides of vanilla mobs and loot, the add-on's spawners and its other scripts.

Spawning: the add-on's spawn rules keep their vanilla biomes, the custom ones become the
vanilla biome each of them replaced (BIOME_TAGS); the mobs that only came from the
add-on's spawners get spawn rules in vanilla places (NEW_SPAWNS).
"""
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeons_mobs as dm  # noqa: E402  (shared helpers: JSON, references, RP closure)
import aqueous_mobs as aq  # noqa: E402
import teu_opt  # noqa: E402
import mcstructure as mcs  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "teu"))
import extras  # noqa: E402  (1.1: vanilla loot, particles, arenas, compasses)
from dungeons_mobs import load, dump, read, mentions  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "TEUMobs_BP")
RP = os.path.join(OUT, "TEUMobs_RP")
MCADDON = os.path.join(OUT, "TEUMobs.mcaddon")
NAME = "TEU Mobs"
VERSION = [1, 2, 0]
UUIDS = dict(bp="3b8e1f64-7a29-4c51-9d0e-2f6a8c4b7e13", bp_data="c1d74e98-5b36-4a2f-8e61-0a9f3d7c2b54",
             bp_script="8f2a6c31-9e47-4d18-b5a3-6c0e1f9d4a72", rp="5e9c2b17-4f83-4a6d-a1c8-7d3e0b6f2c95",
             rp_res="a4f61d38-2c95-4e7b-9b14-e8c3f0a5d261")

MOBS = """specter giant_squid torpendo hovering_inferno sky_seeker soulerized_ghast
winter_breeze endersent unholy_assalter ghast_balloon shulk end_mooshroom redstone_golem angry_strider flying_shulker
inviseer astral_orbiter aeroslime creether prismider drenched_squid lurer deer drowned_shark praiser
turkey exorcist solaronemone abyss_guardian blighted_eye crystalized eternal_iris orthoceras grand_guritavoid""".split()
REMOVED = {"mob:wanderer", "mob:evupul", "mob:illager_balloon", "mob:shulk_jouster"}
BOSSES = ["boss:floral_amalgam", "boss:primordial_wyrm", "boss:primordial_wyrm_clone", "boss:pyrogen", "boss:sculk_boss",
          "boss:astrageldon", "boss:irradiated_ghast",
          "boss:sightful_obelisk_of_ender", "boss:void_pope"]
# what summons the bosses (the item placers and projectiles are entities too)
SUMMONERS = ["item:genesis_seed", "projectile:stellar_communicator", "mob:supreme_ender_eye", "mob:sculk_intro",
             "mob:tempered_forge"]
NEVER = {"mechanic:entity_spawner", "mechanic:sf_entity_spawner", "mechanic:biome_ambience_tif",
         "mechanic:equipment_commands", "mechanic:meteor_spawner", "mechanic:meteor_shower", "mechanic:wind_noise",
         # only named by a "kill @e[type=...]" of the End trial's warp pad
         "mob:ender_creeper", "mob:final_skeleton",
         # placed by items that are kept as plain items (dropped from chests)
         "item:dragonchick_egg", "item:bottle_of_souls",
         # the bosses have arenas now: no boss sleeping in a structure; the Torpendo lunges itself
         "boss:irradiated_ghast_sleeping", "item:torpendo_dash"} | REMOVED
SUMMON_ITEMS = {"item:genesis_seed", "item:stellar_communicator", "item:supreme_ender_eye", "item:heart_of_darkness"}
SUMMON_BLOCKS = {"block:tempered_forge", "block:obelisk_frame"}

# custom biome tag -> the vanilla biome that biome replaced (its tags)
BIOME_TAGS = {
    "holy_ground": ["crimson_forest"],
    "eldritch_crystal_cove": ["warped_forest"],
    "irradiated_wastes": ["basalt_deltas"],
    "glowing_ocean": ["ocean"],
    "thermal_seas": ["ocean", "lukewarm"],
    "drenched_void": ["ocean", "deep"],
    "dread_reef": ["ocean", "cold"],
    "wilted_garden_caves": ["lush_caves"],
}


def tag(v, op="=="):
    return {"test": "has_biome_tag", "operator": op, "value": v}


END = [tag("the_end")]
OVERWORLD = [tag("overworld")]


def any_of(*tags):
    return [{"any_of": [tag(t) for t in tags]}]


# ident -> (population, weight, herd, biome filter, where, extra conditions)
NEW_SPAWNS = {
    # the End (the add-on spawned these on its End blocks and biomes)
    "mob:torpendo": ("monster", 3, (1, 1), END, "surface", {}),
    "mob:inviseer": ("monster", 3, (1, 1), END, "surface", {}),
    "mob:blighted_eye": ("monster", 3, (1, 2), END, "surface", {}),
    "mob:eternal_iris": ("monster", 2, (1, 1), END, "surface", {}),
    "mob:endersent": ("monster", 1, (1, 1), END, "surface", {}),
    "mob:shulk": ("monster", 4, (1, 3), END, "surface", {}),
    "mob:flying_shulker": ("monster", 3, (1, 2), END, "surface", {}),
    "mob:astral_orbiter": ("monster", 2, (1, 1), END, "surface", {}),
    "mob:grand_guritavoid": ("monster", 1, (1, 1), END, "surface", {}),
    "mob:end_mooshroom": ("animal", 8, (2, 4), END, "surface", {}),
    # the Overworld (the add-on spawned these in its sky and weather biomes)
    "mob:specter": ("monster", 3, (1, 1), OVERWORLD, "surface",
                    {"minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
                     "minecraft:height_filter": {"min": 90, "max": 320}}),
    "mob:sky_seeker": ("monster", 2, (1, 1), OVERWORLD, "surface", {"minecraft:height_filter": {"min": 120, "max": 320}}),
    "mob:aeroslime": ("monster", 4, (1, 2), OVERWORLD, "surface", {"minecraft:height_filter": {"min": 110, "max": 320}}),
    "mob:winter_breeze": ("monster", 5, (1, 1), any_of("frozen"), "surface", {}),
    "mob:solaronemone": ("monster", 3, (1, 1), any_of("desert"), "surface",
                         {"minecraft:brightness_filter": {"min": 10, "max": 15, "adjust_for_weather": True}}),
    "mob:redstone_golem": ("monster", 1, (1, 1), any_of("roofed_forest", "taiga"), "surface",
                           {"minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True}}),
    "mob:abyss_guardian": ("monster", 2, (1, 1), [{"all_of": [tag("ocean"), tag("deep")]}], "underwater", {}),
    # the Nether
    "mob:hovering_inferno": ("monster", 3, (1, 1), any_of("nether_wastes", "basalt_deltas"), "nether", {}),
}
PLACES = {
    "surface": {"minecraft:spawns_on_surface": {}},
    "underwater": {"minecraft:spawns_underwater": {}},
    "nether": {"minecraft:spawns_on_surface": {}, "minecraft:spawns_underground": {}},
}

# the End structures: on the outer islands, on land (y -1 cancels the placement)
END_Y = ("(math.abs(v.worldx) > 1000 || math.abs(v.worldz) > 1000) && q.heightmap(v.worldx, v.worldz) > 20 ? "
         "q.heightmap(v.worldx, v.worldz) : -1")
# structure -> (dimension/biome filter, y, chance per chunk %, pass)
STRUCTURES = {
    "abyssalchambers": (END, END_Y, 0.10, "after_surface_pass"),
    "astralstructure1": (END, END_Y, 0.20, "after_surface_pass"),
    "astralstructure2": (END, END_Y, 0.20, "after_surface_pass"),
    "chorusstructure1": (END, END_Y, 0.27, "after_surface_pass"),
    "chorusstructure2": (END, END_Y, 0.27, "after_surface_pass"),
    "chorusstructure3": (END, END_Y, 0.27, "after_surface_pass"),
    "endertowerthing": (END, END_Y, 0.27, "after_surface_pass"),
    "endtrialchamberscommand": (END, END_Y, 0.10, "after_surface_pass"),
    "portalstructure1": (END, END_Y, 0.20, "after_surface_pass"),
    "portalstructure2": (END, END_Y, 0.20, "after_surface_pass"),
    "portalstructure4": (END, END_Y, 0.20, "after_surface_pass"),
    # the Overworld: the sky towers float over land, the cryo chambers lie under the snow
    "skytower": (any_of("forest", "plains", "mountains"), {"distribution": "uniform", "extent": [260, 280]}, 2,
                 "after_surface_pass"),
    "starstructure4": (any_of("plains", "birch", "savanna"), {"distribution": "uniform", "extent": [260, 280]}, 1.5,
                       "after_surface_pass"),
    "cryochamberscommand": (any_of("frozen"), {"distribution": "uniform", "extent": [-50, -30]}, 3, "after_underground_pass"),
    # the Nether: the obsidian home floats on the lava sea, the irradiated home holds the
    "infernochambers": ([tag("nether")], {"distribution": "uniform", "extent": [31, 32]}, 2, "after_underground_pass"),
    "obsidianhome4": ([tag("nether")], 31, 2, "after_underground_pass"),
}

# too big for a feature: a command block placed by the feature loads them (as in the add-on)
LOADED = {"endtrialchamberscommand": "endtrialchamber", "cryochamberscommand": "cryochambers"}

NAMES = {"mob:soulerized_ghast": "Soulerized Ghast"}
# decoration entities of the structures (beams of the crystal beacons), kept as they are
DECOR = {"mob:ender_crystal_beacon", "mob:cloud_crystal_beacon"}

# boss summoners, crafted from vanilla materials of a similar rank
SUMMON_RECIPES = {
    "item:genesis_seed": (["ABA", "BCB", "ABA"], {"A": "spore_blossom", "B": "moss_block", "C": "golden_apple"}),
    "item:stellar_communicator": (["ABA", "CDC", " C "], {"A": "amethyst_block", "B": "end_crystal", "C": "echo_shard",
                                                          "D": "nether_star"}),
    "item:supreme_ender_eye": ([" A ", "CBD", " E "], {"A": "shulker_shell", "B": "ender_eye", "C": "end_crystal",
                                                        "D": "dragon_breath", "E": "nether_star"}),
    "block:obelisk_frame": (["ABA", "BCB", "ABA"], {"A": "end_stone_bricks", "B": "obsidian", "C": "ender_eye"}),
    "item:heart_of_darkness": (["ABA", "BCB", "ABA"], {"A": "echo_shard", "B": "sculk_catalyst", "C": "recovery_compass"}),
    "block:tempered_forge": (["ABA", "CDC", "EFE"], {"A": "magma_block", "B": "blaze_rod", "C": "gold_block",
                                                     "D": "blast_furnace", "E": "crying_obsidian", "F": "netherite_block"}),
}
GENESIS_TEXT = "Genesis Seed\n\n§7Plant it on Moss in the Lush Caves\nbelow Y=0 to awaken the Floral Amalgam"


# --- structures: only the chosen mobs ------------------------------------------------------
MOB_ANY = re.compile(r"(?:mob|boss):[a-z0-9_]+")


LOOT_ANY = re.compile(r"loot_tables/[A-Za-z0-9_/.]+?\.json")


def _replace_ids(v, mapping, chest=None):
    """Walks a typed NBT tree (mcstructure.read_nbt) replacing ids (and the add-on's loot
    tables by vanilla ones when chest is given)."""
    if isinstance(v, str):      # an id, or a command naming it
        v = MOB_ANY.sub(lambda m: mapping.get(m.group(0), m.group(0)), v)
        if chest:
            v = LOOT_ANY.sub(lambda m: extras.loot_path_for(m.group(0), chest), v)
        return v
    if isinstance(v, dict):
        return {k: _replace_ids(x, mapping, chest) for k, x in v.items()}
    if isinstance(v, list):
        return [_replace_ids(x, mapping, chest) for x in v]
    if isinstance(v, mcs.Tag):
        if v.type == mcs.LIST:
            t, xs = v.value
            return mcs.Tag(mcs.LIST, (t, [_replace_ids(x, mapping, chest) for x in xs]))
        return v
    return v


def adapt_structures(src, keep_ids):
    """The structures (and those their command blocks load through functions) keep their
    spawners, but these spawn the chosen mobs of each structure instead of the add-on's
    others (and so do the functions those command blocks run). Returns the structures."""
    chosen = {"mob:" + m for m in MOBS}
    def dim_of(n):
        biome = json.dumps(STRUCTURES[n][0]) if n in STRUCTURES else ""
        return "the_end" if "the_end" in biome else "nether" if '"nether"' in biome or "basalt" in biome else "overworld"
    loaders = {v: k for k, v in LOADED.items()}
    done, todo = {}, [(n, None, dim_of(loaders.get(n, n))) for n in list(STRUCTURES) + list(LOADED.values())]
    changed = 0
    while todo:
        name, parent_pool, dim = todo.pop()
        if name in done:
            continue
        rel = "structures/" + name + ".mcstructure"
        path = src.bp_path(rel)
        raw = open(path, "rb").read()
        text = raw.decode("latin-1")
        pool = sorted(set(re.findall(r"mob:[a-z0-9_]+", text)) & chosen) or parent_pool or []
        done[name] = rel
        others = sorted({i for i in re.findall(r"(?:mob|boss):[a-z0-9_]+", text) if i not in keep_ids})
        mapping = {}
        if others:
            if not pool:
                raise SystemExit(f"{name}: no tiene mobs elegidos para sustituir {others}")
            mapping = {o: pool[sum(map(ord, o)) % len(pool)] for o in others}
            changed += 1
        # and vanilla loot in their chests and trial spawners
        root = mcs.read_nbt(raw)
        with open(path, "wb") as f:
            f.write(mcs.write_nbt(_replace_ids(root, mapping, extras.structure_loot(name, dim))))
        for fn in set(re.findall(r"function ([a-z0-9_/]+)", text)):
            fp = src.bp_path("functions/" + fn + ".mcfunction")
            if not os.path.isfile(fp):
                continue
            body = read(fp)
            for o in sorted({i for i in re.findall(r"(?:mob|boss):[a-z0-9_]+", body) if i in src.entities
                             and i not in keep_ids}):
                if not pool:
                    raise SystemExit(f"{fn}: no hay mobs elegidos para sustituir {o}")
                body = re.sub(re.escape(o) + r"\b", pool[sum(map(ord, o)) % len(pool)], body)
            with open(fp, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            for sub in re.findall(r"structure load ([a-z0-9_:/]+)", body):
                todo.append((sub.split(":")[-1], pool, dim))
    print(f"  estructuras: {len(done)} (con las cargadas por bloques de comandos); "
          f"{changed} con spawners cambiados a los mobs elegidos")
    return done


# --- 1.1 balance ---------------------------------------------------------------------------------
def _holders(e):
    return [e.get("components", {})] + list(e.get("component_groups", {}).values())


def scale_health(e, f):
    for h in _holders(e):
        hp = h.get("minecraft:health")
        if isinstance(hp, dict):
            for k in ("value", "max"):
                if isinstance(hp.get(k), (int, float)):
                    hp[k] = round(hp[k] * f)


def tweak_entity(ident, data):
    e = data["minecraft:entity"]
    if ident == "mob:eternal_iris":                       # -25 % health
        scale_health(e, 0.75)
    elif ident == "projectile:eternal_iris_projectile":   # each shot teleported the iris
        e.get("events", {}).pop("minecraft:entity_spawned", None)
    elif ident == "mob:torpendo":                         # -15 % health and damage; it lunges (teu_torpendo.js)
        scale_health(e, 0.85)
        for h in _holders(e):
            a = h.get("minecraft:attack")
            if isinstance(a, dict) and isinstance(a.get("damage"), (int, float)):
                a["damage"] = round(a["damage"] * 0.85, 1)
            for k in ("minecraft:shooter", "minecraft:behavior.ranged_attack"):
                h.pop(k, None)


class Closure(dm.BPClosure):
    def allowed_entity(self, ident):
        return ident in self.src.entities and ident not in NEVER and not ident.startswith("minecraft:")

    def add_words(self, words, origin):
        if origin.startswith(("blocks/", "scripts/")):
            self.place_words |= words
            origin = "functions/" + origin       # counts as placing, like a function
        return super().add_words(words, origin)


# --- block scripts --------------------------------------------------------------------------
SUBSCRIBE = "world.beforeEvents.worldInitialize.subscribe("


def component_chunks(scripts_dir):
    """block_components.js: one subscribe() per custom component -> {name: code}."""
    text = read(os.path.join(scripts_dir, "block_components.js"))
    head, *parts = text.split(SUBSCRIBE)
    out = {}
    for p in parts:
        m = re.search(r"registerCustomComponent\('([^']+)'", p)
        if m:
            out[m.group(1)] = SUBSCRIBE + p.rstrip() + "\n"
    return head, out


def component_files(scripts_dir):
    """The other scripts that register one block component each -> {name: file}."""
    out = {}
    for name in os.listdir(scripts_dir):
        if name.endswith(".js") and name != "block_components.js":
            for comp in re.findall(r"registerCustomComponent\('([^']+)'", read(os.path.join(scripts_dir, name))):
                out[comp] = name
    return out


def block_components(src, ident):
    b = load(src.bp_path(src.blocks[ident]))["minecraft:block"]
    out = set()
    for c in [b.get("components", {})] + [p.get("components", {}) for p in b.get("permutations", [])]:
        cc = c.get("minecraft:custom_components")
        if isinstance(cc, list):
            out |= set(cc)
        out |= {k for k in c if ":" in k and not k.startswith(("minecraft:", "tag:"))}
    return out


# --- writing ------------------------------------------------------------------------------
def map_biomes(obj):
    if isinstance(obj, dict):
        if obj.get("test") == "has_biome_tag" and obj.get("value") in BIOME_TAGS \
                and obj.get("operator", "==") in ("==", "equals"):
            tags = BIOME_TAGS[obj["value"]]
            return tag(tags[0]) if len(tags) == 1 else {"all_of": [tag(t) for t in tags]}
        return {k: map_biomes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [map_biomes(v) for v in obj]
    return obj


def spawn_rule(ident, pop, weight, herd, biome, where, extra):
    cond = dict(PLACES[where])
    cond.update({"minecraft:weight": {"default": weight},
                 "minecraft:herd": {"min_size": herd[0], "max_size": herd[1]},
                 "minecraft:density_limit": {"surface": 2, "underground": 2},
                 "minecraft:biome_filter": biome})
    cond.update(extra)
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": ident, "population_control": pop}, "conditions": [cond]}}


def recipe(result, pattern, key):
    ident = "teu_mobs:" + result.split(":")[1]
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": ident}, "tags": ["crafting_table"], "pattern": pattern,
        "key": {k: {"item": "minecraft:" + v} for k, v in key.items()}, "result": {"item": result, "count": 1}}}


def structure_feature(src, name):
    """The add-on's structure_template_feature for a structure -> (path, data)."""
    for dirpath, _, files in os.walk(src.bp_path("features")):
        for n in files:
            path = os.path.join(dirpath, n)
            d = load(path)
            st = d.get("minecraft:structure_template_feature")
            if st and st["structure_name"].split(":")[-1] == name:
                return os.path.relpath(path, src.bp), d
    raise SystemExit(f"sin feature para la estructura {name}")


def filter_loot(data, keep, loot_files, renamed):
    def ok(e):
        if e.get("type") == "item":
            n = e.get("name", "")
            return n.startswith("minecraft:") or ":" not in n or n in keep
        if e.get("type") == "loot_table":
            return aq.loot_rel(e.get("name", "")) in loot_files
        return True
    pools = []
    for pool in data.get("pools", []):
        entries = []
        for e in pool.get("entries", []):
            if not ok(e):
                continue
            if e.get("type") == "loot_table":
                e = dict(e, name=renamed.get(aq.loot_rel(e["name"]), aq.loot_rel(e["name"])))
            if "pools" in e:
                e = dict(e, **filter_loot(e, keep, loot_files, renamed))
            entries.append(e)
        if entries:
            pools.append(dict(pool, entries=entries))
    return dict(data, pools=pools)


def build(src_dir):
    src_bp, src_rp = dm.find_packs(src_dir)
    # the add-on has ten broken JSON files: fix them in a copy first
    work = tempfile.mkdtemp()
    bp_dir, rp_dir = os.path.join(work, "bp"), os.path.join(work, "rp")
    shutil.copytree(src_bp, bp_dir)
    shutil.copytree(src_rp, rp_dir)
    teu_opt.BP, teu_opt.RP, teu_opt.OUT = bp_dir, rp_dir, work
    teu_opt.fix_json()
    fixed = extras.fix_case(rp_dir)
    if fixed:
        print("  modelos con mayúsculas distintas (salían invisibles):", ", ".join(fixed))
    src_bp, src_rp = bp_dir, rp_dir
    src = dm.Source(src_bp, src_rp)
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)

    start = ["mob:" + m for m in MOBS] + BOSSES + SUMMONERS
    missing = [e for e in start if e not in src.entities]
    if missing:
        raise SystemExit(f"no existen: {missing}")
    closure = Closure(src, start)
    keep_ids = set(start) | DECOR | {"mob:sky_seeker_sleeping"}
    structures = adapt_structures(src, keep_ids)
    features = {n: structure_feature(src, n) for n in STRUCTURES}
    closure.add_words(set(SUMMON_ITEMS | SUMMON_BLOCKS), "functions/summon")
    closure.run(sorted(structures.values()) + [f for f, _ in features.values()])

    # blocks: placed by the structures, functions and mobs; their scripts; until nothing new
    scripts_dir = os.path.join(src_bp, "scripts")
    head, chunks = component_chunks(scripts_dir)
    comp_files = component_files(scripts_dir)
    blocks, comps = set(), set()
    while True:
        new = {b for b in src.blocks if b in closure.place_words or b in SUMMON_BLOCKS} - blocks
        if not new:
            break
        blocks |= new
        extra = []
        for b in sorted(new):
            extra += closure.visit_file(src.blocks[b])
            for c in block_components(src, b) - comps:
                comps.add(c)
                if c in chunks:
                    extra += closure.add_words(mentions(chunks[c]), "scripts/" + c)
                elif c in comp_files:
                    extra += closure.add_words(mentions(read(os.path.join(scripts_dir, comp_files[c]))), "scripts/" + c)
        queue = extra
        while queue:
            kind, x = queue.pop()
            queue += closure.visit_file(src.entities[x] if kind == "entity" else x)
    entities = closure.entities
    # 1.1: no items of the add-on but the boss summoners (the rest becomes vanilla loot)
    all_items = set(src.items)
    items = set(SUMMON_ITEMS)
    keep = items | blocks
    with_client = set(dm.RPIndex(src_rp).client)
    boss_loot = {b: "loot_tables/teu_mobs/boss_" + b.split(":")[1] + ".json" for b in BOSSES
                 if not b.endswith("_clone")}

    # vanilla loot tables the mobs use get their own copy (vanilla mobs stay as they are)
    vanilla_loot = {"entities/" + i.split(":")[1] for i in src.entities if i.startswith("minecraft:")}
    renamed = {}
    for rel in sorted(closure.loot):
        key = rel.removeprefix("loot_tables/").removesuffix(".json")
        if key in vanilla_loot or key.startswith(("chests/village", "gameplay/")):
            renamed[rel] = "loot_tables/teu_mobs/" + key.replace("/", "_") + ".json"

    def fix_refs(text):
        for old, new in renamed.items():
            for o, n in ((old, new), (old.removesuffix(".json"), new.removesuffix(".json"))):
                text = text.replace(f'"{o}"', f'"{n}"')
        return text

    # --- BP
    timers = 0
    for ident in sorted(entities):
        text = extras.vanillize_text(fix_refs(json.dumps(load(src.bp_path(src.entities[ident])))), all_items, keep)
        data = aq.fix_entity(aq.sanitize(json.loads(text), src, keep), src)
        if ident == "item:genesis_seed":
            data = map_biomes(data)
        tweak_entity(ident, data)
        e = data["minecraft:entity"]
        if ident in boss_loot:
            e.setdefault("components", {})["minecraft:loot"] = {"table": boss_loot[ident]}
        if ident not in with_client and e["description"].get("is_spawnable"):
            e["description"]["is_spawnable"] = False     # helpers without a model: no (invisible) egg
        timers += extras.slow_particle_timers(data)
        dump(os.path.join(BP, src.entities[ident]), data)
    print(f"  temporizadores de partículas más lentos: {timers}")
    for ident in sorted(items):
        data = load(src.bp_path(src.items[ident]))
        ic = data["minecraft:item"]["components"]
        if ident == "item:genesis_seed":
            ic["minecraft:entity_placer"]["use_on"] = ["minecraft:moss_block"]
            ic["minecraft:display_name"] = {"value": GENESIS_TEXT}
        dump(os.path.join(BP, src.items[ident]), data)
    for ident in sorted(blocks):
        data = load(src.bp_path(src.blocks[ident]))
        c = data["minecraft:block"]["components"]
        if ident == "block:tempered_forge":
            c.pop("minecraft:crafting_table", None)     # the add-on's soul forge recipes are not here
        if ident == "block:obelisk_frame":                # unbreakable in its structure; now crafted
            c.pop("minecraft:loot", None)
            c["minecraft:destructible_by_mining"] = {"seconds_to_destroy": 50}
            c["minecraft:destructible_by_explosion"] = {"explosion_resistance": 1200}
        dump(os.path.join(BP, src.blocks[ident]), data)
    for rel in sorted(closure.loot):
        data = extras.vanillize_loot(load(src.bp_path(rel)), keep)
        data = filter_loot(data, keep, closure.loot, renamed)
        dump(os.path.join(BP, renamed.get(rel, rel)), data)
    for boss, rel in boss_loot.items():
        dump(os.path.join(BP, rel), extras.boss_loot(boss.split(":")[1]))
    bp_anim = {}
    for folder, key in (("animations", "animations"), ("animation_controllers", "animation_controllers")):
        for dirpath, _, files in os.walk(src.bp_path(folder)):
            for name in files:
                path = os.path.join(dirpath, name)
                for ident in load(path).get(key, {}):
                    bp_anim.setdefault(ident, set()).add(os.path.relpath(path, src_bp))
    anim_files = {f for w in closure.words if w in bp_anim for f in bp_anim[w]}
    for rel in sorted(anim_files | set(structures.values())):
        dm.copy(src_bp, BP, rel)
    for rel in sorted(closure.functions):
        out = os.path.join(BP, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(extras.projectiles_at_player(rel, extras.vanillize_text(read(src.bp_path(rel)), all_items, keep)))
    # spawn rules: the add-on's (vanilla biomes) and new ones
    have = set()
    for dirpath, _, files in os.walk(src.bp_path("spawn_rules")):
        for name in files:
            path = os.path.join(dirpath, name)
            data = load(path)
            ident = data["minecraft:spawn_rules"]["description"]["identifier"]
            if ident not in entities or ident.startswith("boss:"):   # the bosses live in their arenas
                continue
            data = map_biomes(data)
            conds, seen = [], set()
            for c in data["minecraft:spawn_rules"]["conditions"]:
                k = json.dumps(c, sort_keys=True)
                if k not in seen:
                    seen.add(k)
                    conds.append(c)
            data["minecraft:spawn_rules"]["conditions"] = conds
            have.add(ident)
            dump(os.path.join(BP, os.path.relpath(path, src_bp)), data)
    for ident, spec in NEW_SPAWNS.items():
        assert ident not in have, ident
        dump(os.path.join(BP, "spawn_rules", "teu_mobs", ident.split(":")[1] + ".json"), spawn_rule(ident, *spec))
    # structures: their feature (as in the add-on) and a rule in vanilla biomes
    for name, (biome, y, chance, pass_) in STRUCTURES.items():
        rel, data = features[name]
        dump(os.path.join(BP, rel), data)
        ident = data["minecraft:structure_template_feature"]["description"]["identifier"]
        dump(os.path.join(BP, "feature_rules", "teu_mobs", name + ".json"), {
            "format_version": "1.13.0", "minecraft:feature_rules": {
                "description": {"identifier": "teu_mobs:" + name, "places_feature": ident},
                "conditions": {"placement_pass": pass_, "minecraft:biome_filter": biome},
                "distribution": {"iterations": 1, "scatter_chance": {"numerator": int(chance * 10), "denominator": 1000},
                                 "x": {"distribution": "uniform", "extent": [0, 15]}, "y": y,
                                 "z": {"distribution": "uniform", "extent": [0, 15]}}}})
    for result, (pattern, key) in SUMMON_RECIPES.items():
        dump(os.path.join(BP, "recipes", "teu_mobs", result.split(":")[1] + ".json"), recipe(result, pattern, key))
    # scripts: the block components the kept blocks use, the Torpendo's lunge, the compasses
    out_scripts = os.path.join(BP, "scripts")
    os.makedirs(out_scripts, exist_ok=True)
    with open(os.path.join(out_scripts, "teu_block_components.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(head.rstrip() + "\n\n" + "\n".join(chunks[c] for c in sorted(comps) if c in chunks))
    shutil.copyfile(os.path.join(HERE, "teu", "torpendo.js"), os.path.join(out_scripts, "teu_torpendo.js"))
    extra_files = sorted({comp_files[c] for c in comps if c in comp_files and c not in chunks})
    files = dm.script_closure(scripts_dir, {f: read(os.path.join(scripts_dir, f)) for f in extra_files})
    for rel in sorted(files):
        dm.copy(scripts_dir, out_scripts, rel)
    imports = ["teu_block_components", "teu_torpendo", "teu_compass"] + [f[:-3] for f in extra_files]
    with open(os.path.join(out_scripts, "main.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(f"import './{i}.js';\n" for i in imports))
    dm.copy(src_bp, BP, "pack_icon.png")
    obp, orp = load(os.path.join(src_bp, "manifest.json")), load(os.path.join(src_rp, "manifest.json"))
    server = [d for d in obp.get("dependencies", []) if d.get("module_name") == "@minecraft/server"]
    dump(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": NAME, "description": "Mobs y jefes de The Everything Update (uso personal).",
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": obp["header"]["min_engine_version"]},
        "modules": [{"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
                    {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
                     "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION}] + server})

    # --- RP
    rpi = dm.RPIndex(src_rp)
    rp_start = {"pack_icon.png"}
    for ident in entities:
        rp_start.update(rpi.client.get(ident, [])[:1])
    for ident in items:
        rp_start.update(rpi.attach.get(ident, []))
    bp_words = set(closure.words)
    for root, _, fs in os.walk(BP):
        for name in fs:
            if name.endswith((".json", ".mcfunction", ".js")):
                bp_words |= mentions(read(os.path.join(root, name)))
    special = {"textures/item_texture.json", "textures/terrain_texture.json", "textures/flipbook_textures.json",
               "blocks.json", "sounds.json", "sounds/sound_definitions.json"}
    blocks_json = load(os.path.join(src_rp, "blocks.json"))
    blocks_json = {k: v for k, v in blocks_json.items() if k == "format_version" or k in blocks}
    bp_words |= mentions(json.dumps(blocks_json))
    rp_files, words = dm.rp_closure(rpi, {f for f in rp_start if os.path.isfile(os.path.join(src_rp, f))} - special,
                                    bp_words)
    dump(os.path.join(RP, "blocks.json"), blocks_json)
    atlas = set()
    for rel in ("textures/item_texture.json", "textures/terrain_texture.json"):
        if os.path.isfile(os.path.join(src_rp, rel)):
            data = load(os.path.join(src_rp, rel))
            data["texture_data"] = {k: v for k, v in data["texture_data"].items() if k in words}
            for v in data["texture_data"].values():
                for t in dm._walk_strings(v):
                    atlas.update(dm.texture_files(src_rp, t))
            dump(os.path.join(RP, rel), data)
    fb = os.path.join(src_rp, "textures", "flipbook_textures.json")
    if os.path.isfile(fb):
        flip = [f for f in load(fb) if f.get("atlas_tile") in words]
        for f in flip:
            atlas.update(dm.texture_files(src_rp, f["flipbook_texture"]))
        dump(os.path.join(RP, "textures", "flipbook_textures.json"), flip)
    sounds = load(os.path.join(src_rp, "sounds.json"))
    ent = sounds.get("entity_sounds", {}).get("entities", {})
    sounds.setdefault("entity_sounds", {})["entities"] = {k: v for k, v in ent.items() if k in entities}
    for k in ("block_sounds", "interactive_sounds"):
        if isinstance(sounds.get(k), dict):
            sounds[k] = {b: v for b, v in sounds[k].items() if b in blocks or b == "block_sounds"}
    dump(os.path.join(RP, "sounds.json"), extras.fix_sounds(sounds))
    sound_words = words | mentions(json.dumps(sounds))
    sd_path = os.path.join(src_rp, "sounds", "sound_definitions.json")
    defs = load(sd_path)
    sd = defs.get("sound_definitions", defs)
    kept = {k: v for k, v in sd.items() if k in sound_words}
    dump(os.path.join(RP, "sounds", "sound_definitions.json"),
         dict(defs, sound_definitions=kept) if "sound_definitions" in defs else kept)
    sound_files = set()
    for v in kept.values():
        for s in v.get("sounds", []):
            n = s if isinstance(s, str) else s.get("name", "")
            for ext in (".ogg", ".fsb", ".wav", ".mp3"):
                if os.path.isfile(os.path.join(src_rp, n + ext)):
                    sound_files.add(n + ext)
    textures = (rp_files - special) | atlas
    for rel in sorted(textures | dm.texture_sets(src_rp, textures) | sound_files):
        if os.path.isfile(os.path.join(src_rp, rel)):
            dm.copy(src_rp, RP, rel)
    n = 0
    for dirpath, _, fs in os.walk(os.path.join(RP, "particles")):
        for name in fs:
            if name.endswith(".json"):
                path = os.path.join(dirpath, name)
                dump(path, extras.lighten_particle(load(path)))
                n += 1
    print(f"  partículas aligeradas: {n}")
    tex = extras.particle_textures(RP)
    print(f"  texturas de partículas más claras: {sum(extras.clearer_particle_texture(t) for t in tex)}")
    fixes = 0
    for folder, fn in (("animation_controllers", extras.fix_controller), ("models", extras.fix_baby_locators)):
        for dirpath, _, fs in os.walk(os.path.join(RP, folder)):
            for name in fs:
                if name.endswith(".json"):
                    path = os.path.join(dirpath, name)
                    d = load(path)
                    if fn(d):
                        fixes += 1
                        dump(path, d)
    print(f"  controladores y modelos corregidos: {fixes}")
    teu_opt.nto.BP, teu_opt.nto.RP = BP, RP
    teu_opt.nto.blocks_json()
    teu_opt.nto.block_loot()
    compass_items, arena_files = extras.write_arenas(BP, RP, os.path.join(HERE, "teu", "compass.js"), entities)
    print(f"  arenas: {', '.join(arena_files)}; brújulas: {len(compass_items)}")
    for rel in sorted(f for f in rp_files if f.startswith("entity/") and f.endswith(".json")):
        dump(os.path.join(RP, rel), extras.fix_guardian_client(aq.fix_client(load(os.path.join(src_rp, rel)))))
    for name in os.listdir(os.path.join(src_rp, "texts")):
        dm.copy(src_rp, RP, "texts/" + name)
        if name.endswith(".lang"):           # the add-on names "mob:soulrized_ghast", a typo
            path = os.path.join(RP, "texts", name)
            text = read(path)
            add = [f"entity.{i}.name={n}" for i, n in NAMES.items()
                   if not re.search(rf"^entity\.{re.escape(i)}\.name=", text, re.M)]
            if add:
                with open(path, "a", encoding="utf-8", newline="\n") as f:
                    f.write(("" if text.endswith("\n") else "\n") + "\n".join(add) + "\n")
    dump(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": NAME, "description": "Recursos de TEU Mobs (uso personal).", "uuid": UUIDS["rp"],
                   "version": VERSION, "min_engine_version": orp["header"]["min_engine_version"]},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}]})
    shutil.rmtree(work, ignore_errors=True)

    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, fs in os.walk(pack):
                dirs.sort()
                for name in sorted(fs):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, OUT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    mobs = sorted(e for e in entities if e.startswith(("mob:", "boss:")))
    print(f"{len(mobs)} mobs y jefes, {len(entities) - len(mobs)} entidades auxiliares, {len(items)} objetos, "
          f"{len(blocks)} bloques, {len(STRUCTURES)} estructuras, {len(closure.loot)} tablas de botín, "
          f"{len(closure.functions)} funciones, {len(comps)} componentes de bloque")
    print("mobs y jefes:", ", ".join(m.split(":")[1] for m in mobs))
    print("añadidos por referencias:", "; ".join(f"{e.split(':')[1]} <- {closure.pulled[e]}" for e in mobs
                                                 if e in closure.pulled and e not in start))
    print("botín renombrado:", ", ".join(sorted(renamed)) or "-")
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for i, s in enumerate(sys.argv[1:]):
            if os.path.isdir(s):
                shutil.copytree(s, os.path.join(tmp, str(i)))
            else:
                aq.unpack(s, os.path.join(tmp, str(i)))
        build(tmp)


if __name__ == "__main__":
    main()
