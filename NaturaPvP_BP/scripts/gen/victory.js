// Natura PvP: the safe room for the victory of the hunted player. A small
// floating island far from everything, a path and a cozy room with a door (the
// script places it and closes it during the cinematic) and a skylight to look
// at the sun at the end.
import { addTrees, decoration, groundColumn, hash, vnoise } from "./core.js";

const VX = 0, VZ = 700, F = 150; // F: the floor of the room (players stand at F + 1)

export const VICTORY = {
  floor: F,
  room: { x: VX, z: VZ },
  door: { x: VX, y: F + 1, z: VZ + 4 },
  start: { x: VX + 0.5, y: F + 1, z: VZ + 13.5 }, // where the walk starts
  stop: { x: VX + 0.5, y: F + 1, z: VZ + 0.5 }, // the middle of the room
  viewers: { x: VX - 2.5, y: F + 1, z: VZ - 2.5 }, // the others (as spectators) wait inside
};

// (no trees between x+2..+7 / z+5..+19: the cameras of the walk are there)
const TREES = [
  [-13, 13, "big", 9], [12, 11, "cherry", 7], [-12, -9, "oak", 6], [11, -9, "cherry", 6], [0, -15, "cherry", 8],
  [-19, -1, "birch", 7], [18, 2, "birch", 7], [-6, 20, "azalea", 3], [11, 20, "bush", 1], [-17, 8, "azalea", 3],
  [17, -6, "spruce", 8], [-7, -17, "bush", 1],
].map(([x, z, type, h]) => ({ x: VX + x, z: VZ + z, y: F, type, h }));

const POND = { x: -11, z: 2, r: 3.6 };
const GARDEN = { x0: 7, x1: 14, z0: -3, z1: 4 };
const ROWS = ["tulip", "allium", "cornflower", "oxeye", "otulip", "azure", "lily", "dandelion"];

function roomColumn(lx, lz, segs) {
  const ax = Math.abs(lx), az = Math.abs(lz);
  if (ax > 4 || az > 4) return false;
  const wall = ax === 4 || az === 4;
  segs.push([F, F, wall ? "sbrick" : "oplanks"]);
  if (wall) {
    const corner = ax === 4 && az === 4;
    segs.push([F + 1, F + 2, corner ? "oak" : "sbrick"], [F + 3, F + 5, corner ? "oak" : "oplanks"]);
    // windows on the sides, the door opening in the south wall
    if ((ax === 4 && lz === 0) || (lz === -4 && lx === 0)) segs.push([F + 3, F + 3, "glass"]);
    if (lz === 4 && lx === 0) segs.push([F + 1, F + 2, "air"]);
  } else {
    if (lz === -3 && ax <= 3) segs.push([F + 1, F + 2, lx === 0 ? "crafting" : "bookshelf"]);
    if (ax <= 1 && lz >= -1 && lz <= 1) segs.push([F, F, "oplanks"], [F + 1, F + 1, "redCarpet"]);
    if (az === 3 && ax === 3 && lz > 0) segs.push([F + 1, F + 1, "lantern"]);
  }
  // the roof, with a skylight in the middle
  segs.push([F + 6, F + 6, ax <= 1 && az <= 1 ? "glass" : "oplanks"]);
  if (ax === 4 || az === 4) segs.push([F + 7, F + 7, hash(lx, lz, 1401) < 0.5 ? "oakL" : "azaleaL"]);
  return true;
}

