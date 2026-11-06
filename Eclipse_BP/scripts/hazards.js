import { system, EntityDamageCause } from "@minecraft/server";
import { C, particle, ring, disc, beam, burst, sound } from "./fx.js";
import { level } from "./settings.js";

// Everything that can hurt: bullets, celestial rays, growing zones and ground waves.
// They are simulated here (cheap) and drawn with particles; nothing is an entity.
//
// Bullets fly on a flat plane 1.1 blocks above the arena floor: the player dodges by
// moving, never by luck. A straight bullet is drawn with ONE particle that flies by
// itself; only homing / curving / waiting bullets are redrawn every few ticks.

export const PLANE = 1.1;
const PLAYER_R = 0.32, PLAYER_H = 1.8;
const BULLET_COOLDOWN = 10; // a player is hurt by bullets at most twice a second

const bullets = [];
const hazards = [];
const cooldown = new Map(); // player id -> tick of the last bullet hit

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);

export function inPlay(p) {
    try {
        const m = String(p.getGameMode()).toLowerCase();
        return m === "survival" || m === "adventure";
    } catch {
        return false;
    }
}

/** Players fighting in this arena. */
export function arenaPlayers(dim, a) {
    try {
        return dim.getPlayers({ location: { x: a.cx, y: a.floor + 2, z: a.cz }, maxDistance: a.R + 8 })
            .filter((p) => inPlay(p) && Math.abs(p.location.y - a.floor) < 14);
    } catch {
        return [];
    }
}

