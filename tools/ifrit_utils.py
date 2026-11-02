"""Builds the "Útils for Ifrit" add-on: utilities activated with items.

- Utilidad de Niebla (ifrit:utilidad_niebla): fog (and sky) colour, 5 presets x density 1-15.
- Camera (ifrit:camera): camera fade, free (cinematics) and shake.
- Cinematic Creator (ifrit:cinematic_creator): editor for cinematics, given by Camera > Free.
- Killer Sure (ifrit:killer_sure): kills any player at once, like /kill.
- Time an Thing (ifrit:time_an_thing): time of day and weather.
- Effects (ifrit:effects): effects for the chosen players.

None of the items can be crafted or found: only the creative inventory or /give.
The scripts are in tools/ifrit_utils/*.js and are copied into the pack as they are.

    python3 tools/ifrit_utils.py
"""
import json
import os
import shutil
import zipfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "ifrit_utils")
ADDON_NAME = "Útils for Ifrit"
BP = os.path.join(ROOT, "IfritUtils_BP")
RP = os.path.join(ROOT, "IfritUtils_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 2, 0]
SCRIPT_API = "2.0.0"
SCRIPT_UI_API = "2.0.0"
MIN_ENGINE = [1, 21, 90]
UUIDS = dict(bp="dd38008d-918c-4516-9bba-e188c0cd82cc", bp_data="6ef2a65b-508d-4fe2-a143-14a6dc4c9c92",
             bp_script="3556f028-7d3f-496c-b6e4-d68ff5cd575f", rp="7542c33c-85ed-4054-8330-3c5a98eb2022",
             rp_res="f23335a0-a730-47ed-91ba-d6d0d9b9c257")

NS = "ifrit"
ITEMS = dict(niebla=f"{NS}:utilidad_niebla", camara=f"{NS}:camera", creador=f"{NS}:cinematic_creator",
             killer=f"{NS}:killer_sure", tiempo=f"{NS}:time_an_thing", efectos=f"{NS}:effects")
NAMES = dict(niebla="Utilidad de Niebla", camara="Camera", creador="Cinematic Creator",
             killer="Killer Sure", tiempo="Time an Thing", efectos="Effects")

# Fog presets. "boton" is the colour code of the menu button.
FOGS = [
    dict(id="verde_claro", nombre="Verde claro", color="#9eeb8f", boton="§a"),
    dict(id="hello_frozen", nombre="Hello Frozen", color="#cbe9f7", boton="§b"),   # winter white + cold cyan
    dict(id="lluvia_de_sangre", nombre="Lluvia de sangre", color="#7a0710", boton="§4"),  # red + dark blood red
    dict(id="blanco", nombre="Blanco", color="#f2f2f2", boton="§f"),
    dict(id="negro", nombre="Negro", color="#050505", boton="§0"),
]
DENSITY_MAX = 15


FOG_FAR = 96   # fog end at density 1; the sky dome sits there, so it must fit in the render distance
FOG_NEAR = 3   # fog end at density 15
SKY = f"{NS}:cielo"


def fog_end(density):
    """Blocks where the fog is total: 1 -> 96 (light haze), 15 -> 3 (you see almost nothing)."""
    return round(FOG_FAR * (FOG_NEAR / FOG_FAR) ** ((density - 1) / (DENSITY_MAX - 1)), 1)


# ---------------------------------------------------------------- sky dome
# Bedrock's sky is not geometry, so the fog does not cover it. The dome is a huge box around
# the camera, just past the end of the fog: the fog paints it fully in the fog colour, so the
# whole sky takes that colour (also at night, when the fog colour gets darker).
def sky_entity():
    return {"format_version": "1.21.90", "minecraft:entity": {
        "description": {"identifier": SKY, "is_spawnable": False, "is_summonable": True,
                        "properties": {
                            f"{NS}:color": {"type": "int", "range": [0, len(FOGS) - 1], "default": 0,
                                            "client_sync": True},
                            f"{NS}:radio": {"type": "float", "range": [0.5, 400], "default": 50,
                                            "client_sync": True}}},
        "components": {
            "minecraft:collision_box": {"width": 0.001, "height": 0.001},
            "minecraft:physics": {"has_gravity": False, "has_collision": False},
            "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
            "minecraft:damage_sensor": {"triggers": {"cause": "all", "deals_damage": "no"}},
            "minecraft:knockback_resistance": {"value": 1},
            "minecraft:fire_immune": True,
            "minecraft:health": {"value": 1, "max": 1},
            "minecraft:type_family": {"family": ["ifrit_cielo", "inanimate"]},
        }}}


def sky_client():
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": SKY,
        "materials": {"default": "entity_alphatest"},
        "textures": {f["id"]: f"textures/entity/ifrit/cielo_{f['id']}" for f in FOGS},
        "geometry": {"default": "geometry.ifrit.cielo"},
        "scripts": {"scale": f"q.property('{NS}:radio') * 2"},
        "render_controllers": ["controller.render.ifrit.cielo"]}}}


