"""Builds "Animaciones Suaves": a resource pack that smooths the player's
abrupt animation changes and adds a few new ones.

    python3 tools/smooth_animations.py            # regenerate the pack and the .mcpack
    python3 tools/smooth_animations.py --preview  # also refresh docs/smooth_animations_preview.png

What it does (third person unless noted):
- Cross-fades (engine "blend_transition") instead of snapping: sneaking, empty
  hand <-> item, mounting, bow, crossbow, shield, spear states, falling,
  elytra, idle.
- Item switch: every time the kind of item in the main hand changes (sword,
  spear, axe, tool, mace, bow, crossbow, shield, food, block/other...) the arm
  dips (the item itself is not scaled). First person: the vanilla dip gets an
  ease-in-out curve.
- Armor: putting on a helmet, chestplate, leggings or boots plays its own
  short animation.
- Shield: sneaking with a shield (either hand) keeps the player standing in a
  guard stance instead of crouching.
- Falling from high up: arms go up and out, legs bend, softly.
- Elytra: arms slightly spread while gliding.
- Idle: after standing still for a while (10 s by default) the player looks
  around, breathes and shifts their weight.
- Pack settings (gear icon of the pack): every feature can be switched off.

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
  humanoid.fishing_rod) or whose content moved elsewhere (holding_heavy_core,
  now inside animation.player.holding).
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

VERSION = [1, 3, 0]
MIN_ENGINE = [1, 26, 0]
UUIDS = dict(rp="52ee589c-ac10-4f69-818c-6d27bce78aa0", rp_res="b70c157b-5b10-4813-9a33-ef6bf87622b6")

# Entity short name -> what this pack uses it for.
SLOTS = dict(
    hold_right="look_at_target_inverted",            # animation.player.look_at_target.inverted
    item_swap="attack.positions",                    # animation.player.attack.positions
    armor_equip="first_person_attack_rotation_item",  # animation.player.first_person.attack_rotation_item
    glide="first_person_crossbow_hold",               # animation.player.first_person.crossbow_hold
    fall="fishing_rod",                              # animation.humanoid.fishing_rod
    idle="holding_heavy_core",                       # animation.player.holding_heavy_core
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
EQUIP_LEN = 0.9     # armor
IDLE_DELAY = 10     # default seconds standing still before the idle animation (pack setting)
FP_SWAP_DEPTH = 10.0  # first person: how far the arm goes down when switching items (same as vanilla)

# Pack settings (shown with the gear icon of the pack in Settings > Global resources). Toggles are
# "turn off" switches that default to off, so the features also work if the game ignores settings.
SETTINGS = [
    ("label", None, "Animaciones Suaves: activa un interruptor para quitar esa animación."),
    ("toggle", "sa:no_item_switch", "Quitar animación de cambio de objeto (3a persona)"),
    ("toggle", "sa:no_fp_ease", "Quitar suavizado del cambio de objeto (1a persona)"),
    ("toggle", "sa:no_armor", "Quitar animaciones de ponerse armadura"),
    ("toggle", "sa:no_shield_guard", "Quitar guardia con escudo (agacharse como en vanilla)"),
    ("toggle", "sa:no_fall", "Quitar animación de caída"),
    ("toggle", "sa:no_glide", "Quitar brazos abiertos con élitros"),
    ("toggle", "sa:no_idle", "Quitar animación de espera"),
    ("toggle", "sa:no_walk", "Quitar caminar y correr mejorados (y con herramienta)"),
    ("toggle", "sa:no_death", "Quitar animación de muerte (arrodillarse)"),
    ("slider", "sa:idle_delay", "Segundos quieto antes de la animación de espera"),
]


def off(name):
    return f"query.is_pack_setting_enabled('sa:no_{name}')"


def on_factor(name):
    return f"(1.0 - {off(name)})"


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
GUARD_ON = f"!{off('shield_guard')}"
# Guard stance: sneaking (or blocking) with a shield. Turned off: vanilla (shield up only while blocking).
GUARD = (f"({GUARD_ON} ? (query.is_sneaking || query.blocking) : query.blocking) && {SHIELD_ANY} && "
         "!query.is_sleeping && !query.is_swimming && !query.is_crawling")
SNEAK_POSE = f"(query.is_sneaking && !query.is_sleeping && !({GUARD_ON} && {SHIELD_ANY}))"
FALL = (f"!query.is_on_ground && query.vertical_speed < {FALL_SPEED} && !query.is_gliding && "
        "!query.is_in_water && !query.is_swimming && !query.is_riding && !query.is_levitating && "
        f"!query.is_sleeping && !query.is_spectator && !{off('fall')}")
GLIDE = f"query.is_gliding && !{off('glide')}"
IDLE = ("query.is_on_ground && !query.is_moving && !query.is_sneaking && !query.blocking && !query.is_riding && "
        "!query.is_sleeping && !query.is_swimming && !query.is_crawling && !query.is_in_water && "
        "!query.is_emoting && variable.attack_time <= 0.0 && variable.item_use_normalized <= 0.0 && "
        f"!{off('idle')}")
TOOL_IN_HAND = (f"({tag_in('is_sword', 'is_axe', 'is_pickaxe', 'is_shovel', 'is_hoe', 'is_spear')} || "
                f"{name_in(MAIN, 'trident', 'mace')})")
DEATH = f"!query.is_alive && !{off('death')}"
CROSSBOW = name_in(MAIN, "crossbow")
HEAVY_CORE = name_in(MAIN, "heavy_core")

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
    ("heavy_core", HEAVY_CORE),
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
        flag("glide", GLIDE, [SLOTS["glide"]]),
        flag("idle", IDLE, [SLOTS["idle"]]),
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
    states."""
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
        else:
            states[f"k_{k}"] = st([], [leave])
    return {"initial_state": "init", "states": states}


