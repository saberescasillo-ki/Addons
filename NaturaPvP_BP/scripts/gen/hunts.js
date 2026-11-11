// Natura PvP: the hunting maps (365x365 each). Blocks cannot be broken; the
// structures (towers, hideouts, igloos, tree houses, bridges) are there for
// both sides, each with a chest the script fills when the hunt starts.
import {
  addTrees, decoration, fbm, gridTrees, groundColumn, hash, smooth, snowOver, stampIndex, topOf, treeHeight, vnoise,
} from "./core.js";
import { bridge, cabin, hideout, igloo, stoneTower, treehouse, watchtower } from "./structures.js";

export const HUNT = { size: 365, floor: 60, wallTop: 96, clearTop: 150, barrierTop: 319 };

function frame(m) {
  m.x0 = m.cx - 182;
  m.z0 = m.cz - 182;
  m.x1 = m.x0 + HUNT.size - 1;
  m.z1 = m.z0 + HUNT.size - 1;
  return m;
}

// Flat spots for the structures: the terrain blends to `y` around them.
function blendFlats(h, lx, lz, flats) {
  for (const f of flats) {
    const d = Math.max(Math.abs(lx - f.x), Math.abs(lz - f.z));
    if (d < f.r + 6) {
      const k = smooth(Math.max(0, Math.min(1, (d - f.r) / 6)));
      h = h * k + f.y * (1 - k);
    }
  }
  return h;
}

function edgeBlend(m, x, z, h, to = 80) {
  const edge = Math.min(x - m.x0, m.x1 - x, z - m.z0, m.z1 - z);
  if (edge < 14) {
    const k = smooth(Math.max(0, edge) / 14);
    h = h * k + to * (1 - k);
  }
  return h;
}

// Chooses where the structures go: near the wanted spots, on dry land, apart.
function sites(raw, water, wanted, rock) {
  const out = [];
  for (const w of wanted) {
    let best = null;
    for (let i = 0; i < 400 && !best; i++) {
      const a = i * 2.4, d = Math.sqrt(i) * 2.2;
      const x = Math.round(w.x + Math.cos(a) * d), z = Math.round(w.z + Math.sin(a) * d);
      let ok = raw(x, z) > water + 2 && !(rock && rock(x, z));
      for (const o of out) if (Math.max(Math.abs(o.x - x), Math.abs(o.z - z)) < o.r + w.r + 8) ok = false;
      if (ok) best = { ...w, x, z };
    }
    if (best) out.push({ ...best, y: Math.round(Math.max(water + 2, raw(best.x, best.z))) });
  }
  return out;
}

function border(m, x, z, segs, theme) {
  const ox = x < m.x0 ? m.x0 - x : x > m.x1 ? x - m.x1 : 0;
  const oz = z < m.z0 ? m.z0 - z : z > m.z1 ? z - m.z1 : 0;
  const o = Math.max(ox, oz);
  if (o === 0) return 0;
  if (o > 2) return 2;
  const F = HUNT.floor;
  segs.push([F, F, "bedrock"]);
  for (let y = F + 1; y <= HUNT.wallTop; y += 4) {
    const r = hash(x * 3 + y, z * 5, 580);
    let b = r < 0.5 ? "msbrick" : r < 0.6 ? "cbrick" : r < 0.7 ? "moss" : "sbrick";
    if (theme === "snow" && y > HUNT.wallTop - 12 && r < 0.6) b = "snow";
    if (theme === "canyon" && r < 0.3) b = "andesite";
    segs.push([y, Math.min(HUNT.wallTop, y + 3), b]);
  }
  const crest = theme === "snow" ? "spruceL" : hash(x, z, 581) < 0.6 ? "oakL" : "azaleaL";
  segs.push([HUNT.wallTop + 1, HUNT.wallTop + 1, o === 1 ? crest : "msbrick"]);
  if (theme === "snow" && o === 1) segs.push([HUNT.wallTop + 2, HUNT.wallTop + 2, "snowL"]);
  segs.push([HUNT.wallTop + (theme === "snow" && o === 1 ? 3 : 2), HUNT.barrierTop, "barrier"]);
  return 1;
}

