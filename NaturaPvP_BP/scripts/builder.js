// Natura PvP: builds (and rebuilds) the areas of gen.js in the world.
// Each area is built in sections of 10x10 chunks: a temporary ticking area
// loads the section, a job places its columns, and the ticking area is removed.
import * as mc from "@minecraft/server";
import { AREA, PALETTE } from "./gen.js";

const { system, world } = mc;
const SECTION = 160; // blocks (10 chunks): the biggest ticking area allowed
const TICKING = "natura_build";

const overworld = () => world.getDimension("minecraft:overworld");
const sleep = (ticks) => new Promise((r) => system.runTimeout(r, ticks));

// ------------------------------------------------------------ blocks
const perms = new Map();
function stateText(states) {
  if (!states) return "";
  const parts = Object.entries(states).map(([k, v]) => `"${k}"=${typeof v === "string" ? `"${v}"` : v}`);
  return parts.length ? `[${parts.join(",")}]` : "";
}

function perm(key) {
  if (perms.has(key)) return perms.get(key);
  const spec = key === "air" ? { id: "minecraft:air" } : PALETTE[key];
  let found = null;
  for (const id of spec.id.split("|")) {
    try {
      found = { perm: mc.BlockPermutation.resolve(id, spec.s), cmd: id + stateText(spec.s) };
      break;
    } catch {
      try {
        found = { perm: mc.BlockPermutation.resolve(id), cmd: id };
        break;
      } catch {}
    }
  }
  if (!found) console.warn(`[Natura PvP] bloque desconocido: ${spec.id}`);
  perms.set(key, found);
  return found;
}

const canFill = typeof mc.BlockVolume === "function";

function fill(dim, x, y0, y1, z, key) {
  const p = perm(key);
  if (!p) return;
  if (y0 === y1) {
    dim.getBlock({ x, y: y0, z })?.setPermutation(p.perm);
  } else if (canFill) {
    dim.fillBlocks(new mc.BlockVolume({ x, y: y0, z }, { x, y: y1, z }), p.perm);
  } else {
    dim.runCommand(`fill ${x} ${y0} ${z} ${x} ${y1} ${z} ${p.cmd}`);
  }
}

// ------------------------------------------------------------ loading
function loaded(dim, points) {
  for (const p of points) {
    try {
      if (!dim.getBlock({ x: p.x, y: 64, z: p.z })) return false;
    } catch {
      return false;
    }
  }
  return true;
}

async function loadSection(dim, x0, z0, x1, z1) {
  const points = [{ x: x0, z: z0 }, { x: x1, z: z0 }, { x: x0, z: z1 }, { x: x1, z: z1 }, { x: (x0 + x1) >> 1, z: (z0 + z1) >> 1 }];
  if (loaded(dim, points)) return { ok: true, area: false };
  try {
    dim.runCommand(`tickingarea remove ${TICKING}`);
  } catch {}
  let area = false;
  try {
    dim.runCommand(`tickingarea add ${x0} 0 ${z0} ${x1} 0 ${z1} ${TICKING} true`);
    area = true;
  } catch (e) {
    console.warn(`[Natura PvP] no se pudo crear la zona de carga: ${e}`);
  }
  for (let i = 0; i < 120; i++) {
    await sleep(10);
    if (loaded(dim, points)) return { ok: true, area };
  }
  if (area) dropSection(dim);
  return { ok: false, area: false };
}

function dropSection(dim) {
  try {
    dim.runCommand(`tickingarea remove ${TICKING}`);
  } catch {}
}

// ------------------------------------------------------------ jobs
export const progress = { busy: false, label: "", done: 0, total: 0, errors: 0 };
let queue = Promise.resolve();
const pending = new Map(); // area id -> jobs waiting or running
const cancels = new Set(); // areas whose jobs must stop

// Stops the jobs of an area (running or waiting). They resolve with "cancelled"
// and `left` holds the columns ("x,z") they did not get to.
export function cancelArea(id) {
  if ((pending.get(id) ?? 0) > 0) cancels.add(id);
}

