// Underworld: terrain generator.
// Plain JavaScript with no game imports, so the same code builds the terrain in the
// game (scripts/main.js) and in the simulation (tools/underworld/simulate.mjs).
//
// The dimension is a closed cavern world, like the Nether: bedrock at y 0 and at the
// roof, a 3D density noise carving caverns, great halls and pillars in between, and a
// lava sea in the deepest chasms. It is generated in cells of 4x4 chunks (64x64
// blocks). The terrain only depends on the world coordinates and the seed, so the
// cells fit together whatever the order they are built in.
//
// buildCell() is a generator function: it yields now and then so the game can spread
// the work over several ticks, and returns { ops, info }. The block operations are:
//   ["f", x1, y1, z1, x2, y2, z2, block]   fill a box
//   ["s", x, y, z, block]                  set one block
//   ["c", x, y, z, block, items]           chest with items [[id, count], ...]
// A block is an id string or { id, states }.

export const CELL = 64;            // one cell = 4x4 chunks
export const HALF = CELL / 2;      // cell (cx, cz) spans x in [cx*64-32, cx*64+31]
export const H = 104;              // bedrock floor at y 0, bedrock roof at y H-1
export const LAVA = 11;            // level of the lava sea
export const ROCK_ORE = "underworld:hallucinogenic_rock_ore";
export const ROCK = "underworld:hallucinogenic_rock";

const SX = 4, SY = 8;              // the density is sampled every 4x8x4 blocks and interpolated
const NX = CELL / SX + 1, NY = H / SY + 1;

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
  return {
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
  };
}

const U = 1 / 4294967296;

// The same hash without the argument list, for the noise (it runs millions of times).
function mix(h, v) {
  h = Math.imul(h ^ v, 16777619);
  h ^= h >>> 13;
  h = Math.imul(h, 0x5bd1e995);
  return h ^ (h >>> 15);
}
const hash3 = (a, b, c) => mix(mix(mix(-2128831035, a | 0), b | 0), c | 0) >>> 0;
const hash4 = (a, b, c, d) => mix(mix(mix(mix(-2128831035, a | 0), b | 0), c | 0), d | 0) >>> 0;

// Smooth value noise in 0..1.
function noise2(seed, x, z) {
  const x0 = Math.floor(x), z0 = Math.floor(z);
  const fx = x - x0, fz = z - z0;
  const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
  const a = hash3(seed, x0, z0) * U, b = hash3(seed, x0 + 1, z0) * U;
  const c = hash3(seed, x0, z0 + 1) * U, d = hash3(seed, x0 + 1, z0 + 1) * U;
  return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
}

function noise3(seed, x, y, z) {
  const x0 = Math.floor(x), y0 = Math.floor(y), z0 = Math.floor(z);
  const fx = x - x0, fy = y - y0, fz = z - z0;
  const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy), sz = fz * fz * (3 - 2 * fz);
  const x1 = x0 + 1, y1 = y0 + 1, z1 = z0 + 1;
  const a = hash4(seed, x0, y0, z0) * U, b = hash4(seed, x1, y0, z0) * U;
  const c = hash4(seed, x0, y0, z1) * U, d = hash4(seed, x1, y0, z1) * U;
  const e = hash4(seed, x0, y1, z0) * U, f = hash4(seed, x1, y1, z0) * U;
  const g = hash4(seed, x0, y1, z1) * U, h = hash4(seed, x1, y1, z1) * U;
  const lo = a + (b - a) * sx, lo2 = c + (d - c) * sx, hi = e + (f - e) * sx, hi2 = g + (h - g) * sx;
  const p = lo + (lo2 - lo) * sz, q = hi + (hi2 - hi) * sz;
  return p + (q - p) * sy;
}

function fbm3(seed, x, y, z) {
  return (noise3(seed, x, y, z) + noise3(seed + 101, x * 2, y * 2, z * 2) * 0.5 +
    noise3(seed + 202, x * 4, y * 4, z * 4) * 0.25) / 1.75;
}

// ------------------------------------------------------------ blocks
const st = (id, states) => ({ id: `minecraft:${id}`, states });
const mc = (id) => `minecraft:${id}`;

