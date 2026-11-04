"""Fixes the Magical Warfare: Light Magic add-on (ZussmanKlint). Personal use: the
output goes to the git-ignored private/ folder.

    python3 tools/lightmagic_fix.py path/to/LightMagic.mcaddon

Fixes:
  * the script asked for @minecraft/server 2.11.0-beta and server-ui 2.3.0-beta,
    betas the game no longer has ("failed to create context": no spell worked).
    The scripts only use stable API (itemUse, runCommand): stable 2.11.0, and
    server-ui is not used at all;
  * the behaviour pack did not depend on the resource pack, so the RP was easy
    to leave off (every icon, block model and texture "missing");
  * empty JSON files (sounds.json, flipbook_textures.json, a loot table) and an
    empty function (flash.mcfunction: "couldn't load");
  * the light blocks named a texture from another add-on (zk_ecrushingtrap) and a
    geometry with no bones;
  * render controllers wrote "geometry.default" for "Geometry.default";
  * the Luminous Circle animation fired a particle its entities did not list;
  * Light Prism Fall played three sounds that do not exist;
  * the light particle entities pointed to a texture that does not exist;
  * the broken wand's held model needed animations from another add-on;
  * two client entities with no behaviour entity (zk:lightspell, zk:blinder).
Change asked for: no mana and no cooldowns, every spell can be cast at any time
(the Mana counter leaves the action bar; Mana Essence stays).
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "LightMagic_BP")
RP = os.path.join(OUT, "LightMagic_RP")
MCADDON = os.path.join(OUT, "LightMagic.mcaddon")
VERSION = [1, 1, 0]


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    return json.loads(text) if text.strip() else None


def dump(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent="\t")


def edit(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def find_packs(src):
    bp = rp = None
    for dirpath, _, files in os.walk(src):
        if "manifest.json" in files:
            m = load(os.path.join(dirpath, "manifest.json"))
            kinds = {mod["type"] for mod in m["modules"]}
            if "resources" in kinds:
                rp = dirpath
            elif "data" in kinds or "script" in kinds:
                bp = dirpath
    if not bp or not rp:
        sys.exit("no encuentro los dos packs")
    return bp, rp


def manifests():
    bpm, rpm = load(os.path.join(BP, "manifest.json")), load(os.path.join(RP, "manifest.json"))
    for m in (bpm, rpm):
        m["header"]["version"] = VERSION
        for mod in m["modules"]:
            mod["version"] = VERSION
    bpm["header"]["min_engine_version"] = [1, 21, 90]
    bpm["dependencies"] = [{"uuid": rpm["header"]["uuid"], "version": VERSION},
                           {"module_name": "@minecraft/server", "version": "2.11.0"}]
    rpm["dependencies"] = [{"uuid": bpm["header"]["uuid"], "version": VERSION}]
    dump(os.path.join(BP, "manifest.json"), bpm)
    dump(os.path.join(RP, "manifest.json"), rpm)


def empty_files():
    fills = {os.path.join(RP, "sounds.json"): {},
             os.path.join(RP, "textures", "flipbook_textures.json"): [],
             os.path.join(BP, "loot_tables", "empty.json"): {"pools": []}}
    for path, value in fills.items():
        if os.path.exists(path) and load(path) is None:
            dump(path, value)
    fn = os.path.join(BP, "functions", "flash.mcfunction")
    if os.path.exists(fn) and not open(fn, encoding="utf-8").read().strip():
        with open(fn, "w", encoding="utf-8", newline="\n") as f:
            f.write("# Flash: the spell runs from its script; this function only has to exist.\n"
                    "tag @s add zk_flash_noop\ntag @s remove zk_flash_noop\n")


def blocks():
    textures = {"light.json": "zk_light", "lightblock.json": "zk_lightblock", "longlight.json": "zk_light"}
    for name, tex in textures.items():
        def f(d, tex=tex):
            comps = d["minecraft:block"]["components"]
            for inst in comps.get("minecraft:material_instances", {}).values():
                if inst.get("texture") == "zk_ecrushingtrap":
                    inst["texture"] = tex
        edit(os.path.join(BP, "blocks", name), f)

    def blank(d):  # a geometry needs at least one bone to be used by a block
        for g in d["minecraft:geometry"]:
            g.setdefault("bones", [{"name": "root", "pivot": [0, 0, 0]}])
    edit(os.path.join(RP, "models", "entity", "blank.geo.json"), blank)


def render_controllers():
    folder = os.path.join(RP, "render_controllers")
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        fixed = (text.replace('"geometry.default"', '"Geometry.default"')
                 .replace('"texture.default"', '"Texture.default"')
                 .replace('"material.default"', '"Material.default"'))
        if fixed != text:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(fixed)


def entities():
    for name in ("luminous.json", "luminousr.json"):
        path = os.path.join(RP, "entity", name)
        if os.path.exists(path):
            edit(path, lambda d: d["minecraft:client_entity"]["description"]
                 .setdefault("particle_effects", {}).update(luminousi="zk:luminous"))

    def fall(d):
        desc = d["minecraft:client_entity"]["description"]
        for k, v in desc.get("sound_effects", {}).items():
            if v in ("zk.lightprism2", "zk.lightprism3", "zk.lightprism4"):
                desc["sound_effects"][k] = "zk.lightprism"
    edit(os.path.join(RP, "entity", "lightprismfall.json"), fall)
    for name in ("lightpart.json", "lightparte.json"):
        edit(os.path.join(RP, "entity", name), lambda d: d["minecraft:client_entity"]["description"]["textures"]
             .update(default="textures/entity/illuminate"))
    for name in ("lightspell.json", "blinder.json"):
        path = os.path.join(RP, "entity", name)
        if os.path.exists(path):
            os.remove(path)
    # the broken wand's held model came from another add-on (a whole body and its
    # animations): held as a normal flat item instead
    path = os.path.join(RP, "attachables", "brokenwand.json")
    if os.path.exists(path):
        os.remove(path)


READY = ["mana", "bscd", "socd", "stcd", "stwcd", "utcd"]  # mana and the spells' cooldown timers
GET_SCORE = "    return world.scoreboard.getObjective(objectiveName)?.getScore(player.scoreboardIdentity)"


def no_mana():
    """Every spell script asks getScore() for mana and its cooldown: they now
    always answer "plenty" (the menus' short click guard, fskcd, stays)."""
    folder = os.path.join(BP, "scripts")
    patched = 0
    for dirpath, _, files in os.walk(folder):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8-sig") as f:
                text = f.read()
            if GET_SCORE not in text or not any(f"getScore('{o}'" in text for o in READY):
                continue
            text = text.replace(GET_SCORE, f"    // no mana and no cooldowns: every spell is always ready\n"
                                           f"    if ({json.dumps(READY)}.includes(objectiveName)) return Infinity;\n"
                                + GET_SCORE)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            patched += 1
    if patched < 10:
        sys.exit(f"no_mana: solo {patched} scripts de hechizos")
    edit(os.path.join(BP, "functions", "tick.json"), lambda d: d.update(values=[v for v in d["values"] if v != "mana"]))
    path = os.path.join(BP, "functions", "worldloaded.mcfunction")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    old = '{"text":"§3Mana: "},{"score":{"name":"*","objective":"mana"}},{"text":"\\n§3Essence: "}'
    if old not in text:
        sys.exit("worldloaded: no encuentro el contador de maná")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(old, '{"text":"§3Essence: "}'))


def build(src):
    src_bp, src_rp = find_packs(src)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    manifests()
    empty_files()
    blocks()
    render_controllers()
    entities()
    no_mana()
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, files in os.walk(pack):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    z.write(full, os.path.relpath(full, OUT))
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.2f} MB)")


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
