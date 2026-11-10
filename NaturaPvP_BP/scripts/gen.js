// Natura PvP: the shape of the lobby and of the three arenas.
// Pure functions (no Minecraft imports) so they also run in Node for the preview.
//
// Every area is described column by column: column(x, z) returns the segments
// [y0, y1, blockKey] to fill, in order (later segments overwrite earlier ones).
// The world is void around them. The same function rebuilds a column, which is
// how the hunting arena regenerates the blocks the players broke or placed.

// ------------------------------------------------------------ blocks
// "a|b|c": the first id this version of the game knows is used.
export const PALETTE = {
  grass: { id: "minecraft:grass_block|minecraft:grass" },
  dirt: { id: "minecraft:dirt" },
  coarse: { id: "minecraft:coarse_dirt|minecraft:dirt" },
  podzol: { id: "minecraft:podzol|minecraft:dirt" },
  moss: { id: "minecraft:moss_block|minecraft:grass_block" },
  stone: { id: "minecraft:stone" },
  andesite: { id: "minecraft:andesite|minecraft:stone" },
  pandesite: { id: "minecraft:polished_andesite|minecraft:stone" },
  cobble: { id: "minecraft:cobblestone" },
  mcobble: { id: "minecraft:mossy_cobblestone" },
  sbrick: { id: "minecraft:stone_bricks|minecraft:stonebrick" },
  msbrick: { id: "minecraft:mossy_stone_bricks|minecraft:stone_bricks" },
  cbrick: { id: "minecraft:cracked_stone_bricks|minecraft:stone_bricks" },
  chbrick: { id: "minecraft:chiseled_stone_bricks|minecraft:stone_bricks" },
  bedrock: { id: "minecraft:bedrock" },
  barrier: { id: "minecraft:barrier" },
  water: { id: "minecraft:water" },
  sand: { id: "minecraft:sand" },
  gravel: { id: "minecraft:gravel" },
  clay: { id: "minecraft:clay" },
  path: { id: "minecraft:grass_path|minecraft:dirt_path|minecraft:gravel" },
  oak: { id: "minecraft:oak_log", s: { pillar_axis: "y" } },
  birch: { id: "minecraft:birch_log", s: { pillar_axis: "y" } },
  spruce: { id: "minecraft:spruce_log", s: { pillar_axis: "y" } },
  oak_x: { id: "minecraft:oak_log", s: { pillar_axis: "x" } },
  oak_z: { id: "minecraft:oak_log", s: { pillar_axis: "z" } },
  birch_x: { id: "minecraft:birch_log", s: { pillar_axis: "x" } },
  birch_z: { id: "minecraft:birch_log", s: { pillar_axis: "z" } },
  spruce_x: { id: "minecraft:spruce_log", s: { pillar_axis: "x" } },
  spruce_z: { id: "minecraft:spruce_log", s: { pillar_axis: "z" } },
  dark: { id: "minecraft:dark_oak_log|minecraft:spruce_log", s: { pillar_axis: "y" } },
  dark_x: { id: "minecraft:dark_oak_log|minecraft:spruce_log", s: { pillar_axis: "x" } },
  dark_z: { id: "minecraft:dark_oak_log|minecraft:spruce_log", s: { pillar_axis: "z" } },
  cherry: { id: "minecraft:cherry_log|minecraft:birch_log", s: { pillar_axis: "y" } },
  cherry_x: { id: "minecraft:cherry_log|minecraft:birch_log", s: { pillar_axis: "x" } },
  cherry_z: { id: "minecraft:cherry_log|minecraft:birch_log", s: { pillar_axis: "z" } },
  darkL: { id: "minecraft:dark_oak_leaves|minecraft:oak_leaves", s: { persistent_bit: true } },
  cherryL: { id: "minecraft:cherry_leaves|minecraft:azalea_leaves_flowered|minecraft:oak_leaves", s: { persistent_bit: true } },
  oakL: { id: "minecraft:oak_leaves", s: { persistent_bit: true } },
  birchL: { id: "minecraft:birch_leaves", s: { persistent_bit: true } },
  spruceL: { id: "minecraft:spruce_leaves", s: { persistent_bit: true } },
  azaleaL: { id: "minecraft:azalea_leaves", s: { persistent_bit: true } },
  fazaleaL: { id: "minecraft:azalea_leaves_flowered|minecraft:azalea_leaves", s: { persistent_bit: true } },
  tgrass: { id: "minecraft:short_grass|minecraft:tallgrass" },
  fern: { id: "minecraft:fern|minecraft:short_grass" },
  poppy: { id: "minecraft:poppy|minecraft:red_flower" },
  dandelion: { id: "minecraft:dandelion|minecraft:yellow_flower" },
  cornflower: { id: "minecraft:cornflower|minecraft:poppy" },
  oxeye: { id: "minecraft:oxeye_daisy|minecraft:poppy" },
  azure: { id: "minecraft:azure_bluet|minecraft:poppy" },
  allium: { id: "minecraft:allium|minecraft:poppy" },
  tulip: { id: "minecraft:red_tulip|minecraft:poppy" },
  otulip: { id: "minecraft:orange_tulip|minecraft:poppy" },
  lily: { id: "minecraft:lily_of_the_valley|minecraft:poppy" },
  mcarpet: { id: "minecraft:moss_carpet|minecraft:short_grass" },
  lantern: { id: "minecraft:lantern" },
  fence: { id: "minecraft:oak_fence|minecraft:fence" },
  shroom: { id: "minecraft:shroomlight|minecraft:glowstone" },
  diamond: { id: "minecraft:diamond_block" },
  emerald: { id: "minecraft:emerald_block" },
  redstone: { id: "minecraft:redstone_block" },
  lapis: { id: "minecraft:lapis_block" },
  vineN: { id: "minecraft:vine", s: { vine_direction_bits: 4 } },
  vineS: { id: "minecraft:vine", s: { vine_direction_bits: 1 } },
  vineW: { id: "minecraft:vine", s: { vine_direction_bits: 2 } },
  vineE: { id: "minecraft:vine", s: { vine_direction_bits: 8 } },
};

// ------------------------------------------------------------ noise
const SEED = 7349;

export function hash(x, z, s = 0) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263) + Math.imul(s | 0, 982451653)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

function smooth(t) {
  return t * t * (3 - 2 * t);
}

