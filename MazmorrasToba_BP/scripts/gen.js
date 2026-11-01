// Mazmorras de Toba: dungeon generator.
// Plain JavaScript with no game imports, so the same code builds the dungeon in the
// game (scripts/main.js) and in the simulation (tools/mazmorras/simulate.mjs).
//
// planDungeon() places the rooms (every room has its own size, from 5x5 to 18x18) one
// after another next to an existing room, joined by a straight corridor or staircase,
// and never overlapping anything; buildDungeon() turns the plan into block operations:
//   ["f", x1, y1, z1, x2, y2, z2, block]   fill a box
//   ["s", x, y, z, block]                  set one block
//   ["c", x, y, z, block, items]           chest with items [[id, count], ...]
// A block is an id string or { id, states, alt: [other blocks to try] }.

export const FLOOR_H = 10;     // height between two floors
export const ENTRY_DEPTH = 16; // the first floor is this many blocks under the entrance
export const MAX_FLOORS = 6;
const ENTRY_STEPS = 18;        // the entrance staircase: 16 steps and 2 landing blocks

// Directions. Stairs ascend towards the direction of their weirdo_direction.
export const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]]; // east, west, south, north
export const OPP = [1, 0, 3, 2];
const PERP = [2, 3, 1, 0];                               // the +v side of a frame looking along d
const CARD = ["east", "west", "south", "north"];
const VINE_BIT = [8, 2, 1, 4];                           // vine_direction_bits: the side it hangs from
export const DIR_NAME = ["este", "oeste", "sur", "norte"];

// ------------------------------------------------------------ themes
export const THEMES = {
  ruinas: {
    name: "Ruinas Frondosas", desc: "equilibrada: generadores, parkour y jardines", bonus: 0,
    parkour: 0.22, spawner: 0.65, down: 0.5, lush: 0.6, pale: 0.12, light: "ochre_froglight", wood: ["oak", "spruce", "mangrove"],
    mobs: [["zombis", 3], ["esqueletos", 3], ["aranas", 2], ["ahogados", 2], ["lepismas", 1], ["breeze", 1]],
  },
  cripta: {
    name: "Cripta de Toba", desc: "difícil: más generadores, musgo pálido, muy profunda", bonus: 8,
    parkour: 0.12, spawner: 0.85, down: 0.62, lush: 0.3, pale: 0.7, light: "pearlescent_froglight", wood: ["dark_oak", "spruce", "pale_oak"],
    mobs: [["esqueletos", 3], ["pantanosos", 2], ["zombis", 2], ["aranas", 2], ["breeze", 2]],
  },
  jardin: {
    name: "Jardín Colgante", desc: "muy frondosa, con más salas de parkour", bonus: 3,
    parkour: 0.35, spawner: 0.5, down: 0.45, lush: 0.95, pale: 0.05, light: "verdant_froglight", wood: ["mangrove", "jungle", "cherry"],
    mobs: [["pantanosos", 3], ["aranas", 2], ["ahogados", 2], ["zombis", 1]],
  },
  abismo: {
    name: "Mazmorras Abisales", desc: "muy difícil: cuevas de pizarra profunda, simas, lava y casi sin luz", bonus: 14,
    style: "abismo", parkour: 0.2, spawner: 0.55, down: 0.6, lush: 0, pale: 0, light: "pearlescent_froglight", wood: ["dark_oak"],
    mobs: [["esqueletos_abismo", 3], ["zombis", 2], ["aranas", 2], ["lepismas", 1], ["blazes", 2], ["breeze", 1]],
    guardians: "guardianes_abismo",
  },
};
export const THEME_KEYS = Object.keys(THEMES);
const isAbyss = (th) => th.style === "abismo";

export const MOB_FAMILIES = {
  zombis: ["minecraft:zombie", "minecraft:husk"],
  esqueletos: ["minecraft:skeleton", "minecraft:bogged"],
  pantanosos: ["minecraft:bogged"],
  aranas: ["minecraft:spider", "minecraft:cave_spider"],
  ahogados: ["minecraft:drowned"],
  lepismas: ["minecraft:silverfish"],
  breeze: ["minecraft:breeze"],
  guardianes: ["minecraft:bogged", "minecraft:stray", "minecraft:breeze"],
  esqueletos_abismo: ["minecraft:skeleton", "minecraft:stray"],
  blazes: ["minecraft:blaze"],
  guardianes_abismo: ["minecraft:wither_skeleton", "minecraft:blaze", "minecraft:stray"],
};

export const TYPE_NAME = {
  vestibulo: "vestíbulo", spawner: "generador", parkour: "parkour", jardin: "jardín", tesoro: "tesoro", arbol: "gran árbol",
  sima: "sima", torre: "torre del tótem",
};

// The entrance gets grander with the difficulty (and rarity) of the dungeon.
export const ENTRANCES = ["Pórtico de Toba", "Pórtico Mayor", "Templo Frondoso", "Gran Santuario de Toba"];

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
// The copper grate barrier of the corridors stays a normal (breakable) block; the bridges of the
// abyss use another grate, which becomes indestructible like the rest of the dungeon.
export const BARRIER = mc("waxed_copper_grate");
const T = {
  tuff: mc("tuff"), polished: mc("polished_tuff"), bricks: mc("tuff_bricks"), chiseled: mc("chiseled_tuff"),
  chiseledBricks: mc("chiseled_tuff_bricks"), brickWall: mc("tuff_brick_wall"), polishedWall: mc("polished_tuff_wall"),
  moss: mc("moss_block"), mossCarpet: mc("moss_carpet"), paleMoss: mc("pale_moss_block"),
  paleCarpet: mc("pale_moss_carpet"), rooted: mc("dirt_with_roots"), clay: mc("clay"), water: mc("water"),
  azalea: mc("azalea"), flowering: mc("flowering_azalea"), spore: mc("spore_blossom"), roots: mc("hanging_roots"),
  fern: mc("fern"), grass: mc("short_grass"), mangroveRoots: mc("mangrove_roots"),
  leaves: st("azalea_leaves", { persistent_bit: true }),
  leavesFlower: st("azalea_leaves_flowered", { persistent_bit: true }),
  lichenUp: st("glow_lichen", { multi_face_direction_bits: 2 }),
  lantern: st("lantern", { hanging: false }), lanternHang: st("lantern", { hanging: true }),
  chain: st("chain", { pillar_axis: "y" }, [st("iron_chain", { pillar_axis: "y" })]),
  dripleaf: (d) => st("big_dripleaf", { big_dripleaf_head: true, big_dripleaf_tilt: "none", "minecraft:cardinal_direction": CARD[d] }),
  log: (axis) => st("oak_log", { pillar_axis: axis }),
};
const slab = (id, top) => st(id, { "minecraft:vertical_half": top ? "top" : "bottom" });
const woodSlab = (wood, top) => st(`${wood}_slab`, { "minecraft:vertical_half": top ? "top" : "bottom" },
  [st("oak_slab", { "minecraft:vertical_half": top ? "top" : "bottom" })]);
const stairs = (id, asc, upside = false) => st(id, { weirdo_direction: asc, upside_down_bit: upside });
const chest = (d) => st("chest", { "minecraft:cardinal_direction": CARD[d] });
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
const lusher = (th, k) => ({ ...th, lush: Math.min(1, th.lush + k) });

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
  // a structure of the pack placed there (the item frame with the totem)
  struct(x, y, z, name) {
    this.ops.push(["t", x, y, z, name]);
  }
  // A frame centred on (cx, cz) looking along direction d: u forwards, v to the side.
  frame(cx, cz, d) {
    return frame(cx, cz, d, this);
  }
}
function frame(cx, cz, d, b) {
  const [dx, dz] = DIRS[d];
  const px = -dz, pz = dx;
  const X = (u, v) => cx + u * dx + v * px, Z = (u, v) => cz + u * dz + v * pz;
  return {
    d,
    // the world direction of a local direction: "u+", "u-", "v+", "v-"
    dir: (k) => ({ "u+": d, "u-": OPP[d], "v+": PERP[d], "v-": OPP[PERP[d]] })[k],
    local: (wd) => (wd === d ? "u+" : wd === OPP[d] ? "u-" : wd === PERP[d] ? "v+" : "v-"),
    axis: (k) => ((k === "u") === (d < 2) ? "x" : "z"),
    fill: (u1, v1, y1, u2, v2, y2, blk) => b.fill(X(u1, v1), y1, Z(u1, v1), X(u2, v2), y2, Z(u2, v2), blk),
    set: (u, v, y, blk) => b.set(X(u, v), y, Z(u, v), blk),
    chest: (u, v, y, blk, items) => b.chest(X(u, v), y, Z(u, v), blk, items),
    struct: (u, v, y, name) => b.struct(X(u, v), y, Z(u, v), name),
    x: X, z: Z,
  };
}

// Cave vines hanging from the block above yTop, len blocks long, almost all with glow berries.
function caveVines(L, u, v, yTop, len, rng, berries = 0.6) {
  for (let k = 0; k < len; k++) {
    const head = k === len - 1, b = rng.chance(berries);
    const id = head ? (b ? "cave_vines_head_with_berries" : "cave_vines") : (b ? "cave_vines_body_with_berries" : "cave_vines");
    L.set(u, v, yTop - k, mc(id));
  }
}
function paleMoss(L, u, v, yTop, len) {
  for (let k = 0; k < len; k++) L.set(u, v, yTop - k, st("pale_hanging_moss", { tip: k === len - 1 }));
}
// Something hanging from the ceiling, depending on the theme: mostly glow berries.
function hanging(L, u, v, yTop, maxLen, rng, th) {
  const k = rng.weighted([["vines", 0.3 + th.lush], ["pale", th.pale * 0.7], ["roots", 0.2], ["lichen", 0.25]]);
  if (k === "vines") caveVines(L, u, v, yTop, rng.int(1, Math.max(1, maxLen)), rng);
  else if (k === "pale") paleMoss(L, u, v, yTop, rng.int(1, Math.max(1, maxLen)));
  else if (k === "roots") L.set(u, v, yTop, T.roots);
  else L.set(u, v, yTop, T.lichenUp);
}

// ------------------------------------------------------------ room shapes
// Every room has its own size: L along the way in (u), W across (v), h of air.
const sizeOf = (rng) => rng.weighted([[[5, 7], 4], [[8, 12], 3.5], [[13, 18], 1.6]]);
const rint = (rng, [lo, hi]) => rng.int(lo, hi);

function makeSpec(type, rng, abyss = false) {
  if (abyss) return makeAbyssSpec(type, rng);
  let L, W, h;
  switch (type) {
    case "vestibulo": L = rng.int(7, 11); W = rng.int(7, 11); break;
    case "spawner": L = rint(rng, sizeOf(rng)); W = rint(rng, sizeOf(rng)); break;
    case "jardin": L = rng.int(7, 15); W = rng.int(7, 15); break;
    case "tesoro": L = rng.int(9, 15); W = rng.int(9, 15); break;
    case "parkour": L = rng.int(8, 16); W = rng.int(5, 7); h = 8; break;
    case "arbol": L = rng.int(16, 18); W = rng.int(16, 18); h = 16; break;
    // 20 long and 40 high: 10 of air over the door, 30 down to the lava
    case "torre": L = 20; W = rng.int(9, 11); h = 10; break;
  }
  h ??= Math.min(9, 5 + Math.floor(Math.max(L, W) / 4));
  const u0 = -Math.floor((L - 1) / 2), v0 = -Math.floor((W - 1) / 2);
  const bottom = type === "parkour" ? -6 : type === "torre" ? -30 : type === "jardin" || type === "arbol" ? -2 : -1;
  return { type, L, W, h, u0, u1: u0 + L - 1, v0, v1: v0 + W - 1, bottom };
}

// The main hall of a cave-entrance dungeon: bigger than every other room.
function caveHallSpec(rng, abyss) {
  const L = abyss ? rng.int(34, 38) : rng.int(20, 26), W = abyss ? rng.int(34, 38) : rng.int(20, 26);
  const u0 = -Math.floor((L - 1) / 2), v0 = -Math.floor((W - 1) / 2);
  return { type: "vestibulo", L, W, h: abyss ? 16 : 12, u0, u1: u0 + L - 1, v0, v1: v0 + W - 1, bottom: -2, natural: true };
}

// Abyss rooms: 20x20 at least, 32x32 at most.
function makeAbyssSpec(type, rng) {
  let L, W, h, bottom = -1;
  const big = () => rng.weighted([[[20, 24], 3], [[25, 28], 2], [[29, 32], 1]]);
  switch (type) {
    case "vestibulo": L = rng.int(20, 24); W = rng.int(20, 24); h = 11; break;
    case "spawner": L = rint(rng, big()); W = rint(rng, big()); h = 11 + Math.floor((Math.max(L, W) - 20) / 3); break;
    case "sima": L = rint(rng, big()); W = rint(rng, big()); h = 12 + Math.floor((Math.max(L, W) - 20) / 3); bottom = -16; break;
    case "parkour": L = rng.int(24, 32); W = rng.int(20, 24); h = 14; bottom = -6; break;
    case "tesoro": L = rng.int(22, 28); W = rng.int(20, 26); h = 14; break;
  }
  const u0 = -Math.floor((L - 1) / 2), v0 = -Math.floor((W - 1) / 2);
  return { type, L, W, h, u0, u1: u0 + L - 1, v0, v1: v0 + W - 1, bottom };
}

function wallDist(room, dir) {
  const s = room.spec;
  if (dir === room.dirIn) return s.u1 + 1;
  if (dir === OPP[room.dirIn]) return -s.u0 + 1;
  return dir === PERP[room.dirIn] ? s.v1 + 1 : -s.v0 + 1;
}

