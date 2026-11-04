import { world, system, GameMode, EquipmentSlot, EntityDamageCause } from "@minecraft/server";
import { config } from "./config.js";

// Ignis' script, rewritten in readable form from the add-on's obfuscated core.js
// (its mechanics are kept: lunges, the homing leap, stuns, the blazing brand,
// lifesteal, the fireball shield, the damage cap...). Changes: the floor no longer
// jumps as physics blocks (it lagged): flames and burning sigils instead; Ignis
// only hunts players and golems; the great-sigil attack sends 4 rows (8 in the
// soul phases) and has a scattered-circles variant.

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


// --- Helpers ----------------------------------------------------------------------
const DIMENSIONS = ["overworld", "nether", "the_end"];
const ALLIES = ["minecraft:iron_golem", "minecraft:snow_golem"]; // besides players, what Ignis fights

function ignisList() {
    const out = [];
    for (const id of DIMENSIONS) {
        try {
            out.push(...world.getDimension(id).getEntities({ type: IGNIS }));
        } catch {
            // dimension not loaded
        }
    }
    return out;
}

function healthOf(entity) {
    try {
        return entity.getComponent("minecraft:health");
    } catch {
        return undefined;
    }
}

/** Sets health, clamped to [1, max] (as the original did: never kills). */
function setHealth(h, value) {
    try {
        h.setCurrentValue(Math.max(1, Math.min(value, h.effectiveMax)));
    } catch {
        // entity gone
    }
}

function healthFrac(entity) {
    const h = healthOf(entity);
    if (!h) return 1;
    return Math.max(0, Math.min(1, h.currentValue / (h.effectiveMax || 1)));
}

function variantOf(entity) {
    try {
        return entity.getComponent("minecraft:variant")?.value;
    } catch {
        return undefined;
    }
}

function isFighter(e) {
    // a valid target: a survival/adventure player, or a golem
    if (!isValid(e)) return false;
    if (e.typeId === "minecraft:player") return e.hasTag("ignis:gm_survival") || e.hasTag("ignis:gm_adventure");
    return ALLIES.includes(e.typeId);
}

/** Ignis' current target, else the one it locked on to, else the nearest fighter. */
function targetOf(ignis, useLock = true) {
    try {
        const t = ignis.target;
        if (isFighter(t)) {
            ignis.setDynamicProperty("ignis:ignisLockTgtId", t.id);
            return t;
        }
    } catch {
        // no target
    }
    const dim = ignis.dimension;
    if (useLock) {
        const id = ignis.getDynamicProperty("ignis:ignisLockTgtId");
        if (id) {
            const locked = world.getEntity?.(id);
            if (isFighter(locked) && locked.dimension.id === dim.id) return locked;
        }
    }
    let best, bestD = Infinity;
    const at = ignis.location;
    const candidates = [
        ...dim.getPlayers({ location: at, maxDistance: 48 }),
        ...ALLIES.flatMap((type) => dim.getEntities({ type, location: at, maxDistance: 48 })),
    ];
    for (const c of candidates) {
        if (!isFighter(c)) continue;
        const d = Math.hypot(c.location.x - at.x, c.location.y - at.y, c.location.z - at.z);
        if (d < bestD) {
            best = c;
            bestD = d;
        }
    }
    if (best) ignis.setDynamicProperty("ignis:ignisLockTgtId", best.id);
    return best;
}

function facing(dx, dy, dz) {
    const flat = Math.hypot(dx, dz) || 0.0001;
    return { x: -Math.atan2(dy, flat) * (180 / Math.PI), y: Math.atan2(-dx, dz) * (180 / Math.PI) };
}

/** Pushes `who` along `by`'s view direction (a lunge). Airborne entities get a third.
 *  Players cannot take impulses: they get knockback of `kb` (when given) instead. */
