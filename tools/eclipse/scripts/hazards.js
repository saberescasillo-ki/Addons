import { system, EntityDamageCause } from "@minecraft/server";
import { C, particle, ring, flatRing, disc, safe, target, waveDecal, beam, burst, sound, gem, unshape, shapeCount } from "./fx.js";
import { level } from "./settings.js";

// Everything that can hurt: bullets, celestial rays, growing zones, ground waves and
// lasers. They are simulated here (cheap) and drawn with particles; nothing is an entity.
// They hurt everything alive in the arena: players (in survival/adventure) and mobs.
//
// Bullets fly on a flat plane 1.1 blocks above the arena floor: dodge them by moving.
// Each bullet is a 3D diamond (a small model entity) that the script moves; past
// MAX_GEMS at once, extra bullets are drawn with particles instead.

export const PLANE = 1.1;
const BODY_R = 0.32, BODY_H = 1.8;
const MAX_GEMS = 100;
const HIT_COOLDOWN = 10; // the same kind of hazard hurts a target at most twice a second
const IGNORE = ["minecraft:item", "minecraft:xp_orb", "minecraft:armor_stand", "minecraft:arrow", "minecraft:snowball",
    "minecraft:egg", "minecraft:ender_pearl", "minecraft:fireball", "minecraft:small_fireball", "minecraft:wind_charge_projectile",
    "minecraft:painting", "minecraft:leash_knot", "minecraft:tnt", "minecraft:falling_block", "minecraft:fishing_hook",
    "minecraft:thrown_trident", "minecraft:splash_potion", "minecraft:lingering_potion", "minecraft:area_effect_cloud",
    "minecraft:lightning_bolt", "minecraft:ender_crystal", "minecraft:eye_of_ender_signal"];

const bullets = [];
const hazards = [];
const cooldown = new Map(); // "<kind>:<entity id>" -> tick of the last hit

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);

export function inPlay(p) {
    try {
        const m = String(p.getGameMode()).toLowerCase();
        return m === "survival" || m === "adventure";
    } catch {
        return false;
    }
}

const center = (a) => ({ x: a.cx, y: a.floor + 2, z: a.cz });
const keyOf = (dim, a) => `${dim.id}:${a.cx}:${a.cz}`;

// Everything asked about an arena is worked out once per tick (the game's queries are
// what costs most; asking again in the same tick is free).
const tickMemo = { tick: -1, map: new Map() };
function memo(key, fn) {
    const now = system.currentTick;
    if (tickMemo.tick !== now) {
        tickMemo.tick = now;
        tickMemo.map.clear();
    }
    if (!tickMemo.map.has(key)) tickMemo.map.set(key, fn());
    return tickMemo.map.get(key);
}

/** Players fighting in this arena. */
export function arenaPlayers(dim, a) {
    return memo(`p:${keyOf(dim, a)}`, () => {
        try {
            return dim.getPlayers({ location: center(a), maxDistance: a.R + 8 })
                .filter((p) => inPlay(p) && Math.abs(p.location.y - a.floor) < 14);
        } catch {
            return [];
        }
    });
}

const mobCache = new Map(); // arena key -> {tick, list}

/** Mobs in this arena (anything alive that is not the Eclipse), searched every 10 ticks. */
export function arenaMobs(dim, a) {
    return memo(`m:${keyOf(dim, a)}`, () => findMobs(dim, a));
}

function findMobs(dim, a) {
    const key = keyOf(dim, a);
    const now = system.currentTick;
    const c = mobCache.get(key);
    if (c && now - c.tick < 10) return c.list.filter(isValid);
    let list = [];
    try {
        list = dim.getEntities({ location: center(a), maxDistance: a.R + 6, excludeFamilies: ["eclipse", "inanimate", "player"],
            excludeTypes: IGNORE }).filter((e) => Math.abs(e.location.y - a.floor) < 14 && !!e.getComponent("minecraft:health"));
    } catch {
        list = [];
    }
    mobCache.set(key, { tick: now, list });
    return list;
}

/** Everything the Eclipse fights here. */
export const arenaTargets = (dim, a) => memo(`t:${keyOf(dim, a)}`, () => [...arenaPlayers(dim, a), ...arenaMobs(dim, a)]);

/** The same, with their positions read once this tick: {id, typeId, location, e}. */
export const arenaBodies = (dim, a) => memo(`b:${keyOf(dim, a)}`, () => arenaTargets(dim, a).map((e) => {
    try {
        return { id: e.id, typeId: e.typeId, location: e.location, e };
    } catch {
        return undefined;
    }
}).filter(Boolean));

