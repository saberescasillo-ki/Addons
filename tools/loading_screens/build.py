"""Builds the Loading Screens add-on (artificial loading screens) into private/.

    python3 tools/loading_screens/build.py

A screen is a picture over the middle 80 % of the screen, above the rest of the
HUD; the player gets Resistance 255 meanwhile (and 5 s more). Optional fade to
black, Blindness and Darkness: 2 s in, the screen, 3 s out. The pictures: Ignis drawn
in code (art.py) and the owner's own images in private/loading_sources/. Admins show them
with the Loading Screen Remote (which screen, how many seconds, to whom) or with
/scriptevent ldscr:show <screen> <seconds>. They have no other effect for now.
"""
import json
import os
import re
import shutil
import sys
import uuid
import zipfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import art  # noqa: E402

OUT = os.path.join(ROOT, "private")
NAME = "LoadingScreens"
BP = os.path.join(OUT, f"{NAME}_BP")
RP = os.path.join(OUT, f"{NAME}_RP")
MCADDON = os.path.join(OUT, f"{NAME}.mcaddon")
SOURCES = os.path.join(OUT, "loading_sources")  # the owner's pictures (not in git)
MAX_W = 1024
VERSION = [1, 3, 0]
ITEM = "ldscr:loading_remote"


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/saberescasillo-ki/addons/{NAME}/{name}"))


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def screens():
    """id -> marker, read from screens.js (the script and the UI must agree)."""
    with open(os.path.join(HERE, "screens.js"), encoding="utf-8") as f:
        text = f.read()
    found = re.findall(r'id: "([a-z_]+)",\s*name: "[^"]*",\s*marker: "([^"]+)"', text)
    if not found:
        sys.exit("screens.js: no encuentro pantallas")
    return found


# --- packs ----------------------------------------------------------------------------
def manifests():
    header = {"version": VERSION, "min_engine_version": [1, 21, 90]}
    dump(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "Loading Screens BP", "description": "Pantallas de carga artificiales", "uuid": uid("bp"), **header},
        "modules": [{"type": "data", "uuid": uid("bp-data"), "version": VERSION},
                    {"type": "script", "language": "javascript", "uuid": uid("bp-script"), "version": VERSION,
                     "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": uid("rp"), "version": VERSION},
                         {"module_name": "@minecraft/server", "version": "2.0.0"},
                         {"module_name": "@minecraft/server-ui", "version": "2.0.0"}]})
    dump(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "Loading Screens RP", "description": "Pantallas de carga artificiales", "uuid": uid("rp"), **header},
        "modules": [{"type": "resources", "uuid": uid("rp-res"), "version": VERSION}],
        "dependencies": [{"uuid": uid("bp"), "version": VERSION}]})


