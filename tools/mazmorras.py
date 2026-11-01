"""Builds "Mazmorras de Toba": a dungeon generator for Minecraft Bedrock.

- Cetro de las Mazmorras (mazmorra:cetro): using it opens a form to choose the kind of
  dungeon, the number of rooms (5-30), the floors (1-6), parkour rooms and a seed.
  The entrance appears where you stand and the dungeon goes down in the direction you look.
- Dungeons of tuff (tuff bricks, polished, chiseled, slabs, stairs and walls) overgrown with
  lush cave plants: moss, pale moss, azalea, lots of cave vines with glow berries, spore
  blossoms, big dripleaves, hanging roots, glow lichen.
- Rooms of every size from 5x5 to 18x18, placed one by one without overlapping, going down
  often; 3x3 corridors and staircases between them.
- Trial spawner rooms (the spawner in the centre) that wake up when a player comes close.
- Parkour rooms: wooden slabs hanging from chains over a pit, a chest on the far side.
- A great hall with a giant tree, gardens, and a treasure room with vaults and a guardian spawner.
- The entrance gets grander with the difficulty (and rarity) of the dungeon: 4 tiers.

The dungeon is built by tools/mazmorras/gen.js, copied into the pack as it is;
tools/mazmorras/simulate.mjs runs it with Node to check it and draw the preview.

    python3 tools/mazmorras.py            # regenerate the packs and the .mcaddon
    python3 tools/mazmorras.py --preview  # also refresh docs/mazmorras_preview.png (needs node)
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mazmorras_clones as clones  # noqa: E402
import mcstructure  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "mazmorras")
ADDON_NAME = "Mazmorras de Toba"
BP = os.path.join(ROOT, "MazmorrasToba_BP")
RP = os.path.join(ROOT, "MazmorrasToba_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 3, 0]
MIN_ENGINE = [1, 26, 0]    # indestructible stairs need several collision boxes per block
SERVER_API = "2.0.0"
SERVER_UI_API = "2.0.0"
UUIDS = dict(bp="012e9dff-6bcd-42ef-8866-3db4d33b8a65", bp_data="0bf4c0f2-b963-480e-a000-38203840ba7e",
             bp_script="391ac560-b6d3-4f0c-9725-12d8ca675736", rp="881065c8-240f-4e5e-8f33-8f855ebaea4d",
             rp_res="24fdaea4-d89a-43b5-869a-9f1d444b7ce7")

NS = "mazmorra"
ITEM = f"{NS}:cetro"

# Everything main.js uses besides the generator.
CONFIG = dict(
    item=ITEM,
    clones=clones.CLONE_MAP,  # vanilla block -> its indestructible copy
    minRooms=5, maxRooms=30, defaultRooms=10,
    opsPerYield=12,       # block operations between pauses while generating
    tile=80,              # pieces are built in groups of about 80x80 blocks, each with one loaded area
    # trial spawners
    detect=6,             # a player this close wakes the spawner up
    leave=20,             # ...and it falls asleep again when nobody is this close
    abandonTicks=600,     # for this long (30 s)
    mobsBase=6, mobsPerPlayer=2, simulBase=3,
    spawnDelay=40,        # ticks between two mobs
    cooldownTicks=36000,  # 30 minutes before a spawner can be used again
    rewards=dict(
        always=[["minecraft:trial_key", 1]], rolls=2,
        random=[["minecraft:emerald", 2, 5], ["minecraft:iron_ingot", 2, 5], ["minecraft:bread", 2, 4],
                ["minecraft:arrow", 4, 10], ["minecraft:golden_carrot", 2, 4], ["minecraft:glow_berries", 3, 8],
                ["minecraft:honey_bottle", 1, 2], ["minecraft:diamond", 1, 1], ["minecraft:experience_bottle", 2, 5]]),
    guardianRewards=dict(
        always=[["minecraft:ominous_trial_key", 1], ["minecraft:trial_key", 1]], rolls=3,
        random=[["minecraft:diamond", 2, 4], ["minecraft:emerald", 6, 12], ["minecraft:golden_apple", 1, 2],
                ["minecraft:experience_bottle", 5, 10], ["minecraft:ender_pearl", 2, 4],
                ["minecraft:enchanted_golden_apple", 1, 1], ["minecraft:wind_charge", 4, 10]]),
)

PREVIEW = dict(seed=20261101, theme="ruinas", rooms=12, floors=4, facing=0)
PREVIEW_ABYSS = dict(seed=20261103, theme="abismo", rooms=10, floors=3, facing=0)
ENTRANCES = ["Pórtico de Toba", "Pórtico Mayor", "Templo Frondoso", "Gran Santuario de Toba"]

LANG = {
    "es": {
        f"item.{ITEM}.name": "Cetro de las Mazmorras",
        "pack.name": ADDON_NAME,
        "pack.description": "Generador de mazmorras de toba y cuevas frondosas.",
    },
    "en": {
        f"item.{ITEM}.name": "Dungeon Scepter",
        "pack.name": ADDON_NAME,
        "pack.description": "Tuff and lush cave dungeon generator.",
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
def scepter_icon():
    """A staff of tuff bricks wrapped in moss, with a glow berry and a small trial spawner flame on top."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = im.load()
    out, dark, tuff, light = hx("#26282a"), hx("#4a4d4c"), hx("#6d716b"), hx("#9a9f97")
    moss, moss2, berry, berry2 = hx("#3f6b22"), hx("#6fa83a"), hx("#f0a52a"), hx("#ffe08a")
    flame, flame2 = hx("#e86a1a"), hx("#ffcf4a")
    # shaft: diagonal from bottom-left to the head
    for i in range(9):
        x, y = 2 + i, 13 - i
        px[x, y] = tuff if i % 3 else light
        px[x + 1, y] = dark
        px[x, y + 1] = out
    px[1, 14] = out
    px[2, 14] = dark
    # moss wrapped around the shaft
    for x, y in [(4, 11), (5, 10), (7, 8), (8, 8), (5, 11)]:
        px[x, y] = moss2 if (x + y) % 2 else moss
    # head: a little cage of tuff with a flame inside
    for x in range(10, 15):
        px[x, 1] = out
        px[x, 6] = out
    for y in range(1, 7):
        px[10, y] = out
        px[14, y] = out
    for x in range(11, 14):
        for y in range(2, 6):
            px[x, y] = dark
    px[12, 3], px[12, 4], px[11, 4], px[13, 4] = flame2, flame, flame, flame
    px[12, 5] = flame
    for x, y in [(11, 1), (13, 6), (14, 3)]:
        px[x, y] = light
    # a glow berry hanging from the head
    px[9, 7], px[9, 8], px[8, 9], px[9, 9] = moss, moss, berry, berry2
    px[8, 10] = berry
    return im