export function hurt(target, amount, owner, cause = EntityDamageCause.entityAttack, kind) {
    const e = target.e ?? target;
    if (kind) {
        const key = `${kind}:${e.id}`, now = system.currentTick;
        if (now - (cooldown.get(key) ?? -100) < HIT_COOLDOWN) return false;
        cooldown.set(key, now);
    }
    const dmg = amount * level().dmg;
    if (dmg <= 0) return false;
    try {
        if (isValid(owner)) e.applyDamage(dmg, { cause, damagingEntity: owner });
        else e.applyDamage(dmg, { cause });
        return true;
    } catch {
        return false;
    }
}

// --- bullets -------------------------------------------------------------------------------
function outside(b, x, z) {
    const a = b.arena;
    const dx = x - a.cx, dz = z - a.cz;
    return b.square ? Math.max(Math.abs(dx), Math.abs(dz)) > a.R + 3 : Math.hypot(dx, dz) > a.R + 3;
}

/** Ticks a straight (maybe accelerating) bullet has left before it leaves the arena. */
function ticksLeft(b) {
    let x = b.x, z = b.z, vx = b.vx, vz = b.vz;
    for (let t = 1; t <= b.life; t++) {
        vx += b.ax / 20;
        vz += b.az / 20;
        x += vx / 20;
        z += vz / 20;
        if (outside(b, x, z)) return t;
    }
    return b.life;
}

function draw(b, ticks, still = false) {
    if (b.e) return;
    const speed = still ? 0 : Math.hypot(b.vx, b.vz);
    const fx = Math.hypot(b.vx, b.vz) > 1e-4 ? b.vx : Math.cos(b.face), fz = Math.hypot(b.vx, b.vz) > 1e-4 ? b.vz : Math.sin(b.face);
    const n = Math.hypot(fx, fz) || 1;
    particle(b.dim, "eclipse:orb", { x: b.x, y: b.y, z: b.z }, {
        color: b.color, size: b.size, life: ticks / 20, dir: { speed, v: { x: fx / n, y: 0, z: fz / n } },
        acc: still ? undefined : { x: b.ax, y: 0, z: b.az } });
}

const dynamic = (b) => b.hold > 0 || b.homeTicks > 0 || (b.curve !== 0 && b.curveTicks > 0) || !!b.stop;

/**
 * Fires a bullet. o: {x, z, angle (rad), speed (blocks/s), accel (blocks/s² along the
 * angle), r, dmg, color, size, life (ticks), hold (ticks it waits, visible, before
 * flying), home {target, turn (rad/s), ticks}, curve (rad/s) for curveTicks, square
 * (walls), stop {at (ticks), hold, speed, aim: fn(bullet) -> target}}.
 */
export function shoot(f, o) {
    const ca = Math.cos(o.angle), sa = Math.sin(o.angle);
    const b = {
        owner: f.id, boss: f.boss, dim: f.dim, arena: f.arena, f,
        x: o.x, y: f.arena.floor + PLANE, z: o.z, face: o.angle,
        vx: ca * o.speed, vz: sa * o.speed, ax: ca * (o.accel ?? 0), az: sa * (o.accel ?? 0),
        r: o.r ?? 0.38, dmg: o.dmg ?? 6, color: o.color ?? C.cyan, size: o.size ?? 0.28,
        life: o.life ?? 220, hold: o.hold ?? 0, square: !!o.square,
        home: o.home?.target, turn: o.home?.turn ?? 0, homeTicks: o.home?.ticks ?? 0,
        curve: o.curve ?? 0, curveTicks: o.curveTicks ?? (o.curve ? 9999 : 0), stop: o.stop,
        age: 0,
    };
    bullets.push(b);
    if (shapeCount("gem") < MAX_GEMS) {
        b.e = gem(f.dim, { x: b.x, y: b.y, z: b.z }, b.color, b.size, Math.min(60, (b.life + b.hold) / 20 + 1));
        sync(b);
    }
    if (b.hold > 0) draw(b, 6, true);
    else if (dynamic(b)) draw(b, 3);
    else draw(b, ticksLeft(b));
    return b;
}

/** Moves the bullet's diamond with the simulation: its velocity, and a nudge if it drifts. */
function sync(b) {
    const e = b.e;
    if (!e) return;
    try {
        let dy = 0;
        if (b.age % 10 === 0) {   // reading its position is not free: only now and then
            const l = e.location;
            if (Math.hypot(l.x - b.x, l.z - b.z) > 0.6) e.teleport({ x: b.x, y: b.y, z: b.z });
            dy = (b.y - l.y) * 0.5;
        }
        e.clearVelocity();
        if (b.hold <= 0) e.applyImpulse({ x: b.vx / 20, y: dy, z: b.vz / 20 });
    } catch {
        b.e = undefined;
    }
}