// World box of a local box, in coordinates relative to the hall (plan) or absolute (build).
function worldBox(cx, cz, d, u1, v1, u2, v2, y1, y2) {
  const F = frame(cx, cz, d, null);
  const xa = F.x(u1, v1), xb = F.x(u2, v2), za = F.z(u1, v1), zb = F.z(u2, v2);
  return [Math.min(xa, xb), y1, Math.min(za, zb), Math.max(xa, xb), y2, Math.max(za, zb)];
}
const overlaps = (a, b, m) => a[0] <= b[3] + m && b[0] <= a[3] + m && a[1] <= b[4] + m && b[1] <= a[4] + m &&
  a[2] <= b[5] + m && b[2] <= a[5] + m;
const roomBoxOf = (r, x = r.cx, z = r.cz) => worldBox(x, z, r.dirIn, r.spec.u0 - 1, r.spec.v0 - 1, r.spec.u1 + 1, r.spec.v1 + 1,
  r.Y + r.spec.bottom, r.Y + r.spec.h);

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
const TREE_LOOT = [["glow_berries", 8, 24, 10], ["golden_apple", 1, 3, 8], ["emerald", 4, 10, 8], ["diamond", 1, 3, 5],
  ["azalea", 2, 4, 5], ["flowering_azalea", 2, 4, 5], ["spore_blossom", 1, 2, 4], ["experience_bottle", 4, 10, 6],
  ["enchanted_golden_apple", 1, 1, 1], ["oak_sapling", 2, 6, 4]];
const TREASURE_LOOT = [["diamond", 3, 6, 10], ["emerald", 8, 16, 10], ["golden_apple", 2, 3, 8],
  ["enchanted_golden_apple", 1, 1, 3], ["totem_of_undying", 1, 1, 3], ["netherite_scrap", 1, 2, 3],
  ["experience_bottle", 8, 16, 8], ["ominous_trial_key", 1, 1, 4], ["trial_key", 2, 3, 6], ["diamond_block", 1, 1, 1],
  ["heavy_core", 1, 1, 1], ["flow_banner_pattern", 1, 1, 2], ["music_disc_precipice", 1, 1, 2]];

// ------------------------------------------------------------ plan
// opts: { seed, rooms, floors, theme, facing, parkour }
export function planDungeon(opts) {
  const theme = opts.theme in THEMES ? opts.theme : "ruinas";
  const th = THEMES[theme];
  const rng = makeRng(opts.seed, 1);
  const facing = opts.facing;
  const floors = Math.max(1, Math.min(MAX_FLOORS, opts.floors));
  const n = opts.rooms;

  const abyss = isAbyss(th);
  // which rooms: one giant tree hall, parkour rooms and the treasure are dead ends
  const nTree = n >= 6 && floors >= 2 && !abyss ? 1 : 0;
  const nTower = n >= 6 && !abyss ? 1 : 0; // the Torre del Tótem
  const nParkour = opts.parkour === false ? 0
    : Math.max(0, Math.min(Math.max(1, Math.round(n * th.parkour)), n - 2 - nTree - nTower));
  const nInner = n - 1 - nParkour - nTree - nTower;
  const inner = [];
  const second = abyss ? "sima" : "jardin";
  for (let i = 0; i < nInner; i++) inner.push(rng.chance(th.spawner) ? "spawner" : second);
  for (let i = 0; i < Math.min(2, nInner); i++) inner[i] = "spawner";
  if (nInner >= 4 && !inner.includes(second)) inner[nInner - 1] = second;
  const order = rng.shuffle(inner);
  if (nTree) order.splice(rng.int(Math.floor(order.length / 3), order.length), 0, "arbol");
  if (nTower) order.push("torre");
  for (let i = 0; i < nParkour; i++) order.push("parkour");
  order.push("tesoro");
  const cave = !!opts.cave;
  const maxDepth = opts.maxDepth ?? 1e9; // how far under the hall floor a room may reach

  // the hall: everything is placed relative to its centre (0, 0) and its floor (y = 0)
  const vest = { id: 0, type: "vestibulo", spec: cave ? caveHallSpec(rng, abyss) : makeSpec("vestibulo", rng, abyss), cx: 0, cz: 0,
    f: 0, Y: 0, dirIn: facing, parent: -1, depth: 0, kids: [], used: new Set([OPP[facing]]) };
  // normal: the staircase reaches the back wall of the hall; cave: the hall is where the player stands
  const vestOff = cave ? 0 : ENTRY_STEPS + 2 - vest.spec.u0;
  const list = [vest];
  const boxes = [{ box: roomBoxOf(vest), owner: 0 }, cave
    // the tunnels that join the hall with the caves around it
    ? { box: worldBox(0, 0, facing, vest.spec.u0 - 30, -9, vest.spec.u0 - 1, 9, -4, 24), owner: -1 }
    // the entrance staircase, from the surface down to the hall
    : { box: worldBox(0, 0, facing, -vestOff - 8, -6, vest.spec.u0 - 2, 6, -4, ENTRY_DEPTH + 24), owner: -1 }];
  // the highest a room of the first floor may reach (under the surface)
  const topLimit = cave ? vest.spec.h + 2 : ENTRY_DEPTH - 5;
  const leaf = (t) => t === "parkour" || t === "tesoro" || t === "torre";

  for (const type of order) {
    let placed = false;
    for (let attempt = 0; attempt < (abyss ? 240 : 120) && !placed; attempt++) {
      const cands = list.filter((r) => !leaf(r.type) && r.kids.length < 3 && r.used.size < 4);
      if (!cands.length) break;
      let parent;
      if (type === "tesoro") {
        // the treasure goes as deep as possible
        const deep = cands.slice().sort((a, b) => b.f * 100 + b.depth - (a.f * 100 + a.depth));
        parent = deep[Math.min(deep.length - 1, Math.floor(attempt / 8))];
      } else {
        const k = rng.next();
        if (k < 0.45) parent = cands[Math.max(0, cands.length - 1 - rng.int(0, 2))];
        else if (k < 0.75) {
          // grow from the deepest floor reached: the dungeon keeps going down
          const fMax = Math.max(...cands.map((r) => r.f));
          parent = rng.pick(cands.filter((r) => r.f === fMax));
        } else parent = rng.pick(cands);
      }
      const dir = rng.pick([0, 1, 2, 3].filter((d) => !parent.used.has(d)));
      let f = parent.f;
      const canDown = parent.f + 1 < floors;
      if (canDown && (type === "tesoro" || rng.chance(th.down))) f++;
      else if (f > 0 && rng.chance(0.05)) f--;
      if (type === "arbol" && f < 1) {
        if (!canDown) continue;
        f = parent.f + 1;
      }
      const spec = makeSpec(type, rng, abyss);
      // the rooms of the first floor stay well under the surface
      if (-f * FLOOR_H + spec.h > topLimit || -f * FLOOR_H + spec.bottom < -maxDepth) continue;
      const stair = f !== parent.f;
      const len = stair ? rng.int(12, abyss ? 18 : 15) : abyss ? rng.int(8, 18) : rng.int(3, 8);
      const half = abyss ? 3 : 2;
      const t0 = wallDist(parent, dir);
      const D = t0 + len + 1 + (-spec.u0 + 1);
      const room = {
        id: list.length, type, spec, f, Y: -f * FLOOR_H, dirIn: dir, parent: parent.id, depth: parent.depth + 1,
        cx: parent.cx + DIRS[dir][0] * D, cz: parent.cz + DIRS[dir][1] * D, kids: [], used: new Set([OPP[dir]]),
      };
      const rb = roomBoxOf(room);
      const cb = worldBox(parent.cx, parent.cz, dir, t0 + 1, -half, t0 + len, half,
        Math.min(room.Y, parent.Y) - (abyss ? 4 : 2), Math.max(room.Y, parent.Y) + 4);
      // the corridor starts at the parent's wall: only the parent may touch it
      if (boxes.some((b) => overlaps(b.box, rb, 2)) || boxes.some((b) => b.owner !== parent.id && overlaps(b.box, cb, 1))) continue;
      boxes.push({ box: rb, owner: room.id }, { box: cb, owner: -2 });
      parent.kids.push(room.id);
      parent.used.add(dir);
      list.push(room);
      placed = true;
    }
  }

  for (const r of list.slice(1))
    if (r.type === "spawner" || r.type === "sima" || r.type === "tesoro")
      r.mobs = r.type === "tesoro" ? th.guardians ?? "guardianes"
        : rng.weighted(th.mobs.filter(([k]) => !(k === "breeze" || k === "blazes") || r.f > 0));

  const floorsUsed = new Set(list.map((r) => r.f)).size;
  const counts = {};
  for (const r of list.slice(1)) counts[r.type] = (counts[r.type] ?? 0) + 1;
  // difficulty: rooms, floors and theme; now and then a dungeon is rare and gets a grander entrance
  const score = list.length - 1 + floorsUsed * 3 + th.bonus;
  const rare = rng.chance(0.12);
  const tier = Math.min(4, (score < 17 ? 1 : score < 27 ? 2 : score < 37 ? 3 : 4) + (rare ? 1 : 0));
  return { seed: opts.seed, theme, facing, rooms: list, floorsUsed, counts, vestOff, tier, rare, wanted: n, abyss, cave };
}

// ------------------------------------------------------------ rooms
// c: { L, s, Y, rng, th, room, out, doors } (doors: the local walls with a door)
function inLane(c, u, v) {
  const s = c.s;
  return (c.doors.has("u-") && u <= s.u0 + 1 && Math.abs(v) <= 1) || (c.doors.has("u+") && u >= s.u1 - 1 && Math.abs(v) <= 1) ||
    (c.doors.has("v-") && v <= s.v0 + 1 && Math.abs(u) <= 1) || (c.doors.has("v+") && v >= s.v1 - 1 && Math.abs(u) <= 1);
}
const onCross = (u, v) => Math.abs(u) <= 1 || Math.abs(v) <= 1; // keep the ways between doors free
const isBorder = (s, u, v) => u === s.u0 || u === s.u1 || v === s.v0 || v === s.v1;

function shell(c) {
  const { L, s, Y } = c;
  L.fill(s.u0 - 1, s.v0 - 1, Y + s.bottom, s.u1 + 1, s.v1 + 1, Y + s.h, T.bricks);
  L.fill(s.u0, s.v0, Y + s.bottom + 1, s.u1, s.v1, Y + s.h - 1, AIR);
}
function wallOverlay(c, y1, y2, p = 0.35, th = c.th) {
  const { L, s, rng } = c;
  for (let y = y1; y <= y2; y++) {
    for (let u = s.u0; u <= s.u1; u++) {
      if (rng.chance(p)) L.set(u, s.v0 - 1, y, wallVariant(rng, th));
      if (rng.chance(p)) L.set(u, s.v1 + 1, y, wallVariant(rng, th));
    }
    for (let v = s.v0; v <= s.v1; v++) {
      if (rng.chance(p)) L.set(s.u0 - 1, v, y, wallVariant(rng, th));
      if (rng.chance(p)) L.set(s.u1 + 1, v, y, wallVariant(rng, th));
    }
  }
}
function ceilOverlay(c, p = 0.4, th = c.th) {
  const { L, s, rng, Y } = c;
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) if (rng.chance(p)) L.set(u, v, Y + s.h, ceilVariant(rng, th));
}
// Floor with a polished border; center(u, v) can choose a block. Returns the chosen blocks.
function roomFloor(c, center) {
  const { L, s, Y, rng, th } = c;
  const out = new Map();
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) {
      const b = isBorder(s, u, v) ? (rng.chance(0.75) ? T.polished : floorVariant(rng, th)) : (center?.(u, v) ?? floorVariant(rng, th));
      L.set(u, v, Y - 1, b);
      out.set(`${u},${v}`, b);
    }
  return out;
}
function carpets(c, floor, p, skip) {
  for (const [k, b] of floor) {
    const cp = carpetFor(b);
    if (!cp || !c.rng.chance(p)) continue;
    const [u, v] = k.split(",").map(Number);
    if (skip?.(u, v)) continue;
    c.L.set(u, v, c.Y, cp);
  }
}
// The cornice: top slabs along the inside of the walls, just under the ceiling.
function cornice(c, mat = "tuff_brick_slab") {
  const { L, s, Y } = c;
  const b = slab(mat, true), y = Y + s.h - 1;
  L.fill(s.u0, s.v0, y, s.u1, s.v0, y, b);
  L.fill(s.u0, s.v1, y, s.u1, s.v1, y, b);
  L.fill(s.u0, s.v0, y, s.u0, s.v1, y, b);
  L.fill(s.u1, s.v0, y, s.u1, s.v1, y, b);
}
// Froglights in the walls, away from the door lintels.
function wallLights(c, y) {
  const { L, s, th } = c;
  // dim: one light in the middle of each long wall (away from the door lintels), and only in big rooms
  if (Math.max(s.L, s.W) < 11) return;
  const mark = (a, b) => [a + Math.floor((b - a + 1) / 4)].filter((k) => Math.abs(k) >= 3);
  if (s.L >= 11) for (const u of mark(s.u0, s.u1)) {
    L.set(u, s.v0 - 1, y, froglight(th));
    L.set(-u, s.v1 + 1, y, froglight(th));
  }
  if (s.W >= 11) for (const v of mark(s.v0, s.v1)) {
    L.set(s.u0 - 1, -v, y, froglight(th));
    L.set(s.u1 + 1, v, y, froglight(th));
  }
}
// Glow berries and other things hanging from the ceiling, about one every `per` cells.
function ceilingLife(c, per, maxLen, skip) {
  const { L, s, Y, rng, th } = c;
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) {
      if (skip?.(u, v) || !rng.chance(1 / per)) continue;
      hanging(L, u, v, Y + s.h - 1, maxLen, rng, th);
    }
}
function pillar(c, u, v, top) {
  const { L, Y, rng } = c;
  L.set(u, v, Y, T.chiseledBricks);
  L.fill(u, v, Y + 1, u, v, top - 1, rng.chance(0.5) ? T.polished : T.bricks);
  L.set(u, v, top, T.chiseled);
  if (rng.chance(0.5 * c.th.lush + 0.1)) L.set(u, v, Y + rng.int(1, 3), T.moss);
}

