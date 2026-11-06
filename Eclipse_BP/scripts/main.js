import { system, world } from "@minecraft/server";
import "./altar.js";
import "./hazards.js";
import "./boss.js";
import { setLevel, level, LEVELS } from "./settings.js";

// The Eclipse: a bullet-hell boss. /scriptevent eclipse:dificultad facil|normal|dificil

system.afterEvents.scriptEventReceive.subscribe(({ id, message, sourceEntity }) => {
    if (id !== "eclipse:dificultad") return;
    const name = message.trim().toLowerCase();
    const tell = (text) => (sourceEntity?.typeId === "minecraft:player" ? sourceEntity.sendMessage(text) : world.sendMessage(text));
    if (!setLevel(name)) {
        tell(`§8[Eclipse] §7Dificultad actual: §f${level().name}§7. Opciones: ${Object.keys(LEVELS).join(", ")}`);
        return;
    }
    tell(`§8[Eclipse] §7Dificultad: §f${level().name}`);
});
