"""Builds "Natura PvP": an automated PvP map for Minecraft Bedrock.

- An empty (void) world, `dist/NaturaPvP.mcworld`, with the packs already in it.
  The behaviour pack's script builds the whole map the first time the world opens:
  * Lobby: a floating island with a plaza, a fountain and three pads (one per mode).
  * Emparejamiento: two 64x64 arenas with colossal mossy walls (1 vs 1, queue,
    full enchanted diamond kit, 9 s countdown).
  * Caza: a 365x365 forest with lakes, rocks and ruins; up to 5 players, one hunted
    (iron kit that improves with every hunter) against the rest (diamond kit).
    Blocks can be broken: the map regenerates after every hunt. An epic song
    plays when only the hunted and one hunter are left.
  * Campal: a 126x126 arena that is always open, with respawn and kill table.
- An admin panel (tag "admin") to change modes, times, kits, world and more.
- `dist/NaturaPvP.mcaddon` with the same packs, for an existing world.

The world is prebuilt: tools/natura_pvp/gen/ describes every area (pure JS, the
same code the script uses), export.mjs dumps it and world.py writes the chunks
into the world database. The rest of the scripts are in tools/natura_pvp/.

    python3 tools/natura_pvp.py            # packs, .mcworld and .mcaddon
    python3 tools/natura_pvp.py --preview  # also docs/natura_pvp_preview.png (needs node)
    python3 tools/natura_pvp.py --music    # also renders the song again (needs ffmpeg)
"""
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "natura_pvp")
sys.path.insert(0, SRC)

NAME = "Natura PvP"
BP = os.path.join(ROOT, "NaturaPvP_BP")
RP = os.path.join(ROOT, "NaturaPvP_RP")
DIST = os.path.join(ROOT, "dist")
DOCS = os.path.join(ROOT, "docs")

VERSION = [1, 2, 0]
MIN_ENGINE = [1, 21, 90]  # custom commands in @minecraft/server 2.0.0
SERVER_API = "2.0.0"
UI_API = "2.0.0"
UUIDS = dict(bp="0b6f3c52-8e1d-4c7a-9f4e-2a6d1e7b5c31", bp_data="7d2e9a14-3b5f-4e8c-a1d6-9c4b2f8e0a57",
             bp_script="e5a1c7d3-9f2b-4a6e-8d4c-1b7f3e9a2c65", rp="3c8f1e6a-2d4b-4f9e-b7a3-5e1c9d2f8b46",
             rp_res="9a4d2b7e-6c1f-4e3a-8b5d-7f2e1c9a4d83")

BUILD_VERSION = "1.2.0"  # change it to rebuild the map in existing worlds
SONGS_DIR = os.path.join(SRC, "canciones")
AUDIO = (".ogg", ".mp3", ".wav", ".m4a", ".flac", ".opus")

LANG = {
    "es": {
        "pack.name": NAME,
        "pack.description": "Mapa PvP automatizado: Emparejamiento, Caza y Campal.",
        "entity.natura:text.name": "Texto",
    },
    "en": {
        "pack.name": NAME,
        "pack.description": "Automated PvP map: Duels, Hunt and Free-for-all.",
        "entity.natura:text.name": "Text",
    },
}


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")


def lang(d):
    return "".join(f"{k}={v}\n" for k, v in d.items())


# ------------------------------------------------------------ packs
def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUIDS["bp"],
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": UUIDS["rp"], "version": VERSION},
            {"module_name": "@minecraft/server", "version": SERVER_API},
            {"module_name": "@minecraft/server-ui", "version": UI_API},
        ],
    }
    rp = {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUIDS["rp"],
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def text_entity():
    """An invisible entity that only shows its name: the floating texts of the lobby."""
    return {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {"identifier": "natura:text", "is_spawnable": False, "is_summonable": True},
            "components": {
                "minecraft:type_family": {"family": ["natura_text", "inanimate"]},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                "minecraft:collision_box": {"width": 0.01, "height": 0.01},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
                "minecraft:knockback_resistance": {"value": 1},
                "minecraft:fire_immune": {},
                "minecraft:persistent": {},
            },
        },
    }


