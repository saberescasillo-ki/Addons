"""Ports Blook's More Mob Mod (Blooky_Road, made with Addons Maker; "only works in
1.21.00 or below") to current Minecraft (1.26). Personal use: the output goes to
the git-ignored private/ folder.

    python3 tools/bmm_fix.py path/to/BlooksMoreMobMod.mcaddon

What changes:
  * items (139) and blocks (63) used the "Holiday Creator Features" formats
    (1.16.100 / 1.17 items, 1.16.100 / 1.20.10 blocks with events), which the game
    removed: rewritten in the 1.21.80 formats. Their events (on_use, weapon hits,
    digging, eating, block placing/stepping/ticking/interacting...) are played by
    a script (tools/bmm/engine.js) from data extracted here;
  * player.json was a 1.11 copy of the vanilla player: rebuilt on today's vanilla
    player (1.26.30, Mojang's bedrock-samples) with the add-on's additions. Its
    equipment bonuses were re-applied every tick and wiped every potion and beacon
    effect: now the script switches them only when the gear changes;
  * the resource pack's 1.10 player and item files (old vanilla copies) are gone;
  * old command syntax (execute <target> <pos> <cmd>, block data values) in
    functions, entities and animation controllers: converted;
  * collision boxes outside the block, a few unknown values; junk files.
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
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bmm"))
import commands  # noqa: E402

OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "BlooksMoreMob_BP")
RP = os.path.join(OUT, "BlooksMoreMob_RP")
MCADDON = os.path.join(OUT, "BlooksMoreMob.mcaddon")
VANILLA = os.path.join(OUT, "bmm_vanilla")
SAMPLES = "https://raw.githubusercontent.com/Mojang/bedrock-samples/main/"
VERSION = [1, 0, 0]
FORMAT = "1.21.80"
ITEM_COMPONENT, BLOCK_COMPONENT = "mo:item_events", "mo:block_events"


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def files(root, ext=".json"):
    for dirpath, _, names in os.walk(root):
        for n in sorted(names):
            if n.endswith(ext):
                yield os.path.join(dirpath, n)


def find_packs(src):
    bp = rp = None
    for dirpath, _, names in os.walk(src):
        if "manifest.json" in names and "__MACOSX" not in dirpath:
            kinds = {m["type"] for m in load(os.path.join(dirpath, "manifest.json"))["modules"]}
            if "resources" in kinds:
                rp = dirpath
            elif "data" in kinds:
                bp = dirpath
    if not bp or not rp:
        sys.exit("no encuentro los dos packs")
    return bp, rp


def vanilla(path):
    local = os.path.join(VANILLA, os.path.basename(path))
    if not os.path.exists(local):
        os.makedirs(VANILLA, exist_ok=True)
        subprocess.run(["curl", "-sSfL", "-m", "60", "-o", local, SAMPLES + path], check=True)
    return load(local)


# --- commands ----------------------------------------------------------------------------
def convert_commands(obj):
    """Converts every command string inside a JSON value (keys "command", and
    "/..." strings in animation controllers)."""
    if isinstance(obj, dict):
        return {k: ([commands.convert(c) if isinstance(c, str) else c for c in v] if k == "command" and isinstance(v, list)
                    else commands.convert(v) if k == "command" and isinstance(v, str) else convert_commands(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [commands.convert(x) if isinstance(x, str) and x.startswith("/") else convert_commands(x) for x in obj]
    return obj


def fix_commands():
    n = 0
    for path in files(os.path.join(BP, "functions"), ".mcfunction"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        out = [commands.convert(l) if l.strip() and not l.strip().startswith("#") else l for l in lines]
        n += sum(a != b for a, b in zip(lines, out))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
    for top in ("entities", "animation_controllers"):
        for path in files(os.path.join(BP, top)):
            d = load(path)
            c = convert_commands(d)
            if c != d:
                dump(path, c)
    return n


# --- items ----------------------------------------------------------------------------------
SATURATION = {"poor": 0.1, "low": 0.3, "normal": 0.6, "good": 0.8, "high": 1.0, "max": 1.0, "supernatural": 1.2}
ENCHANT = {"helmet": "armor_head", "chestplate": "armor_torso", "leggings": "armor_legs", "legs": "armor_legs",
           "boots": "armor_feet", "feet": "armor_feet", "head": "armor_head", "torso": "armor_torso"}
CATEGORIES = {"construction", "equipment", "items", "nature", "none"}
COPY = {"minecraft:display_name", "minecraft:max_stack_size", "minecraft:hand_equipped", "minecraft:allow_off_hand",
        "minecraft:stacked_by_data", "minecraft:can_destroy_in_creative", "minecraft:cooldown", "minecraft:fuel",
        "minecraft:durability", "minecraft:repairable", "minecraft:use_animation"}
DROPPED = {"minecraft:render_offsets", "minecraft:mining_speed", "minecraft:knockback_resistance",
           "minecraft:creative_category", "minecraft:weapon", "minecraft:on_use", "minecraft:on_use_on",
           "minecraft:use_on", "minecraft:armor", "minecraft:use_duration", "minecraft:foil"}


def menu(desc, comps):
    cat = (desc.get("category") or "items").lower()
    m = {"category": cat if cat in CATEGORIES else "items"}
    parent = (comps.get("minecraft:creative_category") or {}).get("parent")
    if parent:
        m["group"] = parent if parent.startswith("minecraft:") else "minecraft:" + parent
    return m


def item(d, data, unknown):
    it = d["minecraft:item"]
    desc, c, events = it["description"], it["components"], it.get("events", {})
    out, tags, trig = {}, [], {}
    for k, v in c.items():
        if k.startswith("tag:"):
            tags.append(k[4:])
        elif k == "minecraft:display_name":
            if isinstance(v, dict) and v.get("value"):
                out[k] = v
        elif k in COPY:
            out[k] = v
        elif k == "minecraft:icon":
            out[k] = v.get("texture") if isinstance(v, dict) else v
        elif k == "minecraft:damage":
            out[k] = {"value": round(v["value"] if isinstance(v, dict) else v)}
        elif k == "minecraft:enchantable":
            out[k] = {"slot": ENCHANT.get(v.get("slot"), v.get("slot")), "value": v.get("value", 10)}
        elif k == "minecraft:digger":
            speeds, dig = [], {}
            for s in v.get("destroy_speeds", []):
                speeds.append({"block": s["block"], "speed": s["speed"]})
                if s.get("on_dig", {}).get("event") and isinstance(s["block"], str):
                    dig[s["block"]] = s["on_dig"]["event"]
            out[k] = {"use_efficiency": v.get("use_efficiency", True), "destroy_speeds": speeds}
            if dig:
                data["dig"] = dig
        elif k == "minecraft:wearable":
            out[k] = {"slot": v["slot"], "protection": (c.get("minecraft:armor") or {}).get("protection", 0)}
        elif k == "minecraft:food":
            f = {"nutrition": v.get("nutrition", 0), "can_always_eat": v.get("can_always_eat", False),
                 "saturation_modifier": SATURATION.get(v.get("saturation_modifier"), 0.6)
                 if isinstance(v.get("saturation_modifier"), str) else v.get("saturation_modifier", 0.6)}
            if v.get("using_converts_to"):
                f["using_converts_to"] = v["using_converts_to"]
            out[k] = f
            if v.get("on_consume", {}).get("event"):
                trig["consume"] = v["on_consume"]["event"]
        elif k not in DROPPED:
            unknown.add(k)
    if c.get("minecraft:foil"):
        out["minecraft:glint"] = True
    if "minecraft:use_duration" in c:
        out["minecraft:use_modifiers"] = {"use_duration": min(float(c["minecraft:use_duration"]), 3600.0),
                                          "movement_modifier": 0.35}
    w = c.get("minecraft:weapon") or {}
    for old, new in (("on_hurt_entity", "hurt"), ("on_not_hurt_entity", "not_hurt"), ("on_hit_block", "hit_block")):
        if w.get(old, {}).get("event"):
            trig[new] = w[old]["event"]
    for comp, key, new in (("minecraft:on_use", "on_use", "use"), ("minecraft:on_use_on", "on_use_on", "use_on")):
        if (c.get(comp) or {}).get(key, {}).get("event"):
            trig[new] = c[comp][key]["event"]
    if c.get("minecraft:use_on", {}).get("blocks"):
        data["use_on"] = c["minecraft:use_on"]["blocks"]
    if tags:
        out["minecraft:tags"] = {"tags": tags}
    trig = {k: v for k, v in trig.items() if events.get(v)}
    data["dig"] = {b: e for b, e in data.get("dig", {}).items() if events.get(e)}
    if trig or data["dig"]:
        data["triggers"] = trig
        data["events"] = convert_commands(events)
        out["minecraft:custom_components"] = [ITEM_COMPONENT]
    return {"format_version": FORMAT, "minecraft:item": {
        "description": {"identifier": desc["identifier"], "menu_category": menu(desc, c)}, "components": out}}


def fix_items():
    data, unknown = {}, set()
    for path in files(os.path.join(BP, "items")):
        d = load(path)
        entry = {}
        new = item(d, entry, unknown)
        dump(path, new)
        if entry.get("triggers") or entry.get("dig"):
            data[new["minecraft:item"]["description"]["identifier"]] = entry
    shutil.rmtree(os.path.join(RP, "items"), ignore_errors=True)  # 1.10 client items: old format only
    return data, unknown


# --- blocks ------------------------------------------------------------------------------------
TRIGGERS = {"minecraft:on_player_placing": "place_player", "minecraft:on_placed": "placed",
            "minecraft:on_player_destroyed": "destroyed", "minecraft:on_interact": "interact",
            "minecraft:on_step_on": "step_on", "minecraft:on_step_off": "step_off", "minecraft:on_fall_on": "fall_on"}
NOOP = re.compile(r"^fill ~ ~-1 ~ ~ ~-1 ~ air(?: 0)? replace air$")


def molang(text):
    return re.sub(r"\bquery\.block_property\(", "q.block_state(", text) if isinstance(text, str) else text


def box(v):
    if isinstance(v, bool):
        return v
    o, s = v.get("origin", [-8, 0, -8]), v.get("size", [16, 16, 16])
    if all(x == 0 for x in s):
        return False
    ok = (all(x >= 0 for x in s) and -8 <= o[0] and o[0] + s[0] <= 8 and 0 <= o[1] and o[1] + s[1] <= 16
          and -8 <= o[2] and o[2] + s[2] <= 8)
    return {"origin": o, "size": s} if ok else True


def light(v):
    return max(0, min(15, round(v * 15 if isinstance(v, float) and v <= 1 else v)))


def block_components(c, trig, unknown):
    out = {}
    for k, v in c.items():
        if k in TRIGGERS:
            if v.get("event"):
                trig[TRIGGERS[k]] = {"event": v["event"], **({"condition": v["condition"]} if v.get("condition") else {})}
        elif k in ("minecraft:ticking", "minecraft:queued_ticking"):
            ev = (v.get("on_tick") or {}).get("event")
            if ev:
                if k == "minecraft:ticking":
                    r = [max(1, round(x * 20)) if x > 0 else 20 for x in v.get("range", [1, 1])]
                else:
                    r = [x if x > 0 else 10 for x in v.get("interval_range", [10, 10])]
                trig["tick"] = {"event": ev, "interval": r, "looping": v.get("looping", True)}
        elif k == "minecraft:random_ticking":
            ev = (v.get("on_tick") or {}).get("event")
            if ev:
                trig["random_tick"] = {"event": ev}
        elif k.startswith("tag:") or k in ("minecraft:loot", "minecraft:map_color", "minecraft:material_instances",
                                          "minecraft:placement_filter", "minecraft:friction"):
            out[k] = v
        elif k == "minecraft:geometry":
            if isinstance(v, dict):
                v = {**v, "bone_visibility": {b: molang(e) for b, e in v.get("bone_visibility", {}).items()}} \
                    if "bone_visibility" in v else v
            out[k] = v
        elif k == "minecraft:destroy_time":
            out["minecraft:destructible_by_mining"] = {"seconds_to_destroy": v}
        elif k == "minecraft:destructible_by_mining":
            out[k] = v
        elif k == "minecraft:explosion_resistance":
            out["minecraft:destructible_by_explosion"] = {"explosion_resistance": min(v, 1e6)}
        elif k == "minecraft:destructible_by_explosion":
            out[k] = v
        elif k in ("minecraft:block_light_emission", "minecraft:light_emission"):
            out["minecraft:light_emission"] = light(v)
        elif k in ("minecraft:block_light_absorption", "minecraft:light_dampening"):
            out["minecraft:light_dampening"] = light(v)
        elif k in ("minecraft:entity_collision", "minecraft:collision_box"):
            out["minecraft:collision_box"] = box(v)
        elif k in ("minecraft:pick_collision", "minecraft:selection_box"):
            out["minecraft:selection_box"] = box(v)
        elif k == "minecraft:flammable":
            out[k] = {"catch_chance_modifier": v.get("flame_odds", v.get("catch_chance_modifier", 5)),
                      "destroy_chance_modifier": v.get("burn_odds", v.get("destroy_chance_modifier", 20))}
        elif k == "minecraft:rotation":
            out["minecraft:transformation"] = {"rotation": [((x + 180) % 360) - 180 if x % 90 == 0 else x for x in v]}
        elif k == "minecraft:transformation":
            out[k] = v
        elif k == "minecraft:crafting_table":
            out[k] = {"table_name": v.get("custom_description", v.get("table_name", "Crafting")),
                      "crafting_tags": v.get("crafting_tags", [])}
        elif k == "minecraft:creative_category":
            pass
        else:
            unknown.add(k)
    return out


def clean_events(events):
    out = {}
    for name, ev in events.items():
        ev = convert_commands(ev)
        rc = ev.get("run_command")
        if isinstance(rc, dict):
            cmds = [c for c in (rc.get("command") or []) if not NOOP.match(c)]
            if cmds:
                rc["command"] = cmds
            else:
                ev = {k: v for k, v in ev.items() if k != "run_command"}
        if ev:
            out[name] = ev
    return out


def fix_blocks():
    data, unknown = {}, set()
    for path in files(os.path.join(BP, "blocks")):
        d = load(path)
        b = d["minecraft:block"]
        desc = b["description"]
        events = clean_events(b.get("events", {}))
        trig = {}
        comps = block_components(b["components"], trig, unknown)
        perms = []
        for p in b.get("permutations", []):
            pt = {}
            pc = block_components(p.get("components", {}), pt, unknown)
            cond = molang(p["condition"])
            if pc:
                perms.append({"condition": cond, "components": pc})
            pt = {k: v for k, v in pt.items() if v["event"] in events}
            if pt:
                data.setdefault(desc["identifier"], {}).setdefault("perms", []).append({"condition": p["condition"], "triggers": pt})
        trig = {k: v for k, v in trig.items() if v["event"] in events}
        has_perm_trig = bool(data.get(desc["identifier"], {}).get("perms"))
        if trig or has_perm_trig:
            entry = data.setdefault(desc["identifier"], {})
            entry["triggers"] = {k: {x: y for x, y in v.items() if x not in ("interval", "looping")} for k, v in trig.items()}
            entry["events"] = events
            entry.setdefault("perms", [])
            comps["minecraft:custom_components"] = [BLOCK_COMPONENT]
            if "tick" in trig:
                comps["minecraft:tick"] = {"interval_range": trig["tick"]["interval"], "looping": trig["tick"]["looping"]}
            if "fall_on" in trig:
                comps["minecraft:entity_fall_on"] = {"min_fall_distance": 1}
        if isinstance(desc.get("menu_category"), dict) and desc["menu_category"].get("group") \
                and not desc["menu_category"]["group"].startswith("minecraft:"):
            desc["menu_category"]["group"] = "minecraft:" + desc["menu_category"]["group"]
        nd = {"identifier": desc["identifier"], "menu_category": desc.get("menu_category") or
              {"category": (desc.get("category") or "construction").lower()
               if (desc.get("category") or "construction").lower() in CATEGORIES else "construction"}}
        if b["components"].get("minecraft:creative_category", {}).get("category"):
            cat = b["components"]["minecraft:creative_category"]["category"].lower()
            nd["menu_category"] = {"category": cat if cat in CATEGORIES else "construction"}
        if desc.get("properties") or desc.get("states"):
            nd["states"] = desc.get("states") or desc["properties"]
        new = {"format_version": FORMAT, "minecraft:block": {"description": nd, "components": comps}}
        if perms:
            new["minecraft:block"]["permutations"] = perms
        dump(path, new)
    return data, unknown


# --- player --------------------------------------------------------------------------------------
GEAR_BASE = "mo:gear_base"


def fix_player():
    path = os.path.join(BP, "entities", "player.json")
    old = load(path)["minecraft:entity"]
    van = vanilla("behavior_pack/entities/player.json")
    ent = van["minecraft:entity"]
    gear, gear_events, gear_groups = [], {}, []
    keep_triggers = []
    for t in old["components"].get("minecraft:environment_sensor", []):
        env = t.get("on_environment", t)
        flt = json.dumps(env.get("filters", {}))
        ev = env.get("event")
        add = (old["events"].get(ev) or {}).get("add", {}).get("component_groups", [])
        m = re.search(r'"test": "has_equipment", "subject": "self", "domain": "(\w+)", "value": "([^"]+)"', flt)
        if m and len(add) == 1 and add[0] in old["component_groups"] and not ev.startswith("ammo"):
            g = add[0]
            group = old["component_groups"][g]
            gear.append({"item": m.group(2), "domain": m.group(1), "group": g,
                         "effects": [{"effect": e["effect"], "amplifier": e.get("amplifier", 0)}
                                     for e in (group.get("minecraft:spell_effects") or {}).get("add_effects", [])]})
            if g not in gear_groups:
                gear_groups.append(g)
        else:
            keep_triggers.append({"event": ev, "filters": env.get("filters", {})})
    groups = dict(ent.get("component_groups", {}))
    for name, g in old["component_groups"].items():
        g = {k: v for k, v in g.items() if k != "minecraft:spell_effects"}
        groups[name] = g
    # the per-tick refresh only marks the variant now (it also reset health and wiped effects)
    groups["pamobile:respawn"] = {"minecraft:mark_variant": {"value": 99999}}
    groups[GEAR_BASE] = {"minecraft:health": {"value": 20, "max": 20}, "minecraft:movement": {"value": 0.1},
                         "minecraft:attack": {"damage": 1}}
    events = dict(ent.get("events", {}))
    for name, e in old["events"].items():
        if name in ("pamobile:refresh_player",):
            e = {"add": {"component_groups": ["pamobile:respawn"]}}
        if name == "minecraft:entity_spawned":
            e = {"add": {"component_groups": ["pamobile:respawn", GEAR_BASE]}}
        if name in events and name != "minecraft:entity_spawned":
            continue
        events[name] = e
    every = gear_groups + [GEAR_BASE]
    for g in gear_groups:
        ev = "mo:gear_" + re.sub(r"\W", "_", g.split(":")[-1])
        gear_events[g] = ev
        events[ev] = {"remove": {"component_groups": [x for x in every if x != g]}, "add": {"component_groups": [g]}}
    events["mo:gear_none"] = {"remove": {"component_groups": gear_groups}, "add": {"component_groups": [GEAR_BASE]}}
    comps = dict(ent["components"])
    vs = comps.get("minecraft:environment_sensor", {}).get("triggers", [])
    vs = vs if isinstance(vs, list) else [vs]
    comps["minecraft:environment_sensor"] = {"triggers": vs + keep_triggers}
    desc = dict(ent["description"])
    for k in ("scripts", "animations"):
        if k in old["description"]:
            desc[k] = old["description"][k]
    ent = {"description": desc, "component_groups": groups, "components": comps, "events": events}
    dump(path, convert_commands({"format_version": van["format_version"], "minecraft:entity": ent}))
    rp_player = os.path.join(RP, "entity", "player.entity.json")
    if os.path.exists(rp_player):
        os.remove(rp_player)  # a 1.10 copy of the vanilla player: the game's own is used
    return gear, gear_events


# --- repairs (broken in the original too) -------------------------------------------------------
VANILLA_FILES = [
    "animation_controllers/humanoid.animation_controllers.json", "animations/humanoid.animation.json",
    "animations/look_at_target.animation.json", "animations/zombie.animation.json",
    "models/entity/creeper.geo.json", "models/entity/guardian.geo.json", "models/mobs.json",
    "render_controllers/armor.render_controllers.json", "render_controllers/creeper.render_controllers.json",
    "render_controllers/creeper_armor.render_controllers.json", "render_controllers/guardian.render_controllers.json",
    "render_controllers/iron_golem.render_controllers.json", "render_controllers/phantom.render_controllers.json",
    "render_controllers/polar_bear.render_controllers.json", "render_controllers/spider.render_controllers.json",
    "render_controllers/turtle.render_controllers.json", "render_controllers/warden.render_controllers.json",
]


def lenient(text):
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def vanilla_ids():
    """Names the game itself provides (animations, controllers, models) that the mobs use."""
    ids = set()
    for rel in VANILLA_FILES:
        local = os.path.join(VANILLA, "defs", rel.replace("/", "_"))
        if not os.path.exists(local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            subprocess.run(["curl", "-sSfL", "-m", "60", "-o", local, SAMPLES + "resource_pack/" + rel], check=True)
        with open(local, encoding="utf-8-sig") as f:
            d = lenient(f.read())
        for k in ("animations", "animation_controllers", "render_controllers"):
            ids |= set(d.get(k, {}))
        for g in d.get("minecraft:geometry", []):
            ids.add(g["description"]["identifier"])
        ids |= {k.split(":")[0] for k in d if k.startswith("geometry.")}
    dump(os.path.join(VANILLA, "vanilla_ids.json"), sorted(ids))
    return ids


def rp_ids():
    ids = set()
    for folder in ("animations", "animation_controllers", "render_controllers", "models"):
        for path in files(os.path.join(RP, folder)):
            try:
                d = load(path)
            except ValueError:
                continue
            if not isinstance(d, dict):
                os.remove(path)  # an empty ("null") model
                continue
            for k in ("animations", "animation_controllers", "render_controllers"):
                ids |= set(d.get(k, {}) or {})
            for g in d.get("minecraft:geometry", []) or []:
                ids.add(g.get("description", {}).get("identifier"))
            ids |= {k.split(":")[0] for k in d if k.startswith("geometry.")}
    return ids


def repairs():
    known = vanilla_ids() | rp_ids()
    fixed = 0
    # Addons Maker's "iron golem" mobs name a render controller the game no longer has
    dump(os.path.join(RP, "render_controllers", "mo_legacy.render_controllers.json"), {
        "format_version": "1.8.0", "render_controllers": {"controller.render.iron_golem": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]}}})
    known.add("controller.render.iron_golem")
    rename = {"geometry.guardian": "geometry.guardian.v1.8", "animation.humanoid.base_pose.v1.0": "animation.humanoid.base_pose",
              "animation.humanoid.swimming.v1.0": "animation.humanoid.swimming"}
    used = {}
    for path in files(os.path.join(RP, "entity")):
        d = load(path)
        desc = d["minecraft:client_entity"]["description"]
        for k, v in list(desc.get("geometry", {}).items()):
            if v in rename:
                desc["geometry"][k] = rename[v]
                fixed += 1
        anims = desc.get("animations", {})
        for k, v in list(anims.items()):
            v = rename.get(v, v)
            if v not in known:
                # copies of the humanoid set under the mob's own name (never shipped)
                alt = re.sub(r"^animation\.[\w ]+\.", "animation.humanoid.", v)
                v = alt if alt in known else None
            if v:
                anims[k] = v
            else:
                del anims[k]
                fixed += 1
        sc = desc.get("scripts", {})
        if "animate" in sc:
            sc["animate"] = [a for a in sc["animate"] if (next(iter(a)) if isinstance(a, dict) else a) in anims]
        dump(path, d)
        used[desc["identifier"]] = dict(anims)
    # client animation controllers: states playing animations no entity using them defines
    for path in files(os.path.join(RP, "animation_controllers")):
        d = load(path)
        changed = False
        for cid, ctl in d.get("animation_controllers", {}).items():
            users = [a for a in used.values() if cid in a.values()]
            if not users:
                continue
            mine = set().union(*(set(a) for a in users))
            for st in ctl.get("states", {}).values():
                if "animations" in st:
                    keep = [a for a in st["animations"] if (next(iter(a)) if isinstance(a, dict) else a) in mine]
                    if len(keep) != len(st["animations"]):
                        st["animations"] = keep
                        changed = True
                        fixed += 1
        if changed:
            dump(path, d)
    # behaviour entities: events adding groups they do not have, or firing missing events
    bp_anims = set()
    for path in files(os.path.join(BP, "animation_controllers")):
        bp_anims |= set(load(path).get("animation_controllers", {}))

    def prune(node, groups, events):
        nonlocal fixed
        if isinstance(node, dict):
            for key in ("add", "remove"):
                cg = node.get(key, {}).get("component_groups") if isinstance(node.get(key), dict) else None
                if cg is not None:
                    keep = [g for g in cg if g in groups]
                    fixed += len(cg) - len(keep)
                    node[key]["component_groups"] = keep
            if isinstance(node.get("on_damage"), dict) and node["on_damage"].get("event") \
                    and node["on_damage"]["event"] not in events and not node["on_damage"]["event"].startswith("minecraft:"):
                del node["on_damage"]["event"]
                fixed += 1
            if "trigger" in node:
                t = node["trigger"]
                name = t if isinstance(t, str) else t.get("event")
                if name and not name.startswith("minecraft:") and name not in events:
                    del node["trigger"]
                    fixed += 1
            for v in node.values():
                prune(v, groups, events)
        elif isinstance(node, list):
            for v in node:
                prune(v, groups, events)
    for path in files(os.path.join(BP, "entities")):
        d = load(path)
        e = d["minecraft:entity"]
        groups, evs = set(e.get("component_groups", {})), set(e.get("events", {}))
        prune(e.get("events", {}), groups, evs)
        prune(e.get("components", {}), groups, evs)
        prune(e.get("component_groups", {}), groups, evs)
        desc = e["description"]
        if "animations" in desc:
            desc["animations"] = {k: v for k, v in desc["animations"].items() if v in bp_anims or not v.startswith("controller.")}
            sc = desc.get("scripts", {})
            if "animate" in sc:
                sc["animate"] = [a for a in sc["animate"] if (next(iter(a)) if isinstance(a, dict) else a) in desc["animations"]]
        dump(path, d)
    # blocks naming "mo:x" textures the atlas has as "mo_x" (or up/down/side)
    terrain = load(os.path.join(RP, "textures", "terrain_texture.json"))["texture_data"]
    blocks_json = load(os.path.join(RP, "blocks.json"))
    for path in files(os.path.join(BP, "blocks")):
        d = load(path)
        b = d["minecraft:block"]
        ident = b["description"]["identifier"]
        mi = b["components"].get("minecraft:material_instances", {})
        star = mi.get("*", {})
        if star.get("texture") and star["texture"] not in terrain:
            bj = (blocks_json.get(ident) or {}).get("textures")
            base = star["texture"].replace(":", "_")
            if isinstance(bj, dict):
                method = star.get("render_method", "opaque")
                mi["*"] = {**star, "texture": bj.get("side", base)}
                for face in ("up", "down"):
                    if bj.get(face):
                        mi[face] = {"texture": bj[face], "render_method": method}
                fixed += 1
            elif isinstance(bj, str) and bj in terrain:
                star["texture"] = bj
                fixed += 1
            elif base in terrain:
                star["texture"] = base
                fixed += 1
            else:
                # textures that exist as files but were never put in the atlas
                faces = {f: f"{base}_{f}" for f in ("up", "down", "side", "north", "south", "east", "west")
                         if os.path.exists(os.path.join(RP, "textures", "blocks", f"{base}_{f}.png"))}
                if faces:
                    for name in faces.values():
                        terrain[name] = {"textures": f"textures/blocks/{name}"}
                    method = star.get("render_method", "opaque")
                    side = faces.get("side") or faces.get("north") or next(iter(faces.values()))
                    mi["*"] = {**star, "texture": side}
                    for f, name in faces.items():
                        if f != "side":
                            mi[f] = {"texture": name, "render_method": method}
                    fixed += 1
        dump(path, d)
    tt = load(os.path.join(RP, "textures", "terrain_texture.json"))
    tt["texture_data"] = terrain
    dump(os.path.join(RP, "textures", "terrain_texture.json"), tt)
    # item atlas: entries for files that are not there (left over from another add-on), and two missing icons
    itp = os.path.join(RP, "textures", "item_texture.json")
    it = load(itp)
    data = it["texture_data"]
    exists = lambda t: any(os.path.exists(os.path.join(RP, t + e)) for e in (".png", ".tga", ".jpg"))
    for k in list(data):
        t = data[k].get("textures")
        if isinstance(t, str) and not exists(t):
            del data[k]
            fixed += 1
    for path in files(os.path.join(BP, "items")):
        icon = load(path)["minecraft:item"]["components"].get("minecraft:icon")
        if isinstance(icon, str) and icon not in data:
            for cand in (icon.replace(":", "_"), icon.split(":")[-1]):
                rel = f"textures/items/pamobile/{cand if cand.startswith('mo_') else 'mo_' + cand}"
                if exists(rel):
                    data[icon] = {"textures": rel}
                    fixed += 1
                    break
    dump(itp, it)
    lang = os.path.join(RP, "texts", "en_US.lang")
    with open(lang, encoding="utf-8-sig") as f:
        text = f.read()
    if "entity.mo:stoat_snow.name=" not in text:
        with open(lang, "a", encoding="utf-8", newline="\n") as f:
            f.write("\nentity.mo:stoat_snow.name=Snow Stoat\nitem.spawn_egg.entity.mo:stoat_snow.name=Spawn Snow Stoat\n")
        fixed += 1
    return fixed


# --- manifests, script, cleanup ---------------------------------------------------------------------
def manifests():
    bpm, rpm = load(os.path.join(BP, "manifest.json")), load(os.path.join(RP, "manifest.json"))
    text = "More hostile mobs and bosses for survival, by Blooky_Road (ported to Minecraft 1.26)"
    for m in (bpm, rpm):
        m["header"]["version"] = VERSION
        m["header"]["min_engine_version"] = [1, 21, 90]
        m["header"]["description"] = text
        for mod in m["modules"]:
            mod["version"] = VERSION
            mod["description"] = text
    bpm["modules"] = [m for m in bpm["modules"] if m["type"] != "script"] + [{
        "type": "script", "language": "javascript", "uuid": "b7f1c2d4-6a3e-4c8b-9d21-5e7f8a9b0c13",
        "version": VERSION, "entry": "scripts/main.js"}]
    bpm["dependencies"] = [{"uuid": rpm["header"]["uuid"], "version": VERSION},
                           {"module_name": "@minecraft/server", "version": "2.11.0"}]
    rpm["dependencies"] = [{"uuid": bpm["header"]["uuid"], "version": VERSION}]
    dump(os.path.join(BP, "manifest.json"), bpm)
    dump(os.path.join(RP, "manifest.json"), rpm)


def scripts(items, blocks, gear, gear_events):
    folder = os.path.join(BP, "scripts")
    os.makedirs(folder, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "bmm", "engine.js"), os.path.join(folder, "main.js"))
    with open(os.path.join(folder, "data.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("// Generated by tools/bmm_fix.py from the add-on's item, block and player JSON.\n")
        for name, value in (("ITEMS", items), ("BLOCKS", blocks), ("GEAR", gear), ("GEAR_EVENTS", gear_events)):
            f.write(f"export const {name} = {json.dumps(value, ensure_ascii=False)};\n")


def cleanup():
    for p in (os.path.join(BP, ".data"), os.path.join(BP, ".error"), os.path.join(RP, "__MACOSX")):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)


def build(src):
    src_bp, src_rp = find_packs(src)
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    cleanup()
    items, iu = fix_items()
    blocks, bu = fix_blocks()
    gear, gear_events = fix_player()
    n = fix_commands()
    r = repairs()
    manifests()
    scripts(items, blocks, gear, gear_events)
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, names in os.walk(pack):
                dirs.sort()
                for name in sorted(names):
                    full = os.path.join(dirpath, name)
                    z.write(full, os.path.relpath(full, OUT))
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")
    print(f"  objetos con eventos: {len(items)}, bloques con eventos: {len(blocks)}, bonus de equipo: {len(gear)}, "
          f"líneas de funciones convertidas: {n}, reparaciones: {r}")
    if iu or bu:
        print("  componentes sin convertir:", sorted(iu | bu))


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