# ---------------------------------------------------------------- behavior pack
def scepter_item():
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": ITEM, "menu_category": {"category": "equipment"}},
        "components": {
            "minecraft:icon": "mazmorra_cetro",
            "minecraft:display_name": {"value": f"item.{ITEM}.name"},
            "minecraft:max_stack_size": 1,
            "minecraft:glint": True,
            "minecraft:hand_equipped": True,
            "minecraft:cooldown": {"category": ITEM, "duration": 2},
            "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
        }}}


def script():
    with open(os.path.join(SRC, "main.js"), encoding="utf-8") as f:
        return f.read().replace("__CONFIG__", json.dumps(CONFIG))


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Generador de mazmorras de toba y cuevas frondosas.",
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SERVER_API},
                         {"module_name": "@minecraft/server-ui", "version": SERVER_UI_API}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Texturas de Mazmorras de Toba.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


# ---------------------------------------------------------------- simulation render
COLORS = {
    "tuff": "#6c6e66", "polished_tuff": "#7a7d74", "tuff_bricks": "#64675f", "chiseled_tuff": "#5c5f58",
    "chiseled_tuff_bricks": "#73766c", "tuff_brick_wall": "#64675f", "polished_tuff_wall": "#7a7d74",
    "tuff_brick_slab": "#686b63", "polished_tuff_slab": "#7e8178", "tuff_brick_stairs": "#64675f",
    "polished_tuff_stairs": "#7a7d74",
    "moss_block": "#5a7d2a", "moss_carpet": "#6a8f33", "pale_moss_block": "#8f998a", "pale_moss_carpet": "#a3ad9d",
    "pale_hanging_moss": "#a3ad9d", "dirt_with_roots": "#8a6342", "clay": "#a0a6b4", "water": "#3f76e4",
    "azalea": "#5f8f2f", "flowering_azalea": "#b77fc0", "azalea_leaves": "#4f7d28", "azalea_leaves_flowered": "#9a6fb0",
    "spore_blossom": "#e07fb0", "hanging_roots": "#9a6c4a", "glow_lichen": "#7fa88a", "fern": "#4f8a30",
    "short_grass": "#6bab3c", "big_dripleaf": "#5fa83a", "cave_vines": "#4a7a2a",
    "cave_vines_head_with_berries": "#f0a52a", "cave_vines_body_with_berries": "#d99a2a", "lantern": "#f2c25a", "chain": "#3d4148", "chest": "#a2702e", "vault": "#4a5a60", "trial_spawner": "#c4652a",
    "ochre_froglight": "#f3e3a0", "verdant_froglight": "#d5f0c0", "pearlescent_froglight": "#f0dcef",
    "oak_log": "#6b5132", "mangrove_roots": "#5d4530",
    "stone": "#7d7d7d", "andesite": "#8a8a8e", "cobblestone": "#6e6e6e", "diorite": "#bdbdbd", "granite": "#9a6b58",
    "glow_frame": "#d8c06a",
    "deepslate": "#4d4d52", "cobbled_deepslate": "#46464a", "polished_deepslate": "#555559",
    "deepslate_bricks": "#4a4a4e", "cracked_deepslate_bricks": "#444448", "deepslate_tiles": "#38383c",
    "cracked_deepslate_tiles": "#333337", "chiseled_deepslate": "#3d3d41", "smooth_basalt": "#4a4a50",
    "crying_obsidian": "#5a1f9a", "obsidian": "#1b1626", "lava": "#e8701a", "soul_lantern": "#5fe0e8",
    "waxed_weathered_copper_grate": "#5f9a7a", "waxed_copper_grate": "#c06a4a", "vine": "#3f7a22",
    "deepslate_brick_wall": "#4a4a4e", "deepslate_tile_wall": "#38383c", "cobbled_deepslate_wall": "#46464a",
    "cobbled_deepslate_slab": "#4a4a4e", "polished_deepslate_slab": "#58585c", "deepslate_brick_slab": "#4c4c50",
    "deepslate_tile_slab": "#3a3a3e", "cobbled_deepslate_stairs": "#46464a", "polished_deepslate_stairs": "#555559",
    "deepslate_brick_stairs": "#4a4a4e", "deepslate_tile_stairs": "#38383c",
    "green_candle": "#4f8a30", "lime_candle": "#8ad13a", "white_candle": "#f0f0f0",
}
PLANTS = {"moss_carpet", "pale_moss_carpet", "pale_hanging_moss", "azalea", "flowering_azalea", "spore_blossom",
          "hanging_roots", "glow_lichen", "fern", "short_grass", "big_dripleaf", "cave_vines", "vine", "chain",
          "cave_vines_head_with_berries", "cave_vines_body_with_berries", "lantern", "green_candle", "lime_candle",
          "white_candle"}