def armor_controller():
    """Which armor pieces are worn (one state per combination). A piece that appears plays its
    equip animation and one that disappears its removal animation; several at once play one after
    the other. Elytra (chest slot, armor texture 5) have their own animations."""
    finished = "query.all_animations_finished"
    combos = list(itertools.product([0, 1], repeat=4))
    is_elytra = "query.armor_texture_slot(1) == 5"

    def name(bits):
        return "w_" + "".join(map(str, bits))

    def worn(i):
        return f"query.has_armor_slot({i})"

    def cond(bits):
        return " && ".join(("" if b else "!") + worn(i) for i, b in enumerate(bits))

    def one_shot(part_expr, after):
        return {"on_entry": [f"variable.sa_equip_part = {part_expr};"],
                "animations": [SLOTS["armor_equip"]],
                "transitions": [{name(after): finished}],
                "blend_transition": BLEND, "blend_via_shortest_path": True}

    states = {"init": {"on_entry": [f"variable.sa_chest_elytra = {is_elytra};"],
                       "transitions": [{name(o): cond(o)} for o in combos]}}
    for bits in combos:
        tr = []
        for i, b in enumerate(bits):
            flipped = bits[:i] + (1 - b,) + bits[i + 1:]
            tag = f"{ARMOR_PARTS[i]}_{name(bits)[2:]}"
            if b:
                tr.append({f"remove_{tag}": f"!{worn(i)}"})
                part = "(variable.sa_chest_elytra ?? 0.0) ? 9 : 5" if i == 1 else str(4 + i)
                states[f"remove_{tag}"] = one_shot(part, flipped)
            else:
                tr.append({f"equip_{tag}": worn(i)})
                st = one_shot(f"{is_elytra} ? 8 : 1" if i == 1 else str(i), flipped)
                if i == 1:
                    st["on_entry"].append(f"variable.sa_chest_elytra = {is_elytra};")
                states[f"equip_{tag}"] = st
        states[name(bits)] = {"transitions": tr, "blend_transition": BLEND, "blend_via_shortest_path": True}
    return {"initial_state": "init", "states": states}


def build_controllers():
    data = load("player.animation_controllers.json")
    ctrls = data["animation_controllers"]
    third = ctrls["controller.animation.player.root"]["states"]["third_person"]["animations"]
    moved = {"riding.root", "riding.arms", "riding.legs", "sneaking", "shield_block_main_hand",
             "shield_block_off_hand", "crossbow_controller", "third_person_bow_equipped",
             "attack.positions", "holding_heavy_core", "third_person_melee_spear_controller"}
    # holding_heavy_core: its pose moved into animation.player.holding (see build_animations).
    out = []
    for entry in third:
        key = entry if isinstance(entry, str) else next(iter(entry))
        if key in moved:
            moved.discard(key)
            if key == "riding.root":
                out.append(SLOTS["gear_ctrl"])        # where the vanilla riding poses were
            continue
        if key == "sleeping":
            out.append({key: f"({entry[key]}) || ({DEATH})"})   # death pose lives in the sleeping animation
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


