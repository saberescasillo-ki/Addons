// Mazmorras de Toba: dungeon generator.
// Plain JavaScript with no game imports, so the same code builds the dungeon in the
// game (scripts/main.js) and in the simulation (tools/mazmorras/simulate.mjs).
//
// planDungeon() lays the rooms out on a grid (one room per grid column, several floors);
// buildDungeon() turns the plan into block operations, split in pieces:
//   ["f", x1, y1, z1, x2, y2, z2, block]   fill a box
//   ["s", x, y, z, block]                  set one block
//   ["c", x, y, z, block, items]           chest with items [[id, count], ...]
// A block is an id string or { id, states, alt: [other blocks to try] }.

export const GRID = 24;        // distance between two room centres
export const FLOOR_H = 10;     // height between two floors
export const ENTRY_DEPTH = 16; // the first floor is this many blocks under the entrance
export const VEST_OFF = 23;    // distance from the entrance to the centre of the hall

// Directions. Stairs ascend towards the direction of their weirdo_direction.
export const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]]; // east, west, south, north
export const OPP = [1, 0, 3, 2];
const PERP = [2, 3, 1, 0];                               // the +v side of a frame looking along d
const CARD = ["east", "west", "south", "north"];
const FACING = [5, 4, 3, 2];                             // facing_direction of each direction
const VINE_BIT = [8, 2, 1, 4];                           // vine_direction_bits: the side it hangs from
export const DIR_NAME = ["este", "oeste", "sur", "norte"];

// ------------------------------------------------------------ themes
export const THEMES = {
  ruinas: {
    name: "Ruinas Frondosas", desc: "equilibrada: generadores, parkour y jardines",
    parkour: 0.22, spawner: 0.65, down: 0.3, lush: 0.55, pale: 0.12, light: "ochre_froglight", wood: ["oak", "spruce", "mangrove"],
    mobs: [["zombis", 3], ["esqueletos", 3], ["aranas", 2], ["slimes", 1], ["lepismas", 1], ["breeze", 1]],
  },
  cripta: {
    name: "Cripta de Toba", desc: "más generadores, musgo pálido y menos luz",
    parkour: 0.12, spawner: 0.85, down: 0.4, lush: 0.25, pale: 0.7, light: "pearlescent_froglight", wood: ["dark_oak", "spruce", "pale_oak"],
    mobs: [["esqueletos", 3], ["pantanosos", 2], ["zombis", 2], ["aranas", 2], ["breeze", 2]],
  },
  jardin: {
    name: "Jardín Colgante", desc: "muy frondosa, con más salas de parkour",
    parkour: 0.35, spawner: 0.5, down: 0.25, lush: 0.9, pale: 0.05, light: "verdant_froglight", wood: ["mangrove", "jungle", "cherry"],
    mobs: [["pantanosos", 3], ["aranas", 2], ["slimes", 2], ["zombis", 1]],
  },
};
export const THEME_KEYS = Object.keys(THEMES);

export const MOB_FAMILIES = {
  zombis: ["minecraft:zombie", "minecraft:husk"],
  esqueletos: ["minecraft:skeleton", "minecraft:bogged"],
  pantanosos: ["minecraft:bogged"],
  aranas: ["minecraft:spider", "minecraft:cave_spider"],
  slimes: ["minecraft:slime"],
  lepismas: ["minecraft:silverfish"],
  breeze: ["minecraft:breeze"],
  guardianes: ["minecraft:bogged", "minecraft:stray", "minecraft:breeze"],
};

export const TYPE_NAME = {
  vestibulo: "vestíbulo", spawner: "generador", parkour: "parkour", jardin: "jardín", tesoro: "tesoro",
};

// Interior of each room, in the room's own frame: u along the way in, v across.
const SPECS = {
  vestibulo: { u0: -3, u1: 3, vh: 3, h: 6 },
  spawner: { u0: -2, u1: 2, vh: 2, h: 5 },   // 5x5, spawner in the centre
  jardin: { u0: -3, u1: 3, vh: 3, h: 6 },
  tesoro: { u0: -4, u1: 4, vh: 4, h: 7 },
  parkour: { u0: -4, u1: 3, vh: 2, h: 7, pit: 4 }, // 8 long x 5 wide
};

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

export function makeRng(...n) {
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
    shuffle(arr) {
      const out = arr.slice();
      for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
      }
      return out;
    },
  };
}

// ------------------------------------------------------------ blocks
const mc = (id) => `minecraft:${id}`;
const st = (id, states, alt) => (alt ? { id: mc(id), states, alt } : { id: mc(id), states });
const AIR = mc("air");
const T = {
  tuff: mc("tuff"), polished: mc("polished_tuff"), bricks: mc("tuff_bricks"), chiseled: mc("chiseled_tuff"),
  chiseledBricks: mc("chiseled_tuff_bricks"), brickWall: mc("tuff_brick_wall"), polishedWall: mc("polished_tuff_wall"),
  moss: mc("moss_block"), mossCarpet: mc("moss_carpet"), paleMoss: mc("pale_moss_block"),
  paleCarpet: mc("pale_moss_carpet"), rooted: mc("dirt_with_roots"), clay: mc("clay"), water: mc("water"),
  azalea: mc("azalea"), flowering: mc("flowering_azalea"), spore: mc("spore_blossom"), roots: mc("hanging_roots"),
  fern: mc("fern"), grass: mc("short_grass"),
  leaves: st("azalea_leaves", { persistent_bit: true }),
  leavesFlower: st("azalea_leaves_flowered", { persistent_bit: true }),
  lichenUp: st("glow_lichen", { multi_face_direction_bits: 2 }),
  lantern: st("lantern", { hanging: false }), lanternHang: st("lantern", { hanging: true }),
  chain: st("chain", { pillar_axis: "y" }, [st("iron_chain", { pillar_axis: "y" })]),
  dripleaf: (d) => st("big_dripleaf", { big_dripleaf_head: true, big_dripleaf_tilt: "none", "minecraft:cardinal_direction": CARD[d] }),
};
const slab = (id, top) => st(id, { "minecraft:vertical_half": top ? "top" : "bottom" });
const woodSlab = (wood, top) => st(`${wood}_slab`, { "minecraft:vertical_half": top ? "top" : "bottom" },
  [st("oak_slab", { "minecraft:vertical_half": top ? "top" : "bottom" })]);
