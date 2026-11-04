"""The Soul Fortress of the Nether Lord, for the soul sand valley.

A nether-brick keep (37 x 37) with red-brick cornices and battlements, four
round towers with soul-fire braziers, four causeway bridges on arches and
basalt piers, soul soil inlays, bone fossils, soul lanterns on chains, two
wither skeleton spawners (skulls for the altar), chests, and the Soul Altar
on a stepped dais in the courtyard. Size 81 x 44 x 81; the keep floor is at
height FLOOR (the foundation and piers below it reach down to the bottom).
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcstructure import Structure, AIR, byte, int_, Tag, LIST, COMPOUND, FLOAT  # noqa: E402

N = 81
C = N // 2          # 40
H = 44
FLOOR = 10          # keep floor
K = 18              # keep half-size (walls at |d| = 17..18)

BRICK = "minecraft:nether_brick"
CRACKED = "minecraft:cracked_nether_bricks"
CHISELED = "minecraft:chiseled_nether_bricks"
RED = "minecraft:red_nether_brick"
STAIRS = "minecraft:nether_brick_stairs"
RED_STAIRS = "minecraft:red_nether_brick_stairs"
SLAB = "minecraft:nether_brick_slab"
RED_SLAB = "minecraft:red_nether_brick_slab"
FENCE = "minecraft:nether_brick_fence"
RED_WALL = "minecraft:red_nether_brick_wall"
BLACKSTONE = "minecraft:blackstone"
POLISHED = "minecraft:polished_blackstone_bricks"
BASALT = "minecraft:basalt"
BONE = "minecraft:bone_block"
SOUL_SOIL = "minecraft:soul_soil"
SOUL_SAND = "minecraft:soul_sand"
SOUL_FIRE = "minecraft:soul_fire"
SOUL_LANTERN = "minecraft:soul_lantern"
CHAIN = "minecraft:chain"
SPAWNER = "minecraft:mob_spawner"
CHEST = "minecraft:chest"
ALTAR = "netherens:soul_altar"
CRYING = "minecraft:crying_obsidian"
BARS = "minecraft:iron_bars"

BACK = {"E": 0, "W": 1, "S": 2, "N": 3}
VEC = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
OPP = {"E": "W", "W": "E", "N": "S", "S": "N"}


class Fortress:
    def __init__(self, seed=13):
        self.s = Structure((N, H, N))
        self.rng = random.Random(seed)

    def put(self, x, y, z, name, states=None, **kw):
        self.s.set(x, y, z, name, states, **kw)

    def brick(self, x, y, z, cracked=0.12):
        self.put(x, y, z, CRACKED if self.rng.random() < cracked else BRICK)

    def stair(self, x, y, z, back, upside=False, name=STAIRS):
        self.put(x, y, z, name, {"weirdo_direction": BACK[back], "upside_down_bit": byte(upside)})

    def slab(self, x, y, z, top=False, name=SLAB):
        self.put(x, y, z, name, {"minecraft:vertical_half": "top" if top else "bottom"})

    def pillar(self, x, y, z, name=BASALT, axis="y"):
        self.put(x, y, z, name, {"pillar_axis": axis})

    def soul_brazier(self, x, y, z):
        self.put(x, y, z, SOUL_SOIL)
        self.put(x, y + 1, z, SOUL_FIRE, {"age": 0})
        for d, (dx, dz) in VEC.items():
            self.stair(x + dx, y, z + dz, OPP[d], name=RED_STAIRS)

    def lantern(self, x, y, z, chain=2):
        for i in range(chain):
            self.put(x, y - i, z, CHAIN, {"pillar_axis": "y"})
        self.put(x, y - chain, z, SOUL_LANTERN, {"hanging": byte(1)})

    def side(self, x, z):
        dx, dz = x - C, z - C
        if abs(dx) >= abs(dz):
            return "E" if dx > 0 else "W"
        return "S" if dz > 0 else "N"

    # --- parts
    def foundation(self):
        """Solid foundation under the keep, from the bottom to the floor."""
        for x in range(C - K, C + K + 1):
            for z in range(C - K, C + K + 1):
                for y in range(0, FLOOR):
                    edge = max(abs(x - C), abs(z - C)) == K
                    self.put(x, y, z, (BLACKSTONE if y < 3 else BRICK) if edge or y < FLOOR - 1 else BRICK)
                # air inside the keep (the terrain is carved out)
                for y in range(FLOOR, H):
                    self.put(x, y, z, AIR)
        # a sloped skirt of stairs where the foundation meets the ground
        for x in range(C - K - 1, C + K + 2):
            for z in range(C - K - 1, C + K + 2):
                if max(abs(x - C), abs(z - C)) == K + 1 and min(abs(x - C), abs(z - C)) > 3:
                    s = self.side(x, z)
                    for y in (2, 5):
                        self.stair(x, y, z, OPP[s], name=STAIRS)

    def courtyard(self):
        for x in range(C - K + 2, C + K - 1):
            for z in range(C - K + 2, C + K - 1):
                dx, dz = abs(x - C), abs(z - C)
                if (dx + dz) % 6 == 0 and max(dx, dz) > 6:
                    self.put(x, FLOOR - 1, z, SOUL_SOIL)
                elif dx == dz and dx > 6:
                    self.put(x, FLOOR - 1, z, RED)
                elif max(dx, dz) in (10, 11):
                    self.put(x, FLOOR - 1, z, CHISELED if (x + z) % 3 == 0 else RED)
                else:
                    self.brick(x, FLOOR - 1, z, 0.15)

    def keep_walls(self):
        top = FLOOR + 14
        for x in range(C - K, C + K + 1):
            for z in range(C - K, C + K + 1):
                m = max(abs(x - C), abs(z - C))
                if m < K - 1:
                    continue
                side = self.side(x, z)
                along = abs(z - C) if side in "EW" else abs(x - C)
                for y in range(FLOOR - 1, top):
                    if y in (FLOOR + 5, FLOOR + 6) and m == K and along % 6 == 3 and along < K - 3:
                        self.put(x, y, z, BARS)         # windows
                    elif y == FLOOR + 8:
                        self.put(x, y, z, RED)          # red band
                    else:
                        self.brick(x, y, z)
                if m == K:
                    ox, oz = VEC[side]
                    self.stair(x + ox, FLOOR + 8, z + oz, OPP[side], upside=True, name=RED_STAIRS)
                    self.stair(x + ox, top - 1, z + oz, OPP[side], upside=True, name=RED_STAIRS)
                    if along % 2 == 0:
                        self.put(x, top, z, RED)
                        self.slab(x, top + 1, z, name=RED_SLAB)
                    else:
                        self.slab(x, top, z, name=RED_SLAB)
                    if along % 6 == 0 and along < K - 3:
                        self.buttress(x, z, side, top)
                else:
                    ox, oz = VEC[side]
                    self.slab(x - ox, top - 1, z - oz, top=True)        # wall walk
                    if along % 6 == 0 and along < K - 3:
                        self.lantern(x - ox, top - 2, z - oz, chain=1)

    def buttress(self, x, z, side, top):
        ox, oz = VEC[side]
        bx, bz = x + ox, z + oz
        for y in range(0, top - 4):
            self.brick(bx, y, bz)
        self.stair(bx, top - 4, bz, OPP[side])
        cx, cz = bx + ox, bz + oz
        for y in range(0, FLOOR + 3):
            self.brick(cx, y, cz)
        self.stair(cx, FLOOR + 3, cz, OPP[side])

    def gates_and_bridges(self):
        """A gate in each wall and a causeway on arches to the edge of the structure."""
        for d, (dx, dz) in VEC.items():
            px, pz = (0, 1) if d in "EW" else (1, 0)
            # gate: 5 wide, 7 high, red arch
            for w in range(-2, 3):
                for depth in (K - 1, K):
                    gx, gz = C + dx * depth + px * w, C + dz * depth + pz * w
                    for y in range(FLOOR, FLOOR + 7):
                        self.put(gx, y, gz, AIR)
                    if abs(w) == 2:
                        self.stair(gx, FLOOR + 6, gz, "E" if (px * w) > 0 or (pz * w) > 0 and d in "EW" else "W", upside=True,
                                   name=RED_STAIRS)
            for w in range(-3, 4):
                gx, gz = C + dx * (K + 1) + px * w, C + dz * (K + 1) + pz * w
                self.put(gx, FLOOR + 7, gz, CHISELED if w == 0 else RED)
            # causeway from the wall to the edge
            for dist in range(K + 1, C + 1):
                for w in range(-2, 3):
                    bx, bz = C + dx * dist + px * w, C + dz * dist + pz * w
                    self.put(bx, FLOOR - 1, bz, CHISELED if w == 0 and dist % 4 == 0 else BRICK)
                    for y in range(FLOOR, FLOOR + 4):
                        self.put(bx, y, bz, AIR)
                    if abs(w) == 2:
                        self.put(bx, FLOOR, bz, FENCE)
                        if dist % 4 == 0:
                            self.put(bx, FLOOR + 1, bz, FENCE)
                            self.put(bx, FLOOR + 2, bz, SOUL_LANTERN, {"hanging": byte(0)})
                    # arches under the deck: piers every 6 blocks, upside-down stairs in between
                    if (dist - K) % 6 == 0:
                        for y in range(0, FLOOR - 1):
                            if abs(w) == 2:
                                self.pillar(bx, y, bz)
                            else:
                                self.brick(bx, y, bz)
                    else:
                        k = (dist - K) % 6
                        drop = {1: 3, 2: 2, 3: 2, 4: 2, 5: 3}[k]
                        for y in range(FLOOR - 1 - drop, FLOOR - 1):
                            self.brick(bx, y, bz)
                        self.stair(bx, FLOOR - 2 - drop, bz, d if k <= 2 else OPP[d], upside=True)
            # guard posts at the far end: soul braziers on red pedestals
            for w in (-2, 2):
                ex, ez = C + dx * C + px * w, C + dz * C + pz * w
                self.put(ex, FLOOR, ez, RED)
                self.soul_brazier(ex, FLOOR + 1, ez)

    def tower(self, cx, cz, spawner):
        r = 4
        top = FLOOR + 22
        for x in range(cx - r - 1, cx + r + 2):
            for z in range(cz - r - 1, cz + r + 2):
                d = math.hypot(x - cx, z - cz)
                if d > r + 0.5:
                    continue
                shell = d > r - 0.7
                for y in range(0, top):
                    if shell:
                        if y in (FLOOR + 8,):
                            self.put(x, y, z, RED)
                        elif y in (FLOOR + 12, FLOOR + 13) and (x == cx or z == cz):
                            self.put(x, y, z, BARS)
                        else:
                            self.brick(x, y, z, 0.1)
                    elif y >= FLOOR:
                        self.put(x, y, z, AIR)
                    else:
                        self.brick(x, y, z, 0)
                if shell:
                    s = "E" if x > cx else "W"
                    if abs(z - cz) > abs(x - cx):
                        s = "S" if z > cz else "N"
                    ox, oz = VEC[s]
                    if self.s.get(x + ox, top - 1, z + oz) in (None, "minecraft:structure_void", AIR):
                        self.stair(x + ox, top - 1, z + oz, OPP[s], upside=True, name=RED_STAIRS)
                        self.stair(x + ox, FLOOR + 8, z + oz, OPP[s], upside=True, name=RED_STAIRS)
        # inner floor and the spawner behind bars
        for y in (FLOOR + 8, FLOOR + 15):
            for x in range(cx - r + 1, cx + r):
                for z in range(cz - r + 1, cz + r):
                    if math.hypot(x - cx, z - cz) <= r - 0.7:
                        self.slab(x, y, z, top=True)
        if spawner:
            be = {"id": "MobSpawner", "EntityIdentifier": "minecraft:wither_skeleton", "Delay": short(20),
                  "MinSpawnDelay": short(300), "MaxSpawnDelay": short(900), "SpawnCount": short(3),
                  "MaxNearbyEntities": short(5), "RequiredPlayerRange": short(16), "SpawnRange": short(4),
                  "DisplayEntityWidth": Tag(FLOAT, 0.7), "DisplayEntityHeight": Tag(FLOAT, 2.4),
                  "DisplayEntityScale": Tag(FLOAT, 1.0), "isMovable": byte(1),
                  "x": int_(cx), "y": int_(FLOOR + 1), "z": int_(cz)}
            self.put(cx, FLOOR, cz, SOUL_SOIL)
            self.put(cx, FLOOR + 1, cz, SPAWNER, block_entity=be)
        self.lantern(cx, FLOOR + 7, cz, chain=2)
        # doorway from the courtyard (towards the keep's centre)
        sx, sz = (1 if cx < C else -1), (1 if cz < C else -1)
        for i in (2, 3):
            for j in (2, 3):
                for y in range(FLOOR, FLOOR + 3):
                    self.put(cx + sx * i, y, cz + sz * j, AIR)
        # cone roof of red stairs and a soul brazier
        for level in range(0, r + 1):
            rr = r - level + 0.5
            y = top + level
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    d = math.hypot(x - cx, z - cz)
                    if d > rr:
                        continue
                    if d > rr - 1:
                        s = "E" if x > cx else "W"
                        if abs(z - cz) > abs(x - cx):
                            s = "S" if z > cz else "N"
                        self.stair(x, y, z, OPP[s], name=RED_STAIRS)
                    else:
                        self.put(x, y, z, RED)
        self.soul_brazier(cx, top + r + 1, cz)

    def dais(self):
        """Three red steps, crying obsidian rim, the Soul Altar and four soul-fire pillars."""
        for i, half in enumerate((5, 4, 3)):
            y = FLOOR + i
            for x in range(C - half, C + half + 1):
                for z in range(C - half, C + half + 1):
                    m = max(abs(x - C), abs(z - C))
                    if m == half and min(abs(x - C), abs(z - C)) != half:
                        self.stair(x, y, z, OPP[self.side(x, z)], name=RED_STAIRS)
                    elif m == half:
                        self.put(x, y, z, CHISELED)
                    else:
                        self.put(x, y, z, CRYING if (i == 2 and m == half - 1) else RED)
        self.put(C, FLOOR + 3, C, ALTAR, {"netherens:lit": byte(0)})
        for dx, dz in ((7, 7), (-7, 7), (7, -7), (-7, -7)):
            x, z = C + dx, C + dz
            for y in range(FLOOR, FLOOR + 5):
                self.pillar(x, y, z, BASALT)
            self.put(x, FLOOR + 5, z, CHISELED)
            self.soul_brazier(x, FLOOR + 6, z)
        # ring of fences and hanging lanterns between the pillars
        for x in range(C - 7, C + 8):
            for z in range(C - 7, C + 8):
                m = max(abs(x - C), abs(z - C))
                if m == 7 and min(abs(x - C), abs(z - C)) not in (0, 1, 7):
                    self.put(x, FLOOR, z, FENCE)
        for dx, dz in ((0, 9), (0, -9), (9, 0), (-9, 0)):
            self.lantern(C + dx, FLOOR + 13, C + dz, chain=6)

    def gallery(self):
        """Arcade along the inner walls: basalt piers and an upper walkway."""
        y_walk = FLOOR + 7
        for x in range(C - K + 1, C + K):
            for z in range(C - K + 1, C + K):
                m = max(abs(x - C), abs(z - C))
                if m in (K - 2, K - 3):
                    self.slab(x, y_walk, z, top=True)
                if m == K - 4:
                    side = self.side(x, z)
                    along = abs(z - C) if side in "EW" else abs(x - C)
                    if along > 3:
                        self.put(x, y_walk, z, FENCE)
                    if along % 6 == 0 and along < K - 4:
                        for y in range(FLOOR, y_walk):
                            self.pillar(x, y, z)
                        self.stair(x, y_walk - 1, z, side, upside=True, name=RED_STAIRS)

    def gallery_stairs(self):
        """A flight up to the gallery walkway, along the inside of the west wall."""
        y_walk = FLOOR + 7
        x0 = C - K + 2
        for i in range(y_walk - FLOOR):
            z = C + 4 + i
            for w in (0, 1):
                self.stair(x0 + w, FLOOR + i, z, "S")
                for y in range(FLOOR, FLOOR + i):
                    self.brick(x0 + w, y, z)
                for y in range(FLOOR + i + 1, FLOOR + i + 4):
                    if y < y_walk:
                        self.put(x0 + w, y, z, AIR)

    def chests(self):
        for x, z, facing in ((C - 12, C - 14, "south"), (C + 12, C + 14, "north")):
            be = {"id": "Chest", "isMovable": byte(1), "Findable": byte(0),
                  "LootTable": "loot_tables/netherens/chests/soul_fortress.json", "LootTableSeed": int_(0),
                  "Items": Tag(LIST, (COMPOUND, [])), "x": int_(x), "y": int_(FLOOR), "z": int_(z)}
            self.put(x, FLOOR, z, CHEST, {"minecraft:cardinal_direction": facing}, block_entity=be)
            self.put(x + 1, FLOOR, z, SOUL_LANTERN, {"hanging": byte(0)})

    def walls_states(self):
        """Wall blocks need their connections spelled out (no block updates on load)."""
        sx, sy, sz = self.s.size
        for x in range(sx):
            for y in range(sy):
                for z in range(sz):
                    if self.s.get(x, y, z) != RED_WALL:
                        continue
                    conn = {}
                    for name, (dx, dz) in (("east", (1, 0)), ("west", (-1, 0)), ("south", (0, 1)), ("north", (0, -1))):
                        n = self.s.get(x + dx, y, z + dz)
                        conn[name] = "short" if n and n not in (AIR, "minecraft:structure_void") else "none"
                    self.put(x, y, z, RED_WALL, {**{f"wall_connection_type_{k}": v for k, v in conn.items()},
                                                 "wall_post_bit": byte(1)})

    def build(self):
        self.foundation()
        self.courtyard()
        self.keep_walls()
        self.gates_and_bridges()
        for (dx, dz), spawner in zip(((-1, -1), (1, -1), (-1, 1), (1, 1)), (True, False, False, True)):
            self.tower(C + dx * K, C + dz * K, spawner)
        self.gallery()
        self.gallery_stairs()
        self.dais()
        self.chests()
        self.walls_states()
        return self.s


def short(v):
    from mcstructure import Tag as T, SHORT
    return T(SHORT, int(v))


def build():
    return Fortress().build()


if __name__ == "__main__":
    s = build()
    s.save(sys.argv[1] if len(sys.argv) > 1 else "fortress.mcstructure")
    print("palette", len(s.palette))
