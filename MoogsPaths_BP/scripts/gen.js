// Moog's Paths - Bedrock port. Core generator (no direct dependency on @minecraft/server so it can be tested).
import {
  PATH_TYPES, STRUCTURE_SETS, BUSH_SETS, FEATURE_SETS, NO_PATH_BIOMES, CROSSABLE_BIOMES, PALETTE, STRUCTURES,
} from "./data.js";

// ---- constants taken from the Java mod (PathFinder / PathRasteriser / StructurePlacer)
const CELL = 4;                 // A* runs on a 4-block grid
const SLOPE_COST = 0.5;
const MAX_NATURAL_STEP = 64;
const HEURISTIC_WEIGHT = 3;
const MAX_WATER_CROSSING = 8;   // cells
const PROXIMITY_FRACTION = 0.1;
const MAX_CUT = 8, MAX_FILL = 8;
const MIN_STRUCTURE_SPACING_SQ = 25;
// ---- Bedrock-specific: paths grow in windows because only loaded chunks can be read
const WINDOW = 10;              // cells around the head searched per step (40 blocks)
const ITER_CAP = 700;

const NO_PATH = new Set(NO_PATH_BIOMES), CROSSABLE = new Set(CROSSABLE_BIOMES);
const WATER = /:(flowing_)?water$/;
const LAVA = /:(flowing_)?lava$/;
const TREE = /_log$|_wood$|leaves|mushroom_stem|mushroom_block|bamboo$|mangrove_roots|cactus|bee_nest|pumpkin$|melon_block/;
const PLANT = /:air$|snow_layer|grass$|fern$|flower|tulip|dandelion|poppy|orchid|allium|bluet|daisy|cornflower|lily|bush|sapling|reeds|sugar_cane|vine|azalea$|dripleaf|moss_carpet|petals|leaf_litter|rose|peony|lilac|torchflower|pitcher|propagule|sweet_berry|:brown_mushroom$|:red_mushroom$|hanging_roots|glow_lichen|cocoa|web$|bamboo_sapling|deadbush|eyeblossom|cactus_flower|firefly/;
const SOIL = /:(grass_block|dirt|coarse_dirt|podzol|mycelium|moss_block|dirt_with_roots|mud|grass_path)$/;
const SAND = /sand$|hardened_clay|terracotta/;

const FEATURES = {
  forest_flowers: { on: SOIL, n: [3, 6], p: ["dandelion", "poppy", "allium", "azure_bluet", "red_tulip", "orange_tulip", "white_tulip", "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley"] },
  flower_default: { on: SOIL, n: [2, 4], p: ["dandelion", "poppy"] },
  flower_plain: { on: SOIL, n: [3, 6], p: ["dandelion", "poppy", "azure_bluet", "oxeye_daisy", "cornflower", "short_grass", "short_grass"] },
  patch_dead_bush: { on: SAND, n: [1, 2], p: ["deadbush"] },
  patch_tall_grass: { on: SOIL, n: [3, 6], p: ["short_grass", "short_grass", "fern"] },
  brown_mushroom_normal: { on: SOIL, n: [1, 2], p: ["brown_mushroom"] },
  red_mushroom_normal: { on: SOIL, n: [1, 2], p: ["red_mushroom"] },
};

export function hash(...nums) {
  let h = 0x9e3779b9;
  for (const n of nums) {
    h ^= n | 0;
    h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
    h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
    h ^= h >>> 16;
  }
  return h >>> 0;
}

export function rng(seed) {
  let a = seed >>> 0;
  const f = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  f.int = (lo, hi) => lo + Math.floor(f() * (hi - lo + 1)); // inclusive
  f.pick = (list) => {                                        // [[value, weight], ...]
    let total = 0;
    for (const e of list) total += e[1];
    let r = f() * total;
    for (const e of list) if ((r -= e[1]) < 0) return e[0];
    return list[list.length - 1][0];
  };
  return f;
}

export const biomeName = (b) => String(b?.id ?? b ?? "").replace(/^minecraft:/, "");
export const biomeAllowsOrigin = (name) => !NO_PATH.has(name) && !CROSSABLE.has(name);

