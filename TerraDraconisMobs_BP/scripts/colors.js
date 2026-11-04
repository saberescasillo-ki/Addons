import { world, system } from "@minecraft/server";

// Colour variants of the dragons and shield horns.
// The "terradraconis:color" property picks the texture: 1 is the original
// colour, 0 means "not chosen yet". The resource pack's render controllers
// read it, so the colour is chosen once here and then kept by the entity.
const PROP = "terradraconis:color";

// Chance of each colour, in the order of the textures (first = original).
const WEIGHTS = {
    // Crimson, sapphire, emerald, obsidian, amethyst, gold, frost
    dragon: [30, 15, 15, 15, 10, 8, 7],
    // Original, sand, rust, moss, ivory, onyx
    shield_horn: [35, 20, 15, 12, 10, 8],
};

const FAMILY = {
    "terradraconis:wild_crimson_racer": "dragon",
    "terradraconis:crimson_racer": "dragon",
    "terradraconis:savage_crimson_racer": "dragon",
    "terradraconis:male_shield_horn": "shield_horn",
    "terradraconis:female_shield_horn": "shield_horn",
    "terradraconis:baby_shield_horn": "shield_horn",
};

function pick(weights) {
    const total = weights.reduce((a, b) => a + b, 0);
    let r = Math.random() * total;
    for (let i = 0; i < weights.length; i++) {
        r -= weights[i];
        if (r < 0) return i + 1;
    }
    return 1;
}

function getColor(entity) {
    try {
        return entity.getProperty(PROP) ?? 0;
    } catch {
        return 0;
    }
}

function setColor(entity, color) {
    // A shield horn can change into its other form the same tick it spawns:
    // the first entity is already gone and the new one gets its own colour.
    if (!entity.isValid()) return;
    try {
        entity.setProperty(PROP, color);
    } catch (e) {
        console.warn(`[colors] ${entity.typeId}: ${e}`);
    }
}

function distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

// A transformation (baby growing up, a shield horn changing its gender on
// spawn) removes the old entity and creates a new one in the same place.
// The colours of recently removed entities are kept here so the new one can
// take the colour of the one it replaces.
const removed = [];

world.beforeEvents.entityRemove.subscribe(({ removedEntity }) => {
    const family = FAMILY[removedEntity.typeId];
    if (!family) return;
    const color = getColor(removedEntity);
    if (!color) return;
    removed.push({
        family,
        dimension: removedEntity.dimension.id,
        location: removedEntity.location,
        color,
        tick: system.currentTick,
    });
    if (removed.length > 64) removed.shift();
});

function colorOfReplaced(entity, family) {
    const now = system.currentTick;
    let best = -1;
    let bestDistance = 3;
    for (let i = 0; i < removed.length; i++) {
        const r = removed[i];
        if (now - r.tick > 40 || r.family !== family || r.dimension !== entity.dimension.id) continue;
        const d = distance(r.location, entity.location);
        if (d < bestDistance) {
            best = i;
            bestDistance = d;
        }
    }
    if (best < 0) return 0;
    return removed.splice(best, 1)[0].color;
}

// A newborn takes the colour of one of the adults around it (its parents).
function colorOfParent(entity, family) {
    const colors = entity.dimension
        .getEntities({ location: entity.location, maxDistance: 8 })
        .filter((e) => e.id !== entity.id && FAMILY[e.typeId] === family && e.typeId !== entity.typeId)
        .map(getColor)
        .filter((c) => c > 0);
    return colors.length ? colors[Math.floor(Math.random() * colors.length)] : 0;
}

world.afterEvents.entitySpawn.subscribe(({ entity, cause }) => {
    if (!entity.isValid()) return;
    const family = FAMILY[entity.typeId];
    if (!family) return;

    if (cause === "Transformed") {
        // Wait a moment: the old entity may be removed after this one appears.
        system.runTimeout(() => {
            if (!entity.isValid() || getColor(entity)) return;
            setColor(entity, colorOfReplaced(entity, family) || pick(WEIGHTS[family]));
        }, 2);
        return;
    }

    // Already coloured (loaded from the world, or a dragon just tamed).
    if (getColor(entity)) return;
    const inherited = cause === "Born" ? colorOfParent(entity, family) : 0;
    setColor(entity, inherited || pick(WEIGHTS[family]));
});
