"""Builds "The LITIUS Blind" add-on: a new dimension of floating islands.

- The dimension (litius:the_litius_blind) is registered by the script with the
  Custom Dimension API (Beta APIs experiment). It is a void dimension that the
  script fills with islands, one cell of 4x4 chunks at a time, around the players.
- Upper islands (y 80 and up): grass or moss on top, stone (rarely ores) below;
  oases, rivers, ponds, majestic oaks and birches.
- Lower islands (y 20..50): only deepslate blocks, with lava lakes.
- Dungeons without mobs, with an entrance into the island (more on the lower islands).
- Llave de Raices (litius:llave_de_raices): takes you there and back. It cannot be
  crafted nor found for now: only /give.
- No mobs can appear in the dimension for now.

The islands are built by tools/litius_blind/gen.js, which is copied into the pack
as it is; tools/litius_blind/simulate.mjs runs it with Node to draw the preview.

    python3 tools/litius_blind.py            # regenerate the packs and the .mcaddon
    python3 tools/litius_blind.py --preview  # also refresh docs/litius_blind_preview.png (needs node)
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "litius_blind")
ADDON_NAME = "The LITIUS Blind"
BP = os.path.join(ROOT, "LitiusBlind_BP")
RP = os.path.join(ROOT, "LitiusBlind_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "beta"         # registerCustomDimension is only in the beta module
MIN_ENGINE = [1, 26, 20]    # the Custom Dimension API arrived in 26.20
UUIDS = dict(bp="5e2176e5-4c4f-40d1-b07b-b26952caf7c3", bp_data="5721f967-0fcd-42ab-a3bb-7054819d05df",
             bp_script="c8c5953b-4aa4-443d-9a78-6c5c40728443", rp="2ffd24a0-ffdc-4bb3-b637-925e2d296f94",
             rp_res="e4bb1993-5b6e-45b8-b585-4240520d84ed")

NS = "litius"
DIMENSION = f"{NS}:the_litius_blind"
KEY = f"{NS}:llave_de_raices"

# Everything main.js uses besides the generator.
CONFIG = dict(
    dimension=DIMENSION,
    key=KEY,
    radius=2,          # cells (of 4x4 chunks) generated around each player: 5x5 cells
    opsPerStep=48,     # block operations between pauses while generating
)

PREVIEW_SEED = 20261027
PREVIEW_CELLS = [(0, 0), (1, 0), (0, -1), (-1, 1)]

LANG = {
    "es": {
        f"item.{KEY}.name": "Llave de Raíces",
        "pack.name": ADDON_NAME,
        "pack.description": "Una nueva dimensión de islas flotantes.",
    },
    "en": {
        f"item.{KEY}.name": "Root Key",
        "pack.name": ADDON_NAME,
        "pack.description": "A new dimension of floating islands.",
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
def key_icon():
    """A key made of twisted roots, with moss and an amber seed in the bow."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    out, dark, wood, light = hx("#2a1a0e"), hx("#5a3a1e"), hx("#8a5a2e"), hx("#b98a52")
    moss, moss2, amber, amber2 = hx("#4f8a2a"), hx("#7fbf3f"), hx("#f0a020"), hx("#ffe28a")
    px = im.load()
    # bow: a ring of roots
    ring = [(2, 1), (3, 1), (4, 1), (5, 1), (1, 2), (6, 2), (1, 3), (6, 3), (1, 4), (6, 4), (1, 5), (6, 5),
            (2, 6), (3, 6), (4, 6), (5, 6)]
    inner = [(2, 2), (3, 2), (4, 2), (5, 2), (2, 3), (5, 3), (2, 4), (5, 4), (2, 5), (3, 5), (4, 5), (5, 5)]
    for x, y in ring:
        px[x, y] = out
    for i, (x, y) in enumerate(inner):
        px[x, y] = light if (x + y) % 3 == 0 else wood
    for x, y in [(3, 3), (4, 3), (3, 4), (4, 4)]:
        px[x, y] = amber
    px[3, 3] = amber2
    for x, y in [(2, 2), (5, 5), (4, 2)]:
        px[x, y] = moss2
    # shaft: diagonal twisted root
    for i in range(7):
        x, y = 6 + i, 6 + i
        px[x, y] = wood if i % 2 else light
        px[x + 1, y] = dark
        px[x, y + 1] = out if i < 6 else dark
    # teeth: little roots growing from the shaft
    for x, y, c in [(10, 12, dark), (9, 13, wood), (8, 14, out), (12, 10, dark), (13, 9, wood), (14, 8, out),
                    (11, 13, out), (13, 11, out)]:
        px[x, y] = c
    for x, y in [(7, 8), (11, 10), (9, 9)]:
        px[x, y] = moss
    px[14, 14] = out
    px[13, 14] = dark
    return im


