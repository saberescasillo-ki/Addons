import { C, particle, ring, disc, line, burst, charge, pillar, sound, shake } from "./fx.js";
import { shoot, ray, zone, wave, effect, PLANE } from "./hazards.js";

// The Eclipse's attacks. Each one: a clear warning first (pose, sound, marks on the
// ground), then the attack, always with a way out (gaps, lanes, safe tiles, a jump).
// They return how many ticks they keep the boss busy. f is the fight (boss.js).

export const ANIM = { idle: 0, point: 1, raise: 2, spin: 3, cross: 4, summon: 5, charge: 6, release: 7,
    vanish: 8, appear: 9, phase: 10, ultCharge: 11, ultRelease: 12, exhausted: 13, slam: 14 };

const DEG = Math.PI / 180;
const by = (f, list) => list[Math.min(list.length, f.phase) - 1];
const speed = (f, base) => base * by(f, [1, 1.15, 1.25]);
const at = (f) => ({ x: f.boss.location.x, z: f.boss.location.z });
const yawTo = (from, to) => Math.atan2(to.z - from.z, to.x - from.x);
const ground = (f, x, z) => ({ x, y: f.arena.floor + 0.06, z });
const hand = (f) => ({ x: f.boss.location.x, y: f.arena.floor + PLANE + 0.6, z: f.boss.location.z });

function pose(f, o, anim, ticks) {
    if (o.secondary) return;
    f.anim(anim);
    f.after(ticks, () => f.anim(ANIM.idle));
}

// 1. Energy volleys: fans aimed at the target, two speeds in each, offset fans.
export function volley(f, o = {}) {
    const bursts = o.bursts ?? by(f, [3, 4, 5]);
    const n = by(f, [3, 5, 5]), step = 12 * DEG;
    const dur = 14 + bursts * 9 + 6;
    pose(f, o, ANIM.point, dur);
    sound(f.dim, "mob.evocation_illager.prepare_attack", f.boss.location, 1.2, 1.4);
    charge(f.dim, hand(f), C.cyan, 1.6, 0.6, 18);
    for (let i = 0; i < bursts; i++) {
        f.after(14 + i * 9, () => {
            const t = f.target();
            if (!t) return;
            const from = at(f), aim = yawTo(from, t.location);
            const offset = i % 2 ? step / 2 : 0;
            for (let k = 0; k < n; k++) {
                const a = aim + offset + (k - (n - 1) / 2) * step;
                shoot(f, { ...from, angle: a, speed: speed(f, 7), color: C.cyan, dmg: 4 });
                if (f.phase >= 2 || k % 2 === 0) shoot(f, { ...from, angle: a, speed: speed(f, 11.5), color: C.white, size: 0.16, dmg: 4 });
            }
            sound(f.dim, "mob.shulker.shoot", f.boss.location, 1, 1.5);
        });
    }
    return dur;
}

// 2. Rings: rings of bullets with gaps between them; in later phases they speed up.
export function rings(f, o = {}) {
    const count = o.rings ?? by(f, [2, 3, 4]);
    const n = by(f, [20, 24, 28]);
    const dur = 16 + count * 14 + 8;
    pose(f, o, ANIM.cross, dur);
    sound(f.dim, "chime.amethyst_block", f.boss.location, 2, 0.7);
    ring(f.dim, ground(f, f.boss.location.x, f.boss.location.z), 1.8, C.violet, 0.8, { spacing: 0.3 });
    const base = Math.random() * 2 * Math.PI;
    for (let i = 0; i < count; i++) {
        f.after(16 + i * 14, () => {
            const from = at(f);
            const fast = f.phase >= 2 && i % 2 === 1;
            for (let k = 0; k < n; k++) {
                const a = base + ((k + (i % 2) * 0.5) / n) * 2 * Math.PI;
                if (fast) shoot(f, { ...from, angle: a, speed: 2.5, accel: 7, color: C.magenta, dmg: 4, life: 120 });
                else shoot(f, { ...from, angle: a, speed: speed(f, 6.5), color: C.violet, dmg: 4 });
            }
            ring(f.dim, ground(f, from.x, from.z), 1.2, C.violet, 0.4, { speed: 6 });
            sound(f.dim, "mob.shulker.shoot", f.boss.location, 1, 0.9);
        });
    }
    return dur;
}

