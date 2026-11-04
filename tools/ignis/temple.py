"""The Temple of Ignis: a huge polished-blackstone temple around the Altar of
Fire. Generated block by block (97 x 44 x 97); relief from stairs and slabs.

Layout, from the outside in: a three-step plinth, a curtain wall with
buttresses, cornices and battlements, four octagonal towers with stepped
roofs and fire braziers, a south gate, a cloister of 16 columns, a lava moat
with four bridges, the arena, and the stepped dais with the altar in the
middle. A shrine against the north wall keeps two chests (Burning Ashes).
"""
import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcstructure import Structure, AIR, byte, int_, Tag, LIST, COMPOUND  # noqa: E402

N = 97                 # footprint
C = N // 2             # centre (48)
H = 44                 # height
FOUND = 6              # foundation layers
F = FOUND + 3          # courtyard floor level (after a 3-step plinth)

# Materials
BRICK = "minecraft:polished_blackstone_bricks"
CRACKED = "minecraft:cracked_polished_blackstone_bricks"
CHISELED = "minecraft:chiseled_polished_blackstone"
GILDED = "minecraft:gilded_blackstone"
POLISHED = "minecraft:polished_blackstone"
BLACKSTONE = "minecraft:blackstone"
BASALT = "minecraft:polished_basalt"
GOLD = "minecraft:gold_block"
MAGMA = "minecraft:magma"
SHROOM = "minecraft:shroomlight"
CRYING = "minecraft:crying_obsidian"
OBSIDIAN = "minecraft:obsidian"
NETHERRACK = "minecraft:netherrack"
LAVA = "minecraft:lava"
B_STAIRS = "minecraft:polished_blackstone_brick_stairs"
B_SLAB = "minecraft:polished_blackstone_brick_slab"
B_WALL = "minecraft:polished_blackstone_brick_wall"
P_STAIRS = "minecraft:polished_blackstone_stairs"
P_SLAB = "minecraft:polished_blackstone_slab"
CHAIN = "minecraft:chain"
LANTERN = "minecraft:lantern"
BARS = "minecraft:iron_bars"
FIRE = "minecraft:fire"
ALTAR = "ignis:altar_of_fire"
CHEST = "minecraft:chest"

# Direction of a stair's tall back side -> weirdo_direction (Bedrock).
BACK = {"E": 0, "W": 1, "S": 2, "N": 3}
VEC = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