ARMOR_POSES = ["helmet on", "chestplate on", "leggings on", "boots on",
               "helmet off", "chestplate off", "leggings off", "boots off", "elytra on", "elytra off"]


def armor_equip_animation():
    """One animation for every piece; variable.sa_equip_part (set when the state starts) picks the
    pose. Values are added on top of the current pose."""
    t = "query.anim_time"
    # Envelope: goes to the pose in 0.22 s, stays until 0.6 s, back by 0.9 s; "tug" pulls during the hold.
    w = f"({smooth01(f'{t} / 0.22')} * (1.0 - {smooth01(f'({t} - 0.6) / 0.3')}))"
    g = f"math.sin(math.clamp(({t} - 0.15) / 0.5, 0.0, 1.0) * 180.0)"
    b1 = f"math.sin(math.clamp(({t} - 0.12) / 0.3, 0.0, 1.0) * 180.0)"   # first leg / foot
    b2 = f"math.sin(math.clamp(({t} - 0.42) / 0.3, 0.0, 1.0) * 180.0)"   # second leg / foot
    # Boots: kneels on the right knee and pulls the boot of the left foot (in front) with both hands;
    # the model has no knees, so kneeling is the way the hands reach a foot.
    kneel = {"root": {"rotation": [f"16.0 * {w}", "0.0", "0.0"], "position": ["0.0", f"-8.5 * {w}", f"2.0 * {w}"]},
             "head": {"rotation": [f"30.0 * {w}", "0.0", "0.0"]},
             "rightleg": {"rotation": [f"-this * {w} + 80.0 * {w}", "0.0", f"4.0 * {w}"]},
             "leftleg": {"rotation": [f"-this * {w} - 74.0 * {w}", f"-6.0 * {w}", f"-4.0 * {w}"]}}

    def reach(sign):  # both hands at the front foot, pulling (on) or pushing (off) the boot
        return {"rightarm": [f"-this * {w} - 40.0 * {w} {sign} 10.0 * {g}", f"-14.0 * {w}", "0.0"],
                "leftarm": [f"-this * {w} - 40.0 * {w} {sign} 10.0 * {g}", f"10.0 * {w}", "0.0"]}

    over_head = lambda tug: {
        "rightarm": [f"-160.0 * {w} {tug} 18.0 * {g}", "0.0", f"16.0 * {w}"],
        "leftarm": [f"-160.0 * {w} {tug} 18.0 * {g}", "0.0", f"-16.0 * {w}"],
        "head": [f"{'10.0' if tug == '+' else '-8.0'} * {g}", "0.0", "0.0"]}
    behind_back = lambda tug: {  # reach over the shoulders to the elytra
        "rightarm": [f"-175.0 * {w} {tug} 30.0 * {g}", f"-10.0 * {w}", f"26.0 * {w}"],
        "leftarm": [f"-175.0 * {w} {tug} 30.0 * {g}", f"10.0 * {w}", f"-26.0 * {w}"],
        "head": [f"-10.0 * {w} + 6.0 * {g}", "0.0", "0.0"],
        "body": [f"-4.0 * {g}", "0.0", "0.0"]}
    poses = [  # same order as ARMOR_POSES: bone -> [x, y, z] rotation (or {"rotation"/"position": ...})
        over_head("+"),
        {"rightarm": [f"-70.0 * {w} + 22.0 * {g}", f"-40.0 * {w}", "0.0"],
         "leftarm": [f"-70.0 * {w} + 22.0 * {g}", f"40.0 * {w}", "0.0"],
         "head": [f"12.0 * {w}", "0.0", "0.0"]},
        {"rightarm": [f"-12.0 * {w} - 14.0 * {g}", "0.0", f"14.0 * {w}"],
         "leftarm": [f"-12.0 * {w} - 14.0 * {g}", "0.0", f"-14.0 * {w}"],
         "rightleg": [f"-28.0 * {b1}", "0.0", "0.0"], "leftleg": [f"-28.0 * {b2}", "0.0", "0.0"],
         "head": [f"18.0 * {w}", "0.0", "0.0"]},
        dict(kneel, **reach("-")),
        over_head("-"),
        # Chestplate off: arms crossed, then pulled up over the head.
        {"rightarm": [f"-70.0 * {w} - 80.0 * {g}", f"-40.0 * {w} * (1.0 - {g})", "0.0"],
         "leftarm": [f"-70.0 * {w} - 80.0 * {g}", f"40.0 * {w} * (1.0 - {g})", "0.0"],
         "head": [f"8.0 * {w} - 10.0 * {g}", "0.0", "0.0"]},
        # Leggings off: hands push down at the hips, one leg then the other steps out.
        {"rightarm": [f"-10.0 * {w} + 12.0 * {g}", "0.0", f"12.0 * {w}"],
         "leftarm": [f"-10.0 * {w} + 12.0 * {g}", "0.0", f"-12.0 * {w}"],
         "rightleg": [f"-30.0 * {b1}", "0.0", "0.0"], "leftleg": [f"-30.0 * {b2}", "0.0", "0.0"],
         "head": [f"20.0 * {w}", "0.0", "0.0"]},
        dict(kneel, **reach("+")),
        behind_back("+"),
        behind_back("-"),
    ]
    channels = {}  # (bone, channel) -> [axis -> [expr per pose]]
    for i, pose in enumerate(poses):
        for bone, val in pose.items():
            chans = val if isinstance(val, dict) else {"rotation": val}
            for ch, xyz in chans.items():
                slot = channels.setdefault((bone, ch), [["0.0"] * len(poses) for _ in range(3)])
                for axis in range(3):
                    slot[axis][i] = xyz[axis]
    bones = {}
    for (bone, ch), axes in sorted(channels.items()):
        out = []
        for vals in axes:
            if all(v == "0.0" for v in vals):
                out.append(0.0)
                continue
            expr = vals[-1]
            for i in range(len(vals) - 2, -1, -1):
                expr = expr if vals[i] == vals[-1] else f"temp.p == {i} ? ({vals[i]}) : ({expr})"
            out.append(f"temp.p = variable.sa_equip_part ?? 0.0; return ({expr}) * {on_factor('armor')};")
        bones.setdefault(bone, {})[ch] = out
    return {"loop": False, "animation_length": EQUIP_LEN, "bones": bones}