# ---------------------------------------------------------------- behavior pack
def key_item():
    return {"format_version": "1.21.90", "minecraft:item": {
        # "none": not in the creative inventory nor in any recipe; only /give
        "description": {"identifier": KEY, "menu_category": {"category": "none"}},
        "components": {
            "minecraft:icon": "litius_llave_de_raices",
            "minecraft:display_name": {"value": f"item.{KEY}.name"},
            "minecraft:max_stack_size": 1,
            "minecraft:glint": True,
            "minecraft:cooldown": {"category": KEY, "duration": 3},
            "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
        }}}


def script():
    with open(os.path.join(SRC, "main.js"), encoding="utf-8") as f:
        return f.read().replace("__CONFIG__", json.dumps(CONFIG))


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Una nueva dimensión de islas flotantes.",
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
        "header": {"name": ADDON_NAME, "description": "Texturas de The LITIUS Blind.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


# ---------------------------------------------------------------- simulation render
COLORS = {
    "grass_block": "#5f9f35", "dirt": "#7a5534", "stone": "#7d7d7d", "andesite": "#8a8a8e",
    "cobblestone": "#6e6e6e", "mossy_cobblestone": "#5d7350", "moss_block": "#5a7d2a", "moss_carpet": "#6a8f33",
    "dirt_with_roots": "#8a6342", "sand": "#dbcf9a", "sandstone": "#d2c48a", "gravel": "#857f7c",
    "clay": "#a0a6b4", "water": "#3f76e4", "lava": "#e8701a", "waterlily": "#2f7a2a",
    "stone_bricks": "#7a7a7a", "mossy_stone_bricks": "#66765a", "cracked_stone_bricks": "#727272",
    "chiseled_stone_bricks": "#858585", "mossy_stone_brick_stairs": "#66765a",
    "deepslate": "#4d4d52", "cobbled_deepslate": "#46464a", "polished_deepslate": "#555559",
    "deepslate_bricks": "#4a4a4e", "cracked_deepslate_bricks": "#444448", "deepslate_tiles": "#38383c",
    "cracked_deepslate_tiles": "#333337", "chiseled_deepslate": "#3d3d41", "deepslate_brick_stairs": "#4a4a4e",
    "oak_log": "#6b5132", "birch_log": "#d8d2c0", "oak_leaves": "#3f8a26", "birch_leaves": "#6fa344",
    "short_grass": "#6bab3c", "tall_grass": "#6bab3c", "fern": "#4f8a30", "azalea": "#5f8f2f",
    "flowering_azalea": "#c07fc0", "hanging_roots": "#9a6c4a", "mangrove_roots": "#5d4530",
    "lantern": "#f2c25a", "soul_lantern": "#5fe0e8", "chest": "#a2702e", "web": "#e8e8e8",
    "poppy": "#d23a2a", "dandelion": "#f2d23a", "cornflower": "#4a6ad8", "oxeye_daisy": "#f0f0e0",
    "azure_bluet": "#d8e0f0", "allium": "#b060d0", "lily_of_the_valley": "#f4f4f4",
}
PLANTS = {"short_grass", "tall_grass", "fern", "moss_carpet", "waterlily", "web", "hanging_roots", "poppy",
          "dandelion", "cornflower", "oxeye_daisy", "azure_bluet", "allium", "lily_of_the_valley"}


def color_of(bid):
    if bid in COLORS:
        return hx(COLORS[bid])
    if bid.endswith("_ore"):
        return hx("#5a5a60") if bid.startswith("deepslate") else hx("#8a8a8a")
    return hx("#ff00ff")


def simulate(seed, cells):
    args = ["node", os.path.join(SRC, "simulate.mjs"), "blocks", str(seed)] + [f"{x},{z}" for x, z in cells]
    return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (255,)


def render_cell(blocks, s=4, y_min=18, y_max=150):
    """Isometric view of one 4x4-chunk cell (64x64 blocks) seen from the south-east."""
    solid = {(x, y, z): b for x, y, z, b in blocks}
    width = 64 * 2 * s + 4 * s
    height = 64 * s + (y_max - y_min) * s * 2 + 4 * s
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = 64 * s + 2 * s, (y_max - y_min) * s * 2

    def proj(x, y, z):
        return (ox + (x - z) * s, oy + (x + z) * s / 2 - (y - y_min) * s * 2)

    order = sorted(solid.items(), key=lambda kv: (kv[0][0] + kv[0][2], kv[0][1]))
    for (x, y, z), b in order:
        if y < y_min or y > y_max:
            continue
        c = color_of(b)
        plant = b in PLANTS
        up = solid.get((x, y + 1, z))
        if not plant and up and up not in PLANTS and solid.get((x + 1, y, z)) and solid.get((x, y, z + 1)):
            continue
        top = [proj(x, y + 1, z), proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)]
        east = [proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1), proj(x + 1, y, z)]
        south = [proj(x, y + 1, z + 1), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1), proj(x, y, z + 1)]
        if plant:
            top = [proj(x + .3, y + .6, z + .3), proj(x + .7, y + .6, z + .3), proj(x + .7, y + .6, z + .7), proj(x + .3, y + .6, z + .7)]
            d.polygon(top, fill=c)
            continue
        d.polygon(east, fill=shade(c, 0.78))
        d.polygon(south, fill=shade(c, 0.62))
        d.polygon(top, fill=c)
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def preview(cells_data):
    panels = []
    for cell in cells_data:
        im = render_cell(cell["blocks"], s=4)
        im.thumbnail((620, 760), Image.LANCZOS)
        panels.append((cell, im))
    cols = 2
    pw, ph = 640, 820
    sheet = Image.new("RGBA", (pw * cols, ph * ((len(panels) + 1) // cols) + 50), hx("#0d1117"))
    d = ImageDraw.Draw(sheet)
    d.text((pw * cols // 2, 25), "The LITIUS Blind - simulación de celdas de 4x4 chunks (64x64 bloques)",
           fill=(220, 235, 210, 255), anchor="mm", font=font(18))
    for i, (cell, im) in enumerate(panels):
        x0, y0 = (i % cols) * pw, 50 + (i // cols) * ph
        sheet.alpha_composite(im, (x0 + (pw - im.width) // 2, y0 + 40 + (ph - 80 - im.height) // 2))
        title = f"celda {cell['cx']},{cell['cz']}"
        d.text((x0 + pw // 2, y0 + 16), title, fill=(240, 240, 240, 255), anchor="mm", font=font(16))
        d.text((x0 + pw // 2, y0 + ph - 24), " · ".join(cell["info"]), fill=(170, 200, 160, 255), anchor="mm",
               font=font(13))
    return sheet


# ---------------------------------------------------------------- build
def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    icon16 = key_icon()
    path = "textures/items/litius/llave_de_raices"
    full = os.path.join(RP, path + ".png")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    icon16.save(full)
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "litius", "texture_name": "atlas.items", "texture_data": {
            "litius_llave_de_raices": {"textures": path}}})
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    write(os.path.join(BP, "items/llave_de_raices.json"), key_item())
    write(os.path.join(BP, "scripts/main.js"), script())
    shutil.copy(os.path.join(SRC, "gen.js"), os.path.join(BP, "scripts/gen.js"))
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon: the main island, or the key if node is not installed
    icon = Image.new("RGBA", (128, 128), hx("#0d1117"))
    try:
        cells = simulate(PREVIEW_SEED, PREVIEW_CELLS if prev else PREVIEW_CELLS[:1])
        main_island = render_cell(cells[0]["blocks"], s=2, y_min=78, y_max=140)
        main_island.thumbnail((124, 124), Image.LANCZOS)
        icon.alpha_composite(main_island, ((128 - main_island.width) // 2, (128 - main_island.height) // 2))
        icon.alpha_composite(icon16.resize((40, 40), Image.NEAREST), (86, 86))
    except (OSError, subprocess.CalledProcessError) as e:
        print("No se pudo simular con node:", e)
        cells = None
        icon.alpha_composite(icon16.resize((112, 112), Image.NEAREST), (8, 8))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "LitiusBlind.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev and cells:
        preview(cells).save(os.path.join(ROOT, "docs", "litius_blind_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
