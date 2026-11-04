"""Extracts only the mobs of the TerraDraconis Beta add-on into a standalone
add-on ("TerraDraconis Mobs").

What is kept: the creatures (crimson racer in its wild, savage and tamed forms,
shield horns, shimmer fly), the entities they need to work (fire breath, egg,
shield horn nest and the loot bag the taming spawns), their spawn rules, loot,
models, textures, animations, particles and sounds, the shield horn nest world
generation, and the scripts that drive the mobs (levels, mutations, flying,
stamina, taming, nests, flee, XP on death, spyglass stats and compass settings).

What is left out: terrain generation, custom blocks, items, weapons, armour,
recipes, workbench/engram systems, the unfinished "lapari" NPC and the
herbivore bait.

    python3 tools/terradraconis_mobs.py path/to/TerraDraconis.zip
    python3 tools/terradraconis_mobs.py path/to/extracted_folder
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "TerraDraconisMobs_BP")
RP = os.path.join(ROOT, "TerraDraconisMobs_RP")
DIST = os.path.join(ROOT, "dist")

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
]

RP_ENTITIES = ["crimson_racer", "wild_crimson_racer", "savage_crimson_racer", "crimson_racer_egg",
               "crimson_racer_fire_breath", "male_shield_horn", "female_shield_horn", "baby_shield_horn",
               "shield_horn_nest", "shimmer_fly", "lootbag"]

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
    "render_controllers/dragon_rc.json",
    "render_controllers/gender.rc.json",
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
]

# Sound events used by the mobs (entity sound effects, sounds.json) and by the
# script forms (ui_*, button). Weapon and level-up sounds are dropped.
SOUND_PREFIXES = ("crimson_racer_", "savage_crimson_racer_")
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
"""

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
    # Weapons and workbench tables are only used by the removed item scripts.
    return cut_from(text, "//Weapon And Workbench Setup", "config.js")


def trim_utility(text):
    text = replace_once(text, 'import { world, system, ItemStack, BlockPermutation, EquipmentSlot} from "@minecraft/server";',
                        'import { world, system } from "@minecraft/server";', "utility.js")
    text = replace_once(text, 'import { reduceDur } from "./weapons";\n', "", "utility.js")
    # Wood/stone processing with axes and pickaxes is an item mechanic.
    return cut_from(text, "world.afterEvents.entityHitBlock.subscribe", "utility.js")


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


def build(src):
    src_bp, src_rp = find_packs(src)
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)

    copy(src_bp, BP, BP_FILES)
    with open(os.path.join(src_bp, "scripts/config.js"), encoding="utf-8") as f:
        write(os.path.join(BP, "scripts/config.js"), trim_config(f.read()))
    with open(os.path.join(src_bp, "scripts/utility.js"), encoding="utf-8") as f:
        write(os.path.join(BP, "scripts/utility.js"), trim_utility(f.read()))
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
    write(os.path.join(RP, "texts/languages.json"), ["en_US", "es_ES", "es_MX"])
    write(os.path.join(RP, "texts/en_US.lang"), lang("en"))
    write(os.path.join(RP, "texts/es_ES.lang"), lang("es"))
    write(os.path.join(RP, "texts/es_MX.lang"), lang("es"))
    write(os.path.join(RP, "manifest.json"), manifest("rp"))

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "TerraDraconisMobs.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for dirpath, _, files in os.walk(pack):
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    z.write(full, os.path.relpath(full, ROOT))
    print("OK ->", os.path.relpath(out, ROOT))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    if os.path.isdir(src):
        build(src)
        return
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        build(tmp)


if __name__ == "__main__":
    main()
