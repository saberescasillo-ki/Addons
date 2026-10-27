// The LITIUS Blind: island generator.
// Plain JavaScript with no game imports, so the same code builds the islands in
// the game (scripts/main.js) and the 4x4-chunk simulation (tools/litius_blind/simulate.mjs).
//
// The dimension is split into cells of 4x4 chunks (64x64 blocks). Each cell holds
// one upper island or group of islands (y >= 80) and, most of the time, one lower
// island (y 20..50). buildCell() returns the list of block operations of a cell:
//   ["f", x1, y1, z1, x2, y2, z2, block]   fill a box
//   ["s", x, y, z, block]                  set one block
//   ["c", x, y, z, block, items]           chest with items [[id, count], ...]
// A block is an id string or { id, states }.

export const CELL = 64;            // one cell = 4x4 chunks
export const HALF = CELL / 2;      // cell (cx, cz) spans x in [cx*64-32, cx*64+31]
export const MARGIN = 16;          // nothing of a cell reaches further than this outside it
export const UPPER_MIN = 80;       // upper islands: y 80 and up
export const LOWER_MIN = 20;       // lower islands: y 20..50
export const LOWER_MAX = 50;
export const MAIN_TOP = 100;       // the plaza of the main island
export const SPAWN = { x: 0.5, y: MAIN_TOP + 1, z: 7.5 };

export function cellOf(v) {
  return Math.floor((v + HALF) / CELL);
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

function makeRng(...n) {
  let a = hash(...n);
  const next = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const r = {
    next,
    range: (lo, hi) => lo + (hi - lo) * next(),
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
    shuffle(arr) {
      const out = arr.slice();
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
      }
      return out;
    },
  };
  return r;
}

// Smooth value noise in 0..1.
function noise2(seed, x, z) {
  const x0 = Math.floor(x), z0 = Math.floor(z);
  const fx = x - x0, fz = z - z0;
  const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
  const a = hash(seed, x0, z0) / 4294967296, b = hash(seed, x0 + 1, z0) / 4294967296;
  const c = hash(seed, x0, z0 + 1) / 4294967296, d = hash(seed, x0 + 1, z0 + 1) / 4294967296;
  return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
}

function fbm(seed, x, z, octaves = 3) {
  let sum = 0, amp = 1, total = 0, f = 1;
  for (let i = 0; i < octaves; i++) {
    sum += noise2(seed + i * 101, x * f, z * f) * amp;
    total += amp;
    amp *= 0.5;
    f *= 2;
  }
  return sum / total;
}

const key2 = (x, z) => `${x},${z}`;
const key3 = (x, y, z) => `${x},${y},${z}`;

// ------------------------------------------------------------ blocks
const st = (id, states) => ({ id: `minecraft:${id}`, states });
const mc = (id) => `minecraft:${id}`;
const B = {
  air: mc("air"), stone: mc("stone"), andesite: mc("andesite"), cobble: mc("cobblestone"),
  mossyCobble: mc("mossy_cobblestone"), dirt: mc("dirt"), grass: mc("grass_block"), moss: mc("moss_block"),
  rootedDirt: mc("dirt_with_roots"), sand: mc("sand"), sandstone: mc("sandstone"), gravel: mc("gravel"),
  clay: mc("clay"), water: mc("water"), lava: mc("lava"),
  bricks: mc("stone_bricks"), mossyBricks: mc("mossy_stone_bricks"), crackedBricks: mc("cracked_stone_bricks"),
  chiseledBricks: mc("chiseled_stone_bricks"),
  deepslate: mc("deepslate"), cobbledDeep: mc("cobbled_deepslate"), polishedDeep: mc("polished_deepslate"),
  deepBricks: mc("deepslate_bricks"), crackedDeepBricks: mc("cracked_deepslate_bricks"),
  deepTiles: mc("deepslate_tiles"), crackedDeepTiles: mc("cracked_deepslate_tiles"),
  chiseledDeep: mc("chiseled_deepslate"),
  shortGrass: mc("short_grass"), fern: mc("fern"), mossCarpet: mc("moss_carpet"), azalea: mc("azalea"),
  floweringAzalea: mc("flowering_azalea"), lily: mc("waterlily"), web: mc("web"),
  hangingRoots: mc("hanging_roots"), mangroveRoots: mc("mangrove_roots"),
  tallGrassLow: st("tall_grass", { upper_block_bit: false }), tallGrassHigh: st("tall_grass", { upper_block_bit: true }),
  lantern: st("lantern", { hanging: false }), lanternHanging: st("lantern", { hanging: true }),
  soulLantern: st("soul_lantern", { hanging: false }), soulLanternHanging: st("soul_lantern", { hanging: true }),
};
const FLOWERS = ["poppy", "dandelion", "cornflower", "oxeye_daisy", "azure_bluet", "allium", "lily_of_the_valley"].map(mc);
const WOOD = {
  oak: { log: "minecraft:oak_log", leaves: st("oak_leaves", { persistent_bit: true }) },
  birch: { log: "minecraft:birch_log", leaves: st("birch_leaves", { persistent_bit: true }) },
};
const UPPER_ORES = [["coal_ore", 40], ["iron_ore", 26], ["copper_ore", 16], ["gold_ore", 7], ["lapis_ore", 5],
  ["redstone_ore", 4], ["diamond_ore", 1.5], ["emerald_ore", 0.5]].map(([id, w]) => [mc(id), w]);
const LOWER_ORES = [["deepslate_coal_ore", 22], ["deepslate_iron_ore", 26], ["deepslate_copper_ore", 12],
  ["deepslate_gold_ore", 14], ["deepslate_lapis_ore", 9], ["deepslate_redstone_ore", 11],
  ["deepslate_diamond_ore", 4], ["deepslate_emerald_ore", 2]].map(([id, w]) => [mc(id), w]);

// Directions: stairs ascend towards the direction they face (weirdo_direction).
const DIRS = [
  { dx: 1, dz: 0, stair: 0, face: "east" },
  { dx: -1, dz: 0, stair: 1, face: "west" },
  { dx: 0, dz: 1, stair: 2, face: "south" },
  { dx: 0, dz: -1, stair: 3, face: "north" },
];
const opposite = (d) => DIRS.find((o) => o.dx === -d.dx && o.dz === -d.dz);

const UPPER_LOOT = [["bread", 1, 4, 14], ["apple", 1, 3, 12], ["iron_ingot", 1, 5, 12], ["gold_ingot", 1, 3, 7],
  ["coal", 3, 10, 10], ["string", 1, 4, 8], ["bone", 2, 6, 8], ["wheat", 2, 6, 8], ["saddle", 1, 1, 4],
  ["name_tag", 1, 1, 4], ["golden_apple", 1, 1, 2], ["oak_sapling", 1, 3, 6], ["birch_sapling", 1, 3, 6],
  ["moss_block", 2, 8, 5], ["music_disc_13", 1, 1, 1], ["diamond", 1, 2, 1], ["emerald", 1, 3, 3]];
const LOWER_LOOT = [["iron_ingot", 2, 7, 14], ["gold_ingot", 1, 5, 10], ["redstone", 3, 10, 10],
  ["lapis_lazuli", 3, 9, 8], ["coal", 3, 12, 8], ["amethyst_shard", 1, 4, 6], ["diamond", 1, 3, 4],
  ["emerald", 1, 4, 4], ["golden_apple", 1, 1, 3], ["obsidian", 1, 4, 4], ["iron_horse_armor", 1, 1, 3],
  ["golden_horse_armor", 1, 1, 2], ["name_tag", 1, 1, 3], ["echo_shard", 1, 2, 1], ["music_disc_cat", 1, 1, 1]];

