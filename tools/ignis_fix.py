"""Fixes the Ignis add-on (1.0.8) and adds the Temple of Ignis. Personal use:
the output goes to the git-ignored private/ folder.

    python3 tools/ignis_fix.py path/to/Ignis.zip

Fixes:
  * scripts/core.js (obfuscated) is replaced by a readable rewrite
    (tools/ignis/core.js) with the same mechanics: the altar, the lunges, the
    homing leap, stuns, the blazing brand, lifesteal and the config.js options;
Changes: Ignis is half a block bigger, attacks 5 % faster, the floor burns
instead of jumping as physics blocks, Ignis only fights players and golems,
the great sigil (attack11) sends 4 rows (8 in the soul phases) in every phase
and has a scattered-circles variant (both 10 % faster), and the leap's big
slashes hit a wider area.
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
import re
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ignis"))
import temple  # noqa: E402
import extras  # noqa: E402
from dungeons_mobs import load, dump  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "Ignis_BP")
RP = os.path.join(OUT, "Ignis_RP")
MCADDON = os.path.join(OUT, "Ignis.mcaddon")
VERSION = [1, 4, 0]

# Boss bar names: a leading colour code only (trailing codes may be trimmed by the
# game, and then the HUD no longer recognises the name).
BOSS_NAME = "§6Ignis"
BOSS_NAME_SOUL = "§bIgnis"


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

    # Same pattern as the Dungeons boss bars (a collection binding whose name is
    # the comparison), inserted into the vanilla panel without replacing it.
    def bar(name, color, uv_y):
        q = name.replace("'", "\\'")
        return {"bindings": [{"binding_name": f"(#bossName = '{q}')", "binding_type": "collection",
                              "binding_collection_name": "boss_bars", "binding_name_override": "#visible"}],
                "$tint": color, "$frame_uv": [0, uv_y]}
    dump(os.path.join(RP, "ui", "hud_screen.json"), {
        "namespace": "hud",
        "boss_health_panel": {"modifications": [{"array_name": "controls", "operation": "insert_back", "value": [
            {"ignis_boss_bar@ignis_health_bar.bar": bar(BOSS_NAME, "yellow", 27)},
            {"ignis_boss_bar_soul@ignis_health_bar.bar": bar(BOSS_NAME_SOUL, "cyan", 36)}]}]}})
    dump(os.path.join(RP, "ui", "ignis", "health_bar.json"), {
        "namespace": "ignis_health_bar",
        "bar": {"type": "panel", "offset": [0, 10], "size": [188, 9], "layer": 10,
                "anchor_from": "top_middle", "anchor_to": "top_middle",
                "controls": [{"empty@ignis_health_bar.empty": {}}, {"filled@ignis_health_bar.filled": {}},
                             {"frame@ignis_health_bar.frame": {}}]},
        "empty": {"type": "image", "texture": "textures/ignis/ui/empty_progress_bar", "color": "$tint",
                  "size": [182, 5], "layer": 1},
        "filled": {"type": "image", "texture": "textures/ignis/ui/filled_progress_bar", "color": "$tint",
                   "size": [182, 5], "layer": 2, "clip_direction": "left", "clip_pixelperfect": True,
                   "bindings": [{"binding_name": "#progress_percentage", "binding_name_override": "#clip_ratio",
                                 "binding_type": "collection", "binding_collection_name": "boss_bars"}]},
        "frame": {"type": "image", "texture": "textures/ignis/ui/cataclysm_boss_bar", "size": [188, 9],
                  "uv": "$frame_uv", "uv_size": [188, 9], "layer": 3}})


# --- Combat changes ---------------------------------------------------------------
SIZE = 3.75 / 3.25        # half a block taller (its hitbox is 3.25 high)
SPEED = 1.05              # attacks 5 % faster
DASH_LEAD = 0.15          # the dash starts this many seconds before the hit
SLASH_EVENTS = {"attack1_", "attack2__", "attack3_", "attack3_.", "attack6C__", "attack8_", "attack8__", "attack9S_",
                "attack10__", "attack10Sa", "attack10Sb", "attack12T__", "attack13T__"}
# Events the script turns into lunges (scaled to the target's distance): those
# animations get no extra dash. The impaling thrust's lunge is attack4_.
LUNGE_EVENTS = {"attack2_", "attack4_", "attack6C_", "attack7_", "move2", "move_3", "move3", "attack12T_"}
SIGIL_ANIMS = {"animation.ignis.ignis.attack11"}
CARET = re.compile(r"(positioned |tp @s |summon ignis:ignis_(?:b|p|ba|bb|fire) )\^([-0-9.]*)\^([-0-9.]*)\^([-0-9.]*)")


def _scale_carets(text):
    def num(s):
        v = float(s) if s not in ("", "-") else 0.0
        v = round(v * SIZE, 4)
        return "" if v == 0 else (str(int(v)) if v == int(v) else str(v))
    return CARET.sub(lambda m: f"{m.group(1)}^{num(m.group(2))}^{num(m.group(3))}^{num(m.group(4))}", text)


def _map_strings(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_map_strings(x, fn) for x in obj]
    if isinstance(obj, dict):
        return {k: _map_strings(v, fn) for k, v in obj.items()}
    return obj


def bigger():
    """minecraft:scale for the body and hitbox; the attack hit areas, impact points
    and the impaled target's position move out with the longer sword."""
    def f(d):
        ent = d["minecraft:entity"]
        ent["components"]["minecraft:scale"] = {"value": round(SIZE, 3)}
        ent["events"] = _map_strings(ent["events"], _scale_carets)
    edit(os.path.join(BP, "entities", "ignis.json"), f)
    edit(os.path.join(BP, "animations", "ignis.json"),
         lambda d: d.update(animations=_map_strings(d["animations"], _scale_carets)))


