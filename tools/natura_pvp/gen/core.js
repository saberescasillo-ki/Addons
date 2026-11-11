// Natura PvP: the shared parts of the map generator (pure JS, no Minecraft
// imports: the same code runs in the game, in Node for the previews and to
// write the prebuilt world).
//
// Every area is described column by column: column(x, z) returns the segments
// [y0, y1, blockKey] to fill, in order (later segments overwrite earlier ones;
// "air" carves).

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
  air: { id: "minecraft:air" },
  dark_wood: { id: "minecraft:dark_oak_wood|minecraft:dark_oak_log", s: { pillar_axis: "y" } },
  oak_wood: { id: "minecraft:oak_wood|minecraft:oak_log", s: { pillar_axis: "y" } },
  spruce_wood: { id: "minecraft:spruce_wood|minecraft:spruce_log", s: { pillar_axis: "y" } },
  tuff: { id: "minecraft:tuff|minecraft:andesite" },
  calcite: { id: "minecraft:calcite|minecraft:diorite" },
  planks: { id: "minecraft:spruce_planks|minecraft:planks" },
  oplanks: { id: "minecraft:oak_planks|minecraft:planks" },
  slab: { id: "minecraft:spruce_slab|minecraft:wooden_slab", s: { "minecraft:vertical_half": "bottom" } },
  sfence: { id: "minecraft:spruce_fence|minecraft:oak_fence" },
  hay: { id: "minecraft:hay_block", s: { pillar_axis: "y" } },
  slime: { id: "minecraft:slime" },
  snow: { id: "minecraft:snow" },
  snowL: { id: "minecraft:snow_layer", s: { height: 0 } },
  ice: { id: "minecraft:ice" },
  pice: { id: "minecraft:packed_ice|minecraft:ice" },
  bice: { id: "minecraft:blue_ice|minecraft:packed_ice" },
  petals: { id: "minecraft:pink_petals|minecraft:poppy", s: { growth: 3 } },
  gold: { id: "minecraft:gold_block" },
  glow: { id: "minecraft:glowstone" },
  sealantern: { id: "minecraft:sea_lantern|minecraft:glowstone" },
  mstwall: { id: "minecraft:mossy_stone_brick_wall|minecraft:cobblestone_wall", s: { wall_post_bit: true } },
  ladderN: { id: "minecraft:ladder", s: { facing_direction: 3 } },
  ladderS: { id: "minecraft:ladder", s: { facing_direction: 2 } },
  ladderW: { id: "minecraft:ladder", s: { facing_direction: 5 } },
  ladderE: { id: "minecraft:ladder", s: { facing_direction: 4 } },
  lfern: { id: "minecraft:fern|minecraft:short_grass" },
};

// ------------------------------------------------------------ noise
const SEED = 7349;

export function hash(x, z, s = 0) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(z | 0, 668265263) + Math.imul(s | 0, 982451653)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

export function smooth(t) {
  return t * t * (3 - 2 * t);
}

export function vnoise(x, z, scale, s) {
  const fx = x / scale, fz = z / scale;
  const x0 = Math.floor(fx), z0 = Math.floor(fz);
  const tx = smooth(fx - x0), tz = smooth(fz - z0);
  const a = hash(x0, z0, s), b = hash(x0 + 1, z0, s), c = hash(x0, z0 + 1, s), d = hash(x0 + 1, z0 + 1, s);
  const top = a + (b - a) * tx, bot = c + (d - c) * tx;
  return (top + (bot - top) * tz) * 2 - 1;
}

export function fbm(x, z, scale, s) {
  return vnoise(x, z, scale, s) * 0.6 + vnoise(x, z, scale / 2, s + 1) * 0.28 + vnoise(x, z, scale / 4, s + 2) * 0.12;
}

export const pick = (list, r) => list[Math.min(list.length - 1, Math.floor(r * list.length))];
export const FLOWERS = ["poppy", "dandelion", "cornflower", "oxeye", "azure", "allium", "tulip", "otulip", "lily"];

// ------------------------------------------------------------ trees
// A tree: { x, z, y (ground), type, h }. Its shape is worked out once (and kept)
// as a map "dx,dz" -> leaves and logs of that column, so a column only has to
// look at the trees around it. Types: oak, big (fancy oak with branches and
// roots), birch, spruce, mega (2x2 spruce), dark (2x2 dark oak), azalea,
// cherry, bush and fallen (a log lying on the ground).
const shapes = new Map();
export const TREE_REACH = 6;