function drop(b) {
    if (b.e) unshape(b.e);
    b.e = undefined;
}

function steer(b) {
    const t = b.home;
    if (!isValid(t)) {
        b.homeTicks = 0;
        return;
    }
    const want = Math.atan2(t.location.z - b.z, t.location.x - b.x);
    const now = Math.atan2(b.vz, b.vx);
    let d = want - now;
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    const max = b.turn / 20;
    const a = now + Math.max(-max, Math.min(max, d));
    const s = Math.hypot(b.vx, b.vz);
    b.vx = Math.cos(a) * s;
    b.vz = Math.sin(a) * s;
}

function rotate(b, by) {
    const c = Math.cos(by), s = Math.sin(by);
    [b.vx, b.vz] = [b.vx * c - b.vz * s, b.vx * s + b.vz * c];
}

function moveBullet(b) {
    const keep = stepBullet(b);
    if (keep) sync(b);
    return keep;
}

function stepBullet(b) {
    b.age++;
    if (b.hold > 0) {
        b.hold--;
        if (b.hold === 0) {
            if (b.retarget) {
                const t = b.retarget.aim(b);
                const a = t ? Math.atan2(t.location.z - b.z, t.location.x - b.x) : b.face;
                b.vx = Math.cos(a) * b.retarget.speed;
                b.vz = Math.sin(a) * b.retarget.speed;
                b.face = a;
                b.retarget = undefined;
                sound(b.dim, "random.orb", { x: b.x, y: b.y, z: b.z }, 0.3, 1.8);
            }
            draw(b, dynamic(b) ? 3 : ticksLeft(b));
        } else if (b.hold % 5 === 0) {
            draw(b, 6, true);
        }
        return true;
    }
    if (b.stop && b.age >= b.stop.at) {
        // stop, wait, and set off again towards a target
        b.face = Math.atan2(b.vz, b.vx);
        b.vx = b.vz = b.ax = b.az = 0;
        b.hold = b.stop.hold;
        b.retarget = { speed: b.stop.speed, aim: b.stop.aim };
        b.stop = undefined;
        draw(b, 6, true);
        return true;
    }
    const wasDynamic = dynamic(b);
    if (b.homeTicks > 0) {
        steer(b);
        b.homeTicks--;
    }
    if (b.curve && b.curveTicks > 0) {
        rotate(b, b.curve / 20);
        b.curveTicks--;
    }
    b.vx += b.ax / 20;
    b.vz += b.az / 20;
    b.x += b.vx / 20;
    b.z += b.vz / 20;
    b.life--;
    if (b.life <= 0 || outside(b, b.x, b.z)) return false;
    if (wasDynamic) {
        if (!dynamic(b)) draw(b, ticksLeft(b)); // the homing / curve ended: one last straight particle
        else if (b.age % 2 === 0) draw(b, 3);
    }
    return true;
}

/** Does a body (feet at l) touch a sphere of radius r at p? */
function touches(l, p, r) {
    return p.y >= l.y - r && p.y <= l.y + BODY_H + r && Math.hypot(l.x - p.x, l.z - p.z) <= r + BODY_R;
}

function bulletHits(b, targets) {
    for (const e of targets) {
        if (!touches(e.location, b, b.r)) continue;
        if (hurt(e, b.dmg, b.boss, EntityDamageCause.entityAttack, "bullet")) {
            burst(b.dim, { x: b.x, y: b.y, z: b.z }, b.color, 8, 3);
        }
    }
}

// --- rays, zones, waves ------------------------------------------------------------------------
function groundAt(f, x, z) {
    return { x, y: f.arena.floor + 0.06, z };
}

