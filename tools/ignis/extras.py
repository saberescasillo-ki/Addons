"""Additions to the Ignis add-on, used by tools/ignis_fix.py:

  * minions: Ignis' Blackstone Squires, a small copy of its armour (its own model)
    in blackstone, glowing fire or soul like Ignis' phase; immune to Ignis' attacks;
  * soul strike sigils: the damaging fire circle in the soul-sand colours of the
    great rune, used in the soul phases;
  * the death sequence: Ignis kneels, sinks burning into the ground and bursts;
  * relic chests for the Temple of Ignis: they burst open with their loot once.
"""
import colorsys
import os
import random

from PIL import Image

from dungeons_mobs import dump, load

MINION = "ignis:ignis_minion"
CHEST = "ignis:relic_chest"
FRAMES = 4  # animated glow frames per colour (Ignis has 8)

PLAYER_IN_PLAY = {"all_of": [{"test": "is_family", "subject": "other", "value": "player"},
                             {"any_of": [{"test": "has_tag", "subject": "other", "value": "ignis:gm_survival"},
                                         {"test": "has_tag", "subject": "other", "value": "ignis:gm_adventure"}]}]}
GOLEMS = {"any_of": [{"test": "is_family", "subject": "other", "value": "irongolem"},
                     {"test": "is_family", "subject": "other", "value": "snowgolem"}]}