function buildVestibulo(c) {
  const { L, s, Y, rng } = c;
  shell(c);
  wallOverlay(c, Y, Y + s.h - 1);
  ceilOverlay(c);
  const floor = roomFloor(c, (u, v) => Math.abs(u) <= 1 && Math.abs(v) <= 1 ? T.moss
    : Math.abs(u) <= 2 && Math.abs(v) <= 2 ? T.bricks : null);
  carpets(c, floor, 0.6, (u, v) => isBorder(s, u, v));
  cornice(c);
  L.set(0, 0, Y + s.h - 1, T.spore);
  L.set(0, 0, Y + s.h, T.chiseled);
  for (const u of [s.u0, s.u1])
    for (const v of [s.v0, s.v1]) {
      L.set(u, v, Y - 1, T.moss);
      L.set(u, v, Y, rng.chance(0.6) ? T.flowering : T.azalea);
    }
  for (const [u, v] of [[s.u0 + 1, s.v0 + 1], [s.u1 - 1, s.v1 - 1]]) {
    L.fill(u, v, Y + 4, u, v, Y + s.h - 1, T.chain);
    L.set(u, v, Y + 3, T.lanternHang);
  }
  // benches along the side walls
  for (const u of [s.u0 + 1, s.u1 - 1]) {
    if (!inLane(c, u, s.v0)) L.set(u, s.v0, Y, stairs("polished_tuff_stairs", L.dir("v-")));
    if (!inLane(c, u, s.v1)) L.set(u, s.v1, Y, stairs("polished_tuff_stairs", L.dir("v+")));
  }
  ceilingLife(c, 7, 2, (u, v) => Math.abs(u) <= 1 && Math.abs(v) <= 1);
  wallLights(c, Y + 3);
}

function buildSpawner(c) {
  const { L, s, Y, rng, th, room, out } = c;
  shell(c);
  wallOverlay(c, Y, Y + s.h - 1, 0.3);
  // a band of chiseled tuff bricks above the doors and a cornice of slabs
  L.fill(s.u0 - 1, s.v0 - 1, Y + 3, s.u1 + 1, s.v0 - 1, Y + 3, T.chiseledBricks);
  L.fill(s.u0 - 1, s.v1 + 1, Y + 3, s.u1 + 1, s.v1 + 1, Y + 3, T.chiseledBricks);
  L.fill(s.u0 - 1, s.v0 - 1, Y + 3, s.u0 - 1, s.v1 + 1, Y + 3, T.chiseledBricks);
  L.fill(s.u1 + 1, s.v0 - 1, Y + 3, s.u1 + 1, s.v1 + 1, Y + 3, T.chiseledBricks);
  ceilOverlay(c, 0.3);
  L.set(0, 0, Y + s.h, T.chiseled);
  const ring = (u, v) => Math.max(Math.abs(u), Math.abs(v));
  const floor = roomFloor(c, (u, v) => ring(u, v) === 0 ? T.chiseledBricks : ring(u, v) === 1 ? T.bricks
    : ring(u, v) % 4 === 0 ? T.polished : null);
  carpets(c, floor, 0.3, (u, v) => ring(u, v) <= 1);
  cornice(c, "polished_tuff_slab");
  // corner posts with lanterns
  for (const u of [s.u0, s.u1])
    for (const v of [s.v0, s.v1]) {
      L.set(u, v, Y, T.brickWall);
      L.set(u, v, Y + 1, candle("green", rng.int(1, 3)));
    }
  // big rooms: pillars, azalea in the corners
  const big = s.L >= 11 && s.W >= 11;
  if (big)
    for (const u of [s.u0 + 3, s.u1 - 3])
      for (const v of [s.v0 + 3, s.v1 - 3]) if (!onCross(u, v)) pillar(c, u, v, Y + s.h - 1);
  if (s.L * s.W >= 80)
    for (const [u, v] of [[s.u0 + 1, s.v0], [s.u0, s.v0 + 1], [s.u1 - 1, s.v1], [s.u1, s.v1 - 1]])
      if (!inLane(c, u, v) && rng.chance(0.4 * th.lush + 0.2)) L.set(u, v, Y, rng.chance(0.5) ? T.leavesFlower : T.leaves);
  ceilingLife(c, 6, Math.min(3, s.h - 3), (u, v) => ring(u, v) === 0);
  wallLights(c, Y + 2);
  L.set(0, 0, Y, trialSpawner(false));
  out.spawners.push({
    x: L.x(0, 0), y: Y, z: L.z(0, 0), kind: "normal", family: room.mobs, room: room.id,
    bonus: Math.max(0, Math.floor((s.L * s.W - 25) / 40)) + c.tier - 1,
    box: boxOf(L, s.u0, s.v0, Y, s.u1, s.v1, Y + s.h - 1),
  });
}

function buildJardin(c) {
  const { L, s, Y, rng, th } = c;
  shell(c);
  L.fill(s.u0, s.v0, Y - 2, s.u1, s.v1, Y - 2, T.clay);
  wallOverlay(c, Y, Y + s.h - 1, 0.45, lusher(th, 0.4));
  ceilOverlay(c, 0.6, lusher(th, 0.5));
  // moss floor, a pond in the middle with dripleaves around and a border of slabs
  const floor = new Map();
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) {
      const b = rng.chance(0.15) ? T.rooted : th.pale > 0.5 && rng.chance(0.4) ? T.paleMoss : T.moss;
      L.set(u, v, Y - 1, b);
      floor.set(`${u},${v}`, b);
    }
  const pr = Math.max(1, Math.floor(Math.min(s.L, s.W) / 5));
  for (let u = -pr; u <= pr; u++)
    for (let v = -pr; v <= pr; v++) {
      const corner = Math.abs(u) === pr && Math.abs(v) === pr;
      floor.delete(`${u},${v}`);
      if (corner) {
        L.set(u, v, Y - 1, T.clay);
        L.set(u, v, Y, T.dripleaf(rng.int(0, 3)));
      } else L.set(u, v, Y - 1, T.water);
    }
  for (let u = -pr - 1; u <= pr + 1; u++)
    for (let v = -pr - 1; v <= pr + 1; v++) {
      if (Math.max(Math.abs(u), Math.abs(v)) !== pr + 1 || u < s.u0 || u > s.u1 || v < s.v0 || v > s.v1) continue;
      if (rng.chance(0.6) || onCross(u, v)) {
        L.set(u, v, Y, slab("tuff_brick_slab", false));
        floor.delete(`${u},${v}`);
      }
    }
  // corners: azalea bushes, one of them may hold a chest
  const corners = rng.shuffle([[s.u1, s.v1], [s.u1, s.v0], [s.u0, s.v1], [s.u0, s.v0]]);
  const withChest = rng.chance(0.5) ? corners[0] : null;
  for (const [u, v] of corners) {
    floor.delete(`${u},${v}`);
    if (withChest && u === withChest[0] && v === withChest[1]) {
      c.L.chest(u, v, Y, chest(L.dir(u > 0 ? "u-" : "u+")), loot(rng, GARDEN_LOOT, 3, 5));
      L.set(u, v, Y + 1, T.leavesFlower);
      continue;
    }
    L.set(u, v, Y, rng.chance(0.5) ? T.leavesFlower : T.leaves);
    L.set(u, v, Y + 1, rng.chance(0.5) ? T.flowering : T.azalea);
  }
  // plants on the moss, bushes along the walls in big gardens
  for (const [k] of floor) {
    const [u, v] = k.split(",").map(Number);
    if (inLane(c, u, v)) continue;
    const r = rng.next();
    if (r < 0.12) L.set(u, v, Y, rng.chance(0.4) ? T.fern : T.grass), floor.delete(k);
    else if (r < 0.17 && !onCross(u, v)) L.set(u, v, Y, rng.chance(0.5) ? T.azalea : T.flowering), floor.delete(k);
    else if (r < 0.22 && isBorder(s, u, v) && !onCross(u, v)) L.set(u, v, Y, T.leaves), floor.delete(k);
  }
  carpets(c, floor, 0.45);
  // the ceiling: spore blossoms, lots of glow berries
  L.set(0, 0, Y + s.h - 1, T.spore);
  for (let i = 1; i < Math.floor((s.L * s.W) / 45); i++) L.set(rng.int(s.u0, s.u1), rng.int(s.v0, s.v1), Y + s.h - 1, T.spore);
  ceilingLife(c, 3.5, 3, (u, v) => u === 0 && v === 0);
}

function buildTesoro(c) {
  const { L, s, Y, rng, th, room, out } = c;
  shell(c);
  wallOverlay(c, Y, Y + s.h - 1, 0.3);
  ceilOverlay(c, 0.35);
  const floor = roomFloor(c, (u, v) => ((u + v) & 1 ? T.polished : T.bricks));
  const su = Math.min(-1, s.u1 - 5); // the guardian spawner
  for (let u = s.u0; u < su; u++) {
    L.set(u, 0, Y - 1, T.moss);
    L.set(u, 0, Y, T.mossCarpet);
  }
  carpets(c, floor, 0.25, (u, v) => u >= s.u1 - 2 || v === 0);
  // pillars along the side walls
  for (let u = s.u0 + 2; u <= s.u1 - 3; u += 3)
    for (const v of [s.v0, s.v1]) pillar(c, u, v, Y + s.h - 2);
  cornice(c);
  // the dais at the back: a slab step, the chest between two vaults, candles
  const back = L.dir("u-");
  L.fill(s.u1 - 2, s.v0 + 1, Y, s.u1 - 2, s.v1 - 1, Y, slab("polished_tuff_slab", false));
  L.fill(s.u1 - 1, s.v0 + 1, Y, s.u1, s.v1 - 1, Y, T.polished);
  L.fill(s.u1, s.v0, Y, s.u1, s.v1, Y, T.chiseledBricks);
  L.chest(s.u1, 0, Y + 1, chest(back), loot(rng, TREASURE_LOOT, 6, 8));
  L.set(s.u1, -2, Y + 1, vault(back, false));
  L.set(s.u1, 2, Y + 1, vault(back, true));
  for (const v of [-1, 1]) L.set(s.u1, v, Y + 1, candle("lime", rng.int(2, 4)));
  for (const v of [s.v0 + 1, s.v1 - 1]) L.set(s.u1 - 1, v, Y + 1, candle("white", rng.int(1, 3)));
  for (const v of [s.v0, s.v1]) {
    L.set(s.u1, v, Y + 1, T.leavesFlower);
    L.set(s.u1, v, Y + 2, T.flowering);
    L.set(s.u0, v, Y, T.leaves);
    L.set(s.u0, v, Y + 1, T.leavesFlower);
  }
  for (const [u, v] of [[s.u0 + 2, s.v0 + 2], [s.u1 - 3, s.v1 - 2]]) {
    L.fill(u, v, Y + 4, u, v, Y + s.h - 1, T.chain);
    L.set(u, v, Y + 3, T.lanternHang);
  }
  L.set(s.u0 + 1, 0, Y + s.h - 1, T.spore);
  ceilingLife(c, 6, 2, (u, v) => u === su && v === 0);
  wallLights(c, Y + 4);
  L.set(su, 0, Y - 1, T.chiseledBricks);
  L.set(su, 0, Y, trialSpawner(true));
  out.spawners.push({
    x: L.x(su, 0), y: Y, z: L.z(su, 0), kind: "guardian", family: room.mobs, room: room.id, bonus: c.tier - 1,
    box: boxOf(L, s.u0, s.v0, Y, s.u1 - 3, s.v1, Y + s.h - 1),
  });
}

// A long room over a pit of water: wooden slabs hanging from chains lead to a chest on the far side.
function buildParkour(c) {
  const { L, s, Y, rng, th } = c;
  const pitY = Y + s.bottom + 2; // the water
  shell(c);
  L.fill(s.u0, s.v0, pitY - 1, s.u1, s.v1, pitY - 1, T.clay);
  L.fill(s.u0 + 1, s.v0, pitY, s.u1 - 1, s.v1, pitY, T.water);
  wallOverlay(c, pitY, Y + s.h - 1, 0.4, lusher(th, 0.3));
  ceilOverlay(c, 0.5);
  // the ledge at the door
  L.fill(s.u0, s.v0, pitY, s.u0, s.v1, Y - 2, T.bricks);
  for (let v = s.v0; v <= s.v1; v++) L.set(s.u0, v, Y - 1, rng.chance(0.7) ? T.polished : floorVariant(rng, th));
  // vines on the pit side of the first ledge, to climb back after a fall
  for (let v = s.v0; v <= s.v1; v += 2) L.fill(s.u0 + 1, v, pitY + 1, s.u0 + 1, v, Y - 1, vine(L.dir("u-")));
  // platforms every two blocks: the slab you land on and the slab holding the chain
  const wood = rng.pick(th.wood);
  const lanes = [];
  for (let v = s.v0 + 1; v <= s.v1 - 1; v++) lanes.push(v);
  let v = rng.pick(lanes), h = 0, lastU = s.u0, lastY = Y - 1;
  for (let u = s.u0 + 2; u <= s.u1 - 1; u += 2) {
    const hold = v <= 0 ? v - 1 : v + 1;
    const y = Y - 1 + h;                // top slab at y: you stand at y + 1
    L.set(u, v, y, woodSlab(wood, true));
    L.set(u, hold, y, woodSlab(wood, true));
    L.fill(u, hold, y + 1, u, hold, Y + s.h - 1, T.chain);
    L.set(u, hold, Y + s.h, T.chiseled);
    lastU = u;
    lastY = y;
    // next: another lane, at most two to the side, or one to the side and one block higher
    const nv = rng.pick(lanes.filter((x) => x !== v && Math.abs(x - v) <= 2));
    if (h < 2 && Math.abs(nv - v) === 1 && rng.chance(0.4)) h++;
    v = nv;
  }
  // the raised ledge with the reward, one block over the last platform
  const lastH = lastY + (lastU === s.u1 - 1 ? 1 : 0); // a step up, or the same height across a gap
  L.fill(s.u1, s.v0, pitY, s.u1, s.v1, lastH, T.bricks);
  L.fill(s.u1, s.v0, lastH, s.u1, s.v1, lastH, T.polished);
  const back = L.dir("u-");
  L.chest(s.u1, 0, lastH + 1, chest(back), loot(rng, PARKOUR_LOOT, 4, 6));
  for (const vv of [s.v0, s.v1]) L.set(s.u1, vv, lastH + 1, rng.chance(0.5) ? T.flowering : T.azalea);
  L.set(s.u1, -1, lastH + 1, candle("green", rng.int(1, 3)));
  L.set(s.u1, 1, lastH + 1, T.lantern);
  // light and decoration: spore blossoms, glow berries along the walls, froglights
  for (let u = s.u0 + 1; u < s.u1; u += 5) L.set(u, 0, Y + s.h - 1, T.spore);
  for (let u = s.u0; u <= s.u1; u++)
    for (const vv of [s.v0, s.v1]) if (rng.chance(0.4)) hanging(L, u, vv, Y + s.h - 1, 3, rng, lusher(th, 0.5));
  for (let u = s.u0 + 3; u <= s.u1 - 2; u += 8) L.set(u, (u & 8) ? s.v0 - 1 : s.v1 + 1, Y + 3, froglight(th));
  L.set(s.u1 + 1, 0, Y + 4, froglight(th));
}

