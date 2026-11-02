"""Builds "Animaciones Suaves": a resource pack that smooths the player's
abrupt animation changes (sneaking, item switch, mounting, shield, bow,
spyglass...) so they blend over a few frames instead of snapping.

How it works: vanilla player animations are switched on and off with blend
weights that are 0 or 1 (e.g. {"sneaking": "query.is_sneaking"}), so the pose
jumps in a single frame. This pack adds, in the player's pre_animation script,
one variable per animation that moves from 0 to 1 (and back) over DURATIONS
seconds using query.delta_time (same speed at any frame rate), eased with a
smoothstep curve. The animation controller then uses those variables as blend
weights.

The files are the vanilla ones from Minecraft 1.26.60 (sources/vanilla_player_1.26.60,
from github.com/Mojang/bedrock-samples) with only those changes, so geometry,
textures, render controllers, persona and Marketplace skins work as in vanilla.

    python3 tools/smooth_animations.py      # regenerate the pack and the .mcpack
"""
import json
import os
import re
import shutil
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources", "vanilla_player_1.26.60")
RP = os.path.join(ROOT, "SmoothAnimations_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 26, 0]
UUIDS = dict(rp="52ee589c-ac10-4f69-818c-6d27bce78aa0", rp_res="b70c157b-5b10-4813-9a33-ef6bf87622b6")

# Seconds each transition takes (0 -> 1 and 1 -> 0).
DURATIONS = dict(
    sneak=0.16,       # agacharse / levantarse
    ride=0.25,        # montar / desmontar
    hold_r=0.14,      # brazo derecho: mano vacia <-> objeto
    hold_l=0.14,      # brazo izquierdo: mano vacia <-> objeto
    trident=0.14,     # apuntar el tridente
    charge=0.14,      # cargar (ataque cargado)
    spyglass=0.14,    # catalejo
    horn=0.14,        # cuerno de cabra
    brush=0.14,       # pincel
    bow=0.12,         # tensar el arco
    shield_main=0.10, # escudo en la mano principal
    shield_off=0.10,  # escudo en la otra mano
)
ARM_DROP = 0.08       # 1a persona: tiempo que tarda el brazo en bajar al cambiar de objeto
CONTROLLER_BLEND = 0.15  # blend_transition para los estados de ballesta y lanza en 3a persona

# Condition that switches each smoothed animation on (copied from the vanilla controller).
TARGETS = dict(
    sneak="query.is_sneaking && !query.is_sleeping",
    ride="query.is_riding",
    hold_r="variable.is_holding_right ?? 0.0",
    hold_l="variable.is_holding_left ?? 0.0",
    trident="variable.is_brandishing_spear ?? 0.0",
    charge="query.is_charging",
    spyglass="variable.is_holding_spyglass ?? 0.0",
    horn="variable.is_tooting_goat_horn ?? 0.0",
    brush="variable.is_using_brush ?? 0.0",
    bow="query.get_equipped_item_name == 'bow' && ((variable.item_use_normalized ?? 0.0) > 0.0 && "
        "(variable.item_use_normalized ?? 0.0) < 1.0)",
    shield_main="query.blocking && query.get_equipped_item_name('off_hand') != 'shield' && "
                "query.get_equipped_item_name == 'shield'",
    shield_off="query.blocking && query.get_equipped_item_name('off_hand') == 'shield'",
)

# Blend weights in controller.animation.player.root, state third_person.
THIRD_PERSON_WEIGHTS = {
    "riding.root": "variable.sa_ride",
    "riding.arms": "variable.sa_ride",
    "riding.legs": "variable.sa_ride",
    "brandish_spear": "variable.sa_trident",
    "holding_spyglass": "variable.sa_spyglass",
    "charging": "variable.sa_charge",
    "sneaking": "variable.sa_sneak",
    "bob": "1.0 - math.max(variable.sa_spyglass, math.max(variable.sa_horn, variable.sa_brush))",
    "shield_block_main_hand": "variable.sa_shield_main",
    "shield_block_off_hand": "variable.sa_shield_off",
    "third_person_bow_equipped": "variable.sa_bow",
    "tooting_goat_horn": "variable.sa_horn",
    "brushing": "variable.sa_brush",
}


def load(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        text = f.read()
    return json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.M))