function vnoise(x, z, scale, s) {
  const fx = x / scale, fz = z / scale;
  const x0 = Math.floor(fx), z0 = Math.floor(fz);
  const tx = smooth(fx - x0), tz = smooth(fz - z0);
  const a = hash(x0, z0, s), b = hash(x0 + 1, z0, s), c = hash(x0, z0 + 1, s), d = hash(x0 + 1, z0 + 1, s);
  const top = a + (b - a) * tx, bot = c + (d - c) * tx;
  return (top + (bot - top) * tz) * 2 - 1;
}

function fbm(x, z, scale, s) {
  return vnoise(x, z, scale, s) * 0.6 + vnoise(x, z, scale / 2, s + 1) * 0.28 + vnoise(x, z, scale / 4, s + 2) * 0.12;
}

const pick = (list, r) => list[Math.min(list.length - 1, Math.floor(r * list.length))];
const FLOWERS = ["poppy", "dandelion", "cornflower", "oxeye", "azure", "allium", "tulip", "otulip", "lily"];

// ------------------------------------------------------------ trees
// A tree: { x, z, y (ground), type, h }. Its shape is worked out once (and kept)
// as a map "dx,dz" -> leaves and logs of that column, so a column only has to
// look at the trees around it. Types: oak, big (fancy oak with branches and
// roots), birch, spruce, mega (2x2 spruce), dark (2x2 dark oak), azalea,
// cherry, bush and fallen (a log lying on the ground).
const shapes = new Map();
export const TREE_REACH = 6;

function treeShape(t) {
  const id = `${t.type}:${t.x}:${t.z}:${t.y}:${t.h}`;
  let m = shapes.get(id);
  if (m) return m;
  if (shapes.size > 30000) shapes.clear();
  m = new Map();
  shapes.set(id, m);
  const R = (i) => hash(t.x * 31 + i * 7, t.z * 17 - i * 3, 4242 + t.y);
  const col = (dx, dz) => {
    const k = `${dx},${dz}`;
    let c = m.get(k);
    if (!c) m.set(k, (c = { leaves: [], logs: [] }));
    return c;
  };
  const log = (dx, y, dz, key) => col(dx, dz).logs.push([y, y, key]);
  const trunk = (dx, dz, y0, y1, key) => y1 >= y0 && col(dx, dz).logs.push([y0, y1, key]);
  const leafAt = (dx, dz, y0, y1, key) => y1 >= y0 && col(dx, dz).leaves.push([y0, y1, key]);
  // a round cluster of leaves (vk squashes or stretches it)
  const blob = (bx, by, bz, r, key, vk = 0.75, ragged = 0.3) => {
    const n = Math.ceil(r + 0.5);
    for (let dx = -n; dx <= n; dx++)
      for (let dz = -n; dz <= n; dz++) {
        const d = Math.hypot(dx + (bx % 1), dz + (bz % 1));
        if (d > r) continue;
        const cx = Math.floor(bx) + dx, cz = Math.floor(bz) + dz;
        if (d > r - 1 && hash(t.x + cx, t.z + cz, 4300 + Math.round(by)) < ragged) continue;
        const e = Math.sqrt(r * r - d * d) * vk;
        const k = typeof key === "function" ? key(cx, cz) : key;
        leafAt(cx, cz, Math.round(by - e), Math.round(by + e), k);
      }
  };
  const axis = (wood, a) => (Math.abs(Math.cos(a)) >= Math.abs(Math.sin(a)) ? `${wood}_x` : `${wood}_z`);
  // a branch that leaves the trunk at height y and climbs outwards
  const branch = (wood, y, a, len, rise = 0.6) => {
    let px = 0, pz = 0, py = y;
    for (let s = 1; s <= len; s++) {
      px = Math.round(Math.cos(a) * s);
      pz = Math.round(Math.sin(a) * s);
      py = y + Math.floor(s * rise);
      log(px, py, pz, axis(wood, a));
    }
    return { x: px, y: py, z: pz };
  };
  const top = t.y + t.h;
  const y = t.y;
  switch (t.type) {
    case "oak": {
      trunk(0, 0, y + 1, top - 1, "oak");
      blob(0, top - 0.5, 0, 2.6, "oakL", 0.7);
      for (let i = 0; i < 2; i++) {
        const a = R(i) * Math.PI * 2;
        blob(Math.round(Math.cos(a) * 1.4), top - 1, Math.round(Math.sin(a) * 1.4), 1.9, "oakL", 0.75, 0.4);
      }
      if (t.h >= 6 && R(5) < 0.6) {
        const end = branch("oak", y + t.h - 3, R(6) * Math.PI * 2, 2, 0.5);
        blob(end.x, end.y + 1, end.z, 1.7, "oakL", 0.8, 0.35);
      }
      break;
    }
    case "big": {
      trunk(0, 0, y + 1, top - 1, "oak");
      const n = 3 + (R(1) < 0.5 ? 1 : 0);
      const base = R(2) * Math.PI * 2;
      for (let i = 0; i < n; i++) {
        const a = base + (i * Math.PI * 2) / n + (R(10 + i) - 0.5) * 0.9;
        const by = y + Math.floor(t.h * (0.45 + 0.35 * R(20 + i)));
        const end = branch("oak", by, a, 2 + (R(30 + i) < 0.5 ? 1 : 0));
        blob(end.x, end.y + 1, end.z, 2.2 + R(40 + i) * 0.5, "oakL", 0.7);
      }
      blob(0, top, 0, 3.2, "oakL", 0.72);
      // roots
      [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([dx, dz], i) => {
        if (R(50 + i) < 0.65) log(dx, y + 1, dz, R(55 + i) < 0.5 ? "oak" : dx ? "oak_x" : "oak_z");
        if (R(60 + i) < 0.35) log(dx * 2, y + 1, dz * 2, dx ? "oak_x" : "oak_z");
      });
      break;
    }
    case "birch": {
      trunk(0, 0, y + 1, top, "birch");
      blob(0, top - 1.5, 0, 2.2, "birchL", 1.2, 0.35);
      leafAt(0, 0, top + 1, top + 1, "birchL");
      if (R(3) < 0.4) blob(Math.round(Math.cos(R(4) * 6.3) * 1.5), top - 3, Math.round(Math.sin(R(4) * 6.3) * 1.5), 1.5, "birchL", 0.9, 0.4);
      break;
    }
    case "spruce":
    case "mega": {
      const mega = t.type === "mega";
      const off = mega ? 0.5 : 0;
      const maxR = mega ? 4.2 : 3;
      if (mega) for (const [dx, dz] of [[0, 0], [1, 0], [0, 1], [1, 1]]) trunk(dx, dz, y + 1, top, "spruce");
      else trunk(0, 0, y + 1, top, "spruce");
      const n = Math.ceil(maxR) + 1;
      for (let dx = -n; dx <= n + (mega ? 1 : 0); dx++)
        for (let dz = -n; dz <= n + (mega ? 1 : 0); dz++) {
          const ax = Math.abs(dx - off), az = Math.abs(dz - off);
          const d = Math.max(ax, az) + Math.min(ax, az) * 0.45;
          let run = null;
          // rings: wide and narrow layers that get wider downwards
          for (let yy = top + (mega ? 2 : 1); yy >= y + (mega ? 5 : 3); yy--) {
            const k = top + (mega ? 2 : 1) - yy;
            const grow = Math.min(maxR, 0.6 + k * (mega ? 0.32 : 0.36));
            const r = k % 2 === 0 ? grow : grow - 1.1;
            const inside = d <= r + 0.15 && !(d > r - 0.6 && hash(t.x + dx, t.z + dz, 4400 + yy) < 0.25);
            if (inside) run = run ? [yy, run[1]] : [yy, yy];
            else if (run) {
              leafAt(dx, dz, run[0], run[1], "spruceL");
              run = null;
            }
          }
          if (run) leafAt(dx, dz, run[0], run[1], "spruceL");
        }
      break;
    }
    case "dark": {
      for (const [dx, dz] of [[0, 0], [1, 0], [0, 1], [1, 1]]) trunk(dx, dz, y + 1, top, "dark");
      const n = 2 + (R(1) < 0.5 ? 1 : 0);
      for (let i = 0; i < n; i++) {
        const a = R(10 + i) * Math.PI * 2;
        const end = branch("dark", top - 2, a, 2, 0.5);
        blob(end.x + 0.5, top, end.z + 0.5, 2.6, "darkL", 0.55);
      }
      blob(0.5, top + 0.5, 0.5, 4.3, "darkL", 0.42, 0.35);
      break;
    }
    case "azalea": {
      trunk(0, 0, y + 1, top, "oak");
      const mix = (cx, cz) => (hash(cx + t.x, cz + t.z, 4500) < 0.35 ? "fazaleaL" : "azaleaL");
      blob(0, top + 1, 0, 2.7, mix, 0.5, 0.3);
      break;
    }
    case "cherry": {
      trunk(0, 0, y + 1, y + Math.max(2, t.h - 3), "cherry");
      const a = R(1) * Math.PI * 2;
      for (const k of [0, 1]) {
        const end = branch("cherry", y + t.h - 3, a + k * Math.PI + (R(2 + k) - 0.5) * 0.6, 2 + (R(4 + k) < 0.5 ? 1 : 0), 0.8);
        trunk(end.x, end.z, end.y + 1, end.y + 1, "cherry");
        blob(end.x, end.y + 2, end.z, 2.7, "cherryL", 0.62, 0.3);
      }
      break;
    }
    case "bush": {
      log(0, y + 1, 0, "oak");
      blob(0, y + 1.5, 0, 1.8, R(1) < 0.5 ? "oakL" : "azaleaL", 0.7, 0.35);
      break;
    }
    case "fallen": {
      const along = R(1) < 0.5;
      const len = 4 + Math.floor(R(2) * 3);
      const wood = R(3) < 0.6 ? "oak" : R(3) < 0.85 ? "birch" : "spruce";
      for (let s = 0; s < len; s++) {
        const dx = along ? s - 1 : 0, dz = along ? 0 : s - 1;
        log(dx, y + 1, dz, `${wood}_${along ? "x" : "z"}`);
        if (s > 0 && hash(t.x + s, t.z, 4600) < 0.55) log(dx, y + 2, dz, "mcarpet");
      }
      log(along ? -3 : 0, y + 1, along ? 0 : -3, wood);
      break;
    }
  }
  return m;
}

