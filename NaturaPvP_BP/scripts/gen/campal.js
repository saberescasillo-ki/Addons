// Natura PvP: the Campal arena (126x126, always open).
import { addTrees, decoration, fbm, gridTrees, groundColumn, hash, treeHeight, vnoise, walledColumn, WALL_THEMES } from "./core.js";

// ------------------------------------------------------------ campal (126x126)
export const CAMPAL = { cx: 320, cz: 0, y: 80, half: 63, wallTop: 118, thick: 4, theme: WALL_THEMES.forest };
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

function campalFloor(lx, lz, segs) {
  const x = lx + CAMPAL.cx, z = lz + CAMPAL.cz;
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
}

function campalColumn(x, z) {
  return walledColumn(x, z, CAMPAL, campalFloor);
}

export function campalSpawns() {
  return CAMPAL_SPAWNS.map((s) => ({
    x: CAMPAL.cx + s.lx + 0.5, y: campalHeight(s.lx, s.lz) + 1, z: CAMPAL.cz + s.lz + 0.5,
    facing: { x: CAMPAL.cx, y: CAMPAL.y + 2, z: CAMPAL.cz },
  }));
}

export const CAMPAL_AREA = { id: "campal", name: "Campal", x0: CAMPAL.cx - 67, z0: CAMPAL.cz - 67, x1: CAMPAL.cx + 66, z1: CAMPAL.cz + 66, bottom: CAMPAL.y - 6, clearTop: CAMPAL.wallTop + 14, column: campalColumn };