// A giant azalea-like tree: 2x2 (or 1x1) oak trunk, root flares, branches, a canopy of azalea
// leaves and glow berries hanging under it. (cu, cv) is the north-west log of the trunk.
function bigTree(L, cu, cv, yb, H, r, rng, opts = {}) {
  const t2 = opts.thin ? 0 : 1;
  const mu = cu + t2 / 2, mv = cv + t2 / 2, cy = yb + H + 1;
  const ry = Math.max(2, Math.round(r * 0.65));
  const bottom = new Map();
  for (let du = -r - 1; du <= r + 1; du++)
    for (let dv = -r - 1; dv <= r + 1; dv++)
      for (let dy = -ry; dy <= ry; dy++) {
        const u = Math.round(mu + du), v = Math.round(mv + dv), y = cy + dy;
        const d = ((u - mu) / r) ** 2 + ((v - mv) / r) ** 2 + (dy / ry) ** 2;
        if (d > 1 - rng.next() * 0.28 * (d > 0.55)) continue;
        if (opts.maxY !== undefined && y > opts.maxY) continue;
        L.set(u, v, y, rng.chance(0.3) ? T.leavesFlower : T.leaves);
        const k = `${u},${v}`;
        if (!bottom.has(k) || bottom.get(k) > y) bottom.set(k, y);
      }
  // trunk, branches and root flares
  L.fill(cu, cv, yb, cu + t2, cv + t2, yb + H, T.log("y"));
  const by = yb + H - 2;
  const au = L.axis("u"), av = L.axis("v");
  for (const [du, dv] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
    const len = opts.thin ? 2 : rng.int(2, 3);
    for (let k = 1; k <= len; k++) {
      const u = du < 0 ? cu - k : du > 0 ? cu + t2 + k : cu + (k & 1 ? 0 : t2);
      const v = dv < 0 ? cv - k : dv > 0 ? cv + t2 + k : cv + (k & 1 ? t2 : 0);
      L.set(u, v, by - (du + dv > 0 ? 1 : 0) + Math.floor(k / 2), T.log(du ? au : av));
    }
    if (!opts.thin) {
      const u = du < 0 ? cu - 1 : du > 0 ? cu + t2 + 1 : cu + rng.int(0, t2);
      const v = dv < 0 ? cv - 1 : dv > 0 ? cv + t2 + 1 : cv + rng.int(0, t2);
      L.set(u, v, yb, T.log(du ? au : av));
      L.set(u, v, yb + 1, T.mangroveRoots);
      L.set(u, v, yb - 1, T.rooted);
    }
  }
  // glow berries hanging under the canopy
  for (const [k, y] of bottom) {
    const [u, v] = k.split(",").map(Number);
    if (u >= cu && u <= cu + t2 && v >= cv && v <= cv + t2) continue;
    if (!rng.chance(opts.vines ?? 0.3)) continue;
    const len = Math.min(rng.int(1, 4), y - 1 - (yb + 2));
    if (len > 0) caveVines(L, u, v, y - 1, len, rng, 0.9);
  }
}

// The great hall with a tree inside.
function buildArbol(c) {
  const { L, s, Y, rng, th } = c;
  shell(c);
  L.fill(s.u0, s.v0, Y - 2, s.u1, s.v1, Y - 2, T.clay);
  wallOverlay(c, Y, Y + s.h - 1, 0.45, lusher(th, 0.4));
  ceilOverlay(c, 0.6, lusher(th, 0.5));
  // moss and rooted dirt, grass, ferns, bushes and small ponds in the corners
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) {
      const near = Math.abs(u - 0.5) <= 3 && Math.abs(v - 0.5) <= 3;
      L.set(u, v, Y - 1, near && rng.chance(0.6) ? T.rooted : th.pale > 0.5 && rng.chance(0.3) ? T.paleMoss : T.moss);
      if (inLane(c, u, v) || near) continue;
      const r = rng.next();
      if (r < 0.18) L.set(u, v, Y, rng.chance(0.35) ? T.fern : T.grass);
      else if (r < 0.3) L.set(u, v, Y, T.mossCarpet);
      else if (r < 0.34 && !onCross(u, v)) L.set(u, v, Y, rng.chance(0.5) ? T.flowering : T.azalea);
      else if (r < 0.38 && isBorder(s, u, v) && !onCross(u, v)) {
        L.set(u, v, Y, T.leaves);
        if (rng.chance(0.5)) L.set(u, v, Y + 1, T.leavesFlower);
      }
    }
  for (const [u, v] of [[s.u0 + 2, s.v0 + 2], [s.u1 - 3, s.v1 - 3], [s.u0 + 2, s.v1 - 3], [s.u1 - 3, s.v0 + 2]]) {
    if (!rng.chance(0.6)) continue;
    L.fill(u, v, Y, u + 1, v + 1, Y + 1, AIR);
    L.fill(u, v, Y - 1, u + 1, v + 1, Y - 1, T.water);
    L.set(u - 1, v, Y, T.dripleaf(L.dir("u-")));
    L.set(u + 2, v + 1, Y, T.dripleaf(L.dir("u+")));
  }
  // the tree, an offering chest at its feet and spore blossoms on the ceiling
  const r = Math.min(6, Math.floor(Math.min(s.L, s.W) / 2) - 2);
  bigTree(L, 0, 0, Y, s.h - 7, r, rng, { vines: 0.35, maxY: Y + s.h - 1 });
  L.chest(-2, 0, Y, chest(L.dir("u-")), loot(rng, TREE_LOOT, 4, 6));
  L.set(-2, 1, Y, candle("lime", rng.int(1, 4)));
  for (let i = 0; i < 6; i++) {
    const u = rng.pick([rng.int(s.u0, s.u0 + 3), rng.int(s.u1 - 3, s.u1)]), v = rng.int(s.v0, s.v1);
    L.set(u, v, Y + s.h - 1, T.spore);
  }
  ceilingLife(c, 5, 4, (u, v) => Math.abs(u - 0.5) <= r + 1 && Math.abs(v - 0.5) <= r + 1);
  wallLights(c, Y + 6);
}

function boxOf(L, u1, v1, y1, u2, v2, y2) {
  const xa = L.x(u1, v1), xb = L.x(u2, v2), za = L.z(u1, v1), zb = L.z(u2, v2);
  return [Math.min(xa, xb), y1, Math.min(za, zb), Math.max(xa, xb), y2, Math.max(za, zb)];
}

const BUILDERS = {
  vestibulo: buildVestibulo, spawner: buildSpawner, jardin: buildJardin, tesoro: buildTesoro, parkour: buildParkour,
  arbol: buildArbol, torre: buildTorre,
};
const NS = "mazmorra";

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
    if (rng.chance(0.4)) caveVines(L, t, rng.pick([-1, 1]), b + 3, 1, rng);
    else if (rng.chance(0.3)) L.set(t, 0, b + 3, T.lichenUp);
    return;
  }
  for (let l = -1; l <= 1; l++) {
    const cp = carpetFor(floor[l + 1]);
    if (cp && rng.chance(0.5)) L.set(t, l, b + 1, cp);
  }
  if (opts.rib) {
    // a beam of slabs across the ceiling
    L.fill(t, -1, b + 3, t, 1, b + 3, slab("tuff_brick_slab", true));
    L.fill(t, -2, b + 1, t, -2, b + 3, T.polished);
    L.fill(t, 2, b + 1, t, 2, b + 3, T.polished);
    return;
  }
  if (rng.chance(0.45 + 0.3 * th.lush)) hanging(L, t, rng.pick([-1, 1]), b + 3, 1, rng, th);
}

// Door through a room wall at distance t: 3x3 opening with a frame.
function door(L, t, Y) {
  L.fill(t, -1, Y, t, 1, Y + 2, AIR);
  L.fill(t, -1, Y - 1, t, 1, Y - 1, T.polished);
  for (const side of [-2, 2]) L.fill(t, side, Y, t, side, Y + 2, T.chiseledBricks);
  L.fill(t, -2, Y + 3, t, 2, Y + 3, T.polished);
}

// The corridor (flat or with stairs) from room a to its child room c.
function corridor(bld, a, c, th, rng) {
  const abyss = isAbyss(th);
  const d = c.dirIn;
  const L = bld.frame(a.x, a.z, d);
  const t0 = wallDist(a, d), t1 = Math.abs((c.x - a.x) * DIRS[d][0] + (c.z - a.z) * DIRS[d][1]) - wallDist(c, OPP[d]);
  const n = t1 - t0 - 1;
  const k0 = Math.floor((n - 10) / 2);
  for (let i = 0; i < n; i++) {
    const t = t0 + 1 + i;
    let b, asc;
    if (a.Y === c.Y) b = a.Y - 1;
    else {
      const down = c.Y < a.Y;
      const hi = down ? a.Y : c.Y, lo = down ? c.Y : a.Y;
      const j = (down ? i : n - 1 - i) - k0;
      if (j < 0) b = hi - 1;
      else if (j < 10) {
        b = hi - 1 - j;
        asc = down ? OPP[d] : d;
      } else b = lo - 1;
    }
    if (abyss) {
      acol(L, t, b, rng, { asc, hang: asc === undefined && i % 4 === 2, barrier: a.Y === c.Y && i === Math.floor(n / 2) });
      continue;
    }
    const light = i % 10 === 4 ? (i % 20 === 4 ? -2 : 2) : undefined;
    column(L, t, b, th, rng, { asc, light, rib: asc === undefined && i % 5 === 0 && i > 0 && i < n - 1 });
  }
  if (abyss) {
    adoor(L, t0, a.Y);
    adoor(L, t1, c.Y);
    return;
  }
  // a barrier of copper grates in the middle of every corridor without stairs (it can be mined)
  if (a.Y === c.Y) L.fill(t0 + 1 + Math.floor(n / 2), -1, a.Y, t0 + 1 + Math.floor(n / 2), 1, a.Y + 2, BARRIER);
  door(L, t0, a.Y);
  door(L, t1, c.Y);
}

// ------------------------------------------------------------ entrance
// A small obelisk: chiseled base, polished shaft, lantern on top, berries hanging from it.
function obelisk(L, t, v, ys, hgt, rng) {
  L.set(t, v, ys, T.chiseledBricks);
  L.fill(t, v, ys + 1, t, v, ys + hgt - 2, T.polished);
  L.set(t, v, ys + hgt - 1, T.chiseled);
  L.set(t, v, ys + hgt, T.lantern);
  if (rng.chance(0.7)) L.set(t, v, ys + rng.int(1, hgt - 2), T.moss);
}
// Paved ground at the surface, with foundation under it and air over it.
function pave(L, t1, v1, t2, v2, ys, rng, th, airTo = 12) {
  L.fill(t1, v1, ys, t2, v2, ys + airTo, AIR);
  L.fill(t1, v1, ys - 4, t2, v2, ys - 1, T.tuff);
  for (let t = Math.min(t1, t2); t <= Math.max(t1, t2); t++)
    for (let v = Math.min(v1, v2); v <= Math.max(v1, v2); v++) {
      const path = Math.abs(v) <= 1;
      const b = path ? (t & 1 ? T.chiseledBricks : T.polished) : rng.chance(0.3 * th.lush + 0.1) ? T.moss : rng.chance(0.5) ? T.bricks : T.polished;
      L.set(t, v, ys - 1, b);
      if (b === T.moss && rng.chance(0.5)) L.set(t, v, ys, T.mossCarpet);
    }
}

