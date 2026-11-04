"""Fixes and lightens Netherens V4, and turns its boss into a fortress fight.
Personal use: output in the git-ignored private/ folder.

    python3 tools/netherens_fix.py path/to/Netherens_V4.zip

Errors fixed:
  * the RP module reused the BP's UUID (Minecraft can reject the pair);
  * the boss loops listed the End's bosses inside a getEntities() call by
    mistake (spread in the wrong parenthesis): rewritten with getBosses();
  * the skull function ran "scoreboard objectives add" every tick;
  * the wolf fired 'low:equip_armor', an event it does not have;
  * the boss's death animation played sound effects ('magic') it does not define;
  * short sound effects were in the 'record' category and streamed;
  * client entities with no behaviour entity (NPCs, 20 portals, ghosts,
    DJ ghast, second phase) and every asset only they used.
Changes asked for:
  * the Trapped Soul Energy item is gone (item, drops and script);
  * the Soul Fortress (tools/netherens/fortress.py) generates only in soul
    sand valleys; its Soul Altar starts the fight with a Wither Skeleton Skull;
  * the Nether Lord has 3600 health (was 1350): a fight for three players.
Lighter: sounds re-encoded (music stays stereo), JSON minified, PNG optimised.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "netherens"))
import fortress  # noqa: E402
from dungeons_mobs import load, dump, mentions, RPIndex, rp_closure, texture_files  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "Netherens_BP")
RP = os.path.join(OUT, "Netherens_RP")
MCADDON = os.path.join(OUT, "Netherens.mcaddon")
VERSION = [1, 2, 0]
NEW_RP_MODULE_UUID = "3b1f6a52-8c4d-4e9a-b7f2-6d0c5e8a9f13"
BOSS_HEALTH = 3600
UNUSED_CLIENT = ["low:npc", "low:nb_npc", "low:lord_ghost", "low:scarred_ghast", "low:secondphase"]
MISSING_SOUND_EFFECTS = {"magic": "mob.evocation_illager.cast_spell", "death": "netherboss.death"}


def find_packs(src):
    bp = rp = None
    for dirpath, _, files in os.walk(src):
        for f in files:
            if f.endswith(".mcpack"):
                d = os.path.join(dirpath, f[:-7])
                with zipfile.ZipFile(os.path.join(dirpath, f)) as z:
                    z.extractall(d)
    for dirpath, _, files in os.walk(src):
        if "manifest.json" in files:
            types = {m["type"] for m in load(os.path.join(dirpath, "manifest.json"))["modules"]}
            if "resources" in types:
                rp = dirpath
            elif "data" in types:
                bp = dirpath
    if not bp or not rp:
        sys.exit("No se encontraron los packs de Netherens en " + src)
    return bp, rp


def edit(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def replace_once(text, old, new, where):
    if text.count(old) != 1:
        sys.exit(f"{where}: no se encontró el texto a cambiar ({old[:50]!r})")
    return text.replace(old, new)


# --- manifests ------------------------------------------------------------------
def fix_manifests():
    def bp(m):
        m["header"]["version"] = VERSION
        m["header"]["min_engine_version"] = [1, 21, 90]  # data-driven structures
        m["header"]["description"] = "Nether Mobs expanded - 1.2.0 (corregido, Fortaleza de Almas)"
        for mod in m["modules"]:
            mod["version"] = VERSION
        for d in m["dependencies"]:
            if "uuid" in d:
                d["version"] = VERSION
    edit(os.path.join(BP, "manifest.json"), bp)
    bp_uuid = load(os.path.join(BP, "manifest.json"))["header"]["uuid"]

    def rp(m):
        m["header"]["version"] = VERSION
        m["header"]["min_engine_version"] = [1, 21, 90]
        for mod in m["modules"]:
            mod["version"] = VERSION
            if mod["uuid"] == bp_uuid:
                mod["uuid"] = NEW_RP_MODULE_UUID
        m["dependencies"] = [{"uuid": bp_uuid, "version": VERSION}]
    edit(os.path.join(RP, "manifest.json"), rp)


# --- behaviour pack ---------------------------------------------------------------
GET_BOSSES = '''function getBosses() {
  const out = []
  for (const id of ["overworld", "nether", "the_end"]) {
    try {
      out.push(...world.getDimension(id).getEntities({ type: "low:netherboss" }))
    } catch { }
  }
  return out
}

'''


def fix_scripts():
    path = os.path.join(BP, "scripts", "index.js")
    t = read(path)
    # The End's bosses were passed as extra arguments of the Nether's getEntities().
    buggy = re.compile(r"const bosses = \[\s*\.\.\.world\.getDimension\(\"overworld\"\)[^\]]*?\.\.\.world\.getDimension\(\"the_end\"\)"
                       r"\.getEntities\(\{ type: \"low:netherboss\" \}\)\)\s*\]")
    t, n = buggy.subn("const bosses = getBosses()", t)
    if n != 3:
        sys.exit(f"index.js: esperaba 3 listas de jefes, encontré {n}")
    t = replace_once(t, "function getRandomOffset(", GET_BOSSES + "function getRandomOffset(", "index.js")
    # Trapped Soul Energy: its use (summons the boss) and its drop from the nether mobs.
    start = t.index('world.afterEvents.itemUse.subscribe((event) => {\n  if (event.itemStack?.typeId !== "codegeek:soul_energy")')
    end = t.index('world.afterEvents.entityDie.subscribe((event) => {\n  if (event.deadEntity.typeId !== "low:netherboss")')
    t = t[:start] + t[end:]
    start = t.index('world.afterEvents.entityDie.subscribe((event) => {\n  if (["low:withie"')
    end = t.index("world.afterEvents.dataDrivenEntityTrigger.subscribe((event) => {\n  if (event.eventId === \"minecraft:on_tame\"")
    t = t[:start] + t[end:]
    if "soul_energy" in t:
        sys.exit("index.js: quedan referencias a soul_energy")
    # The skull scores need the objective (created once by soul_altar.js).
    t = replace_once(t, '      world.scoreboard.getObjective("NetherBossDistance").setScore(',
                     '      world.scoreboard.getObjective("NetherBossDistance")?.setScore(', "index.js")
    t = "import './soul_altar.js';\n" + t
    write(path, t)
    shutil.copyfile(os.path.join(HERE, "netherens", "soul_altar.js"), os.path.join(BP, "scripts", "soul_altar.js"))
    fpath = os.path.join(BP, "functions", "netherBossSkullTracking.mcfunction")
    lines = [l for l in read(fpath).splitlines() if not l.startswith("scoreboard objectives add")]
    write(fpath, "\n".join(lines) + "\n")


def remove_soul_energy():
    os.remove(os.path.join(BP, "items", "soul_energy.json"))
    edit(os.path.join(RP, "textures", "item_texture.json"), lambda d: d["texture_data"].pop("soul_energy", None))


def fix_wolf():
    def f(d):
        events = d["minecraft:entity"]["events"]
        events.setdefault("low:equip_armor", {})  # the interaction fired it; nothing to add
    edit(os.path.join(BP, "entities", "custom_wolf.json"), f)


def fix_boss():
    def f(d):
        c = d["minecraft:entity"]["components"]
        c["minecraft:health"] = {"value": BOSS_HEALTH, "max": BOSS_HEALTH}
        c["minecraft:boss"]["name"] = "§4Nether Lord"
    edit(os.path.join(BP, "entities", "netherboss.behavior.json"), f)


def add_altar_block():
    dump(os.path.join(BP, "blocks", "soul_altar.json"), {
        "format_version": "1.21.40",
        "minecraft:block": {
            "description": {"identifier": "netherens:soul_altar", "menu_category": {"category": "construction"},
                            "states": {"netherens:lit": [False, True]}},
            "components": {
                "minecraft:geometry": "geometry.netherens.soul_altar",
                "minecraft:material_instances": {
                    "*": {"texture": "netherens_altar_side", "render_method": "opaque"},
                    "top": {"texture": "netherens_altar_top", "render_method": "opaque"}},
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 40},
                "minecraft:destructible_by_explosion": False,
                "minecraft:light_emission": 4,
                "minecraft:map_color": "#1b3d47",
                "minecraft:display_name": "tile.netherens:soul_altar.name"},
            "permutations": [{
                "condition": "q.block_state('netherens:lit')",
                "components": {
                    "minecraft:light_emission": 14,
                    "minecraft:material_instances": {
                        "*": {"texture": "netherens_altar_side_lit", "render_method": "opaque"},
                        "top": {"texture": "netherens_altar_top_lit", "render_method": "opaque"}}}}]}})

    def face(u, v, w, h, mat=None):
        f = {"uv": [u, v], "uv_size": [w, h]}
        if mat:
            f["material_instance"] = mat
        return f

    def cube(origin, size, top_mat=None):
        x, y, z = size
        side = 16 - y
        return {"origin": origin, "size": size, "uv": {
            "north": face((16 - x) // 2, side - y if side - y >= 0 else 0, x, y),
            "south": face((16 - x) // 2, max(side - y, 0), x, y),
            "east": face((16 - z) // 2, max(side - y, 0), z, y),
            "west": face((16 - z) // 2, max(side - y, 0), z, y),
            "up": face((16 - x) // 2, (16 - z) // 2, x, z, top_mat),
            "down": face((16 - x) // 2, (16 - z) // 2, x, z)}}
    dump(os.path.join(RP, "models", "blocks", "soul_altar.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.netherens.soul_altar", "texture_width": 16,
                            "texture_height": 16, "visible_bounds_width": 2, "visible_bounds_height": 2,
                            "visible_bounds_offset": [0, 0.5, 0]},
            "bones": [{"name": "altar", "pivot": [0, 0, 0], "cubes": [
                cube([-8, 0, -8], [16, 4, 16]),
                cube([-5, 4, -5], [10, 8, 10]),
                cube([-7, 12, -7], [14, 4, 14], "top")]}]}]})
    altar_textures(os.path.join(RP, "textures", "blocks"))
    tt = os.path.join(RP, "textures", "terrain_texture.json")
    dump(tt, {"resource_pack_name": "netherens", "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4,
              "texture_data": {k: {"textures": f"textures/blocks/{k}"} for k in
                               ("netherens_altar_side", "netherens_altar_top", "netherens_altar_side_lit",
                                "netherens_altar_top_lit")}})
    dump(os.path.join(RP, "blocks.json"), {"format_version": "1.21.40", "netherens:soul_altar": {"sound": "stone"}})


def altar_textures(folder):
    """16x16 textures drawn here: dark blackstone with soul runes."""
    from PIL import Image
    import random
    os.makedirs(folder, exist_ok=True)
    rng = random.Random(4)

    def stone():
        img = Image.new("RGBA", (16, 16))
        for x in range(16):
            for y in range(16):
                v = 34 + rng.randint(-6, 6)
                if y % 4 == 0 or (x + (y // 4) * 4) % 8 == 0:
                    v -= 10  # brick joints
                img.putpixel((x, y), (v, v - 4, v + 4, 255))
        return img
    rune = (70, 190, 210, 255)
    rune_lit = (150, 245, 255, 255)
    glyph = [(3, 6), (4, 5), (5, 6), (4, 7), (4, 8), (4, 9), (10, 6), (11, 5), (12, 6), (11, 7), (11, 8),
             (11, 9), (7, 10), (8, 10), (7, 11), (8, 11), (6, 12), (9, 12)]
    for lit in (False, True):
        side = stone()
        for p in glyph:
            side.putpixel(p, rune_lit if lit else rune)
        side.save(os.path.join(folder, "netherens_altar_side" + ("_lit" if lit else "") + ".png"))
        top = stone()
        for x in range(16):
            for y in range(16):
                d = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5
                if 5.2 < d < 6.3 or d < 1.6:
                    top.putpixel((x, y), rune_lit if lit else rune)
                elif lit and d < 5.2:
                    r, g, b, a = top.getpixel((x, y))
                    top.putpixel((x, y), (r, min(255, g + 40), min(255, b + 60), 255))
        for a in range(0, 360, 45):
            import math
            x = round(7.5 + 3.4 * math.cos(math.radians(a)))
            y = round(7.5 + 3.4 * math.sin(math.radians(a)))
            top.putpixel((x, y), rune_lit if lit else rune)
        top.save(os.path.join(folder, "netherens_altar_top" + ("_lit" if lit else "") + ".png"))


def add_fortress():
    os.makedirs(os.path.join(BP, "structures", "netherens"), exist_ok=True)
    fortress.build().save(os.path.join(BP, "structures", "netherens", "soul_fortress.mcstructure"))
    wg = os.path.join(BP, "worldgen")
    dump(os.path.join(wg, "processors", "soul_fortress.json"), {
        "format_version": "1.21.20",
        "minecraft:processor_list": {"description": {"identifier": "netherens:soul_fortress"}, "processors": []}})
    dump(os.path.join(wg, "template_pools", "soul_fortress.json"), {
        "format_version": "1.21.20",
        "minecraft:template_pool": {"description": {"identifier": "netherens:soul_fortress"}, "elements": [{
            "element": {"element_type": "minecraft:single_pool_element", "location": "netherens/soul_fortress",
                        "processors": "netherens:soul_fortress"}, "weight": 1}]}})
    # In the Nether the surface heightmap is the bedrock roof (~128): a negative
    # offset puts the base near the valley floor (keep floor ~ y 34).
    dump(os.path.join(wg, "structures", "soul_fortress.json"), {
        "format_version": "1.21.20",
        "minecraft:jigsaw": {
            "description": {"identifier": "netherens:soul_fortress"},
            "biome_filters": [{"test": "has_biome_tag", "operator": "==", "value": "soulsand_valley"}],
            "heightmap_projection": "world_surface",
            "max_depth": 1,
            "start_height": {"type": "constant", "value": {"absolute": -104}},
            "start_pool": "netherens:soul_fortress",
            "step": "surface_structures",
            "terrain_adaptation": "none"}})
    dump(os.path.join(wg, "structure_sets", "soul_fortress.json"), {
        "format_version": "1.21.20",
        "minecraft:structure_set": {
            "description": {"identifier": "netherens:soul_fortress"},
            "placement": {"type": "minecraft:random_spread", "salt": 61432907, "separation": 8, "spacing": 22},
            "structures": [{"structure": "netherens:soul_fortress", "weight": 1}]}})
    dump(os.path.join(BP, "loot_tables", "netherens", "chests", "soul_fortress.json"), {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:wither_skeleton_skull", "weight": 1},
                                 {"type": "empty", "weight": 2}]},
        {"rolls": {"min": 3, "max": 6}, "entries": [
            {"type": "item", "name": "minecraft:gold_ingot", "weight": 15,
             "functions": [{"function": "set_count", "count": {"min": 2, "max": 6}}]},
            {"type": "item", "name": "minecraft:quartz", "weight": 15,
             "functions": [{"function": "set_count", "count": {"min": 4, "max": 12}}]},
            {"type": "item", "name": "minecraft:soul_lantern", "weight": 10,
             "functions": [{"function": "set_count", "count": {"min": 1, "max": 3}}]},
            {"type": "item", "name": "minecraft:blaze_rod", "weight": 10,
             "functions": [{"function": "set_count", "count": {"min": 1, "max": 3}}]},
            {"type": "item", "name": "minecraft:nether_wart", "weight": 10,
             "functions": [{"function": "set_count", "count": {"min": 2, "max": 6}}]},
            {"type": "item", "name": "minecraft:diamond", "weight": 4},
            {"type": "item", "name": "minecraft:netherite_scrap", "weight": 2},
            {"type": "item", "name": "minecraft:golden_apple", "weight": 3}]}]})
    write(os.path.join(BP, "functions", "netherens", "soul_fortress.mcfunction"),
          "# Soul Fortress by hand: the keep floor ends up at your feet, the altar where you stand.\n"
          f"structure load netherens:soul_fortress ~-{fortress.C} ~-{fortress.FLOOR} ~-{fortress.C}\n")


def fix_lang():
    path = os.path.join(RP, "texts", "en_US.lang")
    lines = read(path).splitlines()
    drop = tuple(f"entity.{e}.name" for e in UNUSED_CLIENT) + tuple(
        f"item.spawn_egg.entity.{e}.name" for e in UNUSED_CLIENT)
    out = []
    for line in lines:
        key = line.split("=", 1)[0]
        if key in drop:
            continue
        if key == "entity.low:netherboss.name":
            line = "entity.low:netherboss.name=Nether Lord"
        if key == "item.spawn_egg.entity.low:netherboss.name":
            line = "item.spawn_egg.entity.low:netherboss.name=Spawn Nether Lord"
        out.append(line)
    out.append("tile.netherens:soul_altar.name=Soul Altar")
    write(path, "\n".join(out) + "\n")
    es = [l for l in out]
    es = [re.sub(r"^(tile\.netherens:soul_altar\.name)=.*", r"\1=Altar de Almas", l) for l in es]
    es = [re.sub(r"^(entity\.low:netherboss\.name)=.*", r"\1=Señor del Nether", l) for l in es]
    for code in ("es_ES", "es_MX"):
        write(os.path.join(RP, "texts", f"{code}.lang"), "\n".join(es) + "\n")
    dump(os.path.join(RP, "texts", "languages.json"), ["en_US", "es_ES", "es_MX"])


# --- resource pack ------------------------------------------------------------------
def remove_unused_clients():
    for dirpath, _, files in os.walk(os.path.join(RP, "entity")):
        for name in files:
            path = os.path.join(dirpath, name)
            ident = load(path).get("minecraft:client_entity", {}).get("description", {}).get("identifier", "")
            if ident in UNUSED_CLIENT or ident.startswith("codegeek:portal"):
                os.remove(path)
    portals = os.path.join(RP, "entity", "portals")
    if os.path.isdir(portals) and not os.listdir(portals):
        os.rmdir(portals)


def fix_sound_effects():
    """Client entities whose animations play sound effects they never define."""
    rpi = RPIndex(RP)
    for ident, files in rpi.client.items():
        for rel in files:
            path = os.path.join(RP, rel)
            data = load(path)
            desc = data["minecraft:client_entity"]["description"]
            effects = desc.setdefault("sound_effects", {})
            changed = False
            for anim in (desc.get("animations") or {}).values():
                for f in rpi.defs.get(anim, ()):
                    a = load(os.path.join(RP, f)).get("animations", {}).get(anim, {})
                    for frame in (a.get("sound_effects") or {}).values():
                        for e in frame if isinstance(frame, list) else [frame]:
                            name = e.get("effect")
                            if name and name not in effects and name in MISSING_SOUND_EFFECTS:
                                effects[name] = MISSING_SOUND_EFFECTS[name]
                                changed = True
            if changed:
                dump(path, data)


def fix_sound_definitions():
    def f(d):
        defs = d.get("sound_definitions", d)
        for name, v in defs.items():
            if name.startswith("music."):
                continue  # boss music: streamed, music slider
            if v.get("category") in ("record", "music"):
                v["category"] = "hostile"
            for s in v.get("sounds", []):
                if isinstance(s, dict):
                    s["stream"] = False
    edit(os.path.join(RP, "sounds", "sound_definitions.json"), f)


def prune_rp():
    """Deletes models, animations, controllers, particles, textures and sounds
    that nothing in the packs mentions any more."""
    rpi = RPIndex(RP)
    bp_words = set()
    for dirpath, _, files in os.walk(BP):
        for name in files:
            if name.endswith((".json", ".js", ".mcfunction")):
                bp_words |= mentions(read(os.path.join(dirpath, name)))
    start = []
    for dirpath, _, files in os.walk(RP):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), RP)
            top = rel.split(os.sep)[0]
            if top in ("entity", "attachables", "ui", "texts") or rel in ("sounds.json", "blocks.json"):
                start.append(rel)
            if rel in ("textures/item_texture.json", "textures/terrain_texture.json"):
                start.append(rel)
    keep, words = rp_closure(rpi, start, bp_words)
    defs = load(os.path.join(RP, "sounds", "sound_definitions.json"))
    sd = defs.get("sound_definitions", defs)
    kept = {k: v for k, v in sd.items() if k in words}
    if "sound_definitions" in defs:
        defs["sound_definitions"] = kept
    else:
        defs = kept
    dump(os.path.join(RP, "sounds", "sound_definitions.json"), defs)
    for v in kept.values():
        for s in v.get("sounds", []):
            n = s if isinstance(s, str) else s.get("name", "")
            keep.add(n + ".ogg")
    removed = 0
    for dirpath, _, files in os.walk(RP):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), RP)
            top = rel.split(os.sep)[0]
            prunable = top in ("models", "animations", "animation_controllers", "render_controllers", "particles") \
                or (top == "textures" and name.endswith((".png", ".tga"))) or (top == "sounds" and name.endswith(".ogg"))
            if prunable and rel not in keep:
                os.remove(os.path.join(dirpath, name))
                removed += 1
    for dirpath, dirs, files in os.walk(RP, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
    return removed


def compress():
    if shutil.which("ffmpeg"):
        for dirpath, _, files in os.walk(os.path.join(RP, "sounds")):
            for name in files:
                if not name.endswith(".ogg"):
                    continue
                path = os.path.join(dirpath, name)
                music = os.sep + "music" + os.sep in path
                cmd = ["ffmpeg", "-v", "error", "-y", "-i", path, "-map_metadata", "-1"]
                cmd += ["-c:a", "libvorbis", "-q:a", "1"] if music else ["-ac", "1", "-c:a", "libvorbis", "-q:a", "4"]
                tmp = path + ".tmp.ogg"
                cmd += ["-fflags", "+bitexact", "-flags:a", "+bitexact", tmp]
                if subprocess.run(cmd).returncode == 0 and os.path.getsize(tmp) < os.path.getsize(path):
                    os.replace(tmp, path)
                elif os.path.exists(tmp):
                    os.remove(tmp)
    from PIL import Image
    for root in (BP, RP):
        for dirpath, _, files in os.walk(root):
            for name in files:
                path = os.path.join(dirpath, name)
                if name.endswith(".png"):
                    before = os.path.getsize(path)
                    im = Image.open(path)
                    im.load()
                    tmp = path + ".tmp.png"
                    im.save(tmp, optimize=True)
                    if os.path.getsize(tmp) < before:
                        os.replace(tmp, path)
                    else:
                        os.remove(tmp)
                elif name.endswith(".json"):
                    try:
                        dump(path, load(path))
                    except ValueError:
                        pass


def size(path):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)


def build(src):
    src_bp, src_rp = find_packs(src)
    before = size(src_bp) + size(src_rp)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    fix_manifests()
    fix_scripts()
    remove_soul_energy()
    fix_wolf()
    fix_boss()
    add_altar_block()
    add_fortress()
    fix_lang()
    remove_unused_clients()
    fix_sound_effects()
    fix_sound_definitions()
    removed = prune_rp()
    compress()
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
    after = size(BP) + size(RP)
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.2f} MB); "
          f"packs {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB; {removed} archivos sin uso borrados")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if os.path.isdir(sys.argv[1]):
            shutil.copytree(sys.argv[1], os.path.join(tmp, "src"))
        else:
            with zipfile.ZipFile(sys.argv[1]) as z:
                z.extractall(os.path.join(tmp, "src"))
        build(os.path.join(tmp, "src"))


if __name__ == "__main__":
    main()