def resource_files():
    write(os.path.join(RP, "entity/text.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": "natura:text",
            "materials": {"default": "entity_alphatest"},
            "textures": {"default": "textures/entity/natura/blank"},
            "geometry": {"default": "geometry.natura.blank"},
            "render_controllers": ["controller.render.default"],
        }},
    })
    write(os.path.join(RP, "models/entity/natura_blank.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.natura.blank", "texture_width": 16, "texture_height": 16},
            "bones": [{"name": "root", "pivot": [0, 0, 0]}],
        }],
    })
    blank = os.path.join(RP, "textures/entity/natura/blank.png")
    os.makedirs(os.path.dirname(blank), exist_ok=True)
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(blank)


def slug(text):
    out = "".join(ch if ch.isalnum() else "_" for ch in text.lower())
    return "_".join(p for p in out.split("_") if p)[:40] or "cancion"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def songs(force_music):
    """The songs: tools/natura_pvp/canciones/canciones.json (in that order).

    Any other audio file put in that folder is converted to .ogg (same loudness,
    stereo) and added at the end, named after the file. "Duelo Final" is
    synthesised by music.py."""
    import music
    listing = os.path.join(SONGS_DIR, "canciones.json")
    with open(listing, encoding="utf-8") as fh:
        entries = json.load(fh)
    epic = os.path.join(SONGS_DIR, "duelo_final.ogg")
    if force_music or not os.path.exists(epic):
        music.write_ogg(epic)
    known = {e["file"] for e in entries}
    for name in sorted(os.listdir(SONGS_DIR)):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in AUDIO or name in known:
            continue
        target = slug(stem) + ".ogg"
        if target in known:
            continue
        src = os.path.join(SONGS_DIR, name)
        tmp = os.path.join(SONGS_DIR, "_tmp_" + target)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-ar", "44100", "-ac", "2", "-c:a", "libvorbis", "-q:a", "2", tmp], check=True)
        if name != target:
            os.remove(src)
        os.replace(tmp, os.path.join(SONGS_DIR, target))
        entries.append({"file": target, "name": stem.replace("_", " ").strip()})
        known.add(target)
        print("Canción añadida:", target)
    defs, tracks = {}, []
    for e in entries:
        path = os.path.join(SONGS_DIR, e["file"])
        if "seconds" not in e or force_music:
            e["seconds"] = round(duration(path), 2)
        sid = "natura.song." + slug(os.path.splitext(e["file"])[0])
        rel = "sounds/natura/songs/" + os.path.splitext(e["file"])[0]
        dst = os.path.join(RP, rel + ".ogg")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(path, dst)
        # stereo + a huge min_distance: the song sounds the same anywhere
        defs[sid] = {"category": "record", "min_distance": 4096.0, "max_distance": 8192.0,
                     "sounds": [{"name": rel, "stream": True, "volume": 1.0, "load_on_low_memory": True}]}
        tracks.append({"id": sid, "name": e["name"], "ticks": int(e["seconds"] * 20) + 10})
    with open(listing, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    write(os.path.join(RP, "sounds/sound_definitions.json"), {"format_version": "1.14.0", "sound_definitions": defs})
    return tracks


def scripts(tracks):
    cfg = {"buildVersion": BUILD_VERSION, "tracks": tracks}
    with open(os.path.join(SRC, "main.js"), encoding="utf-8") as f:
        main = f.read().replace("__CONFIG__", json.dumps(cfg))
    write(os.path.join(BP, "scripts/main.js"), main)
    for name in ("builder.js", "kits.js"):
        shutil.copy(os.path.join(SRC, name), os.path.join(BP, "scripts", name))
    shutil.copytree(os.path.join(SRC, "gen"), os.path.join(BP, "scripts", "gen"))


# ------------------------------------------------------------ level.dat (little-endian NBT)
class Tag:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value


def b(v): return Tag(1, v)
def i(v): return Tag(3, v)
def l(v): return Tag(4, v)
def f(v): return Tag(5, v)
def s(v): return Tag(8, v)
def ilist(v): return Tag(9, [Tag(3, x) for x in v])
def c(v): return Tag(10, v)


def nbt_payload(tag):
    k, v = tag.kind, tag.value
    if k == 1:
        return struct.pack("<b", v)
    if k == 3:
        return struct.pack("<i", v)
    if k == 4:
        return struct.pack("<q", v)
    if k == 5:
        return struct.pack("<f", v)
    if k == 8:
        raw = v.encode("utf-8")
        return struct.pack("<H", len(raw)) + raw
    if k == 9:
        kind = v[0].kind if v else 1
        return struct.pack("<bi", kind, len(v)) + b"".join(nbt_payload(x) for x in v)
    if k == 10:
        out = b""
        for name, child in v.items():
            raw = name.encode("utf-8")
            out += struct.pack("<bH", child.kind, len(raw)) + raw + nbt_payload(child)
        return out + b"\x00"
    raise ValueError(k)


VOID_LAYERS = json.dumps({"biome_id": 1, "block_layers": [{"block_name": "minecraft:air", "count": 1}],
                          "encoding_version": 6, "structure_options": None,
                          "world_version": "version.post_1_18"}, separators=(",", ":"))


def level_dat(packs_required=False):
    game = [1, 21, 100, 0, 0]  # the blocks of the prebuilt chunks are from 1.21.100
    rules = dict(
        commandblockoutput=b(0), commandblocksenabled=b(1), dodaylightcycle=b(0), doentitydrops=b(1),
        dofiretick=b(0), doimmediaterespawn=b(1), doinsomnia=b(0), domobloot=b(1), domobspawning=b(0),
        dotiledrops=b(1), doweathercycle=b(0), drowningdamage=b(1), falldamage=b(1), firedamage=b(1),
        freezedamage=b(1), keepinventory=b(1), mobgriefing=b(0), naturalregeneration=b(1), pvp=b(1),
        respawnblocksexplode=b(1), sendcommandfeedback=b(1), showbordereffect=b(1), showcoordinates=b(0),
        showdaysplayed=b(0), showdeathmessages=b(1), showtags=b(1), tntexplodes=b(0),
        projectilescanbreakblocks=b(0), recipesunlock=b(0), showrecipemessages=b(0),
        functioncommandlimit=i(10000), maxcommandchainlength=i(65535), spawnradius=i(0),
        playerssleepingpercentage=i(100), randomtickspeed=i(1),
    )
    root = dict(
        BiomeOverride=s(""), CenterMapsToOrigin=b(0), ConfirmedPlatformLockedContent=b(0), Difficulty=i(2),
        FlatWorldLayers=s(VOID_LAYERS), ForceGameType=b(0), GameType=i(2), Generator=i(2),
        InventoryVersion=s("1.21.100"), LANBroadcast=b(1), LANBroadcastIntent=b(1), LastPlayed=l(int(time.time())),
        LevelName=s(NAME), LimitedWorldDepth=i(16), LimitedWorldOriginX=i(0), LimitedWorldOriginY=i(32767),
        LimitedWorldOriginZ=i(0), LimitedWorldWidth=i(16), MinimumCompatibleClientVersion=ilist(game),
        MultiplayerGame=b(1), MultiplayerGameIntent=b(1), NetherScale=i(8), NetworkVersion=i(827), Platform=i(2),
        PlatformBroadcastIntent=i(3), RandomSeed=l(73492026), SpawnV1Villagers=b(0), SpawnX=i(0), SpawnY=i(101),
        SpawnZ=i(21), StorageVersion=i(10), Time=l(6000), WorldVersion=i(1), XBLBroadcastIntent=i(3),
        baseGameVersion=s("*"), bonusChestEnabled=b(0), bonusChestSpawned=b(0), commandsEnabled=b(1),
        currentTick=l(0), daylightCycle=i(0), editorWorldType=i(0), eduOffer=i(0), educationFeaturesEnabled=b(0),
        experiments=c(dict(experiments_ever_used=b(0), saved_with_toggled_experiments=b(0))),
        hasBeenLoadedInCreative=b(1), hasLockedBehaviorPack=b(0), hasLockedResourcePack=b(0), immutableWorld=b(0),
        isCreatedInEditor=b(0), isExportedFromEditor=b(0), isFromLockedTemplate=b(0), isFromWorldTemplate=b(0),
        isHardcore=b(0), isRandomSeedAllowed=b(0), isSingleUseWorld=b(0), isWorldTemplateOptionLocked=b(0),
        lastOpenedWithVersion=ilist(game), lightningLevel=f(0.0), lightningTime=i(100000), limitedWorldDepth=i(16),
        limitedWorldWidth=i(16), permissionsLevel=i(0), playerPermissionsLevel=i(1), prid=s(""), rainLevel=f(0.0),
        rainTime=i(100000), requiresCopiedPackRemovalCheck=b(0), serverChunkTickRange=i(4), spawnMobs=b(0),
        startWithMapEnabled=b(0), texturePacksRequired=b(1 if packs_required else 0), useMsaGamertagsOnly=b(0), worldStartCount=l(0),
        **rules,
    )
    payload = struct.pack("<bH", 10, 0) + nbt_payload(c(root))
    return struct.pack("<ii", 10, len(payload)) + payload


def read_level_dat(data):
    """Reads it back (a check that the file is well formed)."""
    version, length = struct.unpack_from("<ii", data, 0)
    assert length == len(data) - 8, "longitud incorrecta"
    pos = 8

    def read(kind):
        nonlocal pos
        if kind == 1:
            v = struct.unpack_from("<b", data, pos)[0]; pos += 1; return v
        if kind == 3:
            v = struct.unpack_from("<i", data, pos)[0]; pos += 4; return v
        if kind == 4:
            v = struct.unpack_from("<q", data, pos)[0]; pos += 8; return v
        if kind == 5:
            v = struct.unpack_from("<f", data, pos)[0]; pos += 4; return v
        if kind == 8:
            n = struct.unpack_from("<H", data, pos)[0]; pos += 2
            v = data[pos:pos + n].decode("utf-8"); pos += n; return v
        if kind == 9:
            k, n = struct.unpack_from("<bi", data, pos); pos += 5
            return [read(k) for _ in range(n)]
        if kind == 10:
            out = {}
            while True:
                k = data[pos]; pos += 1
                if k == 0:
                    return out
                n = struct.unpack_from("<H", data, pos)[0]; pos += 2
                name = data[pos:pos + n].decode("utf-8"); pos += n
                out[name] = read(k)
        raise ValueError(kind)

    assert data[pos] == 10
    pos += 3
    root = read(10)
    assert pos == len(data)
    return version, root


# ------------------------------------------------------------ preview
COLORS = {
    "grass": "#5f9e3a", "dirt": "#7a5636", "coarse": "#80603f", "podzol": "#6b4a24", "moss": "#5a7d2c",
    "stone": "#808080", "andesite": "#8a8a86", "pandesite": "#9a9c9a", "cobble": "#7a7a7a", "mcobble": "#6a7a5a",
    "sbrick": "#7b7b7b", "msbrick": "#6f7a5d", "cbrick": "#707070", "chbrick": "#858585", "bedrock": "#333333",
    "barrier": "#000000", "water": "#3a66d6", "sand": "#dccf8e", "gravel": "#8d8580", "clay": "#9ea3b0",
    "path": "#a08d4a", "oak": "#6b5130", "birch": "#d8d3c2", "spruce": "#4b3620", "oakL": "#3f7d22",
    "birchL": "#6a9a3d", "spruceL": "#2f5a30", "azaleaL": "#5c8a2c", "fazaleaL": "#9a6aa8", "tgrass": "#6aae40",
    "fern": "#4f8f36", "poppy": "#d33a2c", "dandelion": "#f1d93b", "cornflower": "#4d6fe0", "oxeye": "#efefe6",
    "azure": "#cfe0ef", "allium": "#b46ad8", "tulip": "#e04a3a", "otulip": "#ef8d2f", "lily": "#f4f4f4",
    "mcarpet": "#6a8a35", "lantern": "#f0b040", "fence": "#9a7a4a", "shroom": "#f0a050", "diamond": "#5ee0d8",
    "emerald": "#30c060", "redstone": "#c0281c", "lapis": "#2a4ab0", "vineN": "#3d7a25", "vineS": "#3d7a25",
    "vineW": "#3d7a25", "vineE": "#3d7a25", "dark": "#3e2a17", "darkL": "#2c5a1a", "cherry": "#4a2a2a",
    "cherryL": "#f2a7c8",
}
COLORS.update({
    "snow": "#f2f6f8", "snowL": "#eef3f6", "ice": "#9cc4f2", "pice": "#8db3e6", "bice": "#74a8f0", "petals": "#f4a6c9",
    "tuff": "#6d6e66", "calcite": "#dfe0dc", "planks": "#73553a", "oplanks": "#a4834f", "slab": "#73553a",
    "sfence": "#6b4f35", "hay": "#c9a92e", "slime": "#76c35d", "gold": "#f2d23a", "glow": "#f0c870", "sealantern": "#c8e0dc",
    "mstwall": "#6f7a5d", "ladderN": "#9a7a4a", "ladderS": "#9a7a4a", "ladderW": "#9a7a4a", "ladderE": "#9a7a4a",
    "lfern": "#4f8f36", "dark_wood": "#4a3a26", "oak_wood": "#6b5130", "spruce_wood": "#4b3620",
})
for _wood in ("oak", "birch", "spruce", "dark", "cherry"):
    for _ax in ("x", "z"):
        COLORS[f"{_wood}_{_ax}"] = COLORS[_wood]


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


def simulate():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "sim.json")
        subprocess.run(["node", os.path.join(SRC, "simulate.mjs"), out], check=True, cwd=SRC)
        with open(out) as fh:
            return json.load(fh)


