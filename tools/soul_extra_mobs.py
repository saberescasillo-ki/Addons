"""More mobs for The Revamp of the Soul: soul corrupted spider, summoner
zombie (straw hat + cape), the navy Titan Creeper sub-boss, and a vanilla
skeleton variant with a cape that shoots two arrows. Used by
tools/soul_mobs.py."""
import copy

from PIL import Image

from models import Model
from soul_mobs import (A, NS, TEX, OUTLINE_TEX, WHITE, Pal16, add_soul_extras, fam, hexcol, hx, immunities,
                       ident, kf, patch_mob, recolor_rgb, walk)
from textures import Mat, d_tattered

SPIDER = dict(es="Araña de Alma Corrupta", en="Soul Corrupted Spider", scale=1.3, hp=24, dmg=4, speed=0.33)
SUMMONER = dict(es="Zombi Invocador de Alma Corrupta", en="Soul Corrupted Summoner Zombie")
TITAN = "soul_corrupted_creeper_titan"
TITAN_INFO = dict(es="Creeper Titán de Alma Corrupta", en="Soul Corrupted Titan Creeper", hp=40, weight=2,
                  hue=0.62, value=0.5)
CAPED = "caped_skeleton"
CAPED_INFO = dict(es="Esqueleto Encapotado", en="Caped Skeleton", weight=20)


# ================================================================ painting
def d_spider_face():
    """Eight white eyes and a dark maw."""
    def fn(f):
        f.px([(1, 2), (2, 2), (5, 2), (6, 2), (0, 1), (7, 1), (3, 3), (4, 3)], WHITE)
        f.px([(1, 3), (2, 3), (5, 3), (6, 3)], f.tone(5))
        for x in range(1, 7):
            f.put(x, 6, f.tone(5) if x % 2 else WHITE)
    return fn


def d_creeper_face_white():
    """The original soul creeper face: a white creeper face."""
    def fn(f):
        f.px([(1, 2), (2, 2), (1, 3), (2, 3), (5, 2), (6, 2), (5, 3), (6, 3)], WHITE)
        f.px([(3, 4), (4, 4), (2, 5), (3, 5), (4, 5), (5, 5), (2, 6), (3, 6), (4, 6), (5, 6), (2, 7), (5, 7)], WHITE)
    return fn


def d_straw():
    def fn(f):
        for y in range(f.h):
            for x in range(f.w):
                if (x + y) % 3 == 0:
                    f.put(x, y, f.tone(1))
    return fn


def d_hat_band():
    def fn(f):
        for x in range(f.w):
            f.put(x, f.h - 1, f.tone(5))
    return fn


# ================================================================== models
def spider_model():
    """Monstrous spider: big spiked abdomen, fangs, clawed legs, eight eyes.
    Vanilla bone names so the vanilla spider animations drive it."""
    m = Model("soul_corrupted_spider", tex_w=128, bounds=(4.0, 2.5), ns="eu.sc")
    skin, deep = Pal16("skin"), Pal16("deep", 0.6)
    root = m.bone("root", [0, 0, 0])
    root["locators"] = {"particle_locator": [0, 0, 0]}
    body0 = m.bone("body0", [0, 9, 0], "root")
    m.cube(body0, [-3, 6, -3], [6, 6, 6], skin)
    head = m.bone("head", [0, 9, -3], "body0")
    m.cube(head, [-4, 5, -11], [8, 8, 8], skin.with_deco(front=d_spider_face()))
    for x in (-3, 1):  # fangs
        m.cube(head, [x, 3, -12], [2, 3, 2], deep)
        m.cube(head, [x + 0.5, 1, -12], [1, 2, 1], Pal16("bone"))
    body1 = m.bone("body1", [0, 9, 9], "body0")
    m.cube(body1, [-6, 4, 3], [12, 10, 13], skin)
    for o, s in (([-1, 14, 5], [2, 3, 2]), ([-4, 14, 9], [2, 2, 2]), ([2, 14, 9], [2, 2, 2]),
                 ([-1, 14, 12], [2, 3, 2]), ([-0.5, 12, 16], [1, 2, 2])):  # spikes
        m.cube(body1, o, s, deep)
    for i, (px, pz) in enumerate(((-4, 2), (4, 2), (-4, 1), (4, 1), (-4, 0), (4, 0), (-4, -1), (4, -1))):
        leg = m.bone(f"leg{i}", [px, 9, pz], "body0")
        if px < 0:
            m.cube(leg, [-19, 8, pz - 1], [16, 2, 2], deep)
            m.cube(leg, [-21, 6, pz - 1], [2, 4, 2], Pal16("bone"))  # claw
        else:
            m.cube(leg, [3, 8, pz - 1], [16, 2, 2], deep)
            m.cube(leg, [19, 6, pz - 1], [2, 4, 2], Pal16("bone"))
    return m