def save(rel, data):
    path = os.path.join(RP, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ease(var):
    return f"variable.{var} * variable.{var} * (3.0 - 2.0 * variable.{var})"


def ramp_script(key, duration):
    """variable.sa_<key>_t moves linearly towards the target; variable.sa_<key> is the eased value."""
    raw = f"sa_{key}_t"
    step = f"math.clamp(query.delta_time, 0.0, 0.25) / {duration}"
    return (f"temp.sa_target = ({TARGETS[key]}) ? 1.0 : 0.0; "
            f"variable.{raw} = temp.sa_target > variable.{raw} ? math.min(variable.{raw} + {step}, 1.0) "
            f": math.max(variable.{raw} - {step}, 0.0); "
            f"variable.sa_{key} = {ease(raw)};")


def build_entity():
    data = load("player.entity.json")
    scripts = data["minecraft:client_entity"]["description"]["scripts"]
    for key in DURATIONS:
        scripts["initialize"] += [f"variable.sa_{key}_t = 0.0;", f"variable.sa_{key} = 0.0;"]
    scripts["initialize"] += ["variable.sa_arm = 1.0;", "variable.sa_arm_ok = 0.0;"]
    scripts["pre_animation"] += [ramp_script(k, d) for k, d in DURATIONS.items()]
    # First person item switch: the engine drops player_arm_height to 0 at once and raises it again;
    # here the arm goes down in ARM_DROP seconds instead and follows the engine on the way up.
    # If player_arm_height cannot be read here, sa_arm_ok stays 0 and the animation uses the engine value.
    scripts["pre_animation"].append(
        "variable.sa_arm_ok = (variable.player_arm_height ?? -1.0) >= 0.0; "
        "temp.sa_h = math.clamp(variable.player_arm_height ?? 1.0, 0.0, 1.0); "
        f"variable.sa_arm = temp.sa_h >= variable.sa_arm ? temp.sa_h "
        f": math.max(temp.sa_h, variable.sa_arm - math.clamp(query.delta_time, 0.0, 0.25) / {ARM_DROP});")
    save("entity/player.entity.json", data)


def build_controllers():
    data = load("player.animation_controllers.json")
    ctrls = data["animation_controllers"]
    third = ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"]
    done = set()
    for entry in third:
        if isinstance(entry, dict):
            (name,) = entry.keys()
            if name in THIRD_PERSON_WEIGHTS:
                entry[name] = THIRD_PERSON_WEIGHTS[name]
                done.add(name)
    missing = set(THIRD_PERSON_WEIGHTS) - done
    assert not missing, f"not found in the vanilla controller: {missing}"
    for cid in ("controller.animation.player.crossbow", "controller.animation.player.melee_spear"):
        for state in ctrls[cid]["states"].values():
            state["blend_transition"] = CONTROLLER_BLEND
            state["blend_via_shortest_path"] = True
    save("animation_controllers/player.animation_controllers.json", data)


def replace_in(obj, old, new):
    if isinstance(obj, str):
        return obj.replace(old, new)
    if isinstance(obj, list):
        return [replace_in(x, old, new) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_in(v, old, new) for k, v in obj.items()}
    return obj


def build_animations():
    data = load("player.animation.json")
    anims = data["animations"]
    bones = anims["animation.player.holding"]["bones"]
    for bone, side in (("rightarm", "r"), ("leftarm", "l")):
        flag = "right" if side == "r" else "left"
        assert bones[bone]["rotation"][0] == f"variable.is_holding_{flag} ? (-this * 0.5 - 18.0) : 0.0"
        bones[bone]["rotation"][0] = (f"(-this * 0.5 - 18.0) * (variable.sa_hold_{side} ?? "
                                      f"((variable.is_holding_{flag} ?? 0.0) ? 1.0 : 0.0))")
    # Poses that tilt by a fixed amount when sneaking follow the smoothed sneak instead.
    smooth_sneak = "(variable.sa_sneak ?? query.is_sneaking)"
    for aid in ("animation.player.bow_equipped", "animation.player.crossbow_hold",
                "animation.player.melee_spear_attack"):
        a = replace_in(anims[aid], "query.is_sneaking", smooth_sneak)
        anims[aid] = replace_in(a, "q.is_sneaking", smooth_sneak)
    save("animations/player.animation.json", data)

    data = load("player_firstperson.animation.json")
    anims = data["animations"]
    arm_h = ("temp.h = math.clamp((variable.sa_arm_ok ?? 0.0) ? variable.sa_arm : variable.player_arm_height, "
             "0.0, 1.0); ")
    eased_main = (arm_h +
                  "return -10.0 * (1.0 - temp.h * temp.h * (3.0 - 2.0 * temp.h));")
    eased_off = ("temp.h = math.clamp(context.player_offhand_arm_height, 0.0, 1.0); "
                 "return -10.0 * (1.0 - temp.h * temp.h * (3.0 - 2.0 * temp.h));")
    swap = anims["animation.player.first_person.swap_item"]["bones"]
    assert swap["rightarm"]["position"][1] == "-10.0 * (1.0 - variable.player_arm_height)"
    swap["rightarm"]["position"][1] = eased_main
    swap["leftarm"]["position"][1] = (
        "temp.h = math.clamp(context.player_offhand_arm_height, 0.0, 1.0); "
        "return (query.get_equipped_item_name('off_hand') == 'filled_map' || "
        "query.get_equipped_item_name('off_hand') == 'shield') ? 0.0 "
        ": -10.0 * (1.0 - temp.h * temp.h * (3.0 - 2.0 * temp.h));")
    block = anims["animation.player.first_person.shield_block"]["bones"]
    block["leftarm"]["position"][1] = eased_off
    block["rightarm"]["position"][1] = (
        arm_h +
        "return query.get_equipped_item_name('off_hand') != 'shield' ? "
        "-10.0 * (1.0 - temp.h * temp.h * (3.0 - 2.0 * temp.h)) : 0.0;")
    save("animations/player_firstperson.animation.json", data)


def build_manifest():
    save("manifest.json", {
        "format_version": 2,
        "header": {"name": "Animaciones Suaves",
                   "description": "Suaviza las animaciones bruscas del jugador. Compatible con skins del Marketplace.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
    })


def build_icon():
    s, ss = 128, 4
    img = Image.new("RGBA", (s * ss, s * ss), (38, 50, 72, 255))
    d = ImageDraw.Draw(img)
    # A figure going from standing to crouched, drawn as fading "frames".
    for i, t in enumerate([0.0, 0.33, 0.66, 1.0]):
        a = int(70 + 185 * (i / 3))
        col = (120 + int(100 * t), 200, 255 - int(60 * t), a)
        x = (22 + i * 26) * ss
        top = (24 + t * 14) * ss
        lean = t * 8 * ss
        d.rectangle([x + lean, top, x + lean + 14 * ss, top + 14 * ss], fill=col)              # head
        d.rectangle([x + lean * 0.6, top + 15 * ss, x + lean * 0.6 + 14 * ss, top + 45 * ss], fill=col)  # body
        d.rectangle([x, top + 46 * ss, x + 14 * ss, 104 * ss], fill=col)                        # legs
    d.rectangle([12 * ss, 108 * ss, 116 * ss, 112 * ss], fill=(255, 255, 255, 120))
    img.resize((s, s), Image.LANCZOS).save(os.path.join(RP, "pack_icon.png"))


def main():
    if os.path.isdir(RP):
        shutil.rmtree(RP)
    os.makedirs(RP)
    build_manifest()
    build_entity()
    build_controllers()
    build_animations()
    build_icon()
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "SmoothAnimations.mcpack")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(RP):
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, RP))
    print("wrote", out)


if __name__ == "__main__":
    main()