function push(who, by, power, y, groundOnly = true, kb) {
    try {
        const v = by.getViewDirection();
        const up = y || v.y * power;
        try {
            who.clearVelocity();
            if (!groundOnly || who.isOnGround) who.applyImpulse({ x: v.x * power, y: up, z: v.z * power });
            else who.applyImpulse({ x: (v.x * power) / 3, y: up / 3, z: (v.z * power) / 3 });
        } catch {
            if (kb !== undefined) who.applyKnockback({ x: v.x * kb, z: v.z * kb }, up);
        }
    } catch {
        // entity gone or cannot be pushed
    }
}

const lunge = (ignis, power, y, groundOnly = true) => push(ignis, ignis, power, y, groundOnly);

/** Highest solid block near (x, y, z) with room above, or y - 1 when none. */
function groundAt(dim, x, y, z) {
    const bx = Math.floor(x), bz = Math.floor(z), by = Math.floor(y);
    for (let yy = by + 3; yy >= by - 5; yy--) {
        try {
            const b = dim.getBlock({ x: bx, y: yy, z: bz });
            if (b && !b.isAir && !b.isLiquid && b.above()?.isAir) return yy;
        } catch {
            return by - 1;
        }
    }
    return by - 1;
}

// --- Distances, healing tags, stuns (every tick) ----------------------------------
const taggedTargets = new Map(); // non-player entity id -> entity carrying ignis:ignis_target

system.runInterval(() => {
    const current = new Set();
    for (const ignis of ignisList()) {
        try {
            const t = ignis.target;
            if (isValid(t)) {
                // the attack choice (root event) reads these: lxz >= 16 is the leap
                const dx = ignis.location.x - t.location.x, dz = ignis.location.z - t.location.z;
                ignis.setProperty("ignis:lxz", Math.min(200, Math.hypot(dx, dz)));
                ignis.setProperty("ignis:ly", Math.min(200, Math.abs(ignis.location.y - t.location.y)));
                if (t.typeId !== "minecraft:player") {
                    t.addTag("ignis:ignis_target"); // the fire orbs aim at this tag
                    taggedTargets.set(t.id, t);
                    current.add(t.id);
                }
            }
        } catch {
            // target gone
        }
        const h = healthOf(ignis);
        if (h && h.currentValue >= 1.5) {
            for (const tag of ignis.getTags()) {
                if (!tag.startsWith("ignis:ignisHealth_")) continue;
                ignis.removeTag(tag);
                setHealth(h, h.currentValue + 5 * Number(tag.slice("ignis:ignisHealth_".length) || 1));
                break;
            }
        }
    }
    for (const [id, e] of taggedTargets) {
        if (current.has(id)) continue;
        taggedTargets.delete(id);
        try {
            e.removeTag("ignis:ignis_target");
        } catch {
            // gone
        }
    }
    // Roars and slams tag players with ignis:ignisS_<seconds>: they are stunned.
    for (const player of world.getAllPlayers()) {
        for (const tag of player.getTags()) {
            if (!tag.startsWith("ignis:ignisS_")) continue;
            player.removeTag(tag);
            if (player.hasTag("ignis:gm_survival") || player.hasTag("ignis:gm_adventure")) {
                stun(player, Number(tag.slice("ignis:ignisS_".length)) || 1);
            }
            break;
        }
    }
});

function stun(entity, seconds) {
    const ticks = Math.round(20 * seconds);
    try {
        if (entity.typeId === "minecraft:player") {
            entity.onScreenDisplay.setActionBar({
                rawtext: [{ text: "§cStunned by " }, { translate: "entity.ignis:ignis.name" },
                    { text: `§c for ${seconds} seconds - unable to act.` }],
            });
            entity.addEffect("slowness", ticks, { amplifier: 5, showParticles: false });
            entity.runCommand("inputpermission set @s movement disabled");
            entity.runCommand(`camerashake add @s 0.1 ${seconds} rotational`);
            system.runTimeout(() => unstun(entity), ticks);
        } else {
            entity.addEffect("slowness", ticks, { amplifier: 255, showParticles: false });
            entity.addEffect("weakness", ticks, { amplifier: 255, showParticles: false });
        }
    } catch {
        // gone
    }
}