const stairs = (id, asc, upside = false) => st(id, { weirdo_direction: asc, upside_down_bit: upside });
const chest = (d) => st("chest", { "minecraft:cardinal_direction": CARD[d] }, [st("chest", { facing_direction: FACING[d] })]);
const vine = (d) => st("vine", { vine_direction_bits: VINE_BIT[d] });
const froglight = (th) => st(th.light, { pillar_axis: "y" });
const candle = (color, n) => st(`${color}_candle`, { candles: n, lit: true });
const vault = (d, ominous) => st("vault", { "minecraft:cardinal_direction": CARD[d], vault_state: "inactive", ominous });
const trialSpawner = (ominous) => st("trial_spawner", { trial_spawner_state: 1, ominous });

function wallVariant(rng, th) {
  return rng.weighted([[T.tuff, 4], [T.polished, 1], [T.chiseledBricks, 0.6], [T.moss, 3 * th.lush],
    [T.paleMoss, 3 * th.pale], [T.rooted, 0.6 * th.lush], [T.chiseled, 0.3]]);
}
function floorVariant(rng, th) {
  return rng.weighted([[T.polished, 4], [T.bricks, 2], [T.tuff, 1.5], [T.moss, 2.5 * th.lush],
    [T.paleMoss, 2 * th.pale], [T.rooted, 0.5 * th.lush]]);
}
function ceilVariant(rng, th) {
  return rng.weighted([[T.tuff, 3], [T.polished, 1], [T.moss, 3 * th.lush], [T.paleMoss, 2.5 * th.pale],
    [T.rooted, 1 * th.lush]]);
}
const carpetFor = (b) => (b === T.moss ? T.mossCarpet : b === T.paleMoss ? T.paleCarpet : null);

// ------------------------------------------------------------ building helpers
class Builder {
  constructor() {
    this.ops = [];
  }
  fill(x1, y1, z1, x2, y2, z2, b) {
    if (y2 < y1) [y1, y2] = [y2, y1];
    this.ops.push(["f", Math.min(x1, x2), y1, Math.min(z1, z2), Math.max(x1, x2), y2, Math.max(z1, z2), b]);
  }
  set(x, y, z, b) {
    this.ops.push(["s", x, y, z, b]);
  }
  chest(x, y, z, b, items) {
    this.ops.push(["c", x, y, z, b, items]);
  }
  // A frame centred on (cx, cz) looking along direction d: u forwards, v to the side.
  frame(cx, cz, d) {
    const [dx, dz] = DIRS[d];
    const px = -dz, pz = dx;
    const b = this;
    const X = (u, v) => cx + u * dx + v * px, Z = (u, v) => cz + u * dz + v * pz;
    return {
      d,
      // the world direction of a local direction: "u+", "u-", "v+", "v-"
      dir: (k) => ({ "u+": d, "u-": OPP[d], "v+": PERP[d], "v-": OPP[PERP[d]] })[k],
      fill: (u1, v1, y1, u2, v2, y2, blk) => b.fill(X(u1, v1), y1, Z(u1, v1), X(u2, v2), y2, Z(u2, v2), blk),
      set: (u, v, y, blk) => b.set(X(u, v), y, Z(u, v), blk),
      chest: (u, v, y, blk, items) => b.chest(X(u, v), y, Z(u, v), blk, items),
      x: X, z: Z,
    };
  }
}

// Cave vines hanging from the block above yTop, len blocks long.
function caveVines(L, u, v, yTop, len, rng) {
  for (let k = 0; k < len; k++) {
    const head = k === len - 1, berries = rng.chance(0.55);
    const id = head ? (berries ? "cave_vines_head_with_berries" : "cave_vines")
      : (berries ? "cave_vines_body_with_berries" : "cave_vines");
    L.set(u, v, yTop - k, mc(id));
  }
}
function paleMoss(L, u, v, yTop, len) {
  for (let k = 0; k < len; k++) L.set(u, v, yTop - k, st("pale_hanging_moss", { tip: k === len - 1 }));
}
// Something hanging from the ceiling, depending on the theme.
function hanging(L, u, v, yTop, maxLen, rng, th) {
  const k = rng.weighted([["vines", th.lush], ["pale", th.pale * 0.8], ["roots", 0.25], ["lichen", 0.35]]);
  if (k === "vines") caveVines(L, u, v, yTop, rng.int(1, maxLen), rng);
  else if (k === "pale") paleMoss(L, u, v, yTop, rng.int(1, maxLen));
  else if (k === "roots") L.set(u, v, yTop, T.roots);
  else L.set(u, v, yTop, T.lichenUp);
}