def summoner_extras():
    """Straw farmer hat and cape for the original soul zombie."""
    m = Model("summoner_extras", tex_w=64, ns="eu.sc")
    head = m.bone("head", [0, 24, 0], "body")
    m.cube(head, [-7, 31, -7], [14, 1, 14], Pal16("skin", 0.2).with_deco(top=d_straw(), bottom=d_straw()))
    m.cube(head, [-4.5, 32, -4.5], [9, 4, 9], Pal16("skin", 0.2).with_deco(sides=[d_straw(), d_hat_band()], top=d_straw()))
    cape = m.bone("cape", [0, 24, 2.5], "body")
    m.cube(cape, [-5, 5, 2.5], [10, 19, 1], Pal16("deep", 0.8).with_deco(sides=d_tattered(2, 0.5)))
    return m


def titan_model():
    """A taller creeper on long legs (2.25 blocks)."""
    m = Model(TITAN, tex_w=64, bounds=(2.5, 3.0), ns="eu.sc")
    skin = Pal16("skin", 1.0)
    body = m.bone("body", [0, 14, 0])
    body["locators"] = {"particle_locator": [0, 0, 0]}
    m.cube(body, [-4, 14, -2], [8, 14, 4], skin)
    head = m.bone("head", [0, 28, 0], "body")
    m.cube(head, [-4, 28, -4], [8, 8, 8], skin.with_deco(front=d_creeper_face_white()))
    for name, px, pz in (("leg0", -2, 4), ("leg1", 2, 4), ("leg2", -2, -4), ("leg3", 2, -4)):
        leg = m.bone(name, [px, 14, pz], "body")
        m.cube(leg, [px - 2, 0, pz - 2], [4, 14, 4], Pal16("deep", 0.8))
    return m


def cape_model():
    """Cape for the vanilla skeleton (its own geometry/texture next to the vanilla ones)."""
    m = Model("caped_skeleton_cape", tex_w=32, ns="eu.sc")
    m.bone("body", [0, 24, 0])
    cape = m.bone("cape", [0, 24, 2.5], "body")
    cloth = Mat("#4a2f2a", "cloth", accent="#2e1c18", noise=0.1).with_deco(sides=d_tattered(3, 0.55))
    m.cube(cape, [-5, 3, 2.5], [10, 21, 1], cloth)
    hood = m.bone("hood", [0, 24, 0], "body")
    m.cube(hood, [-5, 21, -3], [10, 3, 6], Mat("#4a2f2a", "cloth", accent="#2e1c18", noise=0.1))
    return m


def extend_geometry(base_geo, base_tex, extras, identifier, drop=()):
    """Base geometry (original texture on top) + extra bones painted below it."""
    extra_img = extras.build(seed=4321)
    names = {b["name"] for b in base_geo["bones"]}
    bones = [copy.deepcopy(b) for b in base_geo["bones"] if b["name"] not in drop]
    for b in extras.geos["default"]:
        if b["name"] in names:  # attach the cubes to the existing bone
            target = next(x for x in bones if x["name"] == b["name"])
        else:
            target = {k: v for k, v in b.items() if k != "cubes"}
            target["cubes"] = []
            bones.append(target)
        target.setdefault("cubes", [])
        for c in b["cubes"]:
            j = c.to_json()
            j["uv"] = [j["uv"][0], j["uv"][1] + 32]
            target["cubes"].append(j)
    th = 64 if 32 + extra_img.height <= 64 else 128
    tex = Image.new("RGBA", (64, th), (0, 0, 0, 0))
    tex.paste(base_tex.convert("RGBA"), (0, 0))
    tex.alpha_composite(extra_img, (0, 32))
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": identifier, "texture_width": 64, "texture_height": th,
                        "visible_bounds_width": 3, "visible_bounds_height": 3, "visible_bounds_offset": [0, 1.5, 0]},
        "bones": bones}]}, tex


