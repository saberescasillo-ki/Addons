import { world, system, GameMode } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import { SCREENS, TIPS, tipsFor } from "./screens.js";

// Artificial loading screens: an image over 80 % of the screen (the rest dims),
// "Loading" in the middle and a boss tip at the bottom. While one is up (and 5 s
// more) the player has Resistance 255.
//
//   * the Loading Screen Remote (ldscr:loading_remote) opens a form for admins:
//     which screen, how many seconds and for whom;
//   * commands: /execute as <players> run scriptevent ldscr:show <screen> <seconds>
//     and /scriptevent ldscr:hide (from a command block it applies to everyone).

const ITEM = "ldscr:loading_remote";
const showing = new Map(); // player id -> token of the screen on show

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const AFTER = 5 * 20; // Resistance lasts this long after the screen
const randomTip = (screen) => {
    const tips = tipsFor(screen);
    return tips[Math.floor(Math.random() * tips.length)];
};

function resist(player, ticks) {
    try {
        player.removeEffect("resistance");
        player.addEffect("resistance", ticks, { amplifier: 255, showParticles: false });
    } catch {
        // left the game
    }
}

export function showLoading(player, screen, seconds, tip) {
    const ticks = Math.max(1, Math.round(seconds * 20));
    player.onScreenDisplay.setTitle(screen.marker, {
        fadeInDuration: 0, stayDuration: ticks, fadeOutDuration: 0, subtitle: tip ?? randomTip(screen),
    });
    resist(player, ticks + AFTER);
    const token = {};
    showing.set(player.id, token);
    system.runTimeout(() => {
        if (showing.get(player.id) !== token) return; // replaced by a newer screen
        hideLoading(player);
    }, ticks);
}

export function hideLoading(player) {
    const early = showing.has(player.id);
    showing.delete(player.id);
    try {
        if (!isValid(player)) return;
        // The HUD keeps the last title's text after it clears, and the screen is
        // drawn while that text holds its marker: replace it with a blank title.
        player.onScreenDisplay.setTitle(" ", { fadeInDuration: 0, stayDuration: 1, fadeOutDuration: 0, subtitle: " " });
        player.onScreenDisplay.clearTitle();
        if (early) resist(player, AFTER);
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
    const tips = TIPS.map(([boss, t]) => `[${boss}] ${t}`);
    const form = new ModalFormData()
        .title("Pantallas de carga")
        .dropdown("Pantalla", SCREENS.map((s) => s.name), { defaultValueIndex: 0 })
        .slider("Duración (segundos)", 1, 60, { valueStep: 1, defaultValue: 5 })
        .dropdown("Para", [...WHO, ...names], { defaultValueIndex: 0 })
        .dropdown("Consejo", ["Al azar (del jefe de la pantalla)", ...tips], { defaultValueIndex: 0 })
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
    const tip = tipIndex > 0 ? TIPS[tipIndex - 1][1] : undefined;
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
