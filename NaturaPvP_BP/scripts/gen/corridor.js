// Natura PvP: the secret corridor. A hidden pit in a corner of the lobby takes
// the player here for 10 seconds: a colossal hall of deepslate, ~100 blocks
// tall and so long (and foggy) that its end can never be seen. Pilasters with
// lights, giant statues in niches, a vault with ribs and gold, chains with
// soul lanterns and braziers along the floor.
import { hash } from "./core.js";

const CX = 0, CZ = -1200, F = 80, LEN = 520, HALF = 14, THICK = 6, TOPW = F + 100;
const BAY = 24; // pilaster every 24 blocks; a statue in a niche between them

export const CORRIDOR = {
  floor: F,
  length: LEN,
  // where the player appears, looking down the corridor (towards -z)
  spawn: { x: CX + 0.5, y: F + 1, z: CZ - 2.5 },
  look: { x: CX + 0.5, y: F + 8, z: CZ - 60 },
  seconds: 10,
};

const vaultY = (ai) => F + 70 + Math.round(26 * Math.sqrt(Math.max(0, 1 - (ai / HALF) ** 2)));

// A giant statue: a robed guardian holding a sword, point down. u = position
// along the niche (-4..4), h = height above the plinth; d = depth (0 = front).
function statue(u, h, d) {
  const au = Math.abs(u);
  if (h < 0) return null;
  if (h <= 4) return au <= 4.5 ? (h === 4 ? "gilded" : "chdeep") : null; // plinth
  const s = (h - 5) / 1.6; // the figure, 1.6 times taller than wide
  if (d === 0) {
    // the sword in front: blade, crossguard and pommel of gold
    if (au < 0.6 && s >= 1 && s <= 15) return "pdeep";
    if (au < 1.6 && s > 15 && s <= 16.2) return "gold";
    if (au < 0.6 && s > 16.2 && s <= 18) return "gilded";
    if (au < 1.6 && s > 17 && s <= 18.4) return "qblock"; // the hands on the hilt
    return null;
  }
  if (s <= 17 && au <= 3.4 - s * 0.08) return hash(Math.round(u), h, 1500 + d) < 0.15 ? "qblock" : "calcite"; // the robe
  if (s > 17 && s <= 21 && au <= 2.2) return "qblock"; // the chest
  if (s > 19.5 && s <= 21.5 && au <= 4.4) return "qpillar"; // the shoulders
  if (s > 21.5 && s <= 24.5 && au <= 1.4) return d === 1 && s > 22.6 && s < 23.6 && au > 0.4 ? "vfrog" : "calcite"; // the head, glowing eyes
  if (s > 24.5 && s <= 25.6 && au <= 1.6 && Math.round(u) % 2 === 0) return "gold"; // the crown
  return null;
}

function wallColumn(x, z, ai, lz, segs) {
  const w = ai - HALF + 1; // 1 = inner face
  const m = ((lz % BAY) + BAY) % BAY;
  for (let y = F - 4; y <= TOPW; y += 8) {
    const r = hash(x * 3 + y, z, 1510);
    segs.push([y, Math.min(TOPW, y + 7), w === 1 && r < 0.12 ? "cdtiles" : (y / 8) % 2 ? "dbricks" : "dtiles"]);
  }
  if (w === 1) segs.push([F, F + 2, "chdeep"], [F + 60, F + 60, "chdeep"], [F + 61, F + 61, "gilded"], [F + 80, F + 80, "chdeep"]);
  // the niche with its statue
  const u = m - 13.5;
  if (Math.abs(u) <= 4.5 && w <= 4) {
    const top = F + 56 + Math.round(Math.sqrt(Math.max(0, 20.25 - u * u)) * 1.6);
    if (w === 4) return segs.push([F + 3, top, "pbbricks"]); // a dark back, behind the statue
    segs.push([F + 3, top, "air"]);
    if (w === 1) segs.push([top, top, "gilded"]);
    for (let y = F + 3; y < top; y++) {
      const b = statue(u, y - F - 3, w - 1);
      if (b) segs.push([y, y, b]);
    }
    if (w === 1 && Math.abs(u) < 0.6) segs.push([F + 58, top - 1, "chain"], [F + 57, F + 57, "soulLantern"]);
  }
}

function interiorColumn(x, z, lx, ai, lz, segs) {
  const m = ((lz % BAY) + BAY) % BAY;
  const rib = m <= 3;
  segs.push([F - 4, F - 1, "deep"]);
  let floor = ai <= 2 ? "pbbricks" : ai === 3 ? "gilded" : (lx + lz) & 1 ? "dtiles" : "pdeep";
  if (ai > 3 && hash(x, z, 1520) < 0.07) floor = "cdtiles";
  if (rib && ai > 3) floor = "chdeep";
  if (ai === 8 && lz % 6 === 0) floor = "sealantern";
  segs.push([F, F, floor]);
  const vy = vaultY(ai);
  // the pilasters (with bands of light) and their capitals
  if (rib && ai >= 12) {
    for (let y = F + 1; y < vy; y += 16) segs.push([y, Math.min(vy - 1, y + 14), "dbricks"], [y + 15, y + 15, "pfrog"]);
    segs.push([F + 1, F + 3, "chdeep"], [F + 64, F + 66, "chdeep"], [F + 67, F + 67, "gilded"]);
  }
  // the vault: solid above, ribs below it, gold along the top
  segs.push([vy, TOPW, ai <= 1 ? "gilded" : "dbricks"]);
  if (rib) segs.push([vy - 2, vy - 1, "chdeep"]);
  // chains hanging from the vault in the middle of every bay
  if (lx === 0 && m === 13) segs.push([F + 50, vy - 1, "chain"], [F + 49, F + 49, "soulLantern"]);
  // braziers on the floor and soul lanterns at the feet of the statues
  if (ai === 7 && m === 13) segs.push([F + 1, F + 1, "chdeep"], [F + 2, F + 2, "campfire"]);
  if (ai === 13 && (m === 9 || m === 18)) segs.push([F + 1, F + 1, "chdeep"], [F + 2, F + 2, "soulLanternF"]);
}

// the sealed gate behind the player and the far end (never reached)
function endColumn(ai, lz, segs) {
  for (let y = F - 4; y <= TOPW; y += 8) segs.push([y, Math.min(TOPW, y + 7), "dbricks"]);
  if (lz !== -1 || ai > HALF - 1) return;
  const arch = F + 34 + Math.round(Math.sqrt(Math.max(0, 81 - ai * ai)) * 1.4);
  if (ai <= 9) {
    for (let y = F + 1; y <= arch; y++) {
      const frame = ai >= 8 || y >= arch - 1;
      segs.push([y, y, frame ? "gold" : (y + ai) % 6 === 0 ? "chdeep" : "pbbricks"]);
    }
  }
}

function corridorColumn(x, z) {
  const segs = [];
  const lx = x - CX, lz = CZ - z;
  const ai = Math.floor(Math.abs(lx + 0.5));
  if (ai >= HALF + THICK) return segs;
  if (lz < 0 || lz > LEN) {
    endColumn(ai, lz, segs);
    return segs;
  }
  if (ai >= HALF) wallColumn(x, z, ai, lz, segs);
  else interiorColumn(x, z, lx, ai, lz, segs);
  return segs;
}

export const CORRIDOR_AREA = {
  id: "corridor", name: "Pasillo secreto",
  x0: CX - HALF - THICK, z0: CZ - LEN - 6, x1: CX + HALF + THICK - 1, z1: CZ + 6,
  bottom: F - 4, clearTop: TOPW + 2, column: corridorColumn,
};
