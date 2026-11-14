// Natura PvP: the Campal arena (126x126, always open), remade: a temple on a
// raised plateau in the middle (ramps on four sides), a stream around it with
// four bridges, watchtowers in the corners, ruined arches, tree houses, groves
// and meadows. Lots of height to play with the mace and the wind charges.
import { addTrees, decoration, fbm, gridTrees, groundColumn, hash, smooth, stampIndex, treeHeight, vnoise, walledColumn, WALL_THEMES } from "./core.js";
import { bridge, ruinArch, temple, treehouse, watchtower } from "./structures.js";

export const CAMPAL = { cx: 320, cz: 0, y: 80, half: 63, wallTop: 140, thick: 6, theme: WALL_THEMES.forest };
const Y = CAMPAL.y;
const TOP = Y + 5; // the plateau
const STREAM = { r0: 30.5, r1: 35.5 };

const SITES = [
  ...[[-46, -46], [46, -46], [-46, 46], [46, 46]].map(([x, z]) => ({ x, z, r: 3, s: "watch" })),
  { x: 50, z: 0, r: 6, s: "archZ" }, { x: -50, z: 0, r: 6, s: "archZ" }, { x: 0, z: 50, r: 6, s: "archX" }, { x: 0, z: -50, r: 6, s: "archX" },
  { x: -30, z: 46, r: 6, s: "tree" }, { x: 30, z: -46, r: 6, s: "tree" },
];

const SPAWNS = Array.from({ length: 12 }, (_, i) => {
  const a = ((15 + 30 * i) * Math.PI) / 180;
  return { lx: Math.round(Math.cos(a) * 50), lz: Math.round(Math.sin(a) * 50) };
});

const ramp = (lx, lz) => {
  const ax = Math.abs(lx + 0.5), az = Math.abs(lz + 0.5);
  return (ax <= 3.5 && az >= 11) || (az <= 3.5 && ax >= 11);
};

function baseHeight(lx, lz) {
  let h = Y + Math.max(0, Math.round(fbm(lx, lz, 34, 300) * 6));
  const d = Math.hypot(lx + 0.5, lz + 0.5);
  if (d > 24 && d < 42) h = Y; // flat around the stream
  else if (d >= 42 && d < 48) h = Math.round(Y + (h - Y) * smooth((d - 42) / 6));
  for (const s of SITES) {
    const dd = Math.max(Math.abs(lx - s.x), Math.abs(lz - s.z));
    if (dd < s.r + 6) h = Math.round(Y + (h - Y) * smooth(Math.max(0, (dd - s.r) / 6)));
  }
  const edge = Math.min(CAMPAL.half - Math.abs(lx + 0.5), CAMPAL.half - Math.abs(lz + 0.5));
  if (edge < 6) h = Math.min(h, Y + 1);
  return h;
}

export function campalHeight(lx, lz) {
  const d = Math.hypot(lx + 0.5, lz + 0.5);
  if (d < 15) return TOP;
  if (ramp(lx, lz) && d < 24) return Math.max(baseHeight(lx, lz), Math.round(TOP - ((d - 15) / 9) * (TOP - Y)));
  return baseHeight(lx, lz);
}

const index = stampIndex([
  { x: CAMPAL.cx, z: CAMPAL.cz, y: TOP, stamp: temple() },
  { x: CAMPAL.cx, z: CAMPAL.cz - 33, y: Y, stamp: bridge(13, "z") },
  { x: CAMPAL.cx, z: CAMPAL.cz + 33, y: Y, stamp: bridge(13, "z") },
  { x: CAMPAL.cx - 33, z: CAMPAL.cz, y: Y, stamp: bridge(13, "x") },
  { x: CAMPAL.cx + 33, z: CAMPAL.cz, y: Y, stamp: bridge(13, "x") },
  ...SITES.map((s) => ({
    x: CAMPAL.cx + s.x, z: CAMPAL.cz + s.z, y: Y,
    stamp: s.s === "watch" ? watchtower() : s.s === "tree" ? treehouse() : ruinArch(s.s === "archX" ? "x" : "z"),
  })),
]);