export function treeHeight(type, r) {
  switch (type) {
    case "big": return 9 + Math.floor(r * 4);
    case "birch": return r < 0.2 ? 9 + Math.floor(r * 10) : 6 + Math.floor(r * 3);
    case "spruce": return 8 + Math.floor(r * 5);
    case "mega": return 15 + Math.floor(r * 5);
    case "dark": return 6 + Math.floor(r * 3);
    case "azalea": return 2 + Math.floor(r * 2);
    case "cherry": return 5 + Math.floor(r * 2);
    case "bush":
    case "fallen": return 1;
    default: return 4 + Math.floor(r * 3);
  }
}

// Trees on a grid of cells (one candidate per cell), so a column only needs to
// look at the trees of the 3x3 cells around it.
function gridTrees(x, z, cell, treeAt) {
  const cx = Math.floor(x / cell), cz = Math.floor(z / cell);
  const out = [];
  for (let i = -1; i <= 1; i++)
    for (let j = -1; j <= 1; j++) {
      const t = treeAt(cx + i, cz + j);
      if (t && Math.abs(t.x - x) <= TREE_REACH && Math.abs(t.z - z) <= TREE_REACH) out.push(t);
    }
  return out;
}

// Adds the leaves and then the logs of the trees on column (x, z). True if a
// log stands on the ground there (no flowers then).
function addTrees(trees, x, z, segs) {
  const logs = [];
  let ground = false;
  for (const t of trees) {
    const c = treeShape(t).get(`${x - t.x},${z - t.z}`);
    if (!c) continue;
    for (const s of c.leaves) segs.push(s);
    for (const s of c.logs) {
      logs.push(s);
      if (s[0] === t.y + 1) ground = true;
    }
  }
  for (const s of logs) segs.push(s);
  return ground;
}

function groundColumn(segs, bottom, h, top, sub = "dirt", rock = "stone", dirtDepth = 3) {
  if (h - dirtDepth - 1 >= bottom) segs.push([bottom, h - dirtDepth - 1, rock]);
  if (h - 1 >= Math.max(bottom, h - dirtDepth)) segs.push([Math.max(bottom, h - dirtDepth), h - 1, sub]);
  segs.push([h, h, top]);
}

function decoration(x, z, s, forest) {
  const r = hash(x, z, s);
  const flowerPatch = vnoise(x, z, 9, s + 5) > 0.35;
  if (flowerPatch && r < 0.32) return pick(FLOWERS, hash(Math.floor(x / 5), Math.floor(z / 5), s + 6) * 0.7 + hash(x, z, s + 8) * 0.3);
  if (r < (forest ? 0.42 : 0.36)) return forest && hash(x, z, s + 3) < 0.45 ? "fern" : "tgrass";
  return null;
}