// Random variety on the inside faces of a room's walls (the ring just outside the interior).
function wallOverlay(L, s, y1, y2, rng, th, p = 0.35) {
  const { u0, u1, vh } = s;
  for (let y = y1; y <= y2; y++) {
    for (let u = u0; u <= u1; u++) {
      if (rng.chance(p)) L.set(u, -vh - 1, y, wallVariant(rng, th));
      if (rng.chance(p)) L.set(u, vh + 1, y, wallVariant(rng, th));
    }
    for (let v = -vh; v <= vh; v++) {
      if (rng.chance(p)) L.set(u0 - 1, v, y, wallVariant(rng, th));
      if (rng.chance(p)) L.set(u1 + 1, v, y, wallVariant(rng, th));
    }
  }
}
function ceilOverlay(L, s, y, rng, th, p = 0.4) {
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = -s.vh; v <= s.vh; v++) if (rng.chance(p)) L.set(u, v, y, ceilVariant(rng, th));
}
// The basic box: walls, floor and ceiling of tuff bricks, interior air.
function roomBox(L, s, yFloor, yTop, rng, th) {
  L.fill(s.u0 - 1, -s.vh - 1, yFloor, s.u1 + 1, s.vh + 1, yTop, T.bricks);
  L.fill(s.u0, -s.vh, yFloor + 1, s.u1, s.vh, yTop - 1, AIR);
}
// Floor with a polished border and random patches; returns the chosen blocks.
function roomFloor(L, s, y, rng, th, center) {
  const out = new Map();
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = -s.vh; v <= s.vh; v++) {
      const border = u === s.u0 || u === s.u1 || v === -s.vh || v === s.vh;
      const b = border ? (rng.chance(0.75) ? T.polished : floorVariant(rng, th)) : (center?.(u, v) ?? floorVariant(rng, th));
      L.set(u, v, y, b);
      out.set(`${u},${v}`, b);
    }
  return out;
}
function carpets(L, floor, y, rng, p, skip) {
  for (const [k, b] of floor) {
    const c = carpetFor(b);
    if (!c || !rng.chance(p)) continue;
    const [u, v] = k.split(",").map(Number);
    if (skip?.(u, v)) continue;
    L.set(u, v, y, c);
  }
}
// The cornice: top slabs along the inside of the walls, just under the ceiling.
function cornice(L, s, y, mat = "tuff_brick_slab") {
  const b = slab(mat, true);
  L.fill(s.u0, -s.vh, y, s.u1, -s.vh, y, b);
  L.fill(s.u0, s.vh, y, s.u1, s.vh, y, b);
  L.fill(s.u0, -s.vh, y, s.u0, s.vh, y, b);
  L.fill(s.u1, -s.vh, y, s.u1, s.vh, y, b);
}

// ------------------------------------------------------------ loot
function loot(rng, table, nMin, nMax) {
  const out = [];
  const used = new Set();
  const n = rng.int(nMin, nMax);
  for (let i = 0; i < n * 3 && out.length < n; i++) {
    const [id, lo, hi] = rng.weighted(table.map((e) => [e, e[3]]));
    if (used.has(id)) continue;
    used.add(id);
    out.push([mc(id), rng.int(lo, hi)]);
  }
  return out;
}
const PARKOUR_LOOT = [["diamond", 1, 3, 5], ["emerald", 3, 8, 8], ["golden_apple", 1, 2, 6], ["iron_ingot", 4, 10, 10],
  ["trial_key", 1, 1, 7], ["glow_berries", 4, 12, 8], ["ender_pearl", 1, 3, 5], ["experience_bottle", 3, 8, 7],
  ["golden_carrot", 3, 8, 6], ["arrow", 8, 16, 5], ["amethyst_shard", 2, 6, 4], ["name_tag", 1, 1, 2],
  ["music_disc_creator_music_box", 1, 1, 1], ["enchanted_golden_apple", 1, 1, 0.6]];
const GARDEN_LOOT = [["glow_berries", 4, 16, 10], ["bread", 2, 6, 8], ["moss_block", 4, 12, 6], ["azalea", 1, 3, 5],
  ["flowering_azalea", 1, 2, 4], ["big_dripleaf", 1, 4, 4], ["spore_blossom", 1, 1, 2], ["bone_meal", 4, 10, 6],
  ["iron_ingot", 1, 4, 4], ["emerald", 1, 4, 3]];
const TREASURE_LOOT = [["diamond", 3, 6, 10], ["emerald", 8, 16, 10], ["golden_apple", 2, 3, 8],
  ["enchanted_golden_apple", 1, 1, 3], ["totem_of_undying", 1, 1, 3], ["netherite_scrap", 1, 2, 3],
  ["experience_bottle", 8, 16, 8], ["ominous_trial_key", 1, 1, 4], ["trial_key", 2, 3, 6], ["diamond_block", 1, 1, 1],
  ["heavy_core", 1, 1, 1], ["flow_banner_pattern", 1, 1, 2], ["music_disc_precipice", 1, 1, 2]];

// ------------------------------------------------------------ plan
// opts: { seed, rooms, floors, theme, facing, parkour }
export function planDungeon(opts) {
  const th = THEMES[opts.theme] ?? THEMES.ruinas;
  const rng = makeRng(opts.seed, 1);
  const facing = opts.facing;
  const list = [{ id: 0, gx: 0, gz: 0, f: 0, type: "vestibulo", dirIn: facing, parent: -1, depth: 0, kids: [] }];
  const occ = new Set(["0,0"]);
  // the entrance staircase comes in from behind the hall: nothing can be built there
  occ.add(`${-DIRS[facing][0]},${-DIRS[facing][1]}`);
  const free = (r) => [0, 1, 2, 3].filter((d) => !occ.has(`${r.gx + DIRS[d][0]},${r.gz + DIRS[d][1]}`));

  for (let guard = 0; list.length <= opts.rooms && guard < 10000; guard++) {
    const cands = list.filter((r) => r.kids.length < 3 && free(r).length);
    if (!cands.length) break;
    // half of the time grow from one of the last rooms (long branches), else anywhere
    const parent = rng.chance(0.55) ? cands[Math.max(0, cands.length - 1 - rng.int(0, 2))] : rng.pick(cands);
    const dir = rng.pick(free(parent));
    let f = parent.f;
    if (f + 1 < opts.floors && rng.chance(th.down)) f++;
    else if (f > 0 && rng.chance(0.08)) f--;
    const room = {
      id: list.length, gx: parent.gx + DIRS[dir][0], gz: parent.gz + DIRS[dir][1], f, type: "",
      dirIn: dir, parent: parent.id, depth: parent.depth + 1, kids: [],
    };
    parent.kids.push(room.id);
    occ.add(`${room.gx},${room.gz}`);
    list.push(room);
  }

  // room types: the deepest leaf holds the treasure, other leaves can be parkour rooms
  const rest = list.slice(1);
  const leaves = rest.filter((r) => !r.kids.length);
  const treasure = leaves.reduce((a, b) => (b.depth * 10 + b.f > a.depth * 10 + a.f ? b : a), leaves[0]);
  treasure.type = "tesoro";
  if (opts.parkour !== false) {
    const want = Math.max(1, Math.round(opts.rooms * th.parkour));
    for (const r of rng.shuffle(leaves.filter((r) => r !== treasure)).slice(0, want)) r.type = "parkour";
  }
  const others = rest.filter((r) => !r.type);
  for (const r of others) r.type = rng.chance(th.spawner) ? "spawner" : "jardin";
  // at least two spawner rooms and one garden when there is room for them
  const count = (t) => rest.filter((r) => r.type === t).length;
  for (const r of rng.shuffle(others)) {
    if (count("spawner") < Math.min(2, others.length)) r.type = "spawner";
    else break;
  }
  if (others.length >= 4 && !count("jardin")) rng.pick(others.filter((r) => r.type === "spawner")).type = "jardin";
  for (const r of rest) {
    if (r.type === "spawner" || r.type === "tesoro") {
      const fam = rng.weighted(th.mobs.filter(([k]) => k !== "breeze" || r.f > 0 || r.type === "tesoro"));
      r.mobs = r.type === "tesoro" ? "guardianes" : fam;
    }
  }

  const floorsUsed = new Set(list.map((r) => r.f)).size;
  const counts = {};
  for (const r of rest) counts[r.type] = (counts[r.type] ?? 0) + 1;
  return { seed: opts.seed, theme: opts.theme in THEMES ? opts.theme : "ruinas", facing, rooms: list, floorsUsed, counts };
}