def render_area(a, scale=1):
    w, h = a["w"], a["h"]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    ys = a["ys"]
    for z in range(h):
        for x in range(w):
            k = a["top"][z * w + x]
            if not k:
                continue
            col = hexc(COLORS.get(k, "#ff00ff"))
            y = ys[z * w + x]
            north = ys[(z - 1) * w + x] if z > 0 and a["top"][(z - 1) * w + x] else y
            shade = 1.0 + max(-0.25, min(0.25, (y - north) * 0.09))
            shade *= 0.85 + 0.15 * max(0, min(1, (y - 60) / 60))
            px[x, z] = tuple(max(0, min(255, int(v * shade))) for v in col) + (255,)
    if scale != 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.NEAREST)
    return img


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def preview(sim):
    rows = [
        [("lobby", "Lobby (Árbol del Mundo)", 2), ("campal", "Campal 126x126", 1.6)],
        [(f"duel{i}", n, 2.4) for i, n in enumerate(["Claro del Bosque", "Ruinas Musgosas", "Cerezal", "Lago Helado"])],
        [(f"hunt{i}", n, 0.9) for i, n in enumerate(["Caza: Bosque Antiguo", "Caza: Cañón del Río", "Caza: Taiga Nevada"])],
    ]
    pad, head = 20, 34
    rendered = [[(label, render_area(sim[k], sc)) for k, label, sc in row] for row in rows]
    W = max(sum(max(im.width, 160) + pad for _, im in row) + pad for row in rendered)
    H = pad + sum(max(im.height for _, im in row) + head + pad for row in rendered)
    out = Image.new("RGBA", (W, H), (18, 26, 20, 255))
    d = ImageDraw.Draw(out)
    y = pad
    for row in rendered:
        x = pad
        for label, im in row:
            d.text((x, y), label, fill=(235, 240, 225), font=font(17))
            out.alpha_composite(im, (x, y + head))
            x += max(im.width, 160) + pad
        y += max(im.height for _, im in row) + head + pad
    return out


