// Mazmorras del Abismo: dungeon generator.
// Plain JavaScript with no game imports, so the same code builds the dungeon in
// the game (scripts/main.js) and the simulation (tools/abismo/simulate.mjs).
//
// The dimension is one endless dungeon of 10x10 rooms on 3 floors. Rooms share
// their walls, so a new room starts every 11 blocks. Room (rx, rz) has its inside
// at x = rx*11-4 .. rx*11+5 (and the same for z); room (0, 0) of the top floor is
// the entrance hall, centred on x = z = 0.5. The world is built one region of
// 8x8 rooms (all floors) at a time. buildRegion() returns block operations:
//   ["f", x1, y1, z1, x2, y2, z2, block]   fill a box
//   ["s", x, y, z, block]                  set one block
//   ["c", x, y, z, block, items]           chest with items [[id, count], ...]

export const PITCH = 11;           // 10 inside + 1 shared wall
export const INNER = 10;
export const REGION = 8;           // rooms per region side
export const FLOORS = [72, 64, 56]; // floor block of each floor: piso 1 (top), 2 and 3
export const HEIGHT = 6;           // air above the floor; the ceiling is at floor + 7
export const ROOF = 80, BOTTOM = 55;
export const SPAWN = { x: 0.5, y: FLOORS[0] + 1, z: 0.5 };

export const roomOf = (v) => Math.floor((v + 5) / PITCH);
export const regionOf = (r) => Math.floor(r / REGION);
export const inner0 = (r) => r * PITCH - 4;
export function floorOf(y) {
  for (let f = 0; f < FLOORS.length; f++) if (y > FLOORS[f] && y <= FLOORS[f] + 7) return f;
  return -1;
}

// ------------------------------------------------------------ random
function hash(...n) {
  let h = 2166136261 >>> 0;
  for (const v of n) {
    h = Math.imul(h ^ (v | 0), 16777619);
    h ^= h >>> 13;
    h = Math.imul(h, 0x5bd1e995);
    h ^= h >>> 15;
  }
  return h >>> 0;
}
const unit = (...n) => hash(...n) / 4294967296;

function makeRng(...n) {
  let a = hash(...n);
  const next = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (lo, hi) => lo + Math.floor(next() * (hi - lo + 1)),
    chance: (p) => next() < p,
    pick: (arr) => arr[Math.floor(next() * arr.length)],
    weighted(list) {
      let total = 0;
      for (const [, w] of list) total += w;
      let k = next() * total;
      for (const [v, w] of list) if ((k -= w) < 0) return v;
      return list[list.length - 1][0];
    },
  };
}

// ------------------------------------------------------------ blocks
const mc = (id) => `minecraft:${id}`;
const st = (id, states) => ({ id: `minecraft:${id}`, states });
const B = {
  air: mc("air"), reinforced: mc("reinforced_deepslate"),
  bricks: mc("deepslate_bricks"), cracked: mc("cracked_deepslate_bricks"), tiles: mc("deepslate_tiles"),
  crackedTiles: mc("cracked_deepslate_tiles"), polished: mc("polished_deepslate"), chiseled: mc("chiseled_deepslate"),
  cobbled: mc("cobbled_deepslate"), deepslate: mc("deepslate"),
  sculk: mc("sculk"), lava: mc("lava"), web: mc("web"), bookshelf: mc("bookshelf"), bars: mc("iron_bars"),
  slab: st("polished_deepslate_slab", { "minecraft:vertical_half": "bottom" }),
  cobbledSlab: st("cobbled_deepslate_slab", { "minecraft:vertical_half": "bottom" }),
  barrel: st("barrel", { facing_direction: 1, open_bit: false }),
  lantern: st("soul_lantern", { hanging: false }), hanging: st("soul_lantern", { hanging: true }),
  stairsDown: st("deepslate_brick_stairs", { weirdo_direction: 1, upside_down_bit: false }),
};
const candle = (n) => st("candle", { candles: n, lit: true });
const WALL_MIX = [[B.cracked, 5], [B.tiles, 3], [B.polished, 1], [B.crackedTiles, 2], [B.cobbled, 2]];

