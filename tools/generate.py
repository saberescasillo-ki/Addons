"""Builds the Medieval Mobs add-on (behavior pack + resource pack + .mcaddon).

    python3 tools/generate.py            # regenerate everything
    python3 tools/generate.py --preview  # also write front/back previews of every model
"""
import json
import os
import shutil
import sys
import zipfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from models import MODELS  # noqa: E402
from textures import hx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "MedievalMobs_BP")
RP = os.path.join(ROOT, "MedievalMobs_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 0]
UUID = {
    "bp_header": "6f1c2a8e-3b4d-4e5f-9a10-2b3c4d5e6f70",
    "bp_data": "7a2d3b9f-4c5e-4f60-8b21-3c4d5e6f7a81",
    "bp_script": "8b3e4c0a-5d6f-4071-9c32-4d5e6f7a8b92",
    "rp_header": "9c4f5d1b-6e70-4182-8d43-5e6f7a8b9ca3",
    "rp_res": "ad506e2c-7f81-4293-9e54-6f7a8b9cadb4",
}
SCRIPT_API = "1.11.0"

# --------------------------------------------------------------------------
# Mob table. effect = [name, seconds] applied by the melee hit (JSON),
# extra = [[name, ticks, amplifier], ...] applied by the script on every hit
# (melee, arrow or explosion).
# --------------------------------------------------------------------------
MOBS = {
    "zombie_knight": dict(kind="zombie", en="Fallen Zombie Knight", es="Caballero Zombi Caído",
                          egg=("#5b6169", "#8e1b1b"), hp=34, speed=0.21, dmg=5, effect=["slowness", 5],
                          extra=[["slowness", 120, 1], ["weakness", 140, 0]], equip="iron_sword", kb=0.5,
                          loot=[("rotten_flesh", 0, 2), ("iron_nugget", 1, 4)], weight=20),
    "zombie_archer": dict(kind="zombie_ranged", en="Fist-Archer Zombie", es="Zombi Lanzaflechas",
                          egg=("#3e5c2b", "#6b4423"), hp=22, speed=0.25, dmg=3, effect=["hunger", 8],
                          arrow=26, extra=[["poison", 80, 0], ["hunger", 160, 0]],
                          loot=[("rotten_flesh", 0, 2), ("arrow", 1, 4), ("feather", 0, 2)], weight=25),
    "zombie_plague": dict(kind="zombie", en="Plague Zombie", es="Zombi de la Peste",
                          egg=("#2a2420", "#cbb68a"), hp=24, speed=0.24, dmg=3, effect=["hunger", 10],
                          extra=[["nausea", 160, 0], ["poison", 80, 0], ["hunger", 200, 1]],
                          loot=[("rotten_flesh", 1, 3), ("spider_eye", 0, 1), ("paper", 0, 2)], weight=20),
    "skeleton_swordsman": dict(kind="skeleton_melee", en="Skeleton Swordsman", es="Esqueleto Espadachín",
                               egg=("#2b3f8c", "#d9d3be"), hp=24, speed=0.27, dmg=4, effect=["weakness", 6],
                               extra=[["slowness", 80, 0], ["weakness", 120, 0]], equip="iron_sword",
                               loot=[("bone", 0, 2), ("iron_nugget", 0, 3)], weight=20),
    "skeleton_longbowman": dict(kind="skeleton_ranged", en="Skeleton Longbowman", es="Esqueleto Arquero Real",
                                egg=("#2f5a26", "#cfc6a8"), hp=20, speed=0.25, dmg=2, effect=["slowness", 4],
                                arrow=19, extra=[["slowness", 100, 1], ["weakness", 100, 0]], equip="bow",
                                loot=[("bone", 0, 2), ("arrow", 1, 5)], weight=20),
    "skeleton_warlord": dict(kind="skeleton_hybrid", en="Skeleton Warlord", es="Señor de la Guerra Esqueleto",
                             egg=("#3a3d44", "#d6a92e"), hp=40, speed=0.26, dmg=6, effect=["wither", 4],
                             arrow=35, extra=[["blindness", 60, 0], ["slowness", 80, 1]], equip="iron_sword", kb=0.4,
                             loot=[("bone", 1, 3), ("arrow", 1, 4), ("gold_nugget", 1, 5), ("emerald", 0, 1)], weight=6),
    "ender_wraith": dict(kind="enderman", en="Ender Wraith", es="Espectro del End",
                         egg=("#2a1838", "#7cf6ff"), hp=36, speed=0.32, dmg=6, effect=["blindness", 4],
                         extra=[["wither", 100, 0], ["blindness", 80, 0]], hostile=True,
                         loot=[("ender_pearl", 0, 1), ("phantom_membrane", 0, 1)], weight=5),
    "ender_knight": dict(kind="enderman", en="Ender Knight", es="Caballero del End",
                         egg=("#1e1530", "#e070ff"), hp=50, speed=0.3, dmg=8, effect=["slowness", 5],
                         extra=[["mining_fatigue", 160, 1], ["levitation", 30, 0]], kb=0.6, equip="iron_sword",
                         loot=[("ender_pearl", 0, 2), ("obsidian", 0, 1), ("iron_nugget", 1, 4)], weight=4),
    "bog_slime": dict(kind="slime", en="Bog Slime", es="Slime del Pantano",
                      egg=("#5f8f3a", "#b02a2a"), speed=0.55, effect=["poison", 4],
                      extra=[["slowness", 80, 0]], loot=[("slime_ball", 0, 2), ("brown_mushroom", 0, 1)], weight=15),
    "royal_slime": dict(kind="slime", en="Royal Slime", es="Slime Real",
                        egg=("#e8b23a", "#8e1b1b"), speed=0.6, effect=["weakness", 6],
                        extra=[["mining_fatigue", 160, 0], ["nausea", 100, 0]],
                        loot=[("slime_ball", 0, 2), ("gold_nugget", 1, 4)], weight=6),
    "siege_creeper": dict(kind="creeper", en="Siege Creeper", es="Creeper de Asedio",
                          egg=("#4f9a3a", "#9ba4ae"), hp=28, speed=0.22, dmg=4, effect=["slowness", 4],
                          extra=[["weakness", 120, 0]], power=4, kb=0.3,
                          loot=[("gunpowder", 1, 3), ("iron_nugget", 0, 3)], weight=15),
    "plague_creeper": dict(kind="creeper", en="Plague Creeper", es="Creeper Pestilente",
                           egg=("#6a7a3a", "#7b2f8a"), hp=20, speed=0.25, dmg=3, effect=["poison", 5],
                           extra=[["nausea", 140, 0], ["hunger", 160, 1]], power=3,
                           loot=[("gunpowder", 0, 2), ("fermented_spider_eye", 0, 1)], weight=15),
}


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")


# ------------------------------------------------------------- behaviour
def fam(*names):
    return {"test": "is_family", "subject": "other", "value": names[0]} if len(names) == 1 else \
        {"any_of": [{"test": "is_family", "subject": "other", "value": n} for n in names]}


def targets(radius=25, villagers=True):
    types = [{"filters": fam("player"), "max_dist": radius + 10}]
    if villagers:
        types.append({"filters": fam("villager", "wandering_trader"), "max_dist": radius})
    types.append({"filters": fam("irongolem"), "max_dist": radius})
    return {"priority": 2, "must_see": True, "reselect_targets": True, "within_radius": radius,
            "must_see_forget_duration": 17.0, "entity_types": types}


def attack(mob, dmg=None):
    a = {"damage": dmg if dmg is not None else mob["dmg"]}
    if mob.get("effect"):
        a["effect_name"], a["effect_duration"] = mob["effect"]
    return a


def common(mob, family, box, xp=5):
    c = {
        "minecraft:type_family": {"family": family + ["monster", "mob", "medieval"]},
        "minecraft:collision_box": {"width": box[0], "height": box[1]},
        "minecraft:movement": {"value": mob["speed"]},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:experience_reward": {"on_death": f"query.last_hit_by_player ? {xp} + (query.equipment_count * Math.Random(1,3)) : 0"},
        "minecraft:loot": {"table": f"loot_tables/medieval/{mob['id']}.json"},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 1.0},
        "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 8, "probability": 0.02},
        "minecraft:behavior.random_look_around": {"priority": 9},
    }
    if "hp" in mob:
        c["minecraft:health"] = {"value": mob["hp"], "max": mob["hp"]}
    if mob.get("kb"):
        c["minecraft:knockback_resistance"] = {"value": mob["kb"]}
    if mob.get("equip"):
        c["minecraft:equipment"] = {
            "table": f"loot_tables/medieval/equipment/{mob['id']}.json",
            "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0.085}],
        }
    return c