def _timeline_add(tl, time, cmd):
    key = f"{max(0.0, round(time, 3)):g}"
    cur = tl.get(key)
    if cur is None:
        tl[key] = cmd
    else:
        tl[key] = (cur if isinstance(cur, list) else [cur]) + [cmd]


SIGIL_SPEED = 1.10        # the great-sigil attacks run another 10 % faster
ROW_SUMMON = re.compile(r"^/summon ignis:ignis_strike \^")


def sigil_attacks():
    """attack11 (a rune under Ignis, then the sword strikes the ground): the rows of
    sigils now come from the script (4 directions, 8 in the soul phases), and a
    scattered-circles variant shares its animation. Both in every phase."""
    def anim(d):
        tl = d["animations"]["animation.ignis.ignis.attack11"]["timeline"]
        removed = 0
        for key in list(tl):
            cmds = tl[key] if isinstance(tl[key], list) else [tl[key]]
            keep = [c for c in cmds if not ROW_SUMMON.match(c)]
            removed += len(cmds) - len(keep)
            if not keep:
                del tl[key]
            else:
                tl[key] = keep if len(keep) > 1 else keep[0]
        if removed != 8:
            sys.exit(f"attack11: esperaba 8 sigilos en la fila, encontré {removed}")
    edit(os.path.join(BP, "animations", "ignis.json"), anim)

    def rune(d):  # the rune under Ignis bursts with the faster sword strike
        t = d["minecraft:entity"]["component_groups"]["ignis"]["minecraft:timer"]
        t["time"] = round(t["time"] / (SPEED * SIGIL_SPEED), 3)
    edit(os.path.join(BP, "entities", "ignis_strike_soul.json"), rune)

    def ent(d):
        e = d["minecraft:entity"]
        props = e["description"]["properties"]
        props["ignis:scatter"] = {"type": "bool", "default": False}
        props["ignis:timerh"] = {"type": "float", "range": [0.0, 40.0], "default": 20.0}
        props["ignis:timerf"]["default"] = 8.0   # first great sigil soon after the fight starts
        found = {"timers": 0, "attack11": 0}

        def walk(node):
            if not isinstance(node, dict):
                return
            sp = node.get("set_property", {})
            if "ignis:timera" in sp and "ignis:timerg" in sp:
                sp["ignis:timerh"] = "q.property('ignis:timerh') > 0 ? q.property('ignis:timerh') - 0.15 : 0"
                found["timers"] += 1
            for k in ("sequence", "randomize"):
                if k not in node:
                    continue
                out = []
                for child in node[k]:
                    walk(child)
                    out.append(child)
                    groups = child.get("add", {}).get("component_groups", [])
                    if k == "randomize" and "attack11" in groups:
                        found["attack11"] += 1
                        # any phase, shield or not (was: phase 3 without shield)
                        child["filters"] = {"test": "float_property", "domain": "ignis:timerf",
                                            "operator": "<=", "value": 0}
                        child["set_property"] = {"ignis:timerf": 45, "ignis:scatter": False}
                        out.append({"filters": {"test": "float_property", "domain": "ignis:timerh",
                                                "operator": "<=", "value": 0},
                                    "weight": child.get("weight", 100),
                                    "add": {"component_groups": list(groups)},
                                    "set_property": {"ignis:timerh": 35, "ignis:scatter": True}})
                node[k] = out
        walk(e["events"]["root"])
        if found != {"timers": 1, "attack11": 2}:
            sys.exit(f"root: estructura inesperada {found}")
    edit(os.path.join(BP, "entities", "ignis.json"), ent)