def sky_render_controller():
    return {"format_version": "1.8.0", "render_controllers": {"controller.render.ifrit.cielo": {
        "arrays": {"textures": {"Array.cielo": [f"Texture.{f['id']}" for f in FOGS]}},
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": [f"Array.cielo[q.property('{NS}:color')]"],
        "ignore_lighting": True,
        # only the owner sees it: the dome is centred on their camera
        "part_visibility": [{"*": "q.distance_from_camera < 3"}]}}}


def sky_geo():
    """Six thin walls of a 1-block box (scaled by the radius). Their inner faces point at the
    centre, so they are visible from inside without a custom material."""
    t, h = 0.05, 8
    walls = [([h - t, -h, -h], [t, 16, 16]), ([-h, -h, -h], [t, 16, 16]),
             ([-h, h - t, -h], [16, t, 16]), ([-h, -h, -h], [16, t, 16]),
             ([-h, -h, h - t], [16, 16, t]), ([-h, -h, -h], [16, 16, t])]
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.ifrit.cielo", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 4, "visible_bounds_height": 4, "visible_bounds_offset": [0, 0, 0]},
        "bones": [{"name": "cielo", "pivot": [0, 0, 0],
                   "cubes": [{"origin": o, "size": sz, "uv": [0, 0]} for o, sz in walls]}]}]}


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- icons (16x16)
ICONS = {
    "niebla": ({"k": "#2b2f3a", "w": "#f4f8fb", "g": "#c9d3dc", "a": "#9eeb8f", "c": "#8fd3f4", "r": "#b3121b"}, [
        "................",
        "......kkkk......",
        ".....kwwwwk.....",
        "...kkwwwwwwkk...",
        "..kwwwwwwggwwk..",
        ".kwwwwwwwwwgwwk.",
        ".kwggwwwwwwwwgk.",
        "..kkkkkkkkkkkk..",
        "................",
        ".aaaaaaa..aaaa..",
        "................",
        "...cccccccccc...",
        "................",
        ".rrrr..rrrrrrr..",
        "................",
        "................"]),
    "camara": ({"k": "#16161c", "b": "#3a3d4a", "B": "#565a6b", "l": "#7fd4ff", "L": "#d8f4ff", "r": "#e0303a"}, [
        "................",
        "................",
        "....kkkk........",
        "...kBBBBk...kk..",
        ".kkkkkkkkkkkkrk.",
        ".kBBBBBBBBBBBBk.",
        ".kBbbbkkkkbbbbk.",
        ".kBbbklllLkbbbk.",
        ".kBbklllLLLkbbk.",
        ".kBbkllllllkbbk.",
        ".kBbklllllLkbbk.",
        ".kBbbkllllkbbbk.",
        ".kbbbbkkkkbbbbk.",
        ".kkkkkkkkkkkkkk.",
        "................",
        "................"]),
    "creador": ({"k": "#111111", "w": "#f2f2f2", "p": "#9b59d6", "b": "#2b2b33", "g": "#ffd84a"}, [
        "................",
        "..kkkkkkkkkkkk..",
        ".kwwkkwwkkwwkkk.",
        ".kkkwwkkwwkkwwk.",
        "..kkkkkkkkkkkkk.",
        ".kkkkkkkkkkkkkk.",
        ".kwwkkwwkkwwkkk.",
        ".kkkkkkkkkkkkkk.",
        ".kbbbbbbbbbbbbk.",
        ".kbpppbbbbbbbbk.",
        ".kbbbbbbbgbbbbk.",
        ".kbppppbbggbbbk.",
        ".kbbbbbbbgbbbbk.",
        ".kbbbbbbbbbbbbk.",
        ".kkkkkkkkkkkkkk.",
        "................"]),
    "killer": ({"k": "#0d0d0d", "s": "#d9dde2", "S": "#ffffff", "d": "#8a9099", "r": "#c0141c", "R": "#5c0006",
                "h": "#3a2316"}, [
        "............kkk.",
        "...........kSsk.",
        "..........kSsdk.",
        ".........kSsdk..",
        "........kSsdk...",
        ".......kSsdk....",
        "......kSsdk.....",
        "..k..kSsdk......",
        "..krkSsdk.......",
        "...krsdk........",
        "....krrk........",
        "...khRrrk.......",
        "..khhk.krk......",
        ".khhk...k.......",
        ".kRk............",
        "..k............."]),
    "tiempo": ({"k": "#2a1d0e", "g": "#e8b931", "G": "#fff2a8", "s": "#ffd23f", "n": "#1d2a5c", "m": "#e9edf7",
                "h": "#2a1d0e"}, [
        "................",
        ".....kkkkkk.....",
        "...kkggggggkk...",
        "..kgssssnnnngk..",
        "..kgssssnnnngk..",
        ".kgsssssnnmnngk.",
        ".kgsssssnnnnngk.",
        ".kgssssshnnnngk.",
        ".kgsssshhhhnngk.",
        ".kgsssssnnnnngk.",
        ".kgsssssnnnnngk.",
        "..kgssssnnnngk..",
        "..kgssssnnnngk..",
        "...kkggggggkk...",
        ".....kkkkkk.....",
        "................"]),
    "efectos": ({"k": "#1a1426", "w": "#e8eef5", "c": "#8a5a2b", "p": "#b04ae0", "P": "#e3a6ff", "q": "#7b2aa8"}, [
        "......kkkk......",
        "......kcck......",
        "......kkkk......",
        ".......kk.......",
        "......kwwk......",
        ".....kwwwwk.....",
        "....kwwwwwwk....",
        "...kwpppppPwk...",
        "..kppPppppppPk..",
        "..kpPppppppppk..",
        "..kpppppppppqk..",
        "..kpppppppppqk..",
        "..kqpppppppqqk..",
        "...kqqqqqqqqk...",
        "....kkkkkkkk....",
        "................"]),
}