def undead(c, mob, avoid_sun=False):
    c["minecraft:burns_in_daylight"] = {}
    c["minecraft:breathable"] = {"total_supply": 15, "suffocate_time": 0, "breathes_water": True}
    c["minecraft:navigation.walk"] = {"is_amphibious": True, "can_pass_doors": True, "can_open_doors": False,
                                      "avoid_water": True, "avoid_sun": avoid_sun}
    c["minecraft:behavior.nearest_attackable_target"] = targets()


def ranged(c, mob, priority=2, burst=None):
    c["minecraft:shooter"] = {"def": "minecraft:arrow", "aux_val": mob["arrow"]}
    r = {"priority": priority, "attack_interval_min": 1.5, "attack_interval_max": 3.0, "attack_radius": 15.0}
    if burst:
        r["burst_shots"], r["burst_interval"] = burst
    c["minecraft:behavior.ranged_attack"] = r


def melee(c, mob, speed=1.0, priority=3, **extra):
    c["minecraft:attack"] = attack(mob)
    c["minecraft:behavior.melee_attack"] = {"priority": priority, "speed_multiplier": speed,
                                            "track_target": False, "require_complete_path": False, **extra}


def entity(mob, components, groups=None, events=None, runtime=None):
    desc = {"identifier": f"medieval:{mob['id']}", "is_spawnable": True, "is_summonable": True,
            "is_experimental": False}
    if runtime:
        desc["runtime_identifier"] = runtime
    e = {"description": desc}
    if groups:
        e["component_groups"] = groups
    e["components"] = components
    if events:
        e["events"] = events
    return {"format_version": "1.20.80", "minecraft:entity": e}