function* placeColumns(dim, area, cols, clear, state) {
  for (const [x, z] of cols) {
    if (cancels.has(area.id)) return;
    state.done++;
    try {
      if (clear) fill(dim, x, area.bottom, area.clearTop, z, "air");
      for (const s of area.column(x, z)) fill(dim, x, s[0], s[1], z, s[2]);
    } catch (e) {
      if (progress.errors++ < 5) console.warn(`[Natura PvP] ${area.id} ${x},${z}: ${e}`);
    }
    progress.done++;
    yield;
  }
}

function sectionsOf(area, only) {
  const out = [];
  const sx0 = Math.floor(area.x0 / SECTION) * SECTION, sz0 = Math.floor(area.z0 / SECTION) * SECTION;
  for (let sx = sx0; sx <= area.x1; sx += SECTION)
    for (let sz = sz0; sz <= area.z1; sz += SECTION) {
      const x0 = Math.max(sx, area.x0), x1 = Math.min(sx + SECTION - 1, area.x1);
      const z0 = Math.max(sz, area.z0), z1 = Math.min(sz + SECTION - 1, area.z1);
      const cols = [];
      if (only) {
        for (const key of only) {
          const [x, z] = key.split(",").map(Number);
          if (x >= x0 && x <= x1 && z >= z0 && z <= z1) cols.push([x, z]);
        }
      } else {
        for (let x = x0; x <= x1; x++) for (let z = z0; z <= z1; z++) cols.push([x, z]);
      }
      if (cols.length) out.push({ x0, z0, x1, z1, cols });
    }
  return out;
}

async function run(id, { clear, only, label }, result) {
  const area = AREA[id];
  const dim = overworld();
  if (cancels.has(id)) {
    result.left = only ? [...only] : null;
    return "cancelled";
  }
  const sections = sectionsOf(area, only);
  progress.busy = true;
  progress.label = label ?? area.name;
  progress.done = 0;
  progress.errors = 0;
  progress.total = sections.reduce((n, s) => n + s.cols.length, 0);
  let ok = true;
  const left = [];
  for (const s of sections) {
    if (cancels.has(id)) {
      for (const [x, z] of s.cols) left.push(`${x},${z}`);
      continue;
    }
    let load = { ok: false };
    for (let tries = 0; tries < 5 && !load.ok; tries++) {
      load = await loadSection(dim, s.x0, s.z0, s.x1, s.z1);
      if (!load.ok) await sleep(100);
    }
    if (!load.ok) {
      console.warn(`[Natura PvP] no se pudo cargar ${area.id} ${s.x0},${s.z0}`);
      ok = false;
      progress.done += s.cols.length;
      continue;
    }
    const state = { done: 0 };
    await new Promise((resolve) => system.runJob((function* () {
      yield* placeColumns(dim, area, s.cols, clear, state);
      resolve();
    })()));
    if (load.area) dropSection(dim);
    if (state.done < s.cols.length) for (const [x, z] of s.cols.slice(state.done)) left.push(`${x},${z}`);
  }
  progress.busy = false;
  if (cancels.has(id)) {
    result.left = only ? left : null; // null: a whole build was cut short
    return "cancelled";
  }
  return ok;
}

// One job at a time (they share the ticking area). Resolves with true (done),
// false (some section could not be loaded) or "cancelled" (see job.left).
function enqueue(id, opts) {
  pending.set(id, (pending.get(id) ?? 0) + 1);
  const result = {};
  const job = queue.then(() => run(id, opts, result)).finally(() => {
    const n = (pending.get(id) ?? 1) - 1;
    pending.set(id, n);
    if (n <= 0) cancels.delete(id);
  });
  queue = job.catch(() => false);
  return Object.assign(job.then((r) => r), { result });
}

export function buildArea(id, clear = false) {
  return enqueue(id, { clear });
}

// Rebuilds only some columns ("x,z" keys) of an area.
export function rebuildColumns(id, keys, label) {
  return enqueue(id, { clear: true, only: keys, label });
}