// The entrance: a roofed porch over a staircase down to the hall. The higher the tier,
// the grander: a paved forecourt with obelisks, a temple with a spire and trees, and
// finally a sanctuary with a great gate, pools and a crown of light.
function entrance(bld, origin, facing, y0, hallBack, tier, th, rng) {
  const L = bld.frame(origin.x, origin.z, facing);
  const ys = origin.y;            // the air block the player stands in
  const T0 = -3, T1 = 6, W = 4;   // the porch spans t in [T0, T1], v in [-W, W]
  // the ground in front: bigger with each tier
  const front = [0, -4, -12, -12, -18][tier], side = [0, 5, 7, 12, 13][tier];
  if (tier >= 2) pave(L, front, -side, T0 - 1, side, ys, rng, th, tier >= 3 ? 16 : 10);
  if (tier >= 3) pave(L, T0, -side, T1 + 2, side, ys, rng, th, 16);
  L.fill(T0 - 1, -W - 1, ys, T1 + 1, W + 1, ys + 9, AIR);
  L.fill(T0, -W, ys - 4, T1, W, ys - 1, T.tuff);
  // the staircase: 16 steps, the first 4 open under the roof
  for (let t = 1; t <= ENTRY_STEPS; t++) {
    const j = t - 1;
    if (j < 16) {
      const b = ys - 1 - j;
      const opts = { asc: OPP[facing], light: t === 9 ? 2 : undefined };
      if (b + 4 > ys - 1) Object.assign(opts, { open: ys + 5, wallTo: ys - 1, light: undefined });
      column(L, t, b, th, rng, opts);
    } else column(L, t, y0 - 1, th, rng);
  }
  door(L, hallBack, y0);
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
  const ph = tier >= 3 ? 5 : 3;    // a taller porch for the temple
  for (const t of [T0, T1])
    for (const v of [-W, W]) {
      L.set(t, v, ys, T.chiseledBricks);
      L.fill(t, v, ys + 1, t, v, ys + ph, T.polished);
      L.set(t, v, ys + ph + 1, T.chiseled);
    }
  const R = ys + ph + 2;           // the beams; the roof starts over them
  if (tier >= 3) {
    // a colonnade along the sides
    for (const t of [0, 3]) for (const v of [-W, W]) {
      L.set(t, v, ys, T.chiseledBricks);
      L.fill(t, v, ys + 1, t, v, ys + ph, T.polishedWall);
      L.set(t, v, ys + ph + 1, T.chiseledBricks);
    }
  }
  for (const v of [-2, 2]) L.fill(T1, v, ys + 1, T1, v, ys + ph, T.polishedWall);
  L.fill(T0, -W, R, T1, -W, R, T.bricks);
  L.fill(T0, W, R, T1, W, R, T.bricks);
  L.fill(T0, -W, R, T0, W, R, T.bricks);
  L.fill(T1, -W, R, T1, W, R, T.bricks);
  L.set(T0, 0, R, T.chiseledBricks);
  const arch = slab("tuff_brick_slab", true);
  for (const v of [-W + 1, W - 1]) {
    L.set(T0, v, R - 1, arch);
    L.set(T1, v, R - 1, arch);
  }
  for (const t of [T0 + 1, T1 - 1]) {
    L.set(t, -W, R - 1, arch);
    L.set(t, W, R - 1, arch);
  }
  L.fill(T0 - 1, -W - 1, R + 1, T1 + 1, W + 1, R + 1, slab("tuff_brick_slab", false));
  L.fill(T0, -W, R + 1, T1, W, R + 1, T.bricks);
  L.fill(T0 + 1, -W + 1, R + 2, T1 - 1, W - 1, R + 2, slab("polished_tuff_slab", false));
  L.fill(T0 + 2, -W + 2, R + 2, T1 - 2, W - 2, R + 2, T.polished);
  L.fill(T0 + 3, -1, R + 3, T1 - 3, 1, R + 3, slab("tuff_brick_slab", false));
  let topY = R + 3;
  if (tier >= 3) {
    // the spire
    L.fill(T0 + 3, -1, R + 3, T1 - 3, 1, R + 3, T.polished);
    L.fill(1, 0, R + 4, 2, 0, R + 6, T.chiseledBricks);
    L.set(1, 0, R + 7, T.chiseled);
    L.set(2, 0, R + 7, T.chiseled);
    topY = R + 7;
    for (const t of [T0, T1]) for (const v of [-W, W]) {
      L.set(t, v, R + 2, T.brickWall);
      L.set(t, v, R + 3, T.lantern);
    }
  }
  L.set(1, 0, topY, tier >= 4 ? froglight(th) : T.chiseled);
  L.set(1, 0, topY + 1, T.lantern);
  // moss and azalea growing over the roof, glow berries hanging from the eaves
  for (let t = T0 - 1; t <= T1 + 1; t++)
    for (let v = -W - 1; v <= W + 1; v++) {
      const ring = t === T0 - 1 || t === T1 + 1 || Math.abs(v) === W + 1;
      const inner = t >= T0 + 1 && t <= T1 - 1 && Math.abs(v) <= W - 1;
      if (ring) {
        if (rng.chance(0.35 * th.lush + 0.15 + 0.08 * tier)) caveVines(L, t, v, R, rng.int(1, 2 + tier), rng, 0.9);
      } else if (!inner && rng.chance(0.35 * th.lush + 0.1)) L.set(t, v, R + 2, rng.chance(0.3) ? T.leavesFlower : T.mossCarpet);
    }
  if (tier < 3)
    for (const [t, v] of [[T0, -W], [T0, W], [T1, -W], [T1, W]]) {
      L.set(t, v, R + 2, T.leavesFlower);
      if (rng.chance(0.6)) L.set(t, v, R + 3, T.leaves);
    }
  // lanterns over the staircase, plants on the porch
  for (const t of [2, 4]) {
    L.fill(t, 0, ys + 4, t, 0, R, T.chain);
    L.set(t, 0, ys + 3, T.lanternHang);
  }
  for (const v of [-3, 3]) {
    L.set(-2, v, ys - 1, T.moss);
    L.set(-2, v, ys, T.flowering);
    L.set(T1 - 1, v, ys - 1, T.moss);
    L.set(T1 - 1, v, ys, T.dripleaf(L.dir(v < 0 ? "v+" : "v-")));
    L.set(0, v, ys, T.lantern);
    L.set(-1, v, ys, slab("polished_tuff_slab", false));
  }

  if (tier >= 2) {
    // forecourt: low walls, obelisks and azalea planters
    for (let t = front; t <= T0 - 1; t++)
      for (const v of [-side, side]) if ((t - front) % 4 !== 2) L.set(t, v, ys, T.brickWall);
    for (let v = -side; v <= side; v++) if (Math.abs(v) > 2) L.set(front, v, ys, T.brickWall);
    for (let t = front + 2; t <= T0 - 2; t += 4) for (const v of [-4, 4]) obelisk(L, t, v, ys, tier >= 3 ? 6 : 4, rng);
    for (let t = front + 4; t <= T0 - 2; t += 4) for (const v of [-side + 2, side - 2]) {
      if (Math.abs(v) === 4) continue;
      L.set(t, v, ys - 1, T.moss);
      L.set(t, v, ys, rng.chance(0.5) ? T.flowering : T.azalea);
    }
  }
  if (tier >= 3)
    // two trees beside the porch, glow berries everywhere
    for (const v of [-9, 9]) {
      L.fill(1, v - 1, ys - 1, 2, v + 1, ys - 1, T.rooted);
      bigTree(L, 1, v, ys, tier >= 4 ? 7 : 5, tier >= 4 ? 4 : 3, rng, { thin: tier < 4, vines: 0.4 });
    }
  if (tier >= 4) {
    // the great gate: two tall pillars, a lintel and a curtain of glow berries
    const g = front + 1, gh = 9;
    for (const v of [-3, 3]) {
      L.fill(g, v, ys, g, v, ys + gh - 1, T.chiseledBricks);
      L.fill(g, v, ys + 2, g, v, ys + gh - 3, T.polished);
      L.set(g, v, ys + gh - 2, froglight(th));
    }
    L.fill(g, -4, ys + gh, g, 4, ys + gh, T.chiseledBricks);
    L.fill(g, -3, ys + gh + 1, g, 3, ys + gh + 1, slab("tuff_brick_slab", false));
    L.set(g, 0, ys + gh + 1, T.chiseled);
    L.set(g, 0, ys + gh + 2, T.lantern);
    for (const v of [-2, 2]) {
      L.set(g, v, ys + gh - 1, stairs("tuff_brick_stairs", L.dir(v < 0 ? "v-" : "v+"), true));
    }
    for (let v = -2; v <= 2; v++) if (v !== 0) caveVines(L, g, v, ys + gh - 1 - (Math.abs(v) === 2 ? 1 : 0), rng.int(2, 4), rng, 0.95);
    // pools on both sides of the path, with dripleaves
    for (const v0 of [3, -7]) {
      L.fill(front + 4, v0, ys - 1, front + 9, v0 + 4, ys - 1, T.polished);
      L.fill(front + 5, v0 + 1, ys - 2, front + 8, v0 + 3, ys - 2, T.clay);
      L.fill(front + 5, v0 + 1, ys - 1, front + 8, v0 + 3, ys - 1, T.water);
      L.fill(front + 5, v0 + 1, ys, front + 8, v0 + 3, ys, AIR);
      L.set(front + 5, v0 + 2, ys - 1, T.clay);
      L.set(front + 5, v0 + 2, ys, T.dripleaf(L.dir("u+")));
      L.set(front + 8, v0 + 2, ys - 1, T.clay);
      L.set(front + 8, v0 + 2, ys, T.dripleaf(L.dir("u-")));
    }
    // a crown of froglights around the spire
    for (const [t, v] of [[0, -1], [0, 1], [3, -1], [3, 1]]) L.set(t, v, R + 4, froglight(th));
  }
}

// ------------------------------------------------------------ the abyss
// Deepslate caves of 20x20 to 32x32: uneven floors made of slabs, stairs on the walls and
// ceilings, stalagmites and stalactites tapered with stairs and slabs, chasms crossed by copper
// grate bridges hanging from chains, lava parkour and almost no light.
const A = {
  deep: mc("deepslate"), cobbled: mc("cobbled_deepslate"), polished: mc("polished_deepslate"),
  bricks: mc("deepslate_bricks"), cracked: mc("cracked_deepslate_bricks"), tiles: mc("deepslate_tiles"),
  crackedTiles: mc("cracked_deepslate_tiles"), chiseled: mc("chiseled_deepslate"), basalt: mc("smooth_basalt"),
  tuff: mc("tuff"), crying: mc("crying_obsidian"), obsidian: mc("obsidian"), lava: mc("lava"),
  grate: mc("waxed_weathered_copper_grate"),
  brickWall: mc("deepslate_brick_wall"), tileWall: mc("deepslate_tile_wall"), cobbledWall: mc("cobbled_deepslate_wall"),
  soulLantern: st("soul_lantern", { hanging: false }), soulHang: st("soul_lantern", { hanging: true }),
  lichen: st("glow_lichen", { multi_face_direction_bits: 2 }),
};
const ASLABS = ["cobbled_deepslate_slab", "polished_deepslate_slab", "deepslate_brick_slab", "deepslate_tile_slab"];
const ASTAIRS = ["cobbled_deepslate_stairs", "polished_deepslate_stairs", "deepslate_brick_stairs", "deepslate_tile_stairs"];
const aWall = (rng) => rng.weighted([[A.deep, 5], [A.cobbled, 3], [A.tiles, 1], [A.bricks, 0.8], [A.cracked, 0.6],
  [A.crackedTiles, 0.6], [A.basalt, 1.2], [A.tuff, 0.5]]);
const aFloor = (rng) => rng.weighted([[A.cobbled, 4], [A.deep, 3], [A.tiles, 1], [A.crackedTiles, 0.8], [A.basalt, 1],
  [A.polished, 0.6]]);
const aTip = (rng) => rng.pick([A.brickWall, A.tileWall, A.cobbledWall]);
const aSlab = (rng, top) => slab(rng.pick(ASLABS), top);
const aStair = (rng, asc, up) => stairs(rng.pick(ASTAIRS), asc, up);
const ldir = (du, dv) => (du > 0 ? "u+" : du < 0 ? "u-" : dv > 0 ? "v+" : "v-");
const N4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];

// Smooth value noise in 0..1.
function noise2(seed, x, z) {
  const x0 = Math.floor(x), z0 = Math.floor(z);
  const fx = x - x0, fz = z - z0;
  const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
  const a = hash(seed, x0, z0) / 4294967296, b = hash(seed, x0 + 1, z0) / 4294967296;
  const c = hash(seed, x0, z0 + 1) / 4294967296, d = hash(seed, x0 + 1, z0 + 1) / 4294967296;
  return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
}

// The shape of a cave room: for every column, whether it is open, the height of its floor
// in half blocks over Y (odd = a slab on top) and the last block of air under its ceiling.
// Lanes (5 wide, from each door to the centre) and the core stay flat at Y.
function caveLayout(c, o = {}) {
  const { s, Y, rng } = c;
  const seed = rng.int(1, 1 << 30);
  const cu = (s.u0 + s.u1) / 2, cv = (s.v0 + s.v1) / 2, ru = s.L / 2, rv = s.W / 2;
  const ex = o.square ?? 2.6, core = o.core ?? 3;
  const lane = (u, v) => [...c.doors].some((d) =>
    (d === "u-" && u <= 0 && Math.abs(v) <= 2) || (d === "u+" && u >= 0 && Math.abs(v) <= 2) ||
    (d === "v-" && v <= 0 && Math.abs(u) <= 2) || (d === "v+" && v >= 0 && Math.abs(u) <= 2));
  const cells = new Map();
  for (let u = s.u0; u <= s.u1; u++)
    for (let v = s.v0; v <= s.v1; v++) {
      const d = Math.abs((u - cu) / ru) ** ex + Math.abs((v - cv) / rv) ** ex + (noise2(seed, u / 6, v / 6) - 0.5) * 0.55;
      const ln = lane(u, v);
      const flat = ln || (Math.abs(u) <= core && Math.abs(v) <= core) || !!o.flat?.(u, v);
      const cave = flat || d < 0.9;
      const fh = flat ? 0 : Math.max(0, Math.round((d - 0.3) * 7 + (noise2(seed + 7, u / 4, v / 4) - 0.5) * 3));
      const roof = 0.55 + 0.45 * Math.sqrt(Math.max(0, 1 - Math.min(1, d)));
      const ch = Math.min(Y + s.h - 1, Y + Math.round((s.h - 1) * roof + (noise2(seed + 13, u / 5, v / 5) - 0.5) * 3));
      cells.set(`${u},${v}`, { u, v, cave, fh, ch, lane: ln, flat, d });
    }
  // neighbouring floors differ by half a block at most: every step is a slab
  for (let pass = 0; pass < 10; pass++)
    for (const cl of cells.values()) {
      if (!cl.cave) continue;
      for (const [du, dv] of N4) {
        const nb = cells.get(`${cl.u + du},${cl.v + dv}`);
        if (nb?.cave && cl.fh > nb.fh + 1) cl.fh = nb.fh + 1;
      }
    }
  for (const cl of cells.values()) {
    cl.air = Y + Math.ceil(cl.fh / 2);
    cl.ch = Math.min(Y + s.h - 1, Math.max(cl.ch, cl.air + (cl.lane || cl.flat ? 4 : 3)));
  }
  return cells;
}

