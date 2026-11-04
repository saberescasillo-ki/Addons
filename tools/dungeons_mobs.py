"""Builds "Dungeons Mobs" from Alylica's Dungeons (2.1.4), for personal use.

Kept:
  * the enemies (entities/new, the variants), minibosses (Endersent, Wildfire,
    Illusioner, Redstone Golem, Drowned Necromancer) and the enchanted mobs
    (with the vanilla mob overrides that let them appear);
  * three bosses: the Vengeful Heart of Ender, the Endersent's six Eyes and
    the Hovering Inferno, with their structures (broken citadel, eye lairs and
    totem, nether arena). Their structure_sets are dropped, so they never
    generate on their own: place them with /place structure;
  * all the armour, with the scripts of its effects, gilding and mystery armour;
  * whatever those need: projectiles, summons, boss chests and keys, blocks of
    the structures, loot, the weapons the mobs hold (as plain items), models,
    textures, animations, particles, sounds and the boss health bars.

Left out: Ancient Hunts (dimensions and Ancients), the other bosses, weapons,
artefacts, ranged weapons, blocks and furniture, advancements, books, maps and
the merchants.

The packs are written to private/ (git-ignored): the add-on is not ours to
share, so nothing it contains goes into this repository.

    python3 tools/dungeons_mobs.py path/to/AlylicasDungeons.zip
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "DungeonsMobs_BP")
RP = os.path.join(OUT, "DungeonsMobs_RP")
MCADDON = os.path.join(OUT, "DungeonsMobs.mcaddon")

NAME = "Dungeons Mobs"
UUIDS = dict(bp="7c1e5a90-3b2d-4f6e-8a41-d2c9b0e7f513", bp_data="1f9d3c72-6e4a-4b85-9d20-a3e7c5b8f146",
             bp_script="b84e2f17-c9a3-4d60-8e5b-7f1a0d3c2e98", rp="4a6c8e20-1b3d-4f57-a9c2-e0d4f6b8a371",
             rp_res="d3f5b791-2a4c-4e68-b0d1-9c7e5a3f2b84")
VERSION = [1, 0, 0]

# --- What to keep -------------------------------------------------------------
ENTITY_DIRS = ["entities/new/", "entities/variant/", "entities/enchanted/", "entities/vanilla/enchantable/"]
BOSS_DIRS = ["entities/new/boss/endersent/", "entities/new/boss/vengeful_heart_of_ender/",
             "entities/new/boss/wildfire/"]
# Not enemies (traders, keys, Ancient Hunt mobs, spawner block entity).
ENTITY_SKIP = {
    "entities/new/ancient_hunt_mooshroom.json", "entities/new/ancient_hunt_silverfish.json",
    "entities/enchanted/new/enchanted_ancient_hunt_mooshroom.json",
    "entities/enchanted/new/enchanted_ancient_hunt_silverfish.json",
    "entities/new/key_golem/key_golem.json", "entities/new/key_golem/diamond_key_golem.json",
    "entities/new/monster_spawner.json", "entities/new/piggy_bank.json", "entities/new/piglin_merchant.json",
}
# Never pulled in by references: other bosses, Ancients, Ancient Hunts, dummies.
ENTITY_NEVER = re.compile(r"^entities/(ancient/|new/boss/(?!endersent/|vengeful_heart_of_ender/|wildfire/)|"
                          r"utility/ancient_hunt|target_dummy|dummy|vanilla/(?!enchantable/))")
UTILITY_NEVER = {  # awakening effects and helpers of the bosses that are not kept
    "dungeons:ancient_guardian_awaken_boom", "dungeons:corrupted_cauldron_awaken_boom",
    "dungeons:jungle_abomination_awaken_boom", "dungeons:mooshroom_monstrosity_awaken_boom",
    "dungeons:nameless_one_awaken_boom", "dungeons:redstone_monstrosity_awaken_boom",
    "dungeons:spooky_monstrosity_awaken_boom", "dungeons:tempest_golem_awaken_boom",
    "dungeons:wretched_wraith_awaken_boom", "dungeons:ancient_guardian_ammo", "dungeons:eye_guardian_ammo",
    "dungeons:nameless_vanguard", "dungeons:redstone_monstrosity_warn", "dungeons:squall_golem_resting",
}

# Structures of the three bosses (worldgen ids). Their structure_sets are left out.
BOSS_STRUCTURES = ["dungeons:broken_citadel", "dungeons:nether_arena", "dungeons:endersent_totem",
                   "dungeons:binding_eye_lair", "dungeons:blight_eye_lair", "dungeons:ravenous_eye_lair",
                   "dungeons:reaping_eye_lair", "dungeons:savage_eye_lair", "dungeons:spiked_eye_lair"]

ITEM_ALWAYS = ["items/armor/", "items/drop_mystery_armour.json", "items/drop_mystery_armour_gilded.json",
               "items/enchanted_eye_of_ender.json"]
# Items kept when something kept refers to them (drops, chests, structures).
ITEM_IF_USED = ["items/keys/", "items/ranged/arrows/"]
# Weapons held by the mobs: kept as plain items, without their scripted effects.
GEAR_DIR = "items/melee/"

# Script modules loaded by main.js / entityBehaviour.js / blocks.js.
MAIN_IMPORTS = {
    "./worldInitialise.js", "./components/armour.js", "./components/blocks.js",
    "./misc/shadowForm.js", "./misc/voidedEffect.js", "./misc/soulSickness.js", "./misc/itemDescriptions.js",
    "./misc/bossManager.js", "./misc/soulManager.js", "./misc/armourEquipSound.js", "./misc/gilds.js",
    "./misc/dropMysteryArmour.js", "./misc/stunnedEffect.js", "./misc/diamondChest.js",
    "./misc/entityBehaviour.js", "./misc/customcommands/gildItem.js", "./misc/customcommands/fixEquipment.js",
    "./misc/customcommands/mysteryArmour.js",
}
BEHAVIOUR_IMPORTS = {
    "hoveringInferno", "vengefulHeartofEnder", "illusioner", "endersent", "wraith", "necromancer", "enchanter",
    "snareling", "watchling", "blastling", "icyCreeper", "geomancer", "poisonQuillVine", "mountaineer",
    "towerGuard", "tropicalSlime", "iceologer", "towerWraith", "raidMob", "spookiness", "enchantedMobs",
}
BLOCK_IMPORTS = {"voidFluid", "voidPortal", "preciseRotation"}
# Rewards of the kept bosses and minibosses that are blocks (heads, paintings).
BLOCK_REWARDS = {"dungeons:wildfire_head", "dungeons:redstone_golem_head", "dungeons:endersent_painting_block",
                 "dungeons:vengeful_painting_block", "dungeons:wildfire_painting_block"}

# RP files always copied (small, used by everything kept).
RP_ALWAYS = ["pack_icon.png", "materials/entity.material", "ui/hud_screen.json", "ui/chat_screen.json",
             "font/glyph_E2.png", "font/glyph_E3.png", "textures/item_texture.json",
             "textures/terrain_texture.json", "textures/flipbook_textures.json", "blocks.json", "sounds.json",
             "sounds/sound_definitions.json"]
TEXTURE_EXTS = (".png", ".tga", ".jpg", ".jpeg")


# --- JSON with comments and trailing commas ------------------------------------
def _strip(text):
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[\]}])", r"\1", "".join(out))


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    try:
        return json.loads(text)
    except ValueError:
        return json.loads(_strip(text))


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


# --- Strings mentioned by a file ------------------------------------------------
_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`([^`]*)`')


def mentions(text):
    """Every string literal of a JSON/JS/mcfunction text, plus its words."""
    found = set()
    for m in _STR.finditer(text):
        s = next(g for g in m.groups() if g is not None)
        for part in re.split(r"\$\{[^}]*\}", s):
            found.add(part)
            found.update(w.strip("/\\") for w in re.split(r"[\s\"'=,(){}\[\]]+", part) if w)
    return found


def mcfunction_words(text):
    return set(re.findall(r"[A-Za-z0-9_:./\-]+", text))


def binary_words(path):
    with open(path, "rb") as f:
        data = f.read()
    return {w.decode() for w in re.findall(rb"[A-Za-z0-9_:./\-]{3,}", data)}


# --- Behaviour pack -------------------------------------------------------------------
class Source:
    def __init__(self, bp, rp):
        self.bp, self.rp = bp, rp
        self.entities = self._index("entities", "minecraft:entity")
        self.items = self._index("items", "minecraft:item")
        self.blocks = self._index("blocks", "minecraft:block")

    def _index(self, folder, key):
        out = {}
        for dirpath, _, files in os.walk(os.path.join(self.bp, folder)):
            for name in files:
                if name.endswith(".json"):
                    path = os.path.join(dirpath, name)
                    ident = load(path)[key]["description"]["identifier"]
                    out[ident] = os.path.relpath(path, self.bp)
        return out

    def bp_path(self, rel):
        return os.path.join(self.bp, rel)


def pick_entities(src):
    keep = set()
    for ident, rel in src.entities.items():
        if rel in ENTITY_SKIP:
            continue
        if rel.startswith("entities/new/boss/"):
            if any(rel.startswith(d) for d in BOSS_DIRS):
                keep.add(ident)
        elif any(rel.startswith(d) for d in ENTITY_DIRS):
            keep.add(ident)
    return keep


def loot_path(src, word):
    """The loot table a word refers to, if any (with or without loot_tables/ and .json)."""
    w = word[len("loot_tables/"):] if word.startswith("loot_tables/") else word
    if not w.endswith(".json"):
        w += ".json"
    rel = "loot_tables/" + w
    return rel if os.path.isfile(src.bp_path(rel)) else None


def function_path(src, word):
    rel = "functions/" + word.strip("/") + ".mcfunction"
    return rel if os.path.isfile(src.bp_path(rel)) else None


class BPClosure:
    """Follows the references between kept entities, loot, functions, structures and scripts."""

    def __init__(self, src, entities):
        self.src = src
        self.entities = set(entities)
        self.loot = set()
        self.equipment_loot = set()
        self.functions = set()
        self.structures = set()
        self.words = set()           # everything mentioned by what is kept
        self.place_words = set()     # mentioned by kept entities, structures and functions
        self.pulled = {}             # entity -> file that pulled it in
        self._done = set()

    def allowed_entity(self, ident):
        rel = self.src.entities.get(ident)
        return (rel and ident.startswith("dungeons:") and not ENTITY_NEVER.match(rel)
                and ident not in UTILITY_NEVER and rel not in ENTITY_SKIP)

    def add_words(self, words, origin):
        self.words |= words
        if origin.startswith(("entities/", "structures/", "functions/")):
            self.place_words |= words
        new = []
        for w in words:
            if w in self.src.entities and w not in self.entities and self.allowed_entity(w):
                self.entities.add(w)
                self.pulled[w] = origin
                new.append(("entity", w))
            if len(w) > 80 or not re.fullmatch(r"[A-Za-z0-9_./:\-]+", w):
                continue
            lp = loot_path(self.src, w)
            if lp and lp not in self.loot:
                self.loot.add(lp)
                new.append(("file", lp))
            fp = function_path(self.src, w)
            if fp and fp not in self.functions:
                self.functions.add(fp)
                new.append(("file", fp))
        return new

    def visit_file(self, rel):
        if rel in self._done:
            return []
        self._done.add(rel)
        path = self.src.bp_path(rel)
        if rel.endswith(".mcstructure"):
            words = binary_words(path)
        elif rel.endswith(".mcfunction"):
            words = mcfunction_words(read(path))
        else:
            text = read(path)
            words = mentions(text)
            if rel.startswith("entities/"):
                data = load(path)
                for comp in _walk_key(data, "minecraft:equipment"):
                    if isinstance(comp, dict) and isinstance(comp.get("table"), str):
                        lp = loot_path(self.src, comp["table"])
                        if lp:
                            self.equipment_loot.add(lp)
        return self.add_words(words, rel)

    def run(self, extra_files):
        queue = [("entity", e) for e in sorted(self.entities)] + [("file", f) for f in extra_files]
        while queue:
            kind, x = queue.pop()
            rel = self.src.entities[x] if kind == "entity" else x
            queue += self.visit_file(rel)


def _walk_key(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from _walk_key(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_key(v, key)


def worldgen_files(src):
    """Jigsaw structures, template pools and processors of the boss structures (no structure_sets)."""
    def index(folder, key):
        out = {}
        for dirpath, _, files in os.walk(src.bp_path("worldgen/" + folder)):
            for name in files:
                path = os.path.join(dirpath, name)
                out[load(path)[key]["description"]["identifier"]] = os.path.relpath(path, src.bp)
        return out
    jigsaws = index("structures", "minecraft:jigsaw")
    pools = index("template_pools", "minecraft:template_pool")
    procs = index("processors", "minecraft:processor_list")
    files, structures = set(), set()
    todo_pools = []
    for sid in BOSS_STRUCTURES:
        rel = jigsaws[sid]
        files.add(rel)
        todo_pools.append(load(src.bp_path(rel))["minecraft:jigsaw"]["start_pool"])
    seen = set()
    while todo_pools:
        pid = todo_pools.pop()
        if pid in seen or pid not in pools:
            continue
        seen.add(pid)
        files.add(pools[pid])
        data = load(src.bp_path(pools[pid]))["minecraft:template_pool"]
        for el in data.get("elements", []):
            e = el.get("element", {})
            loc = e.get("location")
            if loc:
                structures.add("structures/" + loc.replace(":", "/") + ".mcstructure")
            p = e.get("processors")
            if isinstance(p, str) and p in procs:
                files.add(procs[p])
        if data.get("fallback"):
            todo_pools.append(data["fallback"])
    # Jigsaw blocks inside the structures can name more pools.
    for s in list(structures):
        for w in binary_words(src.bp_path(s)):
            if w in pools and w not in seen:
                todo_pools.append(w)
    while todo_pools:
        pid = todo_pools.pop()
        if pid in seen:
            continue
        seen.add(pid)
        files.add(pools[pid])
        for el in load(src.bp_path(pools[pid]))["minecraft:template_pool"].get("elements", []):
            loc = el.get("element", {}).get("location")
            if loc:
                structures.add("structures/" + loc.replace(":", "/") + ".mcstructure")
    missing = [s for s in structures if not os.path.isfile(src.bp_path(s))]
    if missing:
        sys.exit("Faltan estructuras: %s" % missing)
    return files, structures


def pick_items(src, closure):
    keep, gear = set(), set()
    used = closure.words
    for ident, rel in src.items.items():
        if any(rel == p or rel.startswith(p) for p in ITEM_ALWAYS):
            keep.add(ident)
        elif ident in used and any(rel.startswith(p) for p in ITEM_IF_USED):
            keep.add(ident)
    for lp in closure.equipment_loot:
        for w in mentions(read(src.bp_path(lp))):
            rel = src.items.get(w)
            if rel and rel.startswith(GEAR_DIR):
                keep.add(w)
                gear.add(w)
    return keep, gear


def filter_loot(data, items, loot_files):
    """Removes entries for items/tables that are not in the pack, and pools left empty."""
    def ok(entry):
        if entry.get("type") == "item":
            name = entry.get("name", "")
            return not name.startswith("dungeons:") or name in items
        if entry.get("type") == "loot_table":
            name = entry.get("name", "")
            return ("loot_tables/" + name.removeprefix("loot_tables/").removesuffix(".json") + ".json") in loot_files
        return True
    pools = []
    for pool in data.get("pools", []):
        entries = [e for e in pool.get("entries", []) if ok(e)]
        for e in entries:
            if "pools" in e:
                e.update(filter_loot(e, items, loot_files))
        if entries:
            pools.append(dict(pool, entries=entries))
    return dict(data, pools=pools)


def strip_gear(data):
    comps = data["minecraft:item"]["components"]
    for k in [k for k in comps if not k.startswith("minecraft:")]:
        del comps[k]
    comps.pop("minecraft:custom_components", None)
    return data


def recipe_ok(data, items):
    text = json.dumps(data)
    refs = set(re.findall(r'"(dungeons:[a-z0-9_]+)"', text))
    return all(r in items for r in refs) and refs & items


def filter_catalog(data, items):
    for cat in data["minecraft:crafting_items_catalog"]["categories"]:
        groups = []
        for g in cat.get("groups", []):
            def name(i):
                return i if isinstance(i, str) else i.get("name", "")
            g["items"] = [i for i in g.get("items", []) if name(i) in items or not name(i).startswith("dungeons:")]
            icon = g.get("group_identifier", {}).get("icon")
            if g["items"]:
                if icon and icon not in items and icon.startswith("dungeons:"):
                    g["group_identifier"]["icon"] = g["items"][0] if isinstance(g["items"][0], str) else icon
                groups.append(g)
        cat["groups"] = groups
    return data


# --- Scripts ---------------------------------------------------------------------
_IMPORT = re.compile(r'''^\s*import\s+(?:[^'";]*?\s+from\s+)?['"]([^'"]+)['"];?\s*$''', re.M)


def script_closure(scripts_dir, start_texts):
    """Files reached from the patched entry points."""
    seen, todo = set(), []
    for rel, text in start_texts.items():
        seen.add(rel)
        todo.append((rel, text))
    while todo:
        rel, text = todo.pop()
        for m in _IMPORT.findall(text):
            if m.startswith("@minecraft"):
                continue
            dep = os.path.normpath(os.path.join(os.path.dirname(rel), m) if m.startswith(".") else m)
            if not dep.endswith(".js"):
                dep += ".js"
            if dep not in seen:
                seen.add(dep)
                todo.append((dep, read(os.path.join(scripts_dir, dep))))
    return seen


def keep_imports(text, keep, key):
    def repl(m):
        return m.group(0) if key(m.group(1)) in keep else ""
    return re.sub(r'^import\s+"([^"]+)";?[ \t\r]*(?:\n|$)', repl, text, flags=re.M)


def patch_scripts(scripts_dir):
    main = read(os.path.join(scripts_dir, "main.js"))
    main = keep_imports(main, MAIN_IMPORTS, lambda p: p)
    behaviour = read(os.path.join(scripts_dir, "misc/entityBehaviour.js"))
    behaviour = keep_imports(behaviour, BEHAVIOUR_IMPORTS, lambda p: os.path.basename(p)[:-3])
    blocks = read(os.path.join(scripts_dir, "components/blocks.js"))
    blocks = keep_imports(blocks, BLOCK_IMPORTS, lambda p: os.path.basename(p)[:-3])
    return {"main.js": main, "misc/entityBehaviour.js": behaviour, "components/blocks.js": blocks}


# --- Resource pack ------------------------------------------------------------------
class RPIndex:
    def __init__(self, rp):
        self.rp = rp
        self.defs = {}       # identifier -> file (geometry, animations, controllers, particles)
        self.client = {}     # entity identifier -> [files]
        self.attach = {}     # item identifier -> [files]
        for dirpath, _, files in os.walk(rp):
            for name in files:
                if not name.endswith(".json"):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, rp)
                top = rel.split(os.sep)[0]
                if top in ("models", "animations", "animation_controllers", "render_controllers", "particles"):
                    try:
                        data = load(path)
                    except ValueError:
                        continue
                    for ident in _definitions(data):
                        self.defs.setdefault(ident, set()).add(rel)
                elif top == "entity":
                    d = load(path)
                    ident = d.get("minecraft:client_entity", {}).get("description", {}).get("identifier")
                    if ident:
                        self.client.setdefault(ident, []).append(rel)
                elif top == "attachables":
                    d = load(path)
                    ident = d.get("minecraft:attachable", {}).get("description", {}).get("identifier")
                    if ident:
                        self.attach.setdefault(ident, []).append(rel)


def _definitions(data):
    ids = []
    for key in ("animations", "animation_controllers", "render_controllers"):
        if isinstance(data.get(key), dict):
            ids += list(data[key])
    if "particle_effect" in data:
        ids.append(data["particle_effect"]["description"]["identifier"])
    for g in data.get("minecraft:geometry", []):
        ids.append(g.get("description", {}).get("identifier"))
    for k in data:
        if k.startswith("geometry."):
            ids.append(k.split(":")[0])
    return [i for i in ids if i]


def rp_closure(rpi, start_files, seed_words):
    """Adds every RP definition (model, animation, controller, particle) and
    texture that a kept file mentions, until nothing new appears."""
    files, todo = set(), list(start_files)
    words = set()

    def take(new):
        for w in new - words:
            for f in rpi.defs.get(w.split(":")[0] if w.startswith("geometry.") else w, ()):
                todo.append(f)
            if w.startswith("textures/"):
                files.update(texture_files(rpi.rp, w))
                if w.endswith(TEXTURE_EXTS) and os.path.isfile(os.path.join(rpi.rp, w)):
                    files.add(w)
        words.update(new)

    take(set(seed_words))
    while todo:
        rel = todo.pop()
        if rel in files:
            continue
        files.add(rel)
        if rel.endswith(".json"):
            take(mentions(read(os.path.join(rpi.rp, rel))))
    return files, words


def texture_files(rp, path):
    out = []
    for ext in TEXTURE_EXTS:
        if os.path.isfile(os.path.join(rp, path + ext)):
            out.append(path + ext)
    return out


# --- Build -------------------------------------------------------------------------
def copy(src_root, dst_root, rel):
    s, d = os.path.join(src_root, rel), os.path.join(dst_root, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copyfile(s, d)


def find_packs(src):
    bp = rp = None
    for dirpath, _, files in os.walk(src):
        if "manifest.json" in files:
            types = {m["type"] for m in load(os.path.join(dirpath, "manifest.json"))["modules"]}
            if "resources" in types:
                rp = dirpath
            elif "data" in types:
                bp = dirpath
    if not bp or not rp:
        sys.exit("No se encontraron los packs BP y RP en " + src)
    return bp, rp


def manifests(src_bp, src_rp):
    obp, orp = load(os.path.join(src_bp, "manifest.json")), load(os.path.join(src_rp, "manifest.json"))
    deps = [d for d in obp["dependencies"] if "module_name" in d]
    # format_version 3 only takes versions as "x.y.z" strings: with lists
    # Minecraft rejects the behaviour pack ("invalid string") on import.
    v = ".".join(map(str, VERSION))
    bp = {
        "format_version": 3,
        "header": {"name": NAME, "description": "Enemigos, minijefes, 3 jefes y armaduras de Alylica's Dungeons "
                   "(uso personal).", "uuid": UUIDS["bp"], "version": v,
                   "min_engine_version": obp["header"]["min_engine_version"]},
        "modules": [{"type": "data", "uuid": UUIDS["bp_data"], "version": v},
                    {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": v,
                     "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": v}] + deps,
        "metadata": {"product_type": "addon"},
    }
    rp = {
        "format_version": 2,
        "header": {"name": NAME, "description": "Recursos de Dungeons Mobs (uso personal).", "uuid": UUIDS["rp"],
                   "version": VERSION, "min_engine_version": orp["header"]["min_engine_version"]},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def build(src_dir):
    src_bp, src_rp = find_packs(src_dir)
    src = Source(src_bp, src_rp)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)

    # Scripts first: what they mention is part of the closure.
    scripts_dir = os.path.join(src_bp, "scripts")
    patched = patch_scripts(scripts_dir)
    script_files = script_closure(scripts_dir, patched)
    script_words = set()
    for rel in script_files:
        script_words |= mentions(patched.get(rel) or read(os.path.join(scripts_dir, rel)))

    wg_files, structures = worldgen_files(src)
    closure = BPClosure(src, pick_entities(src))
    closure.add_words(script_words, "scripts")
    closure.functions.add("functions/stun_cd.mcfunction")
    closure.run(sorted(structures) + sorted(closure.functions) + sorted(closure.loot))
    items, gear = pick_items(src, closure)

    # BP animations referenced by the kept entities.
    bp_anim = {}
    for folder, key in (("animations", "animations"), ("animation_controllers", "animation_controllers")):
        for dirpath, _, files in os.walk(src.bp_path(folder)):
            for name in files:
                path = os.path.join(dirpath, name)
                for ident in load(path).get(key, {}):
                    bp_anim.setdefault(ident, set()).add(os.path.relpath(path, src_bp))
    bp_anim_files = {f for w in closure.words if w in bp_anim for f in bp_anim[w]}

    # Blocks placed by the structures, or dropped/placed by the kept mobs (not
    # every block a script mentions: those belong to features left out).
    blocks = {b for b in src.blocks if b in closure.place_words or (b in BLOCK_REWARDS and b in closure.words)}

    # --- write BP
    for ident in sorted(closure.entities):
        copy(src_bp, BP, src.entities[ident])
    for ident in sorted(items):
        rel = src.items[ident]
        if ident in gear:
            dump(os.path.join(BP, rel), strip_gear(load(src.bp_path(rel))))
        else:
            copy(src_bp, BP, rel)
    for ident in sorted(blocks):
        copy(src_bp, BP, src.blocks[ident])
    for rel in sorted(closure.loot):
        dump(os.path.join(BP, rel), filter_loot(load(src.bp_path(rel)), items | blocks, closure.loot))
    for rel in sorted(closure.functions | bp_anim_files | wg_files | structures):
        copy(src_bp, BP, rel)
    copy(src_bp, BP, "functions/tick.json")
    for dirpath, _, files in os.walk(src.bp_path("spawn_rules")):
        for name in files:
            path = os.path.join(dirpath, name)
            if load(path)["minecraft:spawn_rules"]["description"]["identifier"] in closure.entities:
                copy(src_bp, BP, os.path.relpath(path, src_bp))
    # Only armour recipes: the weapons and arrows are here because mobs carry them.
    for dirpath, _, files in os.walk(src.bp_path("recipes/armor")):
        for name in files:
            path = os.path.join(dirpath, name)
            if recipe_ok(load(path), items):
                copy(src_bp, BP, os.path.relpath(path, src_bp))
    dump(os.path.join(BP, "item_catalog/crafting_item_catalog.json"),
         filter_catalog(load(src.bp_path("item_catalog/crafting_item_catalog.json")), items))
    for rel in sorted(script_files):
        dst = os.path.join(BP, "scripts", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in patched:
            with open(dst, "w", encoding="utf-8", newline="\n") as f:
                f.write(patched[rel])
        else:
            shutil.copyfile(os.path.join(scripts_dir, rel), dst)
    copy(src_bp, BP, "pack_icon.png")
    bp_manifest, rp_manifest = manifests(src_bp, src_rp)
    dump(os.path.join(BP, "manifest.json"), bp_manifest)

    # --- RP
    rpi = RPIndex(src_rp)
    start = set(RP_ALWAYS)
    for ident in closure.entities:
        start.update(rpi.client.get(ident, []))
    for ident in items:
        start.update(rpi.attach.get(ident, []))
    start = {f for f in start if os.path.isfile(os.path.join(src_rp, f))}
    bp_words = set(closure.words)
    for root, _, files in os.walk(BP):
        for name in files:
            if name.endswith((".json", ".js", ".mcfunction")):
                bp_words |= mentions(read(os.path.join(root, name)))
    rp_files, words = rp_closure(rpi, start - {"textures/item_texture.json", "textures/terrain_texture.json",
                                                "textures/flipbook_textures.json", "sounds/sound_definitions.json",
                                                "sounds.json", "blocks.json"}, bp_words)
    rp_files |= start
    # Texture atlases: keep the entries that something kept mentions.
    atlas_textures = set()
    for rel, key in (("textures/item_texture.json", "texture_data"), ("textures/terrain_texture.json", "texture_data")):
        data = load(os.path.join(src_rp, rel))
        data[key] = {k: v for k, v in data[key].items() if k in words}
        for v in data[key].values():
            for t in _walk_strings(v):
                atlas_textures.update(texture_files(src_rp, t))
        dump(os.path.join(RP, rel), data)
    flip = [f for f in load(os.path.join(src_rp, "textures/flipbook_textures.json")) if f.get("atlas_tile") in words]
    for f in flip:
        atlas_textures.update(texture_files(src_rp, f["flipbook_texture"]))
    dump(os.path.join(RP, "textures/flipbook_textures.json"), flip)
    blocks_json = load(os.path.join(src_rp, "blocks.json"))
    blocks_json = {k: v for k, v in blocks_json.items() if k == "format_version" or k in blocks}
    dump(os.path.join(RP, "blocks.json"), blocks_json)
    # Sounds: entity events of kept entities/blocks, and every definition mentioned.
    sounds = load(os.path.join(src_rp, "sounds.json"))
    ent = sounds.get("entity_sounds", {}).get("entities", {})
    sounds.setdefault("entity_sounds", {})["entities"] = {k: v for k, v in ent.items()
                                                          if k in closure.entities or not k.startswith("dungeons:")}
    if "block_sounds" in sounds:
        sounds["block_sounds"] = {k: v for k, v in sounds["block_sounds"].items() if k in blocks or ":" not in k}
    dump(os.path.join(RP, "sounds.json"), sounds)
    sound_words = words | mentions(json.dumps(sounds))
    defs = load(os.path.join(src_rp, "sounds/sound_definitions.json"))
    sd = defs.get("sound_definitions", defs)
    kept_defs = {k: v for k, v in sd.items() if k in sound_words}
    if "sound_definitions" in defs:
        defs["sound_definitions"] = kept_defs
    else:
        defs = kept_defs
    dump(os.path.join(RP, "sounds/sound_definitions.json"), defs)
    sound_files = set()
    for v in kept_defs.values():
        for s in v.get("sounds", []):
            name = s if isinstance(s, str) else s.get("name", "")
            for ext in (".ogg", ".fsb", ".wav", ".mp3"):
                if os.path.isfile(os.path.join(src_rp, name + ext)):
                    sound_files.add(name + ext)
    skip = {"textures/item_texture.json", "textures/terrain_texture.json", "textures/flipbook_textures.json",
            "blocks.json", "sounds.json", "sounds/sound_definitions.json"}
    for rel in sorted((rp_files - skip) | atlas_textures | sound_files):
        copy(src_rp, RP, rel)
    for name in os.listdir(os.path.join(src_rp, "texts")):
        copy(src_rp, RP, "texts/" + name)
    dump(os.path.join(RP, "manifest.json"), rp_manifest)

    compress_sounds()
    minify_json()
    write_mcaddon()
    report(closure, items, gear, blocks, structures)


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def compress_sounds():
    """Mono Vorbis q5 for mob sounds; music keeps its two channels."""
    if not shutil.which("ffmpeg"):
        print("Aviso: sin ffmpeg los sonidos se copian sin comprimir.")
        return
    for dirpath, _, files in os.walk(os.path.join(RP, "sounds")):
        for name in files:
            if not name.endswith(".ogg"):
                continue
            path = os.path.join(dirpath, name)
            music = "music" in path.lower()
            tmp = path + ".tmp.ogg"
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", path, "-map_metadata", "-1"]
            cmd += [] if music else ["-ac", "1"]
            cmd += ["-c:a", "libvorbis", "-q:a", "5", "-fflags", "+bitexact", "-flags:a", "+bitexact", tmp]
            if subprocess.run(cmd).returncode == 0 and os.path.getsize(tmp) < os.path.getsize(path):
                os.replace(tmp, path)
            elif os.path.exists(tmp):
                os.remove(tmp)


def minify_json():
    for pack in (BP, RP):
        for dirpath, _, files in os.walk(pack):
            for name in files:
                if name.endswith(".json"):
                    path = os.path.join(dirpath, name)
                    try:
                        dump(path, load(path))
                    except ValueError:
                        pass


def write_mcaddon():
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, files in os.walk(pack):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, OUT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)


def report(closure, items, gear, blocks, structures):
    def count(pack):
        return sum(len(f) for _, _, f in os.walk(pack))
    print(f"Entidades: {len(closure.entities)}  Objetos: {len(items)} (armas de mobs: {len(gear)})  "
          f"Bloques: {len(blocks)}  Estructuras: {len(structures)}  Botín: {len(closure.loot)}")
    print(f"Archivos BP: {count(BP)}  RP: {count(RP)}  .mcaddon: {os.path.getsize(MCADDON) / 1e6:.1f} MB")
    print("Añadidas por referencias:")
    for e, origin in sorted(closure.pulled.items()):
        print(f"  {e}  <- {origin}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    src = sys.argv[1]
    if os.path.isdir(src):
        build(src)
        return
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        build(tmp)


if __name__ == "__main__":
    main()
