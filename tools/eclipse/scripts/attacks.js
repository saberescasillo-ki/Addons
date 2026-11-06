import { C, ring, line, laser, burst, charge, column, sound, shake } from "./fx.js";
import { shoot, ray, zone, wave, effect, laserHits, PLANE } from "./hazards.js";

// The Eclipse's attacks. Each one: a clear warning first (pose, sound, marks on the
// floor), then the attack, always with a way out (gaps, lanes, safe tiles, a jump).
// They return how many ticks they last. f is the fight (boss.js). Colour language:
// gold on the floor = jump it or stand in it; red = get out; white = about to hit.

export const ANIM = { idle: 0, point: 1, raise: 2, spin: 3, cross: 4, summon: 5, charge: 6, release: 7,
    vanish: 8, appear: 9, phase: 10, ultCharge: 11, ultRelease: 12, exhausted: 13, slam: 14, dash: 15 };

const DEG = Math.PI / 180;
const by = (f, list) => list[Math.min(list.length, f.phase) - 1];
const speed = (f, base) => base * by(f, [1, 1.15, 1.25]);
const at = (f) => ({ x: f.boss.location.x, z: f.boss.location.z });
const yawTo = (from, to) => Math.atan2(to.z - from.z, to.x - from.x);
const ground = (f, x, z, dy = 0.06) => ({ x, y: f.arena.floor + dy, z });
const chest = (f, x, z) => ({ x, y: f.arena.floor + PLANE, z });
const hand = (f) => ({ x: f.boss.location.x, y: f.arena.floor + PLANE + 0.6, z: f.boss.location.z });

/** The attack's pose for `ticks` (a later attack's pose is not undone by this one ending). */
function pose(f, o, anim, ticks) {
    if (o.secondary) return;
    const token = f.pose(anim);
    f.after(ticks, () => f.unpose(token));
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
                if (f.phase >= 2 || k % 2 === 0) shoot(f, { ...from, angle: a, speed: speed(f, 11.5), color: C.white, size: 0.18, dmg: 4 });
            }
            sound(f.dim, "mob.shulker.shoot", f.boss.location, 1, 1.5);
        });
    }
    return dur;
}

// 2. Rings: rings of bullets with gaps between them; in later phases some speed up.
export function rings(f, o = {}) {
    const count = o.rings ?? by(f, [2, 3, 4]);
    const n = by(f, [20, 24, 28]);
    const dur = 16 + count * 14 + 8;
    pose(f, o, ANIM.cross, dur);
    sound(f.dim, "chime.amethyst_block", f.boss.location, 2, 0.7);
    ring(f.dim, ground(f, ...Object.values(at(f))), 2.4, C.violet, 0.8, { speed: -2 });
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
            ring(f.dim, ground(f, from.x, from.z), 1.2, C.violet, 0.5, { speed: 9 });
            sound(f.dim, "mob.shulker.shoot", f.boss.location, 1, 0.9);
        });
    }
    return dur;
}