def fall_animation():
    """Arms rise over the first 0.4 s and then wave slowly up and out, legs pedal a little and the
    head looks down; the whole body arches back slightly."""
    r = smooth01("query.anim_time / 0.4")
    s1 = "math.sin(query.life_time * 210.0)"
    s2 = "math.sin(query.life_time * 210.0 + 120.0)"
    s3 = "math.sin(query.life_time * 330.0)"
    return {
        "loop": "hold_on_last_frame", "animation_length": 3600.0,
        "bones": {
            "rightarm": {"rotation": [f"(-this * 0.8 - 125.0 - 18.0 * {s1}) * {r}", f"(-8.0 * {s2}) * {r}",
                                      f"(32.0 + 12.0 * {s2}) * {r}"]},
            "leftarm": {"rotation": [f"(-this * 0.8 - 125.0 - 18.0 * {s2}) * {r}", f"(8.0 * {s1}) * {r}",
                                     f"(-32.0 - 12.0 * {s1}) * {r}"]},
            "rightleg": {"rotation": [f"(-this * 0.8 - 22.0 + 16.0 * {s3}) * {r}", 0.0, f"5.0 * {r}"]},
            "leftleg": {"rotation": [f"(-this * 0.8 - 6.0 - 16.0 * {s3}) * {r}", 0.0, f"-5.0 * {r}"]},
            "head": {"rotation": [f"16.0 * {r}", 0.0, 0.0]},
            "root": {"rotation": [f"-5.0 * {r}", 0.0, 0.0]},
        },
    }


