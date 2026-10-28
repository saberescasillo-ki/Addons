// Runs the dungeon generator outside the game.
//   node simulate.mjs check <seed> <rooms>      -> room counts and how much of the dungeon can be reached
//   node simulate.mjs map <seed> <rx0> <rz0> <n> -> JSON map of n x n rooms on every floor
//   node simulate.mjs blocks <seed> <x0> <z0> <x1> <z1> -> JSON blocks inside that box (all floors)
import { arenaAt, buildRegion, edge, FLOORS, regionOf, roomType, stairDown } from "./gen.js";

const [mode, seedArg, ...rest] = process.argv.slice(2);
const seed = Number(seedArg);

function voxels(ops, box) {
  const map = new Map();
  const [bx0, bz0, bx1, bz1] = box;
  const put = (x, y, z, b) => {
    if (x < bx0 || x > bx1 || z < bz0 || z > bz1) return;
    const id = typeof b === "string" ? b : b.id;
    const k = `${x},${y},${z}`;
    if (id === "minecraft:air") map.delete(k);
    else map.set(k, id.replace("minecraft:", ""));
  };
  for (const op of ops) {
    if (op[0] === "f") {
      const [, x1, y1, z1, x2, y2, z2, b] = op;
      for (let x = Math.max(x1, bx0); x <= Math.min(x2, bx1); x++)
        for (let y = y1; y <= y2; y++)
          for (let z = Math.max(z1, bz0); z <= Math.min(z2, bz1); z++) put(x, y, z, b);
    } else put(op[1], op[2], op[3], op[4]);
  }
  return map;
}

if (mode === "check") {
  const n = Number(rest[0] ?? 40);
  const counts = {};
  const arenas = new Set();
  let stairs = [0, 0];
  for (let f = 0; f < 3; f++)
    for (let rx = -n; rx < n; rx++)
      for (let rz = -n; rz < n; rz++) {
        const t = roomType(seed, f, rx, rz);
        counts[`${f + 1}:${t}`] = (counts[`${f + 1}:${t}`] ?? 0) + 1;
        if (t === "escalera") stairs[f]++;
        const a = arenaAt(seed, f, rx, rz);
        if (a) arenas.add(a.key);
        if (stairDown(seed, f, rx, rz) && stairDown(seed, f + 1, rx, rz)) throw new Error("stacked stairs");
        for (let d = 0; d < 4; d++) {
          const nx = rx + [1, -1, 0, 0][d], nz = rz + [0, 0, 1, -1][d];
          if (edge(seed, f, rx, rz, d) !== edge(seed, f, nx, nz, [1, 0, 3, 2][d])) throw new Error("asymmetric edge");
        }
      }
  // reachable rooms from the entrance hall, walking through doors and down the stairs
  const seen = new Set(["0:0:0"]);
  const queue = [[0, 0, 0]];
  while (queue.length) {
    const [f, rx, rz] = queue.pop();
    const next = [];
    for (let d = 0; d < 4; d++) if (edge(seed, f, rx, rz, d) !== "wall") next.push([f, rx + [1, -1, 0, 0][d], rz + [0, 0, 1, -1][d]]);
    if (stairDown(seed, f, rx, rz)) next.push([f + 1, rx, rz]);
    if (stairDown(seed, f - 1, rx, rz)) next.push([f - 1, rx, rz]);
    for (const [nf, nx, nz] of next) {
      if (Math.abs(nx) >= n || Math.abs(nz) >= n) continue;
      const k = `${nf}:${nx}:${nz}`;
      if (!seen.has(k)) { seen.add(k); queue.push([nf, nx, nz]); }
    }
  }
  const reach = [0, 0, 0];
  for (const k of seen) reach[Number(k.split(":")[0])]++;
  const t = Date.now();
  const { ops } = buildRegion(0, 0, seed);
  console.log(JSON.stringify({ rooms: (2 * n) ** 2, reach, stairs, arenas: arenas.size, regionOps: ops.length,
    regionMs: Date.now() - t, counts }, null, 1));
} else if (mode === "map") {
  const [rx0, rz0, n] = rest.map(Number);
  const floors = [];
  for (let f = 0; f < 3; f++) {
    const rooms = [];
    for (let rz = rz0; rz < rz0 + n; rz++)
      for (let rx = rx0; rx < rx0 + n; rx++)
        rooms.push({ rx, rz, type: roomType(seed, f, rx, rz), arrival: stairDown(seed, f - 1, rx, rz),
          doors: [0, 1, 2, 3].map((d) => edge(seed, f, rx, rz, d)) });
    floors.push(rooms);
  }
  process.stdout.write(JSON.stringify({ floors, y: FLOORS }));
} else if (mode === "blocks") {
  const [x0, z0, x1, z1] = rest.map(Number);
  const regions = new Set();
  for (const x of [x0, x1]) for (const z of [z0, z1]) regions.add(`${regionOf(Math.floor((x + 5) / 11))},${regionOf(Math.floor((z + 5) / 11))}`);
  const blocks = [];
  const all = new Map();
  for (const r of regions) {
    const [gx, gz] = r.split(",").map(Number);
    for (const [k, v] of voxels(buildRegion(gx, gz, seed).ops, [x0, z0, x1, z1])) all.set(k, v);
  }
  for (const [k, id] of all) blocks.push([...k.split(",").map(Number), id]);
  process.stdout.write(JSON.stringify(blocks));
}