// 3. Celestial rays: they fall where each player stands (keep moving).
export function raysFollow(f, o = {}) {
    const strikes = o.strikes ?? by(f, [3, 4, 5]);
    const every = by(f, [13, 11, 10]), fuse = by(f, [26, 22, 20]);
    const extra = by(f, [0, 1, 2]);
    const dur = strikes * every + fuse + 8;
    pose(f, o, ANIM.raise, dur);
    sound(f.dim, "beacon.activate", f.boss.location, 2, 1.3);
    for (let i = 0; i < strikes; i++) {
        f.after(i * every, () => {
            for (const p of f.players()) {
                ray(f, p.location.x, p.location.z, { fuse, dmg: 7 });
                for (let k = 0; k < extra; k++) {
                    const a = Math.random() * 2 * Math.PI, d = 3.5 + Math.random() * 3;
                    const x = p.location.x + Math.cos(a) * d, z = p.location.z + Math.sin(a) * d;
                    if (f.inArena(x, z)) ray(f, x, z, { fuse: fuse + 6, dmg: 7, quiet: true });
                }
            }
        });
    }
    return dur;
}

// 3b. Grid of rays: half of the tiles (a chessboard), then the other half.
export function raysGrid(f, o = {}) {
    const a = f.arena, tile = 5, fuse = 34, second = 30;
    const dur = second + fuse + 10;
    pose(f, o, ANIM.raise, dur);
    sound(f.dim, "beacon.power", f.boss.location, 2, 0.8);
    const shift = Math.random() < 0.5 ? 0 : 1;
    const cells = [[], []];
    const n = Math.ceil(a.R / tile);
    for (let i = -n; i <= n; i++) {
        for (let j = -n; j <= n; j++) {
            const x = a.cx + i * tile, z = a.cz + j * tile;
            if (Math.hypot(x - a.cx, z - a.cz) <= a.R - 1) cells[(i + j + shift + 2 * n) % 2].push({ x, z });
        }
    }
    const strike = (list) => {
        for (const c of list) ray(f, c.x, c.z, { radius: 2.6, fuse, dmg: 8, quiet: true, light: true });
        f.after(fuse, () => {
            sound(f.dim, "ambient.weather.thunder", f.boss.location, 1.5, 1.2);
            shake(f.dim, f.boss.location, a.R + 8, 0.15, 0.4);
        });
    };
    strike(cells[0]);
    f.after(second, () => strike(cells[1]));
    return dur;
}

// 4. Homing orbs: they follow for a couple of seconds, then fly straight.
export function homing(f, o = {}) {
    const n = o.count ?? by(f, [3, 4, 5]);
    const dur = 18 + 16;
    pose(f, o, ANIM.summon, dur);
    sound(f.dim, "mob.evocation_illager.cast_spell", f.boss.location, 1.5, 0.8);
    const from = at(f), base = Math.random() * 2 * Math.PI;
    const players = f.players();
    for (let k = 0; k < n; k++) {
        const a = base + (k / n) * 2 * Math.PI;
        const x = from.x + Math.cos(a) * 2.2, z = from.z + Math.sin(a) * 2.2;
        const target = players.length ? players[k % players.length] : f.target();
        shoot(f, { x, z, angle: target ? yawTo({ x, z }, target.location) : a, speed: speed(f, 5.6),
            hold: 18 + k * 3, r: 0.5, size: 0.34, color: C.crimson, dmg: 5, life: 160,
            home: { target, turn: by(f, [70, 85, 95]) * DEG, ticks: by(f, [45, 50, 55]) } });
    }
    f.after(18, () => sound(f.dim, "mob.wither.shoot", f.boss.location, 1, 1.4));
    return dur;
}

