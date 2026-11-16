"""Builds the "Underworld" add-on: a procedurally generated dimension of deepslate, soul sand and bones.

- The dimension (underworld:underworld) is registered by the script with the Custom
  Dimension API (Beta APIs experiment). The script fills it with a closed cavern world,
  like the Nether, one cell of 4x4 chunks at a time, around the players.
- Mena de Roca Alucinogena (underworld:hallucinogenic_rock_ore): generated in the
  negative layers of the Overworld (and, rarely, in the Underworld). It drops the
  Roca Alucinogena (underworld:hallucinogenic_rock).
- Using the rock gives blindness and nausea for a few seconds and then takes you to
  the Underworld; used there, it brings you back to your last position in the
  Overworld. 30 s cooldown.
- Only skeletal mobs appear there.

The terrain is built by tools/underworld/gen.js, which is copied into the pack as it
is; tools/underworld/simulate.mjs runs it with Node to check it and draw the preview.

    python3 tools/underworld.py            # regenerate the packs and the .mcaddon
    python3 tools/underworld.py --preview  # also refresh docs/underworld_preview.png (needs node)
"""
import base64
import json
import os
import random
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "underworld")
ADDON_NAME = "Underworld"
BP = os.path.join(ROOT, "Underworld_BP")
RP = os.path.join(ROOT, "Underworld_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "beta"         # registerCustomDimension is only in the beta module
MIN_ENGINE = [1, 26, 20]    # the Custom Dimension API arrived in 26.20
UUIDS = dict(bp="b3f0c7a2-6f0e-4d1b-9a55-2e7f1c0d8a41", bp_data="0c9d4e7b-51a3-4f2e-8b6d-7a1e3c5f9b20",
             bp_script="7e2a9b14-3c6d-4e8f-a1b0-5d4c3b2a1f6e", rp="d48f1a6c-2b3e-4c7d-9e0f-6a5b4c3d2e1f",
             rp_res="5a6b7c8d-9e0f-4a1b-8c2d-3e4f5a6b7c8d")

NS = "underworld"
DIMENSION = f"{NS}:underworld"
ROCK = f"{NS}:hallucinogenic_rock"
ORE = f"{NS}:hallucinogenic_rock_ore"
FOG = f"{NS}:underworld_fog"

TRANCE = 4       # seconds of blindness and nausea before the trip
COOLDOWN = 30    # seconds before the rock can be used again

# Everything main.js uses besides the generator.
CONFIG = dict(
    dimension=DIMENSION,
    rock=ROCK,
    fog=FOG,
    trance=TRANCE,
    cooldown=COOLDOWN,
    radius=2,          # cells (of 4x4 chunks) generated around each player: 5x5 cells
    opsPerStep=24,     # block operations between pauses while generating
    # mobs: only skeletal ones. Any other mob is removed as it appears.
    skeletal=["minecraft:skeleton", "minecraft:stray", "minecraft:wither_skeleton", "minecraft:bogged",
              "minecraft:parched", "minecraft:skeleton_horse", "minecraft:wither"],
    mobs=dict(   # what appears on each kind of floor: [mob, weight]
        slate=[["minecraft:skeleton", 60], ["minecraft:wither_skeleton", 22], ["minecraft:bogged", 12],
               ["minecraft:skeleton_horse", 3]],
        soul=[["minecraft:skeleton", 40], ["minecraft:stray", 38], ["minecraft:wither_skeleton", 20]],
        bone=[["minecraft:skeleton", 45], ["minecraft:wither_skeleton", 28], ["minecraft:bogged", 12],
              ["minecraft:parched", 10], ["minecraft:skeleton_horse", 4]],
    ),
    mobCap=9,          # skeletal mobs around a player before the script stops adding more
    spawnEvery=80,     # ticks between spawn attempts
    spawnMin=14, spawnMax=34,
)

PREVIEW_SEED = 20261116

LANG = {
    "es": {
        f"item.{ROCK}.name": "Roca Alucinógena",
        f"tile.{ORE}.name": "Mena de Roca Alucinógena",
        "pack.name": ADDON_NAME,
        "pack.description": "Una dimensión de pizarra profunda, arena de almas y huesos.",
    },
    "en": {
        f"item.{ROCK}.name": "Hallucinogenic Rock",
        f"tile.{ORE}.name": "Hallucinogenic Rock Ore",
        "pack.name": ADDON_NAME,
        "pack.description": "A dimension of deepslate, soul sand and bones.",
    },
}


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- textures
TRIP = ["#ff4fd8", "#b04bff", "#5cf0c8", "#ffe14f", "#7a3fd0"]


def ore_texture():
    """Deepslate with veins of a rock whose colours never settle."""
    rnd = random.Random(7)
    im = Image.new("RGBA", (16, 16))
    px = im.load()
    for y in range(16):
        row = rnd.choice([0x47, 0x4d, 0x53, 0x4a])
        for x in range(16):
            v = row + rnd.randint(-7, 7) - (8 if (x + y * 3) % 7 == 0 else 0)
            px[x, y] = (v, v, v + 4, 255)
    blobs = [(3, 3), (10, 2), (12, 8), (5, 9), (8, 13), (1, 13)]
    for i, (bx, by) in enumerate(blobs):
        shape = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2)] if i % 2 == 0 else [(0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
        for j, (dx, dy) in enumerate(shape):
            x, y = (bx + dx) % 16, (by + dy) % 16
            px[x, y] = hx(TRIP[(i + j) % len(TRIP)])
        # dark rim under each vein, a spark on top
        x, y = (bx + 1) % 16, (by + 3 if i % 2 == 0 else by + 2) % 16
        px[x, y] = hx("#26262b")
        px[bx % 16, by % 16] = hx("#ffffff")
    return im


def rock_icon():
    """A rough stone, swirling with colour."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = im.load()
    rows = {2: (6, 9), 3: (4, 11), 4: (3, 12), 5: (2, 13), 6: (2, 13), 7: (1, 13), 8: (1, 14), 9: (2, 14),
            10: (2, 13), 11: (3, 13), 12: (4, 12), 13: (6, 10)}
    rnd = random.Random(3)
    for y, (a, b) in rows.items():
        for x in range(a, b + 1):
            v = 0x58 + rnd.randint(-8, 8) - (y - 7) * 3
            px[x, y] = (v, v, v + 6, 255)
    for y, (a, b) in rows.items():   # outline
        for x in (a, b):
            px[x, y] = hx("#1c1c22")
    for x in range(6, 10):
        px[x, 2] = hx("#1c1c22")
    for x in range(6, 11):
        px[x, 13] = hx("#1c1c22")
    # the swirl: a spiral of colour from the middle of the rock
    spiral = [(7, 7), (8, 7), (8, 8), (7, 9), (6, 9), (5, 8), (5, 7), (5, 6), (6, 5), (7, 4), (8, 4), (9, 5),
              (10, 6), (11, 7), (11, 8), (11, 9), (10, 10), (9, 11), (8, 11), (7, 11)]
    for i, (x, y) in enumerate(spiral):
        px[x, y] = hx(TRIP[(i // 3) % len(TRIP)])
    px[7, 7] = hx("#ffffff")
    px[4, 5] = hx("#8a8a94")
    px[5, 4] = hx("#8a8a94")
    return im


# ---------------------------------------------------------------- behavior pack
def rock_item():
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": ROCK, "menu_category": {"category": "items"}},
        "components": {
            "minecraft:icon": "underworld_hallucinogenic_rock",
            "minecraft:display_name": {"value": f"item.{ROCK}.name"},
            "minecraft:max_stack_size": 16,
            "minecraft:glint": True,
            "minecraft:cooldown": {"category": ROCK, "duration": COOLDOWN},
            "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
        }}}


def ore_block():
    return {"format_version": "1.21.60", "minecraft:block": {
        "description": {"identifier": ORE, "menu_category": {"category": "nature"}},
        "components": {
            "minecraft:destructible_by_mining": {"seconds_to_destroy": 3},
            "minecraft:destructible_by_explosion": {"explosion_resistance": 3},
            "minecraft:geometry": "minecraft:geometry.full_block",
            "minecraft:material_instances": {"*": {"texture": "underworld_hallucinogenic_rock_ore",
                                                   "render_method": "opaque"}},
            "minecraft:loot": "loot_tables/blocks/underworld/hallucinogenic_rock_ore.json",
            "minecraft:light_emission": 5,
            "minecraft:map_color": "#b04bff",
        }}}


def ore_loot():
    return {"pools": [{"rolls": 1, "entries": [{"type": "item", "name": ROCK, "weight": 1}]}]}


def ore_feature():
    return {"format_version": "1.17.0", "minecraft:ore_feature": {
        "description": {"identifier": f"{ORE}_feature"},
        "count": 4,
        "replace_rules": [{"places_block": ORE, "may_replace": ["minecraft:deepslate"]}]}}


def ore_feature_rule():
    """Small veins in the negative layers of the Overworld."""
    return {"format_version": "1.13.0", "minecraft:feature_rules": {
        "description": {"identifier": f"{NS}:overworld_hallucinogenic_rock_ore", "places_feature": f"{ORE}_feature"},
        "conditions": {
            "placement_pass": "underground_pass",
            "minecraft:biome_filter": [{"any_of": [
                {"test": "has_biome_tag", "operator": "==", "value": "overworld"},
                {"test": "has_biome_tag", "operator": "==", "value": "overworld_generation"}]}]},
        "distribution": {
            "iterations": 3,
            "coordinate_eval_order": "zyx",
            "x": {"distribution": "uniform", "extent": [0, 16]},
            "y": {"distribution": "uniform", "extent": [-60, -4]},
            "z": {"distribution": "uniform", "extent": [0, 16]}}}}


def fog():
    """Thick and cold: the caverns fade into it before the edge of what is generated."""
    def layer(start, end, color):
        return {"fog_start": start, "fog_end": end, "fog_color": color, "render_distance_type": "fixed"}
    return {"format_version": "1.16.100", "minecraft:fog_settings": {
        "description": {"identifier": FOG},
        "distance": {"air": layer(6, 76, "#0a1a1e"), "weather": layer(6, 76, "#0a1a1e"),
                     "water": layer(2, 24, "#06282e"), "lava": layer(0.0, 0.6, "#991a00"),
                     "lava_resistance": layer(2, 20, "#991a00"), "powder_snow": layer(0.5, 1.5, "#f9ffff")}}}


def script():
    with open(os.path.join(SRC, "main.js"), encoding="utf-8") as f:
        return f.read().replace("__CONFIG__", json.dumps(CONFIG))


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": LANG["es"]["pack.description"],
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SCRIPT_API}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Texturas y niebla del Underworld.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


# ---------------------------------------------------------------- simulation render
COLORS = {
    "deepslate": "#4d4d52", "cobbled_deepslate": "#5a5a60", "bedrock": "#2a2a2a", "soul_sand": "#5b4538",
    "soul_soil": "#4b3a2f", "lava": "#e8701a", "bone_block": "#d8d3bd", "polished_deepslate": "#555559",
    "deepslate_bricks": "#46464a", "cracked_deepslate_bricks": "#444448", "deepslate_tiles": "#38383c",
    "cracked_deepslate_tiles": "#333337", "chiseled_deepslate": "#3d3d41", "cobbled_deepslate_wall": "#5a5a60",
    "soul_fire": "#4fe6f0", "soul_lantern": "#8ff4ff", "skeleton_skull": "#c8c8c0", "chest": "#a2702e",
    ORE: "#c04bff", "deepslate_coal_ore": "#3a3a3e", "deepslate_iron_ore": "#a08670",
    "deepslate_copper_ore": "#5aa58a", "deepslate_gold_ore": "#d8c04a", "deepslate_redstone_ore": "#b03030",
    "deepslate_lapis_ore": "#3050b0", "deepslate_diamond_ore": "#50d0d8", "deepslate_emerald_ore": "#30c060",
}
GLOW = {"lava", "soul_fire", "soul_lantern"}
SMALL = {"soul_fire", "soul_lantern", "skeleton_skull", "cobbled_deepslate_wall"}


def simulate(seed, cells):
    args = ["node", os.path.join(SRC, "simulate.mjs"), "blocks", str(seed)] + [f"{x},{z}" for x, z in cells]
    out = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    for cell in out:
        cell["grid"] = base64.b64decode(cell["grid"])
    return out


def find_cells(seed, radius=3):
    """One cell of each biome, the ones with the most things to see."""
    args = ["node", "--input-type=module", "-e",
            f"import {{buildCellSync}} from '{SRC}/gen.js';const o=[];"
            f"for(let x=-{radius};x<={radius};x++)for(let z=-{radius};z<={radius};z++)"
            f"{{const c=buildCellSync(x,z,{seed});o.push([x,z,c.info,c.biomes])}}console.log(JSON.stringify(o))"]
    cells = json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)
    picks = []
    for biome in range(3):
        best = max(cells, key=lambda c: c[3][biome] + 900 * len(set(c[2][1:])))
        picks.append((best[0], best[1]))
        cells.remove(best)
    return picks


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (255,)


def render_cell(cell, s=4, cut=None):
    """Isometric view of one cell with the roof taken off at y = cut, seen from the south-east."""
    n, h, grid, names = cell["size"], cell["height"], cell["grid"], cell["names"]
    cut = cut or h - 1
    colors = [hx(COLORS.get(nm, "#ff00ff")) for nm in names]

    def at(x, y, z):
        if x < 0 or z < 0 or x >= n or z >= n or y < 0:
            return 1
        return 0 if y >= cut else grid[(x * n + z) * h + y]

    width, height = n * 2 * s + 4 * s, n * s + cut * s * 2 + 4 * s
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = n * s + 2 * s, cut * s * 2

    def proj(x, y, z):
        return (ox + (x - z) * s, oy + (x + z) * s / 2 - y * s * 2)

    small = {i for i, nm in enumerate(names) if nm in SMALL}
    glow = {i for i, nm in enumerate(names) if nm in GLOW}
    for k in range(2 * n - 1):
        for x in range(max(0, k - n + 1), min(n, k + 1)):
            z = k - x
            base = (x * n + z) * h
            for y in range(cut):
                b = grid[base + y]
                if not b:
                    continue
                up, east, south = at(x, y + 1, z), at(x + 1, y, z), at(x, y, z + 1)
                if x == n - 1:
                    east = 0
                if z == n - 1:
                    south = 0
                c = colors[b]
                if b in small:
                    d.polygon([proj(x + .3, y + .7, z + .3), proj(x + .7, y + .7, z + .3), proj(x + .7, y + .7, z + .7),
                               proj(x + .3, y + .7, z + .7)], fill=c)
                    d.polygon([proj(x + .7, y + .7, z + .3), proj(x + .7, y + .7, z + .7), proj(x + .7, y, z + .7),
                               proj(x + .7, y, z + .3)], fill=shade(c, .8))
                    d.polygon([proj(x + .3, y + .7, z + .7), proj(x + .7, y + .7, z + .7), proj(x + .7, y, z + .7),
                               proj(x + .3, y, z + .7)], fill=shade(c, .65))
                    continue
                opaque = lambda v: v and v not in small
                if opaque(up) and opaque(east) and opaque(south):
                    continue
                lit = 1.0 if b in glow else 0.55 + 0.45 * y / cut   # the deeper, the darker
                if not opaque(east):
                    d.polygon([proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1),
                               proj(x + 1, y, z)], fill=shade(c, .78 * lit))
                if not opaque(south):
                    d.polygon([proj(x, y + 1, z + 1), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1),
                               proj(x, y, z + 1)], fill=shade(c, .62 * lit))
                if not opaque(up):
                    top = shade(c, .42) if y == cut - 1 and b not in glow else shade(c, lit)   # the sawn rock
                    d.polygon([proj(x, y + 1, z), proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1),
                               proj(x, y + 1, z + 1)], fill=top)
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def render_section(cell, s=5):
    """Vertical cut through the middle of the cell: the whole height, from bedrock to bedrock."""
    n, h, grid, names = cell["size"], cell["height"], cell["grid"], cell["names"]
    colors = [hx(COLORS.get(nm, "#ff00ff")) for nm in names]
    img = Image.new("RGBA", (n * s, h * s), hx("#0a1a1e"))
    d = ImageDraw.Draw(img)
    z = n // 2
    for x in range(n):
        for y in range(h):
            b = grid[(x * n + z) * h + y]
            if b:
                d.rectangle([x * s, (h - 1 - y) * s, x * s + s - 1, (h - 1 - y) * s + s - 1], fill=colors[b])
            else:   # what is seen at the back of the cavern
                for depth in range(1, 14):
                    if z + depth >= n:
                        break
                    bb = grid[(x * n + z + depth) * h + y]
                    if bb:
                        f = 0.55 - depth * 0.035
                        c = colors[bb] if names[bb] in GLOW else shade(colors[bb], f)
                        d.rectangle([x * s, (h - 1 - y) * s, x * s + s - 1, (h - 1 - y) * s + s - 1], fill=c)
                        break
    return img


def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def preview(cells_data):
    pw, top, mid, bottom = 600, 560, 540, 50
    ph = 40 + top + mid + bottom
    sheet = Image.new("RGBA", (pw * len(cells_data), ph + 50), hx("#0d1117"))
    d = ImageDraw.Draw(sheet)
    d.text((sheet.width // 2, 25), "Underworld - simulación de celdas de 4x4 chunks (64x64 bloques)",
           fill=(190, 235, 240, 255), anchor="mm", font=font(18))
    for i, cell in enumerate(cells_data):
        x0, y0 = i * pw, 50
        d.text((x0 + pw // 2, y0 + 18), f"celda {cell['cx']},{cell['cz']} · {cell['info'][0]}",
               fill=(240, 240, 240, 255), anchor="mm", font=font(16))
        im = render_cell(cell, s=4, cut=58)
        im.thumbnail((pw - 20, top - 10), Image.LANCZOS)
        sheet.alpha_composite(im, (x0 + (pw - im.width) // 2, y0 + 40 + (top - im.height) // 2))
        sec = render_section(cell, s=5)
        sec.thumbnail((pw - 40, mid - 10), Image.LANCZOS)
        sheet.alpha_composite(sec, (x0 + (pw - sec.width) // 2, y0 + 40 + top + (mid - sec.height) // 2))
        extra = " · ".join(cell["info"][1:]) or "sin estructuras"
        d.text((x0 + pw // 2, y0 + ph - 28), f"{extra} · {cell['ops']} operaciones",
               fill=(150, 200, 205, 255), anchor="mm", font=font(13))
    d.text((sheet.width // 2, 50 + 40 + top - 4), "arriba: la caverna sin techo (cortada en y 58) · abajo: corte vertical, de bedrock a bedrock",
           fill=(120, 150, 155, 255), anchor="mm", font=font(12))
    return sheet


# ---------------------------------------------------------------- build
def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    rock, ore = rock_icon(), ore_texture()
    rock_path, ore_path = "textures/items/underworld/hallucinogenic_rock", "textures/blocks/underworld/hallucinogenic_rock_ore"
    for im, path in ((rock, rock_path), (ore, ore_path)):
        full = os.path.join(RP, path + ".png")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        im.save(full)
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": NS, "texture_name": "atlas.items", "texture_data": {
            "underworld_hallucinogenic_rock": {"textures": rock_path}}})
    write(os.path.join(RP, "textures/terrain_texture.json"), {
        "resource_pack_name": NS, "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4,
        "texture_data": {"underworld_hallucinogenic_rock_ore": {"textures": ore_path}}})
    write(os.path.join(RP, "blocks.json"), {"format_version": "1.21.40", ORE: {"sound": "deepslate"}})
    write(os.path.join(RP, "fogs/underworld_fog.json"), fog())
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    write(os.path.join(BP, "items/hallucinogenic_rock.json"), rock_item())
    write(os.path.join(BP, "blocks/hallucinogenic_rock_ore.json"), ore_block())
    write(os.path.join(BP, "loot_tables/blocks/underworld/hallucinogenic_rock_ore.json"), ore_loot())
    write(os.path.join(BP, "features/hallucinogenic_rock_ore_feature.json"), ore_feature())
    write(os.path.join(BP, "feature_rules/overworld_hallucinogenic_rock_ore.json"), ore_feature_rule())
    write(os.path.join(BP, "scripts/main.js"), script())
    shutil.copy(os.path.join(SRC, "gen.js"), os.path.join(BP, "scripts/gen.js"))
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon: the ore, with the rock in front
    icon = Image.new("RGBA", (128, 128), hx("#0a1a1e"))
    icon.alpha_composite(ore.resize((112, 112), Image.NEAREST), (8, 8))
    icon.alpha_composite(rock.resize((80, 80), Image.NEAREST), (44, 44))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "Underworld.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev:
        preview(simulate(PREVIEW_SEED, find_cells(PREVIEW_SEED))).save(os.path.join(ROOT, "docs", "underworld_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