def color_of(bid):
    if bid in COLORS:
        return hx(COLORS[bid])
    if bid.endswith("_slab"):
        return hx("#9c7a4a")  # wooden slabs
    return hx("#ff00ff")


def simulate(p, tier=None, cave=False):
    args = ["node", os.path.join(SRC, "simulate.mjs"), "blocks", str(p["seed"]), p["theme"], str(p["rooms"]),
            str(p["floors"]), str(p["facing"]), str(tier or 0), "cave" if cave else "normal"]
    return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (255,)


def render(blocks, s, keep=lambda x, y, z: True):
    """Isometric view seen from the south-east."""
    solid = {(x, y, z): b for x, y, z, b in blocks if keep(x, y, z)}
    if not solid:
        return Image.new("RGBA", (1, 1))
    xs = [k[0] for k in solid]; ys = [k[1] for k in solid]; zs = [k[2] for k in solid]
    x0, z0, y0 = min(xs), min(zs), min(ys)
    w = (max(xs) - x0 + max(zs) - z0 + 4) * s
    h = int((max(xs) - x0 + max(zs) - z0 + 4) * s / 2 + (max(ys) - y0 + 4) * s * 1.2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = (max(zs) - z0 + 2) * s, (max(ys) - y0 + 2) * s * 1.2

    def proj(x, y, z):
        x, y, z = x - x0, y - y0, z - z0
        return (ox + (x - z) * s, oy + (x + z) * s / 2 - y * s * 1.2)

    for (x, y, z), b in sorted(solid.items(), key=lambda kv: (kv[0][0] + kv[0][2], kv[0][1])):
        c = color_of(b)
        if b in PLANTS:
            d.polygon([proj(x + .3, y + .6, z + .3), proj(x + .7, y + .6, z + .3), proj(x + .7, y + .6, z + .7),
                       proj(x + .3, y + .6, z + .7)], fill=c)
            continue
        up = solid.get((x, y + 1, z))
        if up and up not in PLANTS and solid.get((x + 1, y, z)) and solid.get((x, y, z + 1)):
            continue
        top = [proj(x, y + 1, z), proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x, y + 1, z + 1)]
        east = [proj(x + 1, y + 1, z), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1), proj(x + 1, y, z)]
        south = [proj(x, y + 1, z + 1), proj(x + 1, y + 1, z + 1), proj(x + 1, y, z + 1), proj(x, y, z + 1)]
        d.polygon(east, fill=shade(c, 0.78))
        d.polygon(south, fill=shade(c, 0.62))
        d.polygon(top, fill=c)
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def in_box(r, x, z):
    b = r["box"]
    return b[0] <= x <= b[3] and b[2] <= z <= b[5]


