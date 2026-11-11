// Natura PvP: the lobby. A big floating island with the Árbol del Mundo in the
// middle (a tree ~100 blocks tall that makes the players feel tiny), giant
// roots, three colossal stone gates (one per mode, each with its pad), a ring
// of ancient pillars, a colossal ring wall floating around the island, and a
// parkour inside the hollow trunk.
import { addTrees, colossalWall, decoration, groundColumn, hash, TREE_REACH, vnoise, WALL_THEMES } from "./core.js";

const Y = 100;
const TOP = 198; // top of the trunk
const PI2 = Math.PI * 2;

// ------------------------------------------------------------ the tree
const trunkR = (y) => 11 - 5.5 * Math.pow(Math.max(0, y - Y) / (TOP - Y), 1.3);
const flare = (y) => (y < Y + 8 ? 4.5 * (1 - (y - Y) / 8) ** 2 : 0);
// the trunk is hollow (walls 2.2 thick) up to the top of the parkour
const hollowR = (y) => trunkR(y) - 2.2;
const SHAFT_TOP = 152;
const radiusAt = (y) => trunkR(y) + flare(y);

function trunkTop(d) {
  if (d > radiusAt(Y)) return null;
  let y = Y;
  while (y < TOP && radiusAt(y + 1) >= d) y++;
  return y;
}

const ROOTS = [45, 135, 225, 315].map((deg) => {
  const a = (deg * Math.PI) / 180;
  return { ux: Math.cos(a), uz: Math.sin(a), s0: 9, s1: 34 };
});
const rootShape = (t) => ({ cy: Y - 1 + 15 * (1 - t) ** 1.5, rr: 1.3 + 3 * (1 - t) });

const BRANCHES = Array.from({ length: 7 }, (_, k) => {
  const a = (k / 7) * PI2 + 0.3;
  const y0 = 152 + (k % 3) * 7;
  const L = 30 + Math.floor(hash(k, 1, 1300) * 7);
  return { ux: Math.cos(a), uz: Math.sin(a), y0, L, rise: 12 + (k % 2) * 4, r0: trunkR(y0) - 1 };
});
const BLOBS = [
  { x: 0, y: TOP + 2, z: 0, r: 17, vk: 0.5 },
  ...BRANCHES.flatMap((b, k) => [
    { x: b.ux * b.L, y: b.y0 + b.rise + 3, z: b.uz * b.L, r: 10 + hash(k, 2, 1301) * 2.5, vk: 0.55 },
    { x: b.ux * b.L * 0.62, y: b.y0 + b.rise * 0.62 + 4, z: b.uz * b.L * 0.62, r: 7, vk: 0.55 },
  ]),
];
const leafMix = (x, z) => {
  const r = hash(x, z, 1310);
  return r < 0.45 ? "oakL" : r < 0.7 ? "darkL" : r < 0.88 ? "azaleaL" : "fazaleaL";
};

