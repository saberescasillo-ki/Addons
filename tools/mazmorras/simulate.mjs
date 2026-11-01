// Runs the dungeon generator outside the game.
//   node simulate.mjs blocks <seed> <theme> <rooms> <floors> <facing>  -> JSON with the plan and the blocks
//   node simulate.mjs check <runs>                                     -> checks many random dungeons
import { buildDungeon, planDungeon, THEME_KEYS, ENTRY_DEPTH } from "./gen.js";

const ORIGIN = { x: 0, y: 80, z: 0 };

function voxels(pieces) {
  const map = new Map();
  for (const p of pieces)
    for (const op of p.ops) {
      const put = (x, y, z, b) => {
        const id = (typeof b === "string" ? b : b.id).replace("minecraft:", "");
        const k = `${x},${y},${z}`;
        if (id === "air") map.delete(k);
        else map.set(k, id);
      };
      if (op[0] === "f") {
        const [, x1, y1, z1, x2, y2, z2, b] = op;
        for (let x = x1; x <= x2; x++) for (let y = y1; y <= y2; y++) for (let z = z1; z <= z2; z++) put(x, y, z, b);
      } else put(op[1], op[2], op[3], op[4]);
    }
  return map;
}

const SOLID_FREE = /air|carpet|vines|lichen|roots|hanging_moss|spore|chain|lantern|candle|water|vine|fern|short_grass|azalea$|dripleaf/;

// Walks the dungeon from the top of the entrance: every room centre must be reachable on foot.
function reachable(map, start, targets) {
  const solid = (x, y, z) => {
    const b = map.get(`${x},${y},${z}`);
    return b !== undefined && !SOLID_FREE.test(b) && !/slab|stairs|wall|chest|vault|spawner/.test(b) ? 2 : b && /slab|stairs/.test(b) ? 1 : 0;
  };
  const free = (x, y, z) => {
    const b = map.get(`${x},${y},${z}`);
    return b === undefined || SOLID_FREE.test(b);
  };
  // a position is standable at (x,y,z) if y and y+1 are free and there is ground at y-1
  const seen = new Set();
  const q = [start];
  seen.add(start.join(","));
  while (q.length) {
    const [x, y, z] = q.pop();
    for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]])
      for (const dy of [-1, 0, 1, -2, -3]) {
        const nx = x + dx, ny = y + dy, nz = z + dz;
        const k = `${nx},${ny},${nz}`;
        if (seen.has(k)) continue;
        if (!free(nx, ny, nz) || !free(nx, ny + 1, nz)) continue;
        if (dy > 0 && !free(x, y + 2, z)) continue;
        const g = map.get(`${nx},${ny - 1},${nz}`);
        if (g === undefined || /air/.test(g)) continue;
        seen.add(k);
        q.push([nx, ny, nz]);
      }
  }
  return targets.filter(([x, y, z]) => ![0, 1].some((dy) => seen.has(`${x},${y + dy},${z}`)));
}

const [mode, ...args] = process.argv.slice(2);
if (mode === "blocks") {
  const [seed, theme, rooms, floors, facing] = args;
  const plan = planDungeon({ seed: Number(seed), theme, rooms: Number(rooms), floors: Number(floors), facing: Number(facing) });
  const built = buildDungeon(plan, ORIGIN);
  const map = voxels(built.pieces);
  const blocks = [];
  for (const [k, id] of map) blocks.push([...k.split(",").map(Number), id]);
  process.stdout.write(JSON.stringify({
    plan: { counts: plan.counts, floors: plan.floorsUsed, theme: plan.theme },
    rooms: built.rooms.map((r) => ({ id: r.id, type: r.type, x: r.x, z: r.z, Y: r.Y, f: r.f })),
    spawners: built.spawners, bounds: built.bounds, y0: built.y0, ops: built.pieces.reduce((a, p) => a + p.ops.length, 0),
    blocks,
  }));
} else if (mode === "check") {
  const runs = Number(args[0] ?? 50);
  const errors = [];
  let ops = 0, maxOps = 0;
  for (let i = 0; i < runs; i++) {
    const theme = THEME_KEYS[i % THEME_KEYS.length];
    const rooms = 5 + (i * 7) % 26, floors = 1 + (i % 4), facing = i % 4;
    const plan = planDungeon({ seed: 1000 + i, theme, rooms, floors, facing });
    const built = buildDungeon(plan, ORIGIN);
    const n = built.pieces.reduce((a, p) => a + p.ops.length, 0);
    ops += n;
    maxOps = Math.max(maxOps, n);
    if (plan.rooms.length !== rooms + 1) errors.push(`${i}: ${plan.rooms.length - 1} salas de ${rooms}`);
    const map = voxels(built.pieces);
    // targets: the floor in front of each room's centre (spawner rooms: next to the spawner)
    const targets = built.rooms.map((r) => [r.x + (r.type === "spawner" ? 1 : 0), r.Y, r.z + (r.type === "spawner" ? 1 : 0)]);
    // parkour rooms: the chest ledge is the goal; test only the door ledge on foot
    const lost = reachable(map, [ORIGIN.x, ORIGIN.y, ORIGIN.z], targets.filter((_, k) => built.rooms[k].type !== "parkour"));
    if (lost.length) errors.push(`${i} (${theme}, ${rooms} salas, ${floors} pisos): inalcanzables ${JSON.stringify(lost)}`);
    if (built.y0 !== ORIGIN.y - ENTRY_DEPTH) errors.push("y0");
  }
  console.log(JSON.stringify({ runs, avgOps: Math.round(ops / runs), maxOps, errors: errors.slice(0, 15), nErrors: errors.length }, null, 1));
}