// ------------------------------------------------------------ build context
function makeCtx(cx, cz) {
  const minX = cx * CELL - HALF - MARGIN, maxX = cx * CELL + HALF - 1 + MARGIN;
  const minZ = cz * CELL - HALF - MARGIN, maxZ = cz * CELL + HALF - 1 + MARGIN;
  const ctx = {
    ops: [], islands: [], logs: new Set(), extra: new Set(), info: [],
    fill(x1, y1, z1, x2, y2, z2, b) {
      if (y2 < y1) return;
      const ax = Math.max(Math.min(x1, x2), minX), bx = Math.min(Math.max(x1, x2), maxX);
      const az = Math.max(Math.min(z1, z2), minZ), bz = Math.min(Math.max(z1, z2), maxZ);
      if (ax > bx || az > bz) return;
      ctx.ops.push(["f", ax, y1, az, bx, y2, bz, b]);
    },
    set(x, y, z, b) {
      if (x < minX || x > maxX || z < minZ || z > maxZ) return;
      ctx.ops.push(["s", x, y, z, b]);
    },
    chest(x, y, z, face, items) {
      if (x < minX || x > maxX || z < minZ || z > maxZ) return;
      ctx.ops.push(["c", x, y, z, st("chest", { "minecraft:cardinal_direction": face }), items]);
    },
    solidAt(x, y, z) {
      const k = key2(x, z);
      if (ctx.logs.has(key3(x, y, z)) || ctx.extra.has(key3(x, y, z))) return true;
      for (const isl of ctx.islands) {
        const c = isl.cols.get(k);
        if (c && y >= c.bottom && y <= c.top) return true;
      }
      return false;
    },
  };
  return ctx;
}

// ------------------------------------------------------------ island shapes
function newIsland(rng, layer, kind, x, z, r, extra = {}) {
  const up = layer === "up";
  const top = extra.top ?? (up ? rng.int(90, 108) : rng.int(36, 46));
  const minY = up ? UPPER_MIN : LOWER_MIN;
  const isl = {
    layer, kind, x, z, r, top, minY, maxY: up ? 250 : LOWER_MAX - 3,
    a: rng.range(0.8, 1.25), rot: rng.range(0, Math.PI),
    hill: up ? rng.int(1, 4) : rng.int(0, 2), rough: 0.36,
    seed: hash(rng.int(0, 1 << 30), x, z),
    hole: 0, cut: null, steps: 0, flat: null, style: "grass", bulk: 0.6, dungeon: false,
    cols: new Map(), trees: [], used: new Set(),
    ...extra,
  };
  isl.thick = Math.min(extra.thick ?? r * (up ? rng.range(0.75, 1.05) : rng.range(0.8, 1.1)), isl.top - minY - 1);
  if (isl.dungeon) {
    // room for a dungeon: a thicker island with a rounder underside
    isl.thick = Math.min(Math.max(isl.thick * 1.4, 16), isl.top - minY - 1);
    isl.bulk = 0.35;
  }
  return isl;
}

function shape(isl) {
  const reach = Math.ceil(isl.r * Math.max(isl.a, 1 / isl.a) * 1.25) + 2;
  const cos = Math.cos(isl.rot), sin = Math.sin(isl.rot);
  for (let x = isl.x - reach; x <= isl.x + reach; x++) {
    for (let z = isl.z - reach; z <= isl.z + reach; z++) {
      const dx = x - isl.x, dz = z - isl.z;
      const u = dx * cos + dz * sin, v = -dx * sin + dz * cos;
      let d = Math.hypot(u / (isl.r * isl.a), (v * isl.a) / isl.r);
      d += (fbm(isl.seed, x / 10, z / 10) - 0.5) * isl.rough;
      if (isl.flat) {
        const fd = Math.hypot(x - isl.flat.x, z - isl.flat.z);
        if (fd <= isl.flat.r + 1) d = Math.min(d, 0.5);
      }
      if (d >= 1) continue;
      let e = d; // 0 in the thick middle of the island, 1 at its coast
      if (isl.hole) {
        const hole = isl.hole + (fbm(isl.seed + 5, x / 6, z / 6, 2) - 0.5) * 0.18;
        if (d < hole) continue;
        e = Math.abs(d - (1 + hole) / 2) / ((1 - hole) / 2);
      }
      if (isl.cut) {
        // a chasm through the island
        const off = (dx * isl.cut.nx + dz * isl.cut.nz) + Math.sin((dx * isl.cut.nz - dz * isl.cut.nx) / 4) * 1.2;
        if (Math.abs(off) < isl.cut.w) continue;
      }
      e = Math.min(1, Math.max(0, e));
      let hill = isl.hill * (fbm(isl.seed + 7, x / 16, z / 16) - 0.3) * (1 - e);
      if (isl.steps) hill = isl.steps * Math.floor(fbm(isl.seed + 9, x / 12, z / 12) * 4) * (1 - e * 0.5);
      let top = isl.top + Math.round(hill + 2.5 * (1 - e * e) - 1);
      if (isl.flat) {
        const fd = Math.hypot(x - isl.flat.x, z - isl.flat.z);
        if (fd <= isl.flat.r) top = isl.flat.y;
        else if (fd <= isl.flat.r + 5) top = Math.round(isl.flat.y + (top - isl.flat.y) * (fd - isl.flat.r) / 5);
      }
      top = Math.min(top, isl.maxY);
      const spike = Math.max(0, noise2(isl.seed + 17, x / 2.5, z / 2.5) - 0.78) * 30 * (1 - e);
      const depth = 1 + isl.thick * Math.pow(1 - e, isl.bulk) * (0.7 + 0.6 * fbm(isl.seed + 13, x / 8, z / 8, 2)) + spike;
      const bottom = Math.min(top, Math.max(isl.minY, top - Math.round(depth)));
      isl.cols.set(key2(x, z), { x, z, top, bottom, e, surface: isl.layer === "up" ? isl.style : "deep", water: false });
    }
  }
}

function writeUpperBody(ctx, isl) {
  for (const c of isl.cols.values()) {
    const { x, z, top, bottom } = c;
    if (isl.kind === "colinas" && top >= isl.top + isl.hill * 0.55 + 1) c.surface = "stone";
    const rock = fbm(isl.seed + 31, x / 7, z / 7, 2) > 0.66 ? B.andesite : B.stone;
    const soil = c.surface === "stone" ? 0 : Math.min(top - bottom, c.surface === "moss" ? 2 : 3);
    ctx.fill(x, bottom, z, x, top - soil - 1, z, rock);
    if (soil > 0) ctx.fill(x, top - soil, z, x, top - 1, z, B.dirt);
    if (isl.roots && top - bottom >= 3) ctx.fill(x, bottom, z, x, bottom + 1, z, B.rootedDirt);
    const surf = { grass: B.grass, moss: B.moss, stone: rock === B.stone ? B.stone : B.andesite }[c.surface];
    ctx.set(x, top, z, surf);
  }
}

function deepSurface(isl, x, z) {
  const n = fbm(isl.seed + 21, x / 5, z / 5, 2);
  if (n < 0.4) return B.cobbledDeep;
  if (n < 0.6) return B.deepslate;
  if (n < 0.72) return B.polishedDeep;
  if (n < 0.82) return B.deepTiles;
  return B.crackedDeepTiles;
}