function wallDist(room, dir) {
  const s = SPECS[room.type];
  if (dir === room.dirIn) return s.u1 + 1;
  if (dir === OPP[room.dirIn]) return -s.u0 + 1;
  return s.vh + 1;
}

// ------------------------------------------------------------ rooms
function buildVestibulo(L, s, Y, rng, th) {
  roomBox(L, s, Y - 1, Y + s.h, rng, th);
  wallOverlay(L, s, Y, Y + s.h - 1, rng, th);
  ceilOverlay(L, s, Y + s.h, rng, th);
  const floor = roomFloor(L, s, Y - 1, rng, th, (u, v) =>
    Math.abs(u) <= 1 && Math.abs(v) <= 1 ? T.moss : Math.abs(u) <= 2 && Math.abs(v) <= 2 ? T.bricks : null);
  carpets(L, floor, Y, rng, 0.6, (u, v) => Math.abs(u) === 3 || Math.abs(v) === 3);
  cornice(L, s, Y + s.h - 1);
  L.set(0, 0, Y + s.h - 1, T.spore);
  L.set(0, 0, Y + s.h, T.chiseled);
  for (const su of [-1, 1])
    for (const sv of [-1, 1]) {
      // flowering azalea on moss in the corners, lanterns on chains, benches along the side walls
      L.set(3 * su, 3 * sv, Y - 1, T.moss);
      L.set(3 * su, 3 * sv, Y, rng.chance(0.6) ? T.flowering : T.azalea);
      L.set(2 * su, 2 * sv, Y + s.h - 1, T.chain);
      L.set(2 * su, 2 * sv, Y + s.h - 2, T.lanternHang);
      L.set(2 * su, 3 * sv, Y, stairs("polished_tuff_stairs", L.dir(sv > 0 ? "v+" : "v-")));
    }
}

function buildSpawner(L, s, Y, rng, th, room, out) {
  roomBox(L, s, Y - 1, Y + s.h, rng, th);
  wallOverlay(L, s, Y, Y + s.h - 1, rng, th, 0.3);
  // a band of chiseled tuff bricks above the doors and a cornice of slabs
  for (let i = -2; i <= 2; i++) {
    L.set(i, -3, Y + 3, T.chiseledBricks);
    L.set(i, 3, Y + 3, T.chiseledBricks);
    L.set(-3, i, Y + 3, T.chiseledBricks);
    L.set(3, i, Y + 3, T.chiseledBricks);
  }
  ceilOverlay(L, s, Y + s.h, rng, th, 0.3);
  L.set(0, 0, Y + s.h, T.chiseled);
  const floor = roomFloor(L, s, Y - 1, rng, th, (u, v) =>
    u === 0 && v === 0 ? T.chiseledBricks : Math.max(Math.abs(u), Math.abs(v)) === 1 ? T.bricks : null);
  carpets(L, floor, Y, rng, 0.3, (u, v) => Math.abs(u) <= 1 && Math.abs(v) <= 1);
  cornice(L, s, Y + s.h - 1, "polished_tuff_slab");
  // corner posts with lanterns
  for (const su of [-1, 1])
    for (const sv of [-1, 1]) {
      L.set(2 * su, 2 * sv, Y, T.brickWall);
      L.set(2 * su, 2 * sv, Y + 1, rng.chance(0.5) ? T.lantern : candle("green", rng.int(1, 4)));
    }
  // things hanging from the ceiling around the spawner
  for (const [u, v] of rng.shuffle([[-1, -1], [-1, 1], [1, -1], [1, 1], [0, -1], [0, 1], [-1, 0], [1, 0]]).slice(0, 3))
    hanging(L, u, v, Y + s.h - 1, 2, rng, th);
  L.set(0, 0, Y, trialSpawner(false));
  out.spawners.push({
    x: L.x(0, 0), y: Y, z: L.z(0, 0), kind: "normal", family: room.mobs, room: room.id,
    box: box(L, s.u0, -s.vh, Y, s.u1, s.vh, Y + s.h - 1),
  });
}

