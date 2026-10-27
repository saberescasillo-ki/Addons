// Runs the island generator outside the game.
//   node simulate.mjs blocks <seed> <cx,cz> ...   -> JSON with the blocks of each 4x4-chunk cell
//   node simulate.mjs check <seed> <radius>       -> checks the layer rules on (2r+1)^2 cells
import { buildCell, CELL, HALF, LOWER_MAX, LOWER_MIN, UPPER_MIN } from "./gen.js";

function voxels(ops) {
  const map = new Map();
  const put = (x, y, z, b) => {
    const id = typeof b === "string" ? b : b.id;
    const k = `${x},${y},${z}`;
    if (id === "minecraft:air") map.delete(k);
    else map.set(k, id.replace("minecraft:", ""));
  };
  for (const op of ops) {
    if (op[0] === "f") {
      const [, x1, y1, z1, x2, y2, z2, b] = op;
      for (let x = x1; x <= x2; x++) for (let y = y1; y <= y2; y++) for (let z = z1; z <= z2; z++) put(x, y, z, b);
    } else put(op[1], op[2], op[3], op[4]);
  }
  return map;
}

const [mode, seedArg, ...rest] = process.argv.slice(2);
const seed = Number(seedArg);

if (mode === "blocks") {
  const out = [];
  for (const arg of rest) {
    const [cx, cz] = arg.split(",").map(Number);
    const { ops, info } = buildCell(cx, cz, seed);
    const blocks = [];
    for (const [k, id] of voxels(ops)) {
      const [x, y, z] = k.split(",").map(Number);
      const lx = x - (cx * CELL - HALF), lz = z - (cz * CELL - HALF);
      if (lx >= 0 && lx < CELL && lz >= 0 && lz < CELL) blocks.push([lx, y, lz, id]);
    }
    out.push({ cx, cz, info, ops: ops.length, blocks });
  }
  process.stdout.write(JSON.stringify(out));
} else if (mode === "check") {
  const r = Number(rest[0] ?? 4);
  const stats = { cells: 0, ops: 0, maxOps: 0, ms: 0, kinds: {}, dungeons: {}, errors: [] };
  for (let cx = -r; cx <= r; cx++)
    for (let cz = -r; cz <= r; cz++) {
      const t = Date.now();
      const { ops, info } = buildCell(cx, cz, seed);
      stats.ms += Date.now() - t;
      stats.cells++;
      stats.ops += ops.length;
      stats.maxOps = Math.max(stats.maxOps, ops.length);
      for (const i of info) {
        const bag = i.startsWith("mazmorra") ? stats.dungeons : stats.kinds;
        bag[i] = (bag[i] ?? 0) + 1;
      }
      const main = cx === 0 && cz === 0;
      for (const [k, id] of voxels(ops)) {
        const [, y] = k.split(",").map(Number);
        const between = y > LOWER_MAX && y < UPPER_MIN && !main;
        if (y < LOWER_MIN || between) stats.errors.push(`${cx},${cz}: ${id} at ${k}`);
        if (y < UPPER_MIN && y >= LOWER_MIN && !main && !/deepslate|lava|air|chest|lantern|web/.test(id))
          stats.errors.push(`${cx},${cz}: ${id} in the lower layer at ${k}`);
      }
    }
  stats.errors = stats.errors.slice(0, 20);
  console.log(JSON.stringify(stats, null, 1));
}