FIGHTERS = {"any_of": [{"test": "is_family", "subject": "other", "value": "irongolem"},
                       {"test": "is_family", "subject": "other", "value": "snowgolem"}]}
PLAYER_IN_PLAY = {"all_of": [{"test": "is_family", "subject": "other", "value": "player"},
                             {"any_of": [{"test": "has_tag", "subject": "other", "value": "ignis:gm_survival"},
                                         {"test": "has_tag", "subject": "other", "value": "ignis:gm_adventure"}]}]}


def hostility():
    """Ignis (and its fire orbs) only fight players and golems, not every mob."""
    def ignis(d):
        start = d["minecraft:entity"]["component_groups"]["start"]
        types = start["minecraft:behavior.nearest_attackable_target"]["entity_types"]
        if len(types) != 2:
            sys.exit("ignis: nearest_attackable_target inesperado")
        types[1]["filters"] = {"all_of": [{"test": "has_target", "value": False},
                                          {"test": "is_variant", "operator": "!=", "value": 6}, FIGHTERS]}
        hurt = start["minecraft:behavior.hurt_by_target"]["entity_types"]
        hurt["filters"] = {"all_of": [{"test": "has_target", "value": False},
                                      {"test": "is_variant", "operator": "!=", "value": 6},
                                      {"any_of": [PLAYER_IN_PLAY, FIGHTERS]}]}
    edit(os.path.join(BP, "entities", "ignis.json"), ignis)

    def orb(d):
        types = d["minecraft:entity"]["components"]["minecraft:behavior.nearest_prioritized_attackable_target"]["entity_types"]
        types[1]["filters"] = {"any_of": [PLAYER_IN_PLAY, FIGHTERS]}
    edit(os.path.join(BP, "entities", "ignis_fire.json"), orb)


BIG_SLASH = {  # the leap's two fiery slashes (attack10S): wider and further ahead
    "x=~1,y=~3,z=~1,dx=-3,dy=-7,dz=-3": "x=~2.5,y=~3.5,z=~2.5,dx=-6,dy=-8,dz=-6",
    "x=~3,y=~3,z=~3,dx=-7,dy=-7,dz=-7": "x=~4.5,y=~3.5,z=~4.5,dx=-10,dy=-8,dz=-10",
}
AHEAD = re.compile(r"(execute positioned \^[-0-9.]*\^[-0-9.]*\^)([-0-9.]+)")


