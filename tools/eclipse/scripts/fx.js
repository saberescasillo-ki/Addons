import { MolangVariableMap } from "@minecraft/server";

// Visual and sound helpers. Every particle takes its colour, size, life and motion
// from Molang variables, so a handful of particle files draw all the attacks.

export const C = {
    white: [1, 1, 1],
    gold: [1, 0.8, 0.28],
    cyan: [0.4, 0.92, 1],
    violet: [0.68, 0.42, 1],
    magenta: [1, 0.35, 0.82],
    azure: [0.35, 0.55, 1],
    crimson: [1, 0.22, 0.3],
    danger: [1, 0.25, 0.4],
    safe: [1, 0.9, 0.45],
};

const ZERO = { x: 0, y: 0, z: 0 };

function vars(o) {
    const m = new MolangVariableMap();
    const c = o.color ?? C.white;
    m.setColorRGBA("variable.color", { red: c[0], green: c[1], blue: c[2], alpha: o.alpha ?? 1 });
    for (const k of ["radius", "count", "life", "speed", "size", "height"]) {
        if (o[k] !== undefined) m.setFloat(`variable.${k}`, o[k]);
    }
    if (o.dir) m.setSpeedAndDirection("variable.dir", o.dir.speed, o.dir.v);
    m.setVector3("variable.acc", o.acc ?? ZERO);
    return m;
}

export function particle(dim, id, at, o = {}) {
    try {
        dim.spawnParticle(id, at, vars(o));
    } catch {
        // unloaded chunk
    }
}

export function sound(dim, id, at, volume = 1, pitch = 1) {
    try {
        dim.playSound(id, at, { volume, pitch });
    } catch {
        // ignore
    }
}

/** A flat ring of dots on the ground (moving outwards at `speed`). */
export function ring(dim, at, radius, color, life, o = {}) {
    const count = Math.max(8, Math.min(o.max ?? 160, Math.round((2 * Math.PI * radius) / (o.spacing ?? 0.6))));
    particle(dim, "eclipse:ring", at, { radius, count, life, color, speed: o.speed ?? 0, size: o.size ?? 0.16,
        alpha: o.alpha ?? 1 });
}

/** A faint filled disc on the ground. */
export function disc(dim, at, radius, color, life, density = 0.5) {
    const count = Math.max(6, Math.min(140, Math.round(Math.PI * radius * radius * density)));
    particle(dim, "eclipse:disc", at, { radius, count, life, color, size: 0.22, alpha: 0.45 });
}

/** Dots along a line on the ground. */
export function line(dim, from, to, color, life, spacing = 1) {
    const dx = to.x - from.x, dz = to.z - from.z;
    const n = Math.max(1, Math.round(Math.hypot(dx, dz) / spacing));
    for (let i = 0; i <= n; i++) {
        particle(dim, "eclipse:dot", { x: from.x + (dx * i) / n, y: from.y, z: from.z + (dz * i) / n },
            { color, life, size: 0.2 });
    }
}

export const beam = (dim, at, color, height = 22) => particle(dim, "eclipse:beam", at, { color, height });
export const burst = (dim, at, color, count = 24, speed = 5) => particle(dim, "eclipse:burst", at, { color, count, speed });
export const charge = (dim, at, color, radius = 2, life = 0.6, count = 20) =>
    particle(dim, "eclipse:charge", at, { color, radius, life, count, speed: radius / life });
export const pillar = (dim, at, color, life = 0.5, height = 6) =>
    particle(dim, "eclipse:pillar", at, { color, life, height, count: Math.round(height * 2.5) });

export function shake(dim, at, r, power, seconds) {
    try {
        dim.runCommand(`camerashake add @a[x=${at.x},y=${at.y},z=${at.z},r=${r}] ${power} ${seconds} positional`);
    } catch {
        // ignore
    }
}

export function flash(player, r = 255, g = 255, b = 255, hold = 0.15) {
    try {
        player.runCommand(`camera @s fade time 0.08 ${hold} 0.6 color ${r} ${g} ${b}`);
    } catch {
        // ignore
    }
}