def idle_animation():
    """Plays from the moment the player stands still; does nothing until the delay has passed, then
    fades in: looking around, breathing and shifting weight."""
    delay = (f"temp.d = query.get_pack_setting('sa:idle_delay'); temp.d = temp.d > 0.0 ? temp.d : {IDLE_DELAY}.0; "
             "temp.t = query.anim_time - temp.d; "
             "temp.r = math.clamp(temp.t / 1.5, 0.0, 1.0); temp.r = temp.r * temp.r * (3.0 - 2.0 * temp.r); ")

    def ch(expr):
        return f"{delay}return ({expr}) * temp.r;"
    return {
        "loop": "hold_on_last_frame", "animation_length": 3600.0,
        "bones": {
            # Looks around slowly (two slow waves so it does not look mechanical) and a bit down.
            "head": {"rotation": [ch("4.0 + 5.0 * math.sin(temp.t * 31.0)"),
                                  ch("24.0 * math.sin(temp.t * 40.0) + 8.0 * math.sin(temp.t * 97.0)"), 0.0]},
            # Breathing: arms move away from the body and back.
            "rightarm": {"rotation": [ch("3.0 * math.sin(temp.t * 53.0)"), 0.0,
                                      ch("2.0 + 2.0 * math.sin(temp.t * 72.0)")]},
            "leftarm": {"rotation": [ch("-3.0 * math.sin(temp.t * 53.0)"), 0.0,
                                     ch("-2.0 - 2.0 * math.sin(temp.t * 72.0)")]},
            # Weight from one leg to the other.
            "rightleg": {"rotation": [ch("-4.0 * math.max(math.sin(temp.t * 27.0), 0.0)"), 0.0,
                                      ch("1.5 * math.sin(temp.t * 27.0)")]},
            "leftleg": {"rotation": [ch("-4.0 * math.max(-math.sin(temp.t * 27.0), 0.0)"), 0.0,
                                     ch("1.5 * math.sin(temp.t * 27.0)")]},
            "body": {"rotation": [0.0, 0.0, ch("1.2 * math.sin(temp.t * 27.0)")]},
        },
    }


def build_walk(anims):
    """Walking and running (setting sa:no_walk turns it back to vanilla). Running is measured from the
    ground speed, so it fades in and out. With a tool or weapon in the main hand the right arm barely
    swings and, when running, carries it forward and up; the left arm swings more instead."""
    k = on_factor("walk")
    run = (f"(math.clamp((query.ground_speed - 4.4) / 1.2, 0.0, 1.0) * !query.is_riding * !query.is_gliding * "
           f"!query.is_swimming * {k})")
    walk = f"(math.clamp(query.modified_move_speed * 2.0, 0.0, 1.0) * !query.is_riding * {k})"
    tool = f"({TOOL_IN_HAND} * {k})"
    arms = anims["animation.player.move.arms"]["bones"]
    assert arms["leftarm"]["rotation"][0] == "variable.tcos0" and arms["rightarm"]["rotation"][0] == "-variable.tcos0"
    arms["leftarm"]["rotation"] = [
        f"variable.tcos0 * (1.0 + 0.3 * {run} + 0.25 * {tool}) - 6.0 * {run}", 0.0, f"-3.0 * {walk} - 3.0 * {run}"]
    arms["rightarm"]["rotation"] = [
        f"-variable.tcos0 * (1.0 + 0.3 * {run} - {tool} * (0.7 + 0.3 * {run})) - 6.0 * {run} - 22.0 * {tool} * {run}",
        f"8.0 * {tool} * {run}", f"3.0 * {walk} + 3.0 * {run}"]
    legs = anims["animation.player.move.legs"]["bones"]
    assert legs["leftleg"]["rotation"][0] == "variable.tcos0 * -1.4"
    legs["leftleg"]["rotation"][0] = f"variable.tcos0 * -1.4 * (1.0 + 0.15 * {run})"
    legs["rightleg"]["rotation"][0] = f"variable.tcos0 * 1.4 * (1.0 + 0.15 * {run})"
    # Running leans the whole body forward a little, pivoting at the feet.
    legs["root"] = {"rotation": [f"7.0 * {run}", 0.0, 0.0]}


