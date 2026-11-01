// Runs the dungeon generator outside the game.
//   node simulate.mjs blocks <seed> <theme> <rooms> <floors> <facing>  -> JSON with the plan and the blocks
//   node simulate.mjs check <runs>                                     -> checks many random dungeons
import { buildDungeon, planDungeon, THEME_KEYS } from "./gen.js";

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
    return b === undefined || SOLID_FREE.test(b) || b === "waxed_copper_grate"; // the barrier can be mined
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
if (mode === "ids") {
  // every block id the generator can write, over many dungeons of every theme and entrance
  const ids = new Set();
  for (let i = 0; i < 40; i++)
    for (const theme of THEME_KEYS) {
      const plan = planDungeon({ seed: 7000 + i, theme, rooms: 30, floors: 6, facing: i % 4 });
      plan.tier = 1 + (i % 4);
      for (const p of buildDungeon(plan, ORIGIN).pieces)
        for (const op of p.ops) {
          const b = op[0] === "f" ? op[7] : op[4];
          ids.add(typeof b === "string" ? b : b.id);
        }
    }
  process.stdout.write(JSON.stringify([...ids].sort()));
} else if (mode === "blocks") {
  const [seed, theme, rooms, floors, facing, tier] = args;
  const plan = planDungeon({ seed: Number(seed), theme, rooms: Number(rooms), floors: Number(floors), facing: Number(facing) });
  if (tier) plan.tier = Number(tier); // to draw every kind of entrance
  const built = buildDungeon(plan, ORIGIN);
  const map = voxels(built.pieces);
  const blocks = [];
  for (const [k, id] of map) blocks.push([...k.split(",").map(Number), id]);
  process.stdout.write(JSON.stringify({
    plan: { counts: plan.counts, floors: plan.floorsUsed, theme: plan.theme },
    rooms: built.rooms.map((r) => ({ id: r.id, type: r.type, x: r.x, z: r.z, Y: r.Y, f: r.f, box: r.box })),
    tier: plan.tier,
    spawners: built.spawners, bounds: built.bounds, y0: built.y0, ops: built.pieces.reduce((a, p) => a + p.ops.length, 0),
    blocks,
  }));
} else if (mode === "check") {
  const runs = Number(args[0] ?? 50);
  const errors = [];
  let ops = 0, maxOps = 0, missing = 0;
  const tiers = [0, 0, 0, 0, 0], floorsHist = {}, sizes = new Set(), types = {};
  for (let i = 0; i < runs; i++) {
    const theme = THEME_KEYS[i % THEME_KEYS.length];
    const rooms = 5 + (i * 7) % 26, floors = 1 + (i % 6), facing = i % 4;
    const plan = planDungeon({ seed: 1000 + i, theme, rooms, floors, facing });
    const built = buildDungeon(plan, ORIGIN);
    const n = built.pieces.reduce((a, p) => a + p.ops.length, 0);
    ops += n;
    maxOps = Math.max(maxOps, n);
    tiers[plan.tier]++;
    floorsHist[`${floors}->${plan.floorsUsed}`] = (floorsHist[`${floors}->${plan.floorsUsed}`] ?? 0) + 1;
    missing += rooms - (plan.rooms.length - 1);
    for (const r of built.rooms) {
      sizes.add(`${r.spec.L}x${r.spec.W}`);
      types[r.type] = (types[r.type] ?? 0) + 1;
    }
    for (const a of built.rooms)
      for (const b of built.rooms)
        if (a.id < b.id && a.box[0] <= b.box[3] && b.box[0] <= a.box[3] && a.box[1] <= b.box[4] && b.box[1] <= a.box[4] &&
          a.box[2] <= b.box[5] && b.box[2] <= a.box[5]) errors.push(`${i}: salas ${a.id} y ${b.id} se solapan`);
    const map = voxels(built.pieces);
    const lost = reachable(map, [ORIGIN.x, ORIGIN.y, ORIGIN.z], built.rooms.map((r) => r.probe));
    if (lost.length) errors.push(`${i} (${theme}, ${rooms} salas, ${floors} pisos): inalcanzables ${JSON.stringify(lost)}`);
  }
  console.log(JSON.stringify({ runs, avgOps: Math.round(ops / runs), maxOps, missingRooms: missing, tiers, floorsHist,
    types, distinctSizes: sizes.size, errors: errors.slice(0, 15), nErrors: errors.length }, null, 1));
}
