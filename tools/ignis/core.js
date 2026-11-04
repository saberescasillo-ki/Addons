import { world, system, GameMode, EquipmentSlot, EntityDamageCause } from "@minecraft/server";
import { config } from "./config.js";

// Ignis' script. The add-on shipped with an empty core.js: the altar could not
// start the fight, Ignis never targeted players (its targeting asks for the
// ignis:gm_* tags this script gives) and none of the config.js options worked.

const IGNIS = "ignis:ignis";
const ALTAR = "ignis:altar_of_fire";
const ASHES = "ignis:burning_ashes";
const RITUAL_TICKS = 120; // ignis_spawn's fuse (6 s): Ignis appears when the sigil bursts
const ALTAR_PROPERTY = "ignis:altar";

const cfg = Object.assign({
    ignis_breaks_all_blocks: true,
    ignis_health_changed_multiplier: 1,
    ignis_enrage_enabled: true,
    ignis_dodge_enabled: true,
    ignis_reduce_enabled: false,
}, config);

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);

// --- Players Ignis can target ------------------------------------------------
function syncTags(player) {
    if (!isValid(player)) return;
    const mode = player.getGameMode();
    const survival = mode === GameMode.Survival || mode === GameMode.survival;
    const adventure = mode === GameMode.Adventure || mode === GameMode.adventure;
    const toggle = (tag, on) => (on ? player.addTag(tag) : player.removeTag(tag));
    toggle("ignis:gm_survival", survival);
    toggle("ignis:gm_adventure", adventure);
    toggle("ignis:ignis_target", survival || adventure);
}

system.runInterval(() => {
    for (const player of world.getAllPlayers()) syncTags(player);
}, 20);
world.afterEvents.playerSpawn.subscribe(({ player }) => syncTags(player));
world.afterEvents.playerGameModeChange?.subscribe(({ player }) => syncTags(player));

// --- Altar of Fire -------------------------------------------------------------
function ignisNear(dimension, location, radius) {
    return dimension.getEntities({ type: IGNIS, location, maxDistance: radius }).length > 0;
}

function startRitual(block, player) {
    const dimension = block.dimension;
    const at = block.location;
    const center = { x: at.x + 0.5, y: at.y, z: at.z + 0.5 };
    block.setPermutation(block.permutation.withState("ignis:start", true));
    const ring = dimension.spawnEntity("ignis:altar_ring", { x: center.x, y: center.y + 1, z: center.z });
    dimension.spawnEntity("ignis:ignis_spawn", { x: center.x, y: center.y + 0.5, z: center.z });
    dimension.playSound("ignis.mob.ignis.summon", center, { volume: 3 });
    dimension.runCommand(`camerashake add @a[x=${center.x},y=${center.y},z=${center.z},r=32] 0.2 6 positional`);
    for (const p of dimension.getPlayers({ location: center, maxDistance: 48 })) {
        p.onScreenDisplay.setActionBar("§6The Altar of Fire awakens...");
    }

    system.runTimeout(() => {
        if (isValid(ring)) ring.remove();
        let altar;
        try {
            altar = dimension.getBlock(at);
        } catch {
            return; // the chunk unloaded: the altar is reset when it is used again
        }
        if (!altar || altar.typeId !== ALTAR) return;
        const ignis = dimension.spawnEntity(IGNIS, { x: center.x, y: center.y + 1, z: center.z });
        ignis.setDynamicProperty(ALTAR_PROPERTY, JSON.stringify({ d: dimension.id, ...at }));
        dimension.runCommand(`camerashake add @a[x=${center.x},y=${center.y},z=${center.z},r=48] 0.6 1.5 positional`);
        dimension.playSound("ignis.mob.ignis.burst", center, { volume: 3 });
    }, RITUAL_TICKS);
}