const octile = (ax, az, bx, bz) => {
  const dx = Math.abs(ax - bx), dz = Math.abs(az - bz);
  return Math.max(dx, dz) + 0.41421356 * Math.min(dx, dz);
};

class Heap {
  constructor() { this.a = []; }
  push(n) {
    const a = this.a; let i = a.length; a.push(n);
    while (i > 0) { const p = (i - 1) >> 1; if (a[p].f <= n.f) break; a[i] = a[p]; i = p; }
    a[i] = n;
  }
  pop() {
    const a = this.a, top = a[0], last = a.pop();
    if (a.length) {
      let i = 0;
      for (;;) {
        let c = 2 * i + 1; if (c >= a.length) break;
        if (c + 1 < a.length && a[c + 1].f < a[c].f) c++;
        if (a[c].f >= last.f) break;
        a[i] = a[c]; i = c;
      }
      a[i] = last;
    }
    return top;
  }
}

/**
 * Creates a generator bound to one dimension.
 * api = { BlockPermutation, log(msg) }
 */
export function createGenerator(dim, api) {
  const perms = new Map();
  const warned = new Set();
  function perm(name, states) {
    const key = states ? name + JSON.stringify(states) : name;
    let p = perms.get(key);
    if (p === undefined) {
      try { p = api.BlockPermutation.resolve(name, states); } catch {
        try { p = api.BlockPermutation.resolve(name); } catch { p = null; }
        if (!warned.has(key)) { warned.add(key); api.log?.(`[Moog's Paths] block fallback: ${key}`); }
      }
      perms.set(key, p);
    }
    return p;
  }
  const leafPerm = (name) => /leaves/.test(name) ? perm(name, { persistent_bit: true }) : perm(name);
  const AIR = () => perm("minecraft:air");

  function set(x, y, z, p) {
    if (!p) return false;
    try { dim.setBlockPermutation({ x, y, z }, p); return true; } catch { return false; }
  }
  function idAt(x, y, z) {
    try { return dim.getBlock({ x, y, z })?.typeId; } catch { return undefined; }
  }

  /** Terrain sampler: top terrain block ignoring trees and plants. Returns {y, w(ater), id, tree} or null. */
  function makeSampler() {
    const cache = new Map();
    const sample = (x, z) => {
      const key = x + "," + z;
      let v = cache.get(key);
      if (v !== undefined) return v;
      v = null;
      try {
        let b = dim.getTopmostBlock({ x, z });
        let tree = false;
        for (let i = 0; b && i < 48; i++) {
          const id = b.typeId;
          if (WATER.test(id)) { v = { y: b.y, w: true, id, tree }; break; }
          if (LAVA.test(id)) break;
          if (TREE.test(id)) { tree = true; b = b.below(); continue; }
          if (PLANT.test(id)) { b = b.below(); continue; }
          v = { y: b.y, w: false, id, tree }; break;
        }
      } catch { v = null; }
      cache.set(key, v);
      return v;
    };
    sample.forget = (x, z) => cache.delete(x + "," + z);
    return sample;
  }

  function makeBiomeTest(net) {
    const cache = new Map();
    const allowed = net.biomes ? new Set(net.biomes) : null;
    return (x, y, z) => {
      const key = (x >> 2) + "," + (z >> 2);
      let v = cache.get(key);
      if (v === undefined) {
        try {
          const b = biomeName(dim.getBiome({ x, y, z }));
          v = CROSSABLE.has(b) || (!NO_PATH.has(b) && (!allowed || allowed.has(b)));
        } catch { v = false; }
        cache.set(key, v);
      }
      return v;
    };
  }

  /** Windowed weighted A* (cost function of the Java mod). Returns list of cells from start to the best reachable cell. */
  function* astar(sample, biomeOk, type, sx, sz, gx, gz) {
    const start = sample(sx * CELL, sz * CELL);
    if (!start) return null;
    const key = (x, z) => x + "," + z;
    const g = new Map(), prev = new Map(), waterRun = new Map();
    const open = new Heap();
    g.set(key(sx, sz), 0);
    open.push({ x: sx, z: sz, f: HEURISTIC_WEIGHT * octile(sx, sz, gx, gz), y: start.y, g: 0 });
    let best = { x: sx, z: sz, d: octile(sx, sz, gx, gz) };
    let iter = 0;
    while (open.a.length && iter++ < ITER_CAP) {
      if (iter % 40 === 0) yield;
      const cur = open.pop();
      const ck = key(cur.x, cur.z);
      if (cur.g > g.get(ck) + 1e-6) continue;
      const d = octile(cur.x, cur.z, gx, gz);
      if (d < best.d) best = { x: cur.x, z: cur.z, d };
      if (d === 0) break;
      if (Math.max(Math.abs(cur.x - sx), Math.abs(cur.z - sz)) >= WINDOW) continue; // window border: do not expand
      for (let i = 0; i < 8; i++) {
        const dx = [1, -1, 0, 0, 1, 1, -1, -1][i], dz = [0, 0, 1, -1, 1, -1, 1, -1][i];
        const nx = cur.x + dx, nz = cur.z + dz;
        const s = sample(nx * CELL, nz * CELL);
        if (!s) continue;
        const dh = Math.abs(s.y - cur.y);
        if (dh > MAX_NATURAL_STEP) continue;
        if (!biomeOk(nx * CELL, s.y, nz * CELL)) continue;
        const run = s.w ? (waterRun.get(ck) ?? 0) + 1 : 0;
        if (run > MAX_WATER_CROSSING) continue;
        const step = (i < 4 ? 1 : 1.4142135) * (s.w ? 1 + type.waterCost : 1) + dh * dh * (1 - type.rigidness) * SLOPE_COST;
        const ng = cur.g + step, nk = key(nx, nz);
        if (ng >= (g.get(nk) ?? Infinity)) continue;
        g.set(nk, ng); prev.set(nk, cur); waterRun.set(nk, run);
        open.push({ x: nx, z: nz, f: ng + HEURISTIC_WEIGHT * octile(nx, nz, gx, gz), y: s.y, g: ng });
      }
    }
    const cells = [];
    for (let c = best; c; c = prev.get(key(c.x, c.z))) cells.push([c.x, c.z]);
    cells.reverse();
    while (cells.length > 1 && sample(cells[cells.length - 1][0] * CELL, cells[cells.length - 1][1] * CELL)?.w) cells.pop();
    return cells.length > 1 ? cells : null;
  }

  function bresenham(x0, z0, x1, z1, out) {
    const dx = Math.abs(x1 - x0), dz = Math.abs(z1 - z0), sx = x0 < x1 ? 1 : -1, sz = z0 < z1 ? 1 : -1;
    let err = dx - dz;
    for (;;) {
      const last = out[out.length - 1];
      if (!last || last[0] !== x0 || last[1] !== z0) out.push([x0, z0]);
      if (x0 === x1 && z0 === z1) return;
      const e2 = 2 * err;
      if (e2 > -dz) { err -= dz; x0 += sx; }
      if (e2 < dx) { err += dx; z0 += sz; }
    }
  }

  /** cells -> block waypoints [x, z], with corners rounded (Chaikin) like the mod's straighten/roundCorners pass. */
  function toWaypoints(st, cells) {
    let pts = cells.map(([x, z]) => [x * CELL, z * CELL]);
    pts[0] = [st.x, st.z];
    // drop collinear points, then cut corners twice
    pts = pts.filter((p, i) => i === 0 || i === pts.length - 1 ||
      (p[0] - pts[i - 1][0]) * (pts[i + 1][1] - p[1]) !== (p[1] - pts[i - 1][1]) * (pts[i + 1][0] - p[0]));
    for (let pass = 0; pass < 2; pass++) {
      const out = [pts[0]];
      for (let i = 0; i < pts.length - 1; i++) {
        const [ax, az] = pts[i], [bx, bz] = pts[i + 1];
        if (i > 0) out.push([ax * 0.75 + bx * 0.25, az * 0.75 + bz * 0.25]);
        if (i < pts.length - 2) out.push([ax * 0.25 + bx * 0.75, az * 0.25 + bz * 0.75]);
      }
      out.push(pts[pts.length - 1]);
      pts = out;
    }
    const way = [];
    for (let i = 0; i < pts.length - 1; i++) {
      bresenham(Math.round(pts[i][0]), Math.round(pts[i][1]), Math.round(pts[i + 1][0]), Math.round(pts[i + 1][1]), way);
    }
    return way;
  }

  function placeColumn(sample, type, r, x, z, ty, edge, cols) {
    const s = sample(x, z);
    if (!s) return;
    let p;
    if (s.w) {
      if (!type.water) return;
      const list = edge && type.water.edge.length ? type.water.edge : type.water.surface;
      const name = r.pick(list);
      if (!name) return;
      p = perm(name);
      if (set(x, s.y, z, p)) cols.add(x + "," + z);
      return;
    }
    if (s.y - ty > MAX_CUT || ty - s.y > MAX_FILL) return;
    if (s.tree && TREE.test(idAt(x, s.y + 1, z) ?? "")) return;   // a trunk stands here: leave the tree alone
    const list = edge && type.edge.length ? type.edge : type.surface;
    const name = r.pick(list);
    if (!name) return;                                            // structure_void: keep the terrain
    p = perm(name);
    if (!p) return;
    for (let y = s.y; y > ty; y--) set(x, y, z, AIR());
    for (let y = s.y + 1; y < ty; y++) set(x, y, z, perm(type.fill));
    if (!set(x, ty, z, p)) return;
    cols.add(x + "," + z);
    const top = Math.max(s.y, ty);
    for (let y = top + 1; y <= top + 2; y++) {
      const id = idAt(x, y, z);
      if (id && !/:air$/.test(id) && PLANT.test(id)) set(x, y, z, AIR());
    }
    const below = idAt(x, ty - 1, z);
    if (below && /:(grass_block|mycelium)$/.test(below)) set(x, ty - 1, z, perm("minecraft:dirt"));
    sample.forget(x, z);
  }

  function tryStructure(sample, r, st, set_, wx, wz, px, pz, radius, cols, placed) {
    const entry = set_.entries[0] && (() => {
      let total = 0; for (const e of set_.entries) total += e.w;
      let k = r() * total;
      for (const e of set_.entries) if ((k -= e.w) < 0) return e;
      return set_.entries[0];
    })();
    const S = STRUCTURES[entry.s][entry.rot ? r.int(0, 3) : 0];
    const side = r() < 0.5 ? -1 : 1;
    const off = set_.side > 0 ? Math.max(set_.side, radius + 1 + (Math.max(S.x, S.z) >> 1)) : 0;
    const ax = Math.round(wx + px * off * side), az = Math.round(wz + pz * off * side);
    for (const [qx, qz] of placed) if ((qx - ax) ** 2 + (qz - az) ** 2 < MIN_STRUCTURE_SPACING_SQ) return false;
    const x0 = ax - (S.x >> 1), z0 = az - (S.z >> 1);
    const anchor = sample(ax, az);
    if (!anchor || anchor.w) return false;
    const ground = new Map();
    for (let x = 0; x < S.x; x++) for (let z = 0; z < S.z; z++) {
      const s = sample(x0 + x, z0 + z);
      if (!s || s.w || s.tree) return false;
      if (Math.abs(s.y - anchor.y) > set_.flat) return false;
      if (set_.side > 0 && cols.has((x0 + x) + "," + (z0 + z))) return false;
      ground.set(x + "," + z, s.y);
    }
    const y0 = anchor.y + entry.dy;
    const lowest = new Map();
    for (const [x, y, z] of S.b) { const k = x + "," + z; if (!(lowest.get(k) <= y)) lowest.set(k, y); }
    for (const [k, ly] of lowest) {                       // "beard_thin": support blocks down to the terrain
      const [x, z] = k.split(",").map(Number);
      const gy = ground.get(k);
      for (let y = Math.max(gy + 1, y0 + ly - 5); y < y0 + ly; y++) set(x0 + x, y, z0 + z, perm("minecraft:dirt"));
    }
    for (const [x, y, z, pi] of S.b) {
      const e = PALETTE[pi];
      set(x0 + x, y0 + y, z0 + z, perm(e.n, e.s));
    }
    for (const [x, y, z, text] of S.t ?? []) {
      try { dim.getBlock({ x: x0 + x, y: y0 + y, z: z0 + z })?.getComponent("minecraft:sign")?.setText(text); } catch { /* cosmetic */ }
    }
    for (let x = 0; x < S.x; x++) for (let z = 0; z < S.z; z++) sample.forget(x0 + x, z0 + z);
    placed.push([ax, az]);
    return true;
  }

  function placeFeature(sample, r, name, cx, cz, cols) {
    const f = FEATURES[name.replace(/^minecraft:/, "")];
    if (!f) return;
    const n = r.int(f.n[0], f.n[1]);
    for (let i = 0; i < n; i++) {
      const x = cx + r.int(-2, 2), z = cz + r.int(-2, 2);
      if (cols.has(x + "," + z)) continue;
      const s = sample(x, z);
      if (!s || s.w || !f.on.test(s.id)) continue;
      if (!/:air$/.test(idAt(x, s.y + 1, z) ?? "x")) continue;
      set(x, s.y + 1, z, perm("minecraft:" + f.p[r.int(0, f.p.length - 1)]));
    }
  }

  function placeBush(sample, r, bs, cx, cz, cols) {
    const name = r.pick(bs.blocks);
    const p = leafPerm(name);
    const size = r.int(bs.size[0], bs.size[1]);
    const base = sample(cx, cz);
    if (!base || base.w) return false;
    let any = false;
    for (let x = 0; x < size; x++) for (let z = 0; z < size; z++) for (let y = 0; y < size; y++) {
      if (size > 1 && r() < (y ? 0.5 : 0.2)) continue;
      const bx = cx + x, bz = cz + z;
      if (cols.has(bx + "," + bz)) continue;
      const s = sample(bx, bz);
      if (!s || s.w || Math.abs(s.y - base.y) > 1) continue;
      const id = idAt(bx, s.y + 1 + y, bz);
      if (id && PLANT.test(id)) any = set(bx, s.y + 1 + y, bz, p) || any;
    }
    return any;
  }

  /**
   * Extends one path by one window. `st` is the persisted path state (mutated).
   * Generator: yields to spread the work over ticks. Returns "more" | "done" | "blocked".
   */
  function* extend(st, net, seed) {
    const type = PATH_TYPES[net.type];
    const r = rng(hash(seed, st.x, st.z, st.t, 77));
    const sample = makeSampler();
    const biomeOk = makeBiomeTest(net);
    const prox = Math.max(6, st.len * PROXIMITY_FRACTION);
    const fdiv = (a, b) => Math.floor(a / b);

    const cells = yield* astar(sample, biomeOk, type, fdiv(st.x, CELL), fdiv(st.z, CELL), fdiv(st.gx, CELL), fdiv(st.gz, CELL));
    if (!cells) return "blocked";
    let way = toWaypoints(st, cells);
    // heights: terrain, smoothed by the "carver" strength, max 1 block step between waypoints
    const terr = [];
    for (const [x, z] of way) { const s = sample(x, z); if (!s) break; terr.push(s); }
    way = way.slice(0, terr.length);
    if (way.length < 3) return "blocked";
    const ys = terr.map((s, i) => {
      let sum = 0, n = 0;
      for (let j = Math.max(0, i - 4); j <= Math.min(terr.length - 1, i + 4); j++) { sum += terr[j].y; n++; }
      return Math.round(s.y + (sum / n - s.y) * type.carver);
    });
    ys[0] = st.t > 0 ? st.y : ys[0];
    for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i - 1] - 1, Math.min(ys[i - 1] + 1, ys[i]));
    yield;

    // stop where the path's length budget or the goal is reached
    let end = way.length - 1, finished = false;
    for (let i = 1; i < way.length; i++) {
      if (st.t + i >= st.len * 1.5 || Math.hypot(way[i][0] - st.gx, way[i][1] - st.gz) <= prox) { end = i; finished = true; break; }
    }

    // pass 1: which columns belong to the path (centre distance decides surface vs edge)
    const columns = new Map();
    const radiusAt = [];
    for (let i = 0; i <= end; i++) {
      const [x, z] = way[i], t = st.t + i;
      const toGoal = Math.max(0, Math.hypot(x - st.gx, z - st.gz) - prox);
      const fade = Math.min(1, type.fade[0] > 0 ? (t + 1) / type.fade[0] : 1, type.fade[1] > 0 ? (toGoal + 1) / type.fade[1] : 1);
      const rad = Math.round(st.w * fade);
      radiusAt.push(rad);
      if (r() >= fade) continue;
      for (let dx = -rad; dx <= rad; dx++) for (let dz = -rad; dz <= rad; dz++) {
        const d = Math.abs(dx) + Math.abs(dz);
        if (d > rad) continue;
        const k = (x + dx) + "," + (z + dz), c = columns.get(k);
        const edge = rad > 0 && d === rad;
        if (!c) columns.set(k, { x: x + dx, z: z + dz, y: ys[i], d, edge });
        else if (d < c.d) { c.d = d; c.y = ys[i]; c.edge = c.edge && edge; }
        else c.edge = c.edge && edge;
      }
    }
    // pass 2: pave
    const cols = new Set();
    let n = 0;
    for (const c of columns.values()) {
      placeColumn(sample, type, r, c.x, c.z, c.y, c.edge, cols);
      if (++n % 12 === 0) yield;
    }
    for (const k of columns.keys()) cols.add(k);

    // pass 3: roadside decorations
    const placed = st.ls ? [st.ls] : [];
    st.s ??= {}; st.b ??= {};
    for (let i = 1; i <= end; i++) {
      const [x, z] = way[i], t = st.t + i;
      const a = way[Math.max(0, i - 2)], b = way[Math.min(end, i + 2)];
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const px = -(b[1] - a[1]) / len, pz = (b[0] - a[0]) / len;   // unit vector pointing to the left of the path
      const rad = radiusAt[i];
      for (const name of net.structs) {
        const ss = STRUCTURE_SETS[name];
        const due = ss.mode === "endpoint" ? (st.s[name] === undefined && t >= 2) || (finished && i === end) : t >= (st.s[name] ?? (st.s[name] = r.int(2, ss.spacing)));
        if (!due) continue;
        tryStructure(sample, r, st, ss, x, z, px, pz, rad, cols, placed);
        st.s[name] = ss.mode === "endpoint" ? 1e9 : t + ss.spacing + r.int(0, ss.variance);
      }
      for (const name of net.feats) {
        const fs = FEATURE_SETS[name];
        if (r() >= fs.density) continue;
        const side = fs.side === "left" ? 1 : fs.side === "right" ? -1 : (r() < 0.5 ? 1 : -1);
        const d = rad + 1 + r.int(0, fs.width);
        placeFeature(sample, r, r.pick(fs.features), Math.round(x + px * d * side), Math.round(z + pz * d * side), cols);
      }
      for (const name of net.bushes) {
        const bs = BUSH_SETS[name];
        if (r() >= bs.density || t - (st.b[name] ?? -99) < bs.spacing) continue;
        const side = bs.side === "left" ? 1 : bs.side === "right" ? -1 : (r() < 0.5 ? 1 : -1);
        const d = rad + r.int(bs.off[0], bs.off[1]);
        if (placeBush(sample, r, bs, Math.round(x + px * d * side), Math.round(z + pz * d * side), cols)) st.b[name] = t;
      }
      if (i % 6 === 0) yield;
    }
    if (placed.length) st.ls = placed[placed.length - 1];

    const progressed = Math.hypot(way[end][0] - st.x, way[end][1] - st.z);
    st.x = way[end][0]; st.z = way[end][1]; st.y = ys[end]; st.t += end;
    if (finished) return "done";
    return progressed < 4 ? "blocked" : "more";
  }

  return { extend, makeSampler, perm };
}

/** New path state starting at (x, z). */
export function newPath(key, net, x, y, z, seed) {
  const type = PATH_TYPES[net.type];
  const r = rng(hash(seed, x, z, 1));
  const len = r.int(type.length[0], type.length[1]);
  const angle = r() * Math.PI * 2;
  return {
    k: key, n: net.id, x, y, z, t: 0, len, w: r.int(type.width[0], type.width[1]), f: 0,
    gx: x + Math.round(Math.cos(angle) * len), gz: z + Math.round(Math.sin(angle) * len),
  };
}
