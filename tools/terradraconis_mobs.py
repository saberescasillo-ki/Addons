"""Extracts only the mobs of the TerraDraconis Beta add-on into a standalone
add-on ("TerraDraconis Mobs").

What is kept: the creatures (crimson racer in its wild, savage and tamed forms,
shield horns, shimmer fly), the entities they need to work (fire breath, egg,
shield horn nest and the loot bag the taming spawns), their spawn rules, loot,
models, textures, animations, particles and sounds, the shield horn nest world
generation, and the scripts that drive the mobs (levels, mutations, flying,
stamina, taming, nests, flee, XP on death, spyglass stats and compass settings).
Also the weapons: steel crossbow, steel long bow, long neck rifle and steel
sword, with their steel and tranquilizer arrows and bullets.

Added here: colour variants for the dragons and the shield horns. The
textures are recoloured from the originals (COLORS below) and the
"terradraconis:color" entity property picks one; tools/terradraconis_mobs/
colors.js chooses it on spawn and keeps it when a baby grows up, an egg
hatches or a dragon is tamed.

What is left out: terrain generation, custom blocks, tools, armour, the other
items, recipes, workbench/engram systems, the unfinished "lapari" NPC and the
herbivore bait.

Fixed here: InvalidEntityError and Molang rider-index errors of the original
scripts and animations (harden_scripts, guard_rider_queries). Smaller: the
JSON is minified and the sounds re-encoded in mono (needs ffmpeg).

    python3 tools/terradraconis_mobs.py path/to/TerraDraconis.zip
    python3 tools/terradraconis_mobs.py path/to/extracted_folder
    python3 tools/terradraconis_mobs.py path/to/TerraDraconis.zip --preview  # also docs/terradraconis_colors.png
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "TerraDraconisMobs_BP")
RP = os.path.join(ROOT, "TerraDraconisMobs_RP")
DIST = os.path.join(ROOT, "dist")
COLORS_JS = os.path.join(ROOT, "tools", "terradraconis_mobs", "colors.js")

NAME = "TerraDraconis Mobs"
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 80]
UUIDS = dict(bp="5b0f3c2e-8d1a-4c47-9e62-3f7a1d2b9c41", bp_data="a7e4d915-2c3b-4f80-b6d1-0e9c5a7f3b22",
             bp_script="c3d8e1f0-6a4b-4d29-8f17-b5e2a9c04d63", rp="e91b7a3d-4f25-4c6e-a8d0-7b3c1e5f9a14",
             rp_res="2f6c9d48-b1e3-4a75-9c02-d8e4f7a1b356")

# --- Files copied unchanged (paths relative to each pack) -------------------
BP_FILES = [
    "pack_icon.png",
    "entities/animals/baby_shield_horn.json",
    "entities/animals/female_shield_horn.json",
    "entities/animals/male_shield_horn.json",
    "entities/animals/shimmer_fly.json",
    "entities/breaths/crimson_racer_fire_breath.json",
    "entities/eggs/crimson_racer_egg.json",
    "entities/nest_entity/shield_horn_nest.json",
    "entities/savage_dragon/savage_crimson_racer.json",
    "entities/tamed_dragon/crimson_racer.json",
    "entities/wild_dragons/wild_crimson_racer.json",
    "entities/lootbag.json",
    "spawn_rules/female_shield_horn.json",
    "spawn_rules/male_shield_horn.json",
    "spawn_rules/shimmer_fly.json",
    "spawn_rules/wild_crimson_racer.json",
    "loot_tables/shield_horn.json",
    "animations/camera_shakes.json",
    "animations/dragon_flying.json",
    "animations/dragon_taming.a.json",
    "animations/fire.json",
    "animations/flee_animation.json",
    "animation_controllers/dragon_camera_shakes_controllers.json",
    "animation_controllers/dragon_flying_controllers.json",
    "animation_controllers/dragon_taming_controller.json",
    "animation_controllers/flee_controllers.json",
    # Shield horn nests in plains: only vanilla blocks plus the nest entity.
    "features/shield_horn_nest.json",
    "feature_rules/shield_horn_nest_feature_rule.json",
    "structures/shield_horn_nest.mcstructure",
    # Scripts copied as they are (config.js and utility.js are trimmed below).
    "scripts/dragon_flying.js",
    "scripts/dragon_stamina.js",
    "scripts/dragon_level.js",
    "scripts/dragon_rng.js",
    "scripts/dragon_taming.js",
    "scripts/non_tameable_scaling.js",
    "scripts/shield_horn.js",
    "scripts/nest.js",
    "scripts/death_loot.js",
    # Weapons and their ammunition.
    "scripts/weapons.js",
    "items/steel_crossbow.json",
    "items/steel_long_bow.json",
    "items/long_neck_rifle.json",
    "items/steel_sword.json",
    "items/steel_arrow.json",
    "items/tranq_steel_arrow.json",
    "items/steel_bullet.json",
    "items/tranq_bullet.json",
    "entities/projectiles/steel_arrow.json",
    "entities/projectiles/tranq_steel_arrow.json",
    "entities/projectiles/steel_bullet.json",
    "entities/projectiles/tranq_bullet.json",
]

RP_ENTITIES = ["crimson_racer", "wild_crimson_racer", "savage_crimson_racer", "crimson_racer_egg",
               "crimson_racer_fire_breath", "male_shield_horn", "female_shield_horn", "baby_shield_horn",
               "shield_horn_nest", "shimmer_fly", "lootbag", "steel_arrow", "tranq_steel_arrow"]
WEAPONS = ["steel_crossbow", "steel_long_bow", "long_neck_rifle", "steel_sword",
           "steel_arrow", "tranq_steel_arrow", "steel_bullet", "tranq_bullet"]

RP_FILES = [
    "pack_icon.png",
    "sounds.json",
    *[f"entity/{e}.json" for e in RP_ENTITIES],
    "models/entity/crimson_racer.geo.json",
    "models/entity/crimson_racer_egg.geo.json",
    "models/entity/shield_horn.geo.json",
    "models/entity/nest.geo.json",
    "models/entity/shimmer_fly.geo.json",
    "models/entity/lootbag.geo.json",
    "animations/crimson_racer.animation.json",
    "animations/crimson_racer_egg.animation.json",
    "animations/dragon_fire_breath.json",
    "animations/cooldown_timers.json",
    "animations/shield_horn.animation.json",
    "animations/shimmer_fly.animation.json",
    "animation_controllers/dragons.json",
    "animation_controllers/shield_horn.json",
    "render_controllers/shimmer_fly.json",
    "particles/eye_aura.json",
    "particles/fire_breath.json",
    "particles/phase_aura.json",
    "textures/particle/glow.png",
    "textures/entity/crimson_racer_texture.png",
    "textures/entity/crimson_racer_saddled_texture.png",
    "textures/entity/savage_crimson_racer_texture.png",
    "textures/entity/crimson_racer_egg_texture.png",
    "textures/entity/shield_horn_texture.png",
    "textures/entity/female_shield_horn_texture.png",
    "textures/entity/male_baby_shield_horn_texture.png",
    "textures/entity/female_baby_shield_horn_texture.png",
    "textures/entity/nest_texture.png",
    "textures/entity/shimmer_fly_texture.png",
    "textures/entity/shimmer_fly_texture2.png",
    "textures/entity/shimmer_fly_texture3.png",
    "textures/entity/shimmer_fly_texture4.png",
    "textures/entity/shimmer_fly_texture5.png",
    "textures/entity/lootbag_texture.png",
    # Weapons: held models, icons and the rifle's muzzle flash.
    *[f"attachables/{w}.json" for w in WEAPONS],
    *[f"textures/attachables/{w}_texture.png" for w in WEAPONS],
    *[f"textures/items/{w}.png" for w in WEAPONS],
    "models/entity/steel_crossbow.geo.json",
    "models/entity/steel_long_bow.geo.json",
    "models/entity/long_neck_rifle.geo.json",
    "models/entity/steel_sword.geo.json",
    "models/entity/steel_arrow.geo.json",
    "models/entity/steel_bullet.geo.json",
    "animations/steel_crossbow.animation.json",
    "animations/steel_long_bow.animation.json",
    "animations/long_neck_rifle.animation.json",
    "animations/steel_axe.animation.json",  # the sword uses its animations
    "animations/steel_arrow.animation.json",
    "animations/steel_bullet.animation.json",
    "animation_controllers/weapons.ac.json",
    "render_controllers/steel_crossbow.json",
    "particles/shoot_effect.json",
]

# Sound events used by the mobs (entity sound effects, sounds.json), the
# weapons and the script forms (ui_*, button). The level-up sound is dropped.
SOUND_PREFIXES = ("crimson_racer_", "savage_crimson_racer_", "steel_crossbow_", "steel_long_bow_", "long_neck_rifle_")
SOUND_EXTRA = {"wind_sound", "ui_popup", "ui_exit", "ui_save", "button"}

MAIN_JS = """import 'config'
import 'dragon_flying'
import 'dragon_stamina'
import 'dragon_level'
import 'dragon_rng'
import 'utility'
import 'dragon_taming'
import 'non_tameable_scaling'
import 'shield_horn'
import 'nest'
import 'death_loot'
import 'weapons'
import 'colors'
"""

# --- Colour variants --------------------------------------------------------
# Each colour recolours the "body" pixels of the original texture: the red
# scales of the dragon, the grey/slate hide of the shield horn. Horns, eyes,
# teeth and the saddle keep their colours. hue = new hue (0-1); sm/sa and
# vm/va multiply and add to saturation and brightness.
COLORS = {
    "dragon": [
        ("crimson", "Carmesí", None),  # original
        ("sapphire", "Zafiro", dict(hue=0.60, sm=0.9)),
        ("emerald", "Esmeralda", dict(hue=0.36, sm=0.9, vm=0.95)),
        ("obsidian", "Obsidiana", dict(hue=0.70, sm=0.25, vm=0.42)),
        ("amethyst", "Amatista", dict(hue=0.79, sm=0.9)),
        ("gold", "Dorado", dict(hue=0.115, vm=1.2, va=0.04)),
        ("frost", "Escarcha", dict(hue=0.55, sm=0.15, vm=0.5, va=0.45)),
    ],
    "shield_horn": [
        ("slate", "Original", None),
        ("sand", "Arena", dict(hue=0.10, sm=0.5, sa=0.25, vm=1.45, va=0.10)),
        ("rust", "Óxido", dict(hue=0.035, sm=0.6, sa=0.38, vm=1.25, va=0.03)),
        ("moss", "Musgo", dict(hue=0.25, sm=0.5, sa=0.22, vm=1.15, va=0.03)),
        ("ivory", "Marfil", dict(hue=0.11, sm=0.1, sa=0.06, vm=0.7, va=0.42)),
        ("onyx", "Ónice", dict(hue=0.65, sm=0.3, vm=0.55)),
    ],
}
# Coloured entities: family, and the texture of each original slot. Entities
# with two slots pick the slot with query.variant (saddle, baby's gender).
COLORED = {
    "wild_crimson_racer": ("dragon", ["crimson_racer_texture"]),
    "savage_crimson_racer": ("dragon", ["savage_crimson_racer_texture"]),
    "crimson_racer": ("dragon", ["crimson_racer_texture", "crimson_racer_saddled_texture"]),
    "male_shield_horn": ("shield_horn", ["shield_horn_texture"]),
    "female_shield_horn": ("shield_horn", ["female_shield_horn_texture"]),
    "baby_shield_horn": ("shield_horn", ["male_baby_shield_horn_texture", "female_baby_shield_horn_texture"]),
}
COLOR_PROP = "terradraconis:color"

# Entity names: (English, Spanish).
NAMES = {
    "wild_crimson_racer": ("Crimson Racer", "Corredor Carmesí"),
    "crimson_racer": ("Crimson Racer", "Corredor Carmesí"),
    "savage_crimson_racer": ("Savage Crimson Racer", "Corredor Carmesí Salvaje"),
    "crimson_racer_egg": ("Crimson Racer Egg", "Huevo de Corredor Carmesí"),
    "crimson_racer_fire_breath": ("Fire Breath", "Aliento de fuego"),
    "male_shield_horn": ("Shield Horn", "Cuerno Escudo"),
    "female_shield_horn": ("Shield Horn", "Cuerno Escudo"),
    "baby_shield_horn": ("Baby Shield Horn", "Cría de Cuerno Escudo"),
    "shield_horn_nest": ("Shield Horn Nest", "Nido de Cuerno Escudo"),
    "shimmer_fly": ("Shimmer Fly", "Mosca Centelleante"),
    "lootbag": ("Loot Bag", "Bolsa de botín"),
    "steel_arrow": ("Steel Arrow", "Flecha de acero"),
    "tranq_steel_arrow": ("Tranq Steel Arrow", "Flecha tranquilizante"),
    "steel_bullet": ("Steel Bullet", "Bala de acero"),
    "tranq_bullet": ("Tranq Bullet", "Bala tranquilizante"),
}
SPAWN_EGG = {"en": "Spawn %s", "es": "Generar %s"}


def find_packs(src):
    """Returns the (BP, RP) folders inside an extracted add-on."""
    bp = rp = None
    for dirpath, _, files in os.walk(src):
        if "manifest.json" not in files:
            continue
        with open(os.path.join(dirpath, "manifest.json"), encoding="utf-8-sig") as f:
            types = {m["type"] for m in json.load(f)["modules"]}
        if "resources" in types:
            rp = dirpath
        elif "data" in types:
            bp = dirpath
    if not bp or not rp:
        sys.exit("No se encontraron los packs BP y RP de TerraDraconis en " + src)
    return bp, rp


def replace_once(text, old, new, name):
    if text.count(old) != 1:
        sys.exit(f"{name}: no se encontró el texto a reemplazar; ¿cambió el addon original?")
    return text.replace(old, new)


def cut_from(text, marker, name):
    """Drops everything from marker to the end of the file."""
    i = text.find(marker)
    if i < 0:
        sys.exit(f"{name}: falta {marker!r}; ¿cambió el addon original?")
    return text[:i].rstrip() + "\n"


def trim_config(text):
    # The first-spawn block gives the Dragon Slayer Codex and sets up engrams
    # (item systems that are not part of this pack); world defaults stay.
    start = text.index('    const spawn = player.getDynamicProperty("spawn");')
    end = text.index("});", text.index("player.setDynamicProperty(\"spawn\", true);"))
    end = text.index("}", end + 3) + 1  # closing brace of `if (!spawn)`
    text = text[:start].rstrip() + "\n" + text[end:].lstrip("\n")
    # Reforge and workbench tables are only used by the removed workbench.
    return cut_from(text, "export const ReforgeItem", "config.js")


def patch_taming(text):
    # The tamed dragon is a new entity: it keeps the wild one's colour.
    text = replace_once(text, "  if (!newEntity) return;\n",
                        "  if (!newEntity) return;\n"
                        f'  newEntity.setProperty("{COLOR_PROP}", entity.getProperty("{COLOR_PROP}") ?? 0);\n',
                        "dragon_taming.js")
    # Original bugs: the health boost went to the wild dragon, already removed
    # by then, and the naming prompt read owner.location without an owner.
    wake = '    newEntity.runCommandAsync("/playanimation @s wake");\n'
    text = replace_once(text, wake, "    if (!newEntity.isValid()) return;\n" + wake, "dragon_taming.js")
    for effect in ("health_boost", "instant_health"):
        text = replace_once(text, f'      entity.addEffect("{effect}"', f'      newEntity.addEffect("{effect}"',
                            "dragon_taming.js")
    naming = "  // Prompt naming if owner is nearby\n"
    return replace_once(text, naming, naming + "  if (!owner) return;\n", "dragon_taming.js")


# Entities can be gone by the time an after-event runs (killed, despawned,
# transformed). The original scripts then call applyDamage/getComponent on
# them and the content log shows InvalidEntityError.
HARDEN = [
    (re.compile(r"^(\s*)const target = event\.hurtEntity;\n", re.M), r"\g<0>\1if (!target?.isValid()) return;\n"),
    (re.compile(r"if \(source\) \{"), "if (source?.isValid()) {"),
    (re.compile(r"target\.applyDamage\(extraDamage\);"), "if (target.isValid()) target.applyDamage(extraDamage);"),
    (re.compile(r"if \(!target \|\| !projectile\) return;"),
     "if (!target?.isValid() || !projectile?.isValid()) return;"),
]
# Debug output of the original that only fills the content log.
DEBUG_LINES = ["            console.warn(entity.nameTag)\n",
               "            console.warn(`[Init] Set default ${key} to ${value}`);\n"]


def harden_scripts():
    for name in sorted(os.listdir(os.path.join(BP, "scripts"))):
        if name == "colors.js":
            continue
        path = os.path.join(BP, "scripts", name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for pattern, repl in HARDEN:
            text = pattern.sub(repl, text)
        for line in DEBUG_LINES:
            text = text.replace(line, "")
        write(path, text)


# Molang: query.rider_*_rotation(0) logs an error every frame while the dragon
# has no rider (original bug). Only ask for it when there is one.
RIDER_QUERIES = [
    ("query.rider_head_x_rotation(0)", "(query.has_rider ? query.rider_head_x_rotation(0) : 0)"),
    ("query.rider_body_y_rotation(0)", "(query.has_rider ? query.rider_body_y_rotation(0) : query.body_y_rotation)"),
]


def guard_rider_queries():
    for pack in (BP, RP):
        for dirpath, _, files in os.walk(pack):
            for name in files:
                if not name.endswith(".json") or name.endswith(".geo.json"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8-sig") as f:
                    text = f.read()
                new = text
                for query, guarded in RIDER_QUERIES:
                    new = new.replace(query, guarded)
                if new != text:
                    write(path, new)


# --- Size ---------------------------------------------------------------------
def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate keys")
    return dict(pairs)


def _round_floats(obj):
    if isinstance(obj, float):
        r = round(obj, 5)
        return int(r) if r == int(r) else r
    if isinstance(obj, list):
        return [_round_floats(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    return obj


def minify_json():
    """Writes every JSON file without indentation (the models were ~40 % spaces).
    Numbers keep 5 decimals, as many as the original models use."""
    for pack in (BP, RP):
        for dirpath, _, files in os.walk(pack):
            for name in files:
                if not name.endswith(".json"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8-sig") as f:
                    text = re.sub(r"^\s*//.*$", "", f.read(), flags=re.M)
                try:
                    data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
                except ValueError:
                    continue  # files with duplicate keys stay exactly as they are
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(_round_floats(data), f, separators=(",", ":"), ensure_ascii=False)


def compress_sounds():
    """Re-encodes the sounds as mono Vorbis q5: they were stereo at maximum
    quality (~500 kbps), and positional mob sounds play in mono anyway."""
    if not shutil.which("ffmpeg"):
        print("Aviso: sin ffmpeg los sonidos se copian sin comprimir.")
        return
    for dirpath, _, files in os.walk(os.path.join(RP, "sounds")):
        for name in files:
            if not name.endswith(".ogg"):
                continue
            path = os.path.join(dirpath, name)
            tmp = path + ".tmp.ogg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map_metadata", "-1", "-ac", "1",
                            "-c:a", "libvorbis", "-q:a", "5", "-fflags", "+bitexact", "-flags:a", "+bitexact", tmp],
                           check=True)
            if os.path.getsize(tmp) < os.path.getsize(path):
                os.replace(tmp, path)
            else:
                os.remove(tmp)


def trim_utility(text):
    text = replace_once(text, 'import { world, system, ItemStack, BlockPermutation, EquipmentSlot} from "@minecraft/server";',
                        'import { world, system } from "@minecraft/server";', "utility.js")
    text = replace_once(text, 'import { reduceDur } from "./weapons";\n', "", "utility.js")
    # Wood/stone processing with axes and pickaxes is an item mechanic.
    return cut_from(text, "world.afterEvents.entityHitBlock.subscribe", "utility.js")


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.loads(re.sub(r"^\s*//.*$", "", f.read(), flags=re.M))


# --- Colour variants --------------------------------------------------------
def _rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6
    h[gm] = (b - r)[gm] / d[gm] + 2
    h[bm] = (r - g)[bm] / d[bm] + 4
    return h / 6, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0), mx


def _hsv_to_rgb(h, s, v):
    i = np.floor(h * 6) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    out = np.zeros(h.shape + (3,))
    for k, chans in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
        m = i == k
        for c in range(3):
            out[..., c][m] = chans[c][m]
    return out


def _hue_offset(h, center):
    return (h - center + 0.5) % 1 - 0.5


def recolor(img, family, p):
    a = np.asarray(img.convert("RGBA")).astype(np.float64) / 255
    h, s, v = _rgb_to_hsv(a[..., :3])
    if family == "dragon":
        # Red/orange scales; keeps the hue variation a bit (spread).
        rel = _hue_offset(h, 0.0)
        mask = (s > 0.2) & (np.abs(rel) < 30 / 360)
        spread = 0.6
    else:
        # Grey (female) or blue-grey slate (male) hide, not the white details.
        off = _hue_offset(h, 215 / 360)
        rel = np.where(s >= 0.15, off, 0)
        mask = ((s < 0.15) | (np.abs(off) < 45 / 360)) & ~((v > 0.88) & (s < 0.12))
        spread = 0.3
    mask &= a[..., 3] > 0
    rgb = _hsv_to_rgb((p["hue"] + rel * spread) % 1,
                      np.clip(s * p.get("sm", 1) + p.get("sa", 0), 0, 1),
                      np.clip(v * p.get("vm", 1) + p.get("va", 0), 0, 1))
    out = a.copy()
    out[..., :3] = np.where(mask[..., None], rgb, a[..., :3])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def color_texture_path(base, color_id, index):
    """Texture path (without .png) of colour `index`; the first is the original."""
    return f"textures/entity/{base}" if index == 0 else f"textures/entity/colors/{base}_{color_id}"


def make_color_textures(src_rp):
    done = set()
    for family, bases in COLORED.values():
        for base in bases:
            if base in done:
                continue
            done.add(base)
            img = Image.open(os.path.join(src_rp, f"textures/entity/{base}.png"))
            for i, (cid, _, params) in enumerate(COLORS[family]):
                if params is None:
                    continue
                out = os.path.join(RP, color_texture_path(base, cid, i) + ".png")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                recolor(img, family, params).save(out, optimize=True)


def add_color_property(bp_entity_path, family):
    data = load_json(bp_entity_path)
    desc = data["minecraft:entity"]["description"]
    desc.setdefault("properties", {})[COLOR_PROP] = {
        "type": "int", "range": [0, len(COLORS[family])], "default": 0, "client_sync": True}
    write(bp_entity_path, json.dumps(data, indent=4, ensure_ascii=False) + "\n")


def color_render_controller(family, slots):
    """Array of every colour x slot; property 0 (not chosen yet) shows colour 1."""
    textures = []
    for cid, _, _ in [COLORS[family][0]] + COLORS[family]:
        textures += [f"Texture.{cid}_{s}" for s in range(slots)]
    index = f"query.property('{COLOR_PROP}')"
    if slots > 1:
        index = f"{index} * {slots} + query.variant"
    return {
        "arrays": {"textures": {"Array.skins": textures}},
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": [f"Array.skins[{index}]"],
    }


def apply_colors():
    """Adds the colour property (BP) and colour textures + render controller (RP)."""
    controllers = {}
    bp_paths = {os.path.splitext(os.path.basename(f))[0]: os.path.join(BP, f)
                for f in BP_FILES if f.startswith("entities/")}
    for ident, (family, bases) in COLORED.items():
        add_color_property(bp_paths[ident], family)
        rc = f"controller.render.terradraconis_{ident}_color"
        controllers[rc] = color_render_controller(family, len(bases))
        path = os.path.join(RP, f"entity/{ident}.json")
        data = load_json(path)
        desc = data["minecraft:client_entity"]["description"]
        desc["textures"] = {f"{cid}_{s}": color_texture_path(base, cid, i)
                            for i, (cid, _, _) in enumerate(COLORS[family])
                            for s, base in enumerate(bases)}
        desc["render_controllers"] = [rc]
        write(path, json.dumps(data, indent=4, ensure_ascii=False) + "\n")
    write(os.path.join(RP, "render_controllers/terradraconis_colors.json"),
          {"format_version": "1.10.0", "render_controllers": controllers})


def preview(src_rp, out):
    """Strip of every colour, cut from the textures, for the README."""
    rows = [("crimson_racer_texture", "dragon", (0, 0, 420, 420)),
            ("shield_horn_texture", "shield_horn", (0, 0, 260, 260))]
    cell, label = 150, 22
    cols = max(len(COLORS[f]) for _, f, _ in rows)
    img = Image.new("RGBA", (cols * cell, len(rows) * (cell + label)), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    for y, (base, family, box) in enumerate(rows):
        for x, (cid, name, _) in enumerate(COLORS[family]):
            tex = Image.open(os.path.join(RP, color_texture_path(base, cid, x) + ".png")).convert("RGBA")
            img.alpha_composite(tex.crop(box).resize((cell, cell), Image.LANCZOS), (x * cell, y * (cell + label)))
            draw.text((x * cell + 6, y * (cell + label) + cell + 4), name, fill=(30, 30, 30, 255), font=font)
    img.save(out)


def manifest(kind):
    if kind == "bp":
        return {
            "format_version": 2,
            "header": {"name": NAME, "description": "Solo los mobs de TerraDraconis Beta: dragones y animales.",
                       "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
            "modules": [
                {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
                {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
                 "entry": "scripts/main.js"},
            ],
            "dependencies": [
                {"uuid": UUIDS["rp"], "version": VERSION},
                {"module_name": "@minecraft/server", "version": "1.18.0"},
                {"module_name": "@minecraft/server-ui", "version": "1.3.0"},
            ],
        }
    return {
        "format_version": 2,
        "header": {"name": NAME, "description": "Recursos de los mobs de TerraDraconis Beta.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }


def lang(code):
    lines = []
    for ident, names in NAMES.items():
        name = names[0] if code == "en" else names[1]
        lines.append(f"entity.terradraconis:{ident}.name={name}")
        lines.append(f"item.spawn_egg.entity.terradraconis:{ident}.name={SPAWN_EGG[code] % name}")
    lines.append(f"pack.name={NAME}")
    return "\n".join(lines) + "\n"


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content if isinstance(content, str) else json.dumps(content, indent=2, ensure_ascii=False) + "\n")


def copy(src_pack, dst_pack, files):
    for rel in files:
        src = os.path.join(src_pack, rel)
        if not os.path.isfile(src):
            sys.exit("Falta en el addon original: " + rel)
        dst = os.path.join(dst_pack, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)


def build(src, with_preview=False):
    src_bp, src_rp = find_packs(src)
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)

    copy(src_bp, BP, BP_FILES)
    with open(os.path.join(src_bp, "scripts/config.js"), encoding="utf-8") as f:
        write(os.path.join(BP, "scripts/config.js"), trim_config(f.read()))
    with open(os.path.join(src_bp, "scripts/utility.js"), encoding="utf-8") as f:
        write(os.path.join(BP, "scripts/utility.js"), trim_utility(f.read()))
    with open(os.path.join(src_bp, "scripts/dragon_taming.js"), encoding="utf-8") as f:
        write(os.path.join(BP, "scripts/dragon_taming.js"), patch_taming(f.read()))
    shutil.copyfile(COLORS_JS, os.path.join(BP, "scripts/colors.js"))
    write(os.path.join(BP, "scripts/main.js"), MAIN_JS)
    write(os.path.join(BP, "manifest.json"), manifest("bp"))

    copy(src_rp, RP, RP_FILES)
    with open(os.path.join(src_rp, "sounds/sound_definitions.json"), encoding="utf-8-sig") as f:
        sounds = json.load(f)
    sounds["sound_definitions"] = {k: v for k, v in sounds["sound_definitions"].items()
                                   if k.startswith(SOUND_PREFIXES) or k in SOUND_EXTRA}
    write(os.path.join(RP, "sounds/sound_definitions.json"), sounds)
    oggs = sorted({s if isinstance(s, str) else s["name"]
                   for v in sounds["sound_definitions"].values() for s in v["sounds"]})
    copy(src_rp, RP, [s + ".ogg" for s in oggs])
    items = load_json(os.path.join(src_rp, "textures/item_texture.json"))
    items["resource_pack_name"] = NAME
    items["texture_data"] = {k: v for k, v in items["texture_data"].items() if k in WEAPONS}
    write(os.path.join(RP, "textures/item_texture.json"), items)
    make_color_textures(src_rp)
    apply_colors()
    write(os.path.join(RP, "texts/languages.json"), ["en_US", "es_ES", "es_MX"])
    write(os.path.join(RP, "texts/en_US.lang"), lang("en"))
    write(os.path.join(RP, "texts/es_ES.lang"), lang("es"))
    write(os.path.join(RP, "texts/es_MX.lang"), lang("es"))
    write(os.path.join(RP, "manifest.json"), manifest("rp"))

    harden_scripts()
    guard_rider_queries()
    compress_sounds()
    minify_json()

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "TerraDraconisMobs.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, files in os.walk(pack):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    # Fixed date: the same packs give the same .mcaddon.
                    info = zipfile.ZipInfo(os.path.relpath(full, ROOT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    print("OK ->", os.path.relpath(out, ROOT))
    if with_preview:
        preview(src_rp, os.path.join(ROOT, "docs", "terradraconis_colors.png"))


def main():
    args = [a for a in sys.argv[1:] if a != "--preview"]
    if len(args) != 1:
        sys.exit(__doc__)
    with_preview = "--preview" in sys.argv
    src = args[0]
    if os.path.isdir(src):
        build(src, with_preview)
        return
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        build(tmp, with_preview)


if __name__ == "__main__":
    main()