// Writes the cave: solid box, then every open column; pit(cell) can send a column down to
// the bottom of the room, with lava over it when o.lava is set.
function caveBuild(c, cells, o = {}) {
  const { L, s, Y, rng } = c;
  L.fill(s.u0 - 1, s.v0 - 1, Y + s.bottom, s.u1 + 1, s.v1 + 1, Y + s.h, A.deep);
  for (const cl of cells.values()) {
    if (!cl.cave) continue;
    const { u, v, fh, ch } = cl;
    if (o.pit?.(cl)) {
      cl.pit = true;
      const fy = Y + s.bottom + 1;
      L.set(u, v, fy, aFloor(rng));
      L.fill(u, v, fy + 1, u, v, ch, AIR);
      if (o.lava) L.set(u, v, fy + 1, A.lava);
      cl.air = fy + (o.lava ? 2 : 1);
    } else {
      L.fill(u, v, cl.air, u, v, ch, AIR);
      L.set(u, v, Y - 1 + Math.floor(fh / 2), aFloor(rng));
      if (fh & 1) L.set(u, v, Y + Math.floor(fh / 2), aSlab(rng, false));
    }
    if (rng.chance(0.45)) L.set(u, v, ch + 1, aWall(rng));
  }
}

// Relief on the walls: stairs at the foot of the walls, upside-down stairs under the ceiling,
// slabs sticking out, cracked and polished blocks; a few specks of crying obsidian.
function caveRelief(c, cells) {
  const { L, rng } = c;
  for (const cl of cells.values()) {
    if (!cl.cave) continue;
    for (const [du, dv] of N4) {
      const nb = cells.get(`${cl.u + du},${cl.v + dv}`);
      if (nb?.cave) continue;
      const toward = L.dir(ldir(du, dv));
      for (let y = cl.air; y <= cl.ch; y++) if (rng.chance(0.3)) L.set(cl.u + du, cl.v + dv, y, aWall(rng));
      if (rng.chance(0.006)) L.set(cl.u + du, cl.v + dv, rng.int(cl.air, cl.ch), A.crying);
      if (cl.lane || cl.pit) continue;
      if (rng.chance(0.35)) L.set(cl.u, cl.v, cl.air, aStair(rng, toward, false));
      else if (rng.chance(0.15)) L.set(cl.u, cl.v, cl.air, aSlab(rng, false));
      if (cl.ch - cl.air >= 4 && rng.chance(0.4)) L.set(cl.u, cl.v, cl.ch, aStair(rng, toward, true));
      else if (cl.ch - cl.air >= 4 && rng.chance(0.2)) L.set(cl.u, cl.v, cl.ch, aSlab(rng, true));
    }
  }
}

// A stalagmite (up) or a stalactite (down) of H blocks starting at y0, tapered with stairs
// and slabs. cells (optional) tells where the flanks fit.
function spike(L, cells, u, v, y0, H, up, rng, big = false) {
  const dy = up ? 1 : -1;
  const fits = (uu, vv, y) => {
    if (!cells) return true;
    const cl = cells.get(`${uu},${vv}`);
    return !!cl && cl.cave && !cl.lane && !cl.walk && y >= cl.air && y <= cl.ch;
  };
  for (let k = 0; k < H; k++) {
    const y = y0 + dy * k;
    const last = k === H - 1;
    L.set(u, v, y, last ? (rng.chance(0.55) ? aTip(rng) : aSlab(rng, !up)) : k < H / 2 ? aWall(rng) : rng.chance(0.5) ? A.polished : A.tiles);
    const flank = big ? k <= 2 : k === 0 || (k === 1 && H >= 6);
    if (flank && !last)
      for (const [du, dv] of N4) {
        if (!fits(u + du, v + dv, y)) continue;
        const asc = L.dir(ldir(-du, -dv));
        if (big && k === 0) L.set(u + du, v + dv, y, aWall(rng));
        else if (rng.chance(0.85)) L.set(u + du, v + dv, y, aStair(rng, asc, !up));
      }
    if (big && k === 0)
      for (const du of [-1, 1]) for (const dv of [-1, 1])
        if (fits(u + du, v + dv, y)) L.set(u + du, v + dv, y, rng.chance(0.6) ? aStair(rng, L.dir(ldir(-du, 0)), !up) : aSlab(rng, !up));
    if (!flank && !last && k === Math.floor(H / 2) && H >= 4)
      for (const [du, dv] of rng.shuffle(N4).slice(0, 2)) if (fits(u + du, v + dv, y)) L.set(u + du, v + dv, y, aSlab(rng, !up));
  }
}

// Stalagmites and stalactites around the room, away from the ways.
function caveSpikes(c, cells, o = {}) {
  const { L, s, rng } = c;
  const area = s.L * s.W;
  const free = (cl) => cl.cave && !cl.lane && !cl.walk && !cl.flat &&
    N4.every(([du, dv]) => { const nb = cells.get(`${cl.u + du},${cl.v + dv}`); return nb?.cave && !nb.lane && !nb.walk; });
  const list = [...cells.values()].filter(free);
  for (let i = 0; i < area / (o.upEvery ?? 40) && list.length; i++) {
    const cl = rng.pick(list);
    if (!(cl.fh % 2 === 0 || cl.pit)) continue;
    const room = cl.ch - cl.air;
    if (room < 4) continue;
    const H = rng.int(2, Math.min(o.upMax ?? 7, room - 2));
    spike(L, cells, cl.u, cl.v, cl.air, H, true, rng, H >= 6 && rng.chance(0.5));
  }
  for (let i = 0; i < area / (o.downEvery ?? 30) && list.length; i++) {
    const cl = rng.pick(list);
    const room = cl.ch - cl.air;
    if (room < 6) continue;
    const H = rng.int(2, Math.min(o.downMax ?? 8, room - 3));
    spike(L, cells, cl.u, cl.v, cl.ch, H, false, rng, H >= 6 && rng.chance(0.5));
  }
}

// Almost no light: one soul lantern on a chain somewhere, and a few glow lichens.
function caveLights(c, cells, lanterns = 1) {
  const { L, rng } = c;
  const open = [...cells.values()].filter((cl) => cl.cave && cl.ch - cl.air >= 6);
  for (let i = 0; i < lanterns && open.length; i++) {
    const cl = rng.pick(open);
    const len = rng.int(1, 3);
    L.fill(cl.u, cl.v, cl.ch - len + 1, cl.u, cl.v, cl.ch, T.chain);
    L.set(cl.u, cl.v, cl.ch - len, A.soulHang);
  }
  for (let i = 0; i < 5 && open.length; i++) {
    const cl = rng.pick(open);
    L.set(cl.u, cl.v, cl.ch, A.lichen);
  }
}

function aVestibulo(c) {
  const { L, Y, rng } = c;
  const cells = caveLayout(c, { core: 4 });
  caveBuild(c, cells);
  caveRelief(c, cells);
  caveSpikes(c, cells);
  // a ring of tiles around an altar with the only lantern of the hall
  for (let u = -3; u <= 3; u++)
    for (let v = -3; v <= 3; v++) {
      const r = Math.max(Math.abs(u), Math.abs(v));
      L.set(u, v, Y - 1, r === 3 ? A.polished : r === 2 ? A.tiles : A.bricks);
    }
  L.set(0, 0, Y, A.chiseled);
  L.set(0, 0, Y + 1, A.soulLantern);
  for (const [du, dv] of N4) L.set(du, dv, Y, aStair(rng, L.dir(ldir(-du, -dv)), false));
  caveLights(c, cells, 1);
}

function aCaverna(c) {
  const { L, s, Y, rng, room, out } = c;
  const cells = caveLayout(c, { core: 3 });
  caveBuild(c, cells);
  caveRelief(c, cells);
  caveSpikes(c, cells);
  for (let u = -2; u <= 2; u++)
    for (let v = -2; v <= 2; v++) L.set(u, v, Y - 1, Math.max(Math.abs(u), Math.abs(v)) === 2 ? A.polished : A.tiles);
  L.set(0, 0, Y - 1, A.chiseled);
  caveLights(c, cells, rng.chance(0.3) ? 2 : 1);
  L.set(0, 0, Y, trialSpawner(false));
  out.spawners.push({
    x: L.x(0, 0), y: Y, z: L.z(0, 0), kind: "normal", family: room.mobs, room: room.id,
    bonus: Math.floor((s.L * s.W - 400) / 150) + 2 + c.tier - 1,
    box: boxOf(L, s.u0, s.v0, Y, s.u1, s.v1, Y + 2),
  });
}

// A chasm: copper grate bridges hanging from chains go from every door to a platform in the
// middle, where the spawner waits. Vines on the walls next to the doors to climb back up.
function aSima(c) {
  const { L, s, Y, rng, room, out } = c;
  const walk = (u, v) => (Math.abs(u) <= 2 && Math.abs(v) <= 2) || [...c.doors].some((d) =>
    (d === "u-" && u <= 0 && Math.abs(v) <= 1) || (d === "u+" && u >= 0 && Math.abs(v) <= 1) ||
    (d === "v-" && v <= 0 && Math.abs(u) <= 1) || (d === "v+" && v >= 0 && Math.abs(u) <= 1));
  const cells = caveLayout(c, { core: 3 });
  for (const cl of cells.values()) cl.walk = walk(cl.u, cl.v);
  caveBuild(c, cells, { pit: (cl) => true });
  caveRelief(c, cells);
  caveSpikes(c, cells, { upMax: 9, upEvery: 30 });
  // the bridges and the platform
  for (const cl of cells.values()) {
    if (!cl.walk) continue;
    const ring = Math.max(Math.abs(cl.u), Math.abs(cl.v)) === 2 && Math.abs(cl.u) <= 2 && Math.abs(cl.v) <= 2;
    L.set(cl.u, cl.v, Y - 1, ring ? A.bricks : A.grate);
  }
  const hanger = (u, v) => {
    const cl = cells.get(`${u},${v}`);
    if (!cl?.cave || cl.walk) return;
    L.set(u, v, Y - 1, slab("polished_deepslate_slab", true));
    L.fill(u, v, Y, u, v, cl.ch, T.chain);
  };
  for (const cl of cells.values()) {
    if (!cl.walk || (Math.abs(cl.u) <= 2 && Math.abs(cl.v) <= 2)) continue;
    const alongU = Math.abs(cl.v) <= 1 && Math.abs(cl.u) > 2;
    if (alongU && cl.v === 0 && cl.u % 4 === 0) { hanger(cl.u, -2); hanger(cl.u, 2); }
    if (!alongU && cl.u === 0 && cl.v % 4 === 0) { hanger(-2, cl.v); hanger(2, cl.v); }
  }
  for (const u of [-3, 3]) for (const v of [-3, 3]) hanger(u, v);
  // vines next to every door, from the bottom of the chasm up to the bridge
  const vines = { "u-": [[s.u0, -2], [s.u0, 2]], "u+": [[s.u1, -2], [s.u1, 2]], "v-": [[-2, s.v0], [2, s.v0]], "v+": [[-2, s.v1], [2, s.v1]] };
  for (const d of c.doors)
    for (const [u, v] of vines[d]) {
      const cl = cells.get(`${u},${v}`);
      if (cl?.pit) L.fill(u, v, cl.air, u, v, Y - 1, vine(L.dir(d)));
    }
  L.set(0, 0, Y - 1, A.chiseled);
  caveLights(c, cells, 2);
  L.set(0, 0, Y, trialSpawner(false));
  out.spawners.push({
    x: L.x(0, 0), y: Y, z: L.z(0, 0), kind: "normal", family: room.mobs, room: room.id,
    bonus: Math.floor((s.L * s.W - 400) / 150) + 1 + c.tier - 1,
    box: boxOf(L, s.u0, s.v0, Y, s.u1, s.v1, Y + 2),
  });
}