system.beforeEvents.startup.subscribe(({ blockComponentRegistry }) => {
    blockComponentRegistry.registerCustomComponent("ignis:altar_of_fire_interact", {
        onPlayerInteract({ block, player }) {
            if (!player || !block) return;
            const lit = block.permutation.getState("ignis:start");
            const center = block.center();
            if (lit) {
                // Lit but nobody is fighting (the world was closed mid-fight): put it out.
                if (!ignisNear(block.dimension, center, 96)) {
                    system.run(() => block.setPermutation(block.permutation.withState("ignis:start", false)));
                } else {
                    player.onScreenDisplay.setActionBar("§cIgnis is already awake.");
                }
                return;
            }
            const equipment = player.getComponent("minecraft:equippable");
            const hand = equipment?.getEquipment(EquipmentSlot.Mainhand);
            if (hand?.typeId !== ASHES) {
                player.onScreenDisplay.setActionBar("§6Offer §cBurning Ashes§6 to the Altar of Fire.");
                return;
            }
            if (ignisNear(block.dimension, center, 96)) {
                player.onScreenDisplay.setActionBar("§cIgnis is already awake.");
                return;
            }
            const creative = player.getGameMode() === GameMode.Creative || player.getGameMode() === GameMode.creative;
            // World changes outside the callback, which may run in a restricted context.
            system.run(() => {
                if (!creative) {
                    if (hand.amount > 1) {
                        hand.amount -= 1;
                        equipment.setEquipment(EquipmentSlot.Mainhand, hand);
                    } else {
                        equipment.setEquipment(EquipmentSlot.Mainhand, undefined);
                    }
                }
                startRitual(block, player);
            });
        },
    });
});

// When Ignis is gone (dead, killed, unloaded), its altar can be used again.
world.beforeEvents.entityRemove.subscribe(({ removedEntity }) => {
    if (removedEntity.typeId !== IGNIS) return;
    const raw = removedEntity.getDynamicProperty(ALTAR_PROPERTY);
    if (typeof raw !== "string") return;
    system.run(() => {
        try {
            const a = JSON.parse(raw);
            const block = world.getDimension(a.d).getBlock({ x: a.x, y: a.y, z: a.z });
            if (block?.typeId === ALTAR) block.setPermutation(block.permutation.withState("ignis:start", false));
        } catch {
            // unloaded chunk: the altar notices when someone uses it
        }
    });
});

// --- Combat options (config.js) -------------------------------------------------
function healthOf(entity) {
    const h = entity.getComponent("minecraft:health");
    if (!h) return undefined;
    return { h, frac: Math.max(0, Math.min(1, h.currentValue / h.effectiveMax)) };
}

function heal(entity, amount) {
    const hp = healthOf(entity);
    if (!hp || amount <= 0 || hp.h.currentValue <= 1) return;
    hp.h.setCurrentValue(Math.min(hp.h.effectiveMax, hp.h.currentValue + amount));
}

function healTag(ignis) {
    // Attacks mark Ignis with ignis:ignisH_<n>: n health drained per hit.
    for (const tag of ignis.getTags()) {
        const m = /^ignis:ignisH_(\d+)$/.exec(tag);
        if (m) return Number(m[1]);
    }
    return 0;
}

const extraDamage = new Set(); // entity ids hit by the enrage bonus this tick

world.afterEvents.entityHurt.subscribe(({ hurtEntity, damage, damageSource }) => {
    if (!isValid(hurtEntity)) return;
    const attacker = damageSource.damagingEntity;

    // Ignis hits something
    if (attacker?.typeId === IGNIS && hurtEntity.typeId !== IGNIS && isValid(attacker)) {
        lastHit.set(attacker.id, system.currentTick);
        maybeImpale(attacker);
        const drain = healTag(attacker) * cfg.ignis_health_changed_multiplier;
        if (drain > 0) heal(attacker, drain);
        if (cfg.ignis_enrage_enabled && !extraDamage.has(hurtEntity.id)) {
            const hp = healthOf(attacker);
            const bonus = hp ? damage * (1 - hp.frac) : 0; // up to +100% at low health
            if (bonus >= 0.5) {
                extraDamage.add(hurtEntity.id);
                hurtEntity.applyDamage(bonus, { cause: EntityDamageCause.fire });
                system.run(() => extraDamage.delete(hurtEntity.id));
            }
        }
        return;
    }

    // Something hits Ignis
    if (hurtEntity.typeId !== IGNIS || !attacker || attacker.typeId === IGNIS) return;
    const hp = healthOf(hurtEntity);
    if (!hp || hp.h.currentValue <= 1) return;
    const low = Math.max(0, Math.min(1, (0.5 - hp.frac) / 0.5)); // 0 at half health, 1 near death
    if (cfg.ignis_dodge_enabled && hp.frac < 0.5 && Math.random() < 0.05 + 0.55 * low) {
        heal(hurtEntity, damage);
        hurtEntity.dimension.playSound("ignis.mob.ignis.sword", hurtEntity.location, { pitch: 1.4 });
        hurtEntity.dimension.spawnParticle("ignis:ignis_jump", hurtEntity.location);
        return;
    }
    if (cfg.ignis_reduce_enabled && hp.frac < 0.5) {
        heal(hurtEntity, damage * (0.01 + 0.79 * low));
    }
});