// The cell is built in a grid of palette indices; 0 is air. "Late" blocks need the
// terrain around them (fire, lanterns, skulls...), so they are placed at the end.
const PAL = [mc("air")];
const LATE = [false];
function pal(block, late = false) {
  PAL.push(block);
  LATE.push(late);
  return PAL.length - 1;
}
const AIR = 0;
const DEEP = pal(mc("deepslate")), COBBLED = pal(mc("cobbled_deepslate")), BEDROCK = pal(mc("bedrock"));
const SOUL_SAND = pal(mc("soul_sand")), SOUL_SOIL = pal(mc("soul_soil")), LAVA_B = pal(mc("lava"));
const BONE = pal(mc("bone_block")), BONE_X = pal(st("bone_block", { pillar_axis: "x" }));
const BONE_Z = pal(st("bone_block", { pillar_axis: "z" }));
const POLISHED = pal(mc("polished_deepslate")), BRICKS = pal(mc("deepslate_bricks"));
const CRACKED_BRICKS = pal(mc("cracked_deepslate_bricks")), TILES = pal(mc("deepslate_tiles"));
const CRACKED_TILES = pal(mc("cracked_deepslate_tiles")), CHISELED = pal(mc("chiseled_deepslate"));
const WALL = pal(mc("cobbled_deepslate_wall"), true), SOUL_FIRE = pal(mc("soul_fire"), true);
const LANTERN = pal(st("soul_lantern", { hanging: false }), true);
const LANTERN_HANG = pal(st("soul_lantern", { hanging: true }), true);
const SKULL = pal(st("skeleton_skull", { facing_direction: 1 }), true);
const CHEST = pal(st("chest", { "minecraft:cardinal_direction": "south" }), true);
const ORES = [["deepslate_coal_ore", 24], ["deepslate_iron_ore", 24], ["deepslate_copper_ore", 10],
  ["deepslate_gold_ore", 14], ["deepslate_redstone_ore", 10], ["deepslate_lapis_ore", 8],
  ["deepslate_diamond_ore", 4], ["deepslate_emerald_ore", 1.5]].map(([id, w]) => [pal(mc(id)), w]);
ORES.push([pal(ROCK_ORE), 4.5]);
const ROCK_ORE_ID = ORES[ORES.length - 1][0];

const LOOT = [["bone", 3, 9, 16], ["bone_meal", 2, 8, 8], ["arrow", 4, 14, 12], ["soul_torch", 2, 8, 10],
  ["coal", 3, 10, 8], ["iron_ingot", 2, 6, 10], ["gold_ingot", 1, 5, 8], ["bow", 1, 1, 4], ["diamond", 1, 3, 3],
  ["golden_apple", 1, 1, 3], ["skeleton_skull", 1, 1, 3], ["wither_skeleton_skull", 1, 1, 0.6],
  ["soul_lantern", 1, 3, 5], ["echo_shard", 1, 2, 1.5], ["music_disc_13", 1, 1, 1], ["name_tag", 1, 1, 2]];

// ------------------------------------------------------------ terrain
export const BIOMES = ["Páramo de Pizarra", "Valle de Almas", "Osario"];
const WASTES = 0, SOUL = 1, OSSUARY = 2;

function biomeAt(seed, x, z) {
  const v = noise2(seed + 71, x / 150, z / 150) + (noise2(seed + 73, x / 31, z / 31) - 0.5) * 0.14;
  return v < 0.36 ? OSSUARY : v > 0.63 ? SOUL : WASTES;
}

// Positive = rock, negative = cavern.
function density(seed, x, y, z) {
  const n = fbm3(seed, x / 52, y / 25, z / 52);
  const hall = noise2(seed + 31, x / 140, z / 140);          // tight tunnels .. great halls
  let d = (n - 0.5) * 2.4 + 0.1 - hall * 0.36;
  const pillar = noise2(seed + 53, x / 23, z / 23);          // columns from floor to roof
  if (pillar > 0.8) d += (pillar - 0.8) * 7;
  const lo = (15 - y) / 15, hi = (y - (H - 22)) / 22;
  if (lo > 0) d += lo * lo * 1.3;
  if (hi > 0) d += hi * hi * 1.9;
  return d;
}