def iso_region(area, x0, z0, x1, z1, s=4, ymin=70):
    """An isometric view of a region (to show the trees)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "iso.json")
        subprocess.run(["node", os.path.join(SRC, "iso.mjs"), area, str(x0), str(z0), str(x1), str(z1), out], check=True, cwd=SRC)
        with open(out) as fh:
            cols = json.load(fh)
    blocks = []
    for x, z, segs in cols:
        col = {}
        for y0, y1, k in segs:
            for y in range(max(y0, ymin), y1 + 1):
                if k == "air":
                    col.pop(y, None)
                else:
                    col[y] = k
        blocks += [(x - x0, y - ymin, z - z0, k) for y, k in col.items()]
    W, D = x1 - x0 + 1, z1 - z0 + 1
    top = max(b[1] for b in blocks)
    img = Image.new("RGB", ((W + D) * s + 10, (W + D) * s // 2 + (top + 3) * s + 10), (18, 26, 20))
    d = ImageDraw.Draw(img)
    for x, y, z, k in sorted(blocks, key=lambda b: (b[0] + b[2], b[1])):
        c = hexc(COLORS.get(k, "#ff00ff"))
        px, py = (x - z) * s + D * s + 5, (x + z) * s // 2 - y * s + (top + 1) * s + 5
        d.polygon([(px, py), (px + s, py + s // 2), (px, py + s), (px - s, py + s // 2)], fill=c)
        d.polygon([(px - s, py + s // 2), (px, py + s), (px, py + 2 * s), (px - s, py + s + s // 2)], fill=tuple(int(v * 0.75) for v in c))
        d.polygon([(px, py + s), (px + s, py + s // 2), (px + s, py + s + s // 2), (px, py + 2 * s)], fill=tuple(int(v * 0.6) for v in c))
    return img


def icon(sim):
    lobby = render_area(sim["lobby"], 2)
    bg = Image.new("RGBA", lobby.size, (24, 40, 30, 255))
    bg.alpha_composite(lobby)
    return bg.resize((256, 256), Image.LANCZOS)


# ------------------------------------------------------------ main
def zip_dir(z, folder, arc_root):
    for base, _, files in os.walk(folder):
        for name in sorted(files):
            full = os.path.join(base, name)
            z.write(full, os.path.join(arc_root, os.path.relpath(full, folder)))


def main():
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)
    resource_files()
    tracks = songs("--music" in sys.argv)
    scripts(tracks)
    write(os.path.join(BP, "entities/text.json"), text_entity())
    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items() if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    try:
        sim = simulate()
    except (OSError, subprocess.CalledProcessError) as e:
        print("No se pudo simular con node:", e)
        sim = None
    ic = icon(sim) if sim else Image.new("RGBA", (256, 256), (40, 110, 50, 255))
    for pack in (BP, RP):
        ic.save(os.path.join(pack, "pack_icon.png"))
    if sim and "--preview" in sys.argv:
        preview(sim).convert("RGB").save(os.path.join(DOCS, "natura_pvp_preview.png"))
        iso_region("lobby", -76, -76, 75, 75, s=4, ymin=60).save(os.path.join(DOCS, "natura_pvp_lobby.png"))
        parts = [iso_region("hunt0", -40, -520, 30, -450, s=4, ymin=74), iso_region("hunt2", 520, -520, 600, -440, s=4, ymin=74)]
        both = Image.new("RGB", (sum(p.width for p in parts) + 20, max(p.height for p in parts)), (18, 26, 20))
        both.paste(parts[0], (0, (both.height - parts[0].height) // 2))
        both.paste(parts[1], (parts[0].width + 20, (both.height - parts[1].height) // 2))
        both.save(os.path.join(DOCS, "natura_pvp_caza.png"))

    # the world: void, with the whole map already built in its database
    os.makedirs(DIST, exist_ok=True)
    import world as world_writer
    tmp = tempfile.mkdtemp(prefix="natura_world_")
    try:
        subprocess.run(["node", os.path.join(SRC, "export.mjs"), tmp], check=True, cwd=SRC)
        db = os.path.join(tmp, "db")
        info = world_writer.build(tmp, db)
        print("Mundo prebuilt:", info)
        db_files = {name: open(os.path.join(db, name), "rb").read() for name in os.listdir(db)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    jpg = io.BytesIO()
    ic.convert("RGB").save(jpg, "JPEG", quality=90)

    def world_zip(path, folder="", packs_required=False):
        dat = level_dat(packs_required)
        read_level_dat(dat)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(folder + "level.dat", dat)
            z.writestr(folder + "levelname.txt", NAME)
            z.writestr(folder + "world_icon.jpeg", jpg.getvalue())
            z.writestr(folder + "world_behavior_packs.json", json.dumps([{"pack_id": UUIDS["bp"], "version": VERSION}], indent=2))
            z.writestr(folder + "world_resource_packs.json", json.dumps([{"pack_id": UUIDS["rp"], "version": VERSION}], indent=2))
            for name, data in db_files.items():
                z.writestr(folder + "db/" + name, data)
            zip_dir(z, BP, folder + "behavior_packs/NaturaPvP_BP")
            zip_dir(z, RP, folder + "resource_packs/NaturaPvP_RP")

    world_zip(os.path.join(DIST, "NaturaPvP.mcworld"))
    # for a Bedrock server (Aternos, BDS): the world folder inside a .zip, and the
    # resource pack (with the songs) required to join, so every player has it
    world_zip(os.path.join(DIST, "NaturaPvP_Aternos.zip"), "NaturaPvP/", packs_required=True)
    with zipfile.ZipFile(os.path.join(DIST, "NaturaPvP.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        zip_dir(z, BP, "NaturaPvP_BP")
        zip_dir(z, RP, "NaturaPvP_RP")
    print("Built", NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
