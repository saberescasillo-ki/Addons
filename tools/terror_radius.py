"""Builds the "Terror Radius" add-on: players near a carrier hear a looping theme.

- Selector de Terror Radius (terror:selector): use it looking at a player (or a
  dummy) to give / remove the terror radius; use it on the air (or sneaking) to
  open the menu: who has it, your own volume and the options.
- Layer 1 loops for every player 30..15 blocks away from a carrier, layer 2 for
  every player 15..0 blocks away. It stops as soon as they leave the radius.
- Only players count. The Dummy (terror:dummy) is a still entity that the script
  treats as a player, to test the add-on alone.

The audio is in sources/terror_radius/ (one .ogg per layer). The length of each
loop is read from the file, so replacing a file is enough to change the theme.
The script is tools/terror_radius/main.js.

    python3 tools/terror_radius.py            # regenerate the packs and the .mcaddon
    python3 tools/terror_radius.py --preview  # also refresh docs/terror_radius_preview.png
"""
import json
import os
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "terror_radius")
AUDIO = os.path.join(ROOT, "sources", "terror_radius")
ADDON_NAME = "Terror Radius"
BP = os.path.join(ROOT, "TerrorRadius_BP")
RP = os.path.join(ROOT, "TerrorRadius_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "2.0.0"
SCRIPT_UI = "2.0.0"
MIN_ENGINE = [1, 21, 90]
UUIDS = dict(bp="cf78e115-b9d8-4ab6-bf19-ae52be408c7d", bp_data="ff2c99db-b347-4f9f-8f0c-26b91aff006b", bp_script="67effdf6-0986-4f74-90eb-3e9b35273510", rp="56e13f80-c27c-480f-92e7-ccfdc0e9085a", rp_res="bcd23ab6-9ec1-433c-a51e-284453c9ad99")

NS = "terror"
SELECTOR = f"{NS}:selector"
DUMMY = f"{NS}:dummy"

# The only terror radius for now: (sound id, file in sources/terror_radius/).
LAYERS = [
    (f"{NS}.burden.layer1", "burden_layer_1.ogg"),   # far: 30..15 blocks
    (f"{NS}.burden.layer2", "burden_layer_2.ogg"),   # near: 15..0 blocks
]

# Everything main.js uses (the layers are added in main()).
CONFIG = dict(
    item=SELECTOR,
    dummy=DUMMY,
    tag="terror_radius",   # the carriers have this tag (also works with /tag)
    outer=30,              # layer 1 from here...
    inner=15,              # ...to here; layer 2 from here to 0
    reach=12,              # blocks: how far the selector picks the player you look at
    overlapMs=50,          # each loop starts this early, so there is never a gap
)

LANG = {
    "es": {
        f"item.{SELECTOR}.name": "Selector de Terror Radius",
        f"entity.{DUMMY}.name": "Dummy",
        f"item.spawn_egg.entity.{DUMMY}.name": "Generar Dummy",
        "pack.name": ADDON_NAME,
        "pack.description": "Los jugadores cercanos oyen tu Terror Radius.",
    },
    "en": {
        f"item.{SELECTOR}.name": "Terror Radius Selector",
        f"entity.{DUMMY}.name": "Dummy",
        f"item.spawn_egg.entity.{DUMMY}.name": "Spawn Dummy",
        "pack.name": ADDON_NAME,
        "pack.description": "Nearby players hear your Terror Radius.",
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


def ogg_seconds(path):
    """Length of an Ogg Vorbis file: last granule position / sample rate."""
    with open(path, "rb") as f:
        data = f.read()
    head = data.index(b"\x01vorbis")
    rate = int.from_bytes(data[head + 12:head + 16], "little")
    last = data.rindex(b"OggS")
    samples = int.from_bytes(data[last + 6:last + 14], "little")
    return samples / rate


# ---------------------------------------------------------------- textures
def selector_icon():
    """A red heart in the middle of two rings (the two layers)."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = im.load()
    far, near = hx("#5a1016"), hx("#c8202a")
    for x in range(16):
        for y in range(16):
            r = ((x - 7.5) ** 2 + (y - 7.5) ** 2) ** 0.5
            if 6.6 <= r < 7.7:
                px[x, y] = far
            elif 4.3 <= r < 5.3:
                px[x, y] = near
    heart = ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]
    for j, row in enumerate(heart):
        for i, c in enumerate(row):
            if c == "1":
                px[5 + i - 1, 5 + j] = hx("#ff4a4a") if j < 2 and i in (1, 4) else hx("#e01020")
    return im


SKIN = dict(head="#c9a27a", hair="#3b2a1c", shirt="#8a8f98", arms="#7a7f88", legs="#3d4250", shoes="#22242b",
            eye="#ffffff", pupil="#b01820", mark="#c8202a")


def dummy_skin():
    """64x64 player layout: a plain grey mannequin with a red target on the chest."""
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def box(u, v, w, h, depth, color):
        # the unwrapped faces of one cube
        d.rectangle([u + depth, v, u + depth + 2 * w - 1, v + depth - 1], fill=hx(color))
        d.rectangle([u, v + depth, u + 2 * depth + 2 * w - 1, v + depth + h - 1], fill=hx(color))

    box(0, 0, 8, 8, 8, SKIN["head"])
    d.rectangle([8, 0, 15, 7], fill=hx(SKIN["hair"]))            # top of the head
    d.rectangle([0, 8, 31, 9], fill=hx(SKIN["hair"]))            # hairline all around
    d.rectangle([24, 8, 31, 15], fill=hx(SKIN["hair"]))          # back of the head
    for x in (9, 13):                                           # eyes on the front face
        d.rectangle([x, 11, x + 1, 12], fill=hx(SKIN["eye"]))
    d.point([(10, 12), (13, 12)], fill=hx(SKIN["pupil"]))
    d.rectangle([10, 14, 13, 14], fill=hx("#8a6a4a"))            # mouth
    box(16, 16, 8, 12, 4, SKIN["shirt"])
    d.ellipse([21, 21, 26, 26], outline=hx(SKIN["mark"]))        # target on the chest
    d.point([(23, 23), (24, 24), (23, 24), (24, 23)], fill=hx(SKIN["mark"]))
    for u, v in ((40, 16), (32, 48)):                           # arms
        box(u, v, 4, 12, 4, SKIN["arms"])
        d.rectangle([u, v + 13, u + 15, v + 15], fill=hx(SKIN["head"]))
    for u, v in ((0, 16), (16, 48)):                            # legs
        box(u, v, 4, 12, 4, SKIN["legs"])
        d.rectangle([u, v + 13, u + 15, v + 15], fill=hx(SKIN["shoes"]))
    return im


# ---------------------------------------------------------------- dummy
def dummy_geometry():
    def bone(name, pivot, origin, size, uv, mirror=False):
        cube = {"origin": origin, "size": size, "uv": uv}
        if mirror:
            cube["mirror"] = True
        return {"name": name, "pivot": pivot, "cubes": [cube]}

    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.terror.dummy", "texture_width": 64, "texture_height": 64,
                        "visible_bounds_width": 2, "visible_bounds_height": 3,
                        "visible_bounds_offset": [0, 1, 0]},
        "bones": [
            bone("body", [0, 24, 0], [-4, 12, -2], [8, 12, 4], [16, 16]),
            bone("head", [0, 24, 0], [-4, 24, -4], [8, 8, 8], [0, 0]),
            bone("rightArm", [-5, 22, 0], [-8, 12, -2], [4, 12, 4], [40, 16]),
            bone("leftArm", [5, 22, 0], [4, 12, -2], [4, 12, 4], [32, 48]),
            bone("rightLeg", [-1.9, 12, 0], [-3.9, 0, -2], [4, 12, 4], [0, 16]),
            bone("leftLeg", [1.9, 12, 0], [-0.1, 0, -2], [4, 12, 4], [16, 48]),
        ]}]}


def dummy_entity():
    """Stands still and does nothing: the script is what treats it as a player."""
    return {"format_version": "1.21.0", "minecraft:entity": {
        "description": {"identifier": DUMMY, "is_spawnable": True, "is_summonable": True,
                        "is_experimental": False},
        "components": {
            "minecraft:type_family": {"family": ["terror_dummy", "inanimate"]},
            "minecraft:collision_box": {"width": 0.6, "height": 1.8},
            "minecraft:health": {"value": 20, "max": 20},
            "minecraft:physics": {},
            "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
            "minecraft:knockback_resistance": {"value": 1.0},
            "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
            "minecraft:persistent": {},
            "minecraft:fire_immune": {},
            "minecraft:damage_sensor": {"triggers": [
                {"cause": "fall", "deals_damage": "no"}]},
        }}}


def dummy_client():
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": {
        "identifier": DUMMY,
        "materials": {"default": "entity_alphatest"},
        "textures": {"default": "textures/entity/terror/dummy"},
        "geometry": {"default": "geometry.terror.dummy"},
        "render_controllers": ["controller.render.terror.dummy"],
        "spawn_egg": {"base_color": "#8a8f98", "overlay_color": "#c8202a"},
    }}}


def render_controller():
    return {"format_version": "1.8.0", "render_controllers": {"controller.render.terror.dummy": {
        "geometry": "Geometry.default", "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"]}}}


# ---------------------------------------------------------------- item + sounds
def selector_item():
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": SELECTOR, "menu_category": {"category": "equipment"}},
        "components": {
            "minecraft:icon": "terror_selector",
            "minecraft:display_name": {"value": f"item.{SELECTOR}.name"},
            "minecraft:max_stack_size": 1,
            "minecraft:glint": True,
            "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
        }}}


def sound_definitions():
    # Not 3D and not streamed: the loop sounds the same wherever the listener moves,
    # and starts again without a pause.
    return {"format_version": "1.14.0", "sound_definitions": {
        sound: {"category": "ui", "sounds": [
            {"name": f"sounds/terror/{os.path.splitext(name)[0]}", "is3D": False, "stream": False,
             "volume": 1.0, "load_on_low_memory": True}]}
        for sound, name in LAYERS}}


def script(config):
    with open(os.path.join(SRC, "main.js"), encoding="utf-8") as f:
        return f.read().replace("__CONFIG__", json.dumps(config))


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Los jugadores cercanos oyen tu Terror Radius.",
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SCRIPT_API},
                         {"module_name": "@minecraft/server-ui", "version": SCRIPT_UI}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Audio, selector y dummy del Terror Radius.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def lang(d):
    return "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"


# ---------------------------------------------------------------- preview
def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def dummy_front(skin, s):
    """The dummy seen from the front, from its skin."""
    im = Image.new("RGBA", (16 * s, 32 * s), (0, 0, 0, 0))
    parts = [((8, 8, 16, 16), (4, 0)), ((20, 20, 28, 32), (4, 8)), ((44, 20, 48, 32), (0, 8)),
             ((36, 52, 40, 64), (12, 8)), ((4, 20, 8, 32), (4, 20)), ((20, 52, 24, 64), (8, 20))]
    for crop, (x, y) in parts:
        face = skin.crop(crop)
        im.alpha_composite(face.resize((face.width * s, face.height * s), Image.NEAREST), (x * s, y * s))
    return im


def preview(icon16, skin, config):
    w, h = 760, 420
    sheet = Image.new("RGBA", (w, h), hx("#12090b"))
    d = ImageDraw.Draw(sheet)
    cx, cy, k = 250, 215, 6   # k pixels per block
    outer, inner = config["outer"], config["inner"]
    d.ellipse([cx - outer * k, cy - outer * k, cx + outer * k, cy + outer * k], fill=hx("#2a0e12"),
              outline=hx("#5a1016"), width=3)
    d.ellipse([cx - inner * k, cy - inner * k, cx + inner * k, cy + inner * k], fill=hx("#4a1218"),
              outline=hx("#c8202a"), width=3)
    body = dummy_front(skin, 3)
    sheet.alpha_composite(body, (cx - body.width // 2, cy - body.height // 2))
    d.text((cx, cy - inner * k + 22), f"capa 2 · {inner} a 0 bloques", fill=hx("#ff9a9a"), anchor="mm",
           font=font(15))
    d.text((cx, cy - outer * k + 22), f"capa 1 · {outer} a {inner} bloques", fill=hx("#c87070"), anchor="mm",
           font=font(15))
    x = 500
    sheet.alpha_composite(icon16.resize((96, 96), Image.NEAREST), (x, 40))
    d.text((x + 110, 70), "Selector de", fill=hx("#f0e0e0"), anchor="lm", font=font(17))
    d.text((x + 110, 96), "Terror Radius", fill=hx("#f0e0e0"), anchor="lm", font=font(17))
    big = dummy_front(skin, 6)
    sheet.alpha_composite(big, (x, 170))
    d.text((x + 110, 250), "Dummy", fill=hx("#f0e0e0"), anchor="lm", font=font(17))
    d.text((x + 110, 276), "cuenta como jugador", fill=hx("#b09090"), anchor="lm", font=font(13))
    return sheet


# ---------------------------------------------------------------- build
def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    icon16, skin = selector_icon(), dummy_skin()
    for path, im in (("textures/items/terror/selector", icon16), ("textures/entity/terror/dummy", skin)):
        full = os.path.join(RP, path + ".png")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        im.save(full)
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "terror", "texture_name": "atlas.items", "texture_data": {
            "terror_selector": {"textures": "textures/items/terror/selector"}}})

    config = dict(CONFIG, layers=[])
    os.makedirs(os.path.join(RP, "sounds/terror"))
    for sound, name in LAYERS:
        shutil.copy(os.path.join(AUDIO, name), os.path.join(RP, "sounds/terror", name))
        config["layers"].append(dict(sound=sound, seconds=round(ogg_seconds(os.path.join(AUDIO, name)), 3)))
    write(os.path.join(RP, "sounds/sound_definitions.json"), sound_definitions())

    write(os.path.join(RP, "entity/dummy.entity.json"), dummy_client())
    write(os.path.join(RP, "models/entity/dummy.geo.json"), dummy_geometry())
    write(os.path.join(RP, "render_controllers/terror.render_controllers.json"), render_controller())
    write(os.path.join(BP, "entities/dummy.json"), dummy_entity())
    write(os.path.join(BP, "items/selector.json"), selector_item())
    write(os.path.join(BP, "scripts/main.js"), script(config))

    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        write(os.path.join(RP, f"texts/{code}.lang"), lang(LANG[key]))
        write(os.path.join(BP, f"texts/{code}.lang"), lang({k: v for k, v in LANG[key].items()
                                                             if k.startswith("pack.")}))
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    icon = Image.new("RGBA", (128, 128), hx("#12090b"))
    icon.alpha_composite(icon16.resize((112, 112), Image.NEAREST), (8, 8))
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "TerrorRadius.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))

    if prev:
        preview(icon16, skin, config).save(os.path.join(ROOT, "docs", "terror_radius_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))
    for layer in config["layers"]:
        print("  ", layer["sound"], layer["seconds"], "s")


if __name__ == "__main__":
    main()
