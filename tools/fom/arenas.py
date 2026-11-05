"""The two boss structures of Figures of Malice, built block by block.

  * baron_citadel(): the Black Baron's frost citadel — a round arena of deepslate
    with a blue-ice lightning sigil, a crenellated wall with oxidised-copper bands,
    six spires crowned with lightning rods, a gate and a raised throne;
  * lantern_asylum(): Dr. Lantern's pale asylum — a cloister of pale oak, mud and
    resin bricks around a lamp-lit courtyard, four towers and a clock tower,
    iron-barred cells, cobwebs, a dead pale tree and a small graveyard.

Each has its seal block (the script raises the boss's statue there) in the
middle. The floor is at y = FLOOR; the part below sinks into the ground.
"""
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcstructure import Structure, byte  # noqa: E402

FLOOR = 6
BACK = {"E": 0, "W": 1, "S": 2, "N": 3}       # stair's tall side -> weirdo_direction
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


class Builder:
    def __init__(self, n, h, seed):
        self.n, self.h = n, h
        self.c = n // 2
        self.s = Structure((n, h, n))
        self.rng = random.Random(seed)

    def put(self, x, y, z, name, states=None):
        if 0 <= x < self.n and 0 <= y < self.h and 0 <= z < self.n:
            self.s.set(x, y, z, name, states or {})

    def stair(self, x, y, z, back, name, upside=False):
        self.put(x, y, z, name, {"weirdo_direction": BACK[back], "upside_down_bit": byte(upside)})

    def slab(self, x, y, z, name, top=False):
        self.put(x, y, z, name, {"minecraft:vertical_half": "top" if top else "bottom"})

    def pillar(self, x, y, z, name, axis="y"):
        self.put(x, y, z, name, {"pillar_axis": axis})

    def lantern(self, x, y, z, chain, name="minecraft:lantern"):
        for i in range(chain):
            self.pillar(x, y - i, z, "minecraft:chain")
        self.put(x, y - chain, z, name, {"hanging": byte(1)})

    def ring(self, r0, r1):
        """Cells whose distance from the centre is in [r0, r1)."""
        c = self.c
        for x in range(self.n):
            for z in range(self.n):
                d = math.hypot(x - c, z - c)
                if r0 <= d < r1:
                    yield x, z, d

    def clear_above(self, r, y0):
        for x, z, _ in self.ring(0, r):
            for y in range(y0, self.h):
                self.put(x, y, z, "minecraft:air")

    def facing(self, x, z):
        """The side of (x, z) that faces away from the centre."""
        dx, dz = x - self.c, z - self.c
        if abs(dx) > abs(dz):
            return "E" if dx > 0 else "W"
        return "S" if dz > 0 else "N"