function treeColumn(x, z, segs) {
  const d = Math.hypot(x + 0.5, z + 0.5);
  let solid = false;
  // trunk with bands of bark, moss and a few lights
  const top = trunkTop(d);
  if (top !== null) {
    solid = true;
    for (let y = Y - 2; y <= top; y += 6) {
      const r = hash(x * 3 + y, z * 7, 1320);
      const outer = d > trunkR(y) - 1.2;
      segs.push([y, Math.min(top, y + 5), outer && r < 0.18 ? "moss" : outer && r < 0.24 ? "oak_wood" : "dark_wood"]);
      if (outer && r > 0.97) segs.push([y + 2, y + 2, "shroom"]);
    }
    // the hollow inside, lit by shroomlights in its walls
    if (d < hollowR(Y + 1)) {
      let yh = Y + 1;
      while (yh < SHAFT_TOP && hollowR(yh + 1) > d) yh++;
      segs.push([Y + 1, yh, "air"]);
    } else if (d < hollowR(Y + 1) + 1.3) {
      for (let y = Y + 6; y < SHAFT_TOP; y += 7) if (hash(x, z + y, 1325) < 0.3) segs.push([y, y, "shroom"]);
    }
    // the door, facing the spawn
    const ax = Math.abs(x + 0.5);
    if (z + 0.5 > 0 && ax <= 1.6 && d >= hollowR(Y + 1) - 1) segs.push([Y + 1, Y + (ax > 1 ? 3 : 4), "air"]);
  }
  // roots
  for (const R of ROOTS) {
    const s = (x + 0.5) * R.ux + (z + 0.5) * R.uz;
    if (s < R.s0 || s > R.s1) continue;
    const perp = Math.abs((x + 0.5) * R.uz - (z + 0.5) * R.ux);
    const { cy, rr } = rootShape((s - R.s0) / (R.s1 - R.s0));
    if (perp > rr) continue;
    const e = Math.sqrt(rr * rr - perp * perp);
    segs.push([Math.max(Y - 3, Math.round(cy - e)), Math.round(cy + e), "dark_wood"]);
    if (hash(x, z, 1321) < 0.3) segs.push([Math.round(cy + e) + 1, Math.round(cy + e) + 1, "mcarpet"]);
    solid = true;
  }
  // branches
  for (const b of BRANCHES) {
    const s = (x + 0.5) * b.ux + (z + 0.5) * b.uz;
    if (s < b.r0 || s > b.L) continue;
    const perp = Math.abs((x + 0.5) * b.uz - (z + 0.5) * b.ux);
    const t = (s - b.r0) / (b.L - b.r0);
    const rr = 3.2 - 1.8 * t;
    if (perp > rr) continue;
    const cy = b.y0 + b.rise * t;
    const e = Math.sqrt(rr * rr - perp * perp) * 0.9;
    segs.push([Math.round(cy - e), Math.round(cy + e), "dark_wood"]);
  }
  // leaves (and curtains of leaves hanging from them)
  for (const B of BLOBS) {
    const dd = Math.hypot(x + 0.5 - B.x, z + 0.5 - B.z);
    if (dd > B.r) continue;
    if (dd > B.r - 1.5 && hash(x, z, 1330 + Math.round(B.y)) < 0.35) continue;
    const e = Math.sqrt(B.r * B.r - dd * dd) * B.vk;
    const y0 = Math.round(B.y - e), y1 = Math.round(B.y + e);
    segs.push([y0, y1, leafMix(x, z)]);
    if (hash(x, z, 1331) < 0.05) segs.push([y0 - 3 - Math.floor(hash(x, z, 1332) * 8), y0 - 1, "azaleaL"]);
  }
  return solid;
}

// ------------------------------------------------------------ gates, pads, pillars
const GATE_R = 40;
const PADS = {
  duel: { a: -Math.PI / 2, block: "diamond" },
  hunt: { a: Math.PI, block: "redstone" },
  campal: { a: 0, block: "emerald" },
};
for (const p of Object.values(PADS)) {
  p.ux = Math.round(Math.cos(p.a));
  p.uz = Math.round(Math.sin(p.a));
  p.x = p.ux * GATE_R;
  p.z = p.uz * GATE_R;
}

function gateColumn(x, z, segs) {
  for (const p of Object.values(PADS)) {
    const along = x * p.ux + z * p.uz;
    const lat = x * -p.uz + z * p.ux;
    const da = Math.abs(along - GATE_R);
    // the pad: 3x3 coloured block, a border and a lantern on each corner
    if (da <= 2 && Math.abs(lat) <= 2) {
      segs.push([Y, Y, da <= 1 && Math.abs(lat) <= 1 ? p.block : "pandesite"]);
      if (da === 2 && Math.abs(lat) === 2) segs.push([Y + 1, Y + 2, "fence"], [Y + 3, Y + 3, "lantern"]);
      return "pad";
    }
    if (da > 2 || Math.abs(lat) > 10) continue;
    const al = Math.abs(lat);
    const k = (y) => (hash(x * 3 + y, z, 1340) < 0.45 ? "msbrick" : hash(x, y, 1341) < 0.2 ? "cbrick" : "chbrick");
    if (al >= 7) {
      // the two pillars, 40 blocks tall, on a plinth
      for (let y = Y + 1; y <= Y + 40; y += 3) segs.push([y, Math.min(Y + 40, y + 2), k(y)]);
      if (al === 10 || da === 2) segs.push([Y + 1, Y + 3, "sbrick"]);
      segs.push([Y + 41, Y + 41, (x + z) % 2 ? "msbrick" : "azaleaL"]);
      return "gate";
    }
    if (da <= 1) {
      // the arch over the pad
      const under = Math.round(Y + 28 + Math.sqrt(49 - lat * lat));
      for (let y = under; y <= Y + 40; y += 3) segs.push([y, Math.min(Y + 40, y + 2), k(y)]);
      if (lat === 0) segs.push([Y + 36, Y + 37, "shroom"]);
      segs.push([Y + 41, Y + 41, hash(x, z, 1342) < 0.5 ? "oakL" : "azaleaL"]);
      if (hash(x, z, 1343) < 0.4) segs.push([under - 2 - Math.floor(hash(x, z, 1344) * 6), under - 1, "azaleaL"]);
    }
  }
  return null;
}