function buildJardin(L, s, Y, rng, th, room, out) {
  roomBox(L, s, Y - 2, Y + s.h, rng, th);
  L.fill(s.u0, -s.vh, Y - 2, s.u1, s.vh, Y - 2, T.clay);
  wallOverlay(L, s, Y, Y + s.h - 1, rng, { ...th, lush: Math.min(1, th.lush + 0.4) }, 0.45);
  ceilOverlay(L, s, Y + s.h, rng, { ...th, lush: Math.min(1, th.lush + 0.5) }, 0.6);
  // moss floor with a cross-shaped pond in the middle, dripleaves around it and a slab border
  const floor = new Map();
  for (let u = -3; u <= 3; u++)
    for (let v = -3; v <= 3; v++) {
      const b = rng.chance(0.15) ? T.rooted : th.pale > 0.5 && rng.chance(0.4) ? T.paleMoss : T.moss;
      L.set(u, v, Y - 1, b);
      floor.set(`${u},${v}`, b);
    }
  const pond = [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]];
  for (const [u, v] of pond) {
    L.set(u, v, Y - 1, T.water);
    floor.delete(`${u},${v}`);
  }
  for (const [u, v] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
    L.set(u, v, Y - 1, T.clay);
    floor.delete(`${u},${v}`);
    L.set(u, v, Y, T.dripleaf(rng.int(0, 3)));
  }
  for (const [u, v] of [[2, 0], [-2, 0], [0, 2], [0, -2]]) {
    L.set(u, v, Y, slab("tuff_brick_slab", false));
    floor.delete(`${u},${v}`);
  }
  // corners: azalea bushes, one of them may hold a chest
  const corners = rng.shuffle([[3, 3], [3, -3], [-3, 3], [-3, -3]]);
  const withChest = rng.chance(0.5) ? corners[0] : null;
  for (const [u, v] of corners) {
    floor.delete(`${u},${v}`);
    if (withChest && u === withChest[0] && v === withChest[1]) {
      const face = u > 0 ? "u-" : "u+";
      L.chest(u, v, Y, chest(L.dir(face)), loot(rng, GARDEN_LOOT, 3, 5));
      L.set(u, v, Y + 1, T.leavesFlower);
      continue;
    }
    L.set(u, v, Y, rng.chance(0.5) ? T.leavesFlower : T.leaves);
    L.set(u, v, Y + 1, rng.chance(0.5) ? T.flowering : T.azalea);
    for (const [du, dv] of [[-Math.sign(u), 0], [0, -Math.sign(v)]])
      if (rng.chance(0.6)) {
        L.set(u + du, v + dv, Y, rng.chance(0.4) ? T.fern : T.grass);
        floor.delete(`${u + du},${v + dv}`);
      }
  }
  carpets(L, floor, Y, rng, 0.45);
  // the ceiling: spore blossom over the pond, vines and roots around
  L.set(0, 0, Y + s.h - 1, T.spore);
  for (let u = -3; u <= 3; u++)
    for (let v = -3; v <= 3; v++) {
      if (u === 0 && v === 0) continue;
      if (rng.chance(0.22)) hanging(L, u, v, Y + s.h - 1, 3, rng, { ...th, lush: th.lush + 0.6 });
    }
  // a light in the middle of each wall, above the doors
  for (const [u, v] of [[0, -4], [0, 4], [-4, 0], [4, 0]]) L.set(u, v, Y + 4, froglight(th));
}

function buildTesoro(L, s, Y, rng, th, room, out) {
  roomBox(L, s, Y - 1, Y + s.h, rng, th);
  wallOverlay(L, s, Y, Y + s.h - 1, rng, th, 0.3);
  ceilOverlay(L, s, Y + s.h, rng, th, 0.35);
  const floor = roomFloor(L, s, Y - 1, rng, th, (u, v) =>
    (u + v) % 2 === 0 ? T.bricks : T.polished);
  // moss path from the door
  for (let u = -4; u <= -1; u++) {
    L.set(u, 0, Y - 1, T.moss);
    L.set(u, 0, Y, T.mossCarpet);
  }
  carpets(L, floor, Y, rng, 0.25, (u, v) => u >= 2);
  // pillars along the side walls
  for (const u of [-2, 1])
    for (const v of [-4, 4]) {
      L.set(u, v, Y, T.chiseledBricks);
      L.fill(u, v, Y + 1, u, v, Y + s.h - 2, T.polished);
      L.set(u, v, Y + s.h - 1, T.chiseled);
    }
  cornice(L, s, Y + s.h - 1);
  // the dais at the back: a slab step, the chest between two vaults, candles
  const back = L.dir("u-");
  L.fill(2, -3, Y, 2, 3, Y, slab("polished_tuff_slab", false));
  L.fill(3, -3, Y, 4, 3, Y, T.polished);
  L.fill(4, -4, Y, 4, 4, Y, T.chiseledBricks);
  L.chest(4, 0, Y + 1, chest(back), loot(rng, TREASURE_LOOT, 6, 8));
  L.set(4, -2, Y + 1, vault(back, false));
  L.set(4, 2, Y + 1, vault(back, true));
  for (const v of [-1, 1]) L.set(4, v, Y + 1, candle("lime", rng.int(2, 4)));
  for (const v of [-3, 3]) L.set(3, v, Y + 1, candle("white", rng.int(1, 3)));
  for (const v of [-4, 4]) {
    L.set(4, v, Y + 1, T.leavesFlower);
    L.set(4, v, Y + 2, T.flowering);
  }
  // azalea in the corners of the door side, lanterns on chains, the guardian spawner
  for (const v of [-4, 4]) {
    L.set(-4, v, Y, T.leaves);
    L.set(-4, v, Y + 1, T.leavesFlower);
  }
  for (const [u, v] of [[-2, -2], [-2, 2], [2, -2], [2, 2]]) {
    L.fill(u, v, Y + 4, u, v, Y + s.h - 1, T.chain);
    L.set(u, v, Y + 3, T.lanternHang);
  }
  L.set(-3, 0, Y + s.h - 1, T.spore);
  for (let i = 0; i < 6; i++) {
    const u = rng.int(-4, 4), v = rng.pick([-3, 3]);
    hanging(L, u, v, Y + s.h - 2, 2, rng, th);
  }
  L.set(-1, 0, Y - 1, T.chiseledBricks);
  L.set(-1, 0, Y, trialSpawner(true));
  out.spawners.push({
    x: L.x(-1, 0), y: Y, z: L.z(-1, 0), kind: "guardian", family: room.mobs, room: room.id,
    box: box(L, s.u0, -s.vh, Y, 1, s.vh, Y + s.h - 1),
  });
}