// ------------------------------------------------------------ walls
// Colossal mossy walls. `w` = 1 (inner face) .. thickness (outer face),
// `along` = position along the wall, used for the log pillars.
function wallColumn(segs, x, z, w, along, bottom, top, thick, corner) {
  const pillar = w <= 2 && ((along % 9) + 9) % 9 === 0;
  if (pillar) {
    segs.push([bottom, top, w === 1 ? "spruce" : "oak"]);
    for (let y = bottom + 8; y < top - 2; y += 12) segs.push([y, y, "shroom"]);
  } else {
    // bands of bricks, moss and cracks
    for (let y = bottom; y <= top; y += 4) {
      const r = hash(x * 7 + y, z * 13 - y, 41);
      const mossy = y > top - 14 || r < 0.42;
      const b = r < 0.08 ? "cbrick" : r < 0.14 ? "moss" : mossy ? "msbrick" : r < 0.2 ? "chbrick" : "sbrick";
      segs.push([y, Math.min(top, y + 3), w === thick && r > 0.8 ? "mcobble" : b]);
    }
  }
  if (corner) {
    // towers in the corners, a bit higher, with a crown of leaves
    segs.push([top + 1, top + 9, (x + z) % 5 === 0 ? "chbrick" : "msbrick"]);
    segs.push([top + 10, top + 12, "spruceL"]);
    if (w === 2) segs.push([top + 13, top + 13, "spruceL"]);
  } else if (w === thick) {
    if (((along % 2) + 2) % 2 === 0) segs.push([top + 1, top + 2, "msbrick"]);
  } else {
    // a green crest of leaves and moss on the top
    const r = hash(x, z, 51);
    segs.push([top + 1, top + 1, r < 0.5 ? "oakL" : r < 0.75 ? "azaleaL" : "moss"]);
    if (w === 1 && ((along % 9) + 9) % 9 === 4) segs.push([top + 2, top + 2, "lantern"]);
    else if (r < 0.3) segs.push([top + 2, top + 2, "oakL"]);
  }
}

// Vines and leaves hanging on the inner face of a wall. `dir` = side of the wall.
function hangingColumn(segs, x, z, top, floor, dir) {
  const r = hash(x, z, 61);
  if (r < 0.45) {
    const len = 6 + Math.floor(hash(x, z, 62) * (top - floor - 14));
    segs.push([top - len, top, dir]);
  }
  if (hash(x, z, 63) < 0.5) segs.push([top - 1 - Math.floor(hash(x, z, 64) * 4), top, hash(x, z, 65) < 0.5 ? "oakL" : "azaleaL"]);
}

// ------------------------------------------------------------ the lobby
export const LOBBY = {
  cx: 0, cz: 0, y: 100,
  spawn: { x: 0.5, y: 101, z: 5.5 },
  // the three pads that send you to the modes (centre of a 3x3 coloured square)
  pads: {
    duel: { x: 0, z: -17, block: "diamond" },
    hunt: { x: -15, z: 9, block: "redstone" },
    campal: { x: 15, z: 9, block: "emerald" },
  },
};
const LOBBY_R = 27;

function lobbyRadius(x, z) {
  const a = Math.atan2(z, x);
  return LOBBY_R + Math.sin(a * 3 + 0.7) * 1.6 + Math.sin(a * 7 + 2.1) * 1.1 + vnoise(Math.cos(a) * 40, Math.sin(a) * 40, 9, 900) * 1.2;
}

const LOBBY_TREES = [
  [-9, -20, "big", 10], [9, -21, "cherry", 6], [-21, -7, "dark", 7], [21, -6, "big", 9], [-20, 17, "cherry", 5],
  [20, 17, "oak", 6], [-6, 21, "birch", 8], [8, 20, "big", 9], [-15, -16, "birch", 7], [16, -15, "azalea", 3],
  [0, 22, "azalea", 3], [-23, 3, "birch", 8], [23, 3, "cherry", 5], [-12, 13, "bush", 1], [12, 14, "bush", 1],
].map(([x, z, type, h]) => ({ x, z, y: 100, type, h }));

function onLobbyPath(x, z) {
  const p = LOBBY.pads;
  for (const pad of [p.duel, p.hunt, p.campal]) {
    const len = Math.hypot(pad.x, pad.z);
    const ux = pad.x / len, uz = pad.z / len;
    const t = x * ux + z * uz;
    const d = Math.abs(x * uz - z * ux);
    if (t > 6 && t < len - 2 && d <= 1.3) return true;
  }
  return false;
}

function lobbyColumn(x, z) {
  const segs = [];
  const y = LOBBY.y;
  const r = Math.hypot(x, z);
  const R = lobbyRadius(x, z);
  if (r > R) {
    // an invisible fence just outside the edge so nobody falls
    if (r <= R + 1.6) segs.push([y + 1, y + 4, "barrier"]);
    return segs;
  }
  const depth = 4 + Math.floor((1 - Math.pow(r / R, 1.6)) * 22 + vnoise(x, z, 5, 901) * 3);
  let top = "grass";
  const edge = R - r < 1.5;
  if (!edge && hash(x, z, 902) < 0.1) top = hash(x, z, 903) < 0.5 ? "moss" : "coarse";
  if (onLobbyPath(x, z)) top = "path";
  // the plaza and the fountain
  if (r < 7.5) top = hash(x, z, 904) < 0.3 ? "msbrick" : hash(x, z, 905) < 0.15 ? "cbrick" : "sbrick";
  groundColumn(segs, y - depth, y, top, "dirt", hash(x, z, 906) < 0.3 ? "andesite" : "stone");
  if (r < 7.5) {
    if (r < 0.6) {
      segs.push([y, y + 2, "chbrick"], [y + 3, y + 3, "shroom"]);
    } else if (r < 1.9) {
      segs.push([y - 1, y - 1, "sbrick"], [y, y, "water"]);
    } else if (r < 2.9) {
      segs.push([y + 1, y + 1, "msbrick"]);
    }
    // lanterns around the plaza
    const a = Math.atan2(z, x);
    if (r > 6.4 && r < 7.5) {
      const k = Math.round((a / (Math.PI * 2)) * 8);
      const ang = (k * Math.PI * 2) / 8 + Math.PI / 8;
      const lx = Math.round(Math.cos(ang) * 6.9), lz = Math.round(Math.sin(ang) * 6.9);
      if (lx === x && lz === z) segs.push([y + 1, y + 2, "fence"], [y + 3, y + 3, "lantern"]);
    }
    return segs;
  }
  // the pads
  for (const pad of Object.values(LOBBY.pads)) {
    const ax = Math.abs(x - pad.x), az = Math.abs(z - pad.z);
    if (ax <= 2 && az <= 2) {
      segs.push([y, y, ax <= 1 && az <= 1 ? pad.block : "pandesite"]);
      if ((ax === 2 && az === 2)) segs.push([y + 1, y + 2, "fence"], [y + 3, y + 3, "lantern"]);
      return segs;
    }
  }
  if (top === "path") return segs;
  const hasTrunk = addTrees(LOBBY_TREES.filter((t) => Math.abs(t.x - x) <= TREE_REACH && Math.abs(t.z - z) <= TREE_REACH), x, z, segs);
  if (!hasTrunk && !edge && (top === "grass" || top === "moss")) {
    const deco = decoration(x, z, 910, false);
    if (deco) segs.push([y + 1, y + 1, deco]);
    else if (hash(x, z, 911) < 0.025) segs.push([y + 1, y + 1, "azaleaL"]);
  }
  return segs;
}

