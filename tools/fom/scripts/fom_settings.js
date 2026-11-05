import { world } from "@minecraft/server";

// Figures of Malice settings (tools/fom_fix.py). Kept in one world dynamic
// property; /xrworks:config opens the menu (fom_menu.js).

const PROPERTY = "xrworks:fom_settings";

export const HEALTH_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6];

export const SETTINGS = [
    // [key, default, kind, extra]
    ["difficulty", "normal", "choice", ["facil", "normal", "dificil", "pesadilla", "personalizada"]],
    ["healthMult", 1, "steps", HEALTH_STEPS],
    ["damageMult", 1, "steps", [0.25, 0.5, 0.6, 0.75, 1, 1.25, 1.5, 2, 2.5, 3]],
    ["maxHit", 12, "slider", [0, 30, 1]],
    ["knockbackMult", 0.5, "steps", [0, 0.25, 0.35, 0.5, 0.75, 1, 1.25, 1.5]],
    ["mpScaling", true, "toggle"],
    ["mpBonus", 0.5, "steps", [0.25, 0.5, 0.75, 1]],
    ["hitMobs", true, "toggle"],
    ["softLanding", true, "toggle"],
    ["baronRegen", true, "toggle"],
    ["baronArmor", true, "toggle"],
    ["lanternFury", false, "toggle"],
    ["telegraph", true, "toggle"],
    ["telegraphDensity", 40, "slider", [10, 120, 10]],
    ["climb", true, "toggle"],
    ["opsOnly", true, "toggle"],
];

export const PRESETS = {
    facil: { healthMult: 0.75, damageMult: 0.6, maxHit: 8, knockbackMult: 0.35 },
    normal: { healthMult: 1, damageMult: 1, maxHit: 12, knockbackMult: 0.5 },
    dificil: { healthMult: 1.5, damageMult: 1.5, maxHit: 16, knockbackMult: 0.75 },
    pesadilla: { healthMult: 2.5, damageMult: 2.5, maxHit: 0, knockbackMult: 1 },
};

const DEFAULTS = Object.fromEntries(SETTINGS.map(([k, d]) => [k, d]));
let cache;

function sanitize(key, value) {
    const def = SETTINGS.find((s) => s[0] === key);
    if (!def) return undefined;
    const [, d, kind, extra] = def;
    if (kind === "toggle") return typeof value === "boolean" ? value : d;
    if (kind === "choice") return extra.includes(value) ? value : d;
    if (kind === "steps") return extra.includes(value) ? value : d;
    if (kind === "slider") {
        const n = Number(value);
        return Number.isFinite(n) ? Math.max(extra[0], Math.min(extra[1], n)) : d;
    }
    return d;
}

function loadAll() {
    if (cache) return cache;
    let stored = {};
    try {
        const raw = world.getDynamicProperty(PROPERTY);
        if (typeof raw === "string") stored = JSON.parse(raw);
    } catch {
        stored = {};
    }
    cache = { ...DEFAULTS };
    for (const [k, v] of Object.entries(stored)) {
        const s = sanitize(k, v);
        if (s !== undefined) cache[k] = s;
    }
    return cache;
}

export function getSetting(key) {
    return loadAll()[key];
}

export function setSettings(patch) {
    const all = loadAll();
    for (const [k, v] of Object.entries(patch)) {
        const s = sanitize(k, v);
        if (s !== undefined) all[k] = s;
    }
    if (patch.difficulty && PRESETS[patch.difficulty]) Object.assign(all, PRESETS[patch.difficulty]);
    const diff = Object.fromEntries(Object.entries(all).filter(([k, v]) => DEFAULTS[k] !== v));
    world.setDynamicProperty(PROPERTY, JSON.stringify(diff));
}

export function resetSettings() {
    cache = { ...DEFAULTS };
    world.setDynamicProperty(PROPERTY, undefined);
}
