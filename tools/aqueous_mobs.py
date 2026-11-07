"""Extracts only the mobs of Aqueous Depths (1.2 Hotfix 2) into "Aqueous Mobs", for
personal use (the add-on is not ours to share: the packs go to the git-ignored private/).

Kept:
  * every mob (mob:...), the Primordial Wyrm boss and its clone, and the three
    turrets of the Atlantis ruins (given spawn eggs, since the ruins are left out);
  * what they need: the projectiles and attack entities they spawn, their
    functions and BP animations, loot, models, textures, animations, particles,
    sounds and names;
  * the items they use, drop or wear (pearls, the merfolk's trade goods, the
    adoption bracelet, scrap metal gear and harpoon...), as plain items: their
    scripted effects, recipes and block placing are left out.

Left out: biomes, blocks and ores, structures and world generation, the other items,
recipes, trades of blocks, scripts (they are all about items and blocks), the item
summons (grimoires, soul forge) and the overrides of vanilla mobs (drowned, glow
squid, nautilus) and of vanilla loot tables.

Spawning without the add-on's biomes: their tags become similar vanilla oceans
(BIOME_TAGS). The boss keeps its natural spawn (deep oceans below y 0) but rarer.

    python3 tools/aqueous_mobs.py path/to/AqueousDepths.mcaddon
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
from dungeons_mobs import load, dump, read, mentions  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "AqueousMobs_BP")
RP = os.path.join(OUT, "AqueousMobs_RP")
MCADDON = os.path.join(OUT, "AqueousMobs.mcaddon")
NAME = "Aqueous Mobs"
VERSION = [1, 0, 0]
UUIDS = dict(bp="0c7f3e52-9a41-4d6b-8e17-5b2a3c9d4f61", bp_data="6e2a9d14-3c58-4b7f-a0e1-d4f8b2c6e937",
             rp="a93d5f27-1e64-4c8a-b2f0-7c5e9d3a1b48", rp_res="4f1b8c63-5d27-4e9a-8a3c-e6b2d0f7c519")

NEVER = {"mob:aqueous_soul_forge", "mob:guardian_grimoire", "mob:sea_urchin_grimoire", "mechanic:structure_block"}
TURRETS = {"mob:arrow_turrent", "mob:fire_turrent", "mob:ice_turrent"}
# The add-on's biomes -> the vanilla oceans most like them.
BIOME_TAGS = {
    "dread_reef": ["ocean", "cold", "deep"],
    "drenched_void": ["ocean", "deep"],
    "glowing_ocean": ["ocean", "lukewarm"],
    "thermal_seas": ["ocean", "warm"],
    "iceberg_ocean": ["ocean", "frozen"],
    "island_ocean": ["ocean", "warm"],
}
# Vanilla loot tables the add-on overrides: the kept mobs get their own copy instead.
VANILLA_LOOT = {"entities/dolphin", "entities/drowned", "entities/drowned_equipment", "entities/drowned_ranged_equipment",
                "entities/fish", "entities/guardian", "entities/pufferfish", "entities/salmon_large",
                "entities/salmon_normal", "entities/skeleton_horse", "entities/cod", "entities/squid",
                "entities/glow_squid", "entities/nautilus"}
# Bugs of the original resource pack, fixed here.
BROKEN_ANIMS = {"attack_controller", "animation.drowned.attack.baby_rotations"}   # used but not defined anywhere
# the brute and the prismarine foe throw a harpoon that does not exist: the merfolk's
ENTITY_RENAMES = {"projectile:scrap_metal_harpoon": "sword:scrap_metal_harpoon_debug"}
NAMES = {"mob:arrow_turrent": "Arrow Turret", "mob:fire_turrent": "Fire Turret", "mob:ice_turrent": "Ice Turret"}
ITEM_DROP = {"minecraft:block_placer", "minecraft:entity_placer", "minecraft:custom_components", "minecraft:shooter",
             "minecraft:projectile", "minecraft:throwable", "minecraft:record"}


class Closure(dm.BPClosure):
    def allowed_entity(self, ident):
        return (ident in self.src.entities and ident not in NEVER
                and not ident.startswith(("minecraft:", "test:")))


def start_entities(src):
    return {i for i in src.entities if i.startswith(("mob:", "boss:")) and i not in NEVER}


def own_ref(s, src):
    return (isinstance(s, str) and ":" in s and not s.startswith("minecraft:")
            and (s in src.items or s in src.blocks or s.startswith(("block:", "ore:"))))


def sanitize(obj, src, items):
    """Drops, from lists, the add-on's blocks and the items that are not kept."""
    if isinstance(obj, dict):
        return {k: sanitize(v, src, items) for k, v in obj.items()}
    if isinstance(obj, list):
        out = []
        for v in obj:
            if own_ref(v, src) and v not in items:
                continue
            out.append(sanitize(v, src, items))
        return out
    return obj