// 5. Spirals: rotating arms of bullets; in phase 3 a second spiral turns the other way.
export function spiral(f, o = {}) {
    const arms = by(f, [2, 3, 4]), every = by(f, [4, 3, 3]), span = o.span ?? 60;
    const turn = by(f, [9, 11, 12]) * DEG * (Math.random() < 0.5 ? 1 : -1);
    const dur = 12 + span + 6;
    pose(f, o, ANIM.spin, dur);
    sound(f.dim, "mob.evocation_illager.prepare_attack", f.boss.location, 1.5, 0.7);
    charge(f.dim, hand(f), C.magenta, 2.2, 0.6, 24);
    const base = Math.random() * 2 * Math.PI;
    for (let t = 0, e = 0; t < span; t += every, e++) {
        f.after(12 + t, () => {
            const from = at(f);
            for (let k = 0; k < arms; k++) {
                shoot(f, { ...from, angle: base + e * turn + (k / arms) * 2 * Math.PI, speed: speed(f, 6), color: C.magenta, dmg: 4 });
            }
            if (f.phase >= 3 && e % 2 === 0) {
                for (let k = 0; k < 2; k++) {
                    shoot(f, { ...from, angle: -base - e * turn * 1.5 + k * Math.PI, speed: speed(f, 5), color: C.azure, dmg: 4 });
                }
            }
            if (e % 4 === 0) sound(f.dim, "mob.shulker.shoot", f.boss.location, 0.6, 1.8);
        });
    }
    return dur;
}

// 6. Walls: a wall of bullets crosses the arena; its gap (marked in gold) is the way out.
function wallFrom(f, side, hold) {
    const a = f.arena, R = a.R + 2;
    const dir = [{ x: 1, z: 0 }, { x: -1, z: 0 }, { x: 0, z: 1 }, { x: 0, z: -1 }][side];
    const across = { x: -dir.z, z: dir.x };
    const gap = (Math.random() * 2 - 1) * (a.R - 7), half = 1.9;
    const start = { x: a.cx - dir.x * R, z: a.cz - dir.z * R };
    const angle = Math.atan2(dir.z, dir.x), v = speed(f, 5.5);
    for (let s = -R; s <= R; s += 0.95) {
        if (Math.abs(s - gap) < half) continue;
        shoot(f, { x: start.x + across.x * s, z: start.z + across.z * s, angle, speed: v, hold, square: true,
            color: C.gold, dmg: 4, life: hold + Math.ceil((2 * R / v) * 20) + 4 });
    }
    const life = (hold + (2 * R / v) * 20) / 20;
    for (const e of [gap - half, gap + half]) {
        const p0 = { x: start.x + across.x * e, y: a.floor + 0.06, z: start.z + across.z * e };
        line(f.dim, p0, { x: p0.x + dir.x * 2 * R, y: p0.y, z: p0.z + dir.z * 2 * R }, C.safe, Math.min(life, 4), 1.4);
    }
    return Math.ceil((2 * R / v) * 20);
}

export function walls(f, o = {}) {
    const hold = 26;
    const side = Math.floor(Math.random() * 4);
    const cross = side < 2 ? 2 + Math.floor(Math.random() * 2) : Math.floor(Math.random() * 2);
    sound(f.dim, "block.end_portal_frame.fill", f.boss.location, 2, 0.6);
    let travel = wallFrom(f, side, hold);
    if (f.phase === 2) f.after(30, () => wallFrom(f, cross, hold));
    if (f.phase >= 3) {
        wallFrom(f, cross, hold);
        f.after(40, () => wallFrom(f, side ^ 1, hold));
        travel += 20;
    }
    const dur = hold + Math.round(travel * 0.55);
    pose(f, o, ANIM.cross, dur);
    return dur;
}

