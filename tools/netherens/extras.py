"""Additions to Netherens, used by tools/netherens_fix.py:

  * Soul Knights: the Nether Lord's own model, smaller, crownless and with one
    sword, in soul-steel colours; the boss calls them now and then
    (tools/netherens/minions.js) and none of its attacks hurt them;
  * a better walk (the walk cycle divided by an undefined variable, so the legs
    barely moved) and a hurt flinch for the Nether Lord.
"""
import colorsys
import os

from PIL import Image

from dungeons_mobs import dump, load

BOSS = "low:netherboss"
KNIGHT = "netherens:soul_knight"
TCOS = ("variable.gliding_speed_value = 1.0; variable.tcos0 = (Math.cos(query.modified_distance_moved * 38.17)"
        " * query.modified_move_speed / variable.gliding_speed_value) * 57.3;")
STRIDE = "Math.cos(q.modified_distance_moved * 38.17)"
SPEED = "math.clamp(q.modified_move_speed * 3, 0, 1)"


def _edit(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def _lang(rp, entries):
    for lang, lines in entries.items():
        path = os.path.join(rp, "texts", f"{lang}.lang")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        add = [line for line in lines if line.split("=")[0] + "=" not in text]
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write("\n".join(add) + "\n")


def _soul_steel(img):
    """The Lord's dark red nether-brick plates turn to cold soul steel."""
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if not a or not (r > g + 8 and r > b):
                continue
            _, light, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            v = min(1.0, light * 1.15)
            px[x, y] = (int(v * 0.55 * 255), int(v * 0.85 * 255), int(v * 0.95 * 255), a)
    return img


ANIMATIONS = {
    # walk: the hips bob, the torso counter-twists and leans, the head steadies
    "animation.netherboss.walk_extra": {"loop": True, "bones": {
        "All": {"position": [0, f"Math.abs({STRIDE}) * {SPEED} * -0.8", 0]},
        "upperBodyPart1": {"rotation": [f"{SPEED} * 7", f"{STRIDE} * {SPEED} * 7", f"{STRIDE} * {SPEED} * -2"]},
        "Head": {"rotation": [f"{SPEED} * -5", f"{STRIDE} * {SPEED} * -5", 0]},
        "Pelvis": {"rotation": [0, f"{STRIDE} * {SPEED} * -5", 0]},
    }},
    # hurt: a sharp flinch back that eases out (q.hurt_time counts 10 -> 0)
    "animation.netherboss.hurt": {"loop": True, "bones": {
        "upperBodyPart1": {"rotation": ["-Math.sin(q.hurt_time * 18) * 16", 0, "Math.sin(q.hurt_time * 18) * 4"]},
        "Head": {"rotation": ["-Math.sin(q.hurt_time * 18) * 12", 0, 0]},
        "leftArm": {"rotation": [0, 0, "-Math.sin(q.hurt_time * 18) * 12"]},
        "rightArm": {"rotation": [0, 0, "Math.sin(q.hurt_time * 18) * 12"]},
        "All": {"position": [0, 0, "Math.sin(q.hurt_time * 18) * 1.2"]},
    }},
    "animation.netherens.knight.swing": {"animation_length": 0.6, "bones": {
        "rightArm": {"rotation": {"0.0": [0, 0, 0], "0.2": [-150, 10, 15], "0.38": [25, -5, -10], "0.6": [0, 0, 0]}},
        "upperBodyPart1": {"rotation": {"0.0": [0, 0, 0], "0.2": [-6, -20, 0], "0.38": [8, 25, 0], "0.6": [0, 0, 0]}},
    }},
}


def animations(rp):
    dump(os.path.join(rp, "animations", "netherens_extra.animation.json"),
         {"format_version": "1.10.0", "animations": ANIMATIONS})

    def boss(d):
        desc = d["minecraft:client_entity"]["description"]
        desc["scripts"]["pre_animation"] = [TCOS]
        desc["animations"]["walk_extra"] = "animation.netherboss.walk_extra"
        desc["animations"]["hurt"] = "animation.netherboss.hurt"
        anim = desc["scripts"]["animate"]
        anim.append({"walk_extra": "query.skin_id != 3 && query.skin_id != 17"})
        anim.append({"hurt": "q.hurt_time > 0 && query.skin_id != 3 && query.skin_id != 17"})
    _edit(os.path.join(rp, "entity", "netherboss.entity.json"), boss)


def add_knights(bp, rp):
    tex = os.path.join(rp, "textures", "entity")
    _soul_steel(Image.open(os.path.join(tex, "netherboss.png"))).save(os.path.join(tex, "soul_knight.png"), optimize=True)
    players = {"test": "is_family", "subject": "other", "value": "player"}
    golems = {"any_of": [{"test": "is_family", "subject": "other", "value": "irongolem"},
                         {"test": "is_family", "subject": "other", "value": "snowgolem"}]}
    dump(os.path.join(bp, "entities", "soul_knight.json"), {
        "format_version": "1.20.40",
        "minecraft:entity": {
            "description": {"identifier": KNIGHT, "is_spawnable": True, "is_summonable": True},
            "components": {
                "minecraft:type_family": {"family": ["netherboss_minion", "monster", "undead", "mob"]},
                "minecraft:health": {"value": 40, "max": 40},
                "minecraft:attack": {"damage": 6, "effect_name": "wither", "effect_duration": 2},
                "minecraft:scale": {"value": 0.75},
                "minecraft:collision_box": {"width": 0.8, "height": 2.4},
                "minecraft:movement": {"value": 0.28},
                "minecraft:navigation.walk": {"can_path_over_lava": True, "avoid_water": True},
                "minecraft:movement.basic": {},
                "minecraft:jump.static": {},
                "minecraft:can_climb": {},
                "minecraft:follow_range": {"value": 64, "max": 64},
                "minecraft:fire_immune": {},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
                "minecraft:knockback_resistance": {"value": 0.4},
                "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0},
                "minecraft:persistent": {},
                "minecraft:experience_reward": {"on_death": "q.last_hit_by_player ? 6 : 0"},
                # nothing of the Lord's hurts them: its blades and beams (family
                # netherboss), its skulls' wither, its TNT, each other
                "minecraft:damage_sensor": {"triggers": [
                    {"on_damage": {"filters": {"any_of": [
                        {"test": "is_family", "subject": "other", "value": "netherboss"},
                        {"test": "is_family", "subject": "other", "value": "netherboss_minion"}]}},
                     "deals_damage": False},
                    {"cause": "entity_explosion", "deals_damage": False},
                    {"cause": "wither", "deals_damage": False},
                    {"cause": "fall", "deals_damage": False}]},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.melee_attack": {"priority": 2, "speed_multiplier": 1.2, "track_target": True},
                "minecraft:behavior.hurt_by_target": {"priority": 1, "entity_types": {
                    "filters": {"any_of": [players, golems]}}},
                "minecraft:behavior.nearest_attackable_target": {
                    "priority": 2, "must_see": False, "reselect_targets": True, "within_radius": 64,
                    "entity_types": [{"filters": {"any_of": [players, golems]}, "max_dist": 64}]},
                "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
                "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 8},
                "minecraft:behavior.random_look_around": {"priority": 8},
            },
        }})
    boss = load(os.path.join(rp, "entity", "netherboss.entity.json"))["minecraft:client_entity"]["description"]
    dump(os.path.join(rp, "entity", "soul_knight.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": KNIGHT,
            "materials": dict(boss["materials"]),
            "textures": {"default": "textures/entity/soul_knight"},
            "geometry": {"default": boss["geometry"]["default"]},
            "animations": {
                "idle": "animation.netherboss.setup",
                "move": "animation.netherboss.move",
                "walk_extra": "animation.netherboss.walk_extra",
                "look": "animation.humanoid.look_at_target.default",
                "hurt": "animation.netherboss.hurt",
                "swing": "animation.netherens.knight.swing",
                "attack": "controller.animation.netherens.knight.attack",
            },
            "scripts": {"pre_animation": [TCOS],
                        "animate": ["idle", "move", "walk_extra", "look", {"hurt": "q.hurt_time > 0"}, "attack"]},
            "particle_effects": {"cape": boss["particle_effects"]["cape"]},
            "sound_effects": {"swing": "mob.wither.shoot"},
            "render_controllers": ["controller.render.netherens.knight"],
            "spawn_egg": {"base_color": "#26383d", "overlay_color": "#4fd6e0"},
        }}})
    dump(os.path.join(rp, "render_controllers", "soul_knight.json"), {
        "format_version": "1.8.0",
        "render_controllers": {"controller.render.netherens.knight": {
            "geometry": "Geometry.default",
            "materials": [{"*": "Material.default"}],
            "textures": ["Texture.default"],
            "part_visibility": [{"Crown": False}, {"sword2": False}],  # no crown, a single sword
        }}})
    dump(os.path.join(rp, "animation_controllers", "soul_knight.json"), {
        "format_version": "1.10.0",
        "animation_controllers": {"controller.animation.netherens.knight.attack": {
            "initial_state": "default",
            "states": {
                "default": {"transitions": [{"swing": "v.attack_time > 0"}]},
                "swing": {"animations": ["swing"], "transitions": [{"default": "q.all_animations_finished"}]},
            }}}})
    _lang(rp, {
        "en_US": [f"entity.{KNIGHT}.name=Soul Knight", f"item.spawn_egg.entity.{KNIGHT}.name=Spawn Soul Knight"],
        "es_ES": [f"entity.{KNIGHT}.name=Caballero de Almas", f"item.spawn_egg.entity.{KNIGHT}.name=Generar Caballero de Almas"],
        "es_MX": [f"entity.{KNIGHT}.name=Caballero de Almas", f"item.spawn_egg.entity.{KNIGHT}.name=Generar Caballero de Almas"],
    })