def build_entity(mob):
    k = mob["kind"]
    if k in ("zombie", "zombie_ranged"):
        c = common(mob, ["zombie", "undead"], (0.6, 1.9))
        undead(c, mob)
        if k == "zombie":
            melee(c, mob)
        else:
            # Ranged punches: arrows leave its fists in bursts of two
            c["minecraft:attack"] = attack(mob)
            ranged(c, mob, burst=(2, 0.35))
        return entity(mob, c)

    if k.startswith("skeleton"):
        c = common(mob, ["skeleton", "undead"], (0.6, 1.99))
        undead(c, mob, avoid_sun=True)
        c["minecraft:behavior.avoid_mob_type"] = {"priority": 4, "entity_types": [
            {"filters": fam("wolf"), "max_dist": 6, "walk_speed_multiplier": 1.2, "sprint_speed_multiplier": 1.2}]}
        if k == "skeleton_melee":
            melee(c, mob, speed=1.15)
            return entity(mob, c)
        if k == "skeleton_ranged":
            c["minecraft:attack"] = attack(mob)
            ranged(c, mob, priority=2)
            return entity(mob, c)
        # Hybrid: bow at range, sword up close. mark_variant 0 = ranged, 1 = melee.
        c["minecraft:attack"] = attack(mob)
        c["minecraft:environment_sensor"] = {"triggers": [
            {"filters": {"all_of": [{"test": "is_mark_variant", "value": 0},
                                    {"test": "has_target", "value": True},
                                    {"test": "target_distance", "operator": "<=", "value": 5}]},
             "event": "medieval:switch_to_melee"},
            {"filters": {"all_of": [{"test": "is_mark_variant", "value": 1},
                                    {"any_of": [{"test": "has_target", "value": False},
                                                {"test": "target_distance", "operator": ">", "value": 9}]}]},
             "event": "medieval:switch_to_ranged"},
        ]}
        rg, ml = {}, {}
        ranged(rg, mob, priority=2, burst=(2, 0.5))
        rg["minecraft:mark_variant"] = {"value": 0}
        ml["minecraft:behavior.melee_attack"] = {"priority": 2, "speed_multiplier": 1.3, "track_target": True,
                                                 "require_complete_path": False}
        ml["minecraft:mark_variant"] = {"value": 1}
        groups = {"medieval:ranged_mode": rg, "medieval:melee_mode": ml}
        events = {
            "minecraft:entity_spawned": {"add": {"component_groups": ["medieval:ranged_mode"]}},
            "medieval:switch_to_melee": {"remove": {"component_groups": ["medieval:ranged_mode"]},
                                         "add": {"component_groups": ["medieval:melee_mode"]}},
            "medieval:switch_to_ranged": {"remove": {"component_groups": ["medieval:melee_mode"]},
                                          "add": {"component_groups": ["medieval:ranged_mode"]}},
        }
        return entity(mob, c, groups, events)

    if k == "enderman":
        c = common(mob, ["enderman"], (0.6, 2.9), xp=8)
        c["minecraft:breathable"] = {"total_supply": 15, "suffocate_time": 0}
        c["minecraft:navigation.walk"] = {"can_pass_doors": True, "avoid_water": True}
        c["minecraft:teleport"] = {"random_teleports": True, "max_random_teleport_time": 30,
                                   "random_teleport_cube": [32, 32, 32], "target_distance": 16,
                                   "target_teleport_chance": 0.05, "light_teleport_chance": 0.05}
        c["minecraft:hurt_on_condition"] = {"damage_conditions": [
            {"filters": {"test": "in_contact_with_water", "operator": "==", "value": True},
             "cause": "drowning", "damage_per_tick": 1}]}
        c["minecraft:lookat"] = {"search_radius": 64.0, "set_target": True, "look_cooldown": 5.0, "filters": {
            "all_of": [fam("player"),
                       {"test": "has_equipment", "domain": "head", "subject": "other", "operator": "not",
                        "value": "carved_pumpkin"}]}}
        melee(c, mob, speed=1.2)
        # Neutral like vanilla (angry when stared at); the wraith also hunts nearby players
        t = targets(radius=10, villagers=False) if mob.get("hostile") else \
            {"priority": 2, "must_see": True, "reselect_targets": True, "within_radius": 16, "entity_types": []}
        t["entity_types"].append({"filters": fam("endermite"), "max_dist": 16})
        c["minecraft:behavior.nearest_attackable_target"] = t
        return entity(mob, c)

    if k == "slime":
        c = common(mob, ["slime"], (0.52, 0.52), xp=2)
        del c["minecraft:can_climb"]
        c["minecraft:movement.jump"] = {"jump_delay": [0.1, 0.4]}
        c["minecraft:navigation.walk"] = {"avoid_water": False, "can_pass_doors": True}
        c["minecraft:damage_sensor"] = {"triggers": {"cause": "fall", "deals_damage": False}}
        c["minecraft:behavior.nearest_attackable_target"] = targets(radius=16, villagers=False)
        c["minecraft:behavior.melee_attack"] = {"priority": 3, "speed_multiplier": 1.5, "track_target": True,
                                                "require_complete_path": False}
        c["minecraft:behavior.random_stroll"]["speed_multiplier"] = 1.2
        sizes = {"small": (1, 0.52, 4, 2), "medium": (2, 1.04, 10, 4), "large": (4, 2.08, 20, 6)}
        groups, events = {}, {}
        for name, (size, box, hp, dmg) in sizes.items():
            groups[f"medieval:{name}"] = {
                "minecraft:variant": {"value": size},
                "minecraft:scale": {"value": size},
                "minecraft:collision_box": {"width": box, "height": box},
                "minecraft:health": {"value": hp, "max": hp},
                "minecraft:attack": attack(mob, dmg),
            }
            events[f"medieval:as_{name}"] = {
                "remove": {"component_groups": [f"medieval:{o}" for o in sizes if o != name]},
                "add": {"component_groups": [f"medieval:{name}"]},
            }
        events["minecraft:entity_spawned"] = {"randomize": [
            {"weight": 2, "add": {"component_groups": ["medieval:large"]}},
            {"weight": 2, "add": {"component_groups": ["medieval:medium"]}},
            {"weight": 1, "add": {"component_groups": ["medieval:small"]}},
        ]}
        return entity(mob, c, groups, events)

    if k == "creeper":
        # Creeper that keeps hitting you while the fuse burns: the first punch
        # (or getting close) lights it, and it keeps chasing and attacking.
        c = common(mob, ["creeper"], (0.6, 1.7))
        c["minecraft:breathable"] = {"total_supply": 15, "suffocate_time": 0}
        c["minecraft:navigation.walk"] = {"can_pass_doors": True, "avoid_water": True}
        c["minecraft:behavior.nearest_attackable_target"] = targets(radius=16, villagers=False)
        melee(c, mob, speed=1.25, priority=3,
              on_attack={"event": "minecraft:start_exploding", "target": "self"})
        c["minecraft:target_nearby_sensor"] = {
            "inside_range": 2.5, "outside_range": 7.0, "must_see": True,
            "on_inside_range": {"event": "minecraft:start_exploding", "target": "self"},
            "on_outside_range": {"event": "minecraft:stop_exploding", "target": "self"},
            "on_vision_lost_inside_range": {"event": "minecraft:stop_exploding", "target": "self"},
        }
        c["minecraft:behavior.avoid_mob_type"] = {"priority": 1, "entity_types": [
            {"filters": fam("ocelot", "cat"), "max_dist": 6, "walk_speed_multiplier": 1, "sprint_speed_multiplier": 1.2}]}
        groups = {"minecraft:exploding": {
            "minecraft:explode": {"fuse_length": 1.5, "fuse_lit": True, "power": mob["power"],
                                  "causes_fire": False, "destroy_affected_by_griefing": True},
            # It runs faster at you once lit
            "minecraft:movement": {"value": mob["speed"] * 1.25},
        }}
        not_lit = {"test": "has_component", "operator": "!=", "value": "minecraft:explode"}
        events = {
            "minecraft:start_exploding": {"sequence": [
                {"filters": not_lit, "add": {"component_groups": ["minecraft:exploding"]}}]},
            "minecraft:start_exploding_forced": {"sequence": [
                {"filters": not_lit, "add": {"component_groups": ["minecraft:exploding"]}}]},
            "minecraft:stop_exploding": {"remove": {"component_groups": ["minecraft:exploding"]}},
        }
        return entity(mob, c, groups, events, runtime="minecraft:creeper")
    raise ValueError(k)


