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

const TREES = [[-9, 9, "big", 9], [9, 10, "birch", 7], [-10, -6, "oak", 6], [10, -7, "cherry", 6], [-6, 15, "azalea", 3], [7, 16, "bush", 1]]
  .map(([x, z, type, h]) => ({ x: VX + x, z: VZ + z, y: F, type, h }));

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

function victoryColumn(x, z) {
  const segs = [];
  const lx = x - VX, lz = z - VZ;
  const r = Math.hypot(lx + 0.5, lz + 0.5 - 3);
  const R = 17 + Math.sin(Math.atan2(lz, lx) * 3) * 1.5 + vnoise(lx, lz, 6, 1402);
  if (r > R) {
    if (r <= R + 1.6) segs.push([F + 1, F + 4, "barrier"]);
    return segs;
  }
  const depth = 4 + Math.floor((1 - r / R) * 12);
  const path = Math.abs(lx + 0.5) <= 1.6 && lz > 4 && lz <= 16;
  groundColumn(segs, F - depth, F, path ? (hash(x, z, 1403) < 0.3 ? "msbrick" : "sbrick") : "grass");
  if (roomColumn(lx, lz, segs) || path) return segs;
  const trunk = addTrees(TREES.filter((t) => Math.abs(t.x - x) <= 6 && Math.abs(t.z - z) <= 6), x, z, segs);
  if (!trunk) {
    const deco = decoration(x, z, 1404, false);
    if (deco) segs.push([F + 1, F + 1, deco]);
  }
  return segs;
}

export const VICTORY_AREA = { id: "victory", name: "Sala de la victoria", x0: VX - 22, z0: VZ - 20, x1: VX + 21, z1: VZ + 26, bottom: F - 20, clearTop: F + 20, column: victoryColumn };
