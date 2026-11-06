import { world } from "@minecraft/server";

// Difficulty: /scriptevent eclipse:dificultad facil|normal|dificil
// It changes damage and the boss's toughness, never the warnings or reaction times.

export const LEVELS = {
    facil: { dmg: 0.6, hp: 0.75, name: "Fácil" },
    normal: { dmg: 1, hp: 1, name: "Normal" },
    dificil: { dmg: 1.4, hp: 1.4, name: "Difícil" },
};
const KEY = "eclipse:difficulty";

export function level() {
    try {
        return LEVELS[world.getDynamicProperty(KEY)] ?? LEVELS.normal;
    } catch {
        return LEVELS.normal;
    }
}

export function setLevel(name) {
    if (!LEVELS[name]) return false;
    world.setDynamicProperty(KEY, name);
    return true;
}