function writeLowerBody(ctx, isl) {
  for (const c of isl.cols.values()) {
    const { x, z, top, bottom } = c;
    ctx.fill(x, bottom, z, x, top - 1, z, B.deepslate);
    if (top - bottom >= 3) ctx.set(x, bottom, z, B.cobbledDeep);
    ctx.set(x, top, z, deepSurface(isl, x, z));
  }
}

function ores(ctx, rng, isl) {
  const list = isl.layer === "up" ? UPPER_ORES : LOWER_ORES;
  const cols = [...isl.cols.values()].filter((c) => c.top - c.bottom >= 6);
  if (!cols.length) return;
  const veins = Math.round(isl.r * (isl.layer === "up" ? 0.3 : 0.35));
  for (let i = 0; i < veins; i++) {
    const c = rng.pick(cols);
    const ore = rng.weighted(list);
    let x = c.x, z = c.z, y = rng.int(c.bottom + 1, c.top - 4);
    for (let n = rng.int(1, 4); n > 0; n--) {
      const cc = isl.cols.get(key2(x, z));
      if (cc && y > cc.bottom && y < cc.top - 3) ctx.set(x, y, z, ore);
      const d = rng.int(0, 2);
      if (d === 0) x += rng.pick([-1, 1]);
      else if (d === 1) z += rng.pick([-1, 1]);
      else y += rng.pick([-1, 1]);
    }
  }
}

// ------------------------------------------------------------ water and lava
// Fills the columns of `isl` within radius r of (px, pz) (or the given set of
// columns) with a fluid whose surface is at the lowest rim height, so it never spills.
function lake(ctx, isl, opts) {
  const { fluid, bed, maxDepth = 3 } = opts;
  const inside = [];
  for (const c of isl.cols.values()) {
    if (c.water || isl.used.has(key2(c.x, c.z))) continue;
    let dist;
    if (opts.columns) {
      if (!opts.columns.has(key2(c.x, c.z))) continue;
      dist = 0.3;
    } else {
      dist = Math.hypot(c.x - opts.x, c.z - opts.z) / opts.r + (fbm(isl.seed + 41, c.x / 4, c.z / 4, 2) - 0.5) * 0.4;
      if (dist >= 1) continue;
    }
    let interior = true;
    for (let dx = -1; dx <= 1 && interior; dx++)
      for (let dz = -1; dz <= 1; dz++)
        if (!isl.cols.get(key2(c.x + dx, c.z + dz))) { interior = false; break; }
    if (interior) inside.push([c, dist]);
  }
  if (inside.length < 4) return null;
  const set = new Set(inside.map(([c]) => key2(c.x, c.z)));
  const rim = [];
  let level = Infinity;
  for (const [c] of inside) {
    level = Math.min(level, c.top);
    for (let dx = -1; dx <= 1; dx++)
      for (let dz = -1; dz <= 1; dz++) {
        const k = key2(c.x + dx, c.z + dz);
        if (set.has(k)) continue;
        const n = isl.cols.get(k);
        rim.push(n);
        level = Math.min(level, n.top);
      }
  }
  const filled = [];
  for (const [c, dist] of inside) {
    let depth = Math.max(1, Math.round(maxDepth * (1 - dist * dist)));
    depth = Math.min(depth, level - c.bottom - 1);
    if (depth < 1) continue;
    if (c.top > level) ctx.fill(c.x, level + 1, c.z, c.x, c.top, c.z, B.air);
    ctx.fill(c.x, level - depth + 1, c.z, c.x, level, c.z, fluid);
    ctx.set(c.x, level - depth, c.z, bed);
    c.top = level;
    c.water = true;
    filled.push(c);
  }
  return { level, filled, rim };
}

function riverColumns(rng, isl) {
  const ang = rng.range(0, Math.PI), ca = Math.cos(ang), sa = Math.sin(ang);
  const amp = rng.range(0.12, 0.25) * isl.r, freq = rng.range(1.2, 2.2), phase = rng.range(0, 6.28);
  const width = rng.range(1.4, 2.3);
  const cols = new Set();
  for (let t = -0.8; t <= 0.8; t += 0.04) {
    const along = t * isl.r, side = Math.sin(t * Math.PI * freq + phase) * amp;
    const px = isl.x + along * ca - side * sa, pz = isl.z + along * sa + side * ca;
    for (let x = Math.floor(px - width); x <= Math.ceil(px + width); x++)
      for (let z = Math.floor(pz - width); z <= Math.ceil(pz + width); z++)
        if (Math.hypot(x - px, z - pz) <= width) cols.add(key2(x, z));
  }
  return cols;
}

function waterFeatures(ctx, rng, isl) {
  const lily = (res, p) => res && res.filled.forEach((c) => {
    if (rng.chance(p)) ctx.set(c.x, c.top + 1, c.z, B.lily);
  });
  if (isl.kind === "oasis") {
    const res = lake(ctx, isl, { x: isl.x, z: isl.z, r: Math.max(3.5, isl.r * 0.3), fluid: B.water, bed: B.sand, maxDepth: 3 });
    lily(res, 0.1);
    for (const c of isl.cols.values()) {
      if (c.water || Math.hypot(c.x - isl.x, c.z - isl.z) > isl.r * 0.5) continue;
      c.surface = "sand";
      ctx.set(c.x, c.top, c.z, B.sand);
      if (c.top - 1 > c.bottom) ctx.set(c.x, c.top - 1, c.z, B.sandstone);
    }
  } else if (isl.kind === "rio") {
    const res = lake(ctx, isl, { columns: riverColumns(rng, isl), fluid: B.water, bed: B.gravel, maxDepth: 2 });
    if (res) for (const c of res.rim) if (c.surface === "grass" && !c.water && rng.chance(0.35)) {
      c.surface = "sand";
      ctx.set(c.x, c.top, c.z, B.sand);
    }
  } else if (isl.kind === "lagunas") {
    for (let i = rng.int(2, 4); i > 0; i--) {
      const a = rng.range(0, 6.28), d = rng.range(0, isl.r * 0.55);
      const res = lake(ctx, isl, { x: isl.x + Math.cos(a) * d, z: isl.z + Math.sin(a) * d, r: rng.range(2.2, 4.2),
        fluid: B.water, bed: B.clay, maxDepth: 2 });
      lily(res, 0.15);
    }
  } else if (isl.kind === "pradera" && rng.chance(0.3)) {
    lily(lake(ctx, isl, { x: isl.x + rng.int(-4, 4), z: isl.z + rng.int(-4, 4), r: rng.range(2.5, 3.5),
      fluid: B.water, bed: B.dirt, maxDepth: 2 }), 0.1);
  }
}

function lavaFeatures(ctx, rng, isl) {
  const lavaLake = (x, z, r) => {
    const res = lake(ctx, isl, { x, z, r, fluid: B.lava, bed: B.deepslate, maxDepth: 2 });
    if (res) for (const c of res.rim) if (!c.water) ctx.set(c.x, c.top, c.z, rng.chance(0.5) ? B.cobbledDeep : B.polishedDeep);
  };
  if (isl.kind === "crater") lavaLake(isl.x, isl.z, Math.max(4, isl.r * 0.45));
  else if (isl.kind !== "archipielago") {
    for (let i = rng.int(0, 2); i > 0; i--) {
      const a = rng.range(0, 6.28), d = rng.range(0, isl.r * 0.5);
      lavaLake(isl.x + Math.cos(a) * d, isl.z + Math.sin(a) * d, rng.range(2.5, 4.5));
    }
  }
}