// Things around the room: porch, chimney, the arch and the lanterns of the path,
// the pond, the garden and a hedge along the edge. True when the column is done.
function gardenColumn(x, z, lx, lz, r, R, segs) {
  // the porch over the door (supports out of the way of the cameras)
  if (lz === 5 && lx >= -3 && lx <= 3) {
    if (Math.abs(lx) === 3) segs.push([F + 1, F + 3, "oak"]);
    segs.push([F + 4, F + 4, "slab"]);
    if (lx === -2 || lx === 2) segs.push([F + 3, F + 3, "lantern"]);
    return Math.abs(lx) === 3;
  }
  // a brick chimney with smoke
  if (lx === -5 && lz === -2) {
    segs.push([F + 1, F + 9, "brick"], [F + 10, F + 10, "campfire"]);
    return true;
  }
  // the entrance arch over the path
  if (lz === 11 && lx >= -3 && lx <= 2) {
    if (lx === -3 || lx === 2) segs.push([F + 1, F + 5, "msbrick"], [F + 6, F + 6, "chbrick"]);
    else segs.push([F + 6, F + 6, "sbrick"]);
    segs.push([F + 7, F + 7, hash(x, z, 1410) < 0.5 ? "cherryL" : "fazaleaL"]);
    if (lx === -1) segs.push([F + 5, F + 5, "soulLantern"]);
    return lx === -3 || lx === 2;
  }
  // lanterns on posts along the path
  if ((lx === -3 || lx === 2) && (lz === 8 || lz === 14 || lz === 18)) {
    segs.push([F + 1, F + 1, "mstwall"], [F + 2, F + 2, "lantern"]);
    return true;
  }
  // the pond, with lily pads and reeds of grass around
  const pr = Math.hypot(lx - POND.x, lz - POND.z);
  if (pr <= POND.r) {
    segs.push([F - 2, F - 2, "clay"], [F - 1, F, "water"]);
    if (hash(x, z, 1411) < 0.22) segs.push([F + 1, F + 1, "lilypad"]);
    return true;
  }
  if (pr <= POND.r + 1) {
    segs.push([F, F, hash(x, z, 1412) < 0.5 ? "mcobble" : "moss"]);
    if (hash(x, z, 1413) < 0.4) segs.push([F + 1, F + 1, "fern"]);
    return true;
  }
  // a walled garden: a hedge around rows of flowers
  const G = GARDEN;
  if (lx >= G.x0 && lx <= G.x1 && lz >= G.z0 && lz <= G.z1) {
    const edge = lx === G.x0 || lx === G.x1 || lz === G.z0 || lz === G.z1;
    if (edge) {
      if (lx === G.x0 && lz === 0) return true; // the gate
      segs.push([F + 1, F + 1, "hedge"]);
      if ((lx === G.x0 || lx === G.x1) && (lz === G.z0 || lz === G.z1)) segs.push([F + 2, F + 2, "lantern"]);
    } else if (lz === 0) segs.push([F, F, "path"]);
    else segs.push([F + 1, F + 1, ROWS[(lx + 8) % ROWS.length]]);
    return true;
  }
  // a low hedge along the edge of the island, with some lanterns
  if (r > R - 1.3) {
    const h = hash(x, z, 1414);
    if (h < 0.75) segs.push([F + 1, F + 1, h < 0.1 ? "fazaleaL" : "hedge"]);
    if (h < 0.04) segs.push([F + 2, F + 2, "lantern"]);
    return true;
  }
  return false;
}

// Under the island: dripstone, hanging roots and stalactites.
function underside(x, z, bottom, r, R, segs) {
  const h = hash(x, z, 1420);
  segs.push([bottom, bottom + 1, h < 0.5 ? "rdirt" : "dripstone"]);
  if (h < 0.14 && r < R - 2) {
    const len = 3 + Math.floor(hash(x, z, 1421) * (r < R / 2 ? 12 : 6));
    segs.push([bottom - len, bottom - 1, hash(x, z, 1422) < 0.6 ? "dripstone" : "cdeep"]);
  } else if (h > 0.62) segs.push([bottom - 1, bottom - 1, "roots"]);
}

function victoryColumn(x, z) {
  const segs = [];
  const lx = x - VX, lz = z - VZ;
  const r = Math.hypot(lx + 0.5, lz + 0.5 - 2);
  const R = 25 + Math.sin(Math.atan2(lz, lx) * 3) * 1.8 + vnoise(lx, lz, 6, 1402) * 1.5;
  if (r > R) {
    if (r <= R + 1.6) segs.push([F + 1, F + 4, "barrier"]);
    return segs;
  }
  const depth = 5 + Math.floor(Math.pow(1 - r / R, 0.7) * 24 + hash(x, z, 1405) * 2);
  const path = Math.abs(lx + 0.5) <= 1.6 && lz > 4 && lz <= 21;
  groundColumn(segs, F - depth, F, path ? (hash(x, z, 1403) < 0.3 ? "msbrick" : "sbrick") : "grass");
  underside(x, z, F - depth - 2, r, R, segs);
  if (roomColumn(lx, lz, segs)) return segs;
  const done = gardenColumn(x, z, lx, lz, r, R, segs) || path;
  const trunk = addTrees(TREES.filter((t) => Math.abs(t.x - x) <= 6 && Math.abs(t.z - z) <= 6), x, z, segs);
  if (!done && !trunk) {
    const deco = decoration(x, z, 1404, false);
    if (deco) segs.push([F + 1, F + 1, deco]);
    else if (hash(x, z, 1406) < 0.08) segs.push([F + 1, F + 1, "petals"]);
  }
  return segs;
}

export const VICTORY_AREA = { id: "victory", name: "Sala de la victoria", x0: VX - 31, z0: VZ - 28, x1: VX + 30, z1: VZ + 33, bottom: F - 46, clearTop: F + 24, column: victoryColumn };