# --- the Black Baron ---------------------------------------------------------------------
def baron_citadel():
    b = Builder(61, 40, 11)
    c, F = b.c, FLOOR
    WALL_R, ARENA_R = 26, 18
    b.clear_above(31, F + 1)
    # foundation: cobbled deepslate with packed-ice veins, sunk under the floor
    for x, z, d in b.ring(0, 30.5):
        for y in range(F):
            vein = (x * 7 + z * 3 + y) % 23 == 0
            b.put(x, y, z, "minecraft:packed_ice" if vein else "minecraft:cobbled_deepslate")
    # floor: arena with the lightning sigil, terrace of bricks and snow
    for x, z, d in b.ring(0, 30.5):
        a = math.degrees(math.atan2(z - c, x - c)) % 360
        if d < ARENA_R:
            block = "minecraft:polished_deepslate"
            if int(d) % 6 == 0:
                block = "minecraft:deepslate_tiles"
            spoke = min((a % 45), 45 - (a % 45))
            zig = abs(((d * 1.3) % 4) - 2)            # zig-zag bolts along 8 spokes
            if 4 < d < ARENA_R - 2 and abs(spoke - zig * 2.2) < 1.4:
                block = "minecraft:blue_ice"
            if abs(d - (ARENA_R - 1.5)) < 0.6:
                block = "minecraft:packed_ice"
            if d < 2.5:
                block = "minecraft:chiseled_deepslate"
        else:
            block = "minecraft:deepslate_bricks" if (x + z) % 3 else "minecraft:cracked_deepslate_bricks"
        b.put(x, F, z, block)
        if ARENA_R + 1 < d < WALL_R - 1 and b.rng.random() < 0.35:
            b.put(x, F + 1, z, "minecraft:snow_layer", {"height": b.rng.randint(0, 2), "covered_bit": byte(0)})
    # wall with crenellations and a copper band
    for x, z, d in b.ring(WALL_R, WALL_R + 2):
        a = math.degrees(math.atan2(z - c, x - c)) % 360
        gate = abs(a - 90) < 9  # south
        for y in range(F + 1, F + 10):
            if gate and y < F + 8:
                continue
            block = "minecraft:deepslate_bricks"
            if y == F + 4:
                block = "minecraft:waxed_oxidized_cut_copper"
            elif y == F + 9:
                block = "minecraft:polished_blackstone_bricks"
            b.put(x, y, z, block)
        if not gate and int(a) % 6 < 3:
            b.put(x, F + 10, z, "minecraft:deepslate_brick_wall")
        if gate:
            b.put(x, F + 7, z, "minecraft:iron_bars")  # portcullis
    # six spires with lightning rods
    for i in range(6):
        ang = math.radians(30 + i * 60)
        tx, tz = c + round(math.cos(ang) * (WALL_R + 1)), c + round(math.sin(ang) * (WALL_R + 1))
        top = F + 22
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                r = math.hypot(dx, dz)
                if r > 3.2:
                    continue
                for y in range(F - 2, top):
                    edge = r > 2.2
                    if edge:
                        block = "minecraft:waxed_oxidized_cut_copper" if y in (F + 4, F + 14) else "minecraft:polished_blackstone_bricks"
                        if y % 5 == 2 and abs(dx) + abs(dz) == 3 and y > F + 2:
                            block = "minecraft:iron_bars"  # arrow slits
                        b.put(tx + dx, y, tz + dz, block)
                    elif y > F:
                        b.put(tx + dx, y, tz + dz, "minecraft:air")
                    else:
                        b.put(tx + dx, y, tz + dz, "minecraft:polished_blackstone")
        # cone roof of deepslate tiles, then the rod
        for k, rr in enumerate((3.4, 2.6, 1.8, 1.0)):
            for dx in range(-4, 5):
                for dz in range(-4, 5):
                    r = math.hypot(dx, dz)
                    if rr - 0.9 <= r <= rr:
                        side = "E" if dx > 0 and abs(dx) >= abs(dz) else "W" if dx < 0 and abs(dx) >= abs(dz) else "S" if dz > 0 else "N"
                        b.stair(tx + dx, top + k, tz + dz, OPP[side], "minecraft:deepslate_tile_stairs")
                    elif r < rr - 0.9:
                        b.put(tx + dx, top + k, tz + dz, "minecraft:deepslate_tiles")
        b.put(tx, top + 4, tz, "minecraft:waxed_copper")
        b.put(tx, top + 5, tz, "minecraft:lightning_rod", {"facing_direction": 1, "powered_bit": byte(0)})
        b.lantern(tx, top - 1, tz, 3, "minecraft:soul_lantern")
    # gate towers' braziers and the gate path
    for gx in (c - 6, c + 6):
        b.put(gx, F + 1, c + WALL_R + 2, "minecraft:polished_blackstone")
        b.put(gx, F + 2, c + WALL_R + 2, "minecraft:soul_campfire", {"extinguished": byte(0), "direction": 0})
    for z in range(c + ARENA_R, c + WALL_R + 3):
        for x in range(c - 3, c + 4):
            b.put(x, F, z, "minecraft:polished_deepslate" if abs(x - c) < 3 else "minecraft:deepslate_tiles")
    # the throne on its dais (north)
    tz = c - WALL_R + 4
    for step in range(4):
        for x in range(c - 6 + step, c + 7 - step):
            for z in range(tz - 2, tz + 4 - step):
                b.put(x, F + 1 + step, z, "minecraft:polished_blackstone")
            b.stair(x, F + 1 + step, tz + 4 - step, "N", "minecraft:polished_blackstone_brick_stairs")
    seat = F + 5
    b.put(c, seat, tz, "minecraft:chiseled_polished_blackstone")
    for y in range(seat + 1, seat + 7):
        b.put(c, y, tz - 1, "minecraft:polished_blackstone_bricks" if y < seat + 6 else "minecraft:waxed_copper")
    for dx in (-1, 1):
        b.stair(c + dx, seat, tz, "E" if dx > 0 else "W", "minecraft:polished_blackstone_brick_stairs")
        b.put(c + dx, seat + 1, tz - 1, "minecraft:polished_blackstone_bricks")
        b.put(c + dx * 2, seat + 3, tz - 1, "minecraft:lightning_rod", {"facing_direction": 1, "powered_bit": byte(0)})
    for dx in (-5, 5):
        b.put(c + dx, F + 2, tz, "minecraft:soul_campfire", {"extinguished": byte(0), "direction": 0})
    # obelisks around the arena with frozen light
    for i in range(8):
        ang = math.radians(i * 45 + 22.5)
        ox, oz = c + round(math.cos(ang) * (ARENA_R + 3)), c + round(math.sin(ang) * (ARENA_R + 3))
        for y in range(F + 1, F + 6):
            b.put(ox, y, oz, "minecraft:polished_blackstone_bricks" if y < F + 5 else "minecraft:pearlescent_froglight", {"pillar_axis": "y"} if y == F + 5 else None)
        b.put(ox, F + 6, oz, "minecraft:lightning_rod", {"facing_direction": 1, "powered_bit": byte(0)})
    # soul lanterns hanging from the wall top, facing in
    for i in range(16):
        ang = math.radians(i * 22.5 + 11.25)
        lx, lz = c + round(math.cos(ang) * (WALL_R - 1)), c + round(math.sin(ang) * (WALL_R - 1))
        if abs(math.degrees(ang) % 360 - 90) < 12:
            continue
        b.put(lx, F + 9, lz, "minecraft:deepslate_brick_slab", {"minecraft:vertical_half": "top"})
        b.lantern(lx, F + 8, lz, 2, "minecraft:soul_lantern")
    # the seal on its plinth
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            b.put(c + dx, F, c + dz, "minecraft:chiseled_deepslate")
    b.put(c, F, c, "xrworks:baron_seal", {"xrworks:used": byte(0)})
    return b.s, (c, F, c)


