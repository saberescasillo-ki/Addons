// Estructuras Épicas — trial spawners propios.
// Funcionan como los de las Trial Chambers: detectan jugadores (14 bloques), sacan una oleada de
// 6 mobs (+2 por jugador extra, máx. 2 vivos +1 por jugador extra), sueltan recompensa al terminar
// (una por jugador) y se enfrían 30 minutos.
import { system, world, GameMode } from "@minecraft/server";

const NS = "epicas";
const SPAWNERS = [{"mobs": [["minecraft:husk", 3], ["minecraft:skeleton", 2], ["minecraft:spider", 1]], "loot": "desierto"}, {"mobs": [["minecraft:spider", 2], ["minecraft:cave_spider", 2], ["minecraft:zombie", 1]], "loot": "jungla"}, {"mobs": [["minecraft:slime", 2], ["minecraft:bogged", 2], ["minecraft:witch", 1]], "loot": "pantano"}, {"mobs": [["minecraft:stray", 3], ["minecraft:zombie", 1]], "loot": "nieve"}, {"mobs": [["minecraft:pillager", 3], ["minecraft:vindicator", 2]], "loot": "saqueadores"}, {"mobs": [["minecraft:zombie_pigman", 2], ["minecraft:magma_cube", 2], ["minecraft:blaze", 1]], "loot": "nether"}, {"mobs": [["minecraft:zombie", 3], ["minecraft:zombie_villager_v2", 1], ["minecraft:skeleton", 2]], "loot": "cripta"}, {"mobs": [["minecraft:skeleton", 2], ["minecraft:zombie", 2], ["minecraft:spider", 1]], "loot": "cripta"}, {"mobs": [["minecraft:zombie", 3], ["minecraft:husk", 2], ["minecraft:spider", 1]], "loot": "camaras"}, {"mobs": [["minecraft:skeleton", 3], ["minecraft:stray", 2], ["minecraft:bogged", 1]], "loot": "camaras"}, {"mobs": [["minecraft:breeze", 1]], "loot": "camaras_breeze"}, {"mobs": [["minecraft:slime", 2], ["minecraft:cave_spider", 2], ["minecraft:silverfish", 1]], "loot": "camaras"}, {"mobs": [["minecraft:wither_skeleton", 3], ["minecraft:blaze", 2], ["minecraft:magma_cube", 1]], "loot": "fortaleza"}, {"mobs": [["minecraft:piglin", 2], ["minecraft:piglin_brute", 1], ["minecraft:hoglin", 1]], "loot": "bastion"}, {"mobs": [["minecraft:shulker", 2], ["minecraft:enderman", 2], ["minecraft:endermite", 1]], "loot": "end"}, {"mobs": [["minecraft:vindicator", 3], ["minecraft:pillager", 2], ["minecraft:evocation_illager", 1]], "loot": "mansion"}];
const RANGE = 14;
const COOLDOWN = 36000;        // ticks (30 min)
const SPAWN_EVERY = 40;        // ticks entre apariciones
const RESET_IDLE = 2400;       // si nadie está cerca 2 min durante la oleada, se reinicia
const FASE = NS + ":fase", CONFIG = NS + ":config";

const keyOf = (b) => `ts:${b.dimension.id}:${b.location.x},${b.location.y},${b.location.z}`;
const tagOf = (b) => `ts_${b.location.x}_${b.location.y}_${b.location.z}`;
const load = (k) => { try { const v = world.getDynamicProperty(k); return v ? JSON.parse(v) : null; } catch { return null; } };
const save = (k, d) => world.setDynamicProperty(k, d === null ? undefined : JSON.stringify(d));