export function* buildCell(cx, cz, seed) {
  const x0 = cx * CELL - HALF, z0 = cz * CELL - HALF;
  const g = new Uint8Array(CELL * CELL * H);
  const at = (x, y, z) => (x * CELL + z) * H + y;
  const inb = (x, y, z) => x >= 0 && x < CELL && z >= 0 && z < CELL && y > 0 && y < H - 1;
  const get = (x, y, z) => (inb(x, y, z) ? g[at(x, y, z)] : DEEP);
  // decorations never replace the terrain, they only grow into the air
  const put = (x, y, z, id) => {
    if (!inb(x, y, z) || g[at(x, y, z)] !== AIR) return false;
    g[at(x, y, z)] = id;
    return true;
  };
  const force = (x, y, z, id) => {
    if (inb(x, y, z)) g[at(x, y, z)] = id;
  };

  // ---- 1. density lattice
  const lat = new Float32Array(NX * NX * NY);
  for (let ix = 0; ix < NX; ix++) {
    for (let iz = 0; iz < NX; iz++)
      for (let iy = 0; iy < NY; iy++)
        lat[(ix * NX + iz) * NY + iy] = density(seed, x0 + ix * SX, iy * SY, z0 + iz * SX);
    if (ix & 1) yield;
  }

  // ---- 2. rock and caverns (trilinear interpolation of the lattice)
  for (let ix = 0; ix < NX - 1; ix++) {
    for (let iz = 0; iz < NX - 1; iz++) {
      const p00 = (ix * NX + iz) * NY, p01 = p00 + NY, p10 = p00 + NX * NY, p11 = p10 + NY;
      for (let iy = 0; iy < NY - 1; iy++) {
        const a00 = lat[p00 + iy], a01 = lat[p01 + iy], a10 = lat[p10 + iy], a11 = lat[p11 + iy];
        const b00 = lat[p00 + iy + 1], b01 = lat[p01 + iy + 1], b10 = lat[p10 + iy + 1], b11 = lat[p11 + iy + 1];
        // a block of solid rock or of open air needs no interpolation
        const allPos = a00 > 0 && a01 > 0 && a10 > 0 && a11 > 0 && b00 > 0 && b01 > 0 && b10 > 0 && b11 > 0;
        const allNeg = a00 <= 0 && a01 <= 0 && a10 <= 0 && a11 <= 0 && b00 <= 0 && b01 <= 0 && b10 <= 0 && b11 <= 0;
        if (allNeg) continue;
        for (let lx = 0; lx < SX; lx++) {
          const tx = lx / SX;
          const a0 = a00 + (a10 - a00) * tx, a1 = a01 + (a11 - a01) * tx;
          const b0 = b00 + (b10 - b00) * tx, b1 = b01 + (b11 - b01) * tx;
          for (let lz = 0; lz < SX; lz++) {
            const tz = lz / SX;
            let a = a0 + (a1 - a0) * tz;
            const step = (b0 + (b1 - b0) * tz - a) / SY;
            const base = at(ix * SX + lx, iy * SY, iz * SX + lz);
            if (allPos) g.fill(DEEP, base, base + SY);
            else
              for (let ly = 0; ly < SY; ly++) {
                if (a > 0) g[base + ly] = DEEP;
                a += step;
              }
          }
        }
      }
    }
    yield;
  }

  // ---- 3. bedrock, lava sea and the surfaces of each biome
  const floors = [];   // x, y, z, headroom, biome   (y = the floor block)
  const roofs = [];    // x, y, z, drop             (y = the air block under the roof)
  const count = [0, 0, 0];
  for (let x = 0; x < CELL; x++) {
    for (let z = 0; z < CELL; z++) {
      const base = at(x, 0, z), gx = x0 + x, gz = z0 + z;
      g[base] = BEDROCK;
      g[base + H - 1] = BEDROCK;
      g[base + 1] = g[base + 2] = g[base + H - 2] = g[base + H - 3] = DEEP;
      for (let y = 3; y <= LAVA; y++) if (g[base + y] === AIR) g[base + y] = LAVA_B;
      const biome = biomeAt(seed, gx, gz);
      count[biome]++;
      const patch = noise2(seed + 90, gx / 7, gz / 7);
      for (let y = H - 4; y > LAVA; y--) {
        if (g[base + y] !== DEEP) continue;
        if (g[base + y + 1] === AIR) {
          let head = 1;
          while (head < 14 && g[base + y + 1 + head] === AIR) head++;
          const r = hash(seed, gx, y, gz) & 255;
          if (biome === SOUL) {
            g[base + y] = patch > 0.5 ? SOUL_SAND : SOUL_SOIL;
            if (g[base + y - 1] === DEEP) g[base + y - 1] = patch > 0.5 ? SOUL_SAND : SOUL_SOIL;
            if (g[base + y - 2] === DEEP) g[base + y - 2] = SOUL_SOIL;
          } else if (biome === OSSUARY) {
            g[base + y] = patch > 0.56 ? BONE : patch < 0.27 ? SOUL_SOIL : r < 90 ? BONE : r < 150 ? COBBLED : DEEP;
            if (patch > 0.56 && g[base + y - 1] === DEEP) g[base + y - 1] = BONE;
          } else if (patch > 0.64) g[base + y] = COBBLED;
          else if (patch < 0.16) g[base + y] = SOUL_SOIL;
          if (head >= 2) floors.push(x, y, z, head, biome);
        } else if (g[base + y - 1] === AIR) {
          let drop = 1;
          while (drop < 14 && g[base + y - 1 - drop] === AIR) drop++;
          if (biome === OSSUARY && patch > 0.6) g[base + y] = BONE;
          else if (biome === WASTES && patch > 0.72) g[base + y] = COBBLED;
          if (drop >= 4) roofs.push(x, y - 1, z, drop);
        }
      }
    }
    if ((x & 3) === 3) yield;
  }

  // ---- 4. ores, decorations and structures
  const rng = makeRng(seed, cx, cz, 4242);
  const info = [];
  const main = count.indexOf(Math.max(...count));
  info.push(BIOMES[main]);
  const share = (b) => count[b] / (CELL * CELL);
  const nFloors = floors.length / 5, nRoofs = roofs.length / 4;
  const floor = (ok, tries = 24) => {
    for (let t = 0; t < tries && nFloors > 0; t++) {
      const i = rng.int(0, nFloors - 1) * 5;
      const s = { x: floors[i], y: floors[i + 1], z: floors[i + 2], head: floors[i + 3], biome: floors[i + 4] };
      // the floor may have been built on since it was listed
      if (get(s.x, s.y + 1, s.z) === AIR && get(s.x, s.y, s.z) !== AIR && (!ok || ok(s))) return s;
    }
    return null;
  };
  const roof = (ok, tries = 16) => {
    for (let t = 0; t < tries && nRoofs > 0; t++) {
      const i = rng.int(0, nRoofs - 1) * 4;
      const s = { x: roofs[i], y: roofs[i + 1], z: roofs[i + 2], drop: roofs[i + 3] };
      if (get(s.x, s.y, s.z) === AIR && (!ok || ok(s))) return s;
    }
    return null;
  };
  const inside = (s, m) => s.x >= m && s.x < CELL - m && s.z >= m && s.z < CELL - m;

  // ore veins (the hallucinogenic rock also grows down here)
  for (let i = 0; i < 46; i++) {
    const id = rng.weighted(ORES);
    let x = rng.int(1, CELL - 2), y = rng.int(4, H - 6), z = rng.int(1, CELL - 2);
    const size = id === ROCK_ORE_ID ? rng.int(2, 4) : rng.int(3, 8);
    for (let k = 0; k < size; k++) {
      if (inb(x, y, z) && g[at(x, y, z)] === DEEP) g[at(x, y, z)] = id;
      const dir = rng.int(0, 5);
      if (dir < 2) x += dir ? 1 : -1;
      else if (dir < 4) y += dir === 2 ? 1 : -1;
      else z += dir === 4 ? 1 : -1;
    }
  }
  yield;

  // shrine: a ruined altar of deepslate with a chest
  const chests = new Map();
  if (rng.chance(0.34)) {
    const s = floor((f) => f.head >= 5 && inside(f, 4) && f.y > LAVA + 2, 60);
    if (s) {
      for (let dx = -2; dx <= 2; dx++)
        for (let dz = -2; dz <= 2; dz++) {
          const edge = Math.abs(dx) === 2 || Math.abs(dz) === 2;
          const corner = Math.abs(dx) === 2 && Math.abs(dz) === 2;
          force(s.x + dx, s.y, s.z + dz, edge ? (rng.chance(0.3) ? CRACKED_BRICKS : BRICKS) : rng.chance(0.25) ? CRACKED_TILES : TILES);
          for (let d = 1; d <= 3; d++) if (get(s.x + dx, s.y - d, s.z + dz) === AIR) force(s.x + dx, s.y - d, s.z + dz, BRICKS);
          for (let d = 1; d <= 4; d++) force(s.x + dx, s.y + d, s.z + dz, AIR);
          if (corner) {
            const tall = rng.int(1, 3);   // broken pillars
            for (let d = 1; d <= tall; d++) force(s.x + dx, s.y + d, s.z + dz, d === tall && tall > 1 ? CHISELED : POLISHED);
            if (rng.chance(0.7)) force(s.x + dx, s.y + tall + 1, s.z + dz, LANTERN);
          }
        }
      force(s.x, s.y, s.z, CHISELED);
      force(s.x, s.y + 1, s.z, CHEST);
      const items = [];
      for (let i = rng.int(4, 7); i > 0; i--) {
        const [id, lo, hi] = rng.weighted(LOOT.map((l) => [l, l[3]]));
        items.push([mc(id), rng.int(lo, hi)]);
      }
      if (rng.chance(0.6)) items.push([ROCK, rng.int(1, 2)]);
      chests.set(at(s.x, s.y + 1, s.z), items);
      info.push("santuario");
    }
  }

  // giant skull with soul light in its eyes
  if (rng.chance(0.1 + 0.25 * (share(SOUL) + share(OSSUARY)))) {
    const s = floor((f) => f.head >= 10 && inside(f, 6) && f.y > LAVA + 1, 80);
    if (s) {
      const turn = rng.int(0, 3);   // the way it looks
      const P = (dx, dy, dz, id, hard) => {
        const [ax, az] = turn === 0 ? [dx, dz] : turn === 1 ? [-dz, dx] : turn === 2 ? [-dx, -dz] : [dz, -dx];
        (hard ? force : put)(s.x + ax, s.y + 4 + dy, s.z + az, id);
      };
      for (let dx = -4; dx <= 4; dx++)
        for (let dy = -4; dy <= 4; dy++)
          for (let dz = -5; dz <= 4; dz++) {
            const e = (dx * dx) / 17 + (dy * dy) / 18 + (dz * dz) / (dz > 0 ? 17 : 25);
            if (e <= 1 && e > 0.5 && dy >= -3) P(dx, dy, dz, BONE);
          }
      for (const ex of [-2, 2]) {
        for (let dz = 3; dz <= 4; dz++)
          for (const dx of [ex, ex - Math.sign(ex)]) for (const dy of [0, 1]) P(dx, dy, dz, AIR, true);
        P(ex, -1, 2, BONE, true);
        P(ex, 0, 2, LANTERN, true);
      }
      for (let dz = 3; dz <= 4; dz++) P(0, -1, dz, AIR, true);            // nose
      for (const dx of [-2, 0, 2]) for (let dz = 2; dz <= 4; dz++) P(dx, -3, dz, AIR, true);   // teeth
      info.push("calavera gigante");
    }
  }

  // ribcages of some huge beast, half buried
  for (let n = rng.chance(0.25 + 0.6 * (share(SOUL) + share(OSSUARY))) ? rng.int(1, 2) : 0; n > 0; n--) {
    const s = floor((f) => f.head >= 7 && f.biome !== WASTES && inside(f, 7), 60);
    if (!s) continue;
    const alongX = rng.chance(0.5), len = rng.int(3, 5), r = rng.int(3, 5);
    for (let i = -len * 2; i <= len * 2; i++) {
      const px = s.x + (alongX ? i : 0), pz = s.z + (alongX ? 0 : i);
      put(px, s.y + 1, pz, alongX ? BONE_X : BONE_Z) || force(px, s.y, pz, alongX ? BONE_X : BONE_Z);
      if (i % 2) continue;
      const rr = r - (Math.abs(i) > len ? 1 : 0);   // the ribs get shorter towards the ends
      for (let a = 0; a <= 20; a++) {
        const ang = (a / 20) * Math.PI * 0.8;       // the ribs do not close at the top
        const side = Math.round(Math.sin(ang) * rr), up = Math.round((1 - Math.cos(ang)) * rr * 0.9);
        for (const sg of [-1, 1]) put(px + (alongX ? 0 : side * sg), s.y + 1 + up, pz + (alongX ? side * sg : 0), BONE);
      }
    }
    info.push("costillar");
  }
  yield;

  // bone spikes and deepslate stalagmites
  for (let i = 0; i < 26; i++) {
    const s = floor((f) => f.head >= 3);
    if (!s) break;
    const bone = s.biome !== WASTES || rng.chance(0.15);
    const tall = Math.min(s.head - 1, bone ? rng.int(2, 8) : rng.int(1, 4));
    for (let d = 1; d <= tall; d++) put(s.x, s.y + d, s.z, bone ? BONE : d === tall ? WALL : COBBLED);
    if (bone && tall >= 5)
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]])
        for (let d = 1; d <= rng.int(0, tall >> 1); d++) put(s.x + dx, s.y + d, s.z + dz, BONE);
  }
  // stalactites; some are bone and carry a soul lantern
  for (let i = 0; i < 30; i++) {
    const lamp = i < 12;
    const s = roof((f) => f.drop >= (lamp ? 5 : 4));
    if (!s) break;
    const bone = lamp || biomeAt(seed, x0 + s.x, z0 + s.z) === OSSUARY;
    const long = Math.min(s.drop - 3, rng.int(1, lamp ? 5 : 6));
    for (let d = 0; d < long; d++) put(s.x, s.y - d, s.z, bone ? BONE : d === long - 1 ? WALL : COBBLED);
    if (lamp) put(s.x, s.y - long, s.z, LANTERN_HANG);
  }
  // soul fire
  const fires = Math.round(4 + 16 * share(SOUL) + 5 * share(OSSUARY));
  for (let i = 0; i < fires; i++) {
    const s = floor((f) => f.biome === SOUL || i < 4 + 5 * share(OSSUARY));
    if (!s) break;
    for (let k = rng.int(1, 4); k > 0; k--) {
      const x = s.x + rng.int(-1, 1), z = s.z + rng.int(-1, 1);
      for (let y = s.y + 2; y >= s.y - 1; y--) {
        const below = get(x, y - 1, z);
        if (get(x, y, z) !== AIR || below === AIR || !inb(x, y - 1, z)) continue;
        if (below === DEEP || below === COBBLED || below === BONE) force(x, y - 1, z, SOUL_SOIL);
        else if (below !== SOUL_SAND && below !== SOUL_SOIL) break;
        put(x, y, z, SOUL_FIRE);
        break;
      }
    }
  }
  // skulls lying around the ossuary
  for (let i = Math.round(10 * share(OSSUARY) + 3 * share(SOUL)); i > 0; i--) {
    const s = floor((f) => f.biome !== WASTES);
    if (s) put(s.x, s.y + 1, s.z, SKULL);
  }
  yield;

  // ---- 5. boxes: merge equal blocks into as few fills as possible
  const ops = [], late = [];
  const done = new Uint8Array(g.length);
  const MAXB = 31;   // a fill is at most 32x32x32 = 32768 blocks
  for (let x = 0; x < CELL; x++) {
    for (let z = 0; z < CELL; z++) {
      const base = at(x, 0, z);
      for (let y = 0; y < H; y++) {
        const id = g[base + y];
        if (id === AIR || done[base + y]) continue;
        if (LATE[id]) {
          if (id === CHEST) late.push(["c", x0 + x, y, z0 + z, PAL[id], chests.get(base + y) ?? []]);
          else late.push(["s", x0 + x, y, z0 + z, PAL[id]]);
          continue;
        }
        let y2 = y;
        while (y2 + 1 < H && y2 - y < MAXB && g[base + y2 + 1] === id && !done[base + y2 + 1]) y2++;
        let z2 = z;
        grow: while (z2 + 1 < CELL && z2 - z < MAXB) {
          const b = at(x, 0, z2 + 1);
          for (let yy = y; yy <= y2; yy++) if (g[b + yy] !== id || done[b + yy]) break grow;
          z2++;
        }
        let x2 = x;
        grow: while (x2 + 1 < CELL && x2 - x < MAXB) {
          for (let zz = z; zz <= z2; zz++) {
            const b = at(x2 + 1, 0, zz);
            for (let yy = y; yy <= y2; yy++) if (g[b + yy] !== id || done[b + yy]) break grow;
          }
          x2++;
        }
        for (let xx = x; xx <= x2; xx++)
          for (let zz = z; zz <= z2; zz++) done.fill(1, at(xx, y, zz), at(xx, y2, zz) + 1);
        if (x === x2 && y === y2 && z === z2) ops.push(["s", x0 + x, y, z0 + z, PAL[id]]);
        else ops.push(["f", x0 + x, y, z0 + z, x0 + x2, y2, z0 + z2, PAL[id]]);
        y = y2;
      }
      if ((z & 15) === 15) yield;
    }
  }
  for (const op of late) ops.push(op);
  return { ops, info, biomes: count };
}

export function buildCellSync(cx, cz, seed) {
  const it = buildCell(cx, cz, seed);
  let r = it.next();
  while (!r.done) r = it.next();
  return r.value;
}
