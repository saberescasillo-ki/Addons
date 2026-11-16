// Runs the Underworld generator outside the game.
//   node simulate.mjs blocks <seed> <cx,cz> ...   -> JSON: for each cell, the palette and the grid (base64)
//   node simulate.mjs check <seed> <radius>       -> statistics and rule checks on (2r+1)^2 cells
import { buildCellSync, CELL, HALF, H, LAVA } from "./gen.js";

// Rebuilds the cell from the block operations, as the game would.
function replay(cx, cz, ops) {
  const x0 = cx * CELL - HALF, z0 = cz * CELL - HALF;
  const names = ["air"], index = new Map([["air", 0]]);
  const grid = new Uint8Array(CELL * CELL * H);
  const errors = [];
  const put = (x, y, z, b) => {
    const id = (typeof b === "string" ? b : b.id).replace("minecraft:", "");
    if (!index.has(id)) {
      index.set(id, names.length);
      names.push(id);
    }
    const lx = x - x0, lz = z - z0;
    if (lx < 0 || lx >= CELL || lz < 0 || lz >= CELL || y < 0 || y >= H) errors.push(`${id} outside the cell at ${x},${y},${z}`);
    else grid[(lx * CELL + lz) * H + y] = index.get(id);
  };
  for (const op of ops) {
    if (op[0] === "f") {
      const [, x1, y1, z1, x2, y2, z2, b] = op;
      if ((x2 - x1 + 1) * (y2 - y1 + 1) * (z2 - z1 + 1) > 32768) errors.push(`fill too big at ${x1},${y1},${z1}`);
      for (let x = x1; x <= x2; x++) for (let y = y1; y <= y2; y++) for (let z = z1; z <= z2; z++) put(x, y, z, b);
    } else put(op[1], op[2], op[3], op[4]);
  }
  return { names, grid, errors };
}

const [mode, seedArg, ...rest] = process.argv.slice(2);
const seed = Number(seedArg);

if (mode === "blocks") {
  const out = [];
  for (const arg of rest) {
    const [cx, cz] = arg.split(",").map(Number);
    const { ops, info } = buildCellSync(cx, cz, seed);
    const { names, grid } = replay(cx, cz, ops);
    out.push({ cx, cz, info, ops: ops.length, size: CELL, height: H, names, grid: Buffer.from(grid).toString("base64") });
  }
  process.stdout.write(JSON.stringify(out));
} else if (mode === "check") {
  const r = Number(rest[0] ?? 3);
  const stats = { cells: 0, ops: 0, maxOps: 0, ms: 0, maxMs: 0, air: 0, standable: 0, minStandable: 1e9, biomes: {}, things: {}, blocks: {}, errors: [] };
  const edges = new Map();
  for (let cx = -r; cx <= r; cx++)
    for (let cz = -r; cz <= r; cz++) {
      const t = performance.now();
      const { ops, info } = buildCellSync(cx, cz, seed);
      const ms = performance.now() - t;
      stats.ms += ms;
      stats.maxMs = Math.max(stats.maxMs, ms);
      stats.cells++;
      stats.ops += ops.length;
      stats.maxOps = Math.max(stats.maxOps, ops.length);
      stats.biomes[info[0]] = (stats.biomes[info[0]] ?? 0) + 1;
      for (const i of info.slice(1)) stats.things[i] = (stats.things[i] ?? 0) + 1;
      const { names, grid, errors } = replay(cx, cz, ops);
      stats.errors.push(...errors.map((e) => `${cx},${cz}: ${e}`));
      const lava = names.indexOf("lava"), bedrock = names.indexOf("bedrock");
      let standable = 0;
      for (let x = 0; x < CELL; x++)
        for (let z = 0; z < CELL; z++) {
          const base = (x * CELL + z) * H;
          if (grid[base] !== bedrock || grid[base + H - 1] !== bedrock) stats.errors.push(`${cx},${cz}: no bedrock at ${x},${z}`);
          for (let y = 1; y < H - 1; y++) {
            const id = grid[base + y];
            if (id === 0) stats.air++;
            else stats.blocks[names[id]] = (stats.blocks[names[id]] ?? 0) + 1;
            if (id === 0 && y <= LAVA) stats.errors.push(`${cx},${cz}: air under the lava level at ${x},${y},${z}`);
            if (id === lava && y > LAVA) stats.errors.push(`${cx},${cz}: lava above its level at ${x},${y},${z}`);
            if (id !== 0 && id !== lava && grid[base + y + 1] === 0 && grid[base + y + 2] === 0 && y > LAVA) standable++;
          }
        }
      stats.standable += standable;
      stats.minStandable = Math.min(stats.minStandable, standable);
      // the walls of the cell, to compare with its neighbours: caverns must continue
      const solid = (x, z) => {
        let s = "";
        for (let y = 0; y < H; y++) s += grid[(x * CELL + z) * H + y] === 0 ? "0" : "1";
        return s;
      };
      const e = { w: [], e: [], n: [], s: [] };
      for (let i = 0; i < CELL; i++) {
        e.w.push(solid(0, i)); e.e.push(solid(CELL - 1, i)); e.n.push(solid(i, 0)); e.s.push(solid(i, CELL - 1));
      }
      edges.set(`${cx},${cz}`, e);
    }
  // adjacent walls of two cells should be nearly equal (the terrain is continuous)
  let seam = 0, seamN = 0;
  const diff = (a, b) => {
    for (let i = 0; i < a.length; i++) for (let y = 0; y < H; y++) { seamN++; if (a[i][y] !== b[i][y]) seam++; }
  };
  for (const [k, e] of edges) {
    const [cx, cz] = k.split(",").map(Number);
    const east = edges.get(`${cx + 1},${cz}`), south = edges.get(`${cx},${cz + 1}`);
    if (east) diff(e.e, east.w);
    if (south) diff(e.s, south.n);
  }
  stats.seamDifference = seamN ? +(seam / seamN).toFixed(4) : 0;
  const total = stats.cells * CELL * CELL * (H - 2);
  stats.air = +(stats.air / total).toFixed(3);
  stats.standable = Math.round(stats.standable / stats.cells);
  stats.ms = Math.round(stats.ms / stats.cells);
  stats.maxMs = Math.round(stats.maxMs);
  stats.ops = Math.round(stats.ops / stats.cells);
  stats.errors = stats.errors.slice(0, 20);
  console.log(JSON.stringify(stats, null, 1));
}