def cutaway(sim):
    """Hide the ceilings: in every column keep only what is below the walking level + 2."""
    lowest = {}
    for x, y, z, _ in sim["blocks"]:
        k = (x, z)
        lowest[k] = min(lowest.get(k, y), y)
    cuts = {}
    for (x, z), low in lowest.items():
        cut = low + 3
        for r in sim["rooms"]:
            if in_box(r, x, z):
                cut = r["Y"] + (13 if r["type"] == "arbol" else 2)
                break
        cuts[(x, z)] = cut
    return lambda x, y, z: y <= cuts[(x, z)] and y < sim["y0"] + 8


def close_up(sim, r, s, section=False):
    """One room without its ceiling and without the two walls in front of the camera; or, for the caves,
    cut in half through the middle so you see the inside."""
    b = r["box"]
    if section:
        return render(sim["blocks"], s, lambda x, y, z: b[0] <= x <= b[3] and b[2] <= z <= r["z"] and b[1] <= y <= b[4])
    return render(sim["blocks"], s, lambda x, y, z: b[0] <= x < b[3] and b[2] <= z < b[5] and b[1] <= y < b[4])


ENTRANCE_BOX = lambda x, y, z: -21 <= x <= 9 and -15 <= z <= 15 and y >= 76


def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


ABYSS_BOX = lambda x, y, z: -20 <= x <= 11 and -17 <= z <= 17 and y >= 75


