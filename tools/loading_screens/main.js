import { world, system, GameMode } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import { SCREENS } from "./screens.js";

// Artificial loading screens: an image over 80 % of the screen, "Loading" in the
// middle and a boss tip at the bottom. They do nothing else (for now).
//
//   * the Loading Screen Remote (ldscr:loading_remote) opens a form for admins:
//     which screen, how many seconds and for whom;
//   * commands: /execute as <players> run scriptevent ldscr:show <screen> <seconds>
//     and /scriptevent ldscr:hide (from a command block it applies to everyone).

const ITEM = "ldscr:loading_remote";
const showing = new Map(); // player id -> token of the screen on show

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const randomTip = (screen) => screen.tips[Math.floor(Math.random() * screen.tips.length)];

export function showLoading(player, screen, seconds, tip) {
    const ticks = Math.max(1, Math.round(seconds * 20));
    player.onScreenDisplay.setTitle(screen.marker, {
        fadeInDuration: 0, stayDuration: ticks, fadeOutDuration: 0, subtitle: tip ?? randomTip(screen),
    });
    const token = {};
    showing.set(player.id, token);
    system.runTimeout(() => {
        if (showing.get(player.id) !== token) return; // replaced by a newer screen
        hideLoading(player);
    }, ticks);
}

export function hideLoading(player) {
    showing.delete(player.id);
    try {
        if (isValid(player)) player.onScreenDisplay.clearTitle();
    } catch {
        // left the game
    }
}

function isAdmin(player) {
    try {
        if (player.playerPermissionLevel === 2) return true; // operator
    } catch {
        // older game: no permission level
    }
    try {
        if (player.isOp?.()) return true;
    } catch {
        // not available
    }
    const mode = player.getGameMode();
    return mode === GameMode.Creative || mode === GameMode.creative;
}

const WHO = ["Todos", "Todos menos yo", "Solo yo", "Cercanos (32 bloques)"];

function targets(admin, choice, names) {
    const all = world.getAllPlayers();
    switch (choice) {
        case 0: return all;
        case 1: return all.filter((p) => p.id !== admin.id);
        case 2: return [admin];
        case 3: return admin.dimension.getPlayers({ location: admin.location, maxDistance: 32 });
        default: return all.filter((p) => p.name === names[choice - WHO.length]);
    }
}

async function openRemote(admin) {
    if (!isAdmin(admin)) {
        admin.onScreenDisplay.setActionBar("§cSolo los administradores pueden usar el control de pantallas de carga.");
        return;
    }
    const names = world.getAllPlayers().map((p) => p.name);
    const tips = SCREENS[0].tips;
    const form = new ModalFormData()
        .title("Pantallas de carga")
        .dropdown("Pantalla", SCREENS.map((s) => s.name), { defaultValueIndex: 0 })
        .slider("Duración (segundos)", 1, 60, { valueStep: 1, defaultValue: 5 })
        .dropdown("Para", [...WHO, ...names], { defaultValueIndex: 0 })
        .dropdown("Consejo", ["Al azar", ...tips], { defaultValueIndex: 0 })
        .toggle("Quitar las pantallas activas en vez de mostrar", { defaultValue: false });
    const res = await form.show(admin);
    if (res.canceled || !res.formValues) return;
    const [screenIndex, seconds, who, tipIndex, remove] = res.formValues;
    const screen = SCREENS[screenIndex] ?? SCREENS[0];
    const list = targets(admin, who, names);
    if (remove) {
        for (const p of list) hideLoading(p);
        admin.sendMessage(`§7Pantallas de carga quitadas a ${list.length} jugador(es).`);
        return;
    }
    const tip = tipIndex > 0 ? screen.tips[tipIndex - 1] : undefined;
    for (const p of list) showLoading(p, screen, seconds, tip ?? randomTip(screen));
    admin.sendMessage(`§7"${screen.name}" mostrada a ${list.length} jugador(es) durante ${seconds} s.`);
}

world.afterEvents.itemUse.subscribe(({ source, itemStack }) => {
    if (itemStack?.typeId !== ITEM || source?.typeId !== "minecraft:player") return;
    openRemote(source).catch(() => {});
});

system.afterEvents.scriptEventReceive.subscribe(({ id, message, sourceEntity }) => {
    if (id !== "ldscr:show" && id !== "ldscr:hide") return;
    const list = sourceEntity?.typeId === "minecraft:player" ? [sourceEntity] : world.getAllPlayers();
    if (id === "ldscr:hide") {
        for (const p of list) hideLoading(p);
        return;
    }
    const words = (message ?? "").trim().split(/\s+/).filter(Boolean);
    const screen = SCREENS.find((s) => s.id === words[0]) ?? SCREENS[0];
    const seconds = Number(words.find((w) => !Number.isNaN(Number(w)))) || 5;
    for (const p of list) showLoading(p, screen, Math.min(600, Math.max(1, seconds)));
});

world.afterEvents.playerLeave?.subscribe(({ playerId }) => showing.delete(playerId));