// 8x5 room over a pit of water: wooden slabs hanging from chains lead to a chest on the far side.
function buildParkour(L, s, Y, rng, th, room, out) {
  const pitY = Y - s.pit;           // the water
  roomBox(L, s, pitY - 2, Y + s.h, rng, th);
  L.fill(s.u0, -s.vh, pitY - 1, s.u1, s.vh, pitY - 1, T.clay);
  L.fill(s.u0 + 1, -s.vh, pitY, s.u1 - 1, s.vh, pitY, T.water);
  wallOverlay(L, s, pitY, Y + s.h - 1, rng, { ...th, lush: Math.min(1, th.lush + 0.3) }, 0.4);
  ceilOverlay(L, s, Y + s.h, rng, th, 0.5);
  // the ledge at the door and the raised ledge with the chest
  L.fill(s.u0, -s.vh, pitY, s.u0, s.vh, Y - 2, T.bricks);
  for (let v = -2; v <= 2; v++) L.set(s.u0, v, Y - 1, rng.chance(0.7) ? T.polished : floorVariant(rng, th));
  L.fill(s.u1, -s.vh, pitY, s.u1, s.vh, Y - 1, T.bricks);
  L.fill(s.u1, -s.vh, Y, s.u1, s.vh, Y, T.polished);
  // vines on the pit side of the first ledge, to climb back after a fall
  const vinesDir = L.dir("u-");
  for (const v of [-2, 0, 2]) L.fill(s.u0 + 1, v, pitY + 1, s.u0 + 1, v, Y - 1, vine(vinesDir));
  // three platforms at u = -2, 0, 2: the slab you land on and the slab holding the chain
  const wood = rng.pick(th.wood);
  let v = rng.int(-1, 1), h = 0;
  for (const u of [-2, 0, 2]) {
    const hold = v <= 0 ? v - 1 : v + 1;
    const y = Y - 1 + h;              // top slab at y: you stand at y + 1
    L.set(u, v, y, woodSlab(wood, true));
    L.set(u, hold, y, woodSlab(wood, true));
    L.fill(u, hold, y + 1, u, hold, Y + s.h - 1, T.chain);
    L.set(u, hold, Y + s.h, T.chiseled);
    // next: another lane, and maybe one block higher (only with a short side step)
    const lanes = [-1, 0, 1].filter((x) => x !== v);
    const nv = rng.pick(lanes);
    if (h === 0 && Math.abs(nv - v) === 1 && rng.chance(0.5)) h = 1;
    v = nv;
  }
  // the reward
  const back = L.dir("u-");
  L.chest(s.u1, 0, Y + 1, chest(back), loot(rng, PARKOUR_LOOT, 4, 6));
  for (const v2 of [-2, 2]) L.set(s.u1, v2, Y + 1, rng.chance(0.5) ? T.flowering : T.azalea);
  L.set(s.u1, -1, Y + 1, candle("green", rng.int(1, 3)));
  L.set(s.u1, 1, Y + 1, T.lantern);
  // light and decoration: spore blossom, vines on the walls, glow lichen
  L.set(-1, 0, Y + s.h - 1, T.spore);
  for (let u = s.u0; u <= s.u1; u++)
    for (const vv of [-2, 2]) if (rng.chance(0.35)) hanging(L, u, vv, Y + s.h - 1, 3, rng, { ...th, lush: th.lush + 0.5 });
  for (const vv of [-3, 3]) L.set(0, vv, Y + 3, froglight(th));
  L.set(s.u1 + 1, 0, Y + 3, froglight(th));
}

function box(L, u1, v1, y1, u2, v2, y2) {
  const xa = L.x(u1, v1), xb = L.x(u2, v2), za = L.z(u1, v1), zb = L.z(u2, v2);
  return [Math.min(xa, xb), y1, Math.min(za, zb), Math.max(xa, xb), y2, Math.max(za, zb)];
}

const BUILDERS = { vestibulo: buildVestibulo, spawner: buildSpawner, jardin: buildJardin, tesoro: buildTesoro, parkour: buildParkour };

// ------------------------------------------------------------ corridors
// One 3x3 column of a corridor or a staircase at distance t along the frame.
// b: the block under your feet (floor or stair). opts.asc: stairs ascending that way.
// opts.open: no ceiling, walls up to opts.wallTo and air up to opts.open.
function column(L, t, b, th, rng, opts = {}) {
  const open = opts.open !== undefined;
  L.fill(t, -2, b - 1, t, 2, open ? opts.wallTo : b + 4, T.bricks);
  L.fill(t, -1, b + 1, t, 1, open ? opts.open : b + 3, AIR);
  const floor = [];
  if (opts.asc !== undefined) L.fill(t, -1, b, t, 1, b, stairs("tuff_brick_stairs", opts.asc));
  else
    for (let l = -1; l <= 1; l++) {
      const f = l === 0 && t % 4 === 0 ? T.chiseledBricks : floorVariant(rng, th);
      floor.push(f);
      L.set(t, l, b, f);
    }
  const wallTop = open ? Math.min(opts.wallTo, b + 3) : b + 3;
  for (const side of [-2, 2]) for (let y = b + 1; y <= wallTop; y++) if (rng.chance(0.4)) L.set(t, side, y, wallVariant(rng, th));
  if (open) return;
  for (let l = -1; l <= 1; l++) if (rng.chance(0.3)) L.set(t, l, b + 4, ceilVariant(rng, th));
  if (opts.light !== undefined) {
    L.set(t, opts.light, b + 2, froglight(th));
    return;
  }
  if (opts.asc !== undefined) {
    if (rng.chance(0.25)) L.set(t, 0, b + 3, T.lichenUp);
    return;
  }
  for (let l = -1; l <= 1; l++) {
    const c = carpetFor(floor[l + 1]);
    if (c && rng.chance(0.5)) L.set(t, l, b + 1, c);
  }
  if (opts.rib) {
    // a beam of slabs across the ceiling
    L.fill(t, -1, b + 3, t, 1, b + 3, slab("tuff_brick_slab", true));
    L.fill(t, -2, b + 1, t, -2, b + 3, T.polished);
    L.fill(t, 2, b + 1, t, 2, b + 3, T.polished);
    return;
  }
  if (rng.chance(0.35 + 0.25 * th.lush)) hanging(L, t, rng.pick([-1, 1]), b + 3, 1, rng, th);
}