def spawn_rules(mob):
    k = mob["kind"]
    base = {
        "minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
        "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
        "minecraft:weight": {"default": mob["weight"]},
        "minecraft:herd": {"min_size": 1, "max_size": 2},
    }
    if k == "slime":
        if mob["id"] == "bog_slime":
            conds = [dict(base, **{"minecraft:spawns_on_surface": {},
                                   "minecraft:biome_filter": {"any_of": [
                                       {"test": "has_biome_tag", "value": "swamp"},
                                       {"test": "has_biome_tag", "value": "mangrove_swamp"}]}})]
        else:
            conds = [dict(base, **{"minecraft:spawns_underground": {},
                                   "minecraft:height_filter": {"min": -63, "max": 40},
                                   "minecraft:biome_filter": {"test": "has_biome_tag", "value": "monster"}})]
    else:
        conds = [dict(base, **{"minecraft:spawns_on_surface": {}, "minecraft:spawns_underground": {},
                               "minecraft:biome_filter": {"test": "has_biome_tag", "value": "monster"}})]
        if k == "enderman":
            conds[0]["minecraft:herd"] = {"min_size": 1, "max_size": 1}
            conds.append({"minecraft:spawns_on_surface": {},
                          "minecraft:weight": {"default": mob["weight"] * 2},
                          "minecraft:herd": {"min_size": 1, "max_size": 2},
                          "minecraft:biome_filter": {"test": "has_biome_tag", "value": "the_end"}})
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": f"medieval:{mob['id']}", "population_control": "monster"},
        "conditions": conds}}