def build_trident(anims):
    """Trident aiming, a bit exaggerated (always on): the body leans back, the free arm points at the
    target, feet apart, and the throwing arm goes further back. Grows with variable.charge_amount."""
    c = "((variable.is_brandishing_spear ?? 0.0) * math.clamp(variable.charge_amount ?? 0.0, 0.0, 1.0))"
    legs = anims["animation.player.move.legs"]["bones"]
    legs["root"]["rotation"][0] = f"{legs['root']['rotation'][0]} - 9.0 * {c}"
    legs["leftleg"]["rotation"] = [f"{legs['leftleg']['rotation'][0]} - 18.0 * {c}", -0.1, f"-0.1 - 4.0 * {c}"]
    legs["rightleg"]["rotation"] = [f"{legs['rightleg']['rotation'][0]} + 14.0 * {c}", 0.1, f"0.1 + 4.0 * {c}"]
    # animation.player.bob plays after the vanilla trident pose (brandish_spear) while aiming.
    bob = anims["animation.player.bob"]["bones"]
    bob["rightarm"]["rotation"][0] = f"-25.0 * {c}"
    bob["leftarm"]["rotation"][0] = f"-this * {c} - 75.0 * {c}"
    bob["leftarm"]["rotation"][1] = f"18.0 * {c}"
    bob["head"] = {"rotation": [f"-6.0 * {c}", 0.0, 0.0]}


def build_death(anims):
    """Death (setting sa:no_death): kneels on the right knee with the right hand on the ground and the
    left forearm on the left knee. Uses the vanilla sleeping animation, which overrides the whole pose;
    the engine tips dying mobs onto their side, the root rotation undoes that."""
    sl = anims["animation.player.sleeping"]
    assert sl["override_previous_animation"] is True
    f = smooth01("query.death_ticks / 8.0")
    # Same curve as the engine's death tip-over (90 degrees, sqrt of time).
    tip = ("math.min(1.0, math.sqrt(math.max(0.0, (query.death_ticks + query.frame_alpha - 1.0) / 20.0 * 1.6)))"
           " * 90.0")
    pose = {  # bone -> channel -> [x, y, z] (absolute, the sleeping animation overrides the rest)
        "root": {"rotation": [f"14.0 * {f}", "0.0", f"-{tip}"], "position": ["0.0", f"-7.5 * {f}", f"2.0 * {f}"]},
        "head": {"rotation": [f"28.0 * {f}", "0.0", "0.0"]},
        "body": {"rotation": ["0.0", "0.0", "0.0"]},
        "rightleg": {"rotation": [f"80.0 * {f}", "0.0", f"4.0 * {f}"]},
        "leftleg": {"rotation": [f"-75.0 * {f}", f"-6.0 * {f}", f"-4.0 * {f}"]},
        "rightarm": {"rotation": [f"-30.0 * {f}", "0.0", f"8.0 * {f}"]},
        "leftarm": {"rotation": [f"-62.0 * {f}", f"20.0 * {f}", "0.0"]},
    }
    bones = sl["bones"]
    for bone, chans in pose.items():
        for ch, xyz in chans.items():
            vanilla = bones.get(bone, {}).get(ch, [0.0, 0.0, 0.0])
            bones.setdefault(bone, {})[ch] = [
                f"query.is_alive ? ({v if isinstance(v, str) else repr(float(v))}) : ({d})"
                for v, d in zip(vanilla, xyz)]