// ------------------------------------------------------------ loot (deeper floors, better loot)
const LOOT = [
  // id, min, max, weight, first floor
  ["bone", 2, 8, 14, 0], ["rotten_flesh", 2, 6, 12, 0], ["arrow", 4, 12, 10, 0], ["coal", 3, 9, 10, 0],
  ["iron_ingot", 1, 5, 12, 0], ["bread", 1, 4, 8, 0], ["string", 2, 6, 8, 0], ["candle", 1, 3, 5, 0],
  ["gold_ingot", 1, 4, 8, 1], ["redstone", 3, 9, 7, 1], ["lapis_lazuli", 3, 9, 6, 1], ["saddle", 1, 1, 3, 0],
  ["name_tag", 1, 1, 3, 0], ["iron_horse_armor", 1, 1, 3, 1], ["golden_apple", 1, 1, 3, 1],
  ["diamond", 1, 3, 3, 1], ["emerald", 1, 4, 4, 1], ["amethyst_shard", 2, 6, 4, 1], ["echo_shard", 1, 2, 2, 2],
  ["diamond_horse_armor", 1, 1, 1, 2], ["music_disc_otherside", 1, 1, 1, 2], ["disc_fragment_5", 1, 3, 2, 2],
  ["enchanted_golden_apple", 1, 1, 1, 2], ["netherite_scrap", 1, 1, 1, 2], ["experience_bottle", 2, 8, 4, 1],
];

function lootFor(rng, f, stacks) {
  const table = LOOT.filter((l) => l[4] <= f).map((l) => [l, l[3] * (1 + 0.4 * f * l[4])]);
  const items = [];
  for (let i = 0; i < stacks; i++) {
    const [id, lo, hi] = rng.weighted(table);
    items.push([mc(id), rng.int(lo, hi)]);
  }
  return items;
}

// ------------------------------------------------------------ layout
// Directions: 0 east (+x), 1 west, 2 south (+z), 3 north
const DX = [1, -1, 0, 0], DZ = [0, 0, 1, -1], OPP = [1, 0, 3, 2];

function arenaOfBlock(seed, bx, bz) {
  if (unit(seed, bx, bz, 77) >= 0.7) return null;
  const ax = bx * REGION + 1 + (hash(seed, bx, bz, 78) % 5), az = bz * REGION + 1 + (hash(seed, bx, bz, 79) % 5);
  return { ax, az, key: `${bx}:${bz}` };
}

// The boss arena (2x2 rooms) a room of floor 3 belongs to, or null.
export function arenaAt(seed, f, rx, rz) {
  if (f !== 2) return null;
  const a = arenaOfBlock(seed, regionOf(rx), regionOf(rz));
  if (!a || rx < a.ax || rx > a.ax + 1 || rz < a.az || rz > a.az + 1) return null;
  return { ...a, cx: (a.ax + 1) * PITCH - 5 + 0.5, cz: (a.az + 1) * PITCH - 5 + 0.5, y: FLOORS[2] + 1 };
}

const FORCED_STAIRS = new Set(["0:2:0", "1:-2:0"]);
const NO_STAIRS = new Set(["0:-2:0", "0:0:0"]);

export function stairDown(seed, f, rx, rz) {
  if (f < 0 || f >= FLOORS.length - 1) return false;
  const k = `${f}:${rx}:${rz}`;
  if (FORCED_STAIRS.has(k)) return true;
  if (NO_STAIRS.has(k) || arenaAt(seed, f + 1, rx, rz)) return false;
  if (stairDown(seed, f - 1, rx, rz)) return false; // the stairs from above land here
  return unit(seed, f, rx, rz, 31) < 0.075;
}

function primary(seed, f, rx, rz) {
  return hash(seed, f, rx, rz, 11) % 4;
}

