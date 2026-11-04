"""Fixes the Ignis add-on (1.0.8) and adds the Temple of Ignis. Personal use:
the output goes to the git-ignored private/ folder.

    python3 tools/ignis_fix.py path/to/Ignis.zip

Fixes:
  * scripts/core.js was empty: rewritten (tools/ignis/core.js). The Altar of
    Fire works with Burning Ashes, Ignis targets players (it needs the
    ignis:gm_* tags the script gives), and config.js does something again;
  * boss health bar: the boss names used formatting codes that do not exist
    (§F§O§R§M) and the bar only showed if a variable trick in the UI worked;
    now valid hidden codes and the binding pattern the game supports;
  * altar_ring named an animation that only exists in the resource pack;
  * the strike sigils played the 'particle.soul' effect they do not define;
  * invisible entities pointed to an empty texture path;
  * Burning Ashes and Ignitium Ingot used the old 1.10 item format;
  * item names in en_US.lang lacked their '.name' suffix;
  * unused files (old_animations).
Adds the Temple of Ignis (tools/ignis/temple.py), with the altar in the
middle and Burning Ashes in its shrine chests: /function ignis/temple
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ignis"))
import temple  # noqa: E402
from dungeons_mobs import load, dump  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "Ignis_BP")
RP = os.path.join(OUT, "Ignis_RP")
MCADDON = os.path.join(OUT, "Ignis.mcaddon")
VERSION = [1, 1, 1]

BOSS_NAME = "§6Ignis§r§i§r"        # §i / §j: material colour codes, invisible with no text after them
BOSS_NAME_SOUL = "§bIgnis§r§j§r"


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
        sys.exit("No se encontraron los packs de Ignis en " + src)
    return bp, rp


def edit(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def fix_manifests():
    def bump(m):
        m["header"]["version"] = VERSION
        for mod in m["modules"]:
            mod["version"] = VERSION
        for d in m.get("dependencies", []):
            if "uuid" in d:
                d["version"] = VERSION
        m["header"]["description"] = "Ignis 1.1.1 (corregido + Templo de Ignis)"
        m["header"]["min_engine_version"] = [1, 21, 90]  # data-driven structure (/place)
    edit(os.path.join(BP, "manifest.json"), bump)
    edit(os.path.join(RP, "manifest.json"), bump)


def fix_scripts():
    shutil.copyfile(os.path.join(HERE, "ignis", "core.js"), os.path.join(BP, "scripts", "core.js"))


def fix_altar_ring():
    def f(d):
        desc = d["minecraft:entity"]["description"]
        desc.pop("animations", None)   # animation.ignis.altar_ring is client-side only
        desc.pop("scripts", None)
    edit(os.path.join(BP, "entities", "altar_ring.json"), f)


def fix_strike_particles():
    path = os.path.join(RP, "animation_controllers", "ignis_strike.ac.json")
    dump(path, {"format_version": "1.10.0", "animation_controllers": {
        "controller.animation.ignis.strike.particles": {
            "initial_state": "default",
            "states": {"default": {"particle_effects": [{"effect": "particle"}]}}}}})
    for name in ("ignis_strike", "ignis_strike_soul"):
        def f(d):
            d["minecraft:client_entity"]["description"]["animations"]["particles"] = \
                "controller.animation.ignis.strike.particles"
        edit(os.path.join(RP, "entity", name + ".entity.json"), f)


def fix_empty_textures():
    from PIL import Image
    tex = os.path.join(RP, "textures", "ignis", "entity", "empty.png")
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(tex)
    for name in os.listdir(os.path.join(RP, "entity")):
        path = os.path.join(RP, "entity", name)
        data = load(path)
        textures = data["minecraft:client_entity"]["description"].get("textures", {})
        changed = False
        for k, v in textures.items():
            if v == "":
                textures[k] = "textures/ignis/entity/empty"
                changed = True
        if changed:
            dump(path, data)


def fix_items():
    """1.10 items (a BP description and an RP file) -> one current item."""
    for ident, rarity in (("burning_ashes", "rare"), ("ignitium_ingot", "epic")):
        dump(os.path.join(BP, "items", ident + ".json"), {
            "format_version": "1.21.40",
            "minecraft:item": {
                "description": {"identifier": "ignis:" + ident, "menu_category": {"category": "items"}},
                "components": {"minecraft:icon": "ignis:" + ident, "minecraft:rarity": rarity,
                               "minecraft:max_stack_size": 64}}})
        os.remove(os.path.join(RP, "items", ident + ".json"))
    if not os.listdir(os.path.join(RP, "items")):
        os.rmdir(os.path.join(RP, "items"))


def fix_lang():
    path = os.path.join(RP, "texts", "en_US.lang")
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    out = []
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.startswith("item.ignis:") and not key.endswith(".name"):
            key += ".name"
        out.append(key + sep + value if sep else line)
    out += ["tile.ignis:temple.name=Temple of Ignis"]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def fix_boss_bar():
    def f(d):
        groups = d["minecraft:entity"]["component_groups"]
        groups["bossbar"]["minecraft:boss"]["name"] = BOSS_NAME
        groups["soul.bossbar"]["minecraft:boss"]["name"] = BOSS_NAME_SOUL
    edit(os.path.join(BP, "entities", "ignis.json"), f)

    def bar(name, color, uv_y):
        q = name.replace("'", "\\'")
        return {
            "type": "panel", "offset": [0, 10], "size": [188, 9],
            "anchor_from": "top_middle", "anchor_to": "top_middle",
            "bindings": [
                {"binding_name": "#bossName", "binding_type": "collection", "binding_collection_name": "boss_bars"},
                {"binding_type": "view", "source_property_name": f"(#bossName = '{q}')",
                 "target_property_name": "#visible"}],
            "controls": [
                {"empty@ignis_health_bar.empty": {"$texture": "textures/ignis/ui/empty_progress_bar", "color": color,
                                                  "size": [182, 5], "layer": 1}},
                {"filled@ignis_health_bar.filled": {"$texture": "textures/ignis/ui/filled_progress_bar",
                                                    "color": color, "size": [182, 5], "layer": 2}},
                {"frame@ignis_health_bar.frame": {"uv": [0, uv_y], "layer": 3}}]}
    dump(os.path.join(RP, "ui", "hud_screen.json"), {
        "namespace": "hud",
        "boss_health_panel": {"modifications": [{"array_name": "controls", "operation": "insert_back", "value": [
            {"ignis_boss_bar": bar(BOSS_NAME, "yellow", 27)},
            {"ignis_boss_bar_soul": bar(BOSS_NAME_SOUL, "cyan", 36)}]}]}})
    dump(os.path.join(RP, "ui", "ignis", "health_bar.json"), {
        "namespace": "ignis_health_bar",
        "filled": {"type": "image", "texture": "$texture", "clip_direction": "left", "clip_pixelperfect": False,
                   "bindings": [{"binding_name": "#progress_percentage", "binding_type": "collection",
                                 "binding_collection_name": "boss_bars", "binding_name_override": "#clip_ratio"}]},
        "empty": {"type": "image", "texture": "$texture"},
        "frame": {"type": "image", "texture": "textures/ignis/ui/cataclysm_boss_bar", "size": [188, 9],
                  "uv_size": [188, 9]}})


def add_temple():
    os.makedirs(os.path.join(BP, "structures", "ignis"), exist_ok=True)
    temple.build().save(os.path.join(BP, "structures", "ignis", "temple.mcstructure"))
    os.makedirs(os.path.join(BP, "functions", "ignis"), exist_ok=True)
    half = temple.N // 2
    with open(os.path.join(BP, "functions", "ignis", "temple.mcfunction"), "w", newline="\n") as f:
        f.write("# Temple of Ignis: the courtyard floor ends up at your feet, the centre where you stand.\n"
                f"structure load ignis:temple ~-{half} ~-{temple.F} ~-{half}\n"
                "tellraw @s {\"rawtext\":[{\"text\":\"§6The Temple of Ignis rises. Offer Burning Ashes to the "
                "Altar of Fire.\"}]}\n")
    # /place structure ignis:temple: a jigsaw structure with a single piece and no
    # structure set (so it never generates by itself). The surface heightmap puts
    # the courtyard floor at ground level.
    wg = os.path.join(BP, "worldgen")
    dump(os.path.join(wg, "processors", "temple.json"), {
        "format_version": "1.21.20",
        "minecraft:processor_list": {"description": {"identifier": "ignis:temple"}, "processors": []}})
    dump(os.path.join(wg, "template_pools", "temple.json"), {
        "format_version": "1.21.20",
        "minecraft:template_pool": {"description": {"identifier": "ignis:temple"}, "elements": [{
            "element": {"element_type": "minecraft:single_pool_element", "location": "ignis/temple",
                        "processors": "ignis:temple"}, "weight": 1}]}})
    dump(os.path.join(wg, "structures", "temple.json"), {
        "format_version": "1.21.20",
        "minecraft:jigsaw": {
            "description": {"identifier": "ignis:temple"},
            "biome_filters": [{"test": "has_biome_tag", "operator": "!=", "value": "ignis_never"}],  # always true
            "heightmap_projection": "world_surface",
            "max_depth": 1,
            "start_height": {"type": "constant", "value": {"absolute": -temple.F}},
            "start_pool": "ignis:temple",
            "step": "surface_structures",
            "terrain_adaptation": "beard_thin"}})
    dump(os.path.join(BP, "loot_tables", "ignis", "chests", "temple.json"), {"pools": [
        {"rolls": 1, "entries": [{"type": "item", "name": "ignis:burning_ashes", "weight": 1,
                                  "functions": [{"function": "set_count", "count": {"min": 1, "max": 2}}]}]},
        {"rolls": {"min": 3, "max": 6}, "entries": [
            {"type": "item", "name": "minecraft:gold_ingot", "weight": 20,
             "functions": [{"function": "set_count", "count": {"min": 2, "max": 7}}]},
            {"type": "item", "name": "minecraft:blaze_rod", "weight": 15,
             "functions": [{"function": "set_count", "count": {"min": 1, "max": 4}}]},
            {"type": "item", "name": "minecraft:magma_cream", "weight": 12,
             "functions": [{"function": "set_count", "count": {"min": 1, "max": 3}}]},
            {"type": "item", "name": "minecraft:fire_charge", "weight": 10,
             "functions": [{"function": "set_count", "count": {"min": 2, "max": 6}}]},
            {"type": "item", "name": "minecraft:diamond", "weight": 5,
             "functions": [{"function": "set_count", "count": {"min": 1, "max": 2}}]},
            {"type": "item", "name": "minecraft:golden_apple", "weight": 4},
            {"type": "item", "name": "minecraft:netherite_scrap", "weight": 2},
            {"type": "item", "name": "minecraft:enchanted_golden_apple", "weight": 1}]}]})


def build(src):
    src_bp, src_rp = find_packs(src)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP, ignore=shutil.ignore_patterns("old_animations"))
    for root in (BP, RP):  # the zip had read-only folders
        for dirpath, dirs, files in os.walk(root):
            os.chmod(dirpath, 0o755)
            for n in files:
                os.chmod(os.path.join(dirpath, n), 0o644)
    fix_manifests()
    fix_scripts()
    fix_altar_ring()
    fix_strike_particles()
    fix_empty_textures()
    fix_items()
    fix_lang()
    fix_boss_bar()
    add_temple()
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
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    if os.path.isdir(sys.argv[1]):
        build(sys.argv[1])
        return
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(sys.argv[1]) as z:
            z.extractall(tmp)
        build(tmp)


if __name__ == "__main__":
    main()