// ------------------------------------------------------------ trees
function log(ctx, x, y, z, wood, axis = "y") {
  ctx.set(x, y, z, { id: WOOD[wood].log, states: { pillar_axis: axis } });
  ctx.logs.add(key3(x, y, z));
}

function leaf(ctx, x, y, z, wood) {
  if (ctx.solidAt(x, y, z)) return;
  ctx.set(x, y, z, WOOD[wood].leaves);
}

function blob(ctx, rng, cx, cy, cz, rx, ry, wood) {
  for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++)
    for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++)
      for (let z = Math.floor(cz - rx); z <= Math.ceil(cz + rx); z++) {
        const q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + ((z - cz) / rx) ** 2;
        if (q <= 1 && !(q > 0.65 && rng.chance(0.35))) leaf(ctx, x, y, z, wood);
      }
}

function branch(ctx, sx, sy, sz, ang, len, rise, wood) {
  const dx = Math.cos(ang), dz = Math.sin(ang);
  const axis = Math.abs(dx) > Math.abs(dz) ? "x" : "z";
  let x = sx, y = sy, z = sz;
  for (let i = 1; i <= len; i++) {
    x += dx; z += dz; y += rise;
    log(ctx, Math.round(x), Math.round(y), Math.round(z), wood, axis);
  }
  return { x: Math.round(x), y: Math.round(y), z: Math.round(z) };
}

// Trunk of size n x n with its corner at (x, z); fills the logs down to each column's ground.
function trunk(ctx, isl, x, z, n, gy, height, wood) {
  for (let i = 0; i < n; i++)
    for (let j = 0; j < n; j++) {
      const c = isl.cols.get(key2(x + i, z + j));
      const base = c ? c.top + 1 : gy + 1;
      if (c) ctx.set(x + i, c.top, z + j, B.dirt);
      for (let y = Math.min(base, gy + 1); y <= gy + height; y++) log(ctx, x + i, y, z + j, wood);
    }
}

const TREES = {
  // roble majestuoso: 2x2 trunk, buttress roots, long branches with leaf clouds
  bigOak(ctx, rng, isl, x, z, gy) {
    const h = rng.int(10, 14);
    trunk(ctx, isl, x, z, 2, gy, h, "oak");
    for (const [ox, oz] of [[-1, 0], [-1, 1], [2, 0], [2, 1], [0, -1], [1, -1], [0, 2], [1, 2]])
      if (rng.chance(0.55)) for (let y = 1; y <= rng.int(1, 2); y++) log(ctx, x + ox, gy + y, z + oz, "oak");
    const n = rng.int(3, 5);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rng.range(0, 0.6);
      const end = branch(ctx, x + 0.5, gy + Math.round(h * rng.range(0.5, 0.85)), z + 0.5, a, rng.int(4, 6), 0.45, "oak");
      blob(ctx, rng, end.x, end.y + 1, end.z, rng.range(3, 4), 2.5, "oak");
    }
    blob(ctx, rng, x + 0.5, gy + h + 1, z + 0.5, 4.6, 3.3, "oak");
  },
  // roble elaborado: 1x1 trunk with branches
  fancyOak(ctx, rng, isl, x, z, gy) {
    const h = rng.int(7, 10);
    trunk(ctx, isl, x, z, 1, gy, h, "oak");
    const n = rng.int(2, 4);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rng.range(0, 1);
      const end = branch(ctx, x, gy + Math.round(h * rng.range(0.5, 0.9)), z, a, rng.int(3, 5), 0.5, "oak");
      blob(ctx, rng, end.x, end.y + 1, end.z, 2.6, 2, "oak");
    }
    blob(ctx, rng, x, gy + h + 1, z, 3.2, 2.5, "oak");
  },
  // abedul majestuoso: tall, slim, with a long columnar crown
  birch(ctx, rng, isl, x, z, gy, giant = false) {
    const n = giant ? 2 : 1;
    const h = giant ? rng.int(16, 21) : rng.int(11, 16);
    const width = giant ? 3.6 : 2.6;
    trunk(ctx, isl, x, z, n, gy, h, "birch");
    const cx = x + (n - 1) / 2, cz = z + (n - 1) / 2;
    for (let i = rng.int(2, 3); i > 0; i--) {
      const end = branch(ctx, cx, gy + Math.round(h * rng.range(0.45, 0.75)), cz, rng.range(0, 6.28), rng.int(2, 3), 0.7, "birch");
      blob(ctx, rng, end.x, end.y + 1, end.z, 1.9, 1.6, "birch");
    }
    const y0 = gy + Math.floor(h * 0.42), y1 = gy + h + 2;
    for (let y = y0; y <= y1; y++) {
      const t = (y - y0) / (y1 - y0);
      const r = width * Math.pow(Math.sin(Math.PI * Math.min(0.97, 0.15 + t * 0.85)), 0.7) + 0.4;
      for (let dx = Math.floor(-r - 1); dx <= Math.ceil(r + 1); dx++)
        for (let dz = Math.floor(-r - 1); dz <= Math.ceil(r + 1); dz++) {
          const d = Math.hypot(dx + Math.round(cx) - cx, dz + Math.round(cz) - cz);
          if (d <= r && !(d > r - 0.8 && rng.chance(0.4))) leaf(ctx, Math.round(cx) + dx, y, Math.round(cz) + dz, "birch");
        }
    }
  },
  giantBirch(ctx, rng, isl, x, z, gy) {
    TREES.birch(ctx, rng, isl, x, z, gy, true);
  },
  smallOak(ctx, rng, isl, x, z, gy) {
    TREES.small(ctx, rng, isl, x, z, gy, "oak", rng.int(4, 6));
  },
  smallBirch(ctx, rng, isl, x, z, gy) {
    TREES.small(ctx, rng, isl, x, z, gy, "birch", rng.int(5, 7));
  },
  small(ctx, rng, isl, x, z, gy, wood, h) {
    trunk(ctx, isl, x, z, 1, gy, h, wood);
    for (let y = gy + h - 2; y <= gy + h + 1; y++) {
      const r = y <= gy + h - 1 ? 2 : 1;
      for (let dx = -r; dx <= r; dx++)
        for (let dz = -r; dz <= r; dz++)
          if (!(Math.abs(dx) === r && Math.abs(dz) === r && (r === 1 || rng.chance(0.5))) || (r === 1 && y === gy + h - 1))
            leaf(ctx, x + dx, y, z + dz, wood);
    }
  },
};
const TREE_SIZE = { bigOak: 2, giantBirch: 2 };
const TREE_SPACING = { bigOak: 9, giantBirch: 8, birch: 6, fancyOak: 6, smallOak: 4, smallBirch: 4 };
const TREE_MIX = {
  pradera: [["bigOak", 3], ["fancyOak", 3], ["birch", 3], ["giantBirch", 1], ["smallOak", 2], ["smallBirch", 2]],
  bosque: [["bigOak", 4], ["fancyOak", 3], ["birch", 4], ["giantBirch", 2], ["smallOak", 1], ["smallBirch", 1]],
  musgo: [["birch", 5], ["giantBirch", 2], ["smallBirch", 3], ["fancyOak", 1]],
  oasis: [["fancyOak", 3], ["smallOak", 2], ["birch", 2], ["smallBirch", 2]],
  default: [["bigOak", 2], ["fancyOak", 3], ["birch", 3], ["smallOak", 2], ["smallBirch", 2]],
};
const TREE_COUNT = {
  pradera: [1, 3], bosque: [4, 7], musgo: [2, 4], oasis: [2, 4], rio: [2, 4], lagunas: [1, 3], colinas: [1, 2],
  anillo: [2, 3], terrazas: [1, 3], islote: [0, 1], principal: [7, 9],
};