const PILLARS = Array.from({ length: 8 }, (_, k) => {
  const a = ((22.5 + 45 * k) * Math.PI) / 180;
  return { x: Math.cos(a) * 56, z: Math.sin(a) * 56, h: 30 + Math.floor(hash(k, 3, 1350) * 26) };
});

function pillarColumn(x, z, segs) {
  for (const [k, p] of PILLARS.entries()) {
    const d = Math.hypot(x + 0.5 - p.x, z + 0.5 - p.z);
    if (d > 3.3) continue;
    const top = Y + p.h - (d > 2.3 ? Math.floor(hash(x, z, 1351) * 6) : 0) - (k % 3 === 1 ? Math.floor(hash(x, z, 1352) * 10) : 0);
    for (let y = Y - 2; y <= top; y += 4) segs.push([y, Math.min(top, y + 3), hash(x * 5 + y, z, 1353) < 0.5 ? "msbrick" : y % 8 ? "sbrick" : "chbrick"]);
    if (d > 2.3 && hash(x, z, 1354) < 0.4) segs.push([top - 8 - Math.floor(hash(x, z, 1355) * 14), top, "mcobble"]);
    segs.push([top + 1, top + 1, hash(x, z, 1356) < 0.6 ? "azaleaL" : "moss"]);
    return true;
  }
  return false;
}

// ------------------------------------------------------------ the parkour
// Inside the hollow trunk: jumps around its inner wall, upwards, from the blue
// start pad on the floor to the golden one at the top. No checkpoints: if you
// fall, you start again from the bottom.
export const PARKOUR = (() => {
  const blocks = []; // { x, y, z, key }
  const a0 = -Math.PI / 2; // the start pad is on the north side, in front of the door
  const r0 = hollowR(Y + 1) - 2.2;
  const sp = { x: Math.round(Math.cos(a0) * r0), z: Math.round(Math.sin(a0) * r0) };
  for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) blocks.push({ x: sp.x + dx, y: Y, z: sp.z + dz, key: dx || dz ? "pandesite" : "lapis" });
  const mats = ["moss", "dark_wood", "azaleaL", "msbrick", "mcobble", "oak_wood", "shroom"];
  let a = a0, y = Y, prev = sp;
  let finish = null;
  const N = 56;
  const used = []; // { x, y, z } of the platforms so far
  // no platform right above another (3 blocks of room for the head)
  const free = (px, py, pz) => !used.some((u) => u.x === px && u.z === pz && Math.abs(u.y - py) <= 3)
    && !(Math.abs(px - sp.x) <= 1 && Math.abs(pz - sp.z) <= 1 && py - Y <= 3);
  for (let i = 0; i < N; i++) {
    const up = i % 5 !== 4;
    y += up ? 1 : 0;
    const r = hollowR(y + 4) - 1.3; // room for the head under the narrowing wall
    let best = null;
    for (const [lo, hi] of up ? [[2.9, 3.6], [2.6, 3.7]] : [[3.3, 4.2], [3.0, 4.3]]) {
      for (let step = 1.5; step <= 8 && !best; step += 0.05) {
        const px = Math.round(Math.cos(a + step / r) * r), pz = Math.round(Math.sin(a + step / r) * r);
        const dd = Math.hypot(px - prev.x, pz - prev.z);
        if (dd >= lo && dd <= hi && free(px, y, pz)) best = { px, pz, step };
      }
      if (best) break;
    }
    if (!best) throw new Error(`parkour: no hay sitio para el salto ${i}`);
    a += best.step / r;
    const { px, pz } = best;
    prev = { x: px, z: pz };
    used.push({ x: px, y, z: pz });
    if (i === N - 1) {
      for (const [dx, dz] of [[0, 0], [1, 0], [0, 1], [1, 1]]) blocks.push({ x: px + dx, y, z: pz + dz, key: "gold" });
      blocks.push({ x: px, y: y + 1, z: pz + 1, key: "lantern" });
      finish = { x: px + 0.5, y: y + 1, z: pz + 0.5 };
    } else blocks.push({ x: px, y, z: pz, key: mats[i % mats.length] });
  }
  const start = { x: sp.x + 0.5, y: Y + 1, z: sp.z + 0.5 };
  return { start, startPad: sp, finish, blocks, checkpoints: [start] };
})();
const PK = new Map();
for (const b of PARKOUR.blocks) {
  const k = `${b.x},${b.z}`;
  if (!PK.has(k)) PK.set(k, []);
  PK.get(k).push([b.y, b.y, b.key]);
}