# ============================================================== animations
ANIMS = {
    "spider_spawn": {"loop": "hold_on_last_frame", "animation_length": 0.9, "bones": {
        "root": {"scale": kf({0.0: [0.05, 0.05, 0.05], 0.4: [0.8, 0.6, 0.8], 0.65: [1.12, 1.15, 1.12], 0.9: [1, 1, 1]}),
                 "position": kf({0.0: [0, -6, 0], 0.5: [0, -1, 0], 0.9: [0, 0, 0]})}}},
    "spider_life": {"loop": True, "bones": {
        "body1": {"rotation": ["math.sin(query.life_time * 90.0) * 3.0", "math.sin(query.life_time * 60.0) * 4.0", 0.0]},
        "head": {"rotation": [f"variable.s_speed * 8.0", 0.0, "math.sin(query.life_time * 40.0) * 3.0"]}}},
    "cape_sway": {"loop": True, "bones": {
        "cape": {"rotation": ["6.0 + query.modified_move_speed * 40.0 + math.sin(query.life_time * 90.0) * 3.0", 0.0, 0.0]}}},
    "summoner_cast": {"animation_length": 1.2, "particle_effects": {"0.4": [{"effect": "burst"}]}, "bones": {
        "rightArm": {"rotation": kf({0.0: [0, 0, 0], 0.3: [-80, 0, 20], 0.9: [-80, 0, 20], 1.2: [0, 0, 0]})},
        "leftArm": {"rotation": kf({0.0: [0, 0, 0], 0.3: [-80, 0, -20], 0.9: [-80, 0, -20], 1.2: [0, 0, 0]})},
        "head": {"rotation": kf({0.0: [0, 0, 0], 0.3: [-30, 0, 0], 0.9: [-30, 0, 0], 1.2: [0, 0, 0]})}}},
}


def controllers():
    action = f"query.property('{NS}:action')"
    return {
        f"controller.animation.{NS}.summoner": {"initial_state": "idle", "states": {
            "idle": {"animations": ["cape_sway"], "transitions": [{"cast": f"{action} == 3"}]},
            "cast": {"animations": ["cape_sway", "summoner_cast"], "blend_transition": 0.2,
                     "transitions": [{"idle": f"{action} != 3 && query.all_animations_finished"}]}}},
        f"controller.animation.{NS}.spider": {"initial_state": "start", "states": {
            "start": {"transitions": [{"emerging": f"query.property('{NS}:emerging')"},
                                      {"alive": f"!query.property('{NS}:emerging')"}]},
            "emerging": {"animations": ["spider_spawn"], "particle_effects": [{"effect": "burst"}],
                         "transitions": [{"alive": f"!query.property('{NS}:emerging')"}], "blend_transition": 0.3},
            "alive": {"animations": ["spider_life"], "blend_transition": 0.3}}},
        f"controller.animation.{NS}.cape": {"initial_state": "default", "states": {
            "default": {"animations": ["cape_sway"]}}},
    }


# =============================================================== behaviour
def soul_base(kind_id, color, emerge=0.9):
    return {
        "properties": {f"{NS}:emerging": {"type": "bool", "default": False, "client_sync": True}},
        "groups": {f"{NS}:emerging": {"minecraft:timer": {"looping": False, "time": emerge,
                                                           "time_down_event": {"event": f"{NS}:emerged"}}}},
        "events": {
            "minecraft:entity_spawned": {"add": {"component_groups": [f"{NS}:emerging"]},
                                         "set_property": {f"{NS}:emerging": True}},
            f"{NS}:emerged": {"remove": {"component_groups": [f"{NS}:emerging"]},
                              "set_property": {f"{NS}:emerging": False}}},
    }


def spider_behavior(color):
    base = soul_base("spider", color)
    comps = {
        "minecraft:type_family": {"family": ["spider", "arthropod", "monster", "mob", "soul_corrupted"]},
        "minecraft:health": {"value": SPIDER["hp"], "max": SPIDER["hp"]},
        "minecraft:scale": {"value": SPIDER["scale"]},
        "minecraft:collision_box": {"width": 1.8, "height": 1.15},
        "minecraft:movement": {"value": SPIDER["speed"]},
        "minecraft:movement.basic": {},
        "minecraft:navigation.climb": {"can_path_over_water": True},
        "minecraft:can_climb": {},
        "minecraft:jump.static": {},
        "minecraft:physics": {},
        "minecraft:pushable_by_entity": {},
        "minecraft:pushable_by_block": {},
        "minecraft:attack": {"damage": SPIDER["dmg"], "effect_name": "darkness", "effect_duration": 2},
        "minecraft:fire_immune": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True, "breathes_water": True},
        "minecraft:damage_sensor": {"triggers": immunities(["fall"])},
        "minecraft:loot": {"table": f"loot_tables/{NS}/spider.json"},
        "minecraft:experience_reward": {"on_death": "query.last_hit_by_player ? 6 : 0"},
        "minecraft:nameable": {},
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 2, "must_see": True, "reselect_targets": True, "within_radius": 20,
            "entity_types": [{"filters": fam("player", "snowgolem", "irongolem"), "max_dist": 24}]},
        "minecraft:behavior.melee_box_attack": {"priority": 3, "track_target": True},
        "minecraft:behavior.leap_at_target": {"priority": 4, "must_be_on_ground": False, "yd": 0.45},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 1.0},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8},
        "minecraft:behavior.random_look_around": {"priority": 8},
    }
    return {"format_version": "1.26.0", "minecraft:entity": {
        "description": {"identifier": f"{NS}:{ident('spider', color)}", "is_spawnable": True, "is_summonable": True,
                        "spawn_category": "monster", "properties": base["properties"]},
        "component_groups": base["groups"], "components": comps, "events": base["events"]}}