def loot_table(mob):
    pools = []
    for item, lo, hi in mob["loot"]:
        pools.append({"rolls": 1, "entries": [{"type": "item", "name": f"minecraft:{item}", "weight": 1, "functions": [
            {"function": "set_count", "count": {"min": lo, "max": hi}},
            {"function": "looting_enchant", "count": {"min": 0, "max": 1}}]}]})
    return {"pools": pools}


def equipment_table(item):
    return {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": f"minecraft:{item}", "weight": 1}]}]}


def script(mobs):
    effects = {f"medieval:{i}": m["extra"] for i, m in mobs.items()}
    splitters = [f"medieval:{i}" for i, m in mobs.items() if m["kind"] == "slime"]
    return f"""// Medieval Mobs - extra effects and slime splitting.
// Generated by tools/generate.py, edit the MOBS table there instead.
import {{ world }} from "@minecraft/server";

// [effect, duration in ticks, amplifier] applied to whatever the mob hurts
// (melee hit, arrow or explosion).
const HIT_EFFECTS = {json.dumps(effects, indent=2)};

const SPLITTING_SLIMES = {json.dumps(splitters)};
const NEXT_SIZE = {{ 4: "medieval:as_medium", 2: "medieval:as_small" }};

world.afterEvents.entityHurt.subscribe((event) => {{
  const attacker = event.damageSource.damagingEntity;
  if (!attacker) return;
  let effects;
  try {{
    effects = HIT_EFFECTS[attacker.typeId];
  }} catch {{
    return;
  }}
  if (!effects) return;
  for (const [id, ticks, amplifier] of effects) {{
    try {{
      event.hurtEntity.addEffect(id, ticks, {{ amplifier, showParticles: true }});
    }} catch {{
      // target died or cannot receive effects
    }}
  }}
}});

world.afterEvents.entityDie.subscribe((event) => {{
  const slime = event.deadEntity;
  try {{
    if (!SPLITTING_SLIMES.includes(slime.typeId)) return;
    const next = NEXT_SIZE[slime.getComponent("minecraft:variant")?.value];
    if (!next) return;
    const {{ dimension, location, typeId }} = slime;
    const count = 2 + Math.floor(Math.random() * 2);
    for (let i = 0; i < count; i++) {{
      const child = dimension.spawnEntity(typeId, {{
        x: location.x + (Math.random() - 0.5),
        y: location.y + 0.5,
        z: location.z + (Math.random() - 0.5),
      }});
      child.triggerEvent(next);
    }}
  }} catch {{
    // entity already gone
  }}
}});
"""


# ------------------------------------------------------------- resources
ANIMS = {
    "look_at_target": {"head": {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0.0]}},
    "legs_walk": {
        "rightLeg": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 70.0 * query.modified_move_speed", 0.0, 0.0]},
        "leftLeg": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -70.0 * query.modified_move_speed", 0.0, 0.0]},
    },
    "arms_walk": {
        "rightArm": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -50.0 * query.modified_move_speed",
                                  0.0, "math.cos(query.life_time * 103.0) * 2.5 + 2.5"]},
        "leftArm": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 50.0 * query.modified_move_speed",
                                 0.0, "-math.cos(query.life_time * 103.0) * 2.5 - 2.5"]},
    },
    "attack_swing": {
        "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 80.0", "math.sin(variable.attack_time * 180.0) * 20.0", 0.0]},
        "body": {"rotation": [0.0, "math.sin(variable.attack_time * 180.0) * 10.0", 0.0]},
    },
    "zombie_arms": {
        "rightArm": {"rotation": ["-90.0 + math.sin(query.life_time * 76.8) * 3.0 + math.sin(variable.attack_time * 180.0) * 25.0",
                                  "-5.0", "math.cos(query.life_time * 103.0) * 3.0 + 3.0"]},
        "leftArm": {"rotation": ["-90.0 - math.sin(query.life_time * 76.8) * 3.0 + math.sin(variable.attack_time * 180.0) * 25.0",
                                 "5.0", "-math.cos(query.life_time * 103.0) * 3.0 - 3.0"]},
    },
    # Alternating jabs while it has a target: the arrows come out of these punches
    "punch_throw": {
        "rightArm": {"rotation": ["-90.0 - math.max(0.0, math.sin(query.life_time * 480.0)) * 35.0",
                                  "query.target_y_rotation * 0.3 + math.max(0.0, math.sin(query.life_time * 480.0)) * 25.0", 0.0]},
        "leftArm": {"rotation": ["-90.0 - math.max(0.0, -math.sin(query.life_time * 480.0)) * 35.0",
                                 "query.target_y_rotation * 0.3 - math.max(0.0, -math.sin(query.life_time * 480.0)) * 25.0", 0.0]},
        "body": {"rotation": [0.0, "math.sin(query.life_time * 480.0) * 12.0", 0.0]},
    },
    "bow_aim": {
        "rightArm": {"rotation": ["query.target_x_rotation - 90.0", "query.target_y_rotation - 5.73", 0.0]},
        "leftArm": {"rotation": ["query.target_x_rotation - 90.0", "query.target_y_rotation + 28.65", 0.0]},
    },
    "ender_walk": {
        "rightLeg": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 40.0 * query.modified_move_speed", 0.0, 0.0]},
        "leftLeg": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -40.0 * query.modified_move_speed", 0.0, 0.0]},
        "rightArm": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -30.0 * query.modified_move_speed", 0.0, 3.0]},
        "leftArm": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 30.0 * query.modified_move_speed", 0.0, -3.0]},
    },
    "ender_attack": {
        "rightArm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 100.0", 0.0, 0.0]},
        "leftArm": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 60.0", 0.0, 0.0]},
        "head": {"position": [0.0, "query.has_target ? 1.5 : 0.0", 0.0]},
    },
    "creeper_legs": {
        "leg0": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 80.0 * query.modified_move_speed", 0.0, 0.0]},
        "leg1": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -80.0 * query.modified_move_speed", 0.0, 0.0]},
        "leg2": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * -80.0 * query.modified_move_speed", 0.0, 0.0]},
        "leg3": {"rotation": ["math.cos(query.modified_distance_moved * 38.17) * 80.0 * query.modified_move_speed", 0.0, 0.0]},
    },
    "creeper_attack": {
        "head": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 35.0", 0.0, 0.0]},
        "body": {"rotation": ["-math.sin(variable.attack_time * 180.0) * 10.0", 0.0, 0.0]},
    },
    "cape_sway": {
        "cape": {"rotation": ["6.0 + query.modified_move_speed * 45.0 + math.sin(query.life_time * 90.0) * 3.0", 0.0, 0.0]},
    },
    "slime_squish": {
        "root": {"scale": ["1.0 + math.sin(query.life_time * 400.0) * 0.06 - (query.is_on_ground ? 0.0 : 0.08)",
                           "1.0 - math.sin(query.life_time * 400.0) * 0.06 + (query.is_on_ground ? 0.0 : 0.18)",
                           "1.0 + math.sin(query.life_time * 400.0) * 0.06 - (query.is_on_ground ? 0.0 : 0.08)"]},
    },
}

