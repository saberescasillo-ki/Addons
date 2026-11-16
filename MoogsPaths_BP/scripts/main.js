// Moog's Paths - Bedrock port (unofficial). Original Java mod by FinnDog, CC0-1.0.
import { world, system, BlockPermutation } from "@minecraft/server";
import { NETWORKS, VILLAGE_NETWORKS } from "./data.js";
import { createGenerator, newPath, hash, rng, biomeName, biomeAllowsOrigin } from "./gen.js";

// ------------------------------------------------------------------ settings
const CONFIG = {
  /** Region size multiplier. The Java mod uses 1.0; lower = more paths. Bedrock can only start a path whose
   *  origin lies in loaded chunks, so the default is denser to compensate. */
  REGION_SCALE: 0.6,
  /** Chance (0-100) for each network to actually lay a path, like config/moogs_paths.json in the Java mod. */
  CHANCE: { /* e.g. brick_road: 50, village_road_plains: 0 */ },
  /** Roads leaving villages (approximation: villages are detected through their villagers). */
  VILLAGE_ROADS: true,
  /** How far from a player (blocks) origins are looked for / paths keep growing. */
  SCAN_RADIUS: 160,
  GROW_RADIUS: 128,
  /** Ticks between scheduler runs. */
  INTERVAL: 20,
  DEBUG: false,
};
// ------------------------------------------------------------------

const P_SEED = "moogs:seed", P_PATH = "moogs:p:", P_DONE = "moogs:d:";
const NETS = Object.fromEntries([...NETWORKS, ...Object.values(VILLAGE_NETWORKS)].map((n) => [n.id, n]));
const SIZES = [...new Set(NETWORKS.map((n) => n.region))];
const scaled = (size) => Math.max(4, Math.round(size * CONFIG.REGION_SCALE));

let seed = 0, dim, gen, busy = false, cycle = 0;
const paths = new Map();      // key -> state (active paths)
const done = new Set();       // origins already evaluated

const log = (msg) => { if (CONFIG.DEBUG) world.sendMessage("§7" + msg); };
const keeps = (net, r) => r() * 100 < (CONFIG.CHANCE[net.id] ?? 100);

function init() {
  dim = world.getDimension("overworld");
  seed = world.getDynamicProperty(P_SEED);
  if (typeof seed !== "number") {
    const s = String(world.seed ?? Math.random());
    seed = hash(...[...s].map((c) => c.charCodeAt(0)));
    world.setDynamicProperty(P_SEED, seed);
  }
  for (const id of world.getDynamicPropertyIds()) {
    if (id.startsWith(P_DONE)) done.add(id.slice(P_DONE.length));
    else if (id.startsWith(P_PATH)) {
      try { const st = JSON.parse(world.getDynamicProperty(id)); if (NETS[st.n]) { st.wait = 0; paths.set(st.k, st); } } catch { world.setDynamicProperty(id, undefined); }
    }
  }
  gen = createGenerator(dim, { BlockPermutation, log: (m) => console.warn(m) });
  system.runInterval(tick, CONFIG.INTERVAL);
}

function markDone(key) { done.add(key); world.setDynamicProperty(P_DONE + key, true); }
function savePath(st) { paths.set(st.k, st); world.setDynamicProperty(P_PATH + st.k, JSON.stringify(st)); }
function dropPath(st) { paths.delete(st.k); world.setDynamicProperty(P_PATH + st.k, undefined); }

function loaded(x, z) {
  try { return dim.isChunkLoaded({ x, y: 64, z }); } catch { return false; }
}
/** The whole search window around a path head must be loaded, otherwise the path would hug the loading border. */
function windowLoaded(x, z) {
  const w = 48;
  return loaded(x, z) && loaded(x - w, z - w) && loaded(x + w, z - w) && loaded(x - w, z + w) && loaded(x + w, z + w);
}

function startPath(key, net, x, z, sample) {
  const s = sample(x, z);
  if (!s || s.w) return false;
  savePath(newPath(key, net, x, s.y, z, seed));
  log(`[Moog's Paths] ${net.id} @ ${x} ${s.y} ${z}`);
  return true;
}

/** One origin per region and region size, exactly like the Java mod's PathRegionSelector. */
function scanOrigins(player, sample) {
  const { x: px, z: pz } = player.location;
  for (const size of SIZES) {
    const sz = scaled(size), span = sz * 16;
    for (let rx = Math.floor((px - CONFIG.SCAN_RADIUS) / span); rx <= Math.floor((px + CONFIG.SCAN_RADIUS) / span); rx++) {
      for (let rz = Math.floor((pz - CONFIG.SCAN_RADIUS) / span); rz <= Math.floor((pz + CONFIG.SCAN_RADIUS) / span); rz++) {
        const key = `${size}_${rx}_${rz}`;
        if (done.has(key)) continue;
        const r = rng(hash(seed, rx, rz, size));
        const ox = (rx * sz + r.int(0, sz - 1)) * 16 + 8, oz = (rz * sz + r.int(0, sz - 1)) * 16 + 8;
        if (!loaded(ox, oz)) continue;                      // evaluated later, when a player gets closer
        const s = sample(ox, oz);
        let biome;
        try { biome = biomeName(dim.getBiome({ x: ox, y: s ? s.y : 64, z: oz })); } catch { continue; }
        markDone(key);
        if (!s || s.w || !biomeAllowsOrigin(biome)) continue;
        const candidates = NETWORKS.filter((n) => n.region === size && (!n.biomes || n.biomes.includes(biome)));
        if (!candidates.length) continue;
        const net = r.pick(candidates.map((n) => [n, n.weight]));
        if (keeps(net, r)) startPath(key, net, ox, oz, sample);
      }
    }
  }
}