def build_animations():
    data = load("player.animation.json")
    anims = data["animations"]

    # Right arm "holding an item" pose: cross-faded by controller.animation.player.base.
    bones = anims["animation.player.holding"]["bones"]
    assert bones["rightarm"]["rotation"][0] == "variable.is_holding_right ? (-this * 0.5 - 18.0) : 0.0"
    del bones["rightarm"]
    anims["animation.player.look_at_target.inverted"] = {
        "loop": True, "bones": {"rightarm": {"rotation": ["-this * 0.5 - 18.0", 0.0, 0.0]}}}

    # Heavy core pose: vanilla played animation.player.holding_heavy_core while holding one; that
    # animation name is now the idle animation, so the same pose lives here (holding always plays).
    core = anims["animation.player.holding_heavy_core"]["bones"]["rightItem"]
    assert core == {"scale": 0.7, "position": [-1.0, 0.0, -2.0]}
    bones["rightItem"] = {"scale": [f"{HEAVY_CORE} ? 0.7 : 1.0"] * 3,
                          "position": [f"{HEAVY_CORE} ? -1.0 : 0.0", 0.0, f"{HEAVY_CORE} ? -2.0 : 0.0"]}
    anims["animation.player.holding_heavy_core"] = idle_animation()

    # Item switch (third person): only the arm dips; the item is not scaled.
    k = on_factor("item_switch")
    anims["animation.player.attack.positions"] = {
        "loop": False, "animation_length": SWAP_LEN,
        "bones": {"rightarm": {"rotation": keyframes([
            (0, [0, 0, 0]), (0.1, [f"26.0 * {k}", 0, f"6.0 * {k}"]), (0.2, [f"14.0 * {k}", 0, f"3.0 * {k}"]),
            (SWAP_LEN, [0, 0, 0])])}},
    }

    # Elytra: arms slightly spread and a little back.
    anims["animation.player.first_person.crossbow_hold"] = {
        "loop": True,
        "bones": {"rightarm": {"rotation": [6.0, 0.0, 14.0]}, "leftarm": {"rotation": [6.0, 0.0, -14.0]}},
    }

    # Shield guard stance (replaces crouching while sneaking with a shield). Arm and shield as in
    # vanilla blocking; feet apart, one forward (not while riding, not with the guard turned off).
    still = f"(1.0 - query.is_riding) * {on_factor('shield_guard')}"
    sb_off = anims["animation.player.shield_block_off_hand"]["bones"]
    sb_off["leftleg"] = {"rotation": [f"-14.0 * {still}", 0.0, f"-4.0 * {still}"]}
    sb_off["rightleg"] = {"rotation": [f"12.0 * {still}", 0.0, f"4.0 * {still}"]}
    sb_off["rightarm"] = {"rotation": [f"-8.0 * {still}", 0.0, f"4.0 * {still}"]}
    sb_main = anims["animation.player.shield_block_main_hand"]["bones"]
    sb_main["rightleg"] = {"rotation": [f"-14.0 * {still}", 0.0, f"4.0 * {still}"]}
    sb_main["leftleg"] = {"rotation": [f"12.0 * {still}", 0.0, f"-4.0 * {still}"]}
    sb_main["leftarm"] = {"rotation": [f"-8.0 * {still}", 0.0, f"-4.0 * {still}"]}

    build_walk(anims)
    build_trident(anims)
    build_death(anims)

    # Poses that lean the arms because the body is crouched follow the real crouch pose.
    for aid in ("animation.player.bow_equipped", "animation.player.crossbow_hold",
                "animation.player.melee_spear_attack"):
        text = json.dumps(anims[aid]).replace("query.is_sneaking", SNEAK_POSE).replace("q.is_sneaking", SNEAK_POSE)
        anims[aid] = json.loads(text)
    save("animations/player.animation.json", data)

    # Slots the vanilla player never plays.
    save("animations/smooth_extra.animation.json", {"format_version": "1.10.0", "animations": {
        "animation.humanoid.fishing_rod": fall_animation(),
        "animation.player.first_person.attack_rotation_item": armor_equip_animation(),
    }})

    data = load("player_firstperson.animation.json")
    anims = data["animations"]
    # First person item switch: same movement as vanilla, slightly deeper, with an ease-in-out curve.
    ease = ("temp.h = math.clamp({h}, 0.0, 1.0); temp.h = " + off("fp_ease") + " ? temp.h : "
            "temp.h * temp.h * (3.0 - 2.0 * temp.h); return {pre}-{d} * (1.0 - temp.h){post};")
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
    settings = []
    for kind, name, text in SETTINGS:
        if kind == "label":
            settings.append({"type": "label", "text": text})
        elif kind == "toggle":
            settings.append({"type": "toggle", "name": name, "text": text, "default": False})
        else:
            settings.append({"type": "slider", "name": name, "text": text, "min": 5, "max": 60, "step": 5,
                             "default": IDLE_DELAY})
    ver = ".".join(map(str, VERSION))
    save("manifest.json", {
        "format_version": 3,
        "header": {"name": "Animaciones Suaves",
                   "description": "Animaciones del jugador más suaves y nuevas (armadura, escudo, caída, élitros, "
                                  "espera). Ajustes en el engranaje del pack. Compatible con skins del Marketplace.",
                   "uuid": UUIDS["rp"], "version": ver, "min_engine_version": ".".join(map(str, MIN_ENGINE))},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": ver}],
        "settings": settings,
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