def _edit(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def _lang(rp, lines):
    path = os.path.join(rp, "texts", "en_US.lang")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    add = [line for line in lines if line.split("=")[0] + "=" not in text]
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write("\n".join(add) + "\n")


# --- Minions -------------------------------------------------------------------------
def _blackstone(img):
    """Ignis' nether-brick armour becomes blackstone; its fire and gold stay."""
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if not a:
                continue
            _, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if light < 0.45 and (r > g or sat < 0.2):
                v = light * 0.85
                px[x, y] = (int(v * 0.95 * 255), int(v * 0.95 * 255), min(255, int(v * 1.1 * 255)), a)
    return img


def add_minion(bp, rp):
    tex = os.path.join(rp, "textures", "ignis", "entity")
    textures = {}
    for colour, src in (("fire", "ignis_idle_{}"), ("soul", "ignis_soul_idle_{}")):
        for i in range(FRAMES):
            name = f"minion_{colour}_{i}"
            _blackstone(Image.open(os.path.join(tex, src.format(i * 2) + ".png"))).save(
                os.path.join(tex, name + ".png"), optimize=True)
            textures[f"{colour}{i}"] = f"textures/ignis/entity/{name}"

    dump(os.path.join(bp, "entities", "ignis_minion.json"), {
        "format_version": "1.20.40",
        "minecraft:entity": {
            "description": {"identifier": MINION, "is_spawnable": True, "is_summonable": True},
            "component_groups": {
                "soul": {"minecraft:skin_id": {"value": 1},
                         "minecraft:health": {"value": 40, "max": 40},
                         "minecraft:attack": {"damage": 7}},
            },
            "components": {
                # family ignis:ignis: every attack of Ignis skips it (selectors, sigils,
                # fireballs and Ignis' own damage sensor all filter on it)
                "minecraft:type_family": {"family": ["ignis:ignis", "ignis_minion", "monster", "mob"]},
                "minecraft:skin_id": {"value": 0},
                "minecraft:health": {"value": 30, "max": 30},
                "minecraft:attack": {"damage": 5},
                "minecraft:scale": {"value": 0.45},
                "minecraft:collision_box": {"width": 1.6, "height": 3.25},
                "minecraft:movement": {"value": 0.3},
                "minecraft:navigation.walk": {"can_path_over_lava": True, "can_walk_in_lava": True,
                                              "avoid_water": True, "can_open_doors": False},
                "minecraft:movement.basic": {},
                "minecraft:jump.static": {},
                "minecraft:can_climb": {},
                "minecraft:follow_range": {"value": 64, "max": 64},
                "minecraft:fire_immune": {},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
                "minecraft:knockback_resistance": {"value": 0.3},
                "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
                "minecraft:persistent": {},
                "minecraft:experience_reward": {"on_death": "q.last_hit_by_player ? 5 : 0"},
                "minecraft:damage_sensor": {"triggers": [
                    {"on_damage": {"filters": {"test": "is_family", "subject": "other", "value": "ignis:ignis"}},
                     "deals_damage": False},
                    {"cause": "fall", "deals_damage": False}]},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.25, "track_target": True},
                "minecraft:behavior.hurt_by_target": {"priority": 1, "entity_types": {
                    "filters": {"any_of": [PLAYER_IN_PLAY, GOLEMS]}}},
                "minecraft:behavior.nearest_attackable_target": {
                    "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 64,
                    "entity_types": [{"filters": {"any_of": [PLAYER_IN_PLAY, GOLEMS]}, "max_dist": 64}]},
                "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
                "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8},
                "minecraft:behavior.random_look_around": {"priority": 8},
            },
            "events": {"soul": {"add": {"component_groups": ["soul"]}}},
        }})

    dump(os.path.join(rp, "entity", "ignis_minion.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": MINION,
            "materials": {"default": "entity_alphatest"},
            "textures": textures,
            "geometry": {"default": "geometry.ignis.ignis"},
            "animations": {
                "hover": "animation.ignis.minion.hover",
                "sway": "animation.ignis.ignis.generala",
                "look": "animation.common.look_at_target",
                "hurt": "animation.ignis.minion.hurt",
                "swing": "animation.ignis.minion.swing",
                "attack": "controller.animation.ignis.minion.attack",
            },
            "scripts": {"animate": ["hover", "sway", "look", {"hurt": "q.hurt_time > 0"}, "attack"]},
            "render_controllers": ["controller.render.ignis.minion"],
            "spawn_egg": {"base_color": "#2b272c", "overlay_color": "#ffae1a"},
        }}})
    dump(os.path.join(rp, "render_controllers", "ignis_minion.render_controllers.json"), {
        "format_version": "1.10.0",
        "render_controllers": {"controller.render.ignis.minion": {
            "arrays": {"textures": {
                "Array.fire": [f"Texture.fire{i}" for i in range(FRAMES)],
                "Array.soul": [f"Texture.soul{i}" for i in range(FRAMES)]}},
            "geometry": "Geometry.default",
            "materials": [{"*": "Material.default"}],
            "textures": ["q.skin_id == 1 ? Array.soul[q.life_time * 6] : Array.fire[q.life_time * 6]"],
            # no shield, short horns, no big shoulder spikes: a squire, not a lord
            "part_visibility": [{"shield_root": False}, {"right_horn2": False}, {"left_horn2": False},
                                {"right_big_spike": False}, {"left_big_spike": False}],
        }}})
    dump(os.path.join(rp, "animations", "ignis_minion.animation.json"), {
        "format_version": "1.10.0",
        "animations": {
            "animation.ignis.minion.hover": {"loop": True, "bones": {
                "root": {"position": [0, "Math.sin(q.life_time * 160) * 0.8", 0]},
                "upperbody": {"rotation": ["math.clamp(q.modified_move_speed * 40, 0, 18)", 0, 0]}}},
            "animation.ignis.minion.hurt": {"loop": True, "bones": {
                "upperbody": {"rotation": ["-Math.sin(q.hurt_time * 18) * 14", 0, 0]},
                "head": {"rotation": ["-Math.sin(q.hurt_time * 18) * 10", 0, 0]}}},
            "animation.ignis.minion.swing": {"animation_length": 0.6, "bones": {
                "right_arm_joint": {"rotation": {"0.0": [0, 0, 0], "0.15": [-125, 0, 20],
                                                 "0.3": [35, 0, -10], "0.6": [0, 0, 0]}},
                "upperbody": {"rotation": {"0.0": [0, 0, 0], "0.15": [0, -18, 0], "0.3": [6, 22, 0],
                                           "0.6": [0, 0, 0]}}}},
        }})
    dump(os.path.join(rp, "animation_controllers", "ignis_minion.ac.json"), {
        "format_version": "1.10.0",
        "animation_controllers": {"controller.animation.ignis.minion.attack": {
            "initial_state": "default",
            "states": {
                "default": {"transitions": [{"swing": "v.attack_time > 0"}]},
                "swing": {"animations": ["swing"], "transitions": [{"default": "q.all_animations_finished"}],
                          "sound_effects": [{"effect": "sword"}]},
            }}}})
    _edit(os.path.join(rp, "entity", "ignis_minion.entity.json"),
          lambda d: d["minecraft:client_entity"]["description"].update(
              sound_effects={"sword": "ignis.mob.ignis.sword"}))
    _lang(rp, ["entity.ignis:ignis_minion.name=Blackstone Squire",
               "item.spawn_egg.entity.ignis:ignis_minion.name=Spawn Blackstone Squire"])