function campalTree(cx, cz) {
  const cell = 9;
  if (hash(cx, cz, 310) > 0.62) return null;
  const lx = cx * cell + 2 + Math.floor(hash(cx, cz, 311) * (cell - 4));
  const lz = cz * cell + 2 + Math.floor(hash(cx, cz, 312) * (cell - 4));
  if (Math.abs(lx + 0.5) > CAMPAL.half - 7 || Math.abs(lz + 0.5) > CAMPAL.half - 7) return null;
  const d = Math.hypot(lx, lz);
  if (d < 22 || (d > STREAM.r0 - 5 && d < STREAM.r1 + 5)) return null;
  if (Math.abs(lx) <= 6 || Math.abs(lz) <= 6) return null; // keep the paths to the bridges clear
  for (const s of SITES) if (Math.max(Math.abs(lx - s.x), Math.abs(lz - s.z)) < s.r + 6) return null;
  for (const s of SPAWNS) if (Math.abs(s.lx - lx) <= 5 && Math.abs(s.lz - lz) <= 5) return null;
  const r = hash(cx, cz, 313);
  const type = r < 0.2 ? "oak" : r < 0.36 ? "birch" : r < 0.56 ? "big" : r < 0.64 ? "azalea" : r < 0.74 ? "cherry"
    : r < 0.84 ? "dark" : r < 0.9 ? "spruce" : r < 0.96 ? "bush" : "fallen";
  return { x: lx, z: lz, y: campalHeight(lx, lz), type, h: treeHeight(type, hash(cx, cz, 314)) };
}

function campalFloor(lx, lz, segs) {
  const x = lx + CAMPAL.cx, z = lz + CAMPAL.cz;
  const h = campalHeight(lx, lz);
  const d = Math.hypot(lx + 0.5, lz + 0.5);
  // the stream around the plateau
  if (d > STREAM.r0 && d < STREAM.r1) {
    groundColumn(segs, Y - 6, Y - 3, hash(x, z, 320) < 0.5 ? "gravel" : "sand", "sand");
    segs.push([Y - 2, Y - 1, "water"]);
    index.apply(x, z, segs);
    return;
  }
  let top = "grass";
  if (d > STREAM.r0 - 1.2 && d < STREAM.r1 + 1.2) top = "sand";
  else if (d < 15 && d > 13.6 && !ramp(lx, lz)) top = "msbrick"; // the edge of the plateau
  else if (ramp(lx, lz) && d < 24) top = (Math.abs(lx + 0.5) <= 1.5 || Math.abs(lz + 0.5) <= 1.5) ? "sbrick" : "path";
  else if (vnoise(lx, lz, 12, 321) > 0.5) top = "podzol";
  else if (hash(lx, lz, 322) < 0.05) top = "coarse";
  // the plateau is held by a wall of bricks
  const cliff = d >= 13.6 && d < 15 && !ramp(lx, lz);
  groundColumn(segs, Y - 6, h, top, cliff ? "msbrick" : "dirt", cliff ? "sbrick" : "stone");
  if (cliff && hash(x, z, 323) < 0.4) segs.push([h + 1, h + 1, "mstwall"]);
  if (ramp(lx, lz) && d < 24 && d > 15 && (Math.abs(lx + 0.5) === 3.5 || Math.abs(lz + 0.5) === 3.5) && Math.round(d) % 4 === 0) {
    segs.push([h + 1, h + 1, "fence"], [h + 2, h + 2, "lantern"]);
  }
  let used = index.apply(x, z, segs) || cliff || (ramp(lx, lz) && d < 24) || d < 15;
  // boulders
  const bx = Math.floor((lx + 200) / 9), bz = Math.floor((lz + 200) / 9);
  if (!used && hash(bx, bz, 330) < 0.15) {
    const ox = bx * 9 - 200 + 4, oz = bz * 9 - 200 + 4;
    const bd = Math.hypot(lx - ox, lz - oz);
    const near = SPAWNS.some((sp) => Math.abs(sp.lx - lx) <= 2 && Math.abs(sp.lz - lz) <= 2) || Math.abs(lx) <= 6 || Math.abs(lz) <= 6;
    if (bd < 1.6 && d > 40 && !near) {
      segs.push([h + 1, h + (bd < 0.5 ? 2 : 1), hash(lx, lz, 331) < 0.5 ? "mcobble" : "andesite"]);
      used = true;
    }
  }
  const trunk = addTrees(gridTrees(lx, lz, 9, campalTree), lx, lz, segs);
  if (!used && !trunk && (top === "grass" || top === "podzol")) {
    const deco = decoration(lx, lz, 340, top === "podzol");
    if (deco) segs.push([h + 1, h + 1, deco]);
  }
}

function campalColumn(x, z) {
  return walledColumn(x, z, CAMPAL, campalFloor);
}

export function campalSpawns() {
  return SPAWNS.map((s) => ({
    x: CAMPAL.cx + s.lx + 0.5, y: campalHeight(s.lx, s.lz) + 1, z: CAMPAL.cz + s.lz + 0.5,
    facing: { x: CAMPAL.cx, y: TOP + 2, z: CAMPAL.cz },
  }));
}

export const CAMPAL_AREA = { id: "campal", name: "Campal", x0: CAMPAL.cx - 69, z0: CAMPAL.cz - 69, x1: CAMPAL.cx + 68, z1: CAMPAL.cz + 68, bottom: CAMPAL.y - 6, clearTop: CAMPAL.wallTop + 14, column: campalColumn };