function unstun(player) {
    try {
        if (isValid(player)) player.runCommand("inputpermission set @s movement enabled");
    } catch {
        // gone
    }
}

// --- Blazing brand -----------------------------------------------------------------
// Ignis' hits brand their victim (up to 5 stacks, for ~12 s): its lifesteal and the
// fireballs' healing are multiplied by the stacks.
const BRAND = "ignis:blazing_brand";
const BRAND_TIME = "ignis:blazing_brand/";
const branded = new Map();

function brandOf(e) {
    try {
        return Number(e.getDynamicProperty(BRAND)) || 0;
    } catch {
        return 0;
    }
}

function addBrand(e, stacks, seconds) {
    try {
        e.setDynamicProperty(BRAND, Math.min(5, brandOf(e) + stacks));
        if ((Number(e.getDynamicProperty(BRAND_TIME)) || 0) < seconds) e.setDynamicProperty(BRAND_TIME, seconds);
        branded.set(e.id, e);
    } catch {
        // gone
    }
}

system.runInterval(() => {
    for (const [id, e] of branded) {
        try {
            if (!isValid(e)) {
                branded.delete(id);
                continue;
            }
            const left = (Number(e.getDynamicProperty(BRAND_TIME)) || 0) - 1;
            if (left > 0) {
                e.setDynamicProperty(BRAND_TIME, left);
            } else {
                e.setDynamicProperty(BRAND, 0);
                e.setDynamicProperty(BRAND_TIME, 0);
                branded.delete(id);
            }
        } catch {
            branded.delete(id);
        }
    }
}, 20);

world.afterEvents.playerSpawn.subscribe(({ player }) => {
    unstun(player);
    try {
        if (player.getDynamicProperty(BRAND_TIME)) {
            player.setDynamicProperty(BRAND, 0);
            player.setDynamicProperty(BRAND_TIME, 0);
        }
    } catch {
        // ignore
    }
});

// --- Damage ------------------------------------------------------------------------
const DODGE_MIN = 0.05, DODGE_MAX = 0.6, REDUCE_MIN = 0.01, REDUCE_MAX = 0.8, ENRAGE = 1;
const busy = new Set(); // "<id>:<kind>" guards, cleared next tick

function once(key) {
    if (busy.has(key)) return false;
    busy.add(key);
    system.run(() => busy.delete(key));
    return true;
}

function percentDamage(victim, damage) {
    // big mobs (bosses) lose the same share of health a 100-health mob would
    const h = healthOf(victim);
    if (h && h.effectiveMax > 100 && once(`${victim.id}:pct`)) {
        try {
            victim.applyDamage(h.effectiveMax * (damage / 100) - damage, { cause: EntityDamageCause.override });
        } catch {
            // ignore
        }
    }
}

function faceAndThrow(victim, ignisTag, up, seconds) {
    const rot = victim.getRotation();
    try {
        victim.runCommand(`tp ~~~ facing @e[tag=${ignisTag},c=1]`);
        victim.setRotation({ x: 0, y: victim.getRotation().y });
    } catch {
        // cannot be turned
    }
    push(victim, victim, -1.4, up, true, -4.5);
    stun(victim, seconds);
    try {
        victim.setRotation(rot);
    } catch {
        // ignore
    }
}

world.afterEvents.entityHurt.subscribe((ev) => {
    try {
        onHurt(ev);
    } catch {
        // an entity vanished mid-hit
    }
});