function plantTrees(ctx, rng, isl, count, mix = TREE_MIX[isl.kind] ?? TREE_MIX.default, where = null) {
  const cols = [...isl.cols.values()].filter((c) =>
    !c.water && (c.surface === "grass" || c.surface === "moss") && c.e < 0.78 && !isl.used.has(key2(c.x, c.z)) &&
    (!where || where(c)));
  let planted = 0;
  for (let attempt = 0; attempt < count * 12 && planted < count && cols.length; attempt++) {
    const c = rng.pick(cols);
    const kind = rng.weighted(mix);
    const n = TREE_SIZE[kind] ?? 1;
    let ok = true;
    for (let i = 0; i < n && ok; i++)
      for (let j = 0; j < n; j++) {
        const cc = isl.cols.get(key2(c.x + i, c.z + j));
        if (!cc || cc.water || isl.used.has(key2(c.x + i, c.z + j)) || Math.abs(cc.top - c.top) > 2) { ok = false; break; }
      }
    if (!ok) continue;
    const space = TREE_SPACING[kind];
    if (isl.trees.some((t) => Math.hypot(t.x - c.x, t.z - c.z) < Math.max(space, t.space))) continue;
    for (let i = -1; i <= n; i++) for (let j = -1; j <= n; j++) isl.used.add(key2(c.x + i, c.z + j));
    isl.trees.push({ x: c.x, z: c.z, space });
    TREES[kind](ctx, rng, isl, c.x, c.z, c.top);
    planted++;
  }
  return planted;
}

// ------------------------------------------------------------ ground cover
function decorate(ctx, rng, isl) {
  for (const c of isl.cols.values()) {
    if (c.water || isl.used.has(key2(c.x, c.z))) continue;
    const y = c.top + 1;
    if (ctx.solidAt(c.x, y, c.z) || ctx.solidAt(c.x, y + 1, c.z)) continue;
    const r = rng.next();
    if (c.surface === "grass") {
      if (r < 0.2) ctx.set(c.x, y, c.z, B.shortGrass);
      else if (r < 0.23) { ctx.set(c.x, y, c.z, B.tallGrassLow); ctx.set(c.x, y + 1, c.z, B.tallGrassHigh); }
      else if (r < 0.265) ctx.set(c.x, y, c.z, rng.pick(FLOWERS));
      else if (r < 0.28) ctx.set(c.x, y, c.z, B.fern);
    } else if (c.surface === "moss") {
      if (r < 0.24) ctx.set(c.x, y, c.z, B.mossCarpet);
      else if (r < 0.27) ctx.set(c.x, y, c.z, B.azalea);
      else if (r < 0.29) ctx.set(c.x, y, c.z, B.floweringAzalea);
      else if (r < 0.33) ctx.set(c.x, y, c.z, B.shortGrass);
    }
  }
  if (isl.kind === "colinas") {
    for (let i = rng.int(1, 3); i > 0; i--) {
      const c = rng.pick([...isl.cols.values()]);
      if (c.water || isl.used.has(key2(c.x, c.z))) continue;
      const r = rng.range(1.2, 2.2);
      for (let dx = -2; dx <= 2; dx++) for (let dy = -1; dy <= 2; dy++) for (let dz = -2; dz <= 2; dz++)
        if (Math.hypot(dx, dy * 1.2, dz) <= r)
          ctx.set(c.x + dx, c.top + dy, c.z + dz, rng.pick([B.cobble, B.mossyCobble, B.andesite]));
    }
  }
}

function spires(ctx, rng, isl) {
  // agujas: deepslate needles rising from the lower islands
  const cols = [...isl.cols.values()].filter((c) => !c.water && c.e < 0.8);
  for (let i = rng.int(5, 11); i > 0 && cols.length; i--) {
    const c = rng.pick(cols);
    const h = Math.min(rng.int(3, 9), LOWER_MAX - c.top);
    const r0 = rng.range(1, 2);
    for (let y = 1; y <= h; y++) {
      const r = r0 * (1 - y / (h + 1)) + 0.3;
      for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++)
        if (Math.hypot(dx, dz) <= r) {
          ctx.set(c.x + dx, c.top + y, c.z + dz, rng.chance(0.7) ? B.deepslate : B.cobbledDeep);
          ctx.extra.add(key3(c.x + dx, c.top + y, c.z + dz));
        }
    }
    isl.used.add(key2(c.x, c.z));
  }
}

// ------------------------------------------------------------ dungeons
function lootItems(rng, table, stacks) {
  const items = [];
  for (let i = 0; i < stacks; i++) {
    const [id, lo, hi] = rng.weighted(table.map((t) => [t, t[3]]));
    items.push([mc(id), rng.int(lo, hi)]);
  }
  return items;
}

const DUNGEON_STYLE = {
  up: {
    walls: [B.cobble, B.mossyCobble, B.mossyBricks], floor: [B.bricks, B.mossyBricks, B.crackedBricks],
    shell: B.cobble, pillar: B.mossyBricks, pedestal: B.chiseledBricks, light: B.lantern, hanging: B.lanternHanging,
    stairs: "minecraft:mossy_stone_brick_stairs", lining: B.mossyBricks, ceiling: B.bricks, loot: UPPER_LOOT,
  },
  low: {
    walls: [B.deepBricks, B.crackedDeepBricks, B.deepTiles], floor: [B.polishedDeep, B.deepTiles, B.crackedDeepTiles],
    shell: B.deepBricks, pillar: B.chiseledDeep, pedestal: B.chiseledDeep, light: B.soulLantern, hanging: B.soulLanternHanging,
    stairs: "minecraft:deepslate_brick_stairs", lining: B.deepBricks, ceiling: B.deepTiles, loot: LOWER_LOOT,
  },
};

function room(ctx, rng, isl, s, rx, rz, hw, F, h, door) {
  const x0 = rx - hw, x1 = rx + hw, z0 = rz - hw, z1 = rz + hw;
  ctx.fill(x0 - 1, F - 1, z0 - 1, x1 + 1, F + h, z1 + 1, s.shell);
  ctx.fill(x0, F, z0, x1, F + h - 1, z1, B.air);
  // walls, floor and ceiling with a mix of blocks
  for (let x = x0 - 1; x <= x1 + 1; x++)
    for (let z = z0 - 1; z <= z1 + 1; z++) {
      const edge = x < x0 || x > x1 || z < z0 || z > z1;
      if (rng.chance(0.6)) ctx.set(x, F - 1, z, rng.pick(s.floor));
      if (rng.chance(0.35)) ctx.set(x, F + h, z, rng.pick(s.walls));
      if (edge) for (let y = F; y < F + h; y++) if (rng.chance(0.4)) ctx.set(x, y, z, rng.pick(s.walls));
    }
  if (hw >= 4) {
    for (const [px, pz] of [[x0 + 1, z0 + 1], [x0 + 1, z1 - 1], [x1 - 1, z0 + 1], [x1 - 1, z1 - 1]])
      ctx.fill(px, F, pz, px, F + h - 1, pz, s.pillar);
  } else {
    for (const [px, pz] of [[x0 + 1, z0 + 1], [x1 - 1, z1 - 1]]) ctx.set(px, F + h - 1, pz, s.hanging);
  }
  // the old altar where a spawner would be: it stays empty, there are no mobs here
  ctx.set(rx, F, rz, s.pedestal);
  ctx.set(rx, F + 1, rz, s.light);
  for (let i = rng.int(2, 4); i > 0; i--)
    ctx.set(rng.pick([x0, x1]), F + h - 1, rng.pick([z0, z1]), B.web);
  // chests against the walls that have no door
  const walls = DIRS.filter((d) => d !== door);
  for (let i = rng.int(1, 2); i > 0; i--) {
    const w = walls.splice(rng.int(0, walls.length - 1), 1)[0];
    const along = rng.int(-hw + 2, hw - 2);
    const cxp = w.dx ? rx + w.dx * hw : rx + along, czp = w.dz ? rz + w.dz * hw : rz + along;
    ctx.chest(cxp, F, czp, opposite(w).face, lootItems(rng, s.loot, rng.int(4, 8)));
  }
  for (let x = x0 - 1; x <= x1 + 1; x++) for (let z = z0 - 1; z <= z1 + 1; z++) isl.used.add(key2(x, z));
}

