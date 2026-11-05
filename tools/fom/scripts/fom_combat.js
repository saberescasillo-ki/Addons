import { world, system, EntityDamageCause, MolangVariableMap } from "@minecraft/server";
import { getSetting, HEALTH_STEPS } from "./fom_settings.js";
import { BOSSES, RINGS } from "./fom_data.js";

// Figures of Malice combat, rebalanced (tools/fom_fix.py):
//   * the attacks' /damage rings (up to 140 damage, stacked, repeated every 0.04 s)
//     now come here as "/scriptevent xrworks:hit <ring>": one hit per target per
//     half second, nerfed values x the damage setting, capped by "max hit";
//   * the bosses' health follows the difficulty and the number of players;
//   * attack knockback is scaled, and players thrown up land softly;
//   * a boss stuck against a step of up to 2 blocks climbs it;
//   * while a boss winds up an attack, particles mark the area it will hit.

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const DIMENSIONS = ["overworld", "nether", "the_end"];
const lastHit = new Map(); // "<boss>:<target>" -> tick
const scriptHits = new Set(); // targets being hurt by this script right now

function inPlay(p) {
    try {
        const m = p.getGameMode().toLowerCase();
        return m === "survival" || m === "adventure";
    } catch {
        return true;
    }
}

function bossOf(entity) {
    return entity && BOSSES[entity.typeId];
}

function allBosses() {
    const out = [];
    for (const id of DIMENSIONS) {
        try {
            for (const type of Object.keys(BOSSES)) out.push(...world.getDimension(id).getEntities({ type }));
        } catch {
            // not loaded
        }
    }
    return out;
}

// --- damage ------------------------------------------------------------------------
function scaled(amount, target) {
    let dmg = amount * getSetting("damageMult");
    const cap = getSetting("maxHit");
    if (cap > 0 && target.typeId === "minecraft:player") dmg = Math.min(dmg, cap);
    return Math.max(0, dmg);
}

function hurt(target, boss, amount) {
    if (amount <= 0) return;
    scriptHits.add(target.id);
    try {
        target.applyDamage(amount, { cause: EntityDamageCause.entityAttack, damagingEntity: boss });
    } catch {
        // gone
    } finally {
        scriptHits.delete(target.id);
    }
}

system.afterEvents.scriptEventReceive.subscribe(({ id, message, sourceEntity: boss }) => {
    if (id !== "xrworks:hit" || !isValid(boss) || !bossOf(boss)) return;
    const rings = RINGS[message.trim()];
    if (!rings) return;
    const def = bossOf(boss);
    const at = boss.location;
    const reach = rings[rings.length - 1][0];
    const now = system.currentTick;
    let list;
    try {
        list = boss.dimension.getEntities({ location: at, maxDistance: reach, excludeFamilies: ["inanimate", def.family],
            excludeTypes: ["minecraft:item", "minecraft:xp_orb"] });
    } catch {
        return;
    }
    for (const t of list) {
        if (t.id === boss.id || BOSSES[t.typeId]) continue;
        const player = t.typeId === "minecraft:player";
        if (player ? !inPlay(t) : !getSetting("hitMobs")) continue;
        const key = `${boss.id}:${t.id}`;
        if (now - (lastHit.get(key) ?? -100) < 10) continue; // once per half second
        const d = Math.hypot(t.location.x - at.x, t.location.y - at.y, t.location.z - at.z);
        const ring = rings.find(([r]) => d <= r);
        if (!ring) continue;
        lastHit.set(key, now);
        hurt(t, boss, scaled(ring[1], t));
    }
});

// The bosses' own melee hit (minecraft:attack, already lowered in the JSON) also
// follows the damage setting and the cap.
world.afterEvents.entityHurt.subscribe(({ hurtEntity: t, damage, damageSource }) => {
    const boss = damageSource.damagingEntity;
    if (!isValid(t) || !bossOf(boss) || scriptHits.has(t.id) || damage <= 0) return;
    if (damageSource.cause !== EntityDamageCause.entityAttack) return;
    const want = scaled(damage, t);
    const h = t.getComponent("minecraft:health");
    if (!h) return;
    if (want < damage) {
        try {
            h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + (damage - want)));
        } catch {
            // dead
        }
    } else if (want > damage) {
        system.run(() => isValid(t) && hurt(t, boss, want - damage));
    }
});

// --- knockback (called by the attack scripts) -----------------------------------------------
export function fomKnockback(target, horizontal, vertical) {
    const k = getSetting("knockbackMult");
    if (k <= 0) return;
    target.applyKnockback({ x: horizontal.x * k, z: horizontal.z * k }, vertical * k);
    if (vertical * k > 0.8) softLanding(target);
}

export function fomImpulse(target, v) {
    const k = getSetting("knockbackMult");
    if (k <= 0) return;
    target.applyImpulse({ x: v.x * k, y: Math.min(v.y * k, 3), z: v.z * k });
}

function softLanding(player) {
    if (!getSetting("softLanding") || player.typeId !== "minecraft:player") return;
    try {
        player.addEffect("slow_falling", 50, { amplifier: 0, showParticles: false });
    } catch {
        // ignore
    }
}