// 3. Celestial rays: they fall where each target stands (keep moving).
export function raysFollow(f, o = {}) {
    const strikes = o.strikes ?? by(f, [3, 4, 5]);
    const every = by(f, [13, 11, 10]), fuse = by(f, [26, 22, 20]);
    const extra = by(f, [0, 1, 2]);
    const dur = strikes * every + fuse + 8;
    pose(f, o, ANIM.raise, dur);
    sound(f.dim, "beacon.activate", f.boss.location, 2, 1.3);
    for (let i = 0; i < strikes; i++) {
        f.after(i * every, () => {
            for (const p of f.targets().slice(0, 6)) {
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

// 3c. Ray spiral: rays fall one after another along a spiral from the boss outwards.
export function raySpiral(f, o = {}) {
    const n = by(f, [14, 18, 22]), every = by(f, [3, 3, 2]), fuse = 22;
    const arms = by(f, [1, 2, 2]);
    const dur = n * every + fuse + 6;
    pose(f, o, ANIM.raise, dur);
    sound(f.dim, "beacon.activate", f.boss.location, 2, 0.9);
    const from = at(f), base = Math.random() * 2 * Math.PI, turn = Math.random() < 0.5 ? 1 : -1;
    for (let i = 0; i < n; i++) {
        f.after(i * every, () => {
            for (let k = 0; k < arms; k++) {
                const ang = base + k * Math.PI + turn * i * 0.42, d = 3 + i * 1.1;
                const x = from.x + Math.cos(ang) * d, z = from.z + Math.sin(ang) * d;
                if (f.inArena(x, z)) ray(f, x, z, { radius: 2, fuse, dmg: 7, quiet: i % 3 !== 0 });
            }
        });
    }
    return dur;
}

// 4. Homing orbs: they follow for a couple of seconds, then fly straight.
export function homing(f, o = {}) {
    const n = o.count ?? by(f, [3, 4, 5]);
    const dur = 18 + 16;
    pose(f, o, ANIM.summon, dur);
    sound(f.dim, "mob.evocation_illager.cast_spell", f.boss.location, 1.5, 0.8);
    const from = at(f), base = Math.random() * 2 * Math.PI;
    const targets = f.targets();
    for (let k = 0; k < n; k++) {
        const a = base + (k / n) * 2 * Math.PI;
        const x = from.x + Math.cos(a) * 2.2, z = from.z + Math.sin(a) * 2.2;
        const target = targets.length ? targets[k % targets.length] : f.target();
        shoot(f, { x, z, angle: target ? yawTo({ x, z }, target.location) : a, speed: speed(f, 5.6),
            hold: 18 + k * 3, r: 0.5, size: 0.4, color: C.crimson, dmg: 5, life: 160,
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

// 5b. Flower: two rings whose bullets curve opposite ways, weaving petals, then fly straight.
export function flower(f, o = {}) {
    const n = by(f, [10, 12, 14]), waves = by(f, [2, 3, 3]);
    const dur = 14 + waves * 16 + 10;
    pose(f, o, ANIM.spin, dur);
    sound(f.dim, "block.bell.hit", f.boss.location, 1.5, 1.6);
    ring(f.dim, ground(f, ...Object.values(at(f))), 3, C.jade, 0.7, { speed: -3 });
    const base = Math.random() * 2 * Math.PI;
    for (let w = 0; w < waves; w++) {
        f.after(14 + w * 16, () => {
            const from = at(f);
            for (let k = 0; k < n; k++) {
                const a = base + ((k + w * 0.5) / n) * 2 * Math.PI;
                shoot(f, { ...from, angle: a, speed: speed(f, 5.2), curve: 75 * DEG, curveTicks: 26, color: C.jade, dmg: 4 });
                shoot(f, { ...from, angle: a, speed: speed(f, 5.2), curve: -75 * DEG, curveTicks: 26, color: C.white, size: 0.18, dmg: 4 });
            }
            sound(f.dim, "chime.amethyst_block", f.boss.location, 1.2, 1.4);
        });
    }
    return dur;
}

// 5c. Constellation: a ring flies out, stops (the stars are joined by lines), then every
// star shoots at the nearest target.
export function constellation(f, o = {}) {
    const n = by(f, [10, 14, 18]), out = 18, wait = by(f, [22, 18, 16]);
    const dur = out + wait + 30;
    pose(f, o, ANIM.summon, dur);
    sound(f.dim, "mob.evocation_illager.cast_spell", f.boss.location, 1.5, 1.4);
    const from = at(f), base = Math.random() * 2 * Math.PI, sp = 7;
    const nearest = (b) => f.nearestTo(b);
    const stars = [];
    for (let k = 0; k < n; k++) {
        const a = base + (k / n) * 2 * Math.PI;
        stars.push({ x: from.x + Math.cos(a) * sp * ((out - 1) / 20), z: from.z + Math.sin(a) * sp * ((out - 1) / 20) });
        shoot(f, { ...from, angle: a, speed: sp, color: C.azure, size: 0.26, dmg: 4, life: 240,
            stop: { at: out, hold: wait, speed: speed(f, 9), aim: nearest } });
    }
    f.after(out + 1, () => {
        for (let k = 0; k < n; k++) {
            const a = stars[k], b = stars[(k + 1) % n];
            laser(f.dim, chest(f, a.x, a.z), chest(f, b.x, b.z), C.azure, 0.04, wait / 20, { alpha: 0.7 });
        }
        sound(f.dim, "random.orb", f.boss.location, 1, 0.6);
    });
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
        line(f.dim, p0, { x: p0.x + dir.x * 2 * R, y: p0.y, z: p0.z + dir.z * 2 * R }, C.safe, Math.min(life, 4), 0.12);
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

// 7. Cross: four streams from the boss (shown on the floor first), slowly turning.
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
        line(f.dim, ground(f, from.x, from.z), ground(f, from.x + Math.cos(a) * 16, from.z + Math.sin(a) * 16), C.gold, warn / 20 + 0.2, 0.1);
        if (spin) {
            const b = a + spin * 0.6; // where the arm will be in a moment: the turning direction
            line(f.dim, ground(f, from.x + Math.cos(b) * 6, from.z + Math.sin(b) * 6),
                ground(f, from.x + Math.cos(b) * 11, from.z + Math.sin(b) * 11), C.white, warn / 20 + 0.2, 0.06);
        }
    }
    for (let s = 0; s < span; s += 2) {
        f.after(warn + s, () => {
            const p = at(f);
            for (let k = 0; k < arms; k++) {
                const a = base + (k / arms) * 2 * Math.PI + spin * (s / 20);
                shoot(f, { ...p, angle: a, speed: speed(f, 9), color: C.gold, dmg: 4, size: 0.2 });
            }
        });
    }
    return dur;
}

// 8. Satellites: portals around the arena, each fires at the nearest target in turn.
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
    for (const s of spots) {
        column(f.dim, ground(f, s.x, s.z), C.white, dur / 20, 4, 0.35, 0.5);
        ring(f.dim, ground(f, s.x, s.z), 1.6, C.white, warn / 20, { speed: -1.6 / (warn / 20) });
        ring(f.dim, ground(f, s.x, s.z, 0.08), 1.1, C.azure, dur / 20);
        sound(f.dim, "block.end_portal_frame.fill", { ...s, y: a.floor + 1 }, 1.5, 1.2);
    }
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
// the opposite: the edge explodes and only the golden sun next to the boss is safe.
export function nova(f, o = {}) {
    const donut = o.donut ?? (f.phase >= 3 && Math.random() < 0.5);
    const grow = by(f, [44, 40, 36]), hold = 10;
    const dur = grow + hold + 14;
    if (!o.secondary) {
        const t1 = f.pose(ANIM.charge);
        f.after(grow + hold - 4, () => {
            if (f.unpose(t1, false)) {
                const t2 = f.pose(ANIM.release);
                f.after(18, () => f.unpose(t2));
            }
        });
    }
    const p = at(f);
    sound(f.dim, "mob.warden.sonic_charge", f.boss.location, 1.5, 1.2);
    if (donut) zone(f, { ...p, r0: 5, r1: 17, inner: 4.5, grow, hold, dmg: 10, color: C.danger });
    else zone(f, { ...p, r0: 2, r1: by(f, [8, 10, 13]), grow, hold, dmg: 9, color: C.violet });
    return dur;
}

// 9b. Trap: a circle grows under each target; step out of it.
export function trap(f, o = {}) {
    const grow = 40, hold = 8;
    const dur = grow + hold + 8;
    pose(f, o, ANIM.summon, dur);
    sound(f.dim, "mob.elderguardian.curse", f.boss.location, 0.6, 1.6);
    for (const p of f.targets().slice(0, 6)) {
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
    ring(f.dim, ground(f, p.x, p.z), 3, C.gold, 0.8, { speed: -2.5 });
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

// 11. Sweeping lasers: low golden lasers turn around the boss over a marked sector:
// jump them as they pass, or stay out of the sector.
export function sweep(f, o = {}) {
    const n = by(f, [1, 2, 3]), warn = 26, span = by(f, [60, 64, 70]);
    const w = by(f, [32, 38, 44]) * DEG * (Math.random() < 0.5 ? 1 : -1);
    const dur = warn + span + 8;
    pose(f, o, ANIM.cross, dur);
    const p = at(f), t = f.target();
    const start = (t ? yawTo(p, t.location) : Math.random() * 2 * Math.PI) - w * 0.6;
    const L = f.arena.R + 4, low = f.arena.floor + 0.35;
    const end = (a) => ({ x: p.x + Math.cos(a) * L, y: low, z: p.z + Math.sin(a) * L });
    sound(f.dim, "mob.warden.sonic_charge", f.boss.location, 1.2, 1.6);
    for (let k = 0; k < n; k++) {
        const a0 = start + (k / n) * 2 * Math.PI, a1 = a0 + w * (span / 20);
        line(f.dim, ground(f, p.x, p.z), ground(f, end(a0).x, end(a0).z), C.gold, (warn + 6) / 20, 0.16);
        line(f.dim, ground(f, p.x, p.z), ground(f, end(a1).x, end(a1).z), C.white, (warn + span) / 20, 0.05);
        for (let s = 0.25; s < 1; s += 0.25) {
            const am = a0 + (a1 - a0) * s, r = 5 + s * 6;
            line(f.dim, ground(f, p.x + Math.cos(am) * r, p.z + Math.sin(am) * r),
                ground(f, p.x + Math.cos(am) * (r + 2), p.z + Math.sin(am) * (r + 2)), C.gold, warn / 20, 0.08);
        }
    }
    for (let s = 0; s < span; s++) {
        f.after(warn + s, () => {
            if (s === 0) sound(f.dim, "beacon.activate", f.boss.location, 2, 1.8);
            for (let k = 0; k < n; k++) {
                const a = start + (k / n) * 2 * Math.PI + w * (s / 20);
                const from = { x: p.x, y: low, z: p.z };
                if (s % 2 === 0) laser(f.dim, from, end(a), C.gold, 0.22, 0.12);
                laserHits(f, from, end(a), 0.25, 5, true);
            }
        });
    }
    return dur;
}

// 12. Lattice: lasers cross the whole arena; thin red lines first, then they fire.
// Stand between them; in later phases a second (and third) set crosses the first.
function latticeSet(f, angle, warn, fire) {
    const a = f.arena, gap = by(f, [7, 6.5, 6]);
    const dir = { x: Math.cos(angle), z: Math.sin(angle) }, nrm = { x: -dir.z, z: dir.x };
    const offset = (Math.random() - 0.5) * gap;
    const beams = [];
    for (let s = -a.R + 2 + offset; s < a.R - 1; s += gap) {
        const half = Math.sqrt(Math.max(0, (a.R + 2) ** 2 - s * s));
        const c = { x: a.cx + nrm.x * s, z: a.cz + nrm.z * s };
        beams.push([chest(f, c.x - dir.x * half, c.z - dir.z * half), chest(f, c.x + dir.x * half, c.z + dir.z * half)]);
    }
    for (const [p, q] of beams) laser(f.dim, p, q, C.danger, 0.05, warn / 20, { alpha: 0.75 });
    sound(f.dim, "block.end_portal_frame.fill", f.boss.location, 1.5, 1.6);
    for (let t = 0; t < fire; t++) {
        f.after(warn + t, () => {
            for (const [p, q] of beams) {
                if (t % 2 === 0) laser(f.dim, p, q, t === 0 ? C.white : C.danger, 0.3, 0.12, { shrink: t >= fire - 2 });
                laserHits(f, p, q, 0.3, 6);
            }
            if (t === 0) sound(f.dim, "mob.warden.sonic_boom", f.boss.location, 0.5, 1.8);
        });
    }
}

export function lattice(f, o = {}) {
    const warn = 26, fire = 10, base = Math.random() * Math.PI;
    const sets = by(f, [1, 2, 3]);
    const dur = warn + fire + (sets - 1) * 24 + 6;
    pose(f, o, ANIM.raise, dur);
    for (let k = 0; k < sets; k++) {
        f.after(k * 24, () => latticeSet(f, base + (k * Math.PI) / (sets === 3 ? 3 : 2), warn, fire));
    }
    return dur;
}

// 13. Dash: a lance of light. The path is marked in red; the boss crosses the arena
// along it, and (phase 2+) leaves stars that fly out sideways.
export function dash(f, o = {}) {
    const a = f.arena, warn = by(f, [24, 20, 18]);
    const times = by(f, [1, 1, 2]);
    let t0 = 0;
    for (let d = 0; d < times; d++) {
        f.after(t0, () => {
            const p = at(f), t = f.target();
            const ang = t ? yawTo(p, t.location) : Math.random() * 2 * Math.PI;
            // as far as the arena allows, through the target
            let len = 4;
            while (len < 30 && Math.hypot(p.x + Math.cos(ang) * (len + 1) - a.cx, p.z + Math.sin(ang) * (len + 1) - a.cz) < a.R - 2) len++;
            const q = { x: p.x + Math.cos(ang) * len, z: p.z + Math.sin(ang) * len };
            const tok = f.pose(ANIM.charge);
            line(f.dim, ground(f, p.x, p.z), ground(f, q.x, q.z), C.danger, warn / 20, 0.7);
            line(f.dim, ground(f, p.x, p.z, 0.1), ground(f, q.x, q.z, 0.1), C.white, warn / 20, 0.12);
            sound(f.dim, "mob.breeze.charge", f.boss.location, 2, 1.2);
            charge(f.dim, hand(f), C.danger, 1.8, warn / 20, 20);
            f.after(warn, () => {
                f.unpose(tok, false);
                const tok2 = f.pose(ANIM.dash);
                sound(f.dim, "mob.enderdragon.flap", f.boss.location, 2, 1.4);
                const ticks = Math.ceil(len / 22 * 20);
                f.dashTo(q.x, q.z, 22, ticks);
                const hit = new Set();
                let n = 0;
                effect(f, () => {
                    if (n++ > ticks + 2) return false;
                    const l = f.boss.location;
                    for (const e of f.targets()) {
                        if (hit.has(e.id) || Math.hypot(e.location.x - l.x, e.location.z - l.z) > 1.6) continue;
                        hit.add(e.id);
                        f.hit(e, 7);
                        try {
                            e.applyKnockback({ x: -Math.sin(ang) * 1.2, z: Math.cos(ang) * 1.2 }, 0.4);
                        } catch {
                            // ignore
                        }
                    }
                    if (n % 2 === 0) burst(f.dim, { x: l.x, y: l.y + 1, z: l.z }, C.danger, 6, 2);
                    if (f.phase >= 2 && n % 3 === 0) {
                        for (const side of [1, -1]) {
                            shoot(f, { x: l.x, z: l.z, angle: ang + side * Math.PI / 2, speed: 4, hold: 14, color: C.danger, dmg: 4, life: 120 });
                        }
                    }
                    return true;
                });
                f.after(ticks + 6, () => f.unpose(tok2));
            });
        });
        t0 += warn + 26;
    }
    return t0 + 4;
}

// Close-range answer: a short-fused pulse pushes away whoever stays glued to the boss.
export function repel(f, o = {}) {
    const fuse = 16;
    const t1 = f.pose(ANIM.charge);
    f.after(fuse - 2, () => {
        f.unpose(t1, false);
        const t2 = f.pose(ANIM.release);
        f.after(12, () => f.unpose(t2));
    });
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

export const ATTACKS = { volley, rings, raysFollow, raysGrid, raySpiral, homing, spiral, flower, constellation, walls,
    cross, satellites, nova, trap, shock, sweep, lattice, dash, repel };

/** Each phase's deck: [attack, weight] or [[first, second, delay, options], weight]. */
export const DECKS = [
    [["volley", 3], ["rings", 3], ["raysFollow", 2], ["homing", 2], ["nova", 1], ["shock", 1], ["cross", 1],
        ["sweep", 2], ["constellation", 2], ["flower", 1], ["raySpiral", 1]],
    [["volley", 2], ["rings", 1], ["raysFollow", 1], ["raysGrid", 2], ["raySpiral", 1], ["homing", 1], ["spiral", 2],
        ["flower", 2], ["constellation", 1], ["walls", 2], ["cross", 1], ["satellites", 2], ["shock", 1], ["trap", 1],
        ["sweep", 2], ["lattice", 2], ["dash", 2],
        [["spiral", "raysFollow", 20, { strikes: 2 }], 2], [["volley", "homing", 12, { count: 2 }], 1],
        [["walls", "raysFollow", 30, { strikes: 2 }], 1], [["sweep", "volley", 20, { bursts: 2 }], 1]],
    [["spiral", 1], ["walls", 1], ["raysGrid", 1], ["satellites", 1], ["nova", 2], ["shock", 1], ["cross", 1], ["trap", 1],
        ["lattice", 2], ["dash", 2], ["flower", 1], ["raySpiral", 1], ["constellation", 1],
        [["raysGrid", "rings", 24, { rings: 2 }], 2], [["satellites", "spiral", 16, { span: 40 }], 2],
        [["cross", "homing", 14, { count: 2 }], 1], [["walls", "volley", 30, { bursts: 3 }], 1],
        [["nova", "raysFollow", 6, { strikes: 2 }], 2], [["sweep", "flower", 20], 1], [["lattice", "homing", 10, { count: 3 }], 1],
        [["constellation", "raySpiral", 14], 1]],
];