function onHurt({ hurtEntity: victim, damage, damageSource }) {
    if (!isValid(victim)) return;
    const attacker = isValid(damageSource.damagingEntity) ? damageSource.damagingEntity : undefined;
    const vh = healthOf(victim);

    // Ignis is hurt: no single hit takes more than 20; low on health it dodges or shrugs.
    if (victim.typeId === IGNIS && vh && vh.currentValue >= 1.5) {
        let back = damage > 20 ? damage - 20 : 0;
        const frac = healthFrac(victim);
        if (cfg.ignis_dodge_enabled && Math.random() < DODGE_MIN + (DODGE_MAX - DODGE_MIN) * (1 - frac)) {
            back = damage;
            try {
                victim.dimension.spawnParticle("ignis:ignis_jump", victim.location);
            } catch {
                // decoration
            }
        } else if (cfg.ignis_reduce_enabled) {
            back = Math.max(back, damage * (REDUCE_MIN + (REDUCE_MAX - REDUCE_MIN) * (1 - frac)));
        }
        if (back > 0) setHealth(vh, vh.currentValue + back);
    }

    // Enrage: everything of Ignis' hits players harder as Ignis loses health.
    if (cfg.ignis_enrage_enabled && attacker && attacker.typeId.startsWith("ignis:") && victim.typeId === "minecraft:player"
        && damage > 0 && once(`${victim.id}:enrage`)) {
        const ignis = attacker.typeId === IGNIS ? attacker
            : attacker.dimension.getEntities({ type: IGNIS, location: attacker.location, maxDistance: 200, closest: 1 })[0];
        const bonus = damage * ENRAGE * (1 - (ignis ? healthFrac(ignis) : 1));
        if (bonus > 0.25) {
            try {
                victim.applyDamage(bonus, { cause: EntityDamageCause.override });
            } catch {
                // ignore
            }
        }
    }

    if (!attacker) {
        const proj = damageSource.damagingProjectile;
        if (proj?.typeId === "ignis:ignis_fireball") addBrand(victim, 1, 10);
        return;
    }

    switch (attacker.typeId) {
        case IGNIS: {
            if (victim.typeId === IGNIS) return;
            const variant = variantOf(attacker);
            const phase = attacker.getProperty("ignis:phase") ?? 1;
            for (const tag of attacker.getTags()) {
                if (!tag.startsWith("ignis:ignisH_")) continue;
                if (variant !== 5 && variant !== 6) {
                    try {
                        victim.setOnFire(2.5, true);
                    } catch {
                        // fire immune
                    }
                }
                if (variant === 5) {
                    if (phase >= 2) addBrand(victim, 1, 12);
                } else {
                    addBrand(victim, phase >= 2 && (variant === 10 || variant === 13) ? 2 : 1, 12);
                }
                const ah = healthOf(attacker);
                if (ah && ah.currentValue >= 1.5) {
                    const drain = Number(tag.slice("ignis:ignisH_".length)) || 0;
                    setHealth(ah, ah.currentValue + drain * (brandOf(victim) || 1) * cfg.ignis_health_changed_multiplier);
                }
                break;
            }
            if (attacker.hasTag("ignis:ignisA2")) {
                // the grab: the victim is turned to Ignis, pulled in and stunned
                if (once(`${attacker.id}:a2sound`)) attacker.dimension.playSound("ignis.mob.ignis.attack2", victim.location, { volume: 2 });
                faceAndThrow(victim, "ignis:ignisA2", 0.5, 3);
            } else if (attacker.hasTag("ignis:ignisA6c")) {
                if (once(`${attacker.id}:a6sound`)) attacker.dimension.playSound("ignis.mob.ignis.attack2", victim.location, { volume: 2 });
                faceAndThrow(victim, "ignis:ignisA6c", 1.25, 2);
            } else if (attacker.hasTag("ignis:ignisA10")) {
                push(victim, victim, 0, 0.75, true, 0); // the spin throws its victims up
            }
            percentDamage(victim, damage);
            if (once(`${attacker.id}:combo`)) {
                // the thrust lifts what it pierces; the first sweep chains into the second
                if (variant === 5 && (healthOf(victim)?.currentValue ?? 0) > 0) attacker.triggerEvent("attack4T");
                if (variant === 15) attacker.triggerEvent("attack8..");
            }
            return;
        }
        case "ignis:ignis_strike":
        case "ignis:ignis_strike_soul":
            try {
                victim.setOnFire(2.5, true);
            } catch {
                // fire immune
            }
            addBrand(victim, 1, 10);
            if (variantOf(attacker) === 1) percentDamage(victim, damage);
            return;
        case "ignis:ignis_fire":
        case "ignis:ignis_fireball":
            addBrand(victim, 1, 10);
            percentDamage(victim, damage);
            return;
        default:
            if (damageSource.damagingProjectile?.typeId === "ignis:ignis_fireball") addBrand(victim, 1, 10);
    }
}