export function treeShape(t) {
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
export function gridTrees(x, z, cell, treeAt) {
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
export function addTrees(trees, x, z, segs) {
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

export function groundColumn(segs, bottom, h, top, sub = "dirt", rock = "stone", dirtDepth = 3) {
  if (h - dirtDepth - 1 >= bottom) segs.push([bottom, h - dirtDepth - 1, rock]);
  if (h - 1 >= Math.max(bottom, h - dirtDepth)) segs.push([Math.max(bottom, h - dirtDepth), h - 1, sub]);
  segs.push([h, h, top]);
}

export function decoration(x, z, s, forest) {
  const r = hash(x, z, s);
  const flowerPatch = vnoise(x, z, 9, s + 5) > 0.35;
  if (flowerPatch && r < 0.32) return pick(FLOWERS, hash(Math.floor(x / 5), Math.floor(z / 5), s + 6) * 0.7 + hash(x, z, s + 8) * 0.3);
  if (r < (forest ? 0.42 : 0.36)) return forest && hash(x, z, s + 3) < 0.45 ? "fern" : "tgrass";
  return null;
}

// ------------------------------------------------------------ walls
// Colossal mossy walls. `w` = 1 (inner face) .. thickness (outer face),
// `along` = position along the wall (for the log pillars). The theme changes
// the logs, the crest and adds snow.
export const WALL_THEMES = {
  forest: { logs: ["spruce", "oak"], crest: ["oakL", "azaleaL", "moss"], tower: "spruceL" },
  ruins: { logs: ["dark", "spruce"], crest: ["mcobble", "azaleaL", "moss"], tower: "darkL" },
  cherry: { logs: ["cherry", "oak"], crest: ["cherryL", "cherryL", "moss"], tower: "cherryL" },
  frozen: { logs: ["spruce", "spruce"], crest: ["snow", "spruceL", "snow"], tower: "spruceL", snow: true },
};

export function wallColumn(segs, x, z, w, along, bottom, top, thick, corner, theme = WALL_THEMES.forest) {
  const pillar = w <= 2 && ((along % 9) + 9) % 9 === 0;
  if (pillar) {
    segs.push([bottom, top, w === 1 ? theme.logs[0] : theme.logs[1]]);
    for (let y = bottom + 8; y < top - 2; y += 12) segs.push([y, y, "shroom"]);
  } else {
    // bands of bricks, moss and cracks
    for (let y = bottom; y <= top; y += 4) {
      const r = hash(x * 7 + y, z * 13 - y, 41);
      const mossy = y > top - 14 || r < 0.42;
      let b = r < 0.08 ? "cbrick" : r < 0.14 ? "moss" : mossy ? "msbrick" : r < 0.2 ? "chbrick" : "sbrick";
      if (theme.snow && y > top - 10 && r < 0.5) b = "snow";
      segs.push([y, Math.min(top, y + 3), w === thick && r > 0.8 ? "mcobble" : b]);
    }
  }
  if (corner) {
    // towers in the corners, a bit higher, with a crown of leaves
    segs.push([top + 1, top + 9, (x + z) % 5 === 0 ? "chbrick" : "msbrick"]);
    segs.push([top + 10, top + 12, theme.tower]);
    if (w === 2) segs.push([top + 13, top + 13, theme.tower]);
    if (theme.snow) segs.push([top + (w === 2 ? 14 : 13), top + (w === 2 ? 14 : 13), "snowL"]);
  } else if (w === thick) {
    if (((along % 2) + 2) % 2 === 0) segs.push([top + 1, top + 2, "msbrick"]);
  } else {
    // a green crest of leaves and moss on the top
    const r = hash(x, z, 51);
    segs.push([top + 1, top + 1, r < 0.5 ? theme.crest[0] : r < 0.75 ? theme.crest[1] : theme.crest[2]]);
    if (w === 1 && ((along % 9) + 9) % 9 === 4) segs.push([top + 2, top + 2, "lantern"]);
    else if (r < 0.3) segs.push([top + 2, top + 2, theme.crest[0]]);
    else if (theme.snow) segs.push([top + 2, top + 2, "snowL"]);
  }
}

// Vines and leaves hanging on the inner face of a wall. `dir` = side of the wall.
export function hangingColumn(segs, x, z, top, floor, dir, leaf = "oakL") {
  const r = hash(x, z, 61);
  if (r < 0.45) {
    const len = 6 + Math.floor(hash(x, z, 62) * (top - floor - 14));
    segs.push([top - len, top, dir]);
  }
  if (hash(x, z, 63) < 0.5) segs.push([top - 1 - Math.floor(hash(x, z, 64) * 4), top, hash(x, z, 65) < 0.5 ? leaf : "azaleaL"]);
}

// A walled square arena: interior [-half, half-1], walls `thick` thick. Calls
// inner(lx, lz, segs) for the floor; returns the segments of column (x, z).
export function walledColumn(x, z, cfg, inner) {
  const lx = x - cfg.cx, lz = z - cfg.cz;
  const H = cfg.half, segs = [];
  const wx = lx < -H ? -H - lx : lx > H - 1 ? lx - (H - 1) : 0;
  const wz = lz < -H ? -H - lz : lz > H - 1 ? lz - (H - 1) : 0;
  if (wx > cfg.thick || wz > cfg.thick) return segs;
  const theme = cfg.theme ?? WALL_THEMES.forest;
  if (wx > 0 || wz > 0) {
    wallColumn(segs, x, z, Math.max(wx, wz), wx >= wz ? lz : lx, cfg.y - 6, cfg.wallTop, cfg.thick, wx > 0 && wz > 0, theme);
    return segs;
  }
  inner(lx, lz, segs);
  const leaf = theme.crest[0] === "cherryL" ? "cherryL" : theme.snow ? "spruceL" : "oakL";
  if (lx === -H) hangingColumn(segs, x, z, cfg.wallTop - 1, cfg.y, "vineW", leaf);
  else if (lx === H - 1) hangingColumn(segs, x, z, cfg.wallTop - 1, cfg.y, "vineE", leaf);
  else if (lz === -H) hangingColumn(segs, x, z, cfg.wallTop - 1, cfg.y, "vineN", leaf);
  else if (lz === H - 1) hangingColumn(segs, x, z, cfg.wallTop - 1, cfg.y, "vineS", leaf);
  segs.push([cfg.wallTop + 1, cfg.wallTop + 1, "barrier"]);
  return segs;
}

export function box(cx, cz, half, extra) {
  return { x0: cx - half - extra, z0: cz - half - extra, x1: cx + half - 1 + extra, z1: cz + half - 1 + extra };
}

// The top block of a column (ignoring barriers and air).
export function topOf(segs) {
  let y = -999, key = null;
  for (const [y0, y1, k] of segs) {
    if (k === "barrier") continue;
    if (k === "air") {
      if (y >= y0 && y <= y1) {
        y = y0 - 1;
        key = null;
      }
      continue;
    }
    if (y1 >= y) {
      y = y1;
      key = k;
    }
  }
  return { y, key };
}

// Snow on top of whatever is on top (grass, leaves, stone...).
const SNOWY = new Set(["grass", "podzol", "moss", "coarse", "dirt", "stone", "andesite", "mcobble", "spruceL", "oakL", "birchL", "darkL", "azaleaL", "fazaleaL", "msbrick", "sbrick", "cbrick", "snow", "planks", "slab", "spruce", "oak", "birch", "dark"]);
export function snowOver(segs) {
  const t = topOf(segs);
  if (t.key && SNOWY.has(t.key)) segs.push([t.y + 1, t.y + 1, "snowL"]);
}

// ------------------------------------------------------------ stamps
// Small 3D structures (towers, huts...) built voxel by voxel and turned into
// column segments. Markers (chests, spawn spots) are kept apart: the script
// places the chests (with their loot) when a hunt starts.
export function makeStamp(build) {
  const vox = new Map();
  const markers = [];
  const api = {
    set: (x, y, z, k) => vox.set(`${x},${y},${z}`, k),
    box: (x0, y0, z0, x1, y1, z1, k) => {
      for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x++)
        for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y++)
          for (let z = Math.min(z0, z1); z <= Math.max(z0, z1); z++) vox.set(`${x},${y},${z}`, k);
    },
    marker: (x, y, z, kind, extra = {}) => markers.push({ x, y, z, kind, ...extra }),
  };
  build(api);
  const cols = new Map();
  let r = 0;
  for (const [key, k] of vox) {
    const [x, y, z] = key.split(",").map(Number);
    r = Math.max(r, Math.abs(x), Math.abs(z));
    const ck = `${x},${z}`;
    if (!cols.has(ck)) cols.set(ck, []);
    cols.get(ck).push([y, k]);
  }
  for (const [ck, list] of cols) {
    list.sort((a, b) => a[0] - b[0]);
    const runs = [];
    for (const [y, k] of list) {
      const last = runs[runs.length - 1];
      if (last && last[2] === k && last[1] === y - 1) last[1] = y;
      else runs.push([y, y, k]);
    }
    cols.set(ck, runs);
  }
  return { cols, markers, r };
}

// A spatial index of placed stamps: { x, z, y, stamp }.
export function stampIndex(placed) {
  const grid = new Map();
  for (const p of placed) {
    const r = p.stamp.r;
    for (let gx = Math.floor((p.x - r) / 16); gx <= Math.floor((p.x + r) / 16); gx++)
      for (let gz = Math.floor((p.z - r) / 16); gz <= Math.floor((p.z + r) / 16); gz++) {
        const k = `${gx},${gz}`;
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(p);
      }
  }
  return {
    at(x, z) {
      return grid.get(`${Math.floor(x / 16)},${Math.floor(z / 16)}`) ?? [];
    },
    apply(x, z, segs) {
      let hit = false;
      for (const p of this.at(x, z)) {
        const runs = p.stamp.cols.get(`${x - p.x},${z - p.z}`);
        if (!runs) continue;
        hit = true;
        for (const [y0, y1, k] of runs) segs.push([p.y + y0, p.y + y1, k]);
      }
      return hit;
    },
    markers() {
      return placed.flatMap((p) => p.stamp.markers.map((m) => ({ ...m, x: p.x + m.x, y: p.y + m.y, z: p.z + m.z })));
    },
  };
}