# --- Soul strike sigils ----------------------------------------------------------------
def soul_strikes(bp, rp):
    """ignis:ignis_strike can turn soul-coloured (event "soul", skin 1)."""
    def beh(d):
        e = d["minecraft:entity"]
        e["components"]["minecraft:skin_id"] = {"value": 0}
        e["component_groups"]["soul"] = {"minecraft:skin_id": {"value": 1}}
        e["events"]["soul"] = {"add": {"component_groups": ["soul"]}}
    _edit(os.path.join(bp, "entities", "ignis_strike.json"), beh)

    def cli(d):
        desc = d["minecraft:client_entity"]["description"]
        desc["textures"]["soul"] = "textures/ignis/entity/soul_flame_strike_sigil"
        desc["particle_effects"]["particle_soul"] = "ignis:ignis_strike_soul"
        desc["animations"]["particles"] = "controller.animation.ignis.strike.colour"
        desc["render_controllers"] = ["controller.render.ignis.strike"]
    _edit(os.path.join(rp, "entity", "ignis_strike.entity.json"), cli)
    dump(os.path.join(rp, "render_controllers", "ignis_strike.render_controllers.json"), {
        "format_version": "1.10.0",
        "render_controllers": {"controller.render.ignis.strike": {
            "geometry": "Geometry.default",
            "materials": [{"*": "Material.default"}],
            "textures": ["q.skin_id == 1 ? Texture.soul : Texture.default"],
            "ignore_lighting": True}}})
    # the colour is set right after spawning: wait a moment before choosing the flames
    dump(os.path.join(rp, "animation_controllers", "ignis_strike_colour.ac.json"), {
        "format_version": "1.10.0",
        "animation_controllers": {"controller.animation.ignis.strike.colour": {
            "initial_state": "default",
            "states": {
                "default": {"transitions": [{"soul": "q.skin_id == 1"}, {"fire": "q.life_time > 0.1"}]},
                "fire": {"particle_effects": [{"effect": "particle"}], "transitions": [{"soul": "q.skin_id == 1"}]},
                "soul": {"particle_effects": [{"effect": "particle_soul"}]},
            }}}})


# --- Death -------------------------------------------------------------------------------
DEATH_LENGTH = 5.0


def death(bp, rp):
    """Ignis could die like any mob (its health had no floor) before the sensor that
    starts its death scene noticed: health now stops at 1 and the scene always
    plays. The scene goes on after the last stab: Ignis sinks burning into the
    ground until it bursts (the script adds the flames and the burst)."""
    _edit(os.path.join(bp, "entities", "ignis.json"),
          lambda d: d["minecraft:entity"]["components"]["minecraft:health"].update(min=1))

    def anim(d):
        for name in ("deatha", "deathb", "deathc"):
            a = d["animations"][f"animation.ignis.ignis.{name}"]
            a["animation_length"] = DEATH_LENGTH
            root = a["bones"].setdefault("root", {})
            root["position"] = {"0.0": [0, 0, 0], "2.4": [0, 0, 0], "3.4": [0, -6, 0],
                                "4.6": [0, -34, 0], str(DEATH_LENGTH): [0, -44, 0]}
            body = a["bones"].setdefault("upperbody", {})
            rot = body.get("rotation")
            if isinstance(rot, dict):
                last = rot[max(rot, key=float)]
                rot["3.2"] = last
                rot["4.6"] = [last[0] - 18, last[1], last[2] + 6] if isinstance(last, list) else last
    _edit(os.path.join(rp, "animations", "ignis.animation.json"), anim)