/** A celestial ray: its target sigil appears with a ring closing in, then a column of light falls. */
export function ray(f, x, z, o = {}) {
    const radius = o.radius ?? 2.3, fuse = o.fuse ?? 24, color = o.color ?? C.gold;
    const at = groundAt(f, x, z);
    target(f.dim, at, radius, color, fuse / 20 + 0.1);
    flatRing(f.dim, { ...at, y: at.y + 0.02 }, radius, C.white, fuse / 20, { speed: -radius / (fuse / 20) });
    let t = 0;
    hazards.push({ owner: f.id, f, update(now, targets) {
        if (++t < fuse) return true;
        beam(f.dim, at, color, o.light ? 14 : 24, radius * 0.45);
        flatRing(f.dim, { ...at, y: at.y + 0.03 }, radius * 0.6, color, 0.3, { speed: 10, max: radius * 1.6 });
        burst(f.dim, { x, y: at.y + 0.3, z }, color, o.light ? 5 : 12, 4);
        if (!o.quiet) sound(f.dim, "ambient.weather.thunder", at, 0.5, 1.6);
        for (const e of targets) {
            if (Math.hypot(e.location.x - x, e.location.z - z) <= radius + BODY_R && e.location.y - f.arena.floor < 4) {
                hurt(e, o.dmg ?? 7, f.boss, EntityDamageCause.lightning);
            }
        }
        return false;
    } });
}

/**
 * A zone that grows from r0 to r1 in `grow` ticks, waits `hold` and explodes. With
 * `inner`, the circle of that radius in its middle is safe (a golden sun). With
 * `follow`, it stays centred on that entity while it grows.
 */
export function zone(f, o) {
    const color = o.color ?? C.violet;
    const hold = o.hold ?? 8, total = o.grow + hold;
    let t = 0, x = o.x, z = o.z;
    const rate = (o.r1 - o.r0) / (o.grow / 20);
    if (!o.follow) {
        disc(f.dim, groundAt(f, x, z), o.r0, color, total / 20, { speed: rate, max: o.r1 });
        if (o.inner) safe(f.dim, { ...groundAt(f, x, z), y: f.arena.floor + 0.09 }, o.inner, C.safe, total / 20);
    }
    hazards.push({ owner: f.id, f, update(now, targets) {
        t++;
        if (o.follow && t <= o.grow && isValid(o.follow)) {
            x = o.follow.location.x;
            z = o.follow.location.z;
        }
        const r = o.r0 + (o.r1 - o.r0) * Math.min(1, t / o.grow);
        const at = groundAt(f, x, z);
        if (t < total) {
            if (o.follow && t % 3 === 1 && t < o.grow) disc(f.dim, at, r, color, 0.18, { wall: 0 });
            if (o.follow && t === o.grow) disc(f.dim, at, r, color, hold / 20 + 0.1);
            if (t === o.grow) ring(f.dim, { ...at, y: at.y + 0.02 }, r, C.white, hold / 20); // about to blow
            return true;
        }
        flatRing(f.dim, { ...at, y: at.y + 0.03 }, r * 0.5, color, 0.4, { speed: r * 2.5, max: r * 1.4 });
        burst(f.dim, { x, y: at.y + 0.5, z }, color, 26, 6);
        for (let i = 0; i < 5; i++) {
            const a = Math.random() * 2 * Math.PI, d = (o.inner ?? 0) + Math.random() * (r - (o.inner ?? 0));
            burst(f.dim, { x: x + Math.cos(a) * d, y: at.y + 0.4, z: z + Math.sin(a) * d }, color, 8, 3);
        }
        sound(f.dim, "random.explode", at, 1.2, 1.3);
        for (const e of targets) {
            const d = Math.hypot(e.location.x - x, e.location.z - z);
            if (d <= r + BODY_R && d >= (o.inner ?? -1) && e.location.y - f.arena.floor < 5) {
                hurt(e, o.dmg ?? 8, f.boss, EntityDamageCause.magic);
                try {
                    const k = Math.max(0.01, d);
                    (e.e ?? e).applyKnockback({ x: ((e.location.x - x) / k) * 0.8, z: ((e.location.z - z) / k) * 0.8 }, 0.3);
                } catch {
                    // ignore
                }
            }
        }
        return false;
    } });
}

/** A low ring running along the floor: jump over it. */
export function wave(f, o) {
    const color = o.color ?? C.gold;
    const hit = new Set();
    let r = o.r0 ?? 1.5;
    const at = groundAt(f, o.x, o.z);
    waveDecal(f.dim, { ...at, y: at.y + 0.04 }, r, o.speed, (o.rMax - r) / o.speed, color);
    hazards.push({ owner: f.id, f, update(now, targets) {
        r += o.speed / 20;
        if (r > o.rMax) return false;
        for (const e of targets) {
            if (hit.has(e.id)) continue;
            const d = Math.hypot(e.location.x - o.x, e.location.z - o.z);
            if (Math.abs(d - r) > 0.75 || e.location.y - f.arena.floor > 0.55) continue; // jumped over
            hit.add(e.id);
            hurt(e, o.dmg ?? 5, f.boss);
        }
        return true;
    } });
}