// ------------------------------------------------------------ the ring wall
// A colossal wall in a ring around the island, floating in the void: its
// arcade faces the island; eight towers. It hides everything beyond it.
const RING = { r: 82, thick: 6, top: 196 };
function ringColumn(x, z, segs) {
  const r = Math.hypot(x + 0.5, z + 0.5);
  if (r < RING.r || r >= RING.r + RING.thick) return false;
  const w = Math.floor(r - RING.r) + 1;
  const ang = Math.atan2(z + 0.5, x + 0.5);
  const along = (ang + Math.PI) * RING.r;
  const seg = (Math.PI * 2 * RING.r) / 8;
  const m = ((along % seg) + seg) % seg;
  const tower = m < 7 || m > seg - 7;
  // the foundation hangs below the island level, like a cliff
  const bottom = Y - 26 - Math.floor(hash(x, z, 1390) * 14) - (w > 2 && w < 5 ? 10 : 0);
  colossalWall(segs, x, z, w, along, bottom, Y, RING.top, RING.thick, WALL_THEMES.forest, tower);
  return true;
}

// ------------------------------------------------------------ the island
const islandR = (x, z) => {
  const a = Math.atan2(z, x);
  return 66 + Math.sin(a * 3 + 0.7) * 3 + Math.sin(a * 7 + 2.1) * 2 + vnoise(Math.cos(a) * 60, Math.sin(a) * 60, 12, 1360) * 1.5;
};
const POND = { x: -24, z: 30, r: 5.5 };

const pathDirs = [[0, -1], [-1, 0], [1, 0]];
function onPath(x, z) {
  for (const [ux, uz] of pathDirs) {
    const along = x * ux + z * uz, lat = Math.abs(x * -uz + z * ux);
    if (along > 20 && along < GATE_R + 6 && lat <= 2.5) return true;
  }
  return false;
}

const DECO_TREES = (() => {
  const out = [];
  for (let i = 0; i < 200 && out.length < 26; i++) {
    const a = hash(i, 4, 1370) * PI2, r = 28 + hash(i, 5, 1371) * 30;
    const x = Math.round(Math.cos(a) * r), z = Math.round(Math.sin(a) * r);
    if (onPath(x, z)) continue;
    if (Object.values(PADS).some((p) => Math.hypot(x - p.x, z - p.z) < 13)) continue;
    if (PILLARS.some((p) => Math.hypot(x - p.x, z - p.z) < 8)) continue;
    if (ROOTS.some((R) => Math.abs(x * R.uz - z * R.ux) < 6 && x * R.ux + z * R.uz < 40)) continue;
    if (Math.hypot(x - POND.x, z - POND.z) < POND.r + 5) continue;
    if (Math.hypot(x, z) > islandR(x, z) - 6) continue;
    if (out.some((t) => Math.hypot(t.x - x, t.z - z) < 9)) continue;
    const t = hash(i, 6, 1372);
    const type = t < 0.25 ? "big" : t < 0.45 ? "cherry" : t < 0.6 ? "birch" : t < 0.72 ? "azalea" : t < 0.85 ? "bush" : "oak";
    out.push({ x, z, y: Y, type, h: type === "big" ? 10 : type === "cherry" ? 6 : type === "birch" ? 8 : type === "azalea" ? 3 : type === "bush" ? 1 : 6 });
  }
  return out;
})();