// --- Impaling thrust ------------------------------------------------------------
// attack4__ is the sword thrust; when it connects, attack4T lifts the target on the
// sword (the JSON teleports Ignis' target in front of it while the tags last).
// Nothing in the JSON triggers attack4T: the original script did, on a hit.
const lastThrust = new Map(); // Ignis id -> tick of its last thrust
const lastHit = new Map();    // Ignis id -> tick it last hurt something
const lastImpale = new Map(); // Ignis id -> tick of its last lift

function maybeImpale(ignis) {
    const now = system.currentTick;
    const thrust = lastThrust.get(ignis.id);
    const hit = lastHit.get(ignis.id);
    if (thrust === undefined || hit === undefined) return;
    if (Math.abs(thrust - hit) > 2 || now - thrust > 3) return;
    if (now - (lastImpale.get(ignis.id) ?? -1000) < 80) return;
    lastImpale.set(ignis.id, now);
    system.runTimeout(() => {
        if (isValid(ignis)) ignis.triggerEvent("attack4T");
    }, 1);
}

// --- Fire orbs ------------------------------------------------------------------
// The orbs (ignis:ignis_fire) aim with a shooter whose projectile is "x" (none)
// and burst 0.05 s later: the fireball comes from here, at the orb's target, in
// the orb's colour (skin 0 fire, 1 soul, 2 abyss).
function nearestTarget(dimension, location) {
    return dimension.getPlayers({ location, maxDistance: 64, tags: ["ignis:ignis_target"], closest: 1 })[0];
}

function launchFireball(orb) {
    let from, dimension, skin, target;
    try {
        from = { ...orb.location };
        dimension = orb.dimension;
        skin = orb.getComponent("minecraft:skin_id")?.value ?? 0;
        target = orb.target;
    } catch {
        return;
    }
    if (!isValid(target)) target = nearestTarget(dimension, from);
    if (!target) return;
    const to = { x: target.location.x, y: target.location.y + 1, z: target.location.z };
    const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
    const len = Math.hypot(dx, dy, dz) || 1;
    const ball = dimension.spawnEntity("ignis:ignis_fireball", from);
    if (skin === 1) ball.triggerEvent("soul");
    else if (skin === 2) ball.triggerEvent("abyss");
    const projectile = ball.getComponent("minecraft:projectile");
    if (!projectile) return;
    const owner = dimension.getEntities({ type: IGNIS, location: from, maxDistance: 48, closest: 1 })[0];
    if (owner) projectile.owner = owner;
    const speed = skin === 2 ? 1.5 : 1.25;
    projectile.shoot({ x: (dx / len) * speed, y: (dy / len) * speed, z: (dz / len) * speed });
}

world.afterEvents.dataDrivenEntityTrigger.subscribe(({ entity, eventId }) => {
    if (entity.typeId === IGNIS && eventId === "attack4__") {
        lastThrust.set(entity.id, system.currentTick);
        maybeImpale(entity);
    } else if (entity.typeId === "ignis:ignis_fire" && (eventId === "a" || eventId === "c")) {
        launchFireball(entity);
    }
});

// --- Ground hits burn the floor (ignis_breaks_all_blocks: burning sigils) -------
const airborne = new Map(); // Ignis id -> lowest vertical speed while in the air

/**
 * Where the floor used to jump (it needed physics entities and lagged): flames,
 * and every few spots a burning sigil (ignis:ignis_strike: area fire damage),
 * removed after 2.5 s.
 */