function treeCell(m, cx, cz, cell, pickType) {
  const lx = cx * cell + 1 + Math.floor(hash(cx, cz, m.seed + 50) * (cell - 2));
  const lz = cz * cell + 1 + Math.floor(hash(cx, cz, m.seed + 51) * (cell - 2));
  const x = lx + m.cx, z = lz + m.cz;
  if (x - m.x0 < 6 || m.x1 - x < 6 || z - m.z0 < 6 || m.z1 - z < 6) return null;
  for (const f of m.flats) if (Math.max(Math.abs(lx - f.x), Math.abs(lz - f.z)) < f.r + 6) return null;
  const y = m.height(x, z);
  const type = pickType(lx, lz, y, hash(cx, cz, m.seed + 53), hash(cx, cz, m.seed + 52));
  if (!type) return null;
  return { x: lx, z: lz, y, type, h: treeHeight(type, hash(cx, cz, m.seed + 54)) };
}

// Somewhere safe to stand: on the ground, not in water, not under a tree.
function surfaceOf(m, x, z) {
  const segs = m.column(x, z);
  const t = topOf(segs);
  const h = m.height(x, z);
  const inside = x > m.x0 + 6 && x < m.x1 - 6 && z > m.z0 + 6 && z < m.z1 - 6;
  const safe = inside && t.key !== "water" && t.key !== "ice" && t.y - h <= 1 && h > m.water;
  return { y: (t.key === "snowL" || t.key === "tgrass" || t.key === "fern" || t.y === h + 1 ? h : t.y) + 1, safe };
}