/** Village roads: the Java mod anchors them on village jigsaw pieces; here a village is "4+ villagers together". */
function scanVillage(player, sample) {
  const villagers = dim.getEntities({ type: "minecraft:villager_v2", location: player.location, maxDistance: 72 });
  if (villagers.length < 4) return;
  let cx = 0, cz = 0;
  for (const v of villagers) { cx += v.location.x; cz += v.location.z; }
  cx = Math.round(cx / villagers.length); cz = Math.round(cz / villagers.length);
  const key = `v_${cx >> 8}_${cz >> 8}`;
  if (done.has(key) || !loaded(cx, cz)) return;
  let radius = 24;
  for (const v of villagers) radius = Math.max(radius, Math.hypot(v.location.x - cx, v.location.z - cz) + 14);
  radius = Math.min(radius, 64);
  const c = sample(cx, cz);
  let biome = "plains";
  try { biome = biomeName(dim.getBiome({ x: cx, y: c ? c.y : 64, z: cz })); } catch { /* keep default */ }
  const kind = /desert|mesa/.test(biome) ? "desert" : /savanna/.test(biome) ? "savanna"
    : /ice|cold|snow|frozen|grove/.test(biome) ? "snowy" : /taiga/.test(biome) ? "taiga" : "plains";
  const net = VILLAGE_NETWORKS[kind];
  const r = rng(hash(seed, cx >> 8, cz >> 8, 9));
  markDone(key);
  if (!net || !keeps(net, r)) return;
  const a0 = r() * Math.PI * 2;
  for (let i = 0; i < 2; i++) {                             // path_count: 2, leaving in roughly opposite directions
    const a = a0 + i * Math.PI + (r() - 0.5);
    const x = Math.round(cx + Math.cos(a) * radius), z = Math.round(cz + Math.sin(a) * radius);
    if (!loaded(x, z) || !startPath(`${key}_${i}`, net, x, z, sample)) continue;
    const st = paths.get(`${key}_${i}`);                    // head away from the village
    st.gx = Math.round(x + Math.cos(a) * st.len); st.gz = Math.round(z + Math.sin(a) * st.len);
    savePath(st);
  }
}

function nearestGrowable(players) {
  let best = null, bestD = Infinity;
  for (const st of paths.values()) {
    if (st.wait > cycle) continue;
    for (const p of players) {
      const d = Math.hypot(st.x - p.location.x, st.z - p.location.z);
      if (d < bestD && d <= CONFIG.GROW_RADIUS && windowLoaded(st.x, st.z)) { best = st; bestD = d; }
    }
  }
  return best;
}

function* growJob(st) {
  try {
    const result = yield* gen.extend(st, NETS[st.n], seed);
    if (result === "done") { dropPath(st); log(`[Moog's Paths] finished ${st.k} (${st.t} blocks)`); }
    else if (result === "blocked") {
      // usually the chunks ahead are not loaded yet: retry a few times, then give up (ocean, cliff, ...)
      if (++st.f >= 6) dropPath(st);
      else { st.wait = cycle + 5 * st.f; savePath(st); }
    } else { st.f = 0; savePath(st); }
  } catch (e) {
    console.warn(`[Moog's Paths] ${e} ${e?.stack ?? ""}`);
    dropPath(st);
  } finally {
    busy = false;
  }
}

function tick() {
  cycle++;
  if (busy) return;
  const players = world.getPlayers().filter((p) => p.dimension.id === "minecraft:overworld");
  if (!players.length) return;
  try {
    const sample = gen.makeSampler();
    for (const p of players) {
      if (cycle % 2 === 0) scanOrigins(p, sample);
      if (CONFIG.VILLAGE_ROADS && cycle % 10 === 5) scanVillage(p, sample);
    }
  } catch (e) { console.warn(`[Moog's Paths] scan: ${e}`); }
  const st = nearestGrowable(players);
  if (st) { busy = true; system.runJob(growJob(st)); }
}

// /scriptevent moogs:path [network]  -> lays a path starting where you stand (handy for testing)
// /scriptevent moogs:info            -> shows what the generator is doing
// /scriptevent moogs:debug           -> toggles chat messages when paths start/finish
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const player = ev.sourceEntity;
  if (!ev.id.startsWith("moogs:") || !player || !gen) return;
  const say = (m) => player.sendMessage?.("§e[Moog's Paths]§r " + m);
  if (ev.id === "moogs:debug") { CONFIG.DEBUG = !CONFIG.DEBUG; say(`debug ${CONFIG.DEBUG ? "on" : "off"}`); }
  else if (ev.id === "moogs:info") {
    const near = [...paths.values()].map((s) => `${s.n} @ ${s.x} ${s.y} ${s.z} (${s.t}/${s.len})`).slice(0, 8);
    say(`seed ${seed}, ${paths.size} growing, ${done.size} origins evaluated\n` + near.join("\n"));
  } else if (ev.id === "moogs:path") {
    const x = Math.floor(player.location.x), z = Math.floor(player.location.z);
    let net = NETS[ev.message.trim()];
    if (!net) {
      let biome = "";
      try { biome = biomeName(dim.getBiome(player.location)); } catch { /* any */ }
      const c = NETWORKS.filter((n) => !n.biomes || n.biomes.includes(biome));
      net = rng(hash(x, z, system.currentTick)).pick(c.map((n) => [n, n.weight]));
    }
    const ok = player.dimension.id === "minecraft:overworld" && startPath(`m_${x}_${z}_${system.currentTick}`, net, x, z, gen.makeSampler());
    say(ok ? `${net.id} started here` : `can't start a path here. Networks: ${Object.keys(NETS).join(", ")}`);
  }
}, { namespaces: ["moogs"] });

world.afterEvents.worldLoad.subscribe(init);