RENDER_CONTROLLERS = {
    "format_version": "1.8.0",
    "render_controllers": {
        "controller.render.medieval.default": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"]},
        "controller.render.medieval.slime_outer": {
            "geometry": "Geometry.outer", "materials": [{"*": "Material.outer"}], "textures": ["Texture.default"]},
        "controller.render.medieval.creeper": {
            "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "overlay_color": {"r": "variable.flash", "g": "variable.flash", "b": "variable.flash", "a": "variable.flash"}},
    },
}


def client_entity(mob_id, mob, model):
    k = mob["kind"]
    anims = {"look": "animation.medieval.look_at_target"}
    animate = ["look"]
    rcs = ["controller.render.medieval.default"]
    scripts = {}
    geometry = {"default": f"geometry.medieval.{mob_id}"}
    materials = {"default": "entity_alphatest"}

    def add(name, cond=None):
        anims[name] = f"animation.medieval.{name}"
        animate.append({name: cond} if cond else name)

    if k.startswith("zombie") or k.startswith("skeleton"):
        add("legs_walk")
    if k == "zombie":
        add("zombie_arms")
    elif k == "zombie_ranged":
        add("zombie_arms", "!query.has_target")
        add("punch_throw", "query.has_target")
    elif k == "skeleton_melee":
        add("arms_walk")
        add("attack_swing")
    elif k == "skeleton_ranged":
        add("arms_walk", "!query.has_target")
        add("bow_aim", "query.has_target")
    elif k == "skeleton_hybrid":
        add("arms_walk", "!(query.has_target && query.mark_variant == 0)")
        add("bow_aim", "query.has_target && query.mark_variant == 0")
        add("attack_swing")
    elif k == "enderman":
        add("ender_walk")
        add("ender_attack")
    elif k == "creeper":
        add("creeper_legs")
        add("creeper_attack")
        rcs = ["controller.render.medieval.creeper"]
        scripts = {
            "pre_animation": [
                "variable.wobble = Math.sin(query.swell_amount * 5730) * query.swell_amount * 0.01 + 1.0;",
                "variable.swelled = Math.pow(Math.clamp(query.swell_amount, 0.0, 1.0), 4.0);",
                "variable.scale_xz = (1.0 + variable.swelled * 0.4) * variable.wobble;",
                "variable.scale_y = (1.0 + variable.swelled * 0.1) / variable.wobble;",
                "variable.flash = math.mod(math.round(query.swell_amount * 10.0), 2.0) * 0.5;",
            ],
            "scalex": "variable.scale_xz", "scaley": "variable.scale_y", "scalez": "variable.scale_xz",
        }
    elif k == "slime":
        anims = {}
        animate = []
        add("slime_squish")
        geometry["outer"] = f"geometry.medieval.{mob_id}_outer"
        materials["outer"] = "slime_outer"
        rcs.append("controller.render.medieval.slime_outer")
    if any(b["name"] == "cape" for b in model.geos["default"]):
        add("cape_sway")
    scripts["animate"] = animate

    desc = {
        "identifier": f"medieval:{mob_id}",
        "materials": materials,
        "textures": {"default": f"textures/entity/medieval/{mob_id}"},
        "geometry": geometry,
        "animations": anims,
        "scripts": scripts,
        "render_controllers": rcs,
        "spawn_egg": {"base_color": mob["egg"][0], "overlay_color": mob["egg"][1]},
    }
    if mob.get("equip"):
        desc["enable_attachables"] = True
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def lang(field, pack_name, pack_desc):
    lines = [f"pack.name={pack_name}", f"pack.description={pack_desc}", ""]
    for i, m in MOBS.items():
        lines.append(f"entity.medieval:{i}.name={m[field]}")
    lines.append("")
    for i, m in MOBS.items():
        egg = f"Generar {m['es']}" if field == "es" else f"Spawn {m['en']}"
        lines.append(f"item.spawn_egg.entity.medieval:{i}.name={egg}")
    return "\n".join(lines) + "\n"


def manifest(kind):
    if kind == "bp":
        return {"format_version": 2, "header": {
            "name": "Medieval Mobs (Behavior)", "description": "Mobs medievales: zombis, esqueletos, slimes, endermen y creepers nuevos.",
            "uuid": UUID["bp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [
                {"type": "data", "uuid": UUID["bp_data"], "version": VERSION},
                {"type": "script", "language": "javascript", "uuid": UUID["bp_script"], "version": VERSION,
                 "entry": "scripts/main.js"}],
            "dependencies": [
                {"uuid": UUID["rp_header"], "version": VERSION},
                {"module_name": "@minecraft/server", "version": SCRIPT_API}]}
    return {"format_version": 2, "header": {
        "name": "Medieval Mobs (Resources)", "description": "Modelos y texturas de los mobs medievales.",
        "uuid": UUID["rp_header"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUID["bp_header"], "version": VERSION}]}


def pack_icon():
    """32x32 heraldic shield with a crossed sword, upscaled to 128."""
    img = Image.new("RGBA", (32, 32), hx("#1b1714"))
    for y in range(3, 29):
        half = 12 if y < 18 else max(0, 12 - (y - 18) * 12 // 10)
        for x in range(16 - half, 16 + half):
            edge = x in (16 - half, 16 + half - 1) or y in (3, 28) or (y > 18 and abs(x - 15.5) >= half - 1.5)
            img.putpixel((x, y), hx("#d6a92e") if edge else hx("#8e1b1b" if x < 16 else "#2b3f8c"))
    for i in range(6, 25):
        img.putpixel((15, i), hx("#cfd6dc"))
        img.putpixel((16, i), hx("#9ba4ae"))
    for x in range(11, 21):
        img.putpixel((x, 20), hx("#d6a92e"))
    for y in (21, 22, 23):
        img.putpixel((15, y), hx("#5a3a1e"))
        img.putpixel((16, y), hx("#5a3a1e"))
    for x, y in ((9, 8), (10, 8), (21, 8), (22, 8)):
        img.putpixel((x, y), hx("#141a10"))
    return img.resize((128, 128), Image.NEAREST)


def preview(model, img, path, scale=8, res=1):
    """Orthographic front + back view (ignores rotations) to check textures."""
    cubes = [c for key in ("default", "outer") for b in model.geos.get(key, []) for c in b["cubes"]]
    xs = [c.origin[0] for c in cubes] + [c.origin[0] + c.size[0] for c in cubes]
    ys = [c.origin[1] for c in cubes] + [c.origin[1] + c.size[1] for c in cubes]
    minx, maxx, maxy = min(xs) - 1, max(xs) + 1, max(ys) + 1
    W, H = int(maxx - minx), int(maxy - min(ys) + 1)
    out = Image.new("RGBA", ((W * 2 + 2) * scale, H * scale), (60, 70, 90, 255))
    for view in (0, 1):
        order = sorted(cubes, key=lambda c: -c.origin[2] if view == 0 else c.origin[2] + c.size[2])
        for c in order:
            w, h, d = c.size
            u, v = c.uv
            if view == 0:
                face = img.crop(tuple(k * res for k in (u + d, v + d, u + d + w, v + d + h)))
                x0 = c.origin[0] - minx
            else:
                face = img.crop(tuple(k * res for k in (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h)))
                face = face.transpose(Image.FLIP_LEFT_RIGHT)
                x0 = W + 2 + (maxx - (c.origin[0] + w))
            y0 = maxy - (c.origin[1] + h)
            face = face.resize((w * scale, h * scale), Image.NEAREST)
            out.alpha_composite(face, (int(x0 * scale), int(y0 * scale)))
    out.save(path)


def sheet(prev_dir, path, cols=4, names=None):
    ims = [Image.open(os.path.join(prev_dir, f"{i}.png")) for i in (names or MOBS)]
    cw, ch = max(i.width for i in ims), max(i.height for i in ims)
    out = Image.new("RGBA", (cw * cols, ch * ((len(ims) + cols - 1) // cols)), (40, 40, 50, 255))
    for k, im in enumerate(ims):
        out.paste(im, ((k % cols) * cw + (cw - im.width) // 2, (k // cols) * ch + ch - im.height))
    out.thumbnail((1600, 1600))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)


def main():
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    prev_dir = None
    if "--preview" in sys.argv:
        prev_dir = os.path.join(ROOT, "previews")
        os.makedirs(prev_dir, exist_ok=True)

    models = {f.__name__: f() for f in MODELS}
    for seed, (mob_id, mob) in enumerate(MOBS.items()):
        mob["id"] = mob_id
        model = models[mob_id]
        img = model.build(seed * 7919 + 13)
        img.save(os.path.join(_mk(RP, "textures/entity/medieval"), f"{mob_id}.png"))
        write(os.path.join(RP, "models/entity", f"{mob_id}.geo.json"), model.geometry_json())
        write(os.path.join(RP, "entity", f"{mob_id}.entity.json"), client_entity(mob_id, mob, model))
        write(os.path.join(BP, "entities", f"{mob_id}.json"), build_entity(mob))
        write(os.path.join(BP, "spawn_rules", f"{mob_id}.json"), spawn_rules(mob))
        write(os.path.join(BP, "loot_tables/medieval", f"{mob_id}.json"), loot_table(mob))
        if mob.get("equip"):
            write(os.path.join(BP, "loot_tables/medieval/equipment", f"{mob_id}.json"), equipment_table(mob["equip"]))
        if prev_dir:
            preview(model, img, os.path.join(prev_dir, f"{mob_id}.png"))

    write(os.path.join(RP, "animations/medieval.animation.json"), {"format_version": "1.8.0", "animations": {
        f"animation.medieval.{n}": {"loop": True, "bones": b} for n, b in ANIMS.items()}})
    write(os.path.join(RP, "render_controllers/medieval.render_controllers.json"), RENDER_CONTROLLERS)
    write(os.path.join(BP, "scripts/main.js"), script(MOBS))

    langs = ["en_US", "es_ES", "es_MX"]
    for pack, name, desc in ((BP, "Medieval Mobs (Behavior)", "Mobs medievales nuevos"),
                             (RP, "Medieval Mobs (Resources)", "Modelos y texturas medievales")):
        write(os.path.join(pack, "texts/languages.json"), langs)
        write(os.path.join(pack, "texts/en_US.lang"), lang("en", name, desc))
        write(os.path.join(pack, "texts/es_ES.lang"), lang("es", name, desc))
        write(os.path.join(pack, "texts/es_MX.lang"), lang("es", name, desc))
        pack_icon().save(os.path.join(pack, "pack_icon.png"))
    write(os.path.join(BP, "manifest.json"), manifest("bp"))
    write(os.path.join(RP, "manifest.json"), manifest("rp"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "MedievalMobs.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    if prev_dir:
        sheet(prev_dir, os.path.join(ROOT, "docs", "preview.png"))
    print("Built", len(MOBS), "mobs ->", os.path.relpath(DIST, ROOT))


def _mk(*parts):
    p = os.path.join(*parts)
    os.makedirs(p, exist_ok=True)
    return p


if __name__ == "__main__":
    main()