function setFase(block, f) {
  try { block.setPermutation(block.permutation.withState(FASE, f)); } catch {}
}
function sound(block, id) {
  try { block.dimension.playSound(id, block.center()); } catch {}
}
function particle(dim, id, loc) {
  try { dim.spawnParticle(id, loc); } catch {}
}
function playersNear(block) {
  return block.dimension.getPlayers({ location: block.center(), maxDistance: RANGE })
    .filter((p) => p.getGameMode() !== GameMode.Spectator);
}
function pick(list) {
  let tot = 0; for (const [, w] of list) tot += w;
  let r = Math.random() * tot;
  for (const [id, w] of list) { r -= w; if (r <= 0) return id; }
  return list[0][0];
}
function freeSpot(block) {
  const dim = block.dimension, o = block.location;
  for (let i = 0; i < 16; i++) {
    const x = o.x + Math.floor(Math.random() * 9) - 4, z = o.z + Math.floor(Math.random() * 9) - 4;
    for (const dy of [0, 1, -1, 2]) {
      const y = o.y + dy;
      try {
        const feet = dim.getBlock({ x, y, z }), head = dim.getBlock({ x, y: y + 1, z }), below = dim.getBlock({ x, y: y - 1, z });
        if (feet && head && below && feet.isAir && head.isAir && !below.isAir && !below.isLiquid) return { x: x + 0.5, y, z: z + 0.5 };
      } catch {}
    }
  }
  return null;
}

function tickSpawner(block) {
  const cfg = SPAWNERS[block.permutation.getState(CONFIG)] ?? SPAWNERS[0];
  const k = keyOf(block), now = world.getAbsoluteTime();
  let s = load(k) ?? { fase: 0 };
  const near = playersNear(block);

  if (s.fase === 2) {                                    // enfriamiento
    if (now >= s.until) { s = { fase: 0 }; setFase(block, 0); save(k, s); }
    return;
  }
  if (s.fase === 0) {                                    // esperando jugadores
    if (near.length === 0) return;
    const n = near.length;
    s = { fase: 1, total: 6 + 2 * (n - 1), maxAlive: 2 + (n - 1), spawned: 0, players: n, last: 0, seen: now };
    setFase(block, 1); sound(block, "trial_spawner.detect_player");
    save(k, s);
    return;
  }
  // fase 1: oleada activa
  if (near.length > s.players) {                         // llegó otro jugador: más mobs
    const extra = near.length - s.players;
    s.total += 2 * extra; s.maxAlive += extra; s.players = near.length;
  }
  if (near.length > 0) s.seen = now;
  const tag = tagOf(block);
  const alive = block.dimension.getEntities({ tags: [tag], location: block.center(), maxDistance: 48 }).length;
  if (now - s.seen > RESET_IDLE) {                        // abandonado: reinicia
    for (const e of block.dimension.getEntities({ tags: [tag] })) { try { e.remove(); } catch {} }
    s = { fase: 0 }; setFase(block, 0); save(k, s); return;
  }
  if (s.spawned < s.total && alive < s.maxAlive && now - s.last >= SPAWN_EVERY && near.length > 0) {
    const spot = freeSpot(block);
    if (spot) {
      try {
        const e = block.dimension.spawnEntity(pick(cfg.mobs), spot);
        e.addTag(tag);
        particle(block.dimension, "minecraft:mobflame_single", spot);
        particle(block.dimension, "minecraft:trial_spawner_detection", block.center());
        sound(block, "trial_spawner.spawn_mob");
        s.spawned++; s.last = now;
      } catch {}
    }
  }
  if (s.spawned >= s.total && alive === 0) {             // oleada superada: recompensa
    setFase(block, 2); sound(block, "trial_spawner.open_shutter");
    const n = Math.max(1, s.players), loc = block.location;
    for (let i = 0; i < n; i++) {
      system.runTimeout(() => {
        try {
          block.dimension.runCommand(`loot spawn ${loc.x + 0.5} ${loc.y + 1.2} ${loc.z + 0.5} loot "${NS}/trial/${cfg.loot}"`);
          sound(block, "trial_spawner.eject_item");
        } catch {}
      }, 20 + i * 20);
    }
    s = { fase: 2, until: now + COOLDOWN };
  }
  save(k, s);
}

system.beforeEvents.startup.subscribe(({ blockComponentRegistry }) => {
  blockComponentRegistry.registerCustomComponent(`${NS}:trial_spawner`, {
    onTick({ block }) { try { tickSpawner(block); } catch (e) { console.warn(`[${NS}] ${e}`); } },
  });
});

world.afterEvents.playerBreakBlock.subscribe(({ block, brokenBlockPermutation }) => {
  if (brokenBlockPermutation.type.id !== `${NS}:trial_spawner`) return;
  save(keyOf(block), null);
});
