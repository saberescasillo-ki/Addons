// Natura PvP: the Emparejamiento maps (1 vs 1, 64x64 with colossal walls).
// Every map is symmetric (the same cover on both halves) so no side is better.
import { addTrees, decoration, FLOWERS, groundColumn, hash, pick, snowOver, vnoise, walledColumn, WALL_THEMES } from "./core.js";

export const DUEL = { y: 80, half: 32, wallTop: 128, thick: 4 };

// the same point on the other half of the arena
const mirror = (lx, lz) => [-1 - lx, -1 - lz];
function canon(lx, lz) {
  const [mx, mz] = mirror(lx, lz);
  return lx < mx || (lx === mx && lz < mz) ? [lx, lz] : [mx, mz];
}
const both = (list) => list.flatMap((c) => [c, { ...c, x: -1 - c.x, z: -1 - c.z }]);

function rockAt(lx, lz, rocks, keys = ["mcobble", "andesite"]) {
  for (const c of rocks) {
    const dx = lx - c.x, dz = lz - c.z;
    if (Math.abs(dx) <= 1 && Math.abs(dz) <= 1) {
      const h = (dx === 0 && dz === 0 ? 3 : Math.abs(dx) + Math.abs(dz) === 1 ? 2 : 1) + (c.tall ?? 0);
      const [sx, sz] = canon(lx, lz);
      return [1, h, keys[hash(sx, sz, 71) < 0.5 ? 0 : 1]];
    }
  }
  return null;
}

function bushAt(lx, lz, bushes, leaf = "azaleaL", edge = "oakL") {
  for (const c of bushes) {
    const dx = lx - c.x, dz = lz - c.z;
    if (dx >= 0 && dx <= 1 && dz >= 0 && dz <= 1) return [1, 2, leaf];
    if (dx >= -1 && dx <= 2 && dz >= -1 && dz <= 2 && !((dx === -1 || dx === 2) && (dz === -1 || dz === 2))) return [1, 1, edge];
  }
  return null;
}

// ------------------------------------------------------------ 1. Claro del Bosque
const FOREST_ROCKS = both([{ x: -12, z: -7 }, { x: -4, z: -1 }, { x: 20, z: -20 }]);
const FOREST_BUSH = both([{ x: 9, z: -13 }, { x: -22, z: 4 }, { x: -16, z: -18 }]);
function forestFloor(lx, lz, segs) {
  const y = DUEL.y;
  const [sx, sz] = canon(lx, lz);
  groundColumn(segs, y - 6, y, hash(sx, sz, 72) < 0.07 ? "moss" : "grass");
  const cover = rockAt(lx, lz, FOREST_ROCKS) ?? bushAt(lx, lz, FOREST_BUSH);
  if (cover) segs.push([y + cover[0], y + cover[1], cover[2]]);
  else {
    const deco = decoration(sx, sz, 73, false);
    if (deco) segs.push([y + 1, y + 1, deco]);
  }
}

// ------------------------------------------------------------ 2. Ruinas Musgosas
const RUIN_PILLARS = both([{ x: -10, z: -8, h: 6 }, { x: 8, z: -15, h: 4 }, { x: -21, z: -2, h: 8 }, { x: 18, z: -6, h: 3 }, { x: -3, z: -20, h: 5 }]);
const RUIN_WALLS = [
  { x0: -16, x1: -10, z0: 5, z1: 5, h: 2 }, { x0: 6, x1: 6, z0: -12, z1: -7, h: 3 }, { x0: -26, x1: -22, z0: -14, z1: -14, h: 2 },
  { x0: 12, x1: 17, z0: 12, z1: 12, h: 2 },
].flatMap((w) => [w, { x0: -1 - w.x1, x1: -1 - w.x0, z0: -1 - w.z1, z1: -1 - w.z0, h: w.h }]);
function ruinsFloor(lx, lz, segs) {
  const y = DUEL.y;
  const [sx, sz] = canon(lx, lz);
  const n = vnoise(sx, sz, 7, 75);
  const r = hash(sx, sz, 76);
  const top = n > 0.25 ? (r < 0.3 ? "moss" : "grass") : r < 0.35 ? "msbrick" : r < 0.55 ? "sbrick" : r < 0.7 ? "cbrick" : r < 0.85 ? "mcobble" : "moss";
  groundColumn(segs, y - 6, y, top, "dirt", "stone");
  // the dais in the middle, with four pillars
  const cx = lx + 0.5, cz = lz + 0.5;
  if (Math.abs(cx) <= 4.5 && Math.abs(cz) <= 4.5) {
    segs.push([y + 1, y + 1, Math.abs(cx) > 3.5 || Math.abs(cz) > 3.5 ? "chbrick" : "sbrick"]);
    if (Math.abs(cx) === 3.5 && Math.abs(cz) === 3.5) segs.push([y + 2, y + 7, "msbrick"], [y + 8, y + 8, "lantern"]);
    return;
  }
  for (const p of RUIN_PILLARS) {
    if (lx === p.x && lz === p.z) {
      segs.push([y + 1, y + p.h, hash(sx, sz, 77) < 0.5 ? "msbrick" : "cbrick"]);
      if (p.h > 5) segs.push([y + p.h + 1, y + p.h + 1, "azaleaL"]);
      return;
    }
  }
  for (const w of RUIN_WALLS) {
    if (lx >= w.x0 && lx <= w.x1 && lz >= w.z0 && lz <= w.z1) {
      const k = (lx - w.x0) + (lz - w.z0);
      segs.push([y + 1, y + Math.max(1, w.h - (k % 3 === 2 ? 1 : 0)), hash(sx, sz, 78) < 0.5 ? "mcobble" : "msbrick"]);
      return;
    }
  }
  if (top === "grass" || top === "moss") {
    const deco = decoration(sx, sz, 79, true);
    if (deco) segs.push([y + 1, y + 1, deco]);
  } else if (hash(sx, sz, 80) < 0.08) segs.push([y + 1, y + 1, "mcarpet"]);
}

