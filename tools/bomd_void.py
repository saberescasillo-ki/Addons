"""Reduces BOMD Bedrock 1.7 (Rossetti's port of Bosses of Mass Destruction) to the
Void Blossom alone. Personal use: the output goes to the git-ignored private/ folder.

    python3 tools/bomd_void.py path/to/BOMD.zip

Kept: the Void Blossom and its parts (anchor, hitbox, petal blades, spikes, spore
balls), its cavern (structure, seed block), the Void Lily that points to a
cavern, the Vine Wall and the healer crystal of the fight, its drops (Void Thorn,
Crystal Fruit), loot, sounds, particles, boss bar and functions, and the settings
menu (/bomd:config) with the options that still apply.
Gone: the Night Lich, Nether Gauntlet and Obsidilith with their items, blocks,
structures, recipes and scripts, and natural generation (the cavern feature):
caverns now come from the Void Lily or /function bomd/void_blossom/build_cavern.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dungeons_mobs import RPIndex, mentions, read, rp_closure  # noqa: E402

OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "VoidBlossom_BP")
RP = os.path.join(OUT, "VoidBlossom_RP")
MCADDON = os.path.join(OUT, "VoidBlossom.mcaddon")
VERSION = [1, 7, 1]

ENTITIES = {"bomd:void_blossom", "bomd:void_blossom_anchor", "bomd:void_blossom_hitbox", "bomd:void_petal_blade",
            "bomd:void_spike_fx", "bomd:void_spore_ball"}
BLOCKS = {"bomd:void_blossom_cavern_seed", "bomd:void_blossom_healer", "bomd:void_lily", "bomd:vine_wall"}
ITEMS = {"bomd:void_thorn", "bomd:crystal_fruit"}
RECIPES = {"bomd:void_lily"}
OTHER_BOSSES = ("lich", "gauntlet", "obsidilith")
REMOVED_SETTINGS = ("lichHealth", "lichDamage", "gauntletHealth", "gauntletDamage", "obsidilithHealth",
                    "obsidilithDamage", "soulKills", "genTower", "genGauntlet", "genObsidilith")


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def files(root, ext=".json"):
    for dirpath, _, names in os.walk(root):
        for n in sorted(names):
            if n.endswith(ext):
                yield os.path.join(dirpath, n)


def ident(path):
    d = load(path)
    for k in ("minecraft:entity", "minecraft:block", "minecraft:item", "minecraft:client_entity",
              "minecraft:attachable"):
        if k in d:
            return d[k]["description"]["identifier"]
    for k, v in d.items():
        if k.startswith("minecraft:recipe"):
            return v["description"]["identifier"]
    return None


def find_packs(src):
    bp = rp = None
    for dirpath, _, names in os.walk(src):
        if "manifest.json" in names:
            kinds = {m["type"] for m in load(os.path.join(dirpath, "manifest.json"))["modules"]}
            if "resources" in kinds:
                rp = dirpath
            elif "data" in kinds:
                bp = dirpath
    if not bp or not rp:
        sys.exit("no encuentro los dos packs")
    return bp, rp


# --- behaviour pack ------------------------------------------------------------------------
def prune_bp():
    removed = []
    for folder, keep in (("entities", ENTITIES), ("blocks", BLOCKS), ("items", ITEMS), ("recipes", RECIPES)):
        for path in list(files(os.path.join(BP, folder))):
            if ident(path) not in keep:
                os.remove(path)
                removed.append(os.path.relpath(path, BP))
    # natural generation: the cavern (and tower) features go
    for folder in ("features", "feature_rules"):
        shutil.rmtree(os.path.join(BP, folder), ignore_errors=True)
    for path in list(files(os.path.join(BP, "loot_tables"))):
        if "/void_blossom/" not in path.replace(os.sep, "/"):
            os.remove(path)
    for path in list(files(os.path.join(BP, "structures"), ".mcstructure")):
        if not os.path.basename(path).startswith("void_blossom"):
            os.remove(path)
    gone = re.compile(r"bomd:(?!" + "|".join(re.escape(i.split(":")[1]) + r"\b" for i in ITEMS | BLOCKS) + r")[a-z_]+")
    fn = os.path.join(BP, "functions", "bomd")
    for name in os.listdir(fn):
        if name != "void_blossom":
            shutil.rmtree(os.path.join(fn, name))
    for path in files(os.path.join(fn, "void_blossom"), ".mcfunction"):
        lines = []
        for line in read(path).splitlines():
            if line.startswith("give ") and gone.search(line):
                continue  # test items of the other bosses
            lines.append(line.replace(", including the Obsidian Heart used by Obsidilith progression recipes", ""))
        write(path, "\n".join(lines) + "\n")
    for dirpath, dirs, names in os.walk(BP, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
    return removed


def script_graph(root):
    graph = {}
    for path in files(root, ".js"):
        rel = os.path.relpath(path, root)
        text = read(path)
        graph[rel] = [os.path.normpath(os.path.join(os.path.dirname(rel), m))
                      for m in re.findall(r'(?:from|import)\s+"(\.[^"]+)"', text)]
    return graph


def prune_scripts():
    scripts = os.path.join(BP, "scripts")
    shutil.copyfile(os.path.join(HERE, "bomd", "main.js"), os.path.join(scripts, "main.js"))
    shutil.copyfile(os.path.join(HERE, "bomd", "void_items.js"), os.path.join(scripts, "progression", "void_items.js"))
    graph = script_graph(scripts)
    keep, todo = set(), ["main.js"]
    while todo:
        f = todo.pop()
        if f in keep:
            continue
        if f not in graph:
            sys.exit(f"scripts: falta {f}")
        keep.add(f)
        todo += graph[f]
    for f in graph:
        if f not in keep:
            os.remove(os.path.join(scripts, f))
    for dirpath, dirs, names in os.walk(scripts, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)

    # settings: only the options that still apply
    path = os.path.join(scripts, "core", "settings.js")
    text = read(path)
    lines = [l for l in text.splitlines() if not any(f'key: "{k}"' in l for k in REMOVED_SETTINGS)]
    write(path, "\n".join(lines) + "\n")
    if any(f'key: "{k}"' in read(path) for k in REMOVED_SETTINGS):
        sys.exit("settings.js: no pude quitar los ajustes de los otros jefes")
    # the test menu summons and clears only the Void Blossom's entities
    path = os.path.join(scripts, "ui", "test_tools.js")
    text = read(path)
    for line in ('  ["lich", BOSS_TYPE],\n', '  ["gauntlet", GAUNTLET_TYPE],\n', '  ["obsidilith", OBSIDILITH_TYPE]\n',
                 "  LICH_PHANTOM_TYPE,\n", "  MAGIC_MISSILE_TYPE,\n", "  COMET_TYPE,\n", "  GAUNTLET_LASER_BEAM_TYPE,\n"):
        if line not in text:
            sys.exit(f"test_tools.js: no encuentro {line.strip()}")
        text = text.replace(line, "")
    text = text.replace('  ["void", VOID_BLOSSOM_TYPE],\n', '  ["void", VOID_BLOSSOM_TYPE]\n')
    write(path, text)
    # the cavern toggle now only concerns caverns found with the Void Lily
    path = os.path.join(scripts, "ui", "strings.js")
    write(path, read(path))
    return len(graph), len(keep)


# --- resource pack --------------------------------------------------------------------------
def prune_rp():
    for folder in ("entity", "attachables"):
        for path in list(files(os.path.join(RP, folder))):
            if ident(path) not in ENTITIES | ITEMS:
                os.remove(path)
    # boss bar: only the Void Blossom's
    hud_path = os.path.join(RP, "ui", "hud_screen.json")
    hud = load(hud_path)
    hud = {k: v for k, v in hud.items() if not any(f"bomd_{b}" in k for b in OTHER_BOSSES)}
    for mod in hud["boss_health_panel"]["modifications"]:
        mod["value"] = [c for c in mod["value"] if not any(f"bomd_{b}" in next(iter(c)) for b in OTHER_BOSSES)]
    dump(hud_path, hud)
    # block and item atlases, blocks.json: kept ones only
    bp_words = set()
    for path in files(BP, ""):
        if path.endswith((".json", ".js", ".mcfunction")):
            bp_words |= mentions(read(path))
    for rel, key in (("textures/item_texture.json", "texture_data"), ("textures/terrain_texture.json", "texture_data")):
        path = os.path.join(RP, rel)
        d = load(path)
        d[key] = {k: v for k, v in d[key].items() if k in bp_words}
        dump(path, d)
    path = os.path.join(RP, "blocks.json")
    if os.path.exists(path):
        d = load(path)
        dump(path, {k: v for k, v in d.items() if k == "format_version" or k in BLOCKS})
    start = []
    for dirpath, _, names in os.walk(RP):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), RP)
            top = rel.split(os.sep)[0]
            if top in ("entity", "attachables", "ui", "texts") or rel in (
                    "sounds.json", "blocks.json", "textures/item_texture.json", "textures/terrain_texture.json",
                    "textures/flipbook_textures.json"):
                start.append(rel)
    keep, words = rp_closure(RPIndex(RP), start, bp_words)
    sd_path = os.path.join(RP, "sounds", "sound_definitions.json")
    defs = load(sd_path)
    sd = defs.get("sound_definitions", defs)
    kept = {k: v for k, v in sd.items() if k in words or k in bp_words}
    if "sound_definitions" in defs:
        defs["sound_definitions"] = kept
    else:
        defs = kept
    dump(sd_path, defs)
    for v in kept.values():
        for s in v.get("sounds", []):
            n = s if isinstance(s, str) else s.get("name", "")
            for ext in (".ogg", ".fsb", ".wav"):
                keep.add(n + ext)
    removed = 0
    for dirpath, _, names in os.walk(RP):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), RP)
            top = rel.split(os.sep)[0]
            prunable = top in ("models", "animations", "animation_controllers", "render_controllers", "particles") \
                or (top == "textures" and name.endswith((".png", ".tga"))) or (top == "sounds" and name.endswith((".ogg", ".fsb", ".wav")))
            if prunable and rel not in keep:
                os.remove(os.path.join(dirpath, name))
                removed += 1
    for dirpath, dirs, names in os.walk(RP, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
    # names of the things that are gone
    for path in files(os.path.join(RP, "texts"), ".lang"):
        lines = read(path).splitlines()
        out = [l for l in lines if not re.match(r"^(entity|item|tile|item\.spawn_egg\.entity)\.bomd:", l)
               or any(i in l for i in ENTITIES | BLOCKS | ITEMS)]
        write(path, "\n".join(out) + "\n")
    return removed


def manifests():
    bpm, rpm = load(os.path.join(BP, "manifest.json")), load(os.path.join(RP, "manifest.json"))
    uid = lambda n: str(uuid.uuid5(uuid.NAMESPACE_URL, f"bomd-void-blossom/{n}"))
    ids = {"bp": uid("bp"), "rp": uid("rp")}
    for m, kind in ((bpm, "bp"), (rpm, "rp")):
        m["header"]["version"] = VERSION
        m["header"]["uuid"] = ids[kind]
        m["header"]["name"] = "BOMD Void Blossom - " + ("Behavior" if kind == "bp" else "Resources")
        m["header"]["description"] = "The Void Blossom from BOMD Bedrock 1.7 (Rossetti), alone"
        for i, mod in enumerate(m["modules"]):
            mod["version"] = VERSION
            mod["uuid"] = uid(f"{kind}-{mod['type']}-{i}")
    for dep in bpm["dependencies"]:
        if "uuid" in dep:
            dep.update(uuid=ids["rp"], version=VERSION)
    for dep in rpm["dependencies"]:
        if "uuid" in dep:
            dep.update(uuid=ids["bp"], version=VERSION)
    dump(os.path.join(BP, "manifest.json"), bpm)
    dump(os.path.join(RP, "manifest.json"), rpm)


def build(src):
    src_bp, src_rp = find_packs(src)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    gone = prune_bp()
    total, kept = prune_scripts()
    removed = prune_rp()
    manifests()
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, names in os.walk(pack):
                dirs.sort()
                for name in sorted(names):
                    full = os.path.join(dirpath, name)
                    z.write(full, os.path.relpath(full, OUT))
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")
    print(f"  BP: {len(gone)} definiciones quitadas; scripts {kept}/{total}; RP: {removed} archivos sin uso")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(sys.argv[1]) as z:
            z.extractall(tmp)
        build(tmp)


if __name__ == "__main__":
    main()