def summoner_behavior(src_zombie, color):
    d = patch_mob(src_zombie, "zombie", color)
    e = d["minecraft:entity"]
    e["description"]["identifier"] = f"{NS}:{ident('summoner', color)}"
    e["description"]["properties"][f"{NS}:action"] = {"type": "int", "range": [0, 3], "default": 0,
                                                       "client_sync": True}

    def fix(k, v, parent):
        if k == "minecraft:type_family" and "soul_summoner" not in v["family"]:
            v["family"].append("soul_summoner")
    walk(e, fix)
    e["components"]["minecraft:health"] = {"value": 30, "max": 30}
    return d


def titan_behavior(src_creeper):
    d = patch_mob(src_creeper, "creeper", "blue")
    e = d["minecraft:entity"]
    e["description"]["identifier"] = f"{NS}:{TITAN}"

    def fix(k, v, parent):
        if k == "minecraft:collision_box":
            v.update({"width": 0.8, "height": 2.2})
        elif k == "minecraft:type_family" and "soul_titan" not in v["family"]:
            v["family"].append("soul_titan")
    walk(e, fix)
    comps = e["components"]
    comps["minecraft:health"] = {"value": TITAN_INFO["hp"], "max": TITAN_INFO["hp"]}
    comps["minecraft:knockback_resistance"] = {"value": 0.5}
    # its own spawn blast must not hurt it
    comps["minecraft:damage_sensor"]["triggers"] += [{"cause": "entity_explosion", "deals_damage": "no"},
                                                      {"cause": "block_explosion", "deals_damage": "no"}]
    return d


def caped_behavior(src_skeleton):
    """A vanilla skeleton (from the original file) with a 2-arrow burst."""
    d = copy.deepcopy(src_skeleton)
    e = d["minecraft:entity"]
    e["description"]["identifier"] = f"{NS}:{CAPED}"
    comps = e["components"]
    comps["minecraft:burns_in_daylight"] = {}
    comps["minecraft:loot"] = {"table": "loot_tables/entities/skeleton.json"}
    comps["minecraft:equipment"] = {"table": "loot_tables/entities/skeleton_gear.json",
                                    "slot_drop_chance": [{"slot": "slot.weapon.mainhand", "drop_chance": 0.085}]}

    def fix(k, v, parent):
        if k == "minecraft:behavior.ranged_attack":
            v.update({"burst_shots": 2, "burst_interval": 0.25})
    walk(e, fix)
    return d