# --- Dr. Lantern -----------------------------------------------------------------------------------
def lantern_asylum():
    b = Builder(61, 36, 23)
    c, F = b.c, FLOOR
    half = 29           # outer half-size of the building ring
    yard = 17           # courtyard half-size
    b.clear_above(42, F + 1)
    for x in range(b.n):
        for z in range(b.n):
            for y in range(F):
                b.put(x, y, z, "minecraft:mud_bricks" if (x + y + z) % 4 else "minecraft:tuff")
    # courtyard floor: tuff paving, a lantern-eye mosaic of resin and pale oak
    for x in range(c - half, c + half + 1):
        for z in range(c - half, c + half + 1):
            d = math.hypot(x - c, z - c)
            block = "minecraft:polished_tuff" if (x + z) % 2 else "minecraft:tuff_bricks"
            if d < 9:
                block = "minecraft:pale_oak_planks"
                if abs(d - 7.5) < 0.7 or abs(d - 4) < 0.6:
                    block = "minecraft:resin_bricks"
                if d < 1.5:
                    block = "minecraft:chiseled_resin_bricks"
            elif abs(x - c) <= 1 or abs(z - c) <= 1:
                block = "minecraft:mud_bricks"
            b.put(x, F, z, block)
            if 10 < d < yard - 1 and b.rng.random() < 0.06:
                b.put(x, F, z, "minecraft:pale_moss_block")
                b.put(x, F + 1, z, "minecraft:open_eyeblossom" if b.rng.random() < 0.5 else "minecraft:closed_eyeblossom")
    # the cloister: four two-storey wings around the yard
    def wing_cell(x, z):
        return yard < max(abs(x - c), abs(z - c)) <= half
    for x in range(c - half, c + half + 1):
        for z in range(c - half, c + half + 1):
            if not wing_cell(x, z):
                continue
            m = max(abs(x - c), abs(z - c))
            outer, inner = m == half, m == yard + 1
            for y in range(F + 1, F + 11):
                if outer or inner:
                    frame = (x + z) % 4 == 0 or y in (F + 1, F + 5, F + 10)
                    if frame:
                        block = "minecraft:stripped_pale_oak_log" if y not in (F + 5, F + 10) else "minecraft:pale_oak_planks"
                    else:
                        block = "minecraft:mud_bricks" if y <= F + 2 else "minecraft:pale_oak_planks"
                    window = y in (F + 3, F + 7) and (x + z) % 4 == 2
                    if window:
                        block = "minecraft:iron_bars"
                    door = inner and y <= F + 3 and (abs(x - c) <= 1 or abs(z - c) <= 1)
                    gate = outer and z == c + half and abs(x - c) <= 2 and y <= F + 5
                    if door or gate:
                        block = "minecraft:air"
                    b.put(x, y, z, block, {"pillar_axis": "y"} if "log" in block else None)
                elif y == F + 5:
                    b.put(x, y, z, "minecraft:pale_oak_planks")            # upper floor
                elif y in (F + 4, F + 9) and b.rng.random() < 0.05:
                    b.put(x, y, z, "minecraft:cobweb")
            # gabled roof over the wing, broken in places
            depth = min(m - yard - 1, half - m)
            ry = F + 11 + depth
            if b.rng.random() > 0.07:
                if depth == (half - yard - 1) // 2:
                    b.put(x, ry, z, "minecraft:pale_oak_slab", {"minecraft:vertical_half": "bottom"})
                else:
                    side = b.facing(x, z) if m - yard - 1 < half - m else OPP[b.facing(x, z)]
                    b.stair(x, ry, z, OPP[side], "minecraft:pale_oak_stairs")
            if b.rng.random() < 0.08:
                b.put(x, ry - 1, z, "minecraft:pale_hanging_moss", {"tip": byte(1)})
    # hanging lanterns along both corridors and over the yard doors
    for k in range(-half + 3, half - 2, 4):
        for (x, z) in ((c + k, c - half + 2), (c + k, c + half - 2), (c - half + 2, c + k), (c + half - 2, c + k)):
            b.lantern(x, F + 4, z, 1)
            b.lantern(x, F + 9, z, 1)
    # cells: iron bars on the inner corridor side of the west and east wings
    for z in range(c - yard + 2, c + yard - 1, 4):
        for x in (c - half + 4, c + half - 4):
            for y in range(F + 1, F + 4):
                b.put(x, y, z, "minecraft:iron_bars")
                b.put(x, y, z + 1, "minecraft:iron_bars")
    # four corner towers, the north-west one a clock tower with a great lantern
    for i, (sx, sz) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        tx, tz = c + sx * (half - 3), c + sz * (half - 3)  # the 7x7 tower fits on the corner
        top = F + (24 if i == 0 else 17)
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                edge = max(abs(dx), abs(dz)) == 3
                for y in range(F + 1, top):
                    if edge:
                        corner = abs(dx) == 3 and abs(dz) == 3
                        block = "minecraft:stripped_pale_oak_log" if corner else "minecraft:mud_bricks"
                        if y % 4 == 3 and not corner and (dx == 0 or dz == 0):
                            block = "minecraft:iron_bars"
                        b.put(tx + dx, y, tz + dz, block, {"pillar_axis": "y"} if corner else None)
                    else:
                        b.put(tx + dx, y, tz + dz, "minecraft:air")
        for k in range(4):  # pyramid roof
            r = 4 - k
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if max(abs(dx), abs(dz)) == r:
                        side = "E" if dx == r else "W" if dx == -r else "S" if dz == r else "N"
                        b.stair(tx + dx, top + k, tz + dz, OPP[side], "minecraft:pale_oak_stairs")
                    else:
                        b.put(tx + dx, top + k, tz + dz, "minecraft:pale_oak_planks")
        if i == 0:
            for dx, dz in ((0, 3), (3, 0), (0, -3), (-3, 0)):
                b.put(tx + dx, top - 3, tz + dz, "minecraft:ochre_froglight", {"pillar_axis": "y"})  # clock faces
            b.lantern(tx, top + 3, tz, 0)
        b.lantern(tx, top - 1, tz, 2)
    # lamp posts around the yard
    for k in range(12):
        a = math.radians(k * 30 + 15)
        lx, lz = c + round(math.cos(a) * 13), c + round(math.sin(a) * 13)
        for y in range(F + 1, F + 5):
            b.put(lx, y, lz, "minecraft:pale_oak_fence")
        b.put(lx, F + 5, lz, "minecraft:lantern", {"hanging": byte(0)})
    # the dead pale tree with hanging moss
    tx, tz = c - 10, c + 9
    for y in range(F + 1, F + 9):
        b.pillar(tx, y, tz, "minecraft:pale_oak_log")
    for dx, dz, h in ((1, 0, 7), (-1, 0, 6), (0, 1, 8), (0, -1, 5), (2, 1, 8), (-2, -1, 6)):
        b.pillar(tx + dx, F + h, tz + dz, "minecraft:pale_oak_log", "x" if dx else "z")
        b.put(tx + dx, F + h - 1, tz + dz, "minecraft:pale_hanging_moss", {"tip": byte(1)})
    # the graveyard (north-east of the yard)
    for gx in range(c + 6, c + 15, 3):
        for gz in range(c - 15, c - 6, 3):
            b.put(gx, F + 1, gz, "minecraft:mossy_stone_brick_wall")
            b.put(gx, F + 2, gz, "minecraft:stone_brick_slab", {"minecraft:vertical_half": "bottom"})
            b.put(gx, F, gz + 1, "minecraft:pale_moss_block")
            if b.rng.random() < 0.6:
                b.put(gx, F + 1, gz + 1, "minecraft:closed_eyeblossom")
    # the operating table with the seal
    for dx in range(-2, 3):
        for dz in range(-1, 2):
            b.slab(c + dx, F + 1, c + dz, "minecraft:resin_brick_slab", top=True)
    for dx in (-2, 2):
        for dz in (-1, 1):
            b.put(c + dx, F + 1, c + dz, "minecraft:resin_brick_wall")
    b.put(c, F + 1, c, "xrworks:lantern_seal", {"xrworks:used": byte(0)})
    for dx, dz in ((-3, 0), (3, 0), (0, -2), (0, 2)):
        b.put(c + dx, F + 1, c + dz, "minecraft:candle", {"candles": 2, "lit": byte(1)})
    return b.s, (c, F + 1, c)


if __name__ == "__main__":
    for name, fn in (("baron_citadel", baron_citadel), ("lantern_asylum", lantern_asylum)):
        s, seal = fn()
        s.save(os.path.join(sys.argv[1] if len(sys.argv) > 1 else '.', f'{name}.mcstructure'))
        print(name, s.size, "seal", seal)