// Door through a room wall at distance t: 3x3 opening with a frame.
function door(L, t, Y) {
  L.fill(t, -1, Y, t, 1, Y + 2, AIR);
  L.fill(t, -1, Y - 1, t, 1, Y - 1, T.polished);
  for (const side of [-2, 2]) L.fill(t, side, Y, t, side, Y + 2, T.chiseledBricks);
  L.fill(t, -2, Y + 3, t, 2, Y + 3, T.polished);
}

// The corridor (flat or with stairs) from room a to its child room c.
function corridor(bld, a, c, pa, pc, th, rng) {
  const d = c.dirIn;
  const L = bld.frame(pa.x, pa.z, d);
  const t0 = wallDist(a, d), t1 = GRID - wallDist(c, OPP[d]);
  const n = t1 - t0 - 1;
  const k0 = Math.floor((n - 10) / 2);
  for (let i = 0; i < n; i++) {
    const t = t0 + 1 + i;
    let b, asc;
    if (pa.Y === pc.Y) b = pa.Y - 1;
    else {
      const down = pc.Y < pa.Y;                 // going down along d
      const hi = down ? pa.Y : pc.Y, lo = down ? pc.Y : pa.Y;
      const j = (down ? i : n - 1 - i) - k0;
      if (j < 0) b = hi - 1;
      else if (j < 10) {
        b = hi - 1 - j;
        asc = down ? OPP[d] : d;
      } else b = lo - 1;
    }
    const light = i % 5 === 2 ? (i % 10 === 2 ? -2 : 2) : undefined;
    column(L, t, b, th, rng, { asc, light, rib: asc === undefined && i % 5 === 0 && i > 0 && i < n - 1 });
  }
  door(L, t0, pa.Y);
  door(L, t1, pc.Y);
}

// ------------------------------------------------------------ entrance
// The "Pórtico de Toba": a mossy roofed porch over a staircase that goes down to the hall.
function entrance(bld, origin, facing, y0, th, rng) {
  const L = bld.frame(origin.x, origin.z, facing);
  const ys = origin.y;            // the air block the player stands in
  const T0 = -3, T1 = 6, W = 4;   // the porch spans t in [T0, T1], v in [-W, W]
  L.fill(T0 - 1, -W - 1, ys, T1 + 1, W + 1, ys + 9, AIR);
  L.fill(T0, -W, ys - 4, T1, W, ys - 1, T.tuff);
  // the staircase: 16 steps, the first 4 open under the roof
  for (let t = 1; t <= 18; t++) {
    const j = t - 1;
    if (j < 16) {
      const b = ys - 1 - j;
      const opts = { asc: OPP[facing], light: t % 5 === 0 ? (t % 10 === 0 ? 2 : -2) : undefined };
      if (b + 4 > ys - 1) Object.assign(opts, { open: ys + 5, wallTo: ys - 1, light: undefined });
      column(L, t, b, th, rng, opts);
    } else column(L, t, y0 - 1, th, rng, { light: t === 17 ? 2 : undefined });
  }
  door(L, 19, y0);
  // the floor of the porch, around the hole
  const hole = (t, v) => t >= 1 && t <= 4 && Math.abs(v) <= 1;
  for (let t = T0; t <= T1; t++)
    for (let v = -W; v <= W; v++) {
      if (hole(t, v)) continue;
      const edge = t === T0 || t === T1 || Math.abs(v) === W;
      const path = Math.abs(v) <= 1 && t <= 0;
      const b = path ? (t % 2 ? T.chiseledBricks : T.polished) : edge ? T.polished : rng.chance(0.3 * th.lush + 0.1) ? T.moss : T.bricks;
      L.set(t, v, ys - 1, b);
      if (b === T.moss && !path && rng.chance(0.6)) L.set(t, v, ys, T.mossCarpet);
    }
  // railings around the hole
  for (let t = 1; t <= 4; t++) for (const v of [-2, 2]) L.set(t, v, ys, T.brickWall);
  L.fill(5, -2, ys, 5, 2, ys, T.brickWall);
  // four pillars, beams with slab arches, a roof in three tiers with eaves
  for (const t of [T0, T1])
    for (const v of [-W, W]) {
      L.set(t, v, ys, T.chiseledBricks);
      L.fill(t, v, ys + 1, t, v, ys + 3, T.polished);
      L.set(t, v, ys + 4, T.chiseled);
    }
  for (const v of [-2, 2]) L.fill(T1, v, ys + 1, T1, v, ys + 3, T.polishedWall);
  L.fill(T0, -W, ys + 5, T1, -W, ys + 5, T.bricks);
  L.fill(T0, W, ys + 5, T1, W, ys + 5, T.bricks);
  L.fill(T0, -W, ys + 5, T0, W, ys + 5, T.bricks);
  L.fill(T1, -W, ys + 5, T1, W, ys + 5, T.bricks);
  L.set(T0, 0, ys + 5, T.chiseledBricks);
  const arch = slab("tuff_brick_slab", true);
  for (const v of [-W + 1, W - 1]) {
    L.set(T0, v, ys + 4, arch);
    L.set(T1, v, ys + 4, arch);
  }
  for (const t of [T0 + 1, T1 - 1]) {
    L.set(t, -W, ys + 4, arch);
    L.set(t, W, ys + 4, arch);
  }
  L.fill(T0 - 1, -W - 1, ys + 6, T1 + 1, W + 1, ys + 6, slab("tuff_brick_slab", false));
  L.fill(T0, -W, ys + 6, T1, W, ys + 6, T.bricks);
  L.fill(T0 + 1, -W + 1, ys + 7, T1 - 1, W - 1, ys + 7, slab("polished_tuff_slab", false));
  L.fill(T0 + 2, -W + 2, ys + 7, T1 - 2, W - 2, ys + 7, T.polished);
  L.fill(T0 + 3, -1, ys + 8, T1 - 3, 1, ys + 8, slab("tuff_brick_slab", false));
  L.set(1, 0, ys + 8, T.chiseled);
  L.set(1, 0, ys + 9, T.lantern);
  // moss and azalea growing over the roof, vines hanging from the eaves
  for (let t = T0 - 1; t <= T1 + 1; t++)
    for (let v = -W - 1; v <= W + 1; v++) {
      const ring = t === T0 - 1 || t === T1 + 1 || Math.abs(v) === W + 1;
      const tier = t >= T0 + 1 && t <= T1 - 1 && Math.abs(v) <= W - 1;
      if (ring) {
        if (rng.chance(0.3 * th.lush + 0.08)) caveVines(L, t, v, ys + 5, rng.int(1, 3), rng);
      } else if (!tier) {
        if (rng.chance(0.35 * th.lush + 0.1)) L.set(t, v, ys + 7, rng.chance(0.3) ? T.leavesFlower : T.mossCarpet);
      }
    }
  for (const [t, v] of [[T0, -W], [T0, W], [T1, -W], [T1, W]]) {
    L.set(t, v, ys + 7, T.leavesFlower);
    if (rng.chance(0.6)) L.set(t, v, ys + 8, T.leaves);
  }
  // lanterns over the staircase, plants on the porch
  for (const t of [2, 4]) {
    L.set(t, 0, ys + 5, T.chain);
    L.set(t, 0, ys + 4, T.lanternHang);
  }
  for (const v of [-3, 3]) {
    L.set(-2, v, ys - 1, T.moss);
    L.set(-2, v, ys, T.flowering);
    L.set(T1 - 1, v, ys - 1, T.moss);
    L.set(T1 - 1, v, ys, T.dripleaf(L.dir(v < 0 ? "v+" : "v-")));
    L.set(0, v, ys, T.lantern);
    L.set(-1, v, ys, slab("polished_tuff_slab", false));
  }
}

