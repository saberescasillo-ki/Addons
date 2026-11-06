import { system, world, MolangVariableMap } from "@minecraft/server";

// Visual and sound helpers. Shapes that are easy to recognise:
//   * circles, rings and zones are flat textures on the floor, with a wall of light
//     2 blocks high around their edge that fades upwards (they grow or shrink by themselves);
//   * lines on the floor are walls of light 3 blocks high, fading upwards;
//   * lasers and rays are 3D cylinders of light; bullets are 3D spinning diamonds.
// The 3D shapes are small model entities (tools/eclipse/shapes.py): the script spawns
// them with their sizes and removes them; the client animates growth and fading.

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

const ORDER = ["white", "gold", "cyan", "violet", "magenta", "azure", "crimson", "danger", "safe", "jade"];
export const colorIndex = (c) => Math.max(0, ORDER.findIndex((k) => C[k] === c));
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

// --- 3D shapes ---------------------------------------------------------------------------------
const RANGE = { w: [0, 8], len: [0, 96], spin: [-360, 360], r0: [0, 64], rate: [-64, 64], rmax: [0, 64], h: [0, 8],
    size: [0, 3], life: [0, 60] };
const live = new Map(); // entity id -> {e, until, owner, kind}
const counts = {};
let owner = null;
export const setOwner = (id) => {
    owner = id;
};
const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
export const yawOf = (dx, dz) => Math.atan2(-dx, dz) * (180 / Math.PI);

// Walls and tubes are only decoration of a warning the floor mark already shows: when
// many are asked for in the same tick, the rest wait for the next ticks (and end on time).
const SPAWNS_PER_TICK = 20;
const DEFERRABLE = new Set(["tube", "wall"]);
const queue = [];
let spawnedTick = -1, spawned = 0;

/** Spawns a shape (gem, beam, column, tube, wall) for `life` seconds, turned to `yaw`. */
export function shape(dim, kind, at, props, color, life, yaw = 0) {
    const now = system.currentTick;
    if (spawnedTick !== now) {
        spawnedTick = now;
        spawned = 0;
    }
    if (DEFERRABLE.has(kind) && spawned >= SPAWNS_PER_TICK) {
        queue.push({ dim, kind, at, props, color, life, yaw, owner, asked: now });
        return undefined;
    }
    spawned++;
    return spawnNow(dim, kind, at, props, color, life, yaw, owner);
}

function spawnNow(dim, kind, at, props, color, life, yaw, who) {
    let e;
    try {
        e = dim.spawnEntity(`eclipse:fx_${kind}`, at, { initialRotation: yaw });
        try {
            e.setRotation({ x: 0, y: yaw });
        } catch {
            // ignore
        }
        e.setProperty("eclipse:color", colorIndex(color));
        e.setProperty("eclipse:life", Math.min(60, life));
        for (const [k, v] of Object.entries(props)) {
            if (typeof v === "boolean") e.setProperty(`eclipse:${k}`, v);
            else e.setProperty(`eclipse:${k}`, Math.max(RANGE[k][0], Math.min(RANGE[k][1], v)));
        }
    } catch {
        return undefined;
    }
    live.set(e.id, { e, until: system.currentTick + Math.ceil(life * 20) + 2, owner: who, kind });
    counts[kind] = (counts[kind] ?? 0) + 1;
    return e;
}

/** Lets the shape registry remove any other entity (the blue Eclipse's clones) when it
 *  expires or its fight is cleared. */
export function track(e, life, kind = "other") {
    if (!e) return e;
    live.set(e.id, { e, until: system.currentTick + Math.ceil(life * 20) + 2, owner, kind });
    counts[kind] = (counts[kind] ?? 0) + 1;
    return e;
}

export function unshape(e) {
    if (!e) return;
    const v = live.get(e.id);
    if (v) {
        counts[v.kind]--;
        live.delete(e.id);
    }
    try {
        if (isValid(e)) e.remove();
    } catch {
        // gone
    }
}

export function clearShapes(id) {
    for (const [k, v] of live) if (v.owner === id) unshape(v.e);
    for (let i = queue.length - 1; i >= 0; i--) if (queue[i].owner === id) queue.splice(i, 1);
}

export const shapeCount = (kind) => (kind ? counts[kind] ?? 0 : live.size);

