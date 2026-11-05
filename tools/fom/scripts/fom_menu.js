import { world, system, CommandPermissionLevel, CustomCommandStatus } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import { getSetting, setSettings, resetSettings, SETTINGS, PRESETS } from "./fom_settings.js";

// /xrworks:config (or /scriptevent xrworks:config): the Figures of Malice settings.

const LABELS = {
    difficulty: "Dificultad",
    healthMult: "Vida de los jefes (×)",
    damageMult: "Daño de los jefes (×)",
    maxHit: "Golpe máximo a jugadores (0 = sin límite)",
    knockbackMult: "Fuerza de los empujes (×)",
    mpScaling: "Más vida con más jugadores",
    mpBonus: "Vida extra por cada jugador más (×)",
    hitMobs: "Los ataques dañan a otros mobs",
    softLanding: "Caída lenta al ser lanzado por los aires",
    baronRegen: "Black Baron: se regenera fuera de combate",
    baronArmor: "Black Baron: armadura de rayo (reduce el daño con poca vida)",
    lanternFury: "Dr. Lantern: furia en la fase 2 (Fuerza)",
    telegraph: "Marcar con partículas el área de los ataques",
    telegraphDensity: "Cantidad de partículas de las marcas",
    climb: "Los jefes escalan escalones de hasta 2 bloques",
    opsOnly: "Solo los operadores cambian la configuración",
};
const DIFFICULTY = { facil: "Fácil", normal: "Normal", dificil: "Difícil", pesadilla: "Pesadilla", personalizada: "Personalizada" };

function canEdit(player) {
    if (!getSetting("opsOnly")) return true;
    try {
        if (player.playerPermissionLevel === 2) return true;
    } catch {
        // ignore
    }
    try {
        return player.getGameMode().toLowerCase() === "creative";
    } catch {
        return false;
    }
}

const fmt = (v) => (typeof v === "number" ? `${v}` : `${v}`);

export async function openMenu(player) {
    if (!canEdit(player)) {
        player.sendMessage("§cSolo los operadores pueden cambiar la configuración de Figures of Malice.");
        return;
    }
    const form = new ModalFormData().title("Figures of Malice — Configuración");
    const order = [];
    for (const [key, , kind, extra] of SETTINGS) {
        const value = getSetting(key);
        const label = LABELS[key] ?? key;
        if (kind === "toggle") form.toggle(label, { defaultValue: value });
        else if (kind === "slider") form.slider(label, extra[0], extra[1], { valueStep: extra[2], defaultValue: value });
        else {
            const options = kind === "choice" ? extra.map((o) => DIFFICULTY[o] ?? o) : extra.map((s) => `${fmt(s)}×`);
            form.dropdown(label, options, { defaultValueIndex: Math.max(0, extra.indexOf(value)) });
        }
        order.push([key, kind, extra]);
    }
    form.toggle("§cRestablecer todo a los valores por defecto", { defaultValue: false });
    const res = await form.show(player);
    if (res.canceled || !res.formValues) return;
    const values = res.formValues;
    if (values[values.length - 1]) {
        resetSettings();
        player.sendMessage("§7Figures of Malice: configuración restablecida.");
        return;
    }
    const patch = {};
    order.forEach(([key, kind, extra], i) => {
        const v = values[i];
        patch[key] = kind === "steps" || kind === "choice" ? extra[v] : v;
    });
    const before = getSetting("difficulty");
    if (patch.difficulty !== before && PRESETS[patch.difficulty]) {
        setSettings({ ...patch, ...PRESETS[patch.difficulty] }); // a new difficulty sets its values
    } else {
        const preset = PRESETS[patch.difficulty];
        const custom = preset && Object.entries(preset).some(([k, v]) => patch[k] !== v);
        setSettings({ ...patch, difficulty: custom ? "personalizada" : patch.difficulty });
    }
    player.sendMessage(`§7Figures of Malice: dificultad §f${DIFFICULTY[getSetting("difficulty")]}§7, configuración guardada.`);
}

system.beforeEvents.startup.subscribe(({ customCommandRegistry }) => {
    try {
        customCommandRegistry.registerCommand({
            name: "xrworks:config",
            description: "Figures of Malice: configuración de los jefes",
            permissionLevel: CommandPermissionLevel.Any,
            cheatsRequired: false,
        }, (origin) => {
            const p = origin.sourceEntity ?? origin.initiator;
            if (p?.typeId !== "minecraft:player") return { status: CustomCommandStatus.Failure, message: "Solo un jugador puede abrir el menú." };
            system.run(() => openMenu(p).catch(() => {}));
            return { status: CustomCommandStatus.Success };
        });
    } catch (e) {
        console.warn(`[Figures of Malice] /xrworks:config no disponible: ${e}`);
    }
});

system.afterEvents.scriptEventReceive.subscribe(({ id, sourceEntity }) => {
    if (id === "xrworks:config" && sourceEntity?.typeId === "minecraft:player") openMenu(sourceEntity).catch(() => {});
});

world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
    if (initialSpawn && canEdit(player)) {
        system.runTimeout(() => player.sendMessage("§8[Figures of Malice] §7Configuración: §f/xrworks:config"), 100);
    }
});