// ------------------------------------------------------------ duel arenas (64x64)
export const DUEL = {
  y: 80, half: 32, wallTop: 128, thick: 4,
  centers: [{ x: 0, z: 320 }, { x: 160, z: 320 }],
};

// cover: the same rocks and bushes on both halves (point symmetry)
const DUEL_COVER = [
  { x: -12, z: -7, kind: "rock" }, { x: 9, z: -13, kind: "bush" }, { x: -22, z: 4, kind: "bush" },
  { x: -4, z: -1, kind: "rock" }, { x: 20, z: -20, kind: "rock" }, { x: -16, z: -18, kind: "bush" },
];

function duelCover(lx, lz) {
  for (const c of DUEL_COVER) {
    for (const [cx, cz] of [[c.x, c.z], [-1 - c.x, -1 - c.z]]) {
      const dx = lx - cx, dz = lz - cz;
      if (c.kind === "rock" && Math.abs(dx) <= 1 && Math.abs(dz) <= 1) {
        const h = dx === 0 && dz === 0 ? 3 : Math.abs(dx) + Math.abs(dz) === 1 ? 2 : 1;
        return [1, h, hash(Math.min(lx, -1 - lx), Math.abs(dz) + Math.abs(dx), 71) < 0.5 ? "mcobble" : "andesite"];
      }
      if (c.kind === "bush" && dx >= 0 && dx <= 1 && dz >= 0 && dz <= 1) return [1, 2, "azaleaL"];
      if (c.kind === "bush" && dx >= -1 && dx <= 2 && dz >= -1 && dz <= 2 && !((dx === -1 || dx === 2) && (dz === -1 || dz === 2))) return [1, 1, "oakL"];
    }
  }
  return null;
}

function duelColumn(arena, x, z) {
  const c = DUEL.centers[arena];
  const lx = x - c.x, lz = z - c.z;
  const H = DUEL.half, y = DUEL.y, segs = [];
  const wx = lx < -H ? -H - lx : lx > H - 1 ? lx - (H - 1) : 0;
  const wz = lz < -H ? -H - lz : lz > H - 1 ? lz - (H - 1) : 0;
  if (wx > DUEL.thick || wz > DUEL.thick) return segs;
  if (wx > 0 || wz > 0) {
    const w = Math.max(wx, wz);
    const along = wx >= wz ? lz : lx;
    wallColumn(segs, x, z, w, along, y - 6, DUEL.wallTop, DUEL.thick, wx > 0 && wz > 0);
    return segs;
  }
  // the floor: grass, symmetric decoration
  const sx = lx < -1 - lx || (lx === -1 - lx && lz < -1 - lz) ? lx : -1 - lx;
  const sz = sx === lx ? lz : -1 - lz;
  const top = hash(sx, sz, 72) < 0.07 ? "moss" : "grass";
  groundColumn(segs, y - 6, y, top);
  const cover = duelCover(lx, lz);
  if (cover) segs.push([y + cover[0], y + cover[1], cover[2]]);
  else {
    const deco = decoration(sx, sz, 73, false);
    if (deco) segs.push([y + 1, y + 1, deco]);
  }
  // vines on the walls
  if (lx === -H) hangingColumn(segs, x, z, DUEL.wallTop - 1, y, "vineW");
  else if (lx === H - 1) hangingColumn(segs, x, z, DUEL.wallTop - 1, y, "vineE");
  else if (lz === -H) hangingColumn(segs, x, z, DUEL.wallTop - 1, y, "vineN");
  else if (lz === H - 1) hangingColumn(segs, x, z, DUEL.wallTop - 1, y, "vineS");
  segs.push([DUEL.wallTop + 1, DUEL.wallTop + 1, "barrier"]);
  return segs;
}

export function duelSpawns(arena) {
  const c = DUEL.centers[arena];
  return [
    { x: c.x + 0.5, y: DUEL.y + 1, z: c.z - 26 + 0.5, facing: { x: c.x + 0.5, y: DUEL.y + 1, z: c.z } },
    { x: c.x - 0.5, y: DUEL.y + 1, z: c.z + 25 + 0.5, facing: { x: c.x, y: DUEL.y + 1, z: c.z } },
  ];
}

// ------------------------------------------------------------ campal (126x126)
export const CAMPAL = { cx: 320, cz: 0, y: 80, half: 63, wallTop: 118, thick: 4 };
const CAMPAL_POND = { x: -34, z: 26, r: 6.5 };

function campalHeight(lx, lz) {
  const n = fbm(lx, lz, 34, 300);
  const d = Math.hypot(lx, lz);
  let h = CAMPAL.y + Math.max(0, Math.round(n * 5));
  if (d < 16) h = CAMPAL.y + (d < 8 ? 1 : 0); // flat ruins in the middle
  const edge = Math.min(CAMPAL.half - Math.abs(lx + 0.5), CAMPAL.half - Math.abs(lz + 0.5));
  if (edge < 5) h = Math.min(h, CAMPAL.y + 1);
  return h;
}

const CAMPAL_SPAWNS = (() => {
  const out = [];
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2 + 0.2;
    const r = i % 2 ? 46 : 32;
    out.push({ lx: Math.round(Math.cos(a) * r), lz: Math.round(Math.sin(a) * r) });
  }
  return out;
})();