function lobbyColumn(x, z) {
  const segs = [];
  const r = Math.hypot(x + 0.5, z + 0.5);
  const R = islandR(x, z);
  if (ringColumn(x, z, segs)) return segs;
  if (r > R) {
    if (r <= R + 1.6) segs.push([Y + 1, Y + 6, "barrier"]);
    return segs;
  }
  // the island: deep in the middle, with rock hanging below
  let depth = 8 + Math.floor((1 - Math.pow(r / R, 1.3)) * 55 + vnoise(x, z, 6, 1361) * 6);
  if (hash(x, z, 1362) < 0.08) depth += 3 + Math.floor(hash(x, z, 1363) * 10);
  const edge = R - r < 1.5;
  let top = "grass";
  if (!edge && hash(x, z, 1364) < 0.08) top = hash(x, z, 1365) < 0.5 ? "moss" : "coarse";
  if (onPath(x, z)) top = "path";
  const plaza = r >= 12 && r <= 24.5;
  if (plaza) top = hash(x, z, 1366) < 0.3 ? "msbrick" : hash(x, z, 1367) < 0.15 ? "cbrick" : "sbrick";
  const rock = (y) => (y < Y - 30 ? "tuff" : hash(x, y, 1368) < 0.3 ? "andesite" : "stone");
  groundColumn(segs, Y - depth, Y, top, "dirt", rock(Y - depth));
  const pond = Math.hypot(x + 0.5 - POND.x, z + 0.5 - POND.z);
  if (pond < POND.r) {
    segs.push([Y - 2, Y - 2, "clay"], [Y - 1, Y, "water"]);
    return segs;
  }
  if (pond < POND.r + 1) segs[segs.length - 1] = [Y, Y, "sand"];
  const solid = treeColumn(x, z, segs);
  const gate = gateColumn(x, z, segs);
  const pk = PK.get(`${x},${z}`);
  if (pk) segs.push(...pk);
  if (solid || gate || pillarColumn(x, z, segs)) return segs;
  // lanterns around the plaza
  if (r > 24 && r < 25.2) {
    const a = Math.atan2(z + 0.5, x + 0.5);
    const k = Math.round((a / PI2) * 16);
    if (k % 4 !== 0 && Math.abs(a - (k * PI2) / 16) * r < 0.6) segs.push([Y + 1, Y + 3, "fence"], [Y + 4, Y + 4, "lantern"]);
  }
  if (plaza || top === "path") return segs;
  const trunk = addTrees(DECO_TREES.filter((t) => Math.abs(t.x - x) <= TREE_REACH && Math.abs(t.z - z) <= TREE_REACH), x, z, segs);
  if (!trunk && !edge && (top === "grass" || top === "moss")) {
    const deco = decoration(x, z, 1380, r < 40);
    if (deco) segs.push([Y + 1, Y + 1, deco]);
    else if (hash(x, z, 1381) < 0.02) segs.push([Y + 1, Y + 1, "azaleaL"]);
  }
  return segs;
}

export const LOBBY = {
  cx: 0, cz: 0, y: Y, radius: 74, ring: 82,
  spawn: { x: 0.5, y: Y + 1, z: 21.5 },
  look: { x: 0.5, y: Y + 45, z: 0.5 },
  pads: Object.fromEntries(Object.entries(PADS).map(([k, p]) => [k, { x: p.x, z: p.z, block: p.block }])),
  marker: { x: 0, y: Y, z: 0, block: "minecraft:dark_oak_wood" },
  parkour: PARKOUR,
};

export const LOBBY_AREA = { id: "lobby", name: "Lobby", x0: -90, z0: -90, x1: 89, z1: 89, bottom: Y - 80, clearTop: 225, column: lobbyColumn };