// 7. Cross: four streams from the boss (shown on the ground first), slowly turning.
export function cross(f, o = {}) {
    const t = f.target();
    const from = at(f);
    const base = (t ? yawTo(from, t.location) : 0) + 45 * DEG;
    const spin = by(f, [0, 22, 32]) * DEG * (Math.random() < 0.5 ? 1 : -1);
    const arms = f.phase >= 3 ? 6 : 4, span = 50, warn = 20;
    const dur = warn + span + 6;
    pose(f, o, ANIM.cross, dur);
    sound(f.dim, "mob.evocation_illager.prepare_attack", f.boss.location, 1.5, 1);
    for (let k = 0; k < arms; k++) {
        const a = base + (k / arms) * 2 * Math.PI;
        line(f.dim, ground(f, from.x, from.z), ground(f, from.x + Math.cos(a) * 14, from.z + Math.sin(a) * 14), C.gold, warn / 20 + 0.2, 1);
        if (spin) {
            const b = a + spin * 0.6; // where the arm will be in a moment: the turning direction
            line(f.dim, ground(f, from.x + Math.cos(b) * 6, from.z + Math.sin(b) * 6),
                ground(f, from.x + Math.cos(b) * 10, from.z + Math.sin(b) * 10), C.white, warn / 20 + 0.2, 1);
        }
    }
    for (let s = 0; s < span; s += 2) {
        f.after(warn + s, () => {
            const p = at(f);
            for (let k = 0; k < arms; k++) {
                const a = base + (k / arms) * 2 * Math.PI + spin * (s / 20);
                shoot(f, { ...p, angle: a, speed: speed(f, 9), color: C.gold, dmg: 4, size: 0.18 });
            }
        });
    }
    return dur;
}

// 8. Satellites: portals around the arena, each fires at the target in turn.
export function satellites(f, o = {}) {
    const a = f.arena, n = by(f, [4, 5, 6]), warn = 22;
    const base = Math.random() * 2 * Math.PI;
    const dur = warn + n * 7 + 14;
    pose(f, o, ANIM.summon, dur);
    const spots = [];
    for (let k = 0; k < n; k++) {
        const ang = base + (k / n) * 2 * Math.PI;
        spots.push({ x: a.cx + Math.cos(ang) * (a.R - 2), z: a.cz + Math.sin(ang) * (a.R - 2) });
    }
    let t = 0;
    effect(f, () => {
        if (t++ > warn + n * 7 + 10) return false;
        if (t % 6 === 1) {
            for (const s of spots) {
                pillar(f.dim, ground(f, s.x, s.z), C.white, 0.35, 4);
                if (t < warn) ring(f.dim, ground(f, s.x, s.z), 1.2, C.white, 0.33, { spacing: 0.5 });
            }
        }
        return true;
    });
    for (const s of spots) sound(f.dim, "block.end_portal_frame.fill", { ...s, y: a.floor + 1 }, 1.5, 1.2);
    spots.forEach((s, k) => {
        f.after(warn + k * 7, () => {
            const target = f.nearestTo(s);
            if (!target) return;
            const aim = yawTo(s, target.location);
            for (let i = 0; i < 3; i++) {
                f.after(i * 3, () => shoot(f, { ...s, angle: aim, speed: speed(f, 9.5), color: C.white, dmg: 4 }));
            }
            if (f.phase >= 2) {
                for (let i = 0; i < 8; i++) shoot(f, { ...s, angle: (i / 8) * 2 * Math.PI, speed: speed(f, 4), color: C.azure, dmg: 4 });
            }
            sound(f.dim, "mob.shulker.shoot", { ...s, y: a.floor + 1 }, 1.5, 1.2);
        });
    });
    return dur;
}

// 9. Nova: a zone grows around the boss and explodes (get out); in phase 3 sometimes
// the opposite: the edge explodes and only the circle next to the boss is safe.
export function nova(f, o = {}) {
    const donut = o.donut ?? (f.phase >= 3 && Math.random() < 0.5);
    const grow = by(f, [44, 40, 36]), hold = 10;
    const dur = grow + hold + 14;
    if (!o.secondary) {
        f.anim(ANIM.charge);
        f.after(grow + hold - 4, () => f.anim(ANIM.release));
        f.after(dur, () => f.anim(ANIM.idle));
    }
    const p = at(f);
    sound(f.dim, "mob.warden.sonic_charge", f.boss.location, 1.5, 1.2);
    if (donut) zone(f, { ...p, r0: 5, r1: 17, inner: 4.5, grow, hold, dmg: 10, color: C.danger });
    else zone(f, { ...p, r0: 2, r1: by(f, [8, 10, 13]), grow, hold, dmg: 9, color: C.violet });
    return dur;
}