// "wall", "door" or "open" (inside a boss arena) for the side `dir` of a room.
export function edge(seed, f, rx, rz, dir) {
  const nx = rx + DX[dir], nz = rz + DZ[dir];
  const a1 = arenaAt(seed, f, rx, rz), a2 = arenaAt(seed, f, nx, nz);
  if (a1 && a2 && a1.key === a2.key) return "open";
  if (f === 0 && ((rx === 0 && rz === 0) || (nx === 0 && nz === 0))) return "door";
  const [ax, az, axis] = dir === 0 ? [rx, rz, 0] : dir === 1 ? [nx, nz, 0] : dir === 2 ? [rx, rz, 1] : [nx, nz, 1];
  if (unit(seed, f, ax, az, axis, 5) < 0.5) return "door";
  if (primary(seed, f, rx, rz) === dir || primary(seed, f, nx, nz) === OPP[dir]) return "door";
  return "wall";
}

const TYPES = [
  // type, weight on floors 1, 2, 3
  ["salon", [18, 14, 10]], ["pilares", [16, 14, 12]], ["celdas", [10, 10, 9]], ["cripta", [8, 12, 14]],
  ["biblioteca", [7, 5, 3]], ["almacen", [9, 7, 5]], ["derrumbe", [8, 10, 12]], ["foso", [2, 5, 8]],
  ["santuario", [3, 4, 5]], ["sculk", [1, 5, 12]],
];

export function roomType(seed, f, rx, rz) {
  if (f === 0 && rx === 0 && rz === 0) return "vestibulo";
  if (arenaAt(seed, f, rx, rz)) return "arena";
  if (stairDown(seed, f, rx, rz)) return "escalera";
  const rng = makeRng(seed, f, rx, rz, 9);
  return rng.weighted(TYPES.map(([t, w]) => [t, w[f]]));
}

// ------------------------------------------------------------ building
function makeCtx(gx, gz) {
  const minX = gx * REGION * PITCH - 5, maxX = (gx + 1) * REGION * PITCH - 5;
  const minZ = gz * REGION * PITCH - 5, maxZ = (gz + 1) * REGION * PITCH - 5;
  const ctx = {
    ops: [], info: [], minX, maxX, minZ, maxZ,
    fill(x1, y1, z1, x2, y2, z2, b) {
      ctx.ops.push(["f", Math.min(x1, x2), Math.min(y1, y2), Math.min(z1, z2), Math.max(x1, x2), Math.max(y1, y2), Math.max(z1, z2), b]);
    },
    set(x, y, z, b) {
      ctx.ops.push(["s", x, y, z, b]);
    },
    chest(x, y, z, face, items) {
      ctx.ops.push(["c", x, y, z, st("chest", { "minecraft:cardinal_direction": face }), items]);
    },
  };
  return ctx;
}

const FACE = ["east", "west", "south", "north"];

