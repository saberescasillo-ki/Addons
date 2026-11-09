"""Boss arenas of TEU Mobs (1.2): one flat arena per boss, shaped as a flower, circle,
octagon, hexagon, star or pentagon. Underground and in the Nether they are closed by a
dome; in the End they are open platforms on an island of end stone.

Only blocks (and block states) that the game itself saves in structures are used, so no
block shows up as "?". A hidden repeating command block under the middle of the floor
runs teu_mobs/arena/<name> (summons the boss once and removes itself) when a player
comes near.

    from teu import arenas; arenas.build(out_dir, commands) -> {name: (path, size, centre)}
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcstructure as m  # noqa: E402
from mcstructure import Tag, byte, int_  # noqa: E402

AIR, VOID = "minecraft:air", m.STRUCTURE_VOID
# block -> the states the game saves for it (copied from structures saved by Minecraft)
STATES = {
    "minecraft:water": {"liquid_depth": 0}, "minecraft:lava": {"liquid_depth": 0},
    "minecraft:basalt": {"pillar_axis": "y"}, "minecraft:polished_basalt": {"pillar_axis": "y"},
    "minecraft:jungle_log": {"pillar_axis": "y"}, "minecraft:stripped_jungle_log": {"pillar_axis": "y"},
    "minecraft:purpur_block": {"pillar_axis": "y"}, "minecraft:purpur_pillar": {"pillar_axis": "y"},
    "minecraft:deepslate": {"pillar_axis": "y"}, "minecraft:sculk_catalyst": {"bloom": False},
    "minecraft:end_rod": {"facing_direction": 1}, "minecraft:sea_pickle": {"cluster_count": 3, "dead_bit": False},
    "minecraft:lantern": {"hanging": False}, "minecraft:soul_lantern": {"hanging": False},
    "minecraft:chain": {"pillar_axis": "y"},
}


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

    def put(self, x, y, z, name):
        self.set(x, y, z, "minecraft:" + name if ":" not in name else name,
                 STATES.get("minecraft:" + name if ":" not in name else name))

    def to_nbt(self):
        root = super().to_nbt()
        pos = root["structure"]["palette"]["default"]["block_position_data"]
        for i in self.ticking:
            pos[str(i)]["tick_queue_data"] = Tag(m.LIST, (m.COMPOUND, [{"tick_delay": int_(0)}]))
        return root


# --- shapes: radius of the arena at an angle --------------------------------------------------
def polygon(n, rot=0.0):
    def r(t):
        a = (t - rot) % (2 * math.pi / n) - math.pi / n
        return math.cos(math.pi / n) / math.cos(a)
    return r


def star(n, inner=0.62, rot=0.0):
    def r(t):
        seg = 2 * math.pi / n
        a = ((t - rot) % seg) / seg          # 0..1 across one point
        f = abs(a - 0.5) * 2                 # 1 at the valleys, 0 at the tip
        return inner + (1 - inner) * (1 - f)
    return r


def flower(n, depth=0.14):
    return lambda t: 1 - depth + depth * math.cos(n * t)


def circle():
    return lambda t: 1.0


class Theme:
    name = ""
    R = 17                       # radius of the floor
    H = 16                       # height of the dome (0: open sky)
    shape = staticmethod(circle())
    floor = "stone"
    rings = []                   # (radius, block) rings drawn on the floor
    wall = "stone"
    roof = "stone"
    light = "glowstone"
    pillar = "stone"
    pillar_top = None
    pillars = 8
    rim = 2                      # height of the low wall round an open arena
    island = None
    water = 0                    # height of water over the floor

    def floor_at(self, x, z, d, frac):
        for rr, block in self.rings:
            if abs(frac - rr) < 0.045:
                return block
        return self.floor


class Floral(Theme):
    name, R, H = "floral", 17, 15
    shape = staticmethod(flower(5))
    floor, wall, roof = "moss_block", "mossy_stone_bricks", "mossy_cobblestone"
    rings = [(0.25, "mossy_stone_bricks"), (0.55, "mossy_stone_bricks"), (0.8, "shroomlight")]
    light, pillar = "shroomlight", "jungle_log"


class Wyrm(Theme):
    name, R, H = "wyrm", 18, 18
    floor, wall, roof = "dark_prismarine", "prismarine_bricks", "prismarine"
    rings = [(0.3, "sea_lantern"), (0.6, "prismarine_bricks"), (0.85, "sea_lantern")]
    light, pillar = "sea_lantern", "prismarine_bricks"
    water = 11


class Sculk(Theme):
    name, R, H = "sculk", 17, 14
    shape = staticmethod(polygon(8, math.pi / 8))
    floor, wall, roof = "deepslate_tiles", "deepslate_bricks", "deepslate_tiles"
    rings = [(0.3, "sculk"), (0.5, "polished_deepslate"), (0.75, "sculk_catalyst")]
    light, pillar = "sculk_catalyst", "chiseled_deepslate"


class Pyrogen(Theme):
    name, R, H = "pyrogen", 17, 15
    shape = staticmethod(polygon(6))
    floor, wall, roof = "polished_blackstone", "polished_blackstone_bricks", "blackstone"
    rings = [(0.2, "magma"), (0.45, "gilded_blackstone"), (0.7, "magma"), (0.9, "gilded_blackstone")]
    light, pillar = "shroomlight", "basalt"


class Ghast(Theme):
    name, R, H = "ghast", 22, 26
    floor, wall, roof = "smooth_basalt", "basalt", "smooth_basalt"
    rings = [(0.25, "slime"), (0.5, "oxidized_cut_copper"), (0.75, "oxidized_copper")]
    light, pillar, pillars = "glowstone", "oxidized_copper", 10


class Astral(Theme):
    name, R, H = "astral", 18, 0
    shape = staticmethod(star(8))
    floor, wall, roof = "calcite", "purpur_block", "purpur_block"
    rings = [(0.3, "amethyst_block"), (0.6, "amethyst_block"), (0.85, "obsidian")]
    light, pillar, pillar_top = "glowstone", "purpur_pillar", "end_rod"
    island = "end_stone"


class Obelisk(Theme):
    name, R, H = "obelisk", 18, 0
    shape = staticmethod(polygon(5, -math.pi / 2))
    floor, wall, roof = "obsidian", "obsidian", "obsidian"
    rings = [(0.3, "crying_obsidian"), (0.6, "crying_obsidian"), (0.85, "purpur_block")]
    light, pillar, pillar_top, pillars = "glowstone", "obsidian", "end_rod", 5
    island = "end_stone"


THEMES = [Floral, Wyrm, Sculk, Pyrogen, Ghast, Astral, Obelisk]


def command_block(a, x, y, z, command):
    a.set(x, y, z, "minecraft:repeating_command_block", {"conditional_bit": False, "facing_direction": 1},
          block_entity={"id": "CommandBlock", "Command": command, "CustomName": "", "auto": byte(1),
                        "ExecuteOnFirstTick": byte(1), "LPCommandMode": int_(0), "LPCondionalMode": byte(0),
                        "LPRedstoneMode": byte(0), "TickDelay": int_(10), "TrackOutput": byte(0), "Version": int_(42),
                        "conditionMet": byte(1), "conditionalMode": byte(0), "isMovable": byte(0), "powered": byte(0),
                        "SuccessCount": int_(0), "LastOutput": "", "LastOutputParams": Tag(m.LIST, (m.END, []))})
    a.ticking.add(a._flat(x, y, z))


def generate(t, trigger_cmd):
    """-> (Arena, (centre x, floor y, centre z)); the floor's top is at y = floor y - 1."""
    R, H = t.R, t.H
    pad = 3
    W = 2 * (R + pad) + 1
    base = 4 if t.island else 2                  # blocks below the floor
    top = H + 3 if H else t.rim + 8
    size = (W, base + 1 + top, W)
    a = Arena(size)
    c = R + pad
    fy = base + 1                                # first air layer over the floor

    def frac(x, z):
        dx, dz = x - c, z - c
        d = math.hypot(dx, dz)
        lim = R * t.shape(math.atan2(dz, dx))
        return d, d / lim if lim else 9

    for x in range(W):
        for z in range(W):
            d, f = frac(x, z)
            inside = f <= 1.0
            edge = 1.0 < f <= 1.0 + 2.2 / R
            if not inside and not edge:
                if t.island and f <= 1.0 + 2.2 / R:
                    pass
                continue
            # floor (two layers) and what lies under it
            for y in range(base - 1, fy):
                a.put(x, y, z, t.floor_at(x, z, d, f) if (inside and y == fy - 1) else t.wall)
            if inside:
                # air (or water) up to the dome
                for y in range(fy, fy + (H if H else top - 1)):
                    hmax = H * math.sqrt(max(0.0, 1 - min(1.0, f) ** 2 * 0.55)) if H else top - 1
                    if y - fy < hmax:
                        a.put(x, y, z, "water" if y - fy < t.water else "air")
                    elif H:
                        a.put(x, y, z, t.roof)
                        if y - fy <= hmax + 1:
                            pass
                        break
                if H:      # a second roof layer
                    hmax = H * math.sqrt(max(0.0, 1 - min(1.0, f) ** 2 * 0.55))
                    yy = fy + int(math.ceil(hmax))
                    if yy + 1 < size[1]:
                        a.put(x, yy + 1, z, t.roof)
                    if noise(x, 0, z, 8) < 0.06 and yy < size[1]:
                        a.put(x, yy, z, t.light)
            else:
                # the wall round the floor: up to the dome, or a low rim in the open
                hw = int(H * math.sqrt(0.45)) + 2 if H else t.rim
                for y in range(fy, fy + hw):
                    a.put(x, y, z, t.light if (H and (y - fy) % 5 == 3 and noise(x, y, z, 2) < 0.35) else t.wall)
    # pillars at the corners / round the edge
    for k in range(t.pillars):
        ang = k * 2 * math.pi / t.pillars + (-math.pi / 2 if t.pillars == 5 else math.pi / t.pillars)
        rr = R * t.shape(ang) - 2.5
        px, pz = int(round(c + rr * math.cos(ang))), int(round(c + rr * math.sin(ang)))
        ph = int(H * 0.55) if H else 6
        for y in range(fy, fy + ph):
            if a.get(px, y, pz) in (AIR, "minecraft:water"):
                a.put(px, y, pz, t.pillar)
        if t.pillar_top:
            a.put(px, fy + ph, pz, t.pillar_top)
    # island of end stone under an open arena
    if t.island:
        for x in range(W):
            for z in range(W):
                d, f = frac(x, z)
                if f > 1.0 + 2.2 / R:
                    continue
                depth = int((1.1 - f) * 9 + 3 * noise(x, 0, z, 4)) + 1
                for y in range(max(0, base - 1 - depth), base - 1):
                    a.put(x, y, z, t.island)
    # the trigger, under the middle of the floor (the boss appears above it)
    command_block(a, c, fy - 2, c, trigger_cmd)
    return a, (c, fy, c)


def build(out_dir, commands):
    out = {}
    os.makedirs(out_dir, exist_ok=True)
    for T in THEMES:
        th = T()
        a, centre = generate(th, commands[th.name])
        path = os.path.join(out_dir, f"teu_mobs_arena_{th.name}.mcstructure")
        a.save(path)
        out[th.name] = (path, a.size, centre)
    return out


if __name__ == "__main__":
    res = build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/arenas", {t.name: "say hi" for t in THEMES})
    for k, v in res.items():
        print(k, v)
