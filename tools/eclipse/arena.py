"""The Celestial Sanctuary, the Eclipse's arena: a round white floor 25 blocks in
radius with a black sun in the middle (the altar), rings of glowstone, twelve quartz
columns with end rods, four black obelisks crowned with amethyst and fragments of
stone floating overhead. The floor is at y = FLOOR; the part below sinks into the ground.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcstructure import Structure  # noqa: E402

N, H, FLOOR = 61, 34, 5
C = N // 2


class Builder:
    def __init__(self):
        self.s = Structure((N, H, N))
        self.rng = random.Random(7)

    def put(self, x, y, z, name, states=None):
        if 0 <= x < N and 0 <= y < H and 0 <= z < N:
            self.s.set(x, y, z, name, states or {})

    def cells(self, r0, r1):
        for x in range(N):
            for z in range(N):
                d = math.hypot(x - C, z - C)
                if r0 <= d < r1:
                    yield x, z, d


def floor_block(x, z, d):
    """The pattern of the floor (y = FLOOR - 1)."""
    a = math.degrees(math.atan2(z - C, x - C)) % 360
    if d < 3.5:
        return "minecraft:black_concrete"                       # the dark sun
    if d < 4.6:
        return "minecraft:glowstone"                            # its corona
    if 11.5 <= d < 12.5 or 21.5 <= d < 22.5:
        return "minecraft:glowstone"                            # rings of light
    if d >= 24:
        return "minecraft:polished_blackstone_bricks"           # the dark rim
    for k in range(8):                                          # eight black rays
        ray = k * 45
        diff = min(abs(a - ray), 360 - abs(a - ray))
        if 5 <= d < 21.5 and diff * math.pi / 180 * d < 0.6:
            return "minecraft:black_concrete"
    if 12.5 <= d < 21.5 and (int(a // 22.5) % 2 == 0):
        return "minecraft:quartz_bricks"
    return "minecraft:smooth_quartz"


def build():
    b = Builder()
    F = FLOOR
    # clear the sky above the sanctuary
    for x, z, d in b.cells(0, 30.5):
        for y in range(F, H):
            b.put(x, y, z, "minecraft:air")
    # foundation, narrowing downwards
    for x, z, d in b.cells(0, 28):
        for y in range(F - 1):
            if d < 28 - (F - 1 - y) * 0.6:
                b.put(x, y, z, "minecraft:calcite" if (x * 7 + z * 3 + y) % 5 else "minecraft:smooth_basalt")
    # the floor and the steps around it
    for x, z, d in b.cells(0, 25.5):
        b.put(x, F - 1, z, floor_block(x, z, d))
    for x, z, d in b.cells(25.5, 28):
        b.put(x, F - 1, z, "minecraft:smooth_quartz")
        if d < 26.5:
            b.put(x, F, z, "minecraft:smooth_quartz_slab", {"minecraft:vertical_half": "bottom"})
    # twelve columns on the rim
    for k in range(12):
        a = math.radians(k * 30 + 15)
        x, z = round(C + math.cos(a) * 25), round(C + math.sin(a) * 25)
        h = 7 if k % 2 else 9
        b.put(x, F - 1, z, "minecraft:chiseled_quartz_block")
        for y in range(F, F + h):
            b.put(x, y, z, "minecraft:quartz_pillar", {"pillar_axis": "y"})
        b.put(x, F + h, z, "minecraft:chiseled_quartz_block")
        b.put(x, F + h + 1, z, "minecraft:end_rod", {"facing_direction": 1})
    # four black obelisks crowned with amethyst
    for k in range(4):
        a = math.radians(k * 90)
        ox, oz = round(C + math.cos(a) * 28), round(C + math.sin(a) * 28)
        for y in range(F - 1, F + 14):
            w = 1 if y < F + 10 else 0
            for dx in range(-w, w + 1):
                for dz in range(-w, w + 1):
                    name = "minecraft:polished_blackstone_bricks"
                    if y == F + 4 and (dx == 0 or dz == 0):
                        name = "minecraft:crying_obsidian"
                    b.put(ox + dx, y, oz + dz, name)
        b.put(ox, F + 14, oz, "minecraft:amethyst_block")
        b.put(ox, F + 15, oz, "minecraft:amethyst_cluster", {"minecraft:block_face": "up"})
        for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            b.put(ox + dx, F + 9, oz + dz, "minecraft:end_rod", {"facing_direction": 1})
    # fragments floating overhead
    for k in range(7):
        a = b.rng.uniform(0, 2 * math.pi)
        r = b.rng.uniform(16, 26)
        fx, fz, fy = round(C + math.cos(a) * r), round(C + math.sin(a) * r), F + b.rng.randint(15, 22)
        size = b.rng.randint(1, 2)
        for dx in range(-size, size + 1):
            for dz in range(-size, size + 1):
                for dy in range(-1, 1):
                    if abs(dx) + abs(dz) + abs(dy) <= size + (dy == 0):
                        b.put(fx + dx, fy + dy, fz + dz, "minecraft:calcite" if dy == 0 else "minecraft:smooth_basalt")
        b.put(fx, fy + 1, fz, "minecraft:amethyst_cluster", {"minecraft:block_face": "up"})
    # the altar of the Eclipse, on the dark sun
    b.put(C, F, C, "eclipse:altar", {"eclipse:active": False})
    return b.s