// Stairway from the room door up to the surface. Returns false if it cannot reach it.
function stairway(ctx, isl, s, rx, rz, hw, F, d, build) {
  const px = -d.dz, pz = d.dx; // sideways
  const steps = [];
  for (let i = 1; i <= 45; i++) {
    const x = rx + d.dx * (hw + 1 + i), z = rz + d.dz * (hw + 1 + i), y = F - 1 + i;
    const c = isl.cols.get(key2(x, z));
    if (!c || c.water || c.bottom >= y - 1) return false;
    for (const o of [-1, 1]) {
      const sc = isl.cols.get(key2(x + px * o, z + pz * o));
      if (!sc || sc.water) return false;
    }
    steps.push({ x, z, y, c });
    if (y >= c.top) break;
    if (i === 45) return false;
  }
  if (!build) return true;
  ctx.fill(rx + d.dx * (hw + 1), F, rz + d.dz * (hw + 1), rx + d.dx * (hw + 1), F + 2, rz + d.dz * (hw + 1), B.air);
  for (const { x, z, y, c } of steps) {
    ctx.fill(x, y + 1, z, x, y + 3, z, B.air);
    ctx.set(x, y, z, { id: s.stairs, states: { weirdo_direction: d.stair, upside_down_bit: false } });
    ctx.set(x, y - 1, z, s.lining);
    if (y + 4 <= c.top) ctx.set(x, y + 4, z, s.ceiling);
    for (const o of [-1, 1]) {
      const sx = x + px * o, sz = z + pz * o;
      const sc = isl.cols.get(key2(sx, sz));
      ctx.fill(sx, y, sz, sx, Math.min(y + 3, sc.top), sz, s.lining);
      isl.used.add(key2(sx, sz));
    }
    isl.used.add(key2(x, z));
  }
  // an arch over the entrance
  const last = steps[steps.length - 1];
  for (const o of [-1, 1]) {
    const sx = last.x + px * o, sz = last.z + pz * o;
    const sc = isl.cols.get(key2(sx, sz));
    ctx.fill(sx, sc.top + 1, sz, sx, last.y + 3, sz, s.pillar);
    if (isl.layer === "up" || last.y + 4 <= LOWER_MAX) ctx.set(sx, last.y + 4, sz, s.light);
  }
  ctx.fill(last.x - px, last.y + 3, last.z - pz, last.x + px, last.y + 3, last.z + pz, s.pillar);
  return true;
}

// Horizontal tunnel from the room door out through the side of the island.
function flankTunnel(ctx, rng, isl, s, rx, rz, hw, F, d, build) {
  const px = -d.dz, pz = d.dx;
  const steps = [];
  for (let i = 1; i <= 32; i++) {
    const x = rx + d.dx * (hw + 1 + i), z = rz + d.dz * (hw + 1 + i);
    const c = isl.cols.get(key2(x, z));
    if (!c || c.top < F + 3 || c.bottom > F - 1) {
      if (i < 2) return false;
      break;
    }
    for (let o = -2; o <= 2; o++) {
      const sc = isl.cols.get(key2(x + px * o, z + pz * o));
      if (sc && sc.water) return false;
    }
    steps.push({ x, z, c });
    if (i === 32) return false;
  }
  if (!build) return steps.length;
  ctx.fill(rx + d.dx * (hw + 1) - px, F, rz + d.dz * (hw + 1) - pz, rx + d.dx * (hw + 1) + px, F + 2, rz + d.dz * (hw + 1) + pz, B.air);
  steps.forEach(({ x, z }, i) => {
    for (let o = -2; o <= 2; o++) {
      const sx = x + px * o, sz = z + pz * o;
      const sc = isl.cols.get(key2(sx, sz));
      isl.used.add(key2(sx, sz));
      if (!sc) continue;
      if (Math.abs(o) === 2) {
        ctx.fill(sx, Math.max(F - 1, sc.bottom), sz, sx, Math.min(F + 3, sc.top), sz, rng.pick(s.walls));
        continue;
      }
      if (sc.bottom <= F - 1) ctx.set(sx, F - 1, sz, rng.pick(s.floor));
      ctx.fill(sx, F, sz, sx, F + 2, sz, B.air);
      if (F + 3 < sc.top) ctx.set(sx, F + 3, sz, s.ceiling);
    }
    if (i % 5 === 3) ctx.set(x + px * (i % 10 < 5 ? 1 : -1), F, z + pz * (i % 10 < 5 ? 1 : -1), s.light);
  });
  return steps.length;
}

function dungeon(ctx, rng, isl) {
  const s = DUNGEON_STYLE[isl.layer === "up" ? "up" : "low"];
  const hw = isl.layer === "up" ? rng.pick([3, 4]) : rng.pick([3, 4, 5]);
  const h = isl.layer === "up" ? 4 : rng.int(4, 5);
  const spread = Math.max(1, Math.floor(isl.r * 0.2));
  const wantFlank = isl.layer !== "up" && (isl.forceFlank || rng.chance(0.65));
  for (let attempt = 0; attempt < 10; attempt++) {
    const rx = isl.x + rng.int(-spread, spread), rz = isl.z + rng.int(-spread, spread);
    let minTop = Infinity, maxBottom = -Infinity, ok = true;
    for (let dx = -hw - 1; dx <= hw + 1 && ok; dx++)
      for (let dz = -hw - 1; dz <= hw + 1; dz++) {
        const c = isl.cols.get(key2(rx + dx, rz + dz));
        if (!c || c.water || isl.used.has(key2(rx + dx, rz + dz))) { ok = false; break; }
        minTop = Math.min(minTop, c.top);
        maxBottom = Math.max(maxBottom, c.bottom);
      }
    if (!ok) continue;
    const F = isl.layer === "up" ? minTop - h - 4 : Math.min(minTop - h - 3, maxBottom + 3 + rng.int(0, 3));
    if (F - 2 < maxBottom || F + h + 1 >= minTop) continue;
    if (wantFlank) {
      let best = null, bestLen = Infinity;
      for (const d of DIRS) {
        const len = flankTunnel(ctx, rng, isl, s, rx, rz, hw, F, d, false);
        if (len && len < bestLen) { best = d; bestLen = len; }
      }
      if (best) {
        room(ctx, rng, isl, s, rx, rz, hw, F, h, best);
        flankTunnel(ctx, rng, isl, s, rx, rz, hw, F, best, true);
        ctx.info.push(`mazmorra ${isl.layer === "up" ? "superior" : "inferior"} (túnel lateral)`);
        return true;
      }
    }
    for (const d of rng.shuffle(DIRS)) {
      if (!stairway(ctx, isl, s, rx, rz, hw, F, d, false)) continue;
      room(ctx, rng, isl, s, rx, rz, hw, F, h, d);
      stairway(ctx, isl, s, rx, rz, hw, F, d, true);
      ctx.info.push(`mazmorra ${isl.layer === "up" ? "superior" : "inferior"} (escalera)`);
      return true;
    }
  }
  return false;
}