function campalTree(cx, cz) {
  const cell = 11;
  if (hash(cx, cz, 310) > 0.6) return null;
  const lx = cx * cell + 2 + Math.floor(hash(cx, cz, 311) * (cell - 4));
  const lz = cz * cell + 2 + Math.floor(hash(cx, cz, 312) * (cell - 4));
  if (Math.abs(lx + 0.5) > CAMPAL.half - 6 || Math.abs(lz + 0.5) > CAMPAL.half - 6) return null;
  if (Math.hypot(lx, lz) < 18) return null;
  if (Math.hypot(lx - CAMPAL_POND.x, lz - CAMPAL_POND.z) < CAMPAL_POND.r + 4) return null;
  for (const s of CAMPAL_SPAWNS) if (Math.abs(s.lx - lx) <= 4 && Math.abs(s.lz - lz) <= 4) return null;
  const r = hash(cx, cz, 313);
  const type = r < 0.22 ? "oak" : r < 0.4 ? "birch" : r < 0.6 ? "big" : r < 0.68 ? "azalea" : r < 0.76 ? "cherry"
    : r < 0.84 ? "dark" : r < 0.9 ? "spruce" : r < 0.95 ? "bush" : "fallen";
  const h = treeHeight(type, hash(cx, cz, 314));
  return { x: lx, z: lz, y: campalHeight(lx, lz), type, h };
}

function campalColumn(x, z) {
  const lx = x - CAMPAL.cx, lz = z - CAMPAL.cz;
  const H = CAMPAL.half, segs = [];
  const wx = lx < -H ? -H - lx : lx > H - 1 ? lx - (H - 1) : 0;
  const wz = lz < -H ? -H - lz : lz > H - 1 ? lz - (H - 1) : 0;
  if (wx > CAMPAL.thick || wz > CAMPAL.thick) return segs;
  if (wx > 0 || wz > 0) {
    wallColumn(segs, x, z, Math.max(wx, wz), wx >= wz ? lz : lx, CAMPAL.y - 6, CAMPAL.wallTop, CAMPAL.thick, wx > 0 && wz > 0);
    return segs;
  }
  const h = campalHeight(lx, lz);
  const d = Math.hypot(lx, lz);
  const pd = Math.hypot(lx - CAMPAL_POND.x, lz - CAMPAL_POND.z);
  if (pd < CAMPAL_POND.r) {
    const deep = pd < CAMPAL_POND.r - 2.5 ? 2 : 1;
    groundColumn(segs, CAMPAL.y - 6, h - deep, hash(x, z, 320) < 0.5 ? "clay" : "sand");
    segs.push([h - deep + 1, h, "water"]);
  } else {
    let top = pd < CAMPAL_POND.r + 1.5 ? "sand" : "grass";
    if (top === "grass" && vnoise(lx, lz, 12, 321) > 0.5) top = "podzol";
    if (top === "grass" && hash(lx, lz, 322) < 0.06) top = "coarse";
    if (d < 8) top = hash(lx, lz, 323) < 0.35 ? "msbrick" : hash(lx, lz, 324) < 0.2 ? "cbrick" : "sbrick";
    groundColumn(segs, CAMPAL.y - 6, h, top);
    // ruins: a ring of broken pillars around the plaza
    let used = d < 8;
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      if (Math.round(Math.cos(a) * 12) === lx && Math.round(Math.sin(a) * 12) === lz) {
        const ph = 3 + Math.floor(hash(i, 1, 325) * 7);
        segs.push([h + 1, h + ph, i % 3 === 0 ? "cbrick" : "msbrick"]);
        if (ph > 6) segs.push([h + ph + 1, h + ph + 1, "oakL"]);
        used = true;
      }
    }
    // a broken wall in the plaza
    if (lz === 3 && lx >= -4 && lx <= 1) {
      segs.push([h + 1, h + 1 + ((lx + 4) % 3), "mcobble"]);
      used = true;
    }
    // boulders
    const bx = Math.floor((lx + 200) / 9), bz = Math.floor((lz + 200) / 9);
    if (!used && hash(bx, bz, 330) < 0.18) {
      const ox = bx * 9 - 200 + 4, oz = bz * 9 - 200 + 4;
      const bd = Math.hypot(lx - ox, lz - oz);
      const nearSpawn = CAMPAL_SPAWNS.some((sp) => Math.abs(sp.lx - lx) <= 2 && Math.abs(sp.lz - lz) <= 2);
      if (bd < 1.6 && d > 18 && pd > CAMPAL_POND.r + 2 && !nearSpawn) {
        segs.push([h + 1, h + (bd < 0.5 ? 2 : 1), hash(lx, lz, 331) < 0.5 ? "mcobble" : "andesite"]);
        used = true;
      }
    }
    const trees = gridTrees(lx, lz, 11, campalTree);
    const trunk = addTrees(trees, lx, lz, segs);
    if (!used && !trunk && (top === "grass" || top === "podzol")) {
      const deco = decoration(lx, lz, 340, top === "podzol");
      if (deco) segs.push([h + 1, h + 1, deco]);
    }
  }
  // vines on the walls
  if (lx === -H) hangingColumn(segs, x, z, CAMPAL.wallTop - 1, CAMPAL.y, "vineW");
  else if (lx === H - 1) hangingColumn(segs, x, z, CAMPAL.wallTop - 1, CAMPAL.y, "vineE");
  else if (lz === -H) hangingColumn(segs, x, z, CAMPAL.wallTop - 1, CAMPAL.y, "vineN");
  else if (lz === H - 1) hangingColumn(segs, x, z, CAMPAL.wallTop - 1, CAMPAL.y, "vineS");
  segs.push([CAMPAL.wallTop + 1, CAMPAL.wallTop + 1, "barrier"]);
  return segs;
}

export function campalSpawns() {
  return CAMPAL_SPAWNS.map((s) => ({
    x: CAMPAL.cx + s.lx + 0.5, y: campalHeight(s.lx, s.lz) + 1, z: CAMPAL.cz + s.lz + 0.5,
    facing: { x: CAMPAL.cx, y: CAMPAL.y + 2, z: CAMPAL.cz },
  }));
}

// ------------------------------------------------------------ hunting arena (365x365)
// Breakable terrain over a bedrock floor, regenerated after every hunt.
export const HUNT = {
  cx: 0, cz: -480, size: 365, floor: 60, water: 77, wallTop: 96, clearTop: 150, buildLimit: 140, barrierTop: 319,
};
HUNT.x0 = HUNT.cx - 182;
HUNT.z0 = HUNT.cz - 182;
HUNT.x1 = HUNT.x0 + HUNT.size - 1;
HUNT.z1 = HUNT.z0 + HUNT.size - 1;