class Temple:
    def __init__(self, seed=7):
        self.s = Structure((N, H, N))
        self.rng = random.Random(seed)

    # --- primitives
    def put(self, x, y, z, name, states=None, **kw):
        self.s.set(x, y, z, name, states, **kw)

    def brick(self, x, y, z, cracked=0.12):
        self.put(x, y, z, CRACKED if self.rng.random() < cracked else BRICK)

    def stair(self, x, y, z, back, upside=False, name=B_STAIRS):
        self.put(x, y, z, name, {"weirdo_direction": BACK[back], "upside_down_bit": byte(upside)})

    def slab(self, x, y, z, top=False, name=B_SLAB):
        self.put(x, y, z, name, {"minecraft:vertical_half": "top" if top else "bottom"})

    def air_box(self, x0, y0, z0, x1, y1, z1):
        self.s.fill(x0, y0, z0, x1, y1, z1, AIR)

    def basalt(self, x, y, z):
        self.put(x, y, z, BASALT, {"pillar_axis": "y"})

    def lantern(self, x, y, z, chain=2):
        for i in range(chain):
            self.put(x, y - i, z, CHAIN, {"pillar_axis": "y"})
        self.put(x, y - chain, z, LANTERN, {"hanging": byte(1)})

    def brazier(self, x, y, z):
        """A gold-rimmed fire bowl standing on (x, y-1, z)."""
        self.put(x, y, z, NETHERRACK)
        self.put(x, y + 1, z, FIRE, {"age": 0})
        for d, (dx, dz) in VEC.items():
            self.stair(x + dx, y, z + dz, OPP[d], name=P_STAIRS)

    # --- parts
    def plinth(self):
        """Foundation and three steps; each step's edge is a stair (relief)."""
        for x in range(N):
            for z in range(N):
                for y in range(FOUND):
                    self.put(x, y, z, BLACKSTONE if y < FOUND - 1 else POLISHED)
        for step in range(3):
            r = C - step * 2           # half-size of this step
            y = FOUND + step
            for x in range(C - r, C + r + 1):
                for z in range(C - r, C + r + 1):
                    edge = max(abs(x - C), abs(z - C))
                    if edge == r:
                        side = self._side(x, z)
                        if abs(x - C) == abs(z - C):
                            self.put(x, y, z, CHISELED)
                        else:
                            self.stair(x, y, z, OPP[side])
                    else:
                        self.put(x, y, z, POLISHED if step < 2 else BRICK)
            # an air band above each step so the terrain does not bury it
            for x in range(C - r, C + r + 1):
                for z in range(C - r, C + r + 1):
                    if max(abs(x - C), abs(z - C)) >= r - 1:
                        for yy in range(y + 1, y + 6):
                            if self.s.get(x, yy, z) in (None, "minecraft:structure_void"):
                                self.put(x, yy, z, AIR)

    def _side(self, x, z):
        dx, dz = x - C, z - C
        if abs(dx) >= abs(dz):
            return "E" if dx > 0 else "W"
        return "S" if dz > 0 else "N"

    def courtyard(self):
        """Clears the inside of the walls and lays the patterned floor."""
        r = 40
        self.air_box(C - r, F, C - r, C + r, H - 1, C + r)
        for x in range(C - r, C + r + 1):
            for z in range(C - r, C + r + 1):
                d = math.hypot(x - C, z - C)
                ang = math.degrees(math.atan2(z - C, x - C)) % 45
                if d > 29 and (ang < 1.6 or ang > 43.4):
                    self.put(x, F - 1, z, MAGMA)          # eight glowing rays
                elif abs(d - 33) < 0.6:
                    self.put(x, F - 1, z, GILDED)
                elif (x + z) % 2 == 0:
                    self.put(x, F - 1, z, POLISHED)
                else:
                    self.put(x, F - 1, z, BRICK if self.rng.random() > 0.08 else CRACKED)
                self.put(x, F - 2, z, BLACKSTONE)
        # hidden lights under the floor
        for x in range(C - r + 3, C + r - 2, 6):
            for z in range(C - r + 3, C + r - 2, 6):
                if math.hypot(x - C, z - C) > 29:
                    self.put(x, F - 2, z, SHROOM)

    def moat(self):
        """Lava ring (radius 26-28) two deep, with four bridges."""
        for x in range(C - 29, C + 30):
            for z in range(C - 29, C + 30):
                d = math.hypot(x - C, z - C)
                if 25.5 <= d < 28.5:
                    bridge = min(abs(x - C), abs(z - C)) <= 2
                    if bridge:
                        self.put(x, F - 1, z, CHISELED if min(abs(x - C), abs(z - C)) == 0 else BRICK)
                        self.put(x, F - 2, z, BRICK)
                        self.put(x, F - 3, z, BRICK)
                        if min(abs(x - C), abs(z - C)) == 2:   # railings
                            self.put(x, F, z, B_WALL)
                    else:
                        self.put(x, F - 1, z, LAVA)
                        self.put(x, F - 2, z, LAVA)
                        self.put(x, F - 3, z, BLACKSTONE)
                elif 24.5 <= d < 25.5 or 28.5 <= d < 29.5:
                    # rims of the moat: slabs on bricks (a low lip)
                    self.put(x, F - 1, z, CHISELED if self.rng.random() < 0.2 else BRICK)
                    self.put(x, F - 2, z, BRICK)
                    self.put(x, F - 3, z, BRICK)
                    if min(abs(x - C), abs(z - C)) > 2:
                        self.slab(x, F, z)

    def arena(self):
        for x in range(C - 25, C + 26):
            for z in range(C - 25, C + 26):
                d = math.hypot(x - C, z - C)
                if d >= 24.5:
                    continue
                if abs(d - 12) < 0.55 or abs(d - 20) < 0.55:
                    block = CHISELED
                elif abs(d - 16) < 0.55:
                    block = GILDED
                elif int(d) % 4 == 0:
                    block = POLISHED
                else:
                    block = BRICK if self.rng.random() > 0.1 else CRACKED
                self.put(x, F - 1, z, block)

    def dais(self):
        """Stepped round dais with the Altar of Fire on top."""
        steps = [(8, 0), (6, 1), (4, 2), (2.6, 3)]
        for radius, h in steps:
            y = F + h
            for x in range(C - 9, C + 10):
                for z in range(C - 9, C + 10):
                    d = math.hypot(x - C, z - C)
                    if d > radius + 0.5:
                        continue
                    outer = d > radius - 0.5
                    if outer and h < 3:
                        side = self._side(x, z)
                        self.stair(x, y, z, OPP[side])
                    else:
                        self.put(x, y, z, CRYING if h == 3 and outer else (CHISELED if h == 2 else BRICK))
        top = F + 4
        self.put(C, top - 1, C, GOLD)
        self.put(C, top, C, ALTAR, {"ignis:start": byte(0)})
        for dx, dz in ((3, 3), (-3, 3), (3, -3), (-3, -3)):
            x, z = C + dx, C + dz
            self.put(x, F + 3, z, GILDED)
            self.put(x, F + 4, z, B_WALL)
            self.brazier(x, F + 5, z)
        # four obelisks around the dais
        for dx, dz in ((10, 10), (-10, 10), (10, -10), (-10, -10)):
            self.obelisk(C + dx, F, C + dz)

    def obelisk(self, x, y, z):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                side = "E" if dx > 0 else "W" if dx < 0 else ("S" if dz > 0 else "N")
                if dx == 0 and dz == 0:
                    self.put(x, y, z, CHISELED)
                elif dx != 0 and dz != 0:
                    self.slab(x + dx, y, z + dz)
                else:
                    self.stair(x + dx, y, z + dz, OPP[side])
        for i in range(1, 9):
            self.put(x, y + i, z, CHISELED if i % 3 == 0 else BRICK)
        self.put(x, y + 9, z, GILDED)
        self.put(x, y + 10, z, GOLD)
        for d, (dx, dz) in VEC.items():
            self.stair(x + dx, y + 8, z + dz, OPP[d], upside=True)
            self.slab(x + dx, y + 9, z + dz, name=P_SLAB)

    def cloister(self):
        """16 columns on a ring (radius 32) under a covered walkway."""
        cols = 16
        ring_r = 32
        top = F + 10
        # roof ring between radius 30.5 and 34.5
        for x in range(C - 36, C + 37):
            for z in range(C - 36, C + 37):
                d = math.hypot(x - C, z - C)
                if 30.5 <= d < 34.5:
                    self.put(x, top, z, BRICK)
                    self.put(x, top + 1, z, POLISHED)
                    inner = d < 31.5
                    outer = d >= 33.5
                    if inner or outer:
                        side = self._side(x, z)
                        # cornices: upside-down stairs under the roof edge, slabs on top
                        self.stair(x, top - 1, z, side if inner else OPP[side], upside=True)
                        self.slab(x, top + 2, z, name=P_SLAB)
        for i in range(cols):
            a = 2 * math.pi * i / cols
            x = C + round(ring_r * math.cos(a))
            z = C + round(ring_r * math.sin(a))
            self.column(x, z, top)
            # lantern hanging between this column and the next
            a2 = 2 * math.pi * (i + 0.5) / cols
            self.lantern(C + round(ring_r * math.cos(a2)), top - 1, C + round(ring_r * math.sin(a2)), chain=2)

    def column(self, x, z, top):
        for d, (dx, dz) in VEC.items():
            self.stair(x + dx, F, z + dz, OPP[d])                 # base flare
            self.stair(x + dx, top - 1, z + dz, OPP[d], upside=True)  # capital
        self.put(x, F, z, CHISELED)
        for y in range(F + 1, top - 1):
            self.basalt(x, y, z)
        self.put(x, top - 1, z, GILDED)

    def walls(self):
        """Curtain wall (radius 40-41) with buttresses, cornices and battlements."""
        r_in, r_out = 40, 41
        top = F + 12
        for x in range(C - r_out, C + r_out + 1):
            for z in range(C - r_out, C + r_out + 1):
                m = max(abs(x - C), abs(z - C))
                if not r_in <= m <= r_out:
                    continue
                for y in range(F - 1, top):
                    if y == F + 6:
                        self.put(x, y, z, CHISELED)
                    else:
                        self.brick(x, y, z)
                side = self._side(x, z)
                along = abs(z - C) if side in "EW" else abs(x - C)
                if m == r_out:
                    # cornice band halfway up and under the battlements
                    ox, oz = VEC[side]
                    self.stair(x + ox, F + 6, z + oz, OPP[side], upside=True)
                    self.stair(x + ox, top - 1, z + oz, OPP[side], upside=True)
                    # battlements: merlon / slab
                    if along % 3 == 0:
                        self.brick(x, top, z)
                        self.put(x, top + 1, z, P_SLAB, {"minecraft:vertical_half": "bottom"})
                    else:
                        self.slab(x, top, z)
                    # buttresses every 8 blocks
                    if along % 8 == 4 and along < r_in - 6:
                        self.buttress(x, z, side, top)
                    # arrow slits
                    elif along % 8 == 0 and along < r_in - 6:
                        for y in (F + 2, F + 3, F + 8, F + 9):
                            self.put(x, y, z, BARS)
                            ix, iz = -ox, -oz
                            self.put(x + ix, y, z + iz, BARS)
                else:
                    # wall walk with slabs and lanterns inside
                    ox, oz = VEC[side]
                    self.slab(x - ox, top - 1, z - oz, top=True)
                    if along % 8 == 2 and along < r_in - 6:
                        self.lantern(x - ox, top - 2, z - oz, chain=1)

    def buttress(self, x, z, side, top):
        ox, oz = VEC[side]
        px, pz = (0, 1) if side in "EW" else (1, 0)
        for w in (0, 1):
            bx, bz = x + ox + px * w, z + oz + pz * w
            for y in range(F - 1, top - 3):
                self.brick(bx, y, bz)
            self.stair(bx, top - 3, bz, OPP[side])
            cx, cz = bx + ox, bz + oz
            for y in range(F - 1, F + 4):
                self.brick(cx, y, cz)
            self.stair(cx, F + 4, cz, OPP[side])
            self.slab(cx, F + 5, cz, name=P_SLAB)

    def tower(self, cx, cz):
        """Octagonal tower, radius 6, with a stepped roof and a brazier."""
        r = 6
        top = F + 22
        for x in range(cx - r - 2, cx + r + 3):
            for z in range(cz - r - 2, cz + r + 3):
                dx, dz = abs(x - cx), abs(z - cz)
                oct_d = max(dx, dz, (dx + dz) * 0.72)
                if oct_d > r + 0.4:
                    continue
                shell = oct_d > r - 1.1
                for y in range(F - 1, top):
                    if shell:
                        if y in (F + 7, F + 15):
                            self.put(x, y, z, CHISELED)
                        elif y in (F + 11, F + 12) and (dx == 0 or dz == 0):
                            self.put(x, y, z, BARS)
                        else:
                            self.brick(x, y, z)
                    else:
                        self.put(x, y, z, AIR if y >= F else BRICK)
                if shell:
                    side = "E" if x - cx > 0 else "W"
                    if dz > dx:
                        side = "S" if z - cz > 0 else "N"
                    ox, oz = VEC[side]
                    if self.s.get(x + ox, top - 1, z + oz) in (None, "minecraft:structure_void", AIR):
                        self.stair(x + ox, top - 1, z + oz, OPP[side], upside=True)
                        self.stair(x + ox, F + 7, z + oz, OPP[side], upside=True)
        # floors inside
        for y in (F + 7, F + 15):
            for x in range(cx - r + 1, cx + r):
                for z in range(cz - r + 1, cz + r):
                    dx, dz = abs(x - cx), abs(z - cz)
                    if max(dx, dz, (dx + dz) * 0.72) <= r - 1.1:
                        self.slab(x, y, z, top=True)
            self.lantern(cx, y - 1, cz, chain=1)
        # stepped roof
        for level in range(0, r + 1):
            rr = r - level + 0.4
            y = top + level
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    dx, dz = abs(x - cx), abs(z - cz)
                    oct_d = max(dx, dz, (dx + dz) * 0.72)
                    if oct_d > rr:
                        continue
                    if oct_d > rr - 1:
                        side = "E" if x - cx > 0 else "W"
                        if dz > dx:
                            side = "S" if z - cz > 0 else "N"
                        self.stair(x, y, z, OPP[side])
                    else:
                        self.put(x, y, z, BRICK)
        spire = top + r + 1
        self.put(cx, spire - 1, cz, GILDED)
        self.brazier(cx, spire, cz)
        self.put(cx, spire + 2, cz, AIR)

    def gate(self):
        """South gate: 7 wide, 9 high, arch of upside-down stairs and a gold crest."""
        z_out = C + 41
        for x in range(C - 3, C + 4):
            for z in range(C + 39, C + 43):
                for y in range(F, F + 9):
                    self.put(x, y, z, AIR)
        for z in range(C + 39, C + 43):
            for x in (C - 3, C + 3):
                self.stair(x, F + 8, z, "W" if x < C else "E", upside=True)
            for x in (C - 2, C + 2):
                self.stair(x, F + 9, z, "W" if x < C else "E", upside=True)
        for x in range(C - 4, C + 5):
            self.put(x, F + 10, z_out + 1, CHISELED)
            self.stair(x, F + 11, z_out + 1, "N", upside=True)
        for x in range(C - 1, C + 2):
            self.put(x, F + 12, z_out, GILDED)
        self.put(C, F + 13, z_out, GOLD)
        for x in (C - 5, C + 5):  # gate towers' braziers
            self.put(x, F + 12, z_out + 1, BRICK)
            self.brazier(x, F + 13, z_out + 1)
        # grand stair down the plinth in front of the gate
        for i, y in enumerate((F - 1, F - 2, F - 3)):
            for x in range(C - 4, C + 5):
                self.stair(x, y, C + 42 + i, "N")
                for yy in range(FOUND, y):
                    self.put(x, yy, C + 42 + i, BRICK)
        for x in range(C - 4, C + 5):
            self.put(x, F - 1, C + 41, CHISELED if x == C else BRICK)

    def shrine(self):
        """Back shrine on the north side: canopy, braziers and two chests."""
        z0 = C - 39
        for x in range(C - 6, C + 7):
            for z in range(z0, z0 + 6):
                self.put(x, F, z, BRICK if (x + z) % 2 else POLISHED)
            self.stair(x, F, z0 + 6, "N")
        for x in (C - 6, C + 6):
            for z in (z0, z0 + 5):
                for y in range(F + 1, F + 8):
                    self.basalt(x, y, z)
        for x in range(C - 7, C + 8):
            for z in range(z0 - 1, z0 + 7):
                self.put(x, F + 8, z, BRICK)
                if z == z0 + 6:
                    self.stair(x, F + 8, z, "N", upside=True)
                    self.slab(x, F + 9, z, name=P_SLAB)
        self.lantern(C, F + 7, z0 + 3, chain=2)
        for x in (C - 3, C + 3):
            self.chest(x, F + 1, z0 + 2)
        for x in (C - 5, C + 5):
            self.put(x, F + 1, z0 + 3, GILDED)
            self.brazier(x, F + 2, z0 + 3)
        self.put(C, F + 1, z0 + 1, CHISELED)
        self.put(C, F + 2, z0 + 1, GOLD)

    def chest(self, x, y, z):
        be = {"id": "Chest", "isMovable": byte(1), "Findable": byte(0),
              "LootTable": "loot_tables/ignis/chests/temple.json", "LootTableSeed": int_(0),
              "Items": Tag(LIST, (COMPOUND, [])), "x": int_(x), "y": int_(y), "z": int_(z)}
        self.put(x, y, z, CHEST, {"minecraft:cardinal_direction": "south"}, block_entity=be)

    def pedestals(self):
        """Braziers on the six magma rays that do not lead to the gate or the shrine."""
        for i in range(8):
            a = math.radians(45 * i)
            if i in (2, 6):      # south: gate, north: shrine
                continue
            x, z = C + round(37 * math.cos(a)), C + round(37 * math.sin(a))
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx or dz:
                        side = "E" if dx > 0 else "W" if dx < 0 else ("S" if dz > 0 else "N")
                        if dx and dz:
                            self.slab(x + dx, F, z + dz)
                        else:
                            self.stair(x + dx, F, z + dz, OPP[side])
            self.put(x, F, z, CHISELED)
            self.put(x, F + 1, z, BRICK)
            self.put(x, F + 2, z, GILDED)
            self.brazier(x, F + 3, z)

    def wall_stairs(self):
        """Two flights up to the wall walk, along the east and west walls."""
        top = F + 11
        for x_wall, inward in ((C + 39, -1), (C - 39, 1)):
            for i in range(top - F):
                z = C - 30 + i
                y = F + i
                for w in (0, 1):
                    x = x_wall + inward * w
                    self.stair(x, y, z, "S", name=B_STAIRS)
                    for yy in range(F, y):
                        self.brick(x, yy, z)
                    for yy in range(y + 1, y + 4):
                        self.put(x, yy, z, AIR)
            for w in (0, 1):  # landing
                self.slab(x_wall + inward * w, top - 1, C - 30 + (top - F), top=True)

    def walls_states(self):
        """Connects wall blocks to their neighbours (structures load without updates)."""
        sx, sy, sz = self.s.size
        solid = lambda n: n and n not in (AIR, "minecraft:structure_void", FIRE, LANTERN, CHAIN, LAVA) \
            and "slab" not in n and "stairs" not in n
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    if self.s.get(x, y, z) != B_WALL:
                        continue
                    conn = {}
                    for name, (dx, dz) in (("east", (1, 0)), ("west", (-1, 0)), ("south", (0, 1)), ("north", (0, -1))):
                        n = self.s.get(x + dx, y, z + dz)
                        conn[name] = "short" if n == B_WALL or solid(n) else "none"
                    above = self.s.get(x, y + 1, z)
                    straight = (conn["east"] != "none" and conn["west"] != "none" and conn["north"] == conn["south"] == "none") or \
                               (conn["north"] != "none" and conn["south"] != "none" and conn["east"] == conn["west"] == "none")
                    post = not straight or (above not in (None, AIR, "minecraft:structure_void"))
                    self.put(x, y, z, B_WALL, {**{f"wall_connection_type_{k}": v for k, v in conn.items()},
                                               "wall_post_bit": byte(post)})

    def build(self):
        self.plinth()
        self.courtyard()
        self.walls()
        for cx, cz in ((C - 40, C - 40), (C + 40, C - 40), (C - 40, C + 40), (C + 40, C + 40)):
            self.tower(cx, cz)
        self.gate()
        self.moat()
        self.arena()
        self.cloister()
        self.dais()
        self.shrine()
        self.pedestals()
        self.wall_stairs()
        self.walls_states()
        return self.s


def build():
    return Temple().build()


if __name__ == "__main__":
    s = build()
    s.save(sys.argv[1] if len(sys.argv) > 1 else "temple.mcstructure")
    print("palette", len(s.palette))
