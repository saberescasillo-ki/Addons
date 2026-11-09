"""Boss arenas of TEU Mobs: one complex per boss, built block by block.

Every arena is a group of rooms joined by curved corridors at different heights around a
domed hall where the boss waits: a hidden repeating command block under the middle of the
hall runs teu_mobs/arena/<name> (summons the boss once and removes itself) when a player
comes near. A spiral stair climbs from one of the rooms. The outside is structure_void
(underground and in the Nether the world stays around the walls); the End arenas float on
an island of end stone.

    from teu import arenas; arenas.build(out_dir) -> {name: structure path}
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcstructure as m  # noqa: E402
from mcstructure import Tag, byte, int_  # noqa: E402

AIR, VOID = "minecraft:air", m.STRUCTURE_VOID
NONE, OPEN, WATER, LAVA = 0, 1, 2, 3


def noise(x, y, z, s=0):
    n = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ (s * 2654435761)
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return (n & 0xFFFFFF) / 0x1000000


class Arena(m.Structure):
    """A Structure that also writes the tick queue a repeating command block needs."""

    def __init__(self, size):
        super().__init__(size, VOID)
        self.ticking = set()

    def to_nbt(self):
        root = super().to_nbt()
        pos = root["structure"]["palette"]["default"]["block_position_data"]
        for i in self.ticking:
            pos[str(i)]["tick_queue_data"] = Tag(m.LIST, (m.COMPOUND, [{"tick_delay": int_(0)}]))
        return root


class Plan:
    """Where the inside is (air, water or lava), before the walls are drawn around it."""

    def __init__(self, size):
        self.W, self.H, self.D = size
        self.cells = bytearray(self.W * self.H * self.D)
        self.floor_marks = {}

    def i(self, x, y, z):
        return (x * self.H + y) * self.D + z

    def ok(self, x, y, z, margin=2):
        return margin <= x < self.W - margin and 1 <= y < self.H - 2 and margin <= z < self.D - margin

    def mark(self, x, y, z, code=OPEN):
        if self.ok(x, y, z):
            j = self.i(x, y, z)
            if self.cells[j] == NONE or code != OPEN:
                self.cells[j] = code

    def get(self, x, y, z):
        if 0 <= x < self.W and 0 <= y < self.H and 0 <= z < self.D:
            return self.cells[self.i(x, y, z)]
        return NONE

    def hall(self, cx, fy, cz, r, wall_h, dome_h, lobes=0, depth=0.0, phase=0.0, code=OPEN):
        """A round room: straight walls, then a dome. lobes/depth make it petal-shaped."""
        for x in range(int(cx - r * 1.4) - 1, int(cx + r * 1.4) + 2):
            for z in range(int(cz - r * 1.4) - 1, int(cz + r * 1.4) + 2):
                dx, dz = x - cx, z - cz
                d = math.hypot(dx, dz)
                rr = r * (1 + depth * math.cos(lobes * math.atan2(dz, dx) + phase)) if lobes else r
                for y in range(fy, fy + wall_h + dome_h):
                    if y < fy + wall_h:
                        inside = d <= rr
                    else:
                        t = (y - fy - wall_h + 0.5) / dome_h
                        inside = t < 1 and d <= rr * math.sqrt(1 - t * t)
                    if inside:
                        self.mark(x, y, z, code)

    def tube(self, pts, w, h, code=OPEN):
        """A corridor along a polyline of floor points (x, y, z), with an arched ceiling."""
        samples = []
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(math.dist(a, b) * 3))
            samples += [tuple(a[k] + (b[k] - a[k]) * s / n for k in range(3)) for s in range(n)]
        samples.append(pts[-1])
        for (x, y, z) in samples:
            for ix in range(int(x - w) - 1, int(x + w) + 2):
                for iz in range(int(z - w) - 1, int(z + w) + 2):
                    lat = math.hypot(ix - x, iz - z)
                    if lat > w:
                        continue
                    top = h - 1.5 * (lat / w) ** 2
                    for iy in range(int(round(y)), int(round(y + top))):
                        self.mark(ix, iy, iz, code)
            self.floor_marks[(int(round(x)), int(round(z)))] = int(round(y))

    def shaft(self, cx, cz, y0, y1, r):
        for y in range(y0, y1):
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    if math.hypot(x - cx, z - cz) <= r + 0.3:
                        self.mark(x, y, z)


def curve(a, b, bend, rnd):
    """Floor points from a to b bending sideways (and with steps if heights differ)."""
    (ax, ay, az), (bx, by, bz) = a, b
    mx, mz = (ax + bx) / 2, (az + bz) / 2
    dx, dz = bx - ax, bz - az
    ln = math.hypot(dx, dz) or 1
    mx += -dz / ln * bend
    mz += dx / ln * bend
    pts = []
    for k in range(9):
        t = k / 8
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * mx + t * t * bx
        z = (1 - t) ** 2 * az + 2 * (1 - t) * t * mz + t * t * bz
        pts.append((x, ay + (by - ay) * t, z))
    return pts


# --- themes -------------------------------------------------------------------------------
class Theme:
    name = ""
    size = (64, 34, 64)
    hall = dict(r=13, wall_h=8, dome_h=12, lobes=6, depth=0.12)
    floor_y = 3
    rooms = 5
    room_phase = None            # None: random
    room_jitter = 0.25
    fill = OPEN                  # what the hall is filled with
    walls = [("minecraft:stone_bricks", 1.0)]
    outer = "minecraft:stone"
    floor = [("minecraft:stone_bricks", 1.0)]
    ceiling = None
    light = "minecraft:glowstone"
    light_rate = 0.05
    pillar = "minecraft:stone_bricks"
    accent = "minecraft:chiseled_stone_bricks"
    loot = "loot_tables/chests/simple_dungeon.json"
    island = None                # End: the arena floats on an island of this block

    def pick(self, choices, x, y, z, s):
        v = noise(x, y, z, s)
        acc = 0.0
        for name, w in choices:
            acc += w
            if v < acc:
                return name
        return choices[-1][0]

    trim = None                  # a stripe every 6 blocks of height

    def wall(self, x, y, z):
        if self.trim and (y - self.floor_y) % 6 == 5:
            return self.trim
        return self.pick(self.walls, x, y, z, 1)

    def floor_at(self, x, z, d, ang):
        return self.pick(self.floor, x, 0, z, 2)

    def hall_decor(self, a, plan, cx, fy, cz):
        pass

    def room_decor(self, a, plan, kind, cx, fy, cz, r):
        pass


def pal(*pairs):
    tot = sum(w for _, w in pairs)
    return [("minecraft:" + n, w / tot) for n, w in pairs]


class Floral(Theme):
    name = "floral"
    size = (64, 32, 64)
    hall = dict(r=14, wall_h=7, dome_h=13, lobes=5, depth=0.16)
    walls = pal(("mossy_stone_bricks", 7), ("moss_block", 2), ("mossy_cobblestone", 1))
    trim = "minecraft:stripped_jungle_wood"
    outer = "minecraft:stone"
    floor = pal(("moss_block", 6), ("rooted_dirt", 2), ("mossy_stone_bricks", 2))
    light = "minecraft:shroomlight"
    light_rate = 0.06
    pillar = "minecraft:stripped_jungle_log"
    accent = "minecraft:mossy_stone_bricks"
    loot = "loot_tables/chests/jungle_temple.json"

    def floor_at(self, x, z, d, ang):
        if abs(d - 7) < 0.7 or abs(d - 11) < 0.7:
            return "minecraft:mossy_stone_bricks"
        return self.pick(self.floor, x, 0, z, 2)

    def hall_decor(self, a, plan, cx, fy, cz):
        # a great root column in the middle, flowering bushes and spore blossoms
        for y in range(fy, fy + 18):
            rr = 2.6 - 1.4 * (y - fy) / 18
            for x in range(cx - 3, cx + 4):
                for z in range(cz - 3, cz + 4):
                    if math.hypot(x - cx, z - cz) <= rr and plan.get(x, y, z) == OPEN:
                        a.set(x, y, z, "minecraft:jungle_log" if noise(x, y, z, 5) > 0.2 else "minecraft:moss_block")
        for k in range(14):
            ang = k * 2 * math.pi / 14
            x, z = int(cx + 9.5 * math.cos(ang)), int(cz + 9.5 * math.sin(ang))
            a.set(x, fy, z, "minecraft:flowering_azalea" if k % 2 else "minecraft:azalea")
        for x in range(cx - 13, cx + 14, 3):
            for z in range(cz - 13, cz + 14, 3):
                y = top_of(plan, x, fy, z)
                if y and noise(x, y, z, 6) < 0.45:
                    a.set(x, y, z, "minecraft:spore_blossom")

    def room_decor(self, a, plan, kind, cx, fy, cz, r):
        if kind == "pond":
            for x in range(cx - r, cx + r + 1):
                for z in range(cz - r, cz + r + 1):
                    if math.hypot(x - cx, z - cz) <= r - 1.5:
                        a.set(x, fy - 1, z, "minecraft:water")
                        if noise(x, 0, z, 7) < 0.15:
                            a.set(x, fy, z, "minecraft:waterlily")


class Wyrm(Theme):
    name = "wyrm"
    size = (64, 36, 64)
    hall = dict(r=15, wall_h=13, dome_h=12, lobes=8, depth=0.08)
    floor_y = 2
    walls = pal(("prismarine_bricks", 8), ("prismarine", 2))
    trim = "minecraft:dark_prismarine"
    outer = "minecraft:deepslate"
    floor = pal(("dark_prismarine", 3), ("prismarine_bricks", 2))
    light = "minecraft:sea_lantern"
    light_rate = 0.07
    pillar = "minecraft:prismarine"
    accent = "minecraft:sea_lantern"
    loot = "loot_tables/chests/underwater_ruin_big.json"
    water_top = 14                # the hall is a flooded pool up to here; galleries above it

    def hall_decor(self, a, plan, cx, fy, cz):
        top = fy + self.water_top
        r = self.hall["r"]
        for x in range(cx - r - 3, cx + r + 4):      # a walkway round the pool, at the water line
            for z in range(cz - r - 3, cz + r + 4):
                if r - 3.5 <= math.hypot(x - cx, z - cz) and a.get(x, top, z) == AIR:
                    a.set(x, top - 1, z, "minecraft:prismarine_bricks")
        for x in range(a.size[0]):
            for z in range(a.size[2]):
                for y in range(fy, top):
                    if a.get(x, y, z) == AIR and math.hypot(x - cx, z - cz) <= self.hall["r"] + 1:
                        a.set(x, y, z, "minecraft:water")
        for k in range(8):                 # coral gardens on the bottom
            ang = k * math.pi / 4
            x, z = int(cx + 8 * math.cos(ang)), int(cz + 8 * math.sin(ang))
            for dx, dz in ((0, 0), (1, 0), (0, 1)):
                a.set(x + dx, fy, z + dz, ["minecraft:tube_coral_block", "minecraft:brain_coral_block",
                                           "minecraft:horn_coral_block"][k % 3])
                a.set(x + dx, fy + 1, z + dz, "minecraft:sea_pickle", {"cluster_count": 3, "dead_bit": False})


class Sculk(Theme):
    name = "sculk"
    size = (64, 30, 64)
    hall = dict(r=14, wall_h=9, dome_h=10, lobes=4, depth=0.18, phase=math.pi / 4)
    walls = pal(("deepslate_bricks", 7), ("cracked_deepslate_bricks", 1), ("sculk", 2))
    trim = "minecraft:deepslate_tiles"
    outer = "minecraft:deepslate"
    floor = pal(("deepslate_tiles", 4), ("sculk", 3), ("polished_deepslate", 2))
    light = "minecraft:sculk_catalyst"
    light_rate = 0.03
    pillar = "minecraft:reinforced_deepslate"
    accent = "minecraft:chiseled_deepslate"
    loot = "loot_tables/chests/ancient_city.json"

    def floor_at(self, x, z, d, ang):
        if int(d) % 5 == 0:
            return "minecraft:polished_deepslate"
        return self.pick(self.floor, x, 0, z, 2)

    def hall_decor(self, a, plan, cx, fy, cz):
        for k in range(12):
            ang = k * math.pi / 6
            x, z = int(round(cx + 11 * math.cos(ang))), int(round(cz + 11 * math.sin(ang)))
            a.set(x, fy, z, "minecraft:sculk_catalyst")
            a.set(x, fy + 1, z, "minecraft:soul_lantern")
        for x in range(cx - 1, cx + 2):       # the dais
            for z in range(cz - 1, cz + 2):
                a.set(x, fy, z, "minecraft:reinforced_deepslate")
        hang_lanterns(a, plan, cx, fy, cz, 13, "minecraft:soul_lantern")


class Pyrogen(Theme):
    name = "pyrogen"
    size = (64, 32, 64)
    hall = dict(r=14, wall_h=8, dome_h=12, lobes=6, depth=0.1)
    walls = pal(("polished_blackstone_bricks", 8), ("cracked_polished_blackstone_bricks", 2))
    trim = "minecraft:gilded_blackstone"
    outer = "minecraft:blackstone"
    floor = pal(("polished_blackstone", 4), ("polished_basalt", 2), ("magma", 1))
    light = "minecraft:shroomlight"
    light_rate = 0.04
    pillar = "minecraft:basalt"
    accent = "minecraft:gold_block"
    loot = "loot_tables/chests/bastion_treasure.json"

    def hall_decor(self, a, plan, cx, fy, cz):
        for x in range(cx - 13, cx + 14):          # a ring of lava around the forge
            for z in range(cz - 13, cz + 14):
                d = math.hypot(x - cx, z - cz)
                if 8.2 <= d <= 9.4:
                    a.set(x, fy - 1, z, "minecraft:lava")
                if d <= 3.2:
                    a.set(x, fy, z, "minecraft:gilded_blackstone" if d > 2 else "minecraft:magma")
        for k in range(4):                         # bridges over the lava
            ang = k * math.pi / 2
            for t in range(8, 11):
                x, z = int(round(cx + t * math.cos(ang))), int(round(cz + t * math.sin(ang)))
                a.set(x, fy - 1, z, "minecraft:polished_blackstone_bricks")
        hang_lanterns(a, plan, cx, fy, cz, 12, "minecraft:lantern")


class Ghast(Theme):
    name = "ghast"
    size = (64, 42, 64)
    hall = dict(r=17, wall_h=12, dome_h=18, lobes=7, depth=0.08)
    rooms = 4
    room_phase = math.pi / 4     # in the corners, round the great hall
    room_jitter = 0.0
    walls = pal(("smooth_basalt", 8), ("basalt", 2))
    trim = "minecraft:oxidized_cut_copper"
    outer = "minecraft:basalt"
    floor = pal(("smooth_basalt", 3), ("verdant_froglight", 1), ("oxidized_cut_copper", 2))
    light = "minecraft:verdant_froglight"
    light_rate = 0.05
    pillar = "minecraft:oxidized_copper"
    accent = "minecraft:verdant_froglight"
    loot = "loot_tables/chests/nether_bridge.json"

    def hall_decor(self, a, plan, cx, fy, cz):
        for x in range(cx - 18, cx + 19):          # a toxic pit in the middle
            for z in range(cz - 18, cz + 19):
                d = math.hypot(x - cx, z - cz)
                if d <= 5:
                    a.set(x, fy - 1, z, "minecraft:slime" if noise(x, 0, z, 9) < 0.5 else "minecraft:verdant_froglight")
                elif 12 < d < 13:
                    a.set(x, fy, z, "minecraft:lime_stained_glass")


class Astral(Theme):
    name = "astral"
    size = (64, 38, 64)
    hall = dict(r=14, wall_h=8, dome_h=13, lobes=0, depth=0)
    floor_y = 9
    walls = pal(("purpur_block", 8), ("purpur_pillar", 2))
    trim = "minecraft:amethyst_block"
    outer = None                 # seen from outside: the same as the walls
    floor = pal(("calcite", 3), ("polished_blackstone", 2), ("amethyst_block", 1))
    ceiling = "minecraft:tinted_glass"
    light = "minecraft:pearlescent_froglight"
    light_rate = 0.05
    pillar = "minecraft:purpur_pillar"
    accent = "minecraft:amethyst_block"
    loot = "loot_tables/chests/end_city_treasure.json"
    island = "minecraft:end_stone"

    def floor_at(self, x, z, d, ang):
        if abs(d - 6) < 0.6 or abs(d - 10) < 0.6:
            return "minecraft:amethyst_block"
        k = int((ang + math.pi) / (math.pi / 6))
        return "minecraft:calcite" if k % 2 else "minecraft:polished_blackstone"

    def hall_decor(self, a, plan, cx, fy, cz):
        for k in range(8):                       # an orrery: rings and floating "planets"
            ang = k * math.pi / 4
            x, z = int(round(cx + 4 * math.cos(ang))), int(round(cz + 4 * math.sin(ang)))
            a.set(x, fy, z, "minecraft:end_rod")
        for y in range(fy, fy + 3):
            a.set(cx, y, cz, "minecraft:purpur_pillar")
        a.set(cx, fy + 3, cz, "minecraft:beacon")


class Obelisk(Theme):
    name = "obelisk"
    size = (64, 40, 64)
    hall = dict(r=14, wall_h=14, dome_h=12, lobes=4, depth=0.14, phase=math.pi / 4)
    floor_y = 9
    walls = pal(("end_stone_bricks", 8), ("end_stone", 1))
    trim = "minecraft:obsidian"
    outer = None
    floor = pal(("end_stone_bricks", 3), ("purpur_block", 2), ("obsidian", 2))
    light = "minecraft:pearlescent_froglight"
    light_rate = 0.05
    pillar = "minecraft:obsidian"
    accent = "minecraft:crying_obsidian"
    loot = "loot_tables/chests/end_city_treasure.json"
    island = "minecraft:end_stone"

    def floor_at(self, x, z, d, ang):
        if abs(abs(x - 32) - abs(z - 32)) < 1:           # an X across the floor
            return "minecraft:obsidian"
        return self.pick(self.floor, x, 0, z, 2)

    def hall_decor(self, a, plan, cx, fy, cz):
        for x in range(cx - 2, cx + 3):
            for z in range(cz - 2, cz + 3):
                a.set(x, fy, z, "minecraft:crying_obsidian" if (x + z) % 2 else "minecraft:obsidian")
        for k in range(4):
            ang = math.pi / 4 + k * math.pi / 2
            x, z = int(round(cx + 10 * math.cos(ang))), int(round(cz + 10 * math.sin(ang)))
            for y in range(fy, fy + 9):
                a.set(x, y, z, "minecraft:obsidian")
            a.set(x, fy + 9, z, "minecraft:end_rod")


THEMES = [Floral, Wyrm, Sculk, Pyrogen, Ghast, Astral, Obelisk]
ROOM_KINDS = ["vault", "shrine", "library", "pond", "armory", "store"]


def top_of(plan, x, y0, z):
    y = y0
    while plan.get(x, y, z) != NONE and y < plan.H - 1:
        y += 1
    return y - 1 if y > y0 else None


def hang_lanterns(a, plan, cx, fy, cz, r, block):
    for k in range(8):
        ang = k * math.pi / 4 + math.pi / 8
        x, z = int(round(cx + r * 0.6 * math.cos(ang))), int(round(cz + r * 0.6 * math.sin(ang)))
        y = top_of(plan, x, fy, z)
        if not y:
            continue
        for yy in range(y, max(fy + 5, y - 4), -1):
            a.set(x, yy, z, "minecraft:chain", {"pillar_axis": "y"})
        a.set(x, max(fy + 5, y - 4), z, block, {"hanging": True})


def chest(a, x, y, z, loot, facing="north"):
    a.set(x, y, z, "minecraft:chest", {"minecraft:cardinal_direction": facing},
          block_entity={"id": "Chest", "LootTable": loot, "LootTableSeed": int_(0), "Findable": byte(0),
                        "isMovable": byte(1)})


def command_block(a, x, y, z, command):
    a.set(x, y, z, "minecraft:repeating_command_block", {"conditional_bit": False, "facing_direction": 1},
          block_entity={"id": "CommandBlock", "Command": command, "CustomName": "", "auto": byte(1),
                        "ExecuteOnFirstTick": byte(1), "LPCommandMode": int_(0), "LPCondionalMode": byte(0),
                        "LPRedstoneMode": byte(0), "TickDelay": int_(10), "TrackOutput": byte(0), "Version": int_(42),
                        "conditionMet": byte(1), "conditionalMode": byte(0), "isMovable": byte(0), "powered": byte(0),
                        "SuccessCount": int_(0), "LastOutput": "", "LastOutputParams": Tag(m.LIST, (m.END, []))})
    a.ticking.add(a._flat(x, y, z))


def generate(theme, trigger_cmd):
    """-> (Arena, (hall centre x, floor y, z))"""
    rnd = random.Random(theme.name)
    W, H, D = theme.size
    plan = Plan(theme.size)
    cx, cz, fy = W // 2, D // 2, theme.floor_y
    hl = theme.hall
    plan.hall(cx, fy, cz, hl["r"], hl["wall_h"], hl["dome_h"], hl.get("lobes", 0), hl.get("depth", 0),
              hl.get("phase", 0))
    # rooms around the hall, at different heights, joined to it and to each other
    rooms = []
    phase = rnd.uniform(0, 2 * math.pi) if theme.room_phase is None else theme.room_phase
    for k in range(theme.rooms):
        ang = phase + k * 2 * math.pi / theme.rooms + rnd.uniform(-theme.room_jitter, theme.room_jitter)
        r = rnd.choice([4, 5, 5])
        dist = hl["r"] + r + (8 if theme.room_phase is not None else 5)
        rx = int(round(cx + dist * math.cos(ang)))
        rz = int(round(cz + dist * math.sin(ang)))
        rx = max(r + 3, min(W - r - 4, rx))
        rz = max(r + 3, min(D - r - 4, rz))
        ry = fy + rnd.choice([0, 2, 3, 5]) if theme.name != "wyrm" else fy + theme.water_top + rnd.choice([0, 1, 2])
        kind = ROOM_KINDS[k % len(ROOM_KINDS)]
        plan.hall(rx, ry, rz, r, rnd.choice([4, 5]), rnd.choice([3, 4, 5]), rnd.choice([0, 3, 4, 5]),
                  rnd.uniform(0.1, 0.2), rnd.uniform(0, 6.28))
        rooms.append((kind, rx, ry, rz, r, ang))
    for kind, rx, ry, rz, r, ang in rooms:   # corridors to the hall
        hy = fy + (theme.water_top if theme.name == "wyrm" else 0)
        hx, hz = cx + (hl["r"] - 1) * math.cos(ang), cz + (hl["r"] - 1) * math.sin(ang)
        ex, ez = rx - (r - 1) * math.cos(ang), rz - (r - 1) * math.sin(ang)
        plan.tube(curve((ex, ry, ez), (hx, hy, hz), rnd.uniform(-3, 3), rnd), 1.7, 4)
    for (k1, x1, y1, z1, r1, a1), (k2, x2, y2, z2, r2, a2) in zip(rooms, rooms[1:]):   # a ring between rooms
        plan.tube(curve((x1, y1, z1), (x2, y2, z2), rnd.uniform(4, 7), rnd), 1.4, 3)
    if theme.name == "wyrm":                 # a gallery all round, above the water
        r_g = hl["r"] - 1
        pts = [(cx + r_g * math.cos(t / 16 * 2 * math.pi), fy + theme.water_top, cz + r_g * math.sin(t / 16 * 2 * math.pi))
               for t in range(17)]
        plan.tube(pts, 1.5, 4)
    # the spiral stair from the first room up to the roof
    kind, sx, sy, sz, sr, _ = rooms[0]
    plan.shaft(sx, sz, sy, H - 3, 2)

    a = Arena(theme.size)
    cells = plan.cells
    Wd, Hd, Dd = plan.W, plan.H, plan.D
    # walls: two layers around the inside; outside stays as it was (structure void)
    near = bytearray(len(cells))
    for x in range(Wd):
        for y in range(Hd):
            for z in range(Dd):
                if cells[plan.i(x, y, z)] == NONE:
                    continue
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        for dz in (-2, -1, 0, 1, 2):
                            nx, ny, nz = x + dx, y + dy, z + dz
                            if 0 <= nx < Wd and 0 <= ny < Hd and 0 <= nz < Dd:
                                j = plan.i(nx, ny, nz)
                                lvl = 1 if max(abs(dx), abs(dy), abs(dz)) == 1 else 2
                                if cells[j] == NONE and (near[j] == 0 or near[j] > lvl):
                                    near[j] = lvl
    for x in range(Wd):
        for y in range(Hd):
            for z in range(Dd):
                j = plan.i(x, y, z)
                c = cells[j]
                if c == OPEN:
                    a.set(x, y, z, AIR)
                elif c == WATER:
                    a.set(x, y, z, "minecraft:water")
                elif c == LAVA:
                    a.set(x, y, z, "minecraft:lava")
                elif near[j]:
                    if near[j] == 2:
                        a.set(x, y, z, theme.outer or theme.wall(x, y, z))
                        continue
                    above = plan.get(x, y + 1, z) != NONE
                    below = plan.get(x, y - 1, z) != NONE
                    d = math.hypot(x - cx, z - cz)
                    ang = math.atan2(z - cz, x - cx)
                    if above:
                        a.set(x, y, z, theme.floor_at(x, z, d, ang))
                    elif below and theme.ceiling and d <= hl["r"] + 1 and y > fy + hl["wall_h"]:
                        a.set(x, y, z, theme.ceiling)
                    elif theme.light_rate and noise(x, y, z, 3) < theme.light_rate and y % 4 == 2:
                        a.set(x, y, z, theme.light)
                    else:
                        a.set(x, y, z, theme.wall(x, y, z))
    if theme.island:                         # an island of end stone under the arena
        for x in range(Wd):
            for z in range(Dd):
                d = math.hypot(x - cx, z - cz)
                depth = int((Wd / 2 - 4 - d) * 0.7 + 3 * noise(x, 0, z, 4))
                if d > Wd / 2 - 4:
                    continue
                for y in range(max(0, fy - 3 - depth), fy - 2):
                    if a.get(x, y, z) == VOID:
                        a.set(x, y, z, theme.island)
    # hall pillars
    for k in range(8):
        ang = k * math.pi / 4 + math.pi / 8
        px, pz = int(round(cx + (hl["r"] - 2.5) * math.cos(ang))), int(round(cz + (hl["r"] - 2.5) * math.sin(ang)))
        for y in range(fy, fy + hl["wall_h"] + 2):
            if plan.get(px, y, pz) != NONE:
                a.set(px, y, pz, theme.pillar, {"pillar_axis": "y"} if theme.pillar.endswith(("log", "basalt", "pillar")) else None)
        a.set(px, fy, pz, theme.accent)
    # rooms
    for kind, rx, ry, rz, r, ang in rooms:
        face = ["south", "west", "north", "east"][int(((ang + math.pi / 4) % (2 * math.pi)) / (math.pi / 2)) % 4]
        if kind == "vault":
            for t in range(3):
                q = ang + math.pi + (t - 1) * 0.6
                chest(a, int(round(rx + (r - 1.5) * math.cos(q))), ry, int(round(rz + (r - 1.5) * math.sin(q))),
                      theme.loot, face)
        elif kind == "shrine":
            for y in range(ry, ry + 2):
                a.set(rx, y, rz, theme.accent)
            a.set(rx, ry + 2, rz, theme.light if theme.light not in ("minecraft:end_rod",) else "minecraft:end_rod")
            chest(a, rx + 1, ry, rz, theme.loot, "east")
        elif kind == "library":
            for q in range(16):
                t = ang + math.pi + (q - 8) * 0.25
                x, z = int(round(rx + (r - 1) * math.cos(t))), int(round(rz + (r - 1) * math.sin(t)))
                for y in range(ry, ry + 3):
                    if plan.get(x, y, z) == OPEN:
                        a.set(x, y, z, "minecraft:bookshelf")
            a.set(rx, ry, rz, "minecraft:enchanting_table")
        elif kind == "armory":
            a.set(rx, ry, rz, "minecraft:anvil", {"minecraft:cardinal_direction": "north", "damage": "undamaged"})
            a.set(rx + 1, ry, rz + 1, "minecraft:smithing_table")
            chest(a, rx - 1, ry, rz, theme.loot, face)
        elif kind == "store":
            for q in range(6):
                t = ang + math.pi + (q - 3) * 0.35
                a.set(int(round(rx + (r - 1.5) * math.cos(t))), ry, int(round(rz + (r - 1.5) * math.sin(t))),
                      "minecraft:barrel", {"facing_direction": 1, "open_bit": False})
        theme.room_decor(a, plan, kind, rx, ry, rz, r)
    # the stair: a spiral of slabs round a central column, up to a trapdoor in the roof
    for y in range(sy, H - 3):
        a.set(sx, y, sz, theme.pillar, {"pillar_axis": "y"} if theme.pillar.endswith(("log", "basalt", "pillar")) else None)
        t = (y - sy) * math.pi / 4
        for rr in (1, 2):
            a.set(int(round(sx + rr * math.cos(t))), y, int(round(sz + rr * math.sin(t))), theme.accent)
    a.set(sx + 1, H - 3, sz, "minecraft:iron_trapdoor", {"direction": 0, "open_bit": False, "upside_down_bit": True})
    theme.hall_decor(a, plan, cx, fy, cz)
    # the trigger, under the middle of the hall (the boss appears above it)
    command_block(a, cx, fy - 2, cz, trigger_cmd)
    return a, (cx, fy, cz)


def build(out_dir, commands):
    """commands: theme name -> the trigger's command. Writes arena_<name>.mcstructure files."""
    out = {}
    for T in THEMES:
        th = T()
        a, centre = generate(th, commands[th.name])
        path = os.path.join(out_dir, f"teu_mobs_arena_{th.name}.mcstructure")
        os.makedirs(out_dir, exist_ok=True)
        a.save(path)
        out[th.name] = (path, th.size, centre)
    return out


if __name__ == "__main__":
    res = build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/arenas", {t.name: "say hi" for t in THEMES})
    for k, v in res.items():
        print(k, v)