// ------------------------------------------------------------ cell plans
const UPPER_KINDS = [["pradera", 18], ["bosque", 14], ["musgo", 12], ["oasis", 9], ["rio", 9], ["lagunas", 9],
  ["colinas", 10], ["archipielago", 7], ["anillo", 5], ["terrazas", 7]];
const LOWER_KINDS = [["meseta", 20], ["agujas", 16], ["crater", 14], ["fracturada", 10], ["archipielago", 10],
  ["escalones", 10]];
export const UPPER_DUNGEON_CHANCE = 0.12;
export const LOWER_DUNGEON_CHANCE = 0.55;

function jitter(rng, r) {
  const j = Math.max(0, Math.min(12, Math.floor(46 - 1.5 * r)));
  return [rng.int(-j, j), rng.int(-j, j)];
}

function satellites(rng, list, main, layer, count, rMin, rMax) {
  for (let i = 0; i < count; i++) {
    const r = rng.int(rMin, rMax), a = rng.range(0, 6.28), d = main.r + r + rng.int(4, 9);
    const x = Math.round(main.x + Math.cos(a) * d), z = Math.round(main.z + Math.sin(a) * d);
    const cxw = Math.round(main.x / CELL) * CELL, czw = Math.round(main.z / CELL) * CELL;
    if (Math.abs(x - cxw) + r > HALF + MARGIN - 4 || Math.abs(z - czw) + r > HALF + MARGIN - 4) continue;
    const top = layer === "up" ? main.top + rng.int(-8, 10) : Math.min(LOWER_MAX - 4, main.top + rng.int(-6, 3));
    list.push(newIsland(rng, layer, "islote", x, z, r, { top, thick: r * rng.range(1, 1.6) }));
  }
}

function upperPlan(rng, cx, cz) {
  const kind = rng.weighted(UPPER_KINDS);
  const list = [];
  const ox = cx * CELL, oz = cz * CELL;
  if (kind === "archipielago") {
    const top = rng.int(92, 106);
    const count = rng.int(4, 7);
    for (let i = 0, tries = 0; i < count && tries < 40; tries++) {
      const r = rng.int(4, 8), a = rng.range(0, 6.28), d = rng.range(0, 22);
      const x = Math.round(ox + Math.cos(a) * d), z = Math.round(oz + Math.sin(a) * d);
      if (list.some((o) => Math.hypot(o.x - x, o.z - z) < o.r + r + 3)) continue;
      list.push(newIsland(rng, "up", "islote", x, z, r, { top: top + rng.int(-10, 10), thick: r * rng.range(1, 1.5) }));
      i++;
    }
    return { kind, list };
  }
  const r = kind === "colinas" || kind === "bosque" ? rng.int(14, 22) : rng.int(11, 21);
  const [jx, jz] = jitter(rng, r);
  const main = newIsland(rng, "up", kind, ox + jx, oz + jz, r, {
    style: kind === "musgo" ? "moss" : "grass",
    hill: kind === "colinas" ? rng.int(6, 9) : rng.int(1, 4),
    hole: kind === "anillo" ? rng.range(0.35, 0.45) : 0,
    dungeon: kind !== "anillo" && r >= 12 && rng.chance(UPPER_DUNGEON_CHANCE),
  });
  list.push(main);
  if (kind === "terrazas") {
    const r2 = Math.max(5, Math.round(r * rng.range(0.4, 0.5))), a = rng.range(0, 6.28);
    const top = main.top + main.hill + rng.int(9, 14);
    const t = newIsland(rng, "up", "pradera", Math.round(main.x + Math.cos(a) * r * 0.35),
      Math.round(main.z + Math.sin(a) * r * 0.35), r2, { top, hill: 1, thick: Math.min(r2 * 0.8, 7) });
    list.push(t);
  }
  satellites(rng, list, main, "up", rng.int(0, 3), 2, 5);
  return { kind, list, main };
}

function lowerPlan(rng, cx, cz) {
  if (!rng.chance(0.85)) return { kind: null, list: [] };
  const kind = rng.weighted(LOWER_KINDS);
  const list = [];
  const ox = cx * CELL, oz = cz * CELL;
  if (kind === "archipielago") {
    const count = rng.int(3, 5);
    for (let i = 0, tries = 0; i < count && tries < 40; tries++) {
      const r = rng.int(4, 8), a = rng.range(0, 6.28), d = rng.range(0, 20);
      const x = Math.round(ox + Math.cos(a) * d), z = Math.round(oz + Math.sin(a) * d);
      if (list.some((o) => Math.hypot(o.x - x, o.z - z) < o.r + r + 3)) continue;
      list.push(newIsland(rng, "low", "islote", x, z, r, { top: rng.int(30, 46), thick: r * rng.range(1, 1.5) }));
      i++;
    }
    return { kind, list };
  }
  const r = rng.int(10, 19);
  const [jx, jz] = jitter(rng, r);
  const a = rng.range(0, 6.28);
  const main = newIsland(rng, "low", kind, ox + jx, oz + jz, r, {
    hill: kind === "meseta" ? 0 : rng.int(1, 3),
    steps: kind === "escalones" ? 2 : 0,
    cut: kind === "fracturada" ? { nx: Math.cos(a), nz: Math.sin(a), w: rng.range(1.2, 2.2) } : null,
    dungeon: kind !== "fracturada" && rng.chance(LOWER_DUNGEON_CHANCE),
  });
  list.push(main);
  satellites(rng, list, main, "low", rng.int(0, 2), 2, 4);
  return { kind, list, main };
}