def map_biomes(obj):
    if isinstance(obj, dict):
        if obj.get("test") == "has_biome_tag" and obj.get("value") in BIOME_TAGS and obj.get("operator", "==") in ("==", "equals"):
            return {"all_of": [{"test": "has_biome_tag", "operator": "==", "value": t} for t in BIOME_TAGS[obj["value"]]]}
        return {k: map_biomes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [map_biomes(v) for v in obj]
    return obj


def plain_item(data, entities, items):
    comps = data["minecraft:item"].get("components", {})
    for k in list(comps):
        if not k.startswith("minecraft:") or k in ITEM_DROP:
            del comps[k]
    # repair / ammo / food conversions naming items that are not kept
    text = json.dumps(comps)
    for ref in set(re.findall(r'"([a-z_]+:[a-z0-9_]+)"', text)):
        if not ref.startswith("minecraft:") and ref not in items and ref not in entities:
            for k in [k for k, v in comps.items() if ref in json.dumps(v)]:
                del comps[k]
    return data


def loot_rel(name):
    return "loot_tables/" + name.removeprefix("loot_tables/").removesuffix(".json") + ".json"


def filter_loot(data, items, loot_files, renamed):
    def ok(e):
        if e.get("type") == "item":
            n = e.get("name", "")
            return n.startswith("minecraft:") or ":" not in n or n in items
        if e.get("type") == "loot_table":
            return loot_rel(e.get("name", "")) in loot_files
        return True
    pools = []
    for pool in data.get("pools", []):
        entries = []
        for e in pool.get("entries", []):
            if not ok(e):
                continue
            if e.get("type") == "loot_table":
                e = dict(e, name=renamed.get(loot_rel(e["name"]), loot_rel(e["name"])))
            entries.append(e)
        if entries:
            pools.append(dict(pool, entries=entries))
    return dict(data, pools=pools)


def fix_entity(data, src):
    """Bugs of the original entities: events fired but not defined (given empty ones),
    component groups added or removed but not defined (dropped from the lists), and a
    loot table that does not exist."""
    ent = data["minecraft:entity"]
    events = ent.setdefault("events", {})
    groups = set(ent.get("component_groups", {}))
    fired = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "event" and isinstance(v, str):
                    fired.add(v)
                if k in ("add", "remove") and isinstance(v, dict) and isinstance(v.get("component_groups"), list):
                    v["component_groups"] = [g for g in v["component_groups"] if g in groups]
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(ent)
    for name in sorted(fired - set(events)):
        events[name] = {}
    loot = ent.get("components", {}).get("minecraft:loot", {}).get("table")
    if isinstance(loot, str) and loot.startswith("loot_tables/entities/") and not os.path.isfile(src.bp_path(loot)) \
            and loot.removeprefix("loot_tables/").removesuffix(".json") not in VANILLA_LOOT | {"entities/skeleton_horse"}:
        del ent["components"]["minecraft:loot"]
    return data


def fix_client(data):
    """Drops animations that point nowhere (and their uses in scripts.animate)."""
    desc = data["minecraft:client_entity"]["description"]
    anims = desc.get("animations", {})
    for k in [k for k, v in anims.items() if v in BROKEN_ANIMS]:
        del anims[k]
    def used(entry):
        name = entry if isinstance(entry, str) else next(iter(entry))
        return name in anims and name not in BROKEN_ANIMS
    for key in ("animate", "pre_animation"):
        scripts = desc.get("scripts", {})
        if isinstance(scripts.get(key), list) and key == "animate":
            scripts[key] = [e for e in scripts[key] if used(e)]
    return data


def build(src_dir):
    src_bp, src_rp = dm.find_packs(src_dir)
    src = dm.Source(src_bp, src_rp)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)

    closure = Closure(src, start_entities(src))
    closure.run([])
    entities = closure.entities
    items = {i for i in src.items if i in closure.words}

    # vanilla loot tables the mobs use: their own copy, so vanilla mobs are not changed
    renamed = {}
    for rel in sorted(closure.loot):
        key = rel.removeprefix("loot_tables/").removesuffix(".json")
        if key in VANILLA_LOOT:
            renamed[rel] = "loot_tables/aqueous/" + key.split("/")[-1] + ".json"

    def fix_refs(text):
        for old, new in renamed.items():
            for o, n in ((old, new), (old.removesuffix(".json"), new.removesuffix(".json"))):
                text = text.replace(f'"{o}"', f'"{n}"')
        return text

    # BP animations / animation controllers named by kept entities
    bp_anim = {}
    for folder, key in (("animations", "animations"), ("animation_controllers", "animation_controllers")):
        for dirpath, _, files in os.walk(src.bp_path(folder)):
            for name in files:
                path = os.path.join(dirpath, name)
                for ident in load(path).get(key, {}):
                    bp_anim.setdefault(ident, set()).add(os.path.relpath(path, src_bp))
    anim_files = {f for w in closure.words if w in bp_anim for f in bp_anim[w]}

    # --- write BP
    for ident in sorted(entities):
        text = fix_refs(json.dumps(load(src.bp_path(src.entities[ident]))))
        for old, new in ENTITY_RENAMES.items():
            text = text.replace(f'"{old}"', f'"{new}"')
        data = fix_entity(sanitize(json.loads(text), src, items), src)
        desc = data["minecraft:entity"]["description"]
        if ident in TURRETS:
            desc["is_spawnable"] = True
        dump(os.path.join(BP, src.entities[ident]), data)
    for ident in sorted(items):
        dump(os.path.join(BP, src.items[ident]), plain_item(load(src.bp_path(src.items[ident])), entities, items))
    for rel in sorted(closure.loot):
        data = filter_loot(load(src.bp_path(rel)), items, closure.loot, renamed)
        dump(os.path.join(BP, renamed.get(rel, rel)), data)
    for rel in sorted(closure.functions | anim_files):
        dm.copy(src_bp, BP, rel)
    for dirpath, _, files in os.walk(src.bp_path("spawn_rules")):
        for name in files:
            path = os.path.join(dirpath, name)
            data = load(path)
            ident = data["minecraft:spawn_rules"]["description"]["identifier"]
            if ident not in entities:
                continue
            data = map_biomes(data)
            if ident == "boss:primordial_wyrm":   # a boss in every deep ocean: much rarer
                for c in data["minecraft:spawn_rules"]["conditions"]:
                    c["minecraft:weight"] = {"default": 1}
                    c["minecraft:density_limit"] = {"surface": 1, "underground": 1}
            dump(os.path.join(BP, os.path.relpath(path, src_bp)), data)
    dm.copy(src_bp, BP, "pack_icon.png")
    obp, orp = load(os.path.join(src_bp, "manifest.json")), load(os.path.join(src_rp, "manifest.json"))
    dump(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": NAME, "description": "Solo los mobs de Aqueous Depths (uso personal).", "uuid": UUIDS["bp"],
                   "version": VERSION, "min_engine_version": obp["header"]["min_engine_version"]},
        "modules": [{"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION}]})

    # --- RP
    rpi = dm.RPIndex(src_rp)
    start = {"pack_icon.png"}
    for ident in entities:
        clients = rpi.client.get(ident, [])
        real = [c for c in clients if "test" not in os.path.basename(c)] or clients[:1]   # merfolktest: a duplicate
        start.update(real[:1])
    for ident in items:
        start.update(rpi.attach.get(ident, []))
    bp_words = set(closure.words)
    for root, _, files in os.walk(BP):
        for name in files:
            if name.endswith((".json", ".mcfunction")):
                bp_words |= mentions(read(os.path.join(root, name)))
    rp_files, words = dm.rp_closure(rpi, {f for f in start if os.path.isfile(os.path.join(src_rp, f))}, bp_words)
    atlas = set()
    for rel in ("textures/item_texture.json", "textures/terrain_texture.json"):
        if os.path.isfile(os.path.join(src_rp, rel)):
            data = load(os.path.join(src_rp, rel))
            data["texture_data"] = {k: v for k, v in data["texture_data"].items() if k in words}
            for v in data["texture_data"].values():
                for t in dm._walk_strings(v):
                    atlas.update(dm.texture_files(src_rp, t))
            dump(os.path.join(RP, rel), data)
    sounds_path = os.path.join(src_rp, "sounds.json")
    sound_words = set(words)
    if os.path.isfile(sounds_path):
        sounds = load(sounds_path)
        ent = sounds.get("entity_sounds", {}).get("entities", {})
        sounds.setdefault("entity_sounds", {})["entities"] = {k: v for k, v in ent.items() if k in entities}
        for v in sounds["entity_sounds"]["entities"].values():   # events whose sound is just "e"
            ev = v.get("events", {})
            for name in [n for n, x in ev.items() if x == "e" or (isinstance(x, dict) and x.get("sound") == "e")]:
                del ev[name]
        sounds.pop("block_sounds", None)
        sounds.pop("interactive_sounds", None)
        dump(os.path.join(RP, "sounds.json"), sounds)
        sound_words |= mentions(json.dumps(sounds))
    sound_files = set()
    sd_path = os.path.join(src_rp, "sounds", "sound_definitions.json")
    if os.path.isfile(sd_path):
        defs = load(sd_path)
        sd = defs.get("sound_definitions", defs)
        kept = {k: v for k, v in sd.items() if k in sound_words}
        dump(os.path.join(RP, "sounds", "sound_definitions.json"),
             dict(defs, sound_definitions=kept) if "sound_definitions" in defs else kept)
        for v in kept.values():
            for s in v.get("sounds", []):
                n = s if isinstance(s, str) else s.get("name", "")
                for ext in (".ogg", ".fsb", ".wav", ".mp3"):
                    if os.path.isfile(os.path.join(src_rp, n + ext)):
                        sound_files.add(n + ext)
    skip = {"textures/item_texture.json", "textures/terrain_texture.json", "sounds.json", "sounds/sound_definitions.json"}
    skip |= {f for f in rp_files if f.startswith("entity/") and "test" in os.path.basename(f)}
    files = (rp_files - skip) | atlas
    for rel in sorted(files | dm.texture_sets(src_rp, files) | sound_files):
        if os.path.isfile(os.path.join(src_rp, rel)):
            dm.copy(src_rp, RP, rel)
    for rel in sorted(f for f in files if f.startswith("entity/") and f.endswith(".json") and f not in skip):
        dump(os.path.join(RP, rel), fix_client(load(os.path.join(src_rp, rel))))
    # spawn eggs for the turrets
    for ident in TURRETS & entities:
        for rel in rpi.client.get(ident, []):
            d = load(os.path.join(src_rp, rel))
            d["minecraft:client_entity"]["description"].setdefault("spawn_egg", {"base_color": "#3a4a52", "overlay_color": "#6fd2c4"})
            dump(os.path.join(RP, rel), d)
    for name in os.listdir(os.path.join(src_rp, "texts")):
        dm.copy(src_rp, RP, "texts/" + name)
        if name.endswith(".lang"):
            path = os.path.join(RP, "texts", name)
            text = read(path)
            add = [f"entity.{i}.name={n}\nitem.spawn_egg.entity.{i}.name=Spawn {n}" for i, n in NAMES.items()
                   if f"entity.{i}.name=" not in text and i in entities]
            if add:
                with open(path, "a", encoding="utf-8", newline="\n") as f:
                    f.write(("" if text.endswith("\n") else "\n") + "\n".join(add) + "\n")
    dump(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": NAME, "description": "Recursos de Aqueous Mobs (uso personal).", "uuid": UUIDS["rp"],
                   "version": VERSION, "min_engine_version": orp["header"]["min_engine_version"]},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}]})

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
    print(f"{len(mobs)} mobs: {', '.join(m.split(':')[1] for m in mobs)}")
    print(f"{len(entities) - len(mobs)} auxiliary entities, {len(items)} items, {len(closure.loot)} loot tables, "
          f"{len(closure.functions)} functions")
    print(f"items: {', '.join(sorted(items))}")
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")


def unpack(path, into):
    """An .mcaddon may hold .mcpack files: unzip those too."""
    with zipfile.ZipFile(path) as z:
        z.extractall(into)
    for dirpath, _, files in os.walk(into):
        for name in files:
            if name.endswith((".mcpack", ".zip")):
                sub = os.path.join(dirpath, name[:-7] if name.endswith(".mcpack") else name[:-4])
                with zipfile.ZipFile(os.path.join(dirpath, name)) as z:
                    z.extractall(sub)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    if os.path.isdir(sys.argv[1]):
        build(sys.argv[1])
        return
    with tempfile.TemporaryDirectory() as tmp:
        unpack(sys.argv[1], tmp)
        build(tmp)


if __name__ == "__main__":
    main()