// 9b. Trap: a circle grows under each player; step out of it.
export function trap(f, o = {}) {
    const grow = 40, hold = 8;
    const dur = grow + hold + 8;
    pose(f, o, ANIM.summon, dur);
    sound(f.dim, "mob.elderguardian.curse", f.boss.location, 0.6, 1.6);
    for (const p of f.players()) {
        zone(f, { x: p.location.x, z: p.location.z, r0: 1, r1: by(f, [4, 5, 6]), grow, hold, dmg: 8, color: C.danger, follow: p });
    }
    return dur;
}

// 10. Ground waves: the boss strikes the floor and rings run along it: jump them.
export function shock(f, o = {}) {
    const n = by(f, [2, 3, 4]), every = by(f, [18, 15, 13]);
    const dur = 16 + n * every + 24;
    pose(f, o, ANIM.slam, dur);
    const p = at(f);
    sound(f.dim, "mob.breeze.charge", f.boss.location, 2, 0.6);
    ring(f.dim, ground(f, p.x, p.z), 2.5, C.gold, 0.8, { spacing: 0.4 });
    for (let i = 0; i < n; i++) {
        f.after(16 + i * every, () => {
            wave(f, { ...p, speed: by(f, [8, 9, 10]), rMax: f.arena.R + 4, dmg: 5, color: C.gold });
            burst(f.dim, { x: p.x, y: f.arena.floor + 0.3, z: p.z }, C.gold, 16, 4);
            sound(f.dim, "random.anvil_land", f.boss.location, 0.8, 0.5);
            shake(f.dim, f.boss.location, 20, 0.12, 0.3);
        });
    }
    return dur;
}

// Close-range answer: a short-fused pulse pushes away whoever stays glued to the boss.
export function repel(f, o = {}) {
    const fuse = 16;
    pose(f, o, ANIM.charge, fuse);
    f.after(fuse - 2, () => f.anim(ANIM.release));
    f.after(fuse + 10, () => f.anim(ANIM.idle));
    sound(f.dim, "mob.warden.sonic_charge", f.boss.location, 1, 2);
    zone(f, { ...at(f), r0: 4.5, r1: 4.5, grow: fuse - 6, hold: 6, dmg: 5, color: C.danger });
    return fuse + 12;
}

/** Two attacks at once (phases 2 and 3): the second gentler, without its own pose. */
export function combo(f, first, second, delay = 10, o2 = {}) {
    const d1 = ATTACKS[first](f, {});
    f.after(delay, () => ATTACKS[second](f, { secondary: true, ...o2 }));
    return Math.max(d1, delay + 30);
}

export const ATTACKS = { volley, rings, raysFollow, raysGrid, homing, spiral, walls, cross, satellites, nova, trap, shock, repel };

/** Each phase's deck: [attack, weight] or [[first, second, delay, options], weight]. */
export const DECKS = [
    [["volley", 3], ["rings", 3], ["raysFollow", 2], ["homing", 2], ["nova", 1], ["shock", 1], ["cross", 1]],
    [["volley", 2], ["rings", 2], ["raysFollow", 1], ["raysGrid", 2], ["homing", 1], ["spiral", 2], ["walls", 2],
        ["cross", 1], ["satellites", 2], ["shock", 1], ["trap", 1],
        [["spiral", "raysFollow", 20, { strikes: 2 }], 2], [["volley", "homing", 12, { count: 2 }], 1],
        [["walls", "raysFollow", 30, { strikes: 2 }], 1]],
    [["spiral", 1], ["walls", 1], ["raysGrid", 1], ["satellites", 1], ["nova", 2], ["shock", 1], ["cross", 1], ["trap", 1],
        [["raysGrid", "rings", 24, { rings: 2 }], 2], [["satellites", "spiral", 16, { span: 40 }], 2],
        [["cross", "homing", 14, { count: 2 }], 1], [["walls", "volley", 30, { bursts: 3 }], 1],
        [["nova", "raysFollow", 6, { strikes: 2 }], 2]],
];