export function hurt(p, amount, owner, cause = EntityDamageCause.entityAttack) {
    const dmg = amount * level().dmg;
    if (dmg <= 0) return;
    try {
        if (isValid(owner)) p.applyDamage(dmg, { cause, damagingEntity: owner });
        else p.applyDamage(dmg, { cause });
    } catch {
        // gone
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

function draw(b, ticks) {
    const speed = Math.hypot(b.vx, b.vz);
    const v = speed > 1e-4 ? { x: b.vx / speed, y: 0, z: b.vz / speed } : { x: 0, y: 1, z: 0 };
    particle(b.dim, "eclipse:orb", { x: b.x, y: b.y, z: b.z }, {
        color: b.color, size: b.size, life: ticks / 20, dir: { speed, v }, acc: { x: b.ax, y: 0, z: b.az } });
}

const dynamic = (b) => b.hold > 0 || b.homeTicks > 0 || b.curve !== 0;

/**
 * Fires a bullet. o: {x, z, angle (rad), speed (blocks/s), accel (blocks/s² along the
 * angle), r, dmg, color, size, life (ticks), hold (ticks it waits, visible, before
 * flying), home {target, turn (rad/s), ticks}, curve (rad/s), square (walls)}.
 */
export function shoot(f, o) {
    const ca = Math.cos(o.angle), sa = Math.sin(o.angle);
    const b = {
        owner: f.id, boss: f.boss, dim: f.dim, arena: f.arena,
        x: o.x, y: f.arena.floor + PLANE, z: o.z,
        vx: ca * o.speed, vz: sa * o.speed, ax: ca * (o.accel ?? 0), az: sa * (o.accel ?? 0),
        r: o.r ?? 0.35, dmg: o.dmg ?? 4, color: o.color ?? C.cyan, size: o.size ?? 0.2,
        life: o.life ?? 220, hold: o.hold ?? 0, square: !!o.square,
        home: o.home?.target, turn: o.home?.turn ?? 0, homeTicks: o.home?.ticks ?? 0, curve: o.curve ?? 0,
        age: 0,
    };
    bullets.push(b);
    if (b.hold > 0) draw({ ...b, vx: 0, vz: 0, ax: 0, az: 0 }, 6);
    else if (dynamic(b)) draw(b, 3);
    else draw(b, ticksLeft(b));
    return b;
}

function steer(b) {
    let t = b.home;
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
    b.age++;
    if (b.hold > 0) {
        b.hold--;
        if (b.hold === 0) {
            draw(b, dynamic(b) ? 3 : ticksLeft(b));
        } else if (b.hold % 5 === 0) {
            draw({ ...b, vx: 0, vz: 0, ax: 0, az: 0 }, 6);
        }
        return true;
    }
    const wasDynamic = dynamic(b);
    if (b.homeTicks > 0) {
        steer(b);
        b.homeTicks--;
    }
    if (b.curve) rotate(b, b.curve / 20);
    b.vx += b.ax / 20;
    b.vz += b.az / 20;
    b.x += b.vx / 20;
    b.z += b.vz / 20;
    b.life--;
    if (b.life <= 0 || outside(b, b.x, b.z)) return false;
    if (wasDynamic) {
        if (!dynamic(b)) draw(b, ticksLeft(b)); // the homing ended: one last straight particle
        else if (b.age % 2 === 0) draw(b, 3);
    }
    return true;
}

function bulletHits(b, players, now) {
    for (const p of players) {
        const l = p.location;
        if (b.y < l.y - b.r || b.y > l.y + PLAYER_H + b.r) continue;
        if (Math.hypot(l.x - b.x, l.z - b.z) > b.r + PLAYER_R) continue;
        if (now - (cooldown.get(p.id) ?? -100) < BULLET_COOLDOWN) continue;
        cooldown.set(p.id, now);
        hurt(p, b.dmg, b.boss);
        burst(b.dim, { x: b.x, y: b.y, z: b.z }, b.color, 8, 3);
    }
}

// --- rays, zones, waves ------------------------------------------------------------------------
function groundAt(f, x, z) {
    return { x, y: f.arena.floor + 0.06, z };
}

/** A celestial ray: its spot is marked (a ring closing in), then it falls. */
export function ray(f, x, z, o = {}) {
    const radius = o.radius ?? 2.3, fuse = o.fuse ?? 24, color = o.color ?? C.gold;
    const at = groundAt(f, x, z);
    ring(f.dim, at, radius, color, fuse / 20, { spacing: o.light ? 1 : 0.7 });
    disc(f.dim, at, radius, color, fuse / 20, o.light ? 0.18 : 0.35);
    let t = 0;
    hazards.push({ owner: f.id, f, update(now, players) {
        t++;
        if (t < fuse) {
            if (t % 5 === 0) ring(f.dim, at, Math.max(0.3, radius * (1 - t / fuse)), C.white, 0.27, { spacing: 0.9, max: 20 });
            return true;
        }
        beam(f.dim, at, color, o.light ? 12 : 22);
        burst(f.dim, { x, y: at.y + 0.3, z }, color, o.light ? 6 : 14, 4);
        if (!o.quiet) sound(f.dim, "ambient.weather.thunder", at, 0.5, 1.6);
        for (const p of players) {
            if (Math.hypot(p.location.x - x, p.location.z - z) <= radius + PLAYER_R && p.location.y - f.arena.floor < 4) {
                hurt(p, o.dmg ?? 7, f.boss, EntityDamageCause.lightning);
            }
        }
        return false;
    } });
}

/**
 * A zone that grows from r0 to r1 in `grow` ticks, waits `hold` and explodes. With
 * `inner`, the circle of that radius in its middle is safe (drawn in gold). With
 * `follow`, it stays centred on that entity while it grows.
 */
export function zone(f, o) {
    const color = o.color ?? C.violet;
    const total = o.grow + (o.hold ?? 8);
    let t = 0, x = o.x, z = o.z;
    hazards.push({ owner: f.id, f, update(now, players) {
        t++;
        if (o.follow && t <= o.grow && isValid(o.follow)) {
            x = o.follow.location.x;
            z = o.follow.location.z;
        }
        const r = o.r0 + (o.r1 - o.r0) * Math.min(1, t / o.grow);
        const at = groundAt(f, x, z);
        if (t < total) {
            if (t % 4 === 1) {
                ring(f.dim, at, r, t > o.grow ? C.white : color, 0.22, { spacing: 0.75 });
                if (o.inner) ring(f.dim, at, o.inner, C.safe, 0.22, { spacing: 0.6 });
            }
            if (t % 10 === 1) disc(f.dim, at, r, color, 0.52, 0.18);
            return true;
        }
        ring(f.dim, at, r * 0.4, color, 0.45, { speed: r * 1.6, spacing: 0.5 });
        burst(f.dim, { x, y: at.y + 0.5, z }, color, 30, 6);
        for (let i = 0; i < 6; i++) {
            const a = Math.random() * 2 * Math.PI, d = (o.inner ?? 0) + Math.random() * (r - (o.inner ?? 0));
            burst(f.dim, { x: x + Math.cos(a) * d, y: at.y + 0.4, z: z + Math.sin(a) * d }, color, 8, 3);
        }
        sound(f.dim, "random.explode", at, 1.2, 1.3);
        for (const p of players) {
            const d = Math.hypot(p.location.x - x, p.location.z - z);
            if (d <= r + PLAYER_R && d >= (o.inner ?? -1) && p.location.y - f.arena.floor < 5) {
                hurt(p, o.dmg ?? 8, f.boss, EntityDamageCause.magic);
                try {
                    const k = Math.max(0.01, d);
                    p.applyKnockback({ x: ((p.location.x - x) / k) * 0.8, z: ((p.location.z - z) / k) * 0.8 }, 0.3);
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
    let r = o.r0 ?? 1.5, t = 0;
    const at = groundAt(f, o.x, o.z);
    hazards.push({ owner: f.id, f, update(now, players) {
        r += o.speed / 20;
        if (r > o.rMax) return false;
        if (t++ % 3 === 0) {
            ring(f.dim, { ...at, y: at.y + 0.15 }, r, color, 0.16, { speed: o.speed, spacing: 0.55, max: 220, size: 0.2 });
        }
        for (const p of players) {
            if (hit.has(p.id)) continue;
            const d = Math.hypot(p.location.x - o.x, p.location.z - o.z);
            if (Math.abs(d - r) > 0.75 || p.location.y - f.arena.floor > 0.55) continue; // jumped over
            hit.add(p.id);
            hurt(p, o.dmg ?? 5, f.boss);
        }
        return true;
    } });
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
        bullets.splice(i, 1);
    }
    for (let i = hazards.length - 1; i >= 0; i--) if (hazards[i].owner === owner) hazards.splice(i, 1);
}

export const count = () => bullets.length;

// --- the loop ---------------------------------------------------------------------------------
system.runInterval(() => {
    if (!bullets.length && !hazards.length) return;
    const now = system.currentTick;
    const cache = new Map();
    const playersOf = (arena, dim) => {
        const key = `${dim.id}:${arena.cx}:${arena.cz}`;
        if (!cache.has(key)) cache.set(key, arenaPlayers(dim, arena));
        return cache.get(key);
    };
    for (let i = bullets.length - 1; i >= 0; i--) {
        const b = bullets[i];
        let keep;
        try {
            keep = moveBullet(b);
            if (keep) bulletHits(b, playersOf(b.arena, b.dim), now);
        } catch {
            keep = false;
        }
        if (!keep) bullets.splice(i, 1);
    }
    for (let i = hazards.length - 1; i >= 0; i--) {
        const h = hazards[i];
        let keep;
        try {
            keep = h.update(now, playersOf(h.f.arena, h.f.dim));
        } catch {
            keep = false;
        }
        if (!keep) hazards.splice(hazards.indexOf(h), 1);
    }
}, 1);