// --- health ----------------------------------------------------------------------------------
function healthIndex(boss) {
    let k = getSetting("healthMult");
    if (getSetting("mpScaling")) {
        let n = 1;
        try {
            n = boss.dimension.getPlayers({ location: boss.location, maxDistance: 64 }).filter(inPlay).length || 1;
        } catch {
            n = 1;
        }
        k *= 1 + getSetting("mpBonus") * (n - 1);
    }
    let best = 0;
    HEALTH_STEPS.forEach((s, i) => {
        if (Math.abs(s - k) < Math.abs(HEALTH_STEPS[best] - k)) best = i;
    });
    return best;
}

world.afterEvents.entitySpawn.subscribe(({ entity }) => {
    if (!bossOf(entity)) return;
    system.runTimeout(() => {
        if (!isValid(entity)) return;
        const i = healthIndex(entity);
        entity.setDynamicProperty("xrworks:hp_step", i);
        try {
            entity.triggerEvent(`xrworks:set_hp_${i}`);
        } catch {
            // ignore
        }
    }, 2);
});

world.afterEvents.dataDrivenEntityTrigger.subscribe(({ entity, eventId }) => {
    const def = bossOf(entity);
    if (!def) return;
    if (eventId === def.phase2Event) {
        const i = entity.getDynamicProperty("xrworks:hp_step") ?? HEALTH_STEPS.indexOf(1);
        system.run(() => isValid(entity) && entity.triggerEvent(`xrworks:set_hp2_${i}`));
    } else if (eventId === "minecraft:delayed_attack_start") {
        telegraph(entity, def);
    }
});

// Dr. Lantern's phase-2 fury (Strength) only when the setting allows it.
system.runInterval(() => {
    if (getSetting("lanternFury")) return;
    for (const b of allBosses()) {
        if (b.typeId !== "xrworks:doctor_lantern") continue;
        try {
            if (b.getEffect("strength")) b.removeEffect("strength");
        } catch {
            // ignore
        }
    }
}, 40);

// --- climbing ----------------------------------------------------------------------------------
const climbCooldown = new Map();

function solid(dim, x, y, z) {
    try {
        const b = dim.getBlock({ x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) });
        return !!b && !b.isAir && !b.isLiquid;
    } catch {
        return false;
    }
}

system.runInterval(() => {
    if (!getSetting("climb")) return;
    const now = system.currentTick;
    for (const boss of allBosses()) {
        try {
            if (!boss.isOnGround || now < (climbCooldown.get(boss.id) ?? 0)) continue;
            const target = boss.target;
            if (!isValid(target)) continue;
            const at = boss.location;
            const dx = target.location.x - at.x, dz = target.location.z - at.z;
            const dist = Math.hypot(dx, dz);
            if (dist < 3) continue;
            const v = boss.getVelocity();
            if (Math.hypot(v.x, v.z) > 0.03) continue; // moving fine
            const fx = dx / dist, fz = dz / dist;
            const reach = (bossOf(boss).width ?? 1) / 2 + 0.6;
            const ax = at.x + fx * reach, az = at.z + fz * reach;
            const dim = boss.dimension;
            const wall = solid(dim, ax, at.y, az) || solid(dim, ax, at.y + 1, az);
            const tooHigh = solid(dim, ax, at.y + 2, az);
            if (!wall || tooHigh) continue;
            const up = solid(dim, ax, at.y + 1, az) ? 0.62 : 0.45; // 2 blocks or 1
            boss.applyImpulse({ x: fx * 0.28, y: up, z: fz * 0.28 });
            climbCooldown.set(boss.id, now + 20);
        } catch {
            // gone
        }
    }
}, 4);

// --- attack telegraphs -------------------------------------------------------------------------------
function telegraph(boss, def) {
    if (!getSetting("telegraph")) return;
    let variant = 0;
    try {
        variant = boss.getComponent("minecraft:variant")?.value ?? 0;
    } catch {
        return;
    }
    const hits = def.attacks[variant];
    if (!hits || !hits.length) return;
    const colour = new MolangVariableMap();
    colour.setColorRGBA("variable.color", { red: def.color[0], green: def.color[1], blue: def.color[2], alpha: 0.9 });
    const flash = new MolangVariableMap();
    flash.setColorRGBA("variable.color", { red: 1, green: 1, blue: 1, alpha: 1 });
    const start = system.currentTick;
    const end = start + Math.round(hits[hits.length - 1].t * 20);
    const runner = system.runInterval(() => {
        const now = system.currentTick;
        if (!isValid(boss) || now > end) {
            system.clearRun(runner);
            return;
        }
        const elapsed = (now - start) / 20;
        const next = hits.find((h) => h.t >= elapsed - 0.05);
        if (!next) return;
        const soon = next.t - elapsed;
        draw(boss, next.r, soon < 0.25 ? flash : colour, soon < 0.25 ? 1.6 : 1);
    }, 3);
}

function draw(boss, radius, colour, boost) {
    const dim = boss.dimension;
    const at = boss.location;
    const budget = Math.round(getSetting("telegraphDensity") * boost);
    const y = at.y + 0.08;
    const edge = Math.max(12, Math.round(radius * 4));
    try {
        for (let i = 0; i < edge; i++) {
            const a = (i / edge) * Math.PI * 2;
            dim.spawnParticle("xrworks:attack_zone", { x: at.x + Math.cos(a) * radius, y, z: at.z + Math.sin(a) * radius }, colour);
        }
        for (let i = 0; i < budget; i++) {
            const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * radius;
            dim.spawnParticle("xrworks:attack_zone", { x: at.x + Math.cos(a) * r, y, z: at.z + Math.sin(a) * r }, colour);
        }
    } catch {
        // unloaded
    }
}