// ------------------------------------------------------------ main island
function mainCell(ctx, rng) {
  // La isla principal: a wide meadow around the Arbol de las Raices, a giant oak
  // whose roots fall through the void down to the main lower island.
  const up = newIsland(rng, "up", "principal", 0, 0, 30, {
    top: MAIN_TOP, hill: 3, thick: 19, a: 1.05, rot: 0.4, roots: true,
    flat: { x: 0, z: 0, r: 9, y: MAIN_TOP },
  });
  const low = newIsland(rng, "low", "cripta", 0, 0, 24, { top: 45, hill: 1, thick: 23, a: 1.1, rot: 1.2, forceFlank: true, dungeon: true });
  const sats = [];
  satellites(rng, sats, up, "up", 3, 3, 5);
  satellites(rng, sats, low, "low", 2, 2, 4);
  const all = [up, low, ...sats];
  for (const isl of all) { shape(isl); ctx.islands.push(isl); }
  for (const isl of all) (isl.layer === "up" ? writeUpperBody : writeLowerBody)(ctx, isl);
  for (const isl of all) ores(ctx, rng, isl);

  // the plaza: rings of stone bricks with moss, and lantern posts
  for (const c of up.cols.values()) {
    const d = Math.hypot(c.x, c.z);
    if (d > 9.5) continue;
    const ring = Math.floor(d) % 3;
    const b = d > 8.5 ? B.chiseledBricks : ring === 0 ? B.mossyBricks : rng.chance(0.25) ? B.crackedBricks : B.bricks;
    ctx.set(c.x, c.top, c.z, b);
    c.surface = "plaza";
    up.used.add(key2(c.x, c.z));
  }
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 + Math.PI / 8;
    const x = Math.round(Math.cos(a) * 11), z = Math.round(Math.sin(a) * 11);
    const c = up.cols.get(key2(x, z));
    if (!c) continue;
    ctx.fill(x, c.top + 1, z, x, c.top + 2, z, B.mossyBricks);
    ctx.set(x, c.top + 3, z, B.lantern);
    up.used.add(key2(x, z));
  }
  // four ponds around the plaza
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
    const res = lake(ctx, up, { x: Math.cos(a) * 19, z: Math.sin(a) * 19, r: rng.range(3, 4.2), fluid: B.water, bed: B.clay, maxDepth: 2 });
    if (res) res.filled.forEach((c) => rng.chance(0.15) && ctx.set(c.x, c.top + 1, c.z, B.lily));
  }

  // the giant tree: 3x3 trunk, flared base, roots over the ground
  const gy = MAIN_TOP, H = 24;
  trunk(ctx, up, -1, -1, 3, gy, H, "oak");
  for (let x = -2; x <= 2; x++)
    for (let z = -2; z <= 2; z++)
      if (Math.abs(x) === 2 || Math.abs(z) === 2) {
        const hgt = Math.abs(x) === 2 && Math.abs(z) === 2 ? 1 : rng.int(2, 4);
        for (let y = 1; y <= hgt; y++) log(ctx, x, gy + y, z, "oak");
      }
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 + rng.range(-0.2, 0.2);
    if (Math.sin(a) > 0.55) continue; // keep the way to the arrival point (south) clear
    const dx = Math.cos(a), dz = Math.sin(a), len = rng.int(6, 10);
    for (let s = 2; s <= len; s++) {
      const x = Math.round(dx * s), z = Math.round(dz * s);
      const c = up.cols.get(key2(x, z));
      if (!c) break;
      log(ctx, x, c.top + (s < len * 0.5 ? 1 : 0), z, "oak", Math.abs(dx) > Math.abs(dz) ? "x" : "z");
      up.used.add(key2(x, z));
    }
  }
  for (let i = 0; i < 7; i++) {
    const a = (i / 7) * Math.PI * 2 + rng.range(0, 0.5);
    const end = branch(ctx, 0, gy + rng.int(12, 21), 0, a, rng.int(7, 10), 0.55, "oak");
    blob(ctx, rng, end.x, end.y + 1, end.z, rng.range(4, 5), 3, "oak");
  }
  blob(ctx, rng, 0, gy + H + 2, 0, 7.5, 4.5, "oak");
  for (let x = -3; x <= 3; x++) for (let z = -3; z <= 3; z++) up.used.add(key2(x, z));
  up.trees.push({ x: 0, z: 0, space: 14 });

  // the roots fall from the bottom of the main island to the main lower island
  const from = low.cols.get(key2(0, 0)).top + 1, to = up.cols.get(key2(0, 0)).bottom + 1;
  for (let y = from; y <= to; y++) {
    const ox = Math.round(1.6 * Math.sin(y / 6)), oz = Math.round(1.6 * Math.cos(y / 8));
    const flare = 3 * (Math.exp(-(y - from) / 4) + Math.exp(-(to - y) / 4));
    const r = 1.7 + flare;
    for (let dx = -6; dx <= 6; dx++)
      for (let dz = -6; dz <= 6; dz++) {
        const d = Math.hypot(dx, dz);
        if (d > r) continue;
        const x = ox + dx, z = oz + dz;
        const b = d < r - 1.3 ? { id: WOOD.oak.log, states: { pillar_axis: "y" } }
          : rng.chance(0.25) ? B.rootedDirt : B.mangroveRoots;
        ctx.set(x, y, z, b);
        ctx.extra.add(key3(x, y, z));
      }
  }
  // hanging roots under the main island
  for (const c of up.cols.values())
    if (rng.chance(0.14) && !ctx.solidAt(c.x, c.bottom - 1, c.z)) ctx.set(c.x, c.bottom - 1, c.z, B.hangingRoots);

  // the lower main island: a chiseled deepslate circle around the roots and lava pools
  for (const c of low.cols.values()) {
    const d = Math.hypot(c.x, c.z);
    if (d >= 6 && d < 7.5) ctx.set(c.x, c.top, c.z, B.chiseledDeep);
    else if (d < 6) ctx.set(c.x, c.top, c.z, B.polishedDeep);
  }
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.5;
    const res = lake(ctx, low, { x: Math.cos(a) * 14, z: Math.sin(a) * 14, r: rng.range(2.5, 3.5), fluid: B.lava, bed: B.deepslate, maxDepth: 2 });
    if (res) for (const c of res.rim) if (!c.water) ctx.set(c.x, c.top, c.z, B.cobbledDeep);
  }
  dungeon(ctx, rng, low);

  for (const isl of all) if (isl.layer === "up") decorate(ctx, rng, isl);
  plantTrees(ctx, rng, up, rng.int(...TREE_COUNT.principal), TREE_MIX.pradera, (c) => Math.hypot(c.x, c.z) > 13);
  for (const s of sats) if (s.layer === "up" && rng.chance(0.5)) plantTrees(ctx, rng, s, 1, TREE_MIX.default);
  ctx.info.push("isla principal: Árbol de las Raíces", "isla inferior principal: Cripta de las Raíces");
}

// ------------------------------------------------------------ public
export function buildCell(cx, cz, seed) {
  const ctx = makeCtx(cx, cz);
  const rng = makeRng(seed, cx, cz, 7);
  if (cx === 0 && cz === 0) {
    mainCell(ctx, rng);
    return { ops: ctx.ops, info: ctx.info };
  }
  const upper = upperPlan(rng, cx, cz);
  const lower = lowerPlan(rng, cx, cz);
  ctx.info.push(`superior: ${upper.kind}`, `inferior: ${lower.kind ?? "ninguna"}`);
  const all = [...upper.list, ...lower.list];
  for (const isl of all) { shape(isl); ctx.islands.push(isl); }
  for (const isl of all) (isl.layer === "up" ? writeUpperBody : writeLowerBody)(ctx, isl);
  for (const isl of all) ores(ctx, rng, isl);
  for (const isl of all) if (isl.dungeon && !dungeon(ctx, rng, isl)) ctx.info.push("mazmorra fallida");
  for (const isl of upper.list) waterFeatures(ctx, rng, isl);
  for (const isl of lower.list) lavaFeatures(ctx, rng, isl);
  for (const isl of upper.list) {
    decorate(ctx, rng, isl);
    const [lo, hi] = TREE_COUNT[isl.kind] ?? [1, 2];
    const n = rng.int(lo, hi) + (isl.kind === "bosque" ? Math.floor(isl.r / 8) : 0);
    plantTrees(ctx, rng, isl, isl.kind === "islote" && isl.r < 5 ? 0 : n);
  }
  for (const isl of lower.list) if (isl.kind === "agujas") spires(ctx, rng, isl);
  return { ops: ctx.ops, info: ctx.info };
}