// Lava parkour: a long cave over a lake of lava, with hanging slabs, chiseled blocks on chains
// and stalagmite pillars rising from the lava; the reward on the far ledge.
function aParkour(c) {
  const { L, s, Y, rng, th } = c;
  const entry = (u) => u <= s.u0 + 1, exit = (u) => u >= s.u1 - 1;
  const cells = caveLayout(c, { square: 6, core: 0, flat: (u) => entry(u) || exit(u) });
  for (const cl of cells.values()) {
    cl.cave = true; // the whole box is open: room to jump
    cl.ch = Math.max(cl.ch, Y + s.h - 4);
  }
  caveBuild(c, cells, { pit: (cl) => !entry(cl.u) && !exit(cl.u), lava: true });
  caveRelief(c, cells);
  caveSpikes(c, cells, { upEvery: 1e9, downEvery: 22 });
  // the path: steps of 2 or 3 blocks, moving to the side, up and down
  const plats = [];
  let u = s.u0 + 1, v = 0, sh = 0;
  const vmin = s.v0 + 3, vmax = s.v1 - 3;
  while (s.u1 - 1 - u > 3) {
    const step = s.u1 - 1 - (u + 3) >= 2 && rng.chance(0.4) ? 3 : 2;
    const dv = step === 2 ? rng.int(-2, 2) : rng.int(-1, 1);
    const nv = Math.max(vmin, Math.min(vmax, v + dv));
    let nh = sh;
    if (step === 2 && Math.abs(nv - v) <= 1) nh = Math.max(-1, Math.min(2, sh + rng.pick([-1, 0, 0, 1])));
    u += step; v = nv; sh = nh;
    plats.push({ u, v, sh, kind: rng.weighted([["hang", 3], ["pillar", 1.5], ["block", 1]]) });
  }
  const tile = slab("deepslate_tile_slab", true);
  for (const p of plats) {
    const y = Y - 1 + p.sh; // the block you stand on
    const ceil = (uu, vv) => cells.get(`${uu},${vv}`)?.ch ?? Y + s.h - 1;
    if (p.kind === "pillar") {
      const base = Y + s.bottom + 2;
      spike(L, null, p.u, p.v, base, y - base + 1, true, rng, false);
      L.set(p.u, p.v, y, A.polished);
      continue;
    }
    const hold = p.v <= 0 ? p.v - 1 : p.v + 1;
    L.set(p.u, p.v, y, p.kind === "block" ? A.chiseled : tile);
    L.set(p.u, hold, y, tile);
    L.fill(p.u, hold, y + 1, p.u, hold, ceil(p.u, hold), T.chain);
  }
  // the ledge with the reward, at the height of the last platform
  const last = plats[plats.length - 1] ?? { sh: 0 };
  const ly = Y - 1 + last.sh;
  L.fill(s.u1 - 1, s.v0, Y + s.bottom + 1, s.u1, s.v1, ly, A.deep);
  for (let vv = s.v0; vv <= s.v1; vv++) L.set(s.u1 - 1, vv, ly, A.polished);
  L.fill(s.u1 - 1, s.v0, ly + 1, s.u1, s.v1, ly + 3, AIR);
  L.chest(s.u1, 0, ly + 1, chest(L.dir("u-")), loot(rng, PARKOUR_LOOT, 5, 7));
  for (const vv of [-2, 2]) L.set(s.u1, vv, ly + 1, A.soulLantern);
  L.set(s.u1, -1, ly + 1, A.chiseled);
  L.set(s.u1, 1, ly + 1, A.chiseled);
}

function aTesoro(c) {
  const { L, s, Y, rng, room, out } = c;
  const back = (u, v) => u >= s.u1 - 6 && Math.abs(v) <= 5;
  const cells = caveLayout(c, { core: 4, flat: back });
  caveBuild(c, cells);
  caveRelief(c, cells);
  caveSpikes(c, cells);
  // the dais: a flight of stairs, tiles, the chest between two vaults, crying obsidian behind
  const toBack = L.dir("u+"), face = L.dir("u-");
  L.fill(s.u1 - 3, -4, Y, s.u1 - 3, 4, Y, stairs("deepslate_tile_stairs", toBack));
  L.fill(s.u1 - 2, -4, Y, s.u1, 4, Y, A.tiles);
  L.fill(s.u1 - 2, -4, Y - 1, s.u1, 4, Y - 1, A.bricks);
  L.chest(s.u1, 0, Y + 1, chest(face), loot(rng, TREASURE_LOOT, 7, 9));
  L.set(s.u1, -2, Y + 1, vault(face, false));
  L.set(s.u1, 2, Y + 1, vault(face, true));
  for (const v of [-4, 4]) {
    L.set(s.u1, v, Y + 1, A.chiseled);
    L.set(s.u1, v, Y + 2, A.soulLantern);
  }
  for (let v = -3; v <= 3; v += 2) L.set(s.u1 + 1, v, Y + 2, A.crying);
  const su = Math.min(0, s.u1 - 9);
  L.set(su, 0, Y - 1, A.chiseled);
  L.set(su, 0, Y, trialSpawner(true));
  out.spawners.push({
    x: L.x(su, 0), y: Y, z: L.z(su, 0), kind: "guardian", family: room.mobs, room: room.id, bonus: 2 + c.tier - 1,
    box: boxOf(L, s.u0, s.v0, Y, s.u1 - 4, s.v1, Y + 2),
  });
}

const ABYSS_BUILDERS = { vestibulo: aVestibulo, spawner: aCaverna, sima: aSima, parkour: aParkour, tesoro: aTesoro };

// One column of an abyss corridor: a 5-wide tunnel; on the flat parts the floor is a copper
// grate bridge over a gap, held by chains every few blocks.
function acol(L, t, b, rng, o = {}) {
  if (o.open !== undefined) {
    L.fill(t, -3, b - 1, t, 3, o.wallTo, A.cobbled);
    L.fill(t, -2, b + 1, t, 2, o.open, AIR);
    L.fill(t, -2, b, t, 2, b, stairs("deepslate_brick_stairs", o.asc));
    return;
  }
  L.fill(t, -3, b - 3, t, 3, b + 4, A.deep);
  for (const side of [-3, 3]) for (let y = b - 2; y <= b + 3; y++) if (rng.chance(0.45)) L.set(t, side, y, aWall(rng));
  for (let l = -2; l <= 2; l++) if (rng.chance(0.4)) L.set(t, l, b + 4, aWall(rng));
  if (o.asc !== undefined || o.solid) {
    L.fill(t, -2, b + 1, t, 2, b + 3, AIR);
    if (o.asc !== undefined) L.fill(t, -2, b, t, 2, b, stairs("deepslate_brick_stairs", o.asc));
    else for (let l = -2; l <= 2; l++) L.set(t, l, b, aFloor(rng));
    if (rng.chance(0.04)) L.set(t, 0, b + 3, A.lichen);
    return;
  }
  L.fill(t, -2, b - 2, t, 2, b + 3, AIR);
  for (let l = -2; l <= 2; l++) if (rng.chance(0.5)) L.set(t, l, b - 3, aFloor(rng));
  L.fill(t, -1, b, t, 1, b, A.grate);
  if (o.hang)
    for (const side of [-2, 2]) {
      L.set(t, side, b, slab("polished_deepslate_slab", true));
      L.fill(t, side, b + 1, t, side, b + 3, T.chain);
    }
  else if (rng.chance(0.25)) {
    // a small stalactite at the side of the tunnel
    const side = rng.pick([-2, 2]);
    L.set(t, side, b + 3, rng.chance(0.5) ? aTip(rng) : aSlab(rng, true));
  }
  if (rng.chance(0.06)) L.set(t, rng.pick([-2, 2]), b + 3, A.lichen);
  if (o.barrier) L.fill(t, -2, b - 2, t, 2, b + 3, BARRIER);
}

function adoor(L, t, Y) {
  L.fill(t, -2, Y, t, 2, Y + 3, AIR);
  L.fill(t, -2, Y - 1, t, 2, Y - 1, A.polished);
  for (const side of [-3, 3]) L.fill(t, side, Y - 1, t, side, Y + 3, A.tiles);
  L.fill(t, -3, Y + 4, t, 3, Y + 4, A.bricks);
  L.set(t, 0, Y + 4, A.chiseled);
}

// The entrance of the abyss: a plaza of deepslate tiles with teeth of stone around it, a
// colossal gate of two pillars and a pointed arch over the staircase, and soul lanterns.
// Higher tiers: taller gate, bigger and more teeth.
function abyssEntrance(bld, origin, facing, y0, hallBack, tier, rng) {
  const L = bld.frame(origin.x, origin.z, facing);
  const ys = origin.y;
  const F = -18, B = 9, S = 15; // the plaza: t in [F, B], v in [-S, S]
  const PH = 15 + 2 * tier;     // the height of the pillars
  L.fill(F, -S, ys, B, S, ys + PH + 8, AIR);
  L.fill(F, -S, ys - 5, B, S, ys - 1, A.cobbled);
  for (let t = F; t <= B; t++)
    for (let v = -S; v <= S; v++) {
      const path = Math.abs(v) <= 2 && t <= 0;
      const edge = t === F || t === B || Math.abs(v) === S;
      L.set(t, v, ys - 1, path ? (t % 4 === 0 ? A.chiseled : A.bricks) : edge ? A.polished
        : rng.weighted([[A.tiles, 4], [A.crackedTiles, 2], [A.cobbled, 1.5], [A.deep, 1], [A.basalt, 1]]));
      if (!path && !edge && rng.chance(0.06)) L.set(t, v, ys, aSlab(rng, false));
    }
  // the staircase: 16 steps (5 wide), the first ones open under the arch
  for (let t = 1; t <= ENTRY_STEPS; t++) {
    const j = t - 1;
    if (j < 16) {
      const b = ys - 1 - j;
      if (b + 4 > ys - 1) acol(L, t, b, rng, { asc: OPP[facing], open: ys + 8, wallTo: ys - 1 });
      else acol(L, t, b, rng, { asc: OPP[facing] });
    } else acol(L, t, y0 - 1, rng, { solid: true });
  }
  adoor(L, hallBack, y0);
  // the rim of the hole
  for (let t = 1; t <= 5; t++) for (const v of [-3, 3]) L.set(t, v, ys, A.tileWall);
  L.fill(5, -3, ys, 5, 3, ys, A.tileWall);
  for (let t = 1; t <= 5; t++) for (const v of [-4, 4]) L.set(t, v, ys - 1, A.crackedTiles);
  // the gate: two pillars 3x3, bands of chiseled deepslate, flared bases and capitals
  for (const sv of [-1, 1]) {
    const v1 = 5 * sv, v2 = 7 * sv;
    L.fill(0, v1, ys, 2, v2, ys + PH - 1, A.bricks);
    for (const t of [0, 2]) for (const v of [v1, v2]) L.fill(t, v, ys, t, v, ys + PH - 1, A.tiles);
    for (let y = ys + 4; y < ys + PH - 2; y += 5) L.fill(0, v1, y, 2, v2, y, A.chiseled);
    const vm = 6 * sv;
    for (const [du, dv] of N4)
      for (let k = -1; k <= 1; k++) {
        const t = 1 + du * 2 + (dv ? k : 0), v = vm + dv * 2 + (du ? k : 0);
        L.set(t, v, ys, aStair(rng, L.dir(ldir(-du, -dv)), false));
        L.set(t, v, ys + PH - 1, aStair(rng, L.dir(ldir(-du, -dv)), true));
      }
    L.fill(-1, vm - 2, ys + PH, 3, vm + 2, ys + PH, slab("polished_deepslate_slab", false));
    L.fill(0, v1, ys + PH, 2, v2, ys + PH, A.polished);
    L.set(1, vm, ys + PH + 1, A.chiseled);
    L.set(1, vm, ys + PH + 2, A.soulLantern);
  }
  // the pointed arch between the pillars, with its keystone and a spire on top
  const rise = [0, 3, 5, 6, 7];
  for (let v = -4; v <= 4; v++) {
    const a = 4 - Math.abs(v), yu = ys + PH - 8 + rise[a];
    L.fill(0, v, yu, 2, v, ys + PH - 1, A.bricks);
    if (v) L.fill(0, v, yu, 2, v, yu, aStair(rng, L.dir(v > 0 ? "v+" : "v-"), true));
    else L.fill(0, 0, yu, 2, 0, yu, A.chiseled);
  }
  L.fill(0, -4, ys + PH, 2, 4, ys + PH, A.polished);
  spike(L, null, 1, 0, ys + PH + 1, 3 + tier, true, rng, false);
  for (const v of [-2, 2]) {
    const yu = ys + PH - 8 + rise[4 - Math.abs(v)];
    L.fill(1, v, yu - 3, 1, v, yu - 1, T.chain);
    L.set(1, v, yu - 4, A.soulHang);
  }
  // the teeth around the plaza, giants in the corners, a guarded path to the gate
  for (let t = F + 2; t <= B - 2; t += 4)
    for (const v of [-S + 1, S - 1]) spike(L, null, t, v, ys, rng.int(3, 4 + tier), true, rng, false);
  for (let v = -S + 5; v <= S - 5; v += 4) spike(L, null, F + 1, v, ys, rng.int(3, 4 + tier), true, rng, false);
  for (const t of [F + 2, B - 2]) for (const v of [-S + 2, S - 2]) spike(L, null, t, v, ys, 8 + 2 * tier, true, rng, true);
  for (let t = F + 3; t <= -3; t += 3) for (const v of [-4, 4]) spike(L, null, t, v, ys, rng.int(2, 3 + Math.floor(tier / 2)), true, rng, false);
  for (const v of [-9, 9]) {
    L.set(-8, v, ys, A.chiseled);
    L.fill(-8, v, ys + 1, -8, v, ys + 3, A.polished);
    L.set(-8, v, ys + 4, A.chiseled);
    L.set(-8, v, ys + 5, A.soulLantern);
  }
  if (tier >= 3)
    // a second ring of giants beside the gate
    for (const v of [-11, 11]) spike(L, null, 1, v, ys, 6 + 2 * tier, true, rng, true);
}