const HUNT_RUINS = [
  { x: -95, z: -70, r: 7 }, { x: 110, z: -95, r: 6 }, { x: 80, z: 105, r: 8 }, { x: -120, z: 95, r: 6 },
];
const HUNT_TOWER = { x: 6, z: 4 };

function huntRaw(lx, lz) {
  // lx, lz relative to the centre
  let h = 82 + fbm(lx, lz, 64, 500) * 7 + fbm(lx, lz, 170, 510) * 6;
  const hill = vnoise(lx, lz, 95, 520);
  if (hill > 0.15) h += (hill - 0.15) * 22;
  const lake = vnoise(lx, lz, 75, 530);
  if (lake < -0.42) h -= (-0.42 - lake) * 34;
  return h;
}

export function huntHeight(x, z) {
  const lx = x - HUNT.cx, lz = z - HUNT.cz;
  let h = huntRaw(lx, lz);
  // flat around the ruins and the tower, and down to 80 near the walls
  for (const r of HUNT_RUINS) {
    const d = Math.hypot(lx - r.x, lz - r.z);
    if (d < r.r + 6) {
      const k = Math.max(0, Math.min(1, (d - r.r) / 6));
      h = h * k + Math.max(HUNT.water + 2, huntRaw(r.x, r.z)) * (1 - k);
    }
  }
  const td = Math.max(Math.abs(lx - HUNT_TOWER.x), Math.abs(lz - HUNT_TOWER.z));
  if (td < 12) {
    const k = Math.max(0, Math.min(1, (td - 5) / 7));
    h = h * k + Math.max(HUNT.water + 3, huntRaw(HUNT_TOWER.x, HUNT_TOWER.z)) * (1 - k);
  }
  const edge = Math.min(x - HUNT.x0, HUNT.x1 - x, z - HUNT.z0, HUNT.z1 - z);
  if (edge < 14) {
    const k = smooth(Math.max(0, edge) / 14);
    h = h * k + 80 * (1 - k);
  }
  return Math.max(HUNT.floor + 4, Math.min(112, Math.round(h)));
}

function huntForest(lx, lz) {
  return vnoise(lx, lz, 60, 540);
}

function huntTree(cx, cz) {
  const cell = 7;
  const lx = cx * cell + 1 + Math.floor(hash(cx, cz, 550) * (cell - 2));
  const lz = cz * cell + 1 + Math.floor(hash(cx, cz, 551) * (cell - 2));
  const f = huntForest(lx, lz);
  const chance = f > 0.25 ? 0.75 : f > -0.1 ? 0.25 : 0.06;
  if (hash(cx, cz, 552) > chance) return null;
  const x = lx + HUNT.cx, z = lz + HUNT.cz; // world position
  if (x - HUNT.x0 < 6 || HUNT.x1 - x < 6 || z - HUNT.z0 < 6 || HUNT.z1 - z < 6) return null;
  for (const r of HUNT_RUINS) if (Math.hypot(lx - r.x, lz - r.z) < r.r + 6) return null;
  if (Math.max(Math.abs(lx - HUNT_TOWER.x), Math.abs(lz - HUNT_TOWER.z)) < 10) return null;
  const y = huntHeight(x, z);
  if (y <= HUNT.water + 1 || huntRock(lx, lz)) return null;
  const r = hash(cx, cz, 553);
  const spruceZone = vnoise(lx, lz, 110, 560) > 0.3;
  let type;
  if (spruceZone) type = r < 0.6 ? "spruce" : r < 0.75 ? "mega" : r < 0.85 ? "fallen" : r < 0.93 ? "bush" : "birch";
  else if (f > 0.25) type = r < 0.2 ? "oak" : r < 0.4 ? "big" : r < 0.58 ? "birch" : r < 0.73 ? "dark" : r < 0.8 ? "azalea"
    : r < 0.88 ? "bush" : "fallen";
  else type = r < 0.3 ? "oak" : r < 0.47 ? "big" : r < 0.62 ? "birch" : r < 0.72 ? "cherry" : r < 0.8 ? "azalea"
    : r < 0.93 ? "bush" : "fallen";
  const h = treeHeight(type, hash(cx, cz, 554));
  return { x: lx, z: lz, y, type, h };
}

function huntRock(lx, lz) {
  return vnoise(lx, lz, 26, 570) > 0.62;
}

function huntTreeCell(cx, cz) {
  return huntTree(cx, cz);
}