system.runInterval(() => {
    const now = system.currentTick;
    for (const [id, v] of live) if (now >= v.until) unshape(v.e);
    if (spawnedTick !== now) {
        spawnedTick = now;
        spawned = 0;
    }
    while (queue.length && spawned < SPAWNS_PER_TICK) {
        const q = queue.shift();
        const left = q.life - (now - q.asked) / 20;
        if (left <= 0.15) continue;
        spawned++;
        spawnNow(q.dim, q.kind, q.at, q.props, q.color, left, q.yaw, q.owner);
    }
}, 1);

// leftovers (a world closed mid-fight): remove shapes nobody is tracking
system.runInterval(() => {
    for (const d of ["overworld", "nether", "the_end"]) {
        try {
            for (const e of world.getDimension(d).getEntities({ families: ["eclipse_fx"] })) {
                if (!live.has(e.id)) e.remove();
            }
        } catch {
            // not loaded
        }
    }
}, 100);

// --- floor decals ---------------------------------------------------------------------------
/** A decal: radius r now, growing `speed` blocks per second (negative: shrinking), at most `max`,
 *  with a wall of light `wall` blocks high around its edge (0: none). */
function decal(kind, dim, at, r, color, life, o = {}) {
    const max = o.max ?? 64;
    particle(dim, `eclipse:decal_${kind}`, at, { radius: r, speed: o.speed ?? 0, size: max, life, color,
        alpha: o.alpha ?? 1 });
    const h = o.wall ?? 2;
    if (h > 0) shape(dim, "tube", at, { r0: r, rate: o.speed ?? 0, rmax: max, h }, color, life);
}

/** A thin glowing ring (telegraphs, a ray's closing timer, portals). */
export const ring = (dim, at, r, color, life, o = {}) => decal("ring", dim, at, r, color, life, o);
/** The same, flat only (for quick or shrinking marks). */
export const flatRing = (dim, at, r, color, life, o = {}) => decal("ring", dim, at, r, color, life, { ...o, wall: 0 });
/** A filled magic circle: the area a zone will hit. */
export const disc = (dim, at, r, color, life, o = {}) => decal("zone", dim, at, r, color, life, { alpha: 0.85, ...o });
/** A celestial ray's target sigil. */
export const target = (dim, at, r, color, life) => decal("target", dim, at, r, color, life);
/** A sun sigil: a safe place. */
export const safe = (dim, at, r, color, life) => decal("safe", dim, at, r, color, life);
/** A thick ring running along the floor (jump it). */
export const waveDecal = (dim, at, r, speed, life, color) => decal("wave", dim, at, r, color, life, { speed });

// --- cylinders and walls of light -----------------------------------------------------------------
/** A laser from `from` to `to` (horizontal), `width` blocks thick (radius). o.spin: degrees
 *  per second it turns around its middle; o.shrink: it thins out as it fades. */
export function laser(dim, from, to, color, width, life, o = {}) {
    const dx = to.x - from.x, dz = to.z - from.z;
    const len = Math.hypot(dx, dz);
    if (len < 0.05) return undefined;
    return shape(dim, "beam", { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2, z: (from.z + to.z) / 2 },
        { w: width, len, spin: o.spin ?? 0, shrink: !!o.shrink }, color, life, yawOf(dx, dz));
}

/** A line on the floor: a wall of light `h` blocks high that fades upwards. */
export function line(dim, from, to, color, life, h = 3) {
    const dx = to.x - from.x, dz = to.z - from.z;
    const len = Math.hypot(dx, dz);
    if (len < 0.05) return undefined;
    return shape(dim, "wall", { x: (from.x + to.x) / 2, y: from.y, z: (from.z + to.z) / 2 }, { len, h }, color, life,
        yawOf(dx, dz));
}

/** A celestial ray falling: a column of light that thins out. */
export function beam(dim, at, color, height = 22, width = 0.6) {
    shape(dim, "column", at, { w: width, len: height, shrink: true }, color, 0.45);
}

/** A steady column of light (safe zones, portals, teleport destinations). */
export function column(dim, at, color, life, height = 6, width = 0.45) {
    return shape(dim, "column", at, { w: width, len: height }, color, life);
}

/** A bullet's diamond (moved by hazards.js). */
export const gem = (dim, at, color, size, life) => shape(dim, "gem", at, { size }, color, life);

export const pillar = (dim, at, color, life = 0.5, height = 6) => column(dim, at, color, life, height, 0.3);

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