def big_slash():
    def f(d):
        events = d["minecraft:entity"]["events"]
        n = 0

        def fix(text):
            nonlocal n
            for old, new in BIG_SLASH.items():
                if old in text:
                    n += 1
                    text = AHEAD.sub(lambda m: f"{m.group(1)}{round(float(m.group(2)) * 1.4, 4):g}",
                                     text.replace(old, new))
            return text
        for name in ("attack10Sa", "attack10Sb"):
            events[name] = _map_strings(events[name], fix)
        if n < 5:
            sys.exit(f"attack10S: solo {n} áreas de daño ampliadas")
    edit(os.path.join(BP, "entities", "ignis.json"), f)


def timing():
    """Dashes before each slash and the thrust; attacks 5 % faster (logic and visuals)."""
    def f(d):
        for name, anim in d["animations"].items():
            if "attack" not in name and "BTS" not in name:
                continue
            tl = anim.get("timeline", {})
            flat = [c for cmds in tl.values() for c in (cmds if isinstance(cmds, list) else [cmds])]
            lunges = any(c.startswith("@s ") and c[3:] in LUNGE_EVENTS for c in flat)
            for key, cmds in list(tl.items()):
                for c in (cmds if isinstance(cmds, list) else [cmds]):
                    ev = c[3:] if c.startswith("@s ") else None
                    if ev in SLASH_EVENTS and not lunges:
                        _timeline_add(tl, float(key) - DASH_LEAD, "/scriptevent ignis:dash slash")
            speed = SPEED * (SIGIL_SPEED if name in SIGIL_ANIMS else 1)
            new = {}
            for key, cmds in tl.items():
                k = f"{round(float(key) / speed, 3):g}"
                if k in new:
                    a, b = new[k], cmds
                    new[k] = (a if isinstance(a, list) else [a]) + (b if isinstance(b, list) else [b])
                else:
                    new[k] = cmds
            anim["timeline"] = new
            if "animation_length" in anim:
                anim["animation_length"] = round(anim["animation_length"] / speed, 3)
    edit(os.path.join(BP, "animations", "ignis.json"), f)
    for name in os.listdir(os.path.join(RP, "animations")):
        path = os.path.join(RP, "animations", name)
        data = load(path)
        changed = False
        for ident, anim in data.get("animations", {}).items():
            if (".attack" in ident or ".BTS" in ident) and "anim_time_update" not in anim:
                speed = round(SPEED * (SIGIL_SPEED if ident in SIGIL_ANIMS else 1), 4)
                anim["anim_time_update"] = f"q.anim_time + q.delta_time * {speed}"
                changed = True
        if changed:
            dump(path, data)


def fix_projectiles():
    """Fireballs fly straight at a steady speed and break on what they hit; the
    orbs no longer aim a projectile that does not exist ('x')."""
    def ball(d):
        ent = d["minecraft:entity"]
        ent["description"]["runtime_identifier"] = "minecraft:snowball"  # plain projectile physics
        for holder in [ent["components"]] + list(ent["component_groups"].values()):
            p = holder.get("minecraft:projectile")
            if p:
                p["inertia"] = 1
                p["liquid_inertia"] = 1
                p["gravity"] = 0
                p.setdefault("on_hit", {})["remove_on_hit"] = {}
                p["on_hit"]["particle_on_hit"] = {"particle_type": "lava", "num_particles": 1,
                                                  "on_entity_hit": True, "on_other_hit": True}
    edit(os.path.join(BP, "entities", "ignis_fireball.json"), ball)

    def orb(d):
        ent = d["minecraft:entity"]
        ent["components"]["minecraft:shooter"] = {"def": "ignis:ignis_fireball"}
        for g in ("a", "c"):
            ent["component_groups"][g].pop("minecraft:behavior.ranged_attack", None)
    edit(os.path.join(BP, "entities", "ignis_fire.json"), orb)


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
    bigger()
    sigil_attacks()
    hostility()
    big_slash()
    timing()
    fix_projectiles()
    extras.add_minion(BP, RP)
    extras.soul_strikes(BP, RP)
    extras.death(BP, RP)
    add_temple()
    extras.relic_chests(BP, RP, "ignis/chests/temple")
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