def preview(sim, entrances, title, closeups, ent_titles, ent_box=ENTRANCE_BOX):
    W, H = 1700, 1320
    sheet = Image.new("RGBA", (W, H), hx("#0d1117"))
    d = ImageDraw.Draw(sheet)
    white, soft = (240, 240, 240, 255), (170, 200, 160, 255)

    def paste(im, cx, top, w, h):
        im = im.copy()
        im.thumbnail((w, h), Image.LANCZOS)
        sheet.alpha_composite(im, (cx - im.width // 2, top + (h - im.height) // 2))

    counts = ", ".join(f"{n} {t}" for t, n in sim["plan"]["counts"].items())
    d.text((W // 2, 24), f"{title} - {len(sim['rooms']) - 1} salas en {sim['plan']['floors']} pisos ({counts})",
           fill=(220, 235, 210, 255), anchor="mm", font=font(20))
    paste(render(sim["blocks"], 8, cutaway(sim)), 590, 50, 1160, 800)
    for k, (typ, name) in enumerate(closeups):
        rooms = [r for r in sim["rooms"] if r["type"] == typ]
        if not rooms:
            continue
        d.text((1440, 64 + k * 400), f"{name} ({rooms[0]['box'][3] - rooms[0]['box'][0] - 1} x "
               f"{rooms[0]['box'][5] - rooms[0]['box'][2] - 1})", fill=white, anchor="mm", font=font(16))
        paste(close_up(sim, rooms[0], 12, section=sim["plan"]["theme"] == "abismo"), 1440, 84 + k * 400, 480, 360)
    d.text((W // 2, 880), "Entradas según la dificultad (y la rareza) de la mazmorra", fill=(220, 235, 210, 255),
           anchor="mm", font=font(18))
    n = len(entrances)
    for k, ent in enumerate(entrances):
        cx = W * (2 * k + 1) // (2 * n)
        d.text((cx, 912), ent_titles[k], fill=white, anchor="mm", font=font(15))
        paste(render(ent["blocks"], 8, ent_box), cx, 930, W // n - 20, 360)
    d.text((W // 2, H - 14), "Vistas generadas con el mismo generador (tools/mazmorras/simulate.mjs)", fill=soft,
           anchor="mm", font=font(13))
    return sheet


def cave_preview():
    """The cave entrance: the main hall of each style cut in half, without any terrain around."""
    W, H = 1700, 760
    sheet = Image.new("RGBA", (W, H), hx("#0d1117"))
    d = ImageDraw.Draw(sheet)
    d.text((W // 2, 24), "Entrada de cueva: la gran sala natural (cortada por la mitad), del borde de piedra a la mazmorra",
           fill=(220, 235, 210, 255), anchor="mm", font=font(18))
    for k, (p, title) in enumerate([(PREVIEW, "Toba (cueva frondosa)"), (PREVIEW_ABYSS, "Abisal")]):
        sim = simulate(p, cave=True)
        hall = sim["rooms"][0]
        b = hall["box"]
        im = render(sim["blocks"], 10, lambda x, y, z: b[0] - 2 <= x <= b[3] + 2 and b[2] - 2 <= z <= hall["z"]
                    and b[1] - 2 <= y <= b[4] + 2)
        im.thumbnail((820, 640), Image.LANCZOS)
        cx = W * (2 * k + 1) // 4
        d.text((cx, 60), title, fill=(240, 240, 240, 255), anchor="mm", font=font(16))
        sheet.alpha_composite(im, (cx - im.width // 2, 90 + (640 - im.height) // 2))
    return sheet


# ---------------------------------------------------------------- build
def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    icon16 = scepter_icon()
    path = "textures/items/mazmorra/cetro"
    full = os.path.join(RP, path + ".png")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    icon16.save(full)
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "mazmorra", "texture_name": "atlas.items", "texture_data": {
            "mazmorra_cetro": {"textures": path}}})
    # the indestructible copies of every block of the dungeons
    ids = json.loads(subprocess.run(["node", os.path.join(SRC, "simulate.mjs"), "ids"], check=True, capture_output=True,
                                    text=True).stdout)
    missing, ungrouped = clones.check(ids)
    if missing or ungrouped:
        sys.exit(f"Bloques sin copia indestructible: {missing}; copias fuera del inventario: {ungrouped}")
    clones.write(BP, RP, LANG["es"], LANG["en"], write)
    # the glow item frame with the totem of the Torre del Tótem, one per direction it can face
    for facing in mcstructure.FACING:
        path = os.path.join(BP, "structures", NS, f"totem_{facing}.mcstructure")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(mcstructure.item_frame(facing, "minecraft:totem_of_undying"))
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    write(os.path.join(BP, "items/cetro.json"), scepter_item())
    write(os.path.join(BP, "scripts/main.js"), script())
    shutil.copy(os.path.join(SRC, "gen.js"), os.path.join(BP, "scripts/gen.js"))
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon: the entrance, or the scepter if node is not installed
    icon = Image.new("RGBA", (128, 128), hx("#0d1117"))
    sim = None
    try:
        sim = simulate(PREVIEW)
        ent = render(simulate(PREVIEW, 4)["blocks"], 3, ENTRANCE_BOX)
        ent.thumbnail((120, 112), Image.LANCZOS)
        icon.alpha_composite(ent, ((128 - ent.width) // 2, (128 - ent.height) // 2 - 4))
        icon.alpha_composite(icon16.resize((40, 40), Image.NEAREST), (86, 86))
    except (OSError, subprocess.CalledProcessError) as e:
        print("No se pudo simular con node:", e)
        icon.alpha_composite(icon16.resize((112, 112), Image.NEAREST), (8, 8))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "MazmorrasToba.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev and sim:
        preview(sim, [simulate(PREVIEW, t) for t in (1, 2, 3, 4)], "Mazmorras de Toba",
                [("torre", "Torre del Tótem"), ("arbol", "Sala del gran árbol")],
                [f"{k + 1}. {e}" for k, e in enumerate(ENTRANCES)]).save(os.path.join(ROOT, "docs", "mazmorras_preview.png"))
        asim = simulate(PREVIEW_ABYSS)
        preview(asim, [simulate(PREVIEW_ABYSS, t) for t in (1, 4)], "Mazmorras Abisales",
                [("sima", "Sima con pasarelas"), ("parkour", "Parkour de lava")],
                ["La Boca del Abismo (dificultad 1)", "La Boca del Abismo (dificultad 4)"], ABYSS_BOX).save(
            os.path.join(ROOT, "docs", "mazmorras_abismo_preview.png"))
        cave_preview().save(os.path.join(ROOT, "docs", "mazmorras_cueva_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