# --- Relic chests ---------------------------------------------------------------------------
def _chest_texture(path):
    """64x64 box-UV texture: polished blackstone, gold trim, lava seams."""
    rng = random.Random(11)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    px = img.load()

    def stone(x, y):
        v = rng.randint(30, 52)
        return (v, v - 3, v + 4, 255)

    regions = [(0, 0, 56, 24, 14), (0, 24, 56, 18, 14), (56, 0, 6, 5, 1)]  # body, lid, lock
    for u, v, w, h, d in regions:
        for y in range(v, v + h):
            for x in range(u, u + w):
                px[x, y] = stone(x, y)
        if w == 6:  # the lock: gold with a lava keyhole
            for y in range(v, v + h):
                for x in range(u, u + w):
                    px[x, y] = (232, 180, 48, 255) if (x + y) % 3 else (255, 214, 92, 255)
            px[u + 1, v + 3] = px[u + 4, v + 3] = (255, 96, 16, 255)
            continue
        # gold rims along every face edge of the box layout
        side_top = v + d
        for x in range(u, u + w):
            for y in (side_top, v + h - 1):
                px[x, y] = (214, 160, 40, 255)
        for x in range(u + d, u + d + w // 2 - d):
            px[x, v] = px[x, v + d - 1] = (214, 160, 40, 255)
        # glowing lava seams on the sides
        for _ in range(w // 3 if v + h - 2 > side_top + 2 else 0):
            x = rng.randrange(u, u + w)
            y = rng.randrange(side_top + 2, v + h - 2)
            for k in range(rng.randint(2, 4)):
                if side_top < y + k < v + h - 1:
                    px[x, y + k] = (255, 120 + 30 * k, 20, 255)
    img.save(path, optimize=True)


def relic_chests(bp, rp, loot_table):
    tex = os.path.join(rp, "textures", "ignis", "blocks")
    os.makedirs(tex, exist_ok=True)
    _chest_texture(os.path.join(tex, "relic_chest.png"))

    def terrain(d):
        d["texture_data"]["ignis:relic_chest"] = {"textures": "textures/ignis/blocks/relic_chest"}
    _edit(os.path.join(rp, "textures", "terrain_texture.json"), terrain)
    _edit(os.path.join(rp, "blocks.json"), lambda d: d.update({CHEST: {"sound": "stone"}}))
    dump(os.path.join(rp, "models", "blocks", "relic_chest.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.ignis.relic_chest", "texture_width": 64, "texture_height": 64,
                            "visible_bounds_width": 2, "visible_bounds_height": 2.5,
                            "visible_bounds_offset": [0, 0.75, 0]},
            "bones": [
                {"name": "body", "pivot": [0, 0, 0], "cubes": [{"origin": [-7, 0, -7], "size": [14, 10, 14], "uv": [0, 0]}]},
                {"name": "lid", "pivot": [0, 10, 7], "cubes": [
                    {"origin": [-7, 10, -7], "size": [14, 4, 14], "uv": [0, 24]},
                    {"origin": [-1, 7, -8], "size": [2, 4, 1], "uv": [56, 0]}]},
                {"name": "lid_open", "pivot": [0, 10, 7], "rotation": [-105, 0, 0], "cubes": [
                    {"origin": [-7, 10, -7], "size": [14, 4, 14], "uv": [0, 24]},
                    {"origin": [-1, 7, -8], "size": [2, 4, 1], "uv": [56, 0]}]},
            ]}]})
    yaw = {"north": 180, "south": 0, "east": 90, "west": 270}
    perms = [{"condition": f"q.block_state('minecraft:cardinal_direction') == '{d}'",
              "components": {"minecraft:transformation": {"rotation": [0, r, 0]}}} for d, r in yaw.items()]
    for is_open in (False, True):
        perms.append({"condition": f"q.block_state('ignis:open') == {str(is_open).lower()}",
                      "components": {
                          "minecraft:geometry": {"identifier": "geometry.ignis.relic_chest",
                                                 "bone_visibility": {"lid": not is_open, "lid_open": is_open}},
                          "minecraft:light_emission": 3 if is_open else 7}})
    dump(os.path.join(bp, "blocks", "relic_chest.json"), {
        "format_version": "1.21.80",
        "minecraft:block": {
            "description": {
                "identifier": CHEST,
                "menu_category": {"category": "items"},
                "states": {"ignis:open": [False, True]},
                "traits": {"minecraft:placement_direction": {"enabled_states": ["minecraft:cardinal_direction"]}},
            },
            "components": {
                "minecraft:geometry": "geometry.ignis.relic_chest",
                "minecraft:material_instances": {"*": {"texture": "ignis:relic_chest", "render_method": "alpha_test"}},
                "minecraft:collision_box": {"origin": [-7, 0, -7], "size": [14, 14, 14]},
                "minecraft:selection_box": {"origin": [-7, 0, -7], "size": [14, 14, 14]},
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 4},
                "minecraft:destructible_by_explosion": {"explosion_resistance": 1200},
                "minecraft:loot": "loot_tables/empty.json",
                "minecraft:map_color": "#2b272c",
                "minecraft:custom_components": ["ignis:relic_chest"],
            },
            "permutations": perms,
        }})
    dump(os.path.join(bp, "loot_tables", "empty.json"), {"pools": []})
    _lang(rp, [f"tile.{CHEST}.name=§6Relic Chest of Ignis§r"])
    return loot_table