// ------------------------------------------------------------ 3. Cerezal
const CHERRY_TREES = both([{ x: -12, z: -10 }, { x: 13, z: -16 }, { x: -22, z: 10 }, { x: 4, z: -4 }])
  .map((t, i) => ({ x: t.x, z: t.z, y: DUEL.y, type: "cherry", h: 6 + (i >> 1) % 2 }));
const CHERRY_ROCKS = both([{ x: -4, z: -14 }, { x: 20, z: -2 }]);
function cherryFloor(lx, lz, segs) {
  const y = DUEL.y;
  const [sx, sz] = canon(lx, lz);
  groundColumn(segs, y - 6, y, hash(sx, sz, 81) < 0.05 ? "moss" : "grass");
  const rock = rockAt(lx, lz, CHERRY_ROCKS, ["calcite", "andesite"]);
  if (rock) return segs.push([y + rock[0], y + rock[1], rock[2]]);
  const trunk = addTrees(CHERRY_TREES.filter((t) => Math.abs(t.x - lx) <= 6 && Math.abs(t.z - lz) <= 6), lx, lz, segs);
  if (trunk) return;
  const r = hash(sx, sz, 82);
  if (vnoise(sx, sz, 6, 83) > 0.1 && r < 0.55) segs.push([y + 1, y + 1, "petals"]);
  else if (r < 0.25) segs.push([y + 1, y + 1, r < 0.08 ? pick(["allium", "tulip", "lily"], hash(sx, sz, 84)) : "tgrass"]);
}

// ------------------------------------------------------------ 4. Lago Helado
const ICE_SPIKES = both([{ x: -14, z: -9, h: 7 }, { x: 10, z: -18, h: 5 }, { x: -24, z: 2, h: 9 }]);
const ICE_TREES = both([{ x: -18, z: -16 }, { x: 18, z: -10 }, { x: -6, z: -22 }])
  .map((t, i) => ({ x: t.x, z: t.z, y: DUEL.y, type: "spruce", h: 9 + (i >> 1) % 3 }));
function frozenFloor(lx, lz, segs) {
  const y = DUEL.y;
  const [sx, sz] = canon(lx, lz);
  const d = Math.hypot(lx + 0.5, lz + 0.5);
  if (d < 9.5) {
    groundColumn(segs, y - 6, y - 2, "gravel", "gravel");
    segs.push([y - 1, y - 1, "water"], [y, y, d < 4 ? "pice" : "ice"]);
    return;
  }
  groundColumn(segs, y - 6, y, d < 11 ? "snow" : hash(sx, sz, 85) < 0.25 ? "snow" : "grass");
  for (const s of ICE_SPIKES) {
    const dd = Math.hypot(lx - s.x, lz - s.z);
    if (dd < 1.6) {
      segs.push([y + 1, y + Math.round(s.h * (1 - dd / 1.8)), dd < 0.5 ? "pice" : "bice"]);
      return;
    }
  }
  const trunk = addTrees(ICE_TREES.filter((t) => Math.abs(t.x - lx) <= 6 && Math.abs(t.z - lz) <= 6), lx, lz, segs);
  if (!trunk && hash(sx, sz, 86) < 0.05) segs.push([y + 1, y + 1, "fern"]);
  snowOver(segs);
}

// ------------------------------------------------------------ the maps
export const DUELS = [
  { id: "duel0", name: "Claro del Bosque", desc: "hierba, rocas y arbustos", cx: 0, cz: 320, theme: WALL_THEMES.forest, floor: forestFloor },
  { id: "duel1", name: "Ruinas Musgosas", desc: "pilares rotos y un altar en el centro", cx: 160, cz: 320, theme: WALL_THEMES.ruins, floor: ruinsFloor },
  { id: "duel2", name: "Cerezal", desc: "cerezos en flor y pétalos", cx: 320, cz: 320, theme: WALL_THEMES.cherry, floor: cherryFloor },
  { id: "duel3", name: "Lago Helado", desc: "nieve, hielo y picos helados", cx: -160, cz: 320, theme: WALL_THEMES.frozen, floor: frozenFloor },
];
for (const d of DUELS) {
  const cfg = { ...DUEL, cx: d.cx, cz: d.cz, theme: d.theme };
  d.column = (x, z) => walledColumn(x, z, cfg, d.floor);
  d.spawns = () => [
    { x: d.cx + 0.5, y: DUEL.y + 1, z: d.cz - 26 + 0.5, facing: { x: d.cx + 0.5, y: DUEL.y + 1, z: d.cz } },
    { x: d.cx - 0.5, y: DUEL.y + 1, z: d.cz + 25 + 0.5, facing: { x: d.cx, y: DUEL.y + 1, z: d.cz } },
  ];
}