function huntColumn(x, z) {
  const segs = [];
  const F = HUNT.floor;
  const ox = x < HUNT.x0 ? HUNT.x0 - x : x > HUNT.x1 ? x - HUNT.x1 : 0;
  const oz = z < HUNT.z0 ? HUNT.z0 - z : z > HUNT.z1 ? z - HUNT.z1 : 0;
  const o = Math.max(ox, oz);
  if (o > 2) return segs;
  if (o > 0) {
    // the border: a mossy wall with an invisible barrier above it
    segs.push([F, F, "bedrock"]);
    for (let y = F + 1; y <= HUNT.wallTop; y += 4) {
      const r = hash(x * 3 + y, z * 5, 580);
      segs.push([y, Math.min(HUNT.wallTop, y + 3), r < 0.5 ? "msbrick" : r < 0.6 ? "cbrick" : r < 0.7 ? "moss" : "sbrick"]);
    }
    segs.push([HUNT.wallTop + 1, HUNT.wallTop + 1, o === 1 ? (hash(x, z, 581) < 0.6 ? "oakL" : "azaleaL") : "msbrick"]);
    segs.push([HUNT.wallTop + 2, HUNT.barrierTop, "barrier"]);
    return segs;
  }
  const lx = x - HUNT.cx, lz = z - HUNT.cz;
  const h = huntHeight(x, z);
  const W = HUNT.water;
  segs.push([F, F, "bedrock"]);
  if (h < W) {
    groundColumn(segs, F + 1, h, h < W - 2 ? (hash(x, z, 590) < 0.6 ? "gravel" : "clay") : "sand", h < W - 2 ? "gravel" : "sand", "stone", 2);
    segs.push([h + 1, W, "water"]);
    return segs;
  }
  const forest = huntForest(lx, lz);
  const spruceZone = vnoise(lx, lz, 110, 560) > 0.3;
  const shore = h === W || (h === W + 1 && vnoise(lx, lz, 75, 530) < -0.36);
  let top = shore ? "sand" : "grass";
  let used = false;
  if (huntRock(lx, lz) && h > W + 1) {
    // rocky outcrops
    const extra = Math.floor((vnoise(lx, lz, 26, 570) - 0.62) * 18);
    const r = hash(x, z, 591);
    groundColumn(segs, F + 1, h, r < 0.3 ? "mcobble" : r < 0.6 ? "andesite" : "stone", "stone", "stone");
    if (extra > 0) segs.push([h + 1, h + extra, r < 0.35 ? "mcobble" : r < 0.7 ? "stone" : "andesite"]);
    if (hash(x, z, 592) < 0.3) segs.push([h + Math.max(0, extra) + 1, h + Math.max(0, extra) + 1, "mcarpet"]);
    return segs;
  }
  if (top === "grass") {
    if (spruceZone && vnoise(lx, lz, 14, 593) > 0.25 && hash(x, z, 597) < 0.7) top = "podzol";
    else if (forest > 0.4 && hash(x, z, 594) < 0.25) top = "moss";
    else if (hash(x, z, 595) < 0.03) top = "coarse";
  }
  groundColumn(segs, F + 1, h, top, top === "sand" ? "sand" : "dirt", hash(x, z, 596) < 0.2 ? "andesite" : "stone");
  // ruins: rings of broken pillars
  for (const r of HUNT_RUINS) {
    const d = Math.hypot(lx - r.x, lz - r.z);
    if (d < r.r - 1.5) {
      segs[segs.length - 1] = [h, h, hash(x, z, 600) < 0.4 ? "msbrick" : hash(x, z, 601) < 0.3 ? "cbrick" : "sbrick"];
      used = true;
    }
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2 + r.x;
      if (Math.round(r.x + Math.cos(a) * r.r) === lx && Math.round(r.z + Math.sin(a) * r.r) === lz) {
        const ph = 2 + Math.floor(hash(i, r.x, 602) * 8);
        segs.push([h + 1, h + ph, i % 3 ? "msbrick" : "cbrick"]);
        if (ph > 6) segs.push([h + ph + 1, h + ph + 1, "oakL"]);
        used = true;
      }
    }
  }
  // the old watchtower in the middle: hollow, 7x7, broken at the top
  const tx = lx - HUNT_TOWER.x, tz = lz - HUNT_TOWER.z;
  if (Math.abs(tx) <= 3 && Math.abs(tz) <= 3) {
    used = true;
    const wall = Math.abs(tx) === 3 || Math.abs(tz) === 3;
    segs[segs.length - 1] = [h, h, "sbrick"];
    if (wall) {
      const door = (tz === 3 && Math.abs(tx) <= 0) || (tx === -3 && tz === 0);
      const wh = 14 + Math.floor(hash(tx, tz, 610) * 6);
      const window = Math.abs(tx) === 0 || Math.abs(tz) === 0;
      if (door) segs.push([h + 3, h + wh, "msbrick"]);
      else if (window) segs.push([h + 1, h + 6, "msbrick"], [h + 8, h + wh, "sbrick"]);
      else segs.push([h + 1, h + wh, hash(tx, tz, 611) < 0.5 ? "msbrick" : "sbrick"]);
      if (hash(tx, tz, 612) < 0.5) segs.push([h + wh + 1, h + wh + 1, "oakL"]);
    } else if (Math.abs(tx) <= 2 && Math.abs(tz) <= 2) {
      // a floor half way up (to climb, break or place blocks)
      if (!(tx === 0 && tz === 0)) segs.push([h + 9, h + 9, "spruce"]);
    }
  }
  const trees = gridTrees(lx, lz, 7, huntTreeCell);
  const trunk = addTrees(trees, lx, lz, segs);
  if (!used && !trunk && top !== "sand") {
    const deco = decoration(x, z, 620, forest > 0.2);
    if (deco) segs.push([h + 1, h + 1, deco]);
    else if (hash(x, z, 621) < (forest > 0.2 ? 0.02 : 0.006)) segs.push([h + 1, h + 1, "azaleaL"]);
    else if (hash(x, z, 622) < 0.002) segs.push([h + 1, h + 2, "mcobble"]);
  }
  return segs;
}

// Somewhere safe to stand in the hunting arena: on grass, not under a tree.
export function huntSurface(x, z) {
  const h = huntHeight(x, z);
  const segs = huntColumn(x, z);
  let top = h;
  for (const s of segs) if (s[2] !== "barrier") top = Math.max(top, s[1]);
  const lx = x - HUNT.cx, lz = z - HUNT.cz;
  const safe = h > HUNT.water && top - h <= 1 && !huntRock(lx, lz) && x > HUNT.x0 + 4 && x < HUNT.x1 - 4 && z > HUNT.z0 + 4 && z < HUNT.z1 - 4;
  return { y: safe ? h + 1 : top + 1, safe };
}

// ------------------------------------------------------------ the areas
function box(cx, cz, half, extra) {
  return { x0: cx - half - extra, z0: cz - half - extra, x1: cx + half - 1 + extra, z1: cz + half - 1 + extra };
}

export const AREAS = [
  { id: "lobby", name: "Lobby", ...box(0, 0, 30, 0), bottom: 60, clearTop: 112, column: lobbyColumn },
  { id: "duel0", name: "Arena de emparejamiento 1", ...box(DUEL.centers[0].x, DUEL.centers[0].z, DUEL.half, DUEL.thick), bottom: DUEL.y - 6, clearTop: DUEL.wallTop + 14, column: (x, z) => duelColumn(0, x, z) },
  { id: "duel1", name: "Arena de emparejamiento 2", ...box(DUEL.centers[1].x, DUEL.centers[1].z, DUEL.half, DUEL.thick), bottom: DUEL.y - 6, clearTop: DUEL.wallTop + 14, column: (x, z) => duelColumn(1, x, z) },
  { id: "campal", name: "Campal", ...box(CAMPAL.cx, CAMPAL.cz, CAMPAL.half, CAMPAL.thick), bottom: CAMPAL.y - 6, clearTop: CAMPAL.wallTop + 14, column: campalColumn },
  { id: "hunt", name: "Caza", x0: HUNT.x0 - 2, z0: HUNT.z0 - 2, x1: HUNT.x1 + 2, z1: HUNT.z1 + 2, bottom: HUNT.floor, clearTop: HUNT.clearTop, column: huntColumn },
];

export const AREA = Object.fromEntries(AREAS.map((a) => [a.id, a]));

export function inHunt(x, z) {
  return x >= HUNT.x0 && x <= HUNT.x1 && z >= HUNT.z0 && z <= HUNT.z1;
}

export function insideArea(id, x, z, margin = 0) {
  const a = AREA[id];
  return x >= a.x0 - margin && x <= a.x1 + margin && z >= a.z0 - margin && z <= a.z1 + margin;
}

export { SEED };
