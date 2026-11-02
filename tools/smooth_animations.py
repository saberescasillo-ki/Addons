"""Builds "Animaciones Suaves": a resource pack that smooths the player's
abrupt animation changes and adds a few new ones.

    python3 tools/smooth_animations.py            # regenerate the pack and the .mcpack
    python3 tools/smooth_animations.py --preview  # also refresh docs/smooth_animations_preview.png

What it does (third person unless noted):
- Cross-fades (engine "blend_transition") instead of snapping: sneaking, empty
  hand <-> item, mounting, bow, crossbow, shield, spear states, falling.
- Item switch: every time the kind of item in the main hand changes (sword,
  spear, axe, tool, mace, bow, crossbow, shield, food, block/other...) the arm
  dips and the new item grows into the hand. First person: the vanilla dip
  gets an ease-in-out curve.
- Armor: putting on a helmet, chestplate, leggings or boots plays its own
  short animation.
- Shield: sneaking with a shield (either hand) keeps the player standing in a
  guard stance instead of crouching.
- Mace: held with both hands; attacking raises it over the head before the slam.
- Falling from high up: arms go up and out, legs bend, softly.

How, without breaking Marketplace / persona skins: entity/player.entity.json is
NOT replaced (replacing it makes the game show Steve instead of the skin). The
pack only uses animation names that the vanilla player entity already has:
- controllers listed by the vanilla entity but not defined by the game
  (controller.animation.player.base / .hudplayer) or whose job this pack takes
  over (controller.animation.player.crossbow / .melee_spear, folded into the
  new controllers);
- animations listed by the vanilla entity but never played
  (look_at_target.inverted, attack.positions [it only set a 0 rotation],
  first_person.attack_rotation_item, first_person.crossbow_hold,
  humanoid.fishing_rod).
See SLOTS below. Nothing keeps per-frame state, so it does not jitter.

The source files are the vanilla ones from Minecraft 1.26.60
(sources/vanilla_player_1.26.60, from github.com/Mojang/bedrock-samples).
"""
import itertools
import json
import os
import re
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources", "vanilla_player_1.26.60")
RP = os.path.join(ROOT, "SmoothAnimations_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 2, 0]
MIN_ENGINE = [1, 26, 0]
UUIDS = dict(rp="52ee589c-ac10-4f69-818c-6d27bce78aa0", rp_res="b70c157b-5b10-4813-9a33-ef6bf87622b6")

# Entity short name -> what this pack uses it for.
SLOTS = dict(
    hold_right="look_at_target_inverted",            # animation.player.look_at_target.inverted
    item_swap="attack.positions",                    # animation.player.attack.positions
    armor_equip="first_person_attack_rotation_item",  # animation.player.first_person.attack_rotation_item
    mace_attack="first_person_crossbow_hold",         # animation.player.first_person.crossbow_hold
    fall="fishing_rod",                              # animation.humanoid.fishing_rod
    mace_hold="holding_heavy_core",                  # animation.player.holding_heavy_core (also keeps heavy core)
    pose_ctrl="base_controller",                     # controller.animation.player.base
    gear_ctrl="hudplayer",                           # controller.animation.player.hudplayer
    armor_ctrl="crossbow_controller",                # controller.animation.player.crossbow
    item_ctrl="third_person_melee_spear_controller",  # controller.animation.player.melee_spear
)
SLOT_IDS = {
    "look_at_target_inverted": "animation.player.look_at_target.inverted",
    "attack.positions": "animation.player.attack.positions",
    "first_person_attack_rotation_item": "animation.player.first_person.attack_rotation_item",
    "first_person_crossbow_hold": "animation.player.first_person.crossbow_hold",
    "fishing_rod": "animation.humanoid.fishing_rod",
    "holding_heavy_core": "animation.player.holding_heavy_core",
}

BLEND = 0.15        # seconds of cross-fade between poses
FALL_SPEED = -9.0   # m/s; a jump never falls this fast, a drop of ~3 blocks does
SWAP_LEN = 0.32     # third person item switch
EQUIP_LEN = 0.7     # armor
MACE_LEN = 0.6      # mace attack
FP_SWAP_DEPTH = 12.0  # first person: how far the arm goes down when switching items (vanilla 10)

# ---------------------------------------------------------------- conditions
MAIN = "'slot.weapon.mainhand'"
OFF = "'slot.weapon.offhand'"


def name_in(slot, *names):
    return f"query.is_item_name_any({slot}, {', '.join(repr('minecraft:' + n) for n in names)})"


def tag_in(*tags):
    return f"query.equipped_item_any_tag({MAIN}, {', '.join(repr('minecraft:' + t) for t in tags)})"


MACE = name_in(MAIN, "mace")
SHIELD_MAIN = name_in(MAIN, "shield")
SHIELD_OFF = name_in(OFF, "shield")
SHIELD_ANY = f"({SHIELD_MAIN} || {SHIELD_OFF})"
GUARD = (f"(query.is_sneaking || query.blocking) && {SHIELD_ANY} && !query.is_sleeping && "
         "!query.is_swimming && !query.is_crawling")
SNEAK_POSE = f"(query.is_sneaking && !query.is_sleeping && !{SHIELD_ANY})"
FALL = (f"!query.is_on_ground && query.vertical_speed < {FALL_SPEED} && !query.is_gliding && "
        "!query.is_in_water && !query.is_swimming && !query.is_riding && !query.is_levitating && "
        "!query.is_sleeping && !query.is_spectator")
CROSSBOW = name_in(MAIN, "crossbow")
TWO_HANDED_MACE = f"({MACE} && !(variable.is_holding_left ?? 0.0))"

# Kinds of main hand item; switching between two kinds plays the item switch animation.
ITEM_KINDS = [
    ("spear", tag_in("is_spear")),
    ("mace", MACE),
    ("trident", name_in(MAIN, "trident")),
    ("sword", tag_in("is_sword")),
    ("axe", tag_in("is_axe")),
    ("tool", tag_in("is_pickaxe", "is_shovel", "is_hoe")),
    ("bow", name_in(MAIN, "bow")),
    ("crossbow", CROSSBOW),
    ("shield", SHIELD_MAIN),
    ("heavy_core", name_in(MAIN, "heavy_core")),
    ("food", tag_in("is_food")),
    ("empty", "!query.is_item_equipped('main_hand')"),
    ("other", "1.0"),
]
ARMOR_PARTS = ["head", "chest", "legs", "feet"]  # query.has_armor_slot index 0..3


def exclusive(options):
    """[(label, cond)] -> [(label, cond that is true only for the first matching option)]."""
    out, before = [], []
    for label, cond in options:
        parts = [f"!({c})" for c in before] + ([] if cond == "1.0" else [f"({cond})"])
        out.append((label, " && ".join(parts) if parts else "1.0"))
        before.append(cond)
    return out


ITEM_CONDS = dict(exclusive(ITEM_KINDS))


# ------------------------------------------------------------ file helpers
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


# ------------------------------------------------------------ controllers
def combo_controller(dims, blend=BLEND):
    """dims: list of dimensions; a dimension is a list of (label, condition, animations) options
    (the first matching one wins). Each dimension also gets an implicit "none of them" option.
    One state per combination; any state can go straight to any other one, cross-fading for
    `blend` seconds."""
    full = []
    for d in dims:
        conds = dict(exclusive([(o[0], o[1]) for o in d]))
        none = " && ".join(f"!({o[1]})" for o in d)
        full.append([("", none, [])] + [(o[0], conds[o[0]], o[2]) for o in d])
    combos = list(itertools.product(*[range(len(f)) for f in full]))

    def name(combo):
        on = [full[d][i][0] for d, i in enumerate(combo) if full[d][i][0]]
        return "_".join(on) if on else "default"

    states = {}
    for combo in combos:
        anims = [a for d, i in enumerate(combo) for a in full[d][i][2]]
        state = {}
        if anims:
            state["animations"] = anims
        # Only to the states that differ in one dimension; several changes at once take a frame each.
        state["transitions"] = [
            {name(combo[:d] + (j,) + combo[d + 1:]): full[d][j][1]}
            for d in range(len(full)) for j in range(len(full[d])) if j != combo[d]]
        state["blend_transition"] = blend
        state["blend_via_shortest_path"] = True
        states[name(combo)] = state
    return {"initial_state": "default", "states": states}


def flag(label, cond, anims):
    return [(label, cond, anims)]


def pose_controller():
    return combo_controller([
        flag("hold_r", "variable.is_holding_right", [SLOTS["hold_right"]]),
        flag("sneak", SNEAK_POSE, ["sneaking"]),
        flag("fall", FALL, [SLOTS["fall"]]),
    ])


def gear_controller():
    return combo_controller([
        flag("ride", "query.is_riding", ["riding.root", "riding.arms", "riding.legs"]),
        [("bow", f"{name_in(MAIN, 'bow')} && variable.item_use_normalized > 0.0 && "
                 "variable.item_use_normalized < 1.0", ["third_person_bow_equipped"]),
         ("xbow_charge", f"{CROSSBOW} && query.item_remaining_use_duration > 0.0", ["third_person_crossbow_equipped"]),
         ("xbow_hold", f"{CROSSBOW} && query.item_is_charged", ["crossbow_hold"])],
        [("guard_off", f"{GUARD} && {SHIELD_OFF}", ["shield_block_off_hand"]),
         ("guard_main", f"{GUARD} && {SHIELD_MAIN}", ["shield_block_main_hand"])],
    ])


def item_controller():
    """Main hand item kind. Changing kind goes through 'swap' (arm dip). Also runs the vanilla spear
    states and the mace hold/attack."""
    states = {}
    finished = "query.all_animations_finished"
    kinds = [k for k, _ in ITEM_KINDS]

    def to_kinds(extra=""):
        return [{f"k_{k}": f"{extra}({ITEM_CONDS[k]})"} for k in kinds]

    def st(anims, transitions):
        s = {}
        if anims:
            s["animations"] = anims
        s["transitions"] = transitions
        s["blend_transition"] = BLEND
        s["blend_via_shortest_path"] = True
        return s

    states["init"] = st([], to_kinds())
    states["swap"] = st([SLOTS["item_swap"]], to_kinds(f"{finished} && "))
    for k in kinds:
        leave = {"swap": f"!({ITEM_CONDS[k]})"}
        if k == "spear":
            states["k_spear"] = st(["third_person_melee_spear_hold"], [
                leave, {"k_spear_use": "variable.item_use_normalized > 0.0"},
                {"k_spear_attack": "variable.attack_time > 0.0"}])
            states["k_spear_use"] = st(["third_person_melee_spear_use"], [
                leave, {"k_spear": "variable.item_use_normalized == 0.0"}])
            states["k_spear_attack"] = st(["third_person_melee_spear_attack"], [
                leave, {"k_spear": "variable.attack_time == 0.0"},
                {"k_spear_use": "variable.item_use_normalized > 0.0"}])
        elif k == "mace":
            states["k_mace"] = st([SLOTS["mace_hold"]], [leave, {"k_mace_attack": "variable.attack_time > 0.0"}])
            states["k_mace_attack"] = st([SLOTS["mace_hold"], SLOTS["mace_attack"]], [
                leave, {"k_mace": finished}])
        elif k == "heavy_core":
            states["k_heavy_core"] = st([SLOTS["mace_hold"]], [leave])
        else:
            states[f"k_{k}"] = st([], [leave])
    return {"initial_state": "init", "states": states}


def armor_controller():
    """Which armor pieces are worn (one state per combination). A piece that appears plays its
    equip animation; several at once play one after the other."""
    finished = "query.all_animations_finished"
    combos = list(itertools.product([0, 1], repeat=4))

    def name(bits):
        return "w_" + "".join(map(str, bits))

    def worn(i):
        return f"query.has_armor_slot({i})"

    def cond(bits):
        return " && ".join(("" if b else "!") + worn(i) for i, b in enumerate(bits))

    states = {"init": {"transitions": [{name(o): cond(o)} for o in combos]}}
    for bits in combos:
        tr = []
        for i, b in enumerate(bits):
            if b:
                tr.append({name(bits[:i] + (0,) + bits[i + 1:]): f"!{worn(i)}"})
            else:
                tr.append({f"equip_{ARMOR_PARTS[i]}_{name(bits)[2:]}": worn(i)})
        states[name(bits)] = {"transitions": tr, "blend_transition": BLEND, "blend_via_shortest_path": True}
        for i, b in enumerate(bits):
            if not b:
                after = bits[:i] + (1,) + bits[i + 1:]
                states[f"equip_{ARMOR_PARTS[i]}_{name(bits)[2:]}"] = {
                    "on_entry": [f"variable.sa_equip_part = {i};"],
                    "animations": [SLOTS["armor_equip"]],
                    "transitions": [{name(after): finished}],
                    "blend_transition": BLEND, "blend_via_shortest_path": True,
                }
    return {"initial_state": "init", "states": states}


def build_controllers():
    data = load("player.animation_controllers.json")
    ctrls = data["animation_controllers"]
    third = ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"]
    moved = {"riding.root", "riding.arms", "riding.legs", "sneaking", "shield_block_main_hand",
             "shield_block_off_hand", "crossbow_controller", "third_person_bow_equipped",
             "attack.positions", "holding_heavy_core", "third_person_melee_spear_controller"}
    out = []
    for entry in third:
        key = entry if isinstance(entry, str) else next(iter(entry))
        if key in moved:
            moved.discard(key)
            if key == "riding.root":
                out.append(SLOTS["gear_ctrl"])        # where the vanilla riding poses were
            continue
        if key in ("attack.rotations",):
            out.append({key: f"({entry[key]}) && !{MACE}"})
            continue
        out.append(entry)
        if key == "holding":
            out.append(SLOTS["pose_ctrl"])            # right arm pose, sneaking, falling
    assert not moved, f"not found in the vanilla controller: {moved}"
    out += [SLOTS["item_ctrl"], SLOTS["armor_ctrl"]]
    ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"] = out
    ctrls["controller.animation.player.base"] = pose_controller()
    ctrls["controller.animation.player.hudplayer"] = gear_controller()
    ctrls["controller.animation.player.crossbow"] = armor_controller()
    ctrls["controller.animation.player.melee_spear"] = item_controller()
    save("animation_controllers/player.animation_controllers.json", data)


# ------------------------------------------------------------ animations
def smooth01(x):
    return f"(math.clamp({x}, 0.0, 1.0) * math.clamp({x}, 0.0, 1.0) * (3.0 - 2.0 * math.clamp({x}, 0.0, 1.0)))"


def keyframes(points):
    return {f"{t:g}": {"post": v, "lerp_mode": "catmullrom"} for t, v in points}


def armor_equip_animation():
    # Envelope: goes to the pose in 0.2 s, stays until 0.45 s, back by 0.7 s; "tug" pulls during the hold.
    t = "query.anim_time"
    w = f"({smooth01(f'{t} / 0.2')} * (1.0 - {smooth01(f'({t} - 0.45) / 0.25')}))"
    g = f"math.sin(math.clamp(({t} - 0.12) / 0.4, 0.0, 1.0) * 180.0)"
    b1 = f"math.sin(math.clamp(({t} - 0.05) / 0.3, 0.0, 1.0) * 180.0)"   # first leg
    b2 = f"math.sin(math.clamp(({t} - 0.35) / 0.3, 0.0, 1.0) * 180.0)"   # second leg
    poses = {  # part -> bone -> [x, y, z] rotation expressions (added on top of the current pose)
        # Arms over the head: with the arm raised, +z (right) / -z (left) bring the hands inward.
        "head": {"rightarm": [f"-160.0 * {w} + 18.0 * {g}", "0.0", f"16.0 * {w}"],
                 "leftarm": [f"-160.0 * {w} + 18.0 * {g}", "0.0", f"-16.0 * {w}"],
                 "head": [f"10.0 * {g}", "0.0", "0.0"]},
        "chest": {"rightarm": [f"-70.0 * {w} + 22.0 * {g}", f"-40.0 * {w}", "0.0"],
                  "leftarm": [f"-70.0 * {w} + 22.0 * {g}", f"40.0 * {w}", "0.0"],
                  "head": [f"12.0 * {w}", "0.0", "0.0"]},
        "legs": {"rightarm": [f"-12.0 * {w} - 14.0 * {g}", "0.0", f"14.0 * {w}"],
                 "leftarm": [f"-12.0 * {w} - 14.0 * {g}", "0.0", f"-14.0 * {w}"],
                 "rightleg": [f"-28.0 * {b1}", "0.0", "0.0"],
                 "leftleg": [f"-28.0 * {b2}", "0.0", "0.0"],
                 "head": [f"18.0 * {w}", "0.0", "0.0"]},
        "feet": {"rightarm": ["0.0", "0.0", f"22.0 * {w}"],
                 "leftarm": ["0.0", "0.0", f"-22.0 * {w}"],
                 "rightleg": [f"-45.0 * {b1}", "0.0", "0.0"],
                 "leftleg": [f"-45.0 * {b2}", "0.0", "0.0"],
                 "head": [f"25.0 * {w}", "0.0", "0.0"]},
    }
    bones = {}
    for bone in ["head", "rightarm", "leftarm", "rightleg", "leftleg"]:
        rot = []
        for axis in range(3):
            vals = [poses[p].get(bone, ["0.0"] * 3)[axis] for p in ARMOR_PARTS]
            if all(v == "0.0" for v in vals):
                rot.append(0.0)
                continue
            expr = vals[-1]
            for i in range(len(ARMOR_PARTS) - 2, -1, -1):
                expr = f"temp.p == {i} ? ({vals[i]}) : ({expr})"
            rot.append(f"temp.p = variable.sa_equip_part ?? 0.0; return {expr};")
        bones[bone] = {"rotation": rot}
    return {"loop": False, "animation_length": EQUIP_LEN, "bones": bones}


def fall_animation():
    r = smooth01("query.anim_time / 0.35")
    s1 = "math.sin(query.life_time * 260.0)"
    s2 = "math.sin(query.life_time * 260.0 + 90.0)"
    return {
        "loop": "hold_on_last_frame", "animation_length": 3600.0,
        "bones": {
            "rightarm": {"rotation": [f"(-this * 0.7 - 40.0 - 10.0 * {s1}) * {r}", 0.0, f"(55.0 + 10.0 * {s2}) * {r}"]},
            "leftarm": {"rotation": [f"(-this * 0.7 - 40.0 - 10.0 * {s2}) * {r}", 0.0, f"(-55.0 - 10.0 * {s1}) * {r}"]},
            "rightleg": {"rotation": [f"(-this * 0.7 - 24.0 + 8.0 * {s1}) * {r}", 0.0, f"6.0 * {r}"]},
            "leftleg": {"rotation": [f"(-this * 0.7 + 8.0 + 8.0 * {s2}) * {r}", 0.0, f"-6.0 * {r}"]},
        },
    }


def build_animations():
    data = load("player.animation.json")
    anims = data["animations"]

    # Right arm "holding an item" pose: cross-faded by controller.animation.player.base.
    bones = anims["animation.player.holding"]["bones"]
    assert bones["rightarm"]["rotation"][0] == "variable.is_holding_right ? (-this * 0.5 - 18.0) : 0.0"
    del bones["rightarm"]
    anims["animation.player.look_at_target.inverted"] = {
        "loop": True, "bones": {"rightarm": {"rotation": [f"{MACE} ? 0.0 : (-this * 0.5 - 18.0)", 0.0, 0.0]}}}

    # Item switch (third person): arm dips and the new item grows into the hand.
    anims["animation.player.attack.positions"] = {
        "loop": False, "animation_length": SWAP_LEN,
        "bones": {
            "rightarm": {"rotation": keyframes([(0, [0, 0, 0]), (0.1, [26, 0, 6]), (0.2, [14, 0, 3]),
                                                (SWAP_LEN, [0, 0, 0])])},
            "rightitem": {"scale": keyframes([(0, [0.85] * 3), (0.1, [0.5] * 3), (0.2, [0.8] * 3),
                                              (SWAP_LEN, [1.0] * 3)])},
        },
    }

    # Mace held with both hands (and the vanilla heavy core pose, which used this animation).
    core = anims["animation.player.holding_heavy_core"]["bones"]["rightItem"]
    assert core == {"scale": 0.7, "position": [-1.0, 0.0, -2.0]}
    m, m2 = MACE, TWO_HANDED_MACE
    anims["animation.player.holding_heavy_core"] = {"loop": True, "bones": {
        "rightItem": {"scale": [f"{m} ? 1.0 : 0.7"] * 3,
                      "position": [f"{m} ? 0.0 : -1.0", 0.0, f"{m} ? 0.0 : -2.0"],
                      "rotation": [f"{m} ? -35.0 : 0.0", 0.0, 0.0]},  # mace head up
        "rightarm": {"rotation": [f"{m} ? (-this * 0.8 - 30.0) : 0.0", f"{m} ? (-this - 16.0) : 0.0",
                                 f"{m} ? -this : 0.0"]},
        "leftarm": {"rotation": [f"{m2} ? (-this * 0.8 - 34.0) : 0.0", f"{m2} ? (-this + 52.0) : 0.0",
                                f"{m2} ? -this : 0.0"]},
    }}

    # Mace attack: raise it over the head, then slam down (added on top of the hold pose).
    # Arms: from the hold (about -30) to over the head (-150), then down in front (-20).
    arm = keyframes([(0, [0, 0, 0]), (0.2, [-110, 0, 0]), (0.3, [-122, 0, 0]), (0.42, [10, 0, 0]),
                     (MACE_LEN, [0, 0, 0])])
    anims["animation.player.first_person.crossbow_hold"] = {
        "loop": False, "animation_length": MACE_LEN,
        "bones": {
            "rightarm": {"rotation": arm},
            "leftarm": {"rotation": arm},
            # Mace head tilted back over the shoulders, then pointing at the ground on the slam.
            "rightitem": {"rotation": keyframes([(0, [0, 0, 0]), (0.3, [-15, 0, 0]), (0.42, [115, 0, 0]),
                                                 (MACE_LEN, [0, 0, 0])])},
            "head": {"rotation": keyframes([(0, [0, 0, 0]), (0.25, [-12, 0, 0]), (0.42, [10, 0, 0]),
                                            (MACE_LEN, [0, 0, 0])])},
            "rightleg": {"rotation": keyframes([(0, [0, 0, 0]), (0.3, [-8, 0, 0]), (0.42, [-16, 0, 0]),
                                                (MACE_LEN, [0, 0, 0])])},
            "leftleg": {"rotation": keyframes([(0, [0, 0, 0]), (0.42, [10, 0, 0]), (MACE_LEN, [0, 0, 0])])},
        },
    }

    # Shield guard stance (replaces crouching while sneaking with a shield). Arm and shield as in
    # vanilla blocking; feet apart, one forward (not while riding).
    still = "(1.0 - query.is_riding)"
    off = anims["animation.player.shield_block_off_hand"]["bones"]
    off["leftleg"] = {"rotation": [f"-14.0 * {still}", 0.0, f"-4.0 * {still}"]}
    off["rightleg"] = {"rotation": [f"12.0 * {still}", 0.0, f"4.0 * {still}"]}
    off["rightarm"] = {"rotation": ["-8.0", 0.0, 4.0]}
    main = anims["animation.player.shield_block_main_hand"]["bones"]
    main["rightleg"] = {"rotation": [f"-14.0 * {still}", 0.0, f"4.0 * {still}"]}
    main["leftleg"] = {"rotation": [f"12.0 * {still}", 0.0, f"-4.0 * {still}"]}
    main["leftarm"] = {"rotation": ["-8.0", 0.0, -4.0]}

    # Poses that lean the arms because the body is crouched follow the real crouch pose.
    for aid in ("animation.player.bow_equipped", "animation.player.crossbow_hold",
                "animation.player.melee_spear_attack"):
        s = json.dumps(anims[aid]).replace("query.is_sneaking", SNEAK_POSE).replace("q.is_sneaking", SNEAK_POSE)
        anims[aid] = json.loads(s)
    save("animations/player.animation.json", data)

    # Fall pose (slot never used by the vanilla player).
    save("animations/smooth_extra.animation.json", {"format_version": "1.10.0", "animations": {
        "animation.humanoid.fishing_rod": fall_animation(),
        "animation.player.first_person.attack_rotation_item": armor_equip_animation(),
    }})

    data = load("player_firstperson.animation.json")
    anims = data["animations"]
    # First person item switch: same movement as vanilla, slightly deeper, with an ease-in-out curve.
    ease = ("temp.h = math.clamp({h}, 0.0, 1.0); return {pre}-{d} * (1.0 - temp.h * temp.h * "
            "(3.0 - 2.0 * temp.h)){post};")
    main_h, off_h = "variable.player_arm_height", "context.player_offhand_arm_height"
    d = f"{FP_SWAP_DEPTH:g}.0" if float(FP_SWAP_DEPTH).is_integer() else f"{FP_SWAP_DEPTH}"
    swap = anims["animation.player.first_person.swap_item"]["bones"]
    assert swap["rightarm"]["position"][1] == f"-10.0 * (1.0 - {main_h})"
    swap["rightarm"]["position"][1] = ease.format(h=main_h, pre="", post="", d=d)
    swap["leftarm"]["position"][1] = ease.format(
        h=off_h, d=d, post="", pre="(query.get_equipped_item_name('off_hand') == 'filled_map' || "
                                  "query.get_equipped_item_name('off_hand') == 'shield') ? 0.0 : ")
    block = anims["animation.player.first_person.shield_block"]["bones"]
    block["leftarm"]["position"][1] = ease.format(h=off_h, pre="", post="", d=d)
    block["rightarm"]["position"][1] = ease.format(
        h=main_h, d=d, pre="query.get_equipped_item_name('off_hand') != 'shield' ? ", post=" : 0.0")
    # These two first person slots are reused above; first person never played them.
    del anims["animation.player.first_person.attack_rotation_item"]
    del anims["animation.player.first_person.crossbow_hold"]
    save("animations/player_firstperson.animation.json", data)


def build_manifest():
    save("manifest.json", {
        "format_version": 2,
        "header": {"name": "Animaciones Suaves",
                   "description": "Animaciones del jugador más suaves y nuevas (armadura, mazo, escudo, caída). "
                                  "Compatible con skins del Marketplace.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
    })


def build_icon():
    s, ss = 128, 4
    img = Image.new("RGBA", (s * ss, s * ss), (38, 50, 72, 255))
    d = ImageDraw.Draw(img)
    for i, t in enumerate([0.0, 0.33, 0.66, 1.0]):
        a = int(70 + 185 * (i / 3))
        col = (120 + int(100 * t), 200, 255 - int(60 * t), a)
        x = (22 + i * 26) * ss
        top = (24 + t * 14) * ss
        lean = t * 8 * ss
        d.rectangle([x + lean, top, x + lean + 14 * ss, top + 14 * ss], fill=col)
        d.rectangle([x + lean * 0.6, top + 15 * ss, x + lean * 0.6 + 14 * ss, top + 45 * ss], fill=col)
        d.rectangle([x, top + 46 * ss, x + 14 * ss, 104 * ss], fill=col)
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
    if "--preview" in sys.argv:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import smooth_animations_check
        smooth_animations_check.preview(os.path.join(ROOT, "docs", "smooth_animations_preview.png"))


if __name__ == "__main__":
    main()
