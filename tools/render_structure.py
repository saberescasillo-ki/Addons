"""Isometric preview of a .mcstructure (or a Structure), seen from the south-east.

    python3 tools/render_structure.py file.mcstructure out.png [scale]
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcstructure as m  # noqa: E402

COLORS = [  # first match wins
    ("lava", (230, 110, 20)), ("fire", (255, 160, 30)), ("magma", (170, 60, 20)), ("shroomlight", (240, 150, 60)),
    ("lantern", (250, 200, 90)), ("gold_block", (240, 200, 60)), ("gilded", (120, 95, 50)),
    ("crying", (70, 30, 120)), ("obsidian", (30, 20, 45)), ("chiseled", (60, 55, 66)),
    ("cracked", (44, 40, 48)), ("polished_blackstone_brick", (50, 46, 56)), ("polished_blackstone", (58, 54, 64)),
    ("blackstone", (40, 36, 44)), ("basalt", (80, 80, 88)), ("netherrack", (110, 50, 50)), ("chain", (70, 70, 80)),
    ("iron_bars", (120, 120, 125)), ("chest", (150, 110, 50)), ("altar", (220, 80, 30)),
    ("red_nether", (90, 20, 25)), ("nether_brick", (60, 30, 36)), ("soul_sand", (85, 65, 52)),
    ("soul_soil", (75, 58, 46)), ("soul", (90, 200, 220)), ("bone", (220, 215, 190)), ("quartz", (230, 225, 215)),
    ("netherens", (80, 200, 230)), ("crimson", (120, 30, 40)), ("warped", (30, 110, 100)),
]


def color(name):
    for key, c in COLORS:
        if key in name:
            return c
    return (150, 150, 150)


def render(structure, out, scale=4):
    if isinstance(structure, str):
        root = m.read_nbt(open(structure, "rb").read())
        size = m.plain(root["size"])
        pal = [b["name"] for b in m.plain(root["structure"]["palette"]["default"]["block_palette"])]
        idx = [t.value for t in root["structure"]["block_indices"].value[1][0].value[1]]
    else:
        size, pal, idx = structure.size, [p["name"] for p in structure.palette], structure.blocks
    sx, sy, sz = size
    skip = {"minecraft:air", "minecraft:structure_void"}

    def at(x, y, z):
        if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
            i = idx[(x * sy + y) * sz + z]
            return pal[i] if i >= 0 else None
        return None

    w = (sx + sz) * scale * 2 + 40
    h = (sx + sz) * scale + sy * scale * 2 + 40
    img = Image.new("RGB", (w, h), (22, 20, 28))
    d = ImageDraw.Draw(img)
    ox, oy = sz * scale * 2 + 20, sy * scale * 2 + 20
    for s in range(sx + sz - 1):
        for y in range(sy):
            for x in range(max(0, s - sz + 1), min(sx, s + 1)):
                z = s - x
                n = at(x, y, z)
                if not n or n in skip:
                    continue
                top_open = (at(x, y + 1, z) or "minecraft:air") in skip or "slab" in n or "stairs" in n
                e_open = (at(x + 1, y, z) or "minecraft:air") in skip
                s_open = (at(x, y, z + 1) or "minecraft:air") in skip
                if not (top_open or e_open or s_open):
                    continue
                c = color(n)
                px = ox + (x - z) * scale * 2
                py = oy + (x + z) * scale - y * scale * 2
                k = scale
                top = [(px, py - k), (px + 2 * k, py), (px, py + k), (px - 2 * k, py)]
                left = [(px - 2 * k, py), (px, py + k), (px, py + 3 * k), (px - 2 * k, py + 2 * k)]
                right = [(px + 2 * k, py), (px, py + k), (px, py + 3 * k), (px + 2 * k, py + 2 * k)]
                d.polygon(left, fill=tuple(int(v * 0.62) for v in c))
                d.polygon(right, fill=tuple(int(v * 0.8) for v in c))
                d.polygon(top, fill=c)
    img = img.crop(img.getbbox())
    img.save(out)


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 4)