# --- Lighter sigils ----------------------------------------------------------------------
# The strike sigils' flames were 128 (fire) and 256 (soul) particles a second, up to
# 1024 alive per circle: 19-27 circles at once lagged phones. Now a few, a bit bigger.
SIGIL_FLAMES = {"ignis_strike.particle.json": 18, "ignis_strike_soul.particle.json": 22}


def lighter_sigils(rp):
    for name, rate in SIGIL_FLAMES.items():
        def f(d, rate=rate):
            c = d["particle_effect"]["components"]
            c["minecraft:emitter_rate_steady"] = {"spawn_rate": rate, "max_particles": rate * 2}
            size = "(0.15 + variable.particle_random_1*0.1) - (0.15 * variable.particle_age)"
            c["minecraft:particle_appearance_billboard"]["size"] = [size, size]
        _edit(os.path.join(rp, "particles", name), f)


# --- Fire lines ----------------------------------------------------------------------------
def _soft_dot(path, size=16):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    c = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5 / (size / 2)
            if d < 1:
                px[x, y] = (255, 255, 255, int(255 * min(1, (1 - d) * 1.6)))
    img.save(path)


def _wave(identifier, uv):
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": identifier, "basic_render_parameters": {
            "material": "particles_alpha", "texture": "textures/particle/particles"}},
        "components": {
            "minecraft:emitter_rate_instant": {"num_particles": 6},
            "minecraft:emitter_lifetime_once": {"active_time": 0.1},
            "minecraft:emitter_shape_box": {"half_dimensions": [0.7, 0.1, 0.7], "direction": "outwards"},
            "minecraft:particle_lifetime_expression": {"max_lifetime": "Math.random(0.35, 0.6)"},
            "minecraft:particle_initial_speed": "Math.random(0.5, 1.5)",
            "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 6, 0], "linear_drag_coefficient": 2},
            "minecraft:particle_appearance_billboard": {
                "size": ["0.35 - 0.3 * v.particle_age / v.particle_lifetime",
                         "0.35 - 0.3 * v.particle_age / v.particle_lifetime"],
                "facing_camera_mode": "rotate_xyz",
                "uv": {"texture_width": 128, "texture_height": 128, "uv": uv, "uv_size": [8, 8]}},
            "minecraft:particle_appearance_lighting": {}}}}


def fire_lines(rp):
    """Particles of the fire-lines attack: the marks on the ground and the waves."""
    tex = os.path.join(rp, "textures", "ignis", "particle")
    os.makedirs(tex, exist_ok=True)
    _soft_dot(os.path.join(tex, "fire_line.png"))
    dump(os.path.join(rp, "particles", "fire_line.particle.json"), {
        "format_version": "1.10.0", "particle_effect": {
            "description": {"identifier": "ignis:fire_line", "basic_render_parameters": {
                "material": "particles_blend", "texture": "textures/ignis/particle/fire_line"}},
            "components": {
                "minecraft:emitter_rate_instant": {"num_particles": 1},
                "minecraft:emitter_lifetime_once": {"active_time": 0.05},
                "minecraft:emitter_shape_point": {},
                "minecraft:particle_lifetime_expression": {"max_lifetime": 1.0},
                "minecraft:particle_appearance_billboard": {
                    "size": ["0.42 + 0.08 * v.particle_age", "0.42 + 0.08 * v.particle_age"],
                    "facing_camera_mode": "emitter_transform_xz",
                    "uv": {"texture_width": 16, "texture_height": 16, "uv": [0, 0], "uv_size": [16, 16]}},
                # brightens as the strike nears, then fades
                "minecraft:particle_appearance_tinting": {"color": [
                    "variable.color.r", "variable.color.g", "variable.color.b",
                    "math.min(1, 0.5 + v.particle_age * 0.6) * math.clamp((1 - v.particle_age) / 0.12, 0, 1)"]}}}})
    # same flames as the sigils (vanilla flame / the soul flame the add-on uses)
    dump(os.path.join(rp, "particles", "fire_wave.particle.json"), _wave("ignis:fire_wave", [0, 24]))
    dump(os.path.join(rp, "particles", "fire_wave_soul.particle.json"), _wave("ignis:fire_wave_soul", [16, 24]))