# ================================================================= clients
def spider_client(color, egg):
    mob = ident("spider", color)
    desc = {
        "identifier": f"{NS}:{mob}",
        "materials": {"default": "outline_base", "outline_main": "outline_main"},
        "textures": {"default": f"{TEX}/{mob}", "outline_main": OUTLINE_TEX},
        "geometry": {"default": "geometry.eu.sc.soul_corrupted_spider",
                     "outline_main": "geometry.eu.sc.soul_corrupted_spider.outline"},
        "spawn_egg": egg,
        "scripts": {"initialize": ["variable.s_speed = 0.0;"],
                    "pre_animation": ["variable.s_speed = math.lerp(variable.s_speed, query.modified_move_speed, 0.1);"],
                    "animate": ["move", "soul", "particles", "emitter_particle_controller"]},
        "animations": {"default_leg_pose": "animation.spider.default_leg_pose",
                       "look_at_target": "animation.spider.look_at_target",
                       "walk": "animation.spider.walk",
                       "move": "controller.animation.spider.move",
                       "spider_spawn": f"{A}.spider_spawn", "spider_life": f"{A}.spider_life",
                       "soul": f"controller.animation.{NS}.spider", "particles": f"{A}.particles",
                       "emitter_particle_controller": "controller.animation.eu.emitter_particle"},
        "particle_effects": {"emitter": f"{NS}:soul_ascending_particle" + ("" if color == "blue" else f"_{color}"),
                             "wisps": f"{NS}:wisp_{color}", "drips": f"{NS}:drip_{color}",
                             "burst": f"{NS}:burst_{color}"},
        "render_controllers": ["controller.render.eu_sc.outline_base.glow", "controller.render.eu_sc.outline_main.glow"],
    }
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def summoner_client(src_zombie_client, color):
    client = copy.deepcopy(src_zombie_client)
    mob = ident("summoner", color)
    desc = client["minecraft:client_entity"]["description"]
    desc["identifier"] = f"{NS}:{mob}"
    desc["textures"]["default"] = f"{TEX}/{mob}"
    desc["geometry"] = {"default": "geometry.eu.sc.soul_corrupted_summoner",
                        "outline_main": "geometry.eu.sc.soul_corrupted_summoner.outline"}
    desc["spawn_egg"] = {"base_color": hexcol(recolor_rgb(hx("#9DF2FF"), color)),
                         "overlay_color": hexcol(recolor_rgb(hx("#E8D9A0"), color))}
    add_soul_extras(desc, "zombie", color)
    desc["animations"].update({"cape_sway": f"{A}.cape_sway", "summoner_cast": f"{A}.summoner_cast",
                               "summoner": f"controller.animation.{NS}.summoner"})
    desc["scripts"]["animate"].append("summoner")
    return client


def titan_client(src_creeper_client):
    client = copy.deepcopy(src_creeper_client)
    desc = client["minecraft:client_entity"]["description"]
    desc["identifier"] = f"{NS}:{TITAN}"
    desc["textures"]["default"] = f"{TEX}/{TITAN}"
    desc["geometry"]["default"] = f"geometry.eu.sc.{TITAN}"
    desc["geometry"]["outline_main"] = f"geometry.eu.sc.{TITAN}.outline"
    desc["spawn_egg"] = {"base_color": "#1B2A55", "overlay_color": "#FFFFFF"}
    add_soul_extras(desc, "creeper", "blue")
    return client


def caped_client(src_skeleton_client, egg):
    """The original skeleton client file (a vanilla copy, format 1.8.0) pointed
    back at the vanilla skeleton model/texture, plus the cape."""
    client = copy.deepcopy(src_skeleton_client)
    desc = client["minecraft:client_entity"]["description"]
    desc["identifier"] = f"{NS}:{CAPED}"
    desc["materials"] = {"default": "skeleton", "cape": "entity_alphatest"}
    desc["textures"] = {"default": "textures/entity/skeleton/skeleton", "cape": f"{TEX}/{CAPED}_cape"}
    desc["geometry"] = {"default": "geometry.skeleton", "cape": "geometry.eu.sc.caped_skeleton_cape"}
    desc["render_controllers"] = ["controller.render.skeleton", f"controller.render.{NS}.cape"]
    desc["spawn_egg"] = egg
    desc.pop("particle_effects", None)
    desc["animation_controllers"] = [c for c in desc.get("animation_controllers", [])
                                     if "emitter_particle_controller" not in c]
    desc["animation_controllers"].append({"cape": f"controller.animation.{NS}.cape"})
    desc["animations"]["cape_sway"] = f"{A}.cape_sway"
    return client


RENDER_CONTROLLERS = {f"controller.render.{NS}.cape": {
    "geometry": "Geometry.cape", "materials": [{"*": "Material.cape"}], "textures": ["Texture.cape"]}}

SOUNDS = {
    "spider": {"events": {"ambient": "mob.spider.say", "hurt": "mob.spider.say", "death": "mob.spider.death",
                          "step": {"sound": "mob.spider.step", "volume": 0.35}}, "pitch": [0.7, 0.85], "volume": 1.0},
}


def lang(es, colors):
    lines = []

    def add(identifier, name):
        lines.append(f"entity.{NS}:{identifier}.name={name}")
        lines.append(f"item.spawn_egg.entity.{NS}:{identifier}.name={'Generar ' if es else 'Spawn '}{name}")

    for kind, info in (("spider", SPIDER), ("summoner", SUMMONER)):
        for color, C in colors.items():
            base = info["es"] if es else info["en"]
            add(ident(kind, color), base if color == "blue" else f"{base} ({C['es'] if es else C['en']})")
    add(TITAN, TITAN_INFO["es"] if es else TITAN_INFO["en"])
    add(CAPED, CAPED_INFO["es"] if es else CAPED_INFO["en"])
    return lines
