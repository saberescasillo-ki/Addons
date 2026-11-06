import { MolangVariableMap } from "@minecraft/server";

// Visual and sound helpers. Shapes that are easy to recognise:
//   * circles, rings and zones are flat textures lying on the floor (one particle each,
//     that can grow or shrink by itself);
//   * lasers and rays are cylinders of light (a billboard that turns around its axis);
//   * bullets are diamonds pointing where they fly.
// Colour, size, life and motion come from Molang variables.

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
    jade: [0.35, 1, 0.65],
};

const ZERO = { x: 0, y: 0, z: 0 };
const UP = { x: 0, y: 1, z: 0 };

function vars(o) {
    const m = new MolangVariableMap();
    const c = o.color ?? C.white;
    m.setColorRGBA("variable.color", { red: c[0], green: c[1], blue: c[2], alpha: o.alpha ?? 1 });
    for (const k of ["radius", "count", "life", "speed", "size", "height"]) {
        if (o[k] !== undefined) m.setFloat(`variable.${k}`, o[k]);
    }
    m.setSpeedAndDirection("variable.dir", o.dir?.speed ?? 0, o.dir?.v ?? UP);
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

// --- floor decals ---------------------------------------------------------------------------
/** A decal: radius r now, growing `speed` blocks per second (negative: shrinking), at most `max`. */
function decal(kind, dim, at, r, color, life, o = {}) {
    particle(dim, `eclipse:decal_${kind}`, at, { radius: r, speed: o.speed ?? 0, size: o.max ?? 64, life, color,
        alpha: o.alpha ?? 1 });
}

/** A thin glowing ring (telegraphs, a ray's closing timer, portals). */
export const ring = (dim, at, r, color, life, o = {}) => decal("ring", dim, at, r, color, life, o);
/** A filled magic circle: the area a zone will hit. */
export const disc = (dim, at, r, color, life, o = {}) => decal("zone", dim, at, r, color, life, { alpha: 0.85, ...o });
/** A celestial ray's target sigil. */
export const target = (dim, at, r, color, life) => decal("target", dim, at, r, color, life);
/** A sun sigil: a safe place. */
export const safe = (dim, at, r, color, life) => decal("safe", dim, at, r, color, life);
/** A thick ring running along the floor (jump it). */
export const waveDecal = (dim, at, r, speed, life, color) => decal("wave", dim, at, r, color, life, { speed });

// --- cylinders of light -------------------------------------------------------------------------
/** A laser from `from` to `to`, `width` blocks thick (radius). shrink: it thins out as it fades. */
export function laser(dim, from, to, color, width, life, o = {}) {
    const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
    const len = Math.hypot(dx, dy, dz);
    if (len < 0.05) return;
    particle(dim, "eclipse:laser", { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2, z: (from.z + to.z) / 2 }, {
        color, radius: width, size: len / 2, life, speed: o.shrink ? 1 : 0, alpha: o.alpha ?? 1,
        dir: { speed: 0, v: { x: dx / len, y: dy / len, z: dz / len } } });
}

/** A faint line on the floor: where something will pass. */
export function line(dim, from, to, color, life, width = 0.09) {
    laser(dim, { ...from, y: from.y + 0.05 }, { ...to, y: to.y + 0.05 }, color, width, life, { alpha: 0.6 });
}

/** A celestial ray falling: a column of light that thins out. */
export function beam(dim, at, color, height = 22, width = 0.6) {
    laser(dim, at, { x: at.x, y: at.y + height, z: at.z }, color, width, 0.45, { shrink: true });
    laser(dim, at, { x: at.x, y: at.y + height, z: at.z }, C.white, width * 0.35, 0.3, { shrink: true });
}

/** A steady, translucent column of light (safe zones, portals, teleport destinations). */
export function column(dim, at, color, life, height = 6, width = 0.45, alpha = 0.45) {
    laser(dim, at, { x: at.x, y: at.y + height, z: at.z }, color, width, life, { alpha });
}

export const pillar = (dim, at, color, life = 0.5, height = 6) => column(dim, at, color, life, height, 0.3, 0.55);

// --- sparks ------------------------------------------------------------------------------------
export const burst = (dim, at, color, count = 24, speed = 5) => particle(dim, "eclipse:burst", at, { color, count, speed });
export const charge = (dim, at, color, radius = 2, life = 0.6, count = 20) =>
    particle(dim, "eclipse:charge", at, { color, radius, life, count, speed: radius / life });

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