def trim_black(img):
    """Drops the black bars along the top and bottom of a picture."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    def black(y):
        return sum(1 for x in range(0, w, 4) if sum(px[x, y]) < 60) / len(range(0, w, 4)) > 0.97
    top, bottom = 0, h - 1
    while top < bottom and black(top):
        top += 1
    while bottom > top and black(bottom):
        bottom -= 1
    return rgb.crop((0, top, w, bottom + 1))


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def write_loading(img, pixel=False):
    """Writes "Loading" in the middle of the picture: gold letters, dark outline.
    pixel: drawn at the picture's own small size without smoothing (pixel art)."""
    from PIL import ImageFont
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    if pixel:
        d.fontmode = "1"
    size = max(10, img.height // (7 if pixel else 8))
    font = ImageFont.truetype(FONT, size)
    x0, y0, x1, y1 = d.textbbox((0, 0), "Loading", font=font)
    x, y = (img.width - (x1 - x0)) / 2 - x0, (img.height - (y1 - y0)) / 2 - y0
    edge = max(1, size // 14)
    d.text((x + edge * 2, y + edge * 2), "Loading", font=font, fill=(40, 16, 0, 200))
    d.text((x, y), "Loading", font=font, fill=(255, 219, 115, 255), stroke_width=edge, stroke_fill=(30, 10, 0, 255))
    return img


def picture_file(sid):
    for ext in (".png", ".jpg", ".jpeg"):
        path = os.path.join(SOURCES, sid + ext)
        if os.path.exists(path):
            return path
    return None


def textures(picture):
    tex = os.path.join(RP, "textures", "ldscr")
    os.makedirs(tex, exist_ok=True)
    small = picture.resize((art.W, art.H), Image.NEAREST)
    write_loading(small, pixel=True).resize(picture.size, Image.NEAREST).convert("RGB").save(
        os.path.join(tex, "ignis.png"), optimize=True)
    for sid, _ in screens():
        if sid == "ignis":
            continue
        path = picture_file(sid)
        if not path:
            sys.exit(f"falta la imagen de la pantalla '{sid}' en {SOURCES}")
        img = trim_black(Image.open(path))
        if img.width > MAX_W:
            img = img.resize((MAX_W, round(img.height * MAX_W / img.width)), Image.LANCZOS)
        write_loading(img).convert("RGB").save(os.path.join(tex, f"{sid}.png"), optimize=True)
    # pack icons: Ignis' head and the burning core
    icon = picture.resize((art.W, art.H), Image.NEAREST).crop((128, 0, 128 + 80, 80)).resize((256, 256), Image.NEAREST)
    icon.save(os.path.join(RP, "pack_icon.png"))
    icon.save(os.path.join(BP, "pack_icon.png"))
    # the remote: a little screen with a flame
    item = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(item)
    d.rectangle((1, 2, 14, 11), fill=(30, 26, 32, 255), outline=(214, 160, 40, 255))
    d.rectangle((3, 4, 12, 9), fill=(70, 20, 16, 255))
    d.polygon([(7, 9), (5, 7), (7, 4), (8, 6), (10, 5), (10, 8), (8, 9)], fill=(255, 150, 40, 255))
    d.point((7, 7), fill=(255, 236, 140, 255))
    d.rectangle((6, 12, 9, 13), fill=(120, 72, 16, 255))
    d.rectangle((4, 14, 11, 14), fill=(214, 160, 40, 255))
    os.makedirs(os.path.join(RP, "textures", "items"), exist_ok=True)
    item.save(os.path.join(RP, "textures", "items", "loading_remote.png"))
    dump(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": NAME, "texture_name": "atlas.items",
        "texture_data": {"ldscr_loading_remote": {"textures": "textures/items/loading_remote"}}})


def item():
    dump(os.path.join(BP, "items", "loading_remote.json"), {
        "format_version": "1.21.40",
        "minecraft:item": {
            "description": {"identifier": ITEM, "menu_category": {"category": "items"}},
            "components": {
                "minecraft:icon": "ldscr_loading_remote",
                "minecraft:display_name": {"value": f"item.{ITEM}.name"},
                "minecraft:max_stack_size": 1,
                "minecraft:glint": True,
            }}})


def scripts():
    for name in ("main.js", "screens.js"):
        os.makedirs(os.path.join(BP, "scripts"), exist_ok=True)
        shutil.copyfile(os.path.join(HERE, name), os.path.join(BP, "scripts", name))


# --- UI ---------------------------------------------------------------------------------
def screen(marker, picture):
    """The picture alone, in the middle 80 % of the screen (proportions kept, no
    frame); the rest of the screen stays as it is."""
    visible = f"(not ((#hud_title_text_string - '{marker}') = #hud_title_text_string))"
    return {
        "type": "panel", "size": ["80%", "80%"], "anchor_from": "center", "anchor_to": "center", "layer": 1,
        "bindings": [{"binding_name": "#hud_title_text_string"},
                     {"binding_type": "view", "source_property_name": visible, "target_property_name": "#visible"}],
        "controls": [{"art": {"type": "image", "texture": f"textures/ldscr/{picture}", "size": ["100%", "100%"],
                              "keep_ratio": True, "bilinear": picture != "ignis", "layer": 2}}],
    }


def ui():
    found = screens()
    doc = {"namespace": "ldscr",
           "overlay": {"type": "panel", "size": ["100%", "100%"], "layer": 90,
                       "controls": [{f"{sid}@ldscr.{sid}_screen": {}} for sid, _ in found]}}
    for sid, marker in found:
        doc[f"{sid}_screen"] = screen(marker, sid)
    dump(os.path.join(RP, "ui", "ldscr_screens.json"), doc)
    dump(os.path.join(RP, "ui", "_ui_defs.json"), {"ui_defs": ["ui/ldscr_screens.json"]})
    dump(os.path.join(RP, "ui", "hud_screen.json"), {
        "root_panel": {"modifications": [{"array_name": "controls", "operation": "insert_back",
                                          "value": [{"ldscr_overlay@ldscr.overlay": {}}]}]}})


def lang():
    names = {"en_US": "Loading Screen Remote", "es_ES": "Control de pantallas de carga",
             "es_MX": "Control de pantallas de carga"}
    for code, n in names.items():
        write(os.path.join(RP, "texts", f"{code}.lang"), f"item.{ITEM}.name=§6{n}§r\n")
        write(os.path.join(BP, "texts", f"{code}.lang"), f"pack.name=Loading Screens\n")
    dump(os.path.join(RP, "texts", "languages.json"), list(names))
    dump(os.path.join(BP, "texts", "languages.json"), list(names))


def build():
    shutil.rmtree(BP, ignore_errors=True)
    shutil.rmtree(RP, ignore_errors=True)
    os.makedirs(BP)
    os.makedirs(RP)
    picture = art.ignis_screen()
    manifests()
    textures(picture)
    item()
    scripts()
    ui()
    lang()
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, files in os.walk(pack):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, OUT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.2f} MB)")


if __name__ == "__main__":
    build()