// ------------------------------------------------------------ 1. Bosque Antiguo
const forest = frame({ id: "hunt0", name: "Bosque Antiguo", desc: "bosque con lagos, ruinas y una torre", cx: 0, cz: -480, seed: 500, water: 77 });
{
  const m = forest;
  const raw = (lx, lz) => {
    let h = 82 + fbm(lx, lz, 64, 500) * 7 + fbm(lx, lz, 170, 510) * 6;
    const hill = vnoise(lx, lz, 95, 520);
    if (hill > 0.15) h += (hill - 0.15) * 22;
    const lake = vnoise(lx, lz, 75, 530);
    if (lake < -0.42) h -= (-0.42 - lake) * 34;
    return h;
  };
  const rock = (lx, lz) => vnoise(lx, lz, 26, 570) > 0.62;
  const ruins = [{ x: -95, z: -70, r: 7 }, { x: 110, z: -95, r: 6 }, { x: 80, z: 105, r: 8 }, { x: -120, z: 95, r: 6 }];
  const S = sites(raw, m.water, [
    { x: 6, z: 4, r: 4, s: "stone" },
    { x: -60, z: -120, r: 3, s: "watch" }, { x: 130, z: 20, r: 3, s: "watch" }, { x: -20, z: 140, r: 3, s: "watch" }, { x: -140, z: -10, r: 3, s: "watch" },
    { x: 60, z: -140, r: 4, s: "hide" }, { x: -110, z: 140, r: 4, s: "hide" }, { x: 150, z: 140, r: 4, s: "hide" }, { x: 40, z: 60, r: 4, s: "hide" },
    { x: -40, z: -40, r: 6, s: "tree" }, { x: 100, z: -40, r: 6, s: "tree" }, { x: -80, z: 50, r: 6, s: "tree" },
    ...ruins.map((r) => ({ ...r, s: "ruin" })),
  ], rock);
  m.flats = S;
  const stamps = { stone: stoneTower(), watch: watchtower(), hide: hideout(), tree: treehouse() };
  m.index = stampIndex(S.filter((s) => stamps[s.s]).map((s) => ({ x: s.x + m.cx, z: s.z + m.cz, y: s.y, stamp: stamps[s.s] })));
  m.height = (x, z) => {
    const lx = x - m.cx, lz = z - m.cz;
    const h = edgeBlend(m, x, z, blendFlats(raw(lx, lz), lx, lz, S));
    return Math.max(HUNT.floor + 4, Math.min(112, Math.round(h)));
  };
  const pickType = (lx, lz, y, r, chanceRoll) => {
    const f = vnoise(lx, lz, 60, 540);
    const chance = f > 0.25 ? 0.75 : f > -0.1 ? 0.25 : 0.06;
    if (chanceRoll > chance || y <= m.water + 1 || rock(lx, lz)) return null;
    if (vnoise(lx, lz, 110, 560) > 0.3) return r < 0.6 ? "spruce" : r < 0.75 ? "mega" : r < 0.85 ? "fallen" : r < 0.93 ? "bush" : "birch";
    if (f > 0.25) return r < 0.2 ? "oak" : r < 0.4 ? "big" : r < 0.58 ? "birch" : r < 0.73 ? "dark" : r < 0.8 ? "azalea" : r < 0.88 ? "bush" : "fallen";
    return r < 0.3 ? "oak" : r < 0.47 ? "big" : r < 0.62 ? "birch" : r < 0.72 ? "cherry" : r < 0.8 ? "azalea" : r < 0.93 ? "bush" : "fallen";
  };
  m.column = (x, z) => {
    const segs = [];
    if (border(m, x, z, segs, "forest")) return segs;
    const lx = x - m.cx, lz = z - m.cz;
    const h = m.height(x, z);
    const F = HUNT.floor, W = m.water;
    segs.push([F, F, "bedrock"]);
    if (h < W) {
      groundColumn(segs, F + 1, h, h < W - 2 ? (hash(x, z, 590) < 0.6 ? "gravel" : "clay") : "sand", h < W - 2 ? "gravel" : "sand", "stone", 2);
      segs.push([h + 1, W, "water"]);
      return segs;
    }
    const forestN = vnoise(lx, lz, 60, 540);
    const spruceZone = vnoise(lx, lz, 110, 560) > 0.3;
    const shore = h === W || (h === W + 1 && vnoise(lx, lz, 75, 530) < -0.36);
    let top = shore ? "sand" : "grass";
    if (rock(lx, lz) && h > W + 1) {
      const extra = Math.floor((vnoise(lx, lz, 26, 570) - 0.62) * 18);
      const r = hash(x, z, 591);
      groundColumn(segs, F + 1, h, r < 0.3 ? "mcobble" : r < 0.6 ? "andesite" : "stone", "stone", "stone");
      if (extra > 0) segs.push([h + 1, h + extra, r < 0.35 ? "mcobble" : r < 0.7 ? "stone" : "andesite"]);
      if (hash(x, z, 592) < 0.3) segs.push([h + Math.max(0, extra) + 1, h + Math.max(0, extra) + 1, "mcarpet"]);
      return segs;
    }
    if (top === "grass") {
      if (spruceZone && vnoise(lx, lz, 14, 593) > 0.25 && hash(x, z, 597) < 0.7) top = "podzol";
      else if (forestN > 0.4 && hash(x, z, 594) < 0.25) top = "moss";
      else if (hash(x, z, 595) < 0.03) top = "coarse";
    }
    groundColumn(segs, F + 1, h, top, top === "sand" ? "sand" : "dirt", hash(x, z, 596) < 0.2 ? "andesite" : "stone");
    let used = false;
    for (const r of ruins) {
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
    if (m.index.apply(x, z, segs)) used = true;
    const trunk = addTrees(gridTrees(lx, lz, 7, (cx, cz) => treeCell(m, cx, cz, 7, pickType)), lx, lz, segs);
    if (!used && !trunk && top !== "sand") {
      const deco = decoration(x, z, 620, forestN > 0.2);
      if (deco) segs.push([h + 1, h + 1, deco]);
      else if (hash(x, z, 621) < (forestN > 0.2 ? 0.02 : 0.006)) segs.push([h + 1, h + 1, "azaleaL"]);
    }
    return segs;
  };
  m.chests = () => m.index.markers();
}

// ------------------------------------------------------------ 2. Cañón del Río
const canyon = frame({ id: "hunt1", name: "Cañón del Río", desc: "meseta cortada por un cañón con río y puentes", cx: -560, cz: 0, seed: 800, water: 71 });
{
  const m = canyon;
  const zc = (lx) => 70 * Math.sin(lx / 85) + 25 * Math.sin(lx / 37 + 1);
  const halfW = (lx) => 17 + 5 * Math.sin(lx / 50 + 2);
  const ramps = [-120, 10, 125];
  const bridgesAt = [-60, 70, 160, -165];
  const plateau = (lx, lz) => {
    let h = 92 + fbm(lx, lz, 70, 800) * 5;
    const mesa = vnoise(lx, lz, 40, 810);
    if (mesa > 0.45) h += Math.min(12, (mesa - 0.45) * 40);
    return h;
  };
  const rawC = (lx, lz) => {
    const p = plateau(lx, lz);
    const d = Math.abs(lz - zc(lx));
    const w = halfW(lx);
    let rf = 0;
    for (const r of ramps) rf = Math.max(rf, Math.exp(-(((lx - r) / 16) ** 2)));
    const slope = 6 + 26 * rf;
    const floor = 71;
    if (d >= w + slope) return p;
    if (d <= w) return d < 5 ? 68 : floor + (d > w - 3 ? 1 : 0);
    const t = (d - w) / slope;
    const k = rf > 0.3 ? t : Math.pow(t, 0.35);
    return floor + 1 + (p - floor - 1) * k;
  };
  const bridgeSites = bridgesAt.map((bx) => {
    const cz = Math.round(zc(bx));
    const w = halfW(bx);
    const len = Math.round(2 * (w + 8)) | 1;
    const y = Math.round(Math.max(plateau(bx, cz - len / 2), plateau(bx, cz + len / 2)));
    return { x: bx, z: cz, len, y };
  });
  const S = sites(rawC, m.water + 1, [
    { x: -100, z: -130, r: 3, s: "watch" }, { x: 120, z: -120, r: 3, s: "watch" }, { x: 30, z: 150, r: 3, s: "watch" },
    { x: -150, z: 120, r: 4, s: "hide" }, { x: 150, z: 120, r: 4, s: "hide" }, { x: 0, z: -150, r: 4, s: "hide" },
    { x: -40, z: 110, r: 6, s: "tree" }, { x: 80, z: -60, r: 6, s: "tree" }, { x: -150, z: -40, r: 4, s: "stone" },
  ], (lx, lz) => Math.abs(lz - zc(lx)) < halfW(lx) + 40);
  // the ends of the bridges are flat at deck height
  const ends = bridgeSites.flatMap((b) => [
    { x: b.x, z: b.z - Math.floor(b.len / 2), r: 3, y: b.y }, { x: b.x, z: b.z + Math.floor(b.len / 2), r: 3, y: b.y },
  ]);
  m.flats = [...S, ...ends];
  const stamps = { stone: stoneTower(), watch: watchtower(), hide: hideout("andesite", "moss"), tree: treehouse() };
  m.index = stampIndex([
    ...S.map((s) => ({ x: s.x + m.cx, z: s.z + m.cz, y: s.y, stamp: stamps[s.s] })),
    ...bridgeSites.map((b) => ({ x: b.x + m.cx, z: b.z + m.cz, y: b.y, stamp: bridge(b.len) })),
  ]);
  m.height = (x, z) => {
    const lx = x - m.cx, lz = z - m.cz;
    let h = rawC(lx, lz);
    const inCanyon = Math.abs(lz - zc(lx)) < halfW(lx) + 2;
    if (!inCanyon) h = blendFlats(h, lx, lz, m.flats);
    h = edgeBlend(m, x, z, h, 92);
    return Math.max(HUNT.floor + 4, Math.min(118, Math.round(h)));
  };
  const strata = ["andesite", "tuff", "stone", "calcite", "andesite", "stone", "tuff"];
  const pickType = (lx, lz, y, r, roll) => {
    const d = Math.abs(lz - zc(lx));
    if (d < halfW(lx) + 6) return d < halfW(lx) && d > 6 && roll < 0.12 ? (r < 0.6 ? "bush" : "azalea") : null;
    if (roll > 0.28) return null;
    return r < 0.3 ? "oak" : r < 0.5 ? "big" : r < 0.65 ? "birch" : r < 0.75 ? "dark" : r < 0.88 ? "bush" : "fallen";
  };
  m.column = (x, z) => {
    const segs = [];
    if (border(m, x, z, segs, "canyon")) return segs;
    const lx = x - m.cx, lz = z - m.cz;
    const h = m.height(x, z);
    const F = HUNT.floor;
    segs.push([F, F, "bedrock"]);
    const d = Math.abs(lz - zc(lx));
    if (h < m.water) {
      groundColumn(segs, F + 1, h, hash(x, z, 820) < 0.5 ? "gravel" : "sand", "gravel", "stone", 2);
      segs.push([h + 1, m.water, "water"]);
      return segs;
    }
    // steep cliffs show bands of rock; gentle slopes and the top are grassy
    const steep = Math.max(...[[1, 0], [-1, 0], [0, 1], [0, -1]].map(([a, b]) => Math.abs(rawC(lx + a, lz + b) - rawC(lx, lz))));
    if (steep > 1.6) {
      segs.push([F + 1, h - 8, "stone"]);
      for (let y = h - 7; y <= h; y++) segs.push([y, y, strata[((y % 7) + 7) % 7]]);
      if (hash(x, z, 821) < 0.25) segs.push([h, h, "mcobble"]);
    } else {
      const top = d < halfW(lx) ? (hash(x, z, 822) < 0.3 ? "coarse" : "grass") : hash(x, z, 823) < 0.08 ? "coarse" : "grass";
      groundColumn(segs, F + 1, h, top);
    }
    let used = m.index.apply(x, z, segs);
    if (steep <= 1.6) {
      const trunk = addTrees(gridTrees(lx, lz, 9, (cx, cz) => treeCell(m, cx, cz, 9, pickType)), lx, lz, segs);
      if (!used && !trunk) {
        const deco = decoration(x, z, 830, false);
        if (deco) segs.push([h + 1, h + 1, deco]);
        else if (hash(x, z, 831) < 0.004) segs.push([h + 1, h + 2, "mcobble"]);
      }
    }
    return segs;
  };
  m.chests = () => m.index.markers();
}

// ------------------------------------------------------------ 3. Taiga Nevada
const taiga = frame({ id: "hunt2", name: "Taiga Nevada", desc: "bosque nevado con montañas, lagos helados e iglús", cx: 560, cz: -480, seed: 900, water: 78 });
{
  const m = taiga;
  const peaks = [{ x: -90, z: -70, h: 34, r: 85 }, { x: 100, z: 90, h: 26, r: 70 }];
  const raw = (lx, lz) => {
    let h = 84 + fbm(lx, lz, 60, 900) * 8 + fbm(lx, lz, 150, 910) * 5;
    for (const p of peaks) {
      const d = Math.hypot(lx - p.x, lz - p.z);
      if (d < p.r) h += p.h * (1 - d / p.r) ** 2 * (0.8 + 0.4 * vnoise(lx, lz, 20, 920));
    }
    const lake = vnoise(lx, lz, 70, 930);
    if (lake < -0.4) h -= (-0.4 - lake) * 30;
    return h;
  };
  const rock = (lx, lz) => raw(lx, lz) > 108;
  const S = sites(raw, m.water, [
    { x: 0, z: 0, r: 4, s: "watch" }, { x: -150, z: 60, r: 3, s: "watch" }, { x: 140, z: -100, r: 3, s: "watch" },
    { x: -40, z: 130, r: 5, s: "igloo" }, { x: 60, z: -150, r: 5, s: "igloo" }, { x: 160, z: 30, r: 5, s: "igloo" }, { x: -150, z: -150, r: 5, s: "igloo" },
    { x: 40, z: 40, r: 4, s: "cabin" }, { x: -120, z: 150, r: 4, s: "cabin" }, { x: 150, z: 160, r: 4, s: "cabin" },
  ], rock);
  m.flats = S;
  const stamps = { watch: watchtower("spruce", "planks"), igloo: igloo(), cabin: cabin() };
  m.index = stampIndex(S.map((s) => ({ x: s.x + m.cx, z: s.z + m.cz, y: s.y, stamp: stamps[s.s] })));
  m.height = (x, z) => {
    const lx = x - m.cx, lz = z - m.cz;
    const h = edgeBlend(m, x, z, blendFlats(raw(lx, lz), lx, lz, S), 84);
    return Math.max(HUNT.floor + 4, Math.min(140, Math.round(h)));
  };
  const pickType = (lx, lz, y, r, roll) => {
    if (y <= m.water + 1 || y > 112) return null;
    const dense = vnoise(lx, lz, 50, 940) > -0.2;
    if (roll > (dense ? 0.8 : 0.3)) return null;
    return r < 0.62 ? "spruce" : r < 0.8 ? "mega" : r < 0.88 ? "fallen" : r < 0.95 ? "bush" : "birch";
  };
  m.column = (x, z) => {
    const segs = [];
    if (border(m, x, z, segs, "snow")) return segs;
    const lx = x - m.cx, lz = z - m.cz;
    const h = m.height(x, z);
    const F = HUNT.floor, W = m.water;
    segs.push([F, F, "bedrock"]);
    if (h < W) {
      groundColumn(segs, F + 1, h, "gravel", "gravel", "stone", 2);
      if (h + 1 <= W - 1) segs.push([h + 1, W - 1, "water"]);
      segs.push([W, W, hash(x, z, 950) < 0.12 ? "pice" : "ice"]);
      return segs;
    }
    if (h > 108) {
      // rocky, snowy peaks
      groundColumn(segs, F + 1, h, hash(x, z, 951) < 0.6 ? "snow" : "stone", "stone", "stone");
      if (hash(x, z, 952) < 0.5) segs.push([h + 1, h + 1, "snowL"]);
      return segs;
    }
    const top = vnoise(lx, lz, 16, 953) > 0.35 ? "podzol" : hash(x, z, 954) < 0.1 ? "coarse" : "grass";
    groundColumn(segs, F + 1, h, top);
    const used = m.index.apply(x, z, segs);
    const trunk = addTrees(gridTrees(lx, lz, 7, (cx, cz) => treeCell(m, cx, cz, 7, pickType)), lx, lz, segs);
    if (!used && !trunk && hash(x, z, 955) < 0.12) segs.push([h + 1, h + 1, hash(x, z, 956) < 0.5 ? "fern" : "tgrass"]);
    else if (!used && !trunk && hash(x, z, 957) < 0.004) segs.push([h + 1, h + 2, "mcobble"]);
    if (!used) snowOver(segs);
    return segs;
  };
  m.chests = () => m.index.markers();
}

export const HUNTS = [forest, canyon, taiga];
for (const m of HUNTS) {
  m.surface = (x, z) => surfaceOf(m, x, z);
  m.inside = (x, z) => x >= m.x0 && x <= m.x1 && z >= m.z0 && z <= m.z1;
}