// ------------------------------------------------------------ the Torre del Tótem
// A shaft 20 long and 40 high with lava at the bottom. From the door, a parkour of ledges on
// the walls and slabs hanging from chains goes round and round, down to a majestic altar on a
// pedestal that rises from the lava, with a totem in a glow item frame. Every jump can be made
// back up (at most one block up with a one-block gap), so you can leave the same way.
function buildTorre(c) {
  const { L, s, Y, rng, th } = c;
  const lavaY = Y + s.bottom + 1;
  shell(c);
  L.fill(s.u0, s.v0, lavaY, s.u1, s.v1, lavaY, mc("lava"));
  wallOverlay(c, lavaY + 1, Y + s.h - 1, 0.3, lusher(th, 0.2));
  ceilOverlay(c, 0.4);
  for (let y = lavaY + 6; y < Y + s.h - 1; y += 8) {
    L.fill(s.u0 - 1, s.v0 - 1, y, s.u1 + 1, s.v0 - 1, y, T.chiseledBricks);
    L.fill(s.u0 - 1, s.v1 + 1, y, s.u1 + 1, s.v1 + 1, y, T.chiseledBricks);
    L.fill(s.u0 - 1, s.v0 - 1, y, s.u0 - 1, s.v1 + 1, y, T.chiseledBricks);
    L.fill(s.u1 + 1, s.v0 - 1, y, s.u1 + 1, s.v1 + 1, y, T.chiseledBricks);
  }
  // the ledge at the door, held by upside-down stairs
  L.fill(s.u0, s.v0, Y - 1, s.u0 + 1, s.v1, Y - 1, T.polished);
  L.fill(s.u0 + 1, s.v0, Y - 2, s.u0 + 1, s.v1, Y - 2, stairs("tuff_brick_stairs", L.dir("u-"), true));
  // the pedestal of the altar, rising from the lava at the far end
  const A = Y - 22, a0 = s.u1 - 4;
  L.fill(a0, s.v0, lavaY, s.u1, s.v1, A - 1, T.bricks);
  for (let y = lavaY + 3; y < A - 1; y += 5) L.fill(a0, s.v0, y, a0, s.v1, y, T.chiseledBricks);
  for (let v = s.v0; v <= s.v1; v++) if (rng.chance(0.35)) caveVines(L, a0 - 1, v, A - 2, rng.int(1, 4), rng, 0.8);
  L.fill(a0, s.v0, A - 1, s.u1, s.v1, A - 1, T.polished);
  // the altar: steps up to a dais of chiseled bricks, the totem on the back wall
  L.fill(a0, 0, A, s.u1 - 3, 0, A, T.mossCarpet);
  L.fill(s.u1 - 2, -2, A, s.u1 - 2, 2, A, stairs("polished_tuff_stairs", L.dir("u+")));
  L.fill(s.u1 - 1, -2, A, s.u1, 2, A, T.chiseledBricks);
  L.set(s.u1, 0, A + 1, T.chiseledBricks);
  L.struct(s.u1, 0, A + 2, `${NS}:totem_${CARD[L.dir("u-")]}`);
  L.fill(s.u1 + 1, -2, A + 1, s.u1 + 1, 2, A + 4, T.chiseledBricks);
  L.set(s.u1 + 1, 0, A + 5, froglight(th));
  for (const v of [-1, 1]) L.set(s.u1, v, A + 1, candle("lime", rng.int(2, 4)));
  for (const v of [-3, 3]) {
    if (v < s.v0 || v > s.v1) continue;
    L.set(s.u1 - 1, v, A, T.chiseledBricks);
    L.fill(s.u1 - 1, v, A + 1, s.u1 - 1, v, A + 4, T.polished);
    L.set(s.u1 - 1, v, A + 5, T.chiseled);
    L.set(s.u1 - 1, v, A + 6, candle("white", rng.int(2, 4)));
    L.set(s.u1, v, A, T.leavesFlower);
    L.set(s.u1, v, A + 1, T.flowering);
    L.set(a0, v, A, rng.chance(0.5) ? T.azalea : T.flowering);
  }
  // two chandeliers on long chains over the altar
  for (const v of [-2, 2]) {
    L.fill(s.u1 - 2, v, A + 6, s.u1 - 2, v, Y + s.h - 1, T.chain);
    L.set(s.u1 - 2, v, A + 5, T.lanternHang);
  }

  // the parkour: a ring along the walls, travelled several times while going down
  const ring = [];
  for (let u = s.u0 + 2; u <= a0 - 1; u++) ring.push([u, s.v1]);
  for (let v = s.v1 - 1; v >= s.v0; v--) ring.push([a0 - 1, v]);
  for (let u = a0 - 2; u >= s.u0 + 2; u--) ring.push([u, s.v0]);
  for (let v = s.v0 + 1; v <= s.v1 - 1; v++) ring.push([s.u0 + 2, v]);
  const used = new Set();
  const wood = rng.pick(th.wood);
  const place = (u, v, sv) => {
    const y = sv - 1;
    used.add(`${u},${v},${y}`);
    if (v === s.v0 || v === s.v1) {
      // a ledge on the wall: a slab over an upside-down stair
      L.set(u, v, y, slab("tuff_brick_slab", true));
      L.set(u, v, y - 1, stairs("tuff_brick_stairs", L.dir(v === s.v1 ? "v+" : "v-"), true));
      if (rng.chance(0.3)) caveVines(L, u, v, y - 2, rng.int(1, 3), rng, 0.7);
      used.add(`${u},${v},${y - 1}`);
      return;
    }
    // a hanging slab, with the chain on the slab next to it (towards the middle)
    const hu = u === a0 - 1 ? u - 1 : u + 1;
    L.set(u, v, y, woodSlab(wood, true));
    L.set(hu, v, y, woodSlab(wood, true));
    used.add(`${hu},${v},${y}`);
    let top = y + 1;
    while (top < Y + s.h - 1 && !used.has(`${hu},${v},${top + 1}`)) top++;
    L.fill(hu, v, y + 1, hu, v, top, T.chain);
  };
  let i = 1, sv = Y, reached = false;
  place(...ring[1], sv);
  for (let guard = 0; guard < 400; guard++) {
    const [u] = ring[i % ring.length];
    if (sv <= A && u === a0 - 1) { reached = true; break; } // next to the altar: the last jump
    const k = rng.chance(0.75) ? 2 : 3;
    if (sv > A && k === 2 && rng.chance(0.9)) sv--;
    i += k;
    place(...ring[i % ring.length], sv);
  }
  c.out.towers = (c.out.towers ?? 0) + (reached ? 1 : 0);
  c.out.towerJumps = Math.floor((i - 1) / 2.25);
}

// ------------------------------------------------------------ the cave entrance
// No entrance: the main hall is a natural-looking cave, larger than every other room, whose
// blocks go from the stone around it to the materials of the dungeon (a gradient), without a
// box around it, so it joins the caves of the terrain.
const natural = (rng, deep) => ({ id: mc(rng.pick(deep ? ["deepslate", "cobbled_deepslate", "tuff", "deepslate"]
  : ["stone", "stone", "andesite", "cobblestone", "diorite", "granite", "stone"])), vanilla: true });

function naturalHall(c) {
  const { L, s, Y, rng, th } = c;
  const abyss = isAbyss(th);
  const deep = Y < 2;
  const cells = caveLayout(c, { core: 4, square: 2.2 });
  // 0 = the dungeon, 1 = the stone around it
  const g = (cl, extra = 0) => Math.min(1, Math.max(0, (cl.d - 0.2) / 0.65 + (rng.next() - 0.5) * 0.4 + extra));
  const wallMat = () => (abyss ? aWall(rng) : wallVariant(rng, th));
  const floorMat = () => (abyss ? aFloor(rng) : rng.chance(0.45) ? T.moss : floorVariant(rng, th));
  for (const cl of cells.values()) {
    if (!cl.cave) continue;
    const { u, v, fh, ch } = cl;
    L.fill(u, v, cl.air, u, v, ch, AIR);
    const fy = Y - 1 + Math.floor(fh / 2), gf = g(cl);
    const fb = rng.next() < gf ? natural(rng, deep) : floorMat();
    L.set(u, v, fy, fb);
    L.set(u, v, fy - 1, rng.next() < gf ? natural(rng, deep) : abyss ? A.cobbled : T.tuff);
    if (fh & 1) L.set(u, v, fy + 1, abyss ? aSlab(rng, false) : slab(rng.chance(0.5) ? "tuff_brick_slab" : "polished_tuff_slab", false));
    else if (!abyss && fb === T.moss && rng.chance(0.4)) L.set(u, v, fy + 1, T.mossCarpet);
    L.set(u, v, ch + 1, rng.next() < g(cl, 0.1) ? natural(rng, deep) : wallMat());
    for (const [du, dv] of N4) {
      if (cells.get(`${u + du},${v + dv}`)?.cave) continue;
      for (let y = cl.air; y <= ch; y++) L.set(u + du, v + dv, y, rng.next() < g(cl, 0.2) ? natural(rng, deep) : wallMat());
    }
  }
  const open = [...cells.values()].filter((cl) => cl.cave);
  if (abyss) {
    caveSpikes(c, cells, { upEvery: 50, downEvery: 30 });
    caveLights(c, cells, 3);
    return;
  }
  // a lush cave: plants, glow berries, pools with dripleaves, spore blossoms
  for (const cl of open) {
    if (cl.ch - cl.air >= 5 && rng.chance(0.1)) hanging(L, cl.u, cl.v, cl.ch, 3, rng, lusher(th, 0.5));
    if (cl.lane || cl.fh & 1 || cl.d > 0.85) continue;
    const r = rng.next();
    if (r < 0.05) L.set(cl.u, cl.v, cl.air, rng.chance(0.5) ? T.fern : T.grass);
    else if (r < 0.08) L.set(cl.u, cl.v, cl.air, rng.chance(0.5) ? T.azalea : T.flowering);
  }
  const flat = open.filter((cl) => cl.fh === 0 && !cl.lane && !(Math.abs(cl.u) <= 4 && Math.abs(cl.v) <= 4));
  for (let k = 0; k < 3 && flat.length; k++) {
    const cl = rng.pick(flat);
    const ok = [[0, 0], [1, 0], [0, 1], [1, 1]].every(([du, dv]) => {
      const n = cells.get(`${cl.u + du},${cl.v + dv}`);
      return n && n.cave && n.fh === 0 && !n.lane;
    });
    if (!ok) continue;
    L.fill(cl.u, cl.v, Y, cl.u + 1, cl.v + 1, Y + 1, AIR);
    L.fill(cl.u, cl.v, Y - 1, cl.u + 1, cl.v + 1, Y - 1, T.water);
    L.fill(cl.u, cl.v, Y - 2, cl.u + 1, cl.v + 1, Y - 2, T.clay);
  }
  for (let k = 0; k < 4 && open.length; k++) {
    const cl = rng.pick(open);
    L.set(cl.u, cl.v, cl.ch, T.spore);
  }
}

// Two or three winding tunnels from the back of the hall, going up and away into the stone:
// they end blind under the surface or meet the caves of the terrain.
function caveTunnels(bld, hall, th, rng) {
  const L = bld.frame(hall.x, hall.z, hall.dirIn);
  const s = hall.spec, Y = hall.Y;
  for (let k = rng.int(2, 3); k > 0; k--) {
    let u = s.u0 + 3, v = rng.int(-6, 6), y = Y + 1, dv = 0;
    const len = rng.int(22, 28);
    for (let i = 0; i < len; i++) {
      const r = rng.chance(0.3) ? 2 : 1;
      L.fill(u - r, v - r, y - 1, u + r, v + r, y + r, AIR);
      if (!isAbyss(th) && i < 8) {
        if (rng.chance(0.4)) L.set(u, v, y - 2, rng.chance(0.6) ? T.moss : T.tuff);
        if (rng.chance(0.25)) caveVines(L, u, v, y + r, rng.int(1, 2), rng);
      }
      u -= 1;
      dv = Math.max(-1, Math.min(1, dv + rng.int(-1, 1)));
      if (rng.chance(0.5)) v = Math.max(-7, Math.min(7, v + dv));
      if (i % 3 === 2 && y < Y + 14) y++;
    }
  }
}

// ------------------------------------------------------------ the whole dungeon
// origin: the block the player stands in (feet), the top of the entrance.
// Returns pieces in three phases (rooms, then corridors, then the entrance):
// a corridor opens doors in the walls of two rooms, so the rooms go first.
export function buildDungeon(plan, origin) {
  const th = THEMES[plan.theme];
  const [fdx, fdz] = DIRS[plan.facing];
  const vx = origin.x + fdx * plan.vestOff, vz = origin.z + fdz * plan.vestOff;
  // cave entrance: the hall floor is where the player stands
  const y0 = plan.cave ? origin.y : origin.y - ENTRY_DEPTH;
  const rooms = plan.rooms.map((r) => ({ ...r, x: vx + r.cx, z: vz + r.cz, Y: y0 + r.Y }));
  const pieces = [];
  const out = { spawners: [] };
  for (const r of rooms) {
    const bld = new Builder();
    const L = bld.frame(r.x, r.z, r.dirIn);
    const natural = plan.cave && r.id === 0;
    const doors = new Set([...(natural ? [] : ["u-"]), ...r.kids.map((k) => L.local(rooms[k].dirIn))]);
    const build = natural ? naturalHall : (isAbyss(th) ? ABYSS_BUILDERS : BUILDERS)[r.type];
    build({ L, s: r.spec, Y: r.Y, rng: makeRng(plan.seed, 100, r.id), th, room: r, out, doors, tier: plan.tier });
    // where you stand just inside the door (used by the simulation)
    r.probe = natural ? [r.x, r.Y, r.z] : [L.x(r.spec.u0, 0), r.Y, L.z(r.spec.u0, 0)];
    r.box = roomBoxOf(r, r.x, r.z);
    pieces.push({ phase: 0, name: `${TYPE_NAME[r.type]} ${r.id}`, ops: bld.ops });
  }
  for (const r of rooms) {
    if (r.parent < 0) continue;
    const bld = new Builder();
    corridor(bld, rooms[r.parent], r, th, makeRng(plan.seed, 200, r.id));
    pieces.push({ phase: 1, name: `pasillo ${r.parent}-${r.id}`, ops: bld.ops });
  }
  const bld = new Builder();
  if (plan.cave) caveTunnels(bld, rooms[0], th, makeRng(plan.seed, 300));
  else (isAbyss(th) ? (b, o, f, y, h, t, _th, r) => abyssEntrance(b, o, f, y, h, t, r) : entrance)(
    bld, origin, plan.facing, y0, plan.vestOff - (-rooms[0].spec.u0 + 1), plan.tier, th, makeRng(plan.seed, 300));
  pieces.push({ phase: 2, name: plan.cave ? "túneles" : "entrada", ops: bld.ops });

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
  return { pieces, spawners: out.spawners, bounds, y0, rooms, towers: out.towers ?? 0 };
}

// How many floors fit above minY (the bottom of the world).
export function maxFloorsAt(y, minY, theme, cave = false) {
  const y0 = cave ? y : y - ENTRY_DEPTH;
  const below = isAbyss(THEMES[theme] ?? {}) ? 18 : 7; // the chasms go 16 blocks under their floor
  let n = 0;
  while (n < MAX_FLOORS && y0 - n * FLOOR_H - below > minY + 1) n++;
  return n;
}