/** A band (the ring between rIn and rOut) marked by red walls of light on both edges;
 *  it explodes after `fuse` ticks. Stand outside it. */
export function band(f, o) {
    const color = o.color ?? C.danger, life = o.fuse / 20;
    const at = groundAt(f, o.x, o.z);
    ring(f.dim, at, o.rIn, color, life);
    ring(f.dim, at, o.rOut, color, life);
    flatRing(f.dim, { ...at, y: at.y + 0.01 }, (o.rIn + o.rOut) / 2, color, life, { alpha: 0.6 });
    let t = 0;
    hazards.push({ owner: f.id, f, update(now, targets) {
        t++;
        if (t === o.fuse - 8) {
            flatRing(f.dim, { ...at, y: at.y + 0.02 }, o.rIn, C.white, 0.4);
            flatRing(f.dim, { ...at, y: at.y + 0.02 }, o.rOut, C.white, 0.4);
        }
        if (t < o.fuse) return true;
        for (let i = 0; i < 8; i++) {
            const a = Math.random() * 2 * Math.PI, d = o.rIn + Math.random() * (o.rOut - o.rIn);
            burst(f.dim, { x: o.x + Math.cos(a) * d, y: at.y + 0.5, z: o.z + Math.sin(a) * d }, color, 10, 4);
        }
        flatRing(f.dim, { ...at, y: at.y + 0.03 }, o.rIn, color, 0.35, { speed: (o.rOut - o.rIn) * 3, max: o.rOut });
        sound(f.dim, "random.explode", at, 1, 1.5);
        for (const e of targets) {
            const d = Math.hypot(e.location.x - o.x, e.location.z - o.z);
            if (d >= o.rIn - BODY_R && d <= o.rOut + BODY_R && e.location.y - f.arena.floor < 5) {
                hurt(e, o.dmg ?? 8, f.boss, EntityDamageCause.magic);
            }
        }
        return false;
    } });
}

/** Hurts what a laser from `a` to `b` touches. low: only what is on the floor (jump it). */
export function laserHits(f, a, b, width, dmg, low = false) {
    const dx = b.x - a.x, dz = b.z - a.z, len2 = dx * dx + dz * dz || 1;
    for (const e of arenaBodies(f.dim, f.arena)) {
        const l = e.location;
        const t = Math.max(0, Math.min(1, ((l.x - a.x) * dx + (l.z - a.z) * dz) / len2));
        const d = Math.hypot(l.x - (a.x + dx * t), l.z - (a.z + dz * t));
        if (d > width + BODY_R) continue;
        if (low ? l.y - f.arena.floor > 0.55 : l.y - f.arena.floor > 3.5) continue;
        hurt(e, dmg, f.boss, EntityDamageCause.magic, low ? "laser_low" : "laser");
    }
}

/** Anything else that runs each tick for a while (portals, safe zones...). */
export function effect(f, update) {
    hazards.push({ owner: f.id, f, update });
}

/** Clears an owner's bullets and hazards (a phase change, a death). */
export function clear(owner, fizzle = true) {
    let shown = 0;
    for (let i = bullets.length - 1; i >= 0; i--) {
        const b = bullets[i];
        if (b.owner !== owner) continue;
        if (fizzle && shown++ < 30) burst(b.dim, { x: b.x, y: b.y, z: b.z }, C.white, 4, 1.5);
        drop(b);
        bullets.splice(i, 1);
    }
    for (let i = hazards.length - 1; i >= 0; i--) if (hazards[i].owner === owner) hazards.splice(i, 1);
}

export const count = () => bullets.length;

// --- the loop ---------------------------------------------------------------------------------
system.runInterval(() => {
    if (!bullets.length && !hazards.length) return;
    const targetsOf = (arena, dim) => arenaBodies(dim, arena);
    for (let i = bullets.length - 1; i >= 0; i--) {
        const b = bullets[i];
        let keep;
        try {
            keep = moveBullet(b);
            if (keep) bulletHits(b, targetsOf(b.arena, b.dim));
        } catch {
            keep = false;
        }
        if (!keep) {
            drop(b);
            bullets.splice(i, 1);
        }
    }
    for (let i = hazards.length - 1; i >= 0; i--) {
        const h = hazards[i];
        let keep;
        try {
            keep = h.update(system.currentTick, targetsOf(h.f.arena, h.f.dim));
        } catch {
            keep = false;
        }
        if (!keep) {
            const k = hazards.indexOf(h);
            if (k >= 0) hazards.splice(k, 1);
        }
    }
}, 1);
