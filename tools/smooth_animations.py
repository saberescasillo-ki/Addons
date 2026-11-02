"""Builds "Animaciones Suaves": a resource pack that smooths the player's
abrupt animation changes (sneaking, item switch, mounting, shield, bow) so
they blend over a few frames instead of snapping.

How it works: the pack does NOT replace entity/player.entity.json (replacing it
makes the game drop Marketplace / persona skins and show Steve). It only uses
the animation names that the vanilla player entity already has:

- controller.animation.player.base and controller.animation.player.hudplayer
  are listed in the vanilla player entity ("base_controller", "hudplayer") but
  are not defined by the game, so the pack defines them. Each one has a state
  for every combination of a few on/off poses (sneaking, holding an item...)
  and uses "blend_transition", the engine's own cross-fade between states.
- "look_at_target_inverted" (animation.player.look_at_target.inverted) is in
  the vanilla entity but no controller uses it; the pack turns it into the
  "right arm holding an item" pose so that pose can be cross-faded too.
- controller.animation.player.root is the vanilla one with those poses moved
  into the two new controllers.

Nothing keeps per-frame state in variables, so there is no jitter between the
different renders of the player (HUD, inventory, first/third person).

The source files are the vanilla ones from Minecraft 1.26.60
(sources/vanilla_player_1.26.60, from github.com/Mojang/bedrock-samples).

    python3 tools/smooth_animations.py      # regenerate the pack and the .mcpack
"""
import itertools
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

VERSION = [1, 1, 0]
MIN_ENGINE = [1, 26, 0]
UUIDS = dict(rp="52ee589c-ac10-4f69-818c-6d27bce78aa0", rp_res="b70c157b-5b10-4813-9a33-ef6bf87622b6")

RIGHT_HOLD = "look_at_target_inverted"  # entity slot reused for the right arm "holding" pose

# Each smoothed controller: (on/off poses, blend seconds). A pose is
# (name, condition, animations listed while it is on).
BASE = ([
    ("hold_r", "variable.is_holding_right", [RIGHT_HOLD]),
    ("sneak", "query.is_sneaking && !query.is_sleeping", ["sneaking"]),
], 0.15)
HUD = ([
    ("ride", "query.is_riding", ["riding.root", "riding.arms", "riding.legs"]),
    ("bow", "query.get_equipped_item_name == 'bow' && variable.item_use_normalized > 0.0 && "
            "variable.item_use_normalized < 1.0", ["third_person_bow_equipped"]),
    ("shield_main", "query.blocking && query.get_equipped_item_name('off_hand') != 'shield' && "
                    "query.get_equipped_item_name == 'shield'", ["shield_block_main_hand"]),
    ("shield_off", "query.blocking && query.get_equipped_item_name('off_hand') == 'shield'",
     ["shield_block_off_hand"]),
], 0.15)
CONTROLLER_BLEND = 0.15  # blend_transition added to the vanilla crossbow and spear controllers


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


def combo_controller(poses, blend):
    """One state per combination of poses; every state can go straight to any other one."""
    def name(bits):
        on = [p[0] for p, b in zip(poses, bits) if b]
        return "_".join(on) if on else "default"

    def cond(bits):
        return " && ".join(f"({c})" if b else f"!({c})" for (_, c, _), b in zip(poses, bits))

    combos = list(itertools.product([0, 1], repeat=len(poses)))
    states = {}
    for bits in combos:
        anims = [a for p, b in zip(poses, bits) if b for a in p[2]]
        state = {}
        if anims:
            state["animations"] = anims
        state["transitions"] = [{name(o): cond(o)} for o in combos if o != bits]
        state["blend_transition"] = blend
        state["blend_via_shortest_path"] = True
        states[name(bits)] = state
    return {"initial_state": "default", "states": states}


def build_controllers():
    data = load("player.animation_controllers.json")
    ctrls = data["animation_controllers"]
    third = ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"]
    moved = {a for poses, _ in (BASE, HUD) for p in poses for a in p[2]} - {RIGHT_HOLD}
    out = []
    for entry in third:
        key = entry if isinstance(entry, str) else next(iter(entry))
        if key in moved:
            moved.discard(key)
            if key == "riding.root":
                out.append("hudplayer")      # same place in the list as the vanilla riding poses
            continue
        if key == "holding":
            out += ["holding", "base_controller"]   # right arm pose + sneaking, right after holding
            continue
        out.append(entry)
    assert not moved, f"not found in the vanilla controller: {moved}"
    ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"] = out
    ctrls["controller.animation.player.base"] = combo_controller(*BASE)
    ctrls["controller.animation.player.hudplayer"] = combo_controller(*HUD)
    for cid in ("controller.animation.player.crossbow", "controller.animation.player.melee_spear"):
        for state in ctrls[cid]["states"].values():
            state["blend_transition"] = CONTROLLER_BLEND
            state["blend_via_shortest_path"] = True
    save("animation_controllers/player.animation_controllers.json", data)


def build_animations():
    data = load("player.animation.json")
    anims = data["animations"]
    bones = anims["animation.player.holding"]["bones"]
    assert bones["rightarm"]["rotation"][0] == "variable.is_holding_right ? (-this * 0.5 - 18.0) : 0.0"
    # The right arm moves to look_at_target.inverted (cross-faded by controller.animation.player.base);
    # the left arm stays as in vanilla.
    del bones["rightarm"]
    assert "animation.player.look_at_target.inverted" in anims
    anims["animation.player.look_at_target.inverted"] = {
        "loop": True,
        "bones": {"rightarm": {"rotation": ["-this * 0.5 - 18.0", 0.0, 0.0]}},
    }
    save("animations/player.animation.json", data)

    data = load("player_firstperson.animation.json")
    anims = data["animations"]
    # First person item switch: same movement as vanilla, but the arm comes back up with an
    # ease-in-out curve instead of a straight line.
    ease = "temp.h = math.clamp({}, 0.0, 1.0); return {}-10.0 * (1.0 - temp.h * temp.h * (3.0 - 2.0 * temp.h)){};"
    main, off = "variable.player_arm_height", "context.player_offhand_arm_height"
    swap = anims["animation.player.first_person.swap_item"]["bones"]
    assert swap["rightarm"]["position"][1] == f"-10.0 * (1.0 - {main})"
    swap["rightarm"]["position"][1] = ease.format(main, "", "")
    swap["leftarm"]["position"][1] = ease.format(
        off, "(query.get_equipped_item_name('off_hand') == 'filled_map' || "
             "query.get_equipped_item_name('off_hand') == 'shield') ? 0.0 : ", "")
    block = anims["animation.player.first_person.shield_block"]["bones"]
    block["leftarm"]["position"][1] = ease.format(off, "", "")
    block["rightarm"]["position"][1] = ease.format(
        main, "query.get_equipped_item_name('off_hand') != 'shield' ? ", " : 0.0")
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
    build_controllers()
    build_animations()
    build_icon()
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "SmoothAnimations.mcpack")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(RP):
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, RP))
    print("wrote", out)


if __name__ == "__main__":
    main()