let markerCount = 0;
const SIGIL_EVERY = 6;      // one sigil per this many shock-wave markers
const SIGIL_TICKS = 50;

function burnAt(dim, x, y, z, sigil) {
    let block;
    try {
        block = dim.getBlock({ x, y, z });
    } catch {
        return;
    }
    if (!block || block.isAir || block.isLiquid || !block.above()?.isAir) return;
    const top = { x: x + 0.5, y: y + 1.05, z: z + 0.5 };
    try {
        dim.spawnParticle("minecraft:basic_flame_particle", top);
        if (Math.random() < 0.35) dim.spawnParticle("minecraft:lava_particle", top);
    } catch {
        // decoration only
    }
    if (!sigil || !cfg.ignis_breaks_all_blocks) return;
    const mark = dim.spawnEntity("ignis:ignis_strike", { x: x + 0.5, y: y + 1, z: z + 0.5 });
    system.runTimeout(() => {
        if (isValid(mark)) mark.remove();
    }, SIGIL_TICKS);
}

// Ground hits summon rings of ignis:ignis_bl markers (the shock wave).
world.afterEvents.entitySpawn.subscribe(({ entity }) => {
    if (entity.typeId !== "ignis:ignis_bl" && entity.typeId !== "ignis:ignis_bla") return;
    let loc;
    try {
        loc = entity.location;
    } catch {
        return;
    }
    markerCount = (markerCount + 1) % SIGIL_EVERY;
    burnAt(entity.dimension, Math.floor(loc.x), Math.floor(loc.y) - 1, Math.floor(loc.z), markerCount === 0);
});

function slam(ignis) {
    const dim = ignis.dimension;
    const bx = Math.floor(ignis.location.x), by = Math.floor(ignis.location.y) - 1, bz = Math.floor(ignis.location.z);
    for (let dx = -3; dx <= 3; dx++) {
        for (let dz = -3; dz <= 3; dz++) {
            const d = Math.hypot(dx, dz);
            if (d > 3.2 || d < 1 || Math.random() < 0.4) continue;
            burnAt(dim, bx + dx, by, bz + dz, (dx === 3 || dx === -3 || dz === 3 || dz === -3) && (dx === 0 || dz === 0));
        }
    }
}

// --- Dashes ----------------------------------------------------------------------
// The attack timelines call "/scriptevent ignis:dash slash|thrust" a moment before
// each hit: Ignis lunges towards its target (or straight ahead) to reach it.
const DASH = { slash: 0.6, thrust: 1.15 };

system.afterEvents.scriptEventReceive.subscribe(({ id, message, sourceEntity: ignis }) => {
    if (id !== "ignis:dash" || ignis?.typeId !== IGNIS || !isValid(ignis)) return;
    let dir;
    try {
        const target = ignis.target;
        if (isValid(target) && target.dimension.id === ignis.dimension.id) {
            const dx = target.location.x - ignis.location.x, dz = target.location.z - ignis.location.z;
            if (Math.hypot(dx, dz) < 16) dir = { x: dx, z: dz };
        }
    } catch {
        dir = undefined;
    }
    if (!dir) {
        const v = ignis.getViewDirection();
        dir = { x: v.x, z: v.z };
    }
    const len = Math.hypot(dir.x, dir.z);
    if (len < 0.01) return;
    const power = DASH[message] ?? DASH.slash;
    ignis.applyImpulse({ x: (dir.x / len) * power, y: 0.08, z: (dir.z / len) * power });
});

system.runInterval(() => {
    for (const dimId of ["overworld", "nether", "the_end"]) {
        let list;
        try {
            list = world.getDimension(dimId).getEntities({ type: IGNIS });
        } catch {
            continue;
        }
        for (const ignis of list) {
            if (!isValid(ignis)) continue;
            const vy = ignis.getVelocity().y;
            if (!ignis.isOnGround) {
                airborne.set(ignis.id, Math.min(airborne.get(ignis.id) ?? 0, vy));
            } else if (airborne.has(ignis.id)) {
                const fall = airborne.get(ignis.id);
                airborne.delete(ignis.id);
                if (fall < -0.6) slam(ignis);
            }
        }
    }
}, 2);