// ------------------------------------------------------------ the whole dungeon
// origin: the block the player stands in (feet), the top of the entrance.
// Returns pieces in three phases (rooms, then corridors, then the entrance):
// a corridor opens doors in the walls of two rooms, so the rooms go first.
export function buildDungeon(plan, origin) {
  const th = THEMES[plan.theme];
  const [fdx, fdz] = DIRS[plan.facing];
  const ox = origin.x + fdx * VEST_OFF, oz = origin.z + fdz * VEST_OFF;
  const y0 = origin.y - ENTRY_DEPTH;
  const pos = (r) => ({ x: ox + r.gx * GRID, z: oz + r.gz * GRID, Y: y0 - r.f * FLOOR_H });
  const pieces = [];
  const out = { spawners: [] };
  for (const r of plan.rooms) {
    const bld = new Builder();
    const p = pos(r);
    BUILDERS[r.type](bld.frame(p.x, p.z, r.dirIn), SPECS[r.type], p.Y, makeRng(plan.seed, 100, r.id), th, r, out);
    pieces.push({ phase: 0, name: `${TYPE_NAME[r.type]} ${r.id}`, ops: bld.ops });
  }
  for (const r of plan.rooms) {
    if (r.parent < 0) continue;
    const bld = new Builder();
    const a = plan.rooms[r.parent];
    corridor(bld, a, r, pos(a), pos(r), th, makeRng(plan.seed, 200, r.id));
    pieces.push({ phase: 1, name: `pasillo ${a.id}-${r.id}`, ops: bld.ops });
  }
  const bld = new Builder();
  entrance(bld, origin, plan.facing, y0, th, makeRng(plan.seed, 300));
  pieces.push({ phase: 2, name: "entrada", ops: bld.ops });

  for (const p of pieces) {
    let x1 = Infinity, z1 = Infinity, x2 = -Infinity, z2 = -Infinity, y1 = Infinity, y2 = -Infinity;
    for (const op of p.ops) {
      const big = op[0] === "f";
      x1 = Math.min(x1, op[1]); y1 = Math.min(y1, op[2]); z1 = Math.min(z1, op[3]);
      x2 = Math.max(x2, big ? op[4] : op[1]); y2 = Math.max(y2, big ? op[5] : op[2]); z2 = Math.max(z2, big ? op[6] : op[3]);
    }
    p.box = [x1, y1, z1, x2, y2, z2];
  }
  const all = pieces.map((p) => p.box);
  const bounds = [0, 1, 2].map((i) => Math.min(...all.map((b) => b[i])))
    .concat([3, 4, 5].map((i) => Math.max(...all.map((b) => b[i]))));
  return { pieces, spawners: out.spawners, bounds, y0, rooms: plan.rooms.map((r) => ({ ...r, ...pos(r) })) };
}

// The lowest floor that still fits above minY (the bottom of the world).
export function maxFloorsAt(y, minY) {
  const y0 = y - ENTRY_DEPTH;
  let n = 0;
  while (n < 4 && y0 - n * FLOOR_H - 7 > minY + 1) n++;
  return n;
}