// Below 30 % in the soul phases, every 10 % lost rings out.
world.afterEvents.entityHealthChanged.subscribe(({ entity, oldValue, newValue }) => {
    try {
        if ((entity.getProperty("ignis:phase") ?? 1) < 2) return;
        const step = (healthOf(entity)?.effectiveMax ?? 0) / 10;
        if (!step) return;
        for (let i = 1; i <= 3; i++) {
            if (oldValue / step >= i && newValue / step < i) entity.runCommand("playsound ignis.mob.ignis.impact @a ~~~");
        }
    } catch {
        // ignore
    }
}, { entityTypes: [IGNIS] });

// --- Fire orbs and fireballs ----------------------------------------------------------
// The orbs (ignis:ignis_fire) aim with a shooter whose projectile is "x" (none)
// and burst 0.05 s later: the fireball comes from here, at the orb's target, in
// the orb's colour (skin 0 fire, 1 soul, 2 abyss).
function orbTarget(orb) {
    try {
        if (isFighter(orb.target)) return orb.target;
    } catch {
        // none
    }
    const dim = orb.dimension, at = orb.location;
    const tagged = dim.getEntities({ tags: ["ignis:ignis_target"], location: at, maxDistance: 64, closest: 1 })[0];
    return isFighter(tagged) ? tagged : undefined;
}