def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


def icon(key):
    pal, rows = ICONS[key]
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                im.putpixel((x, y), hx(pal[ch]))
    return im


# ---------------------------------------------------------------- packs
def item(key):
    comps = {
        "minecraft:icon": f"ifrit_{key}",
        "minecraft:display_name": {"value": f"item.{ITEMS[key]}.name"},
        "minecraft:max_stack_size": 1,
        "minecraft:use_modifiers": {"use_duration": 0.1, "movement_modifier": 1.0},
        "minecraft:glint": key in ("killer", "efectos"),
    }
    if key == "killer":
        comps["minecraft:hand_equipped"] = True
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": ITEMS[key], "menu_category": {"category": "items"}},
        "components": comps}}


def fog(preset, density):
    end = fog_end(density)
    layer = {"fog_start": 0, "fog_end": end, "fog_color": preset["color"], "render_distance_type": "fixed"}
    return {"format_version": "1.16.100", "minecraft:fog_settings": {
        "description": {"identifier": f"{NS}:niebla_{preset['id']}_{density}"},
        "distance": {"air": layer, "weather": layer}}}


def config_js():
    fogs = [{k: f[k] for k in ("id", "nombre", "boton")} for f in FOGS]
    return ("// Generated by tools/ifrit_utils.py\n"
            f"export const ITEMS = {json.dumps(ITEMS, indent=2)};\n\n"
            f"export const NIEBLAS = {json.dumps(fogs, indent=2, ensure_ascii=False)};\n\n"
            f"export const NIEBLA_DENSIDAD_MAX = {DENSITY_MAX};\n\n"
            "// Fog end (blocks) for each density, 1..15: the sky dome goes just past it.\n"
            f"export const NIEBLA_FIN = {json.dumps([fog_end(d) for d in range(1, DENSITY_MAX + 1)])};\n\n"
            f'export const CIELO = "{SKY}";\n')


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Utilidades que se activan con objetos.",
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SCRIPT_API},
                         {"module_name": "@minecraft/server-ui", "version": SCRIPT_UI_API}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Texturas y nieblas de Útils for Ifrit.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def main():
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    # textures
    icons = {k: icon(k) for k in ITEMS}
    texture_data = {}
    for k, im in icons.items():
        path = f"textures/items/ifrit/{k}"
        os.makedirs(os.path.join(RP, os.path.dirname(path)), exist_ok=True)
        im.save(os.path.join(RP, path + ".png"))
        texture_data[f"ifrit_{k}"] = {"textures": path}
    write(os.path.join(RP, "textures/item_texture.json"),
          {"resource_pack_name": NS, "texture_name": "atlas.items", "texture_data": texture_data})

    # fogs: one file per colour and density
    for preset in FOGS:
        for d in range(1, DENSITY_MAX + 1):
            write(os.path.join(RP, f"fogs/{preset['id']}_{d}.json"), fog(preset, d))

    # sky dome
    for f in FOGS:
        path = os.path.join(RP, f"textures/entity/ifrit/cielo_{f['id']}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Image.new("RGBA", (64, 64), hx(f["color"])).save(path)
    write(os.path.join(RP, "entity/cielo.entity.json"), sky_client())
    write(os.path.join(RP, "render_controllers/cielo.render_controllers.json"), sky_render_controller())
    write(os.path.join(RP, "models/entity/cielo.geo.json"), sky_geo())
    write(os.path.join(BP, "entities/cielo.json"), sky_entity())

    # texts
    lang = {f"item.{ITEMS[k]}.name": v for k, v in NAMES.items()}
    lang[f"entity.{SKY}.name"] = "Cielo"
    lang.update({"pack.name": ADDON_NAME, "pack.description": "Utilidades que se activan con objetos."})
    for code in ("es_ES", "es_MX", "en_US", "en_GB"):
        write(os.path.join(RP, f"texts/{code}.lang"), "\n".join(f"{k}={v}" for k, v in lang.items()) + "\n")
        write(os.path.join(BP, f"texts/{code}.lang"),
              "\n".join(f"{k}={v}" for k, v in lang.items() if k.startswith("pack.")) + "\n")
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    # behavior pack
    for k in ITEMS:
        write(os.path.join(BP, f"items/{ITEMS[k].split(':')[1]}.json"), item(k))
    os.makedirs(os.path.join(BP, "scripts"), exist_ok=True)
    for f in sorted(os.listdir(SRC)):
        if f.endswith(".js"):
            shutil.copy(os.path.join(SRC, f), os.path.join(BP, "scripts", f))
    write(os.path.join(BP, "scripts/config.js"), config_js())
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    # pack icon and preview: the six items
    order = ["niebla", "camara", "creador", "killer", "tiempo", "efectos"]
    pack_icon = Image.new("RGBA", (128, 128), (34, 18, 40, 255))
    for i, k in enumerate(order):
        pack_icon.alpha_composite(icons[k].resize((36, 36), Image.NEAREST), (6 + (i % 3) * 40, 22 + (i // 3) * 46))
    for pack in (BP, RP):
        pack_icon.save(os.path.join(pack, "pack_icon.png"))
    preview = Image.new("RGBA", (6 * 80 + 16, 96), (34, 18, 40, 255))
    for i, k in enumerate(order):
        preview.alpha_composite(icons[k].resize((64, 64), Image.NEAREST), (16 + i * 80, 16))
    preview.save(os.path.join(ROOT, "docs", "ifrit_utils_preview.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "IfritUtils.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