function room(ctx, seed, f, rx, rz) {
  const x0 = inner0(rx), z0 = inner0(rz), y = FLOORS[f];
  const rng = makeRng(seed, f, rx, rz, 3);
  const type = roomType(seed, f, rx, rz);
  const arrival = stairDown(seed, f - 1, rx, rz);
  const at = (i, j) => [x0 + i, z0 + j];
  const set = (i, dy, j, b) => ctx.set(x0 + i, y + dy, z0 + j, b);
  const fillIn = (i1, dy1, j1, i2, dy2, j2, b) => ctx.fill(x0 + i1, y + dy1, z0 + j1, x0 + i2, y + dy2, z0 + j2, b);
  // the stairs (from this room down, or from the room above) take the two rows along the north wall
  const reserved = (i, j) => (type === "escalera" || arrival) && j <= 2;
  const free = (i, j) => !reserved(i, j);

  // shell: floor, ceiling and the four walls
  ctx.fill(x0 - 1, y, z0 - 1, x0 + INNER, y, z0 + INNER, B.tiles);
  ctx.fill(x0 - 1, y + 7, z0 - 1, x0 + INNER, y + 7, z0 + INNER, B.bricks);
  ctx.fill(x0 - 1, y + 1, z0 - 1, x0 + INNER, y + 6, z0 - 1, B.bricks);
  ctx.fill(x0 - 1, y + 1, z0 + INNER, x0 + INNER, y + 6, z0 + INNER, B.bricks);
  ctx.fill(x0 - 1, y + 1, z0, x0 - 1, y + 6, z0 + INNER - 1, B.bricks);
  ctx.fill(x0 + INNER, y + 1, z0, x0 + INNER, y + 6, z0 + INNER - 1, B.bricks);
  for (let n = rng.int(10, 18); n > 0; n--) {
    const side = rng.int(0, 3), k = rng.int(-1, INNER), h = rng.int(1, 6);
    const [x, z] = side === 0 ? [x0 + INNER, z0 + k] : side === 1 ? [x0 - 1, z0 + k] : side === 2 ? [x0 + k, z0 + INNER] : [x0 + k, z0 - 1];
    ctx.set(x, y + h, z, rng.weighted(WALL_MIX));
  }
  for (let n = rng.int(6, 14); n > 0; n--) set(rng.int(0, 9), 0, rng.int(0, 9), rng.pick([B.crackedTiles, B.polished, B.cobbled]));

  // doors (4 wide, 4 high) with a polished frame
  for (let d = 0; d < 4; d++) {
    const kind = edge(seed, f, rx, rz, d);
    if (kind === "wall") continue;
    const line = (k) => d === 0 ? [x0 + INNER, z0 + k] : d === 1 ? [x0 - 1, z0 + k] : d === 2 ? [x0 + k, z0 + INNER] : [x0 + k, z0 - 1];
    if (kind === "open") {
      const [a, b] = line(0), [c, e] = line(INNER - 1);
      ctx.fill(a, y + 1, b, c, y + 6, e, B.air);
      continue;
    }
    for (const k of [2, 7]) {
      const [x, z] = line(k);
      ctx.fill(x, y + 1, z, x, y + 5, z, B.polished);
    }
    for (let k = 3; k <= 6; k++) {
      const [x, z] = line(k);
      ctx.set(x, y + 5, z, B.chiseled);
    }
    const [a, b] = line(3), [c, e] = line(6);
    ctx.fill(a, y + 1, b, c, y + 4, e, B.air);
  }

  // the room's own content
  const doorWalls = [0, 1, 2, 3].filter((d) => edge(seed, f, rx, rz, d) !== "wall");
  const quietWall = [2, 0, 1, 3].find((d) => !doorWalls.includes(d) && !(d === 3 && (type === "escalera" || arrival)));
  const cobwebs = (p) => {
    for (const [i, j] of [[0, 0], [9, 0], [0, 9], [9, 9]]) if (free(i, j) && rng.chance(p)) set(i, 6, j, B.web);
  };
  const lootChest = (i, j, dy, face) => ctx.chest(x0 + i, y + dy, z0 + j, face, lootFor(rng, f, rng.int(3, 7)));

  switch (type) {
    case "vestibulo": {
      for (let i = 0; i < INNER; i++) for (let j = 0; j < INNER; j++) {
        const d = Math.hypot(i - 4.5, j - 4.5);
        set(i, 0, j, d < 1.6 ? B.chiseled : d < 3 ? B.polished : d < 4.2 ? B.bricks : B.tiles);
      }
      for (const [i, j] of [[1, 1], [8, 1], [1, 8], [8, 8]]) { set(i, 1, j, B.chiseled); set(i, 2, j, B.lantern); }
      set(4, 6, 4, B.hanging);
      set(5, 6, 5, B.hanging);
      break;
    }
    case "escalera": {
      // from the floor of this room down to the floor below, going east
      for (let i = 1; i <= 8; i++) {
        ctx.fill(x0 + i, y - i + 1, z0, x0 + i, y + 1, z0 + 1, B.air);
        if (i <= 7) {
          ctx.fill(x0 + i, y - i, z0, x0 + i, y - i, z0 + 1, B.stairsDown);
          if (y - i - 1 >= y - 7) ctx.fill(x0 + i, y - 7, z0, x0 + i, y - i - 1, z0 + 1, B.bricks);
        }
      }
      for (let i = 1; i <= 8; i++) set(i, 0, 2, B.polished);
      set(9, 1, 2, B.chiseled);
      set(9, 2, 2, B.lantern);
      set(5, 6, 6, B.hanging);
      break;
    }
    case "arena": {
      const a = arenaAt(seed, f, rx, rz);
      const ci = (a.ax + 1) * PITCH - 5 - x0, cj = (a.az + 1) * PITCH - 5 - z0; // the arena centre in room coordinates
      for (let i = 0; i < INNER; i++) for (let j = 0; j < INNER; j++) {
        const d = Math.hypot(i + 0.5 - ci, j + 0.5 - cj);
        set(i, 0, j, Math.floor(d) % 4 === 0 ? B.chiseled : d < 6 ? B.polished : rng.chance(0.2) ? B.crackedTiles : B.tiles);
      }
      set(4, 6, 4, B.hanging);
      if (rx === a.ax && rz === a.az) ctx.info.push(`arena del jefe ${a.key}`);
      break;
    }
    case "pilares": {
      for (const [i, j] of [[2, 2], [2, 7], [7, 2], [7, 7]]) {
        if (!free(i, j)) continue;
        fillIn(i, 1, j, i, 6, j, B.polished);
        set(i, 1, j, B.chiseled);
        set(i, 6, j, B.chiseled);
      }
      if (rng.chance(0.5)) set(4, 6, 5, B.hanging);
      cobwebs(0.3);
      break;
    }
    case "celdas": {
      if (quietWall === undefined) { cobwebs(0.5); break; }
      // three cells against the quiet wall, closed with iron bars
      for (let k = 0; k < INNER; k++) for (let depth = 0; depth <= 3; depth++) {
        const [i, j] = quietWall === 0 ? [9 - depth, k] : quietWall === 1 ? [depth, k] : quietWall === 2 ? [k, 9 - depth] : [k, depth];
        if (!free(i, j)) continue;
        const partition = k === 3 || k === 6;
        if (depth === 3) fillIn(i, 1, j, i, 6, j, partition ? B.polished : B.bars);
        else if (partition) fillIn(i, 1, j, i, 6, j, B.polished);
        else if (depth === 0 && rng.chance(0.25)) set(i, 6, j, B.web);
      }
      if (rng.chance(0.15)) {
        const [i, j] = quietWall === 0 ? [9, 1] : quietWall === 1 ? [0, 1] : quietWall === 2 ? [1, 9] : [1, 0];
        if (free(i, j)) lootChest(i, j, 1, FACE[OPP[quietWall]]);
      }
      set(4, 6, 4, B.hanging);
      break;
    }
    case "cripta": {
      // stone coffins with candles
      const n = rng.int(2, 3);
      for (let c = 0; c < n; c++) {
        const i = 1 + c * 3, j0 = rng.int(3, 4);
        if (!free(i, j0)) continue;
        fillIn(i, 1, j0, i + 1, 1, j0 + 2, B.polished);
        fillIn(i, 2, j0, i + 1, 2, j0 + 2, B.slab);
        if (rng.chance(0.7)) set(i, 3, j0, candle(rng.int(0, 3)));
      }
      if (rng.chance(0.2) && free(8, 8)) lootChest(8, 8, 1, "west");
      cobwebs(0.4);
      break;
    }
    case "biblioteca": {
      for (const d of [0, 1, 2, 3]) {
        if (doorWalls.includes(d)) continue;
        for (let k = 1; k < 9; k++) {
          const [i, j] = d === 0 ? [9, k] : d === 1 ? [0, k] : d === 2 ? [k, 9] : [k, 0];
          if (free(i, j)) fillIn(i, 1, j, i, 3, j, B.bookshelf);
        }
      }
      if (free(4, 4)) {
        fillIn(4, 1, 4, 5, 1, 5, B.polished);
        fillIn(4, 2, 4, 5, 2, 5, B.slab);
        set(4, 3, 4, candle(rng.int(1, 3)));
      }
      set(4, 6, 4, B.hanging);
      cobwebs(0.5);
      break;
    }
    case "almacen": {
      for (const [ci, cj] of [[1, 1], [8, 8], [1, 8], [8, 1]]) {
        if (!rng.chance(0.75)) continue;
        for (let n = rng.int(2, 5); n > 0; n--) {
          const i = ci + rng.int(-1, 1), j = cj + rng.int(-1, 1);
          if (i < 0 || i > 9 || j < 0 || j > 9 || !free(i, j)) continue;
          fillIn(i, 1, j, i, rng.int(1, 2), j, B.barrel);
        }
      }
      if (rng.chance(0.35) && free(5, 8)) lootChest(5, 8, 1, "north");
      cobwebs(0.3);
      break;
    }
    case "derrumbe": {
      for (let n = rng.int(3, 6); n > 0; n--) {
        const ci = rng.int(1, 8), cj = rng.int(1, 8);
        for (let i = ci - 2; i <= ci + 2; i++) for (let j = cj - 2; j <= cj + 2; j++) {
          if (i < 0 || i > 9 || j < 0 || j > 9 || !free(i, j)) continue;
          const d = Math.hypot(i - ci, j - cj);
          if (d < 1.2) set(i, 1, j, rng.chance(0.6) ? B.cobbled : B.deepslate);
          else if (d < 2.2 && rng.chance(0.6)) set(i, 1, j, B.cobbledSlab);
        }
      }
      for (let n = rng.int(2, 5); n > 0; n--) set(rng.int(0, 9), 6, rng.int(0, 9), B.cracked);
      cobwebs(0.6);
      break;
    }
    case "foso": {
      for (let i = 3; i <= 6; i++) for (let j = 3; j <= 6; j++) if (free(i, j)) set(i, 0, j, B.lava);
      for (let i = 2; i <= 7; i++) for (let j = 2; j <= 7; j++)
        if ((i === 2 || i === 7 || j === 2 || j === 7) && free(i, j)) set(i, 0, j, B.polished);
      break;
    }
    case "santuario": {
      if (!free(3, 3)) { set(4, 6, 4, B.hanging); break; }
      fillIn(3, 1, 3, 5, 1, 5, B.polished);
      set(4, 1, 4, B.chiseled);
      lootChest(4, 4, 2, "south");
      for (const [i, j] of [[3, 3], [5, 3], [3, 5], [5, 5]]) set(i, 2, j, candle(rng.int(0, 3)));
      for (const [i, j] of [[1, 1], [8, 1], [1, 8], [8, 8]]) if (free(i, j)) { set(i, 1, j, B.chiseled); set(i, 2, j, B.lantern); }
      break;
    }
    case "sculk": {
      for (let n = rng.int(3, 6); n > 0; n--) {
        const ci = rng.int(0, 9), cj = rng.int(0, 9), r = rng.int(1, 3);
        for (let i = ci - r; i <= ci + r; i++) for (let j = cj - r; j <= cj + r; j++)
          if (i >= 0 && i <= 9 && j >= 0 && j <= 9 && Math.hypot(i - ci, j - cj) <= r && rng.chance(0.85)) set(i, 0, j, B.sculk);
      }
      if (rng.chance(0.5)) set(4, 6, 4, B.hanging);
      break;
    }
    default: { // salon
      for (let i = 0; i < INNER; i++) for (let j = 0; j < INNER; j++) if ((i + j) % 2 === 0) set(i, 0, j, B.polished);
      if (rng.chance(0.6)) set(4, 6, 4, B.hanging);
      cobwebs(0.35);
    }
  }
  return type;
}

export function buildRegion(gx, gz, seed) {
  const ctx = makeCtx(gx, gz);
  const r0x = gx * REGION, r0z = gz * REGION;
  ctx.fill(ctx.minX, BOTTOM, ctx.minZ, ctx.maxX, BOTTOM, ctx.maxZ, B.reinforced);
  ctx.fill(ctx.minX, ROOF, ctx.minZ, ctx.maxX, ROOF, ctx.maxZ, B.reinforced);
  const counts = {};
  // bottom floor first, so the stairs of the floor above cut through its ceiling
  for (let f = FLOORS.length - 1; f >= 0; f--)
    for (let rx = r0x; rx < r0x + REGION; rx++)
      for (let rz = r0z; rz < r0z + REGION; rz++) {
        const t = room(ctx, seed, f, rx, rz);
        counts[t] = (counts[t] ?? 0) + 1;
      }
  return { ops: ctx.ops, info: ctx.info, counts, bounds: [ctx.minX, ctx.minZ, ctx.maxX, ctx.maxZ] };
}