function launchFireball(orb) {
    let from, dimension, skin, target;
    try {
        from = { ...orb.location };
        dimension = orb.dimension;
        skin = orb.getComponent("minecraft:skin_id")?.value ?? 0;
        target = orbTarget(orb);
    } catch {
        return;
    }
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

world.afterEvents.projectileHitEntity.subscribe((ev) => {
    if (ev.projectile?.typeId !== "ignis:ignis_fireball") return;
    try {
        const hit = ev.getEntityHit()?.entity;
        if (!isValid(hit) || hit.typeId.startsWith("ignis:ignis_fire")) return;
        const source = ev.source;
        if (source && hit.id === source.id) return;
        if (!source || source.typeId.startsWith("ignis:")) {
            // Ignis' fireball found its mark: Ignis drinks from it
            if (hit.typeId.startsWith("ignis:")) return;
            const ignis = hit.dimension.getEntities({ type: IGNIS, location: hit.location, maxDistance: 96, closest: 1 })[0];
            const h = ignis && healthOf(ignis);
            if (h && h.currentValue >= 1.5) setHealth(h, h.currentValue + 5 * (brandOf(hit) || 1));
        } else if (hit.typeId === IGNIS) {
            // a fireball sent back by a player cracks Ignis' shield
            const h = healthOf(source);
            if (h) setHealth(h, h.currentValue + 5 * (brandOf(source) || 1) * cfg.ignis_health_changed_multiplier);
            hit.triggerEvent("shield");
        }
    } catch {
        // gone
    }
});

// --- Burning sigils where the floor used to jump ----------------------------------
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

// Ground hits summon ignis:ignis_bl / ignis_bla markers (the shock wave).
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

/** Burns the floor at offsets (right, forward) from Ignis, like ^r^^f. */
function burnPattern(ignis, offsets) {
    const v = ignis.getViewDirection();
    const len = Math.hypot(v.x, v.z) || 1;
    const f = { x: v.x / len, z: v.z / len }, r = { x: -f.z, z: f.x };
    const at = ignis.location, dim = ignis.dimension;
    for (const [side, ahead] of offsets) {
        const x = at.x + f.x * ahead + r.x * side, z = at.z + f.z * ahead + r.z * side;
        markerCount = (markerCount + 1) % SIGIL_EVERY;
        burnAt(dim, Math.floor(x), groundAt(dim, x, at.y, z), Math.floor(z), markerCount === 0);
    }
}

// attack6S: the sword splits the floor ahead in three waves
const SPLIT_WAVES = [
    [[2, 2], [2, 3], [1, 3], [1, 4], [-2, 2], [-2, 3], [-1, 3], [-1, 4]],
    [[0, 5], [1, 5], [2, 5], [3, 5], [3, 4], [4, 5], [1, 6], [2, 6], [-1, 5], [-2, 5], [-3, 5], [-3, 4], [-4, 5], [-1, 6], [-2, 6]],
    [[0, 7], [0, 8], [1, 7], [2, 7], [3, 7], [4, 7], [3, 6], [4, 6], [5, 6], [1, 8], [2, 8], [-1, 7], [-2, 7], [-3, 7], [-4, 7],
        [-3, 6], [-4, 6], [-5, 6], [-1, 8], [-2, 8]],
];

function splitFloor(ignis) {
    SPLIT_WAVES.forEach((wave, i) => system.runTimeout(() => {
        if (!isValid(ignis)) return;
        ignis.dimension.playSound("ignis.mob.ignis.attack1", ignis.location, { volume: 2 });
        burnPattern(ignis, wave.map(([s, a]) => [s * SIZE, a * SIZE]));
    }, 2 * (i + 1)));
}

// --- The great sigil (attack11) ------------------------------------------------------
// A rune burns under Ignis, then its sword strikes the ground: rows of sigils run out
// in 4 directions (8 in the soul phases), or, the scattered variant, circles erupt
// all around. Sigils never hurt Ignis (their damage skips its family).
const SIZE = 1.154;                     // Ignis' scale (ignis_fix.py)
const ROW = [8.5, 12.75, 17, 21.25, 25.5, 29.75, 34, 38.25].map((d) => d * SIZE);

function sigil(dim, x, y, z, step) {
    try {
        const gy = groundAt(dim, x, y, z) + 1;
        dim.spawnEntity("ignis:ignis_strike", { x, y: gy, z }, { spawnEvent: `ignis${step}` });
    } catch {
        // unloaded or blocked
    }
}

function sigilRows(ignis) {
    const v = ignis.getViewDirection();
    const len = Math.hypot(v.x, v.z) || 1;
    const f = { x: v.x / len, z: v.z / len };
    const dirs = (ignis.getProperty("ignis:phase") ?? 1) >= 2 ? 8 : 4;
    const at = { ...ignis.location }, dim = ignis.dimension;
    const ways = [];
    for (let i = 0; i < dirs; i++) {
        const a = (i * 2 * Math.PI) / dirs;
        ways.push({ x: f.x * Math.cos(a) - f.z * Math.sin(a), z: f.x * Math.sin(a) + f.z * Math.cos(a) });
    }
    ROW.forEach((dist, step) => system.runTimeout(() => {
        for (const w of ways) sigil(dim, at.x + w.x * dist, at.y, at.z + w.z * dist, step + 1);
    }, step));
}

function scatteredCircles(ignis) {
    const soul = (ignis.getProperty("ignis:phase") ?? 1) >= 2;
    const count = soul ? 40 : 28;
    const at = { ...ignis.location }, dim = ignis.dimension;
    const spots = [];
    for (let tries = 0; spots.length < count && tries < count * 12; tries++) {
        const a = Math.random() * 2 * Math.PI;
        const d = 4 + Math.sqrt(Math.random()) * (soul ? 24 : 20); // even spread over the disc
        const p = { x: at.x + Math.cos(a) * d, z: at.z + Math.sin(a) * d };
        if (spots.every((q) => Math.hypot(q.x - p.x, q.z - p.z) >= 3.2)) spots.push(p);
    }
    spots.forEach((p, i) => system.runTimeout(() => {
        sigil(dim, p.x, at.y, p.z, 1 + Math.floor(Math.random() * 8));
    }, Math.floor(i / 2)));
}

// --- Leaps -----------------------------------------------------------------------------
/** attack9 / attack10: a ballistic leap at the target... */
function leap(ignis, up) {
    const t = targetOf(ignis);
    if (!t) return;
    const dx = t.location.x - ignis.location.x, dz = t.location.z - ignis.location.z;
    const flat = Math.max(0.1, Math.hypot(dx, dz));
    const speed = Math.min(32, flat) / ((2 * up) / 0.08); // lands on the target
    const rot = facing(dx, up, dz);
    try {
        ignis.setRotation(rot);
        ignis.setDynamicProperty("ignis:ignisLockYaw", rot.y);
        ignis.setDynamicProperty("ignis:ignisLockPitch", rot.x);
        ignis.clearVelocity();
        ignis.applyImpulse({ x: (dx / flat) * speed, y: up, z: (dz / flat) * speed });
    } catch {
        // gone
    }
}

/** ...steering towards its target while airborne. */
function home(ignis, n = 0) {
    try {
        if (!isValid(ignis)) return;
        const v = variantOf(ignis);
        if ((v !== 18 && v !== 20) || (n >= 3 && ignis.isOnGround)) {
            ignis.setDynamicProperty("ignis:ignisLockYaw", undefined);
            return;
        }
        const yaw = ignis.getDynamicProperty("ignis:ignisLockYaw");
        const pitch = ignis.getDynamicProperty("ignis:ignisLockPitch");
        if (typeof yaw === "number") {
            ignis.setRotation({ x: typeof pitch === "number" ? pitch : ignis.getRotation().x, y: yaw });
        }
        const t = targetOf(ignis);
        if (t) {
            const dx = t.location.x - ignis.location.x, dz = t.location.z - ignis.location.z;
            const d = Math.hypot(dx, dz);
            if (d > 0.5) {
                const p = Math.min(0.18, d * 0.03);
                ignis.applyImpulse({ x: (dx / d) * p, y: 0, z: (dz / d) * p });
            }
        }
        system.runTimeout(() => home(ignis, n + 1), 2);
    } catch {
        // gone
    }
}

/** Stuck inside blocks (damage_sensor's "break", only with mobGriefing): clear room. */
function enclosed(ignis) {
    const dim = ignis.dimension;
    const bx = Math.floor(ignis.location.x), by = Math.floor(ignis.location.y), bz = Math.floor(ignis.location.z);
    const solid = (dx, dy, dz) => {
        try {
            const b = dim.getBlock({ x: bx + dx, y: by + dy, z: bz + dz });
            return !!b && !b.isAir && !b.isLiquid;
        } catch {
            return false;
        }
    };
    const sides = [[1, 0], [-1, 0], [0, 1], [0, -1]].filter(([dx, dz]) => solid(dx, 0, dz) && solid(dx, 1, dz)).length;
    return sides >= 4 && solid(0, 2, 0) && solid(0, 3, 0);
}

// --- Ignis' events ---------------------------------------------------------------------
// The attack timelines fire these JSON events (most are empty in the JSON: the
// script gives them their movement).
function thrustPower(lxz) {
    // the impaling thrust's lunge: reaches the target, and at least 1.725
    const reach = lxz <= 5 ? 3.5 : lxz < 12 ? lxz / 2 - 1.5 : 4.5;
    return Math.max(1.725, reach);
}

world.afterEvents.dataDrivenEntityTrigger.subscribe(({ entity, eventId }) => {
    if (entity.typeId === "ignis:ignis_fire") {
        if (eventId === "a" || eventId === "c") launchFireball(entity);
        return;
    }
    if (entity.typeId !== IGNIS || !isValid(entity)) return;
    const ignis = entity;
    let lxz = 2.3;
    try {
        const t = ignis.target;
        if (isValid(t)) {
            lxz = Math.min(200, Math.hypot(ignis.location.x - t.location.x, ignis.location.z - t.location.z));
            ignis.setProperty("ignis:lxz", lxz);
            ignis.setProperty("ignis:ly", Math.min(200, Math.abs(ignis.location.y - t.location.y)));
        } else {
            lxz = ignis.getProperty("ignis:lxz") ?? 2.3;
        }
    } catch {
        // keep the default
    }
    switch (eventId) {
        case "break":
            if (enclosed(ignis)) ignis.runCommand("fill ~1 ~ ~1 ~-1 ~4 ~-1 air");
            break;
        case "move_3":
            if (lxz >= 2.25) lunge(ignis, 1.5);
            break;
        case "move2":
            if (lxz >= 2.25) lunge(ignis, 1);
            break;
        case "move3":
            if (lxz >= 2.25) lunge(ignis, lxz < 3.25 ? 1 : 1.5);
            break;
        case "attack2_":
            if (lxz > 1) lunge(ignis, Math.min(lxz, 3.5) / 2 - 0.5);
            break;
        case "attack4_":
            lunge(ignis, thrustPower(lxz));
            break;
        case "attack6C_":
            lunge(ignis, Math.min(lxz, 15) / 3.5);
            break;
        case "attack6S_":
            splitFloor(ignis);
            break;
        case "attack7_":
            if (lxz > 1.5) lunge(ignis, Math.min(lxz, 6.5) / 3 - 0.5);
            break;
        case "attack9_":
            leap(ignis, 1.6);
            home(ignis, 0);
            break;
        case "attack11_":
            if (ignis.getProperty("ignis:scatter")) scatteredCircles(ignis);
            else sigilRows(ignis);
            break;
        case "attack12T_":
            lunge(ignis, Math.min(lxz, 24) / 3.5);
            break;
        case "variant":
        case "ignisDeath":
            for (const tag of ignis.getTags()) if (tag.startsWith("ignis:ignis")) ignis.removeTag(tag);
            break;
        default:
            break;
    }
});

// --- Short dashes ------------------------------------------------------------------------
// Slashes with no lunge of their own call "/scriptevent ignis:dash slash" a moment
// before the hit: if the target is a little out of reach, Ignis steps in.
system.afterEvents.scriptEventReceive.subscribe(({ id, sourceEntity: ignis }) => {
    if (id !== "ignis:dash" || ignis?.typeId !== IGNIS || !isValid(ignis)) return;
    let dir, dist = 0;
    try {
        const t = ignis.target;
        if (isValid(t) && t.dimension.id === ignis.dimension.id) {
            const dx = t.location.x - ignis.location.x, dz = t.location.z - ignis.location.z;
            dist = Math.hypot(dx, dz);
            if (dist < 16) dir = { x: dx, z: dz };
        }
    } catch {
        dir = undefined;
    }
    if (dir && dist < 2.5) return; // already in reach
    if (!dir) {
        const v = ignis.getViewDirection();
        dir = { x: v.x, z: v.z };
    }
    const len = Math.hypot(dir.x, dir.z);
    if (len < 0.01) return;
    const power = 0.6;
    ignis.applyImpulse({ x: (dir.x / len) * power, y: 0.08, z: (dir.z / len) * power });
});

// --- Landings burn the floor -----------------------------------------------------------
const airborne = new Map(); // Ignis id -> lowest vertical speed while in the air

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

system.runInterval(() => {
    for (const ignis of ignisList()) {
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
}, 2);
