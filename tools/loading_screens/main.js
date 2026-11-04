import { world, system, GameMode } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import { SCREENS } from "./screens.js";

// Artificial loading screens: a picture over the middle 80 % of the screen. While
// one is up (and 5 s more) the player has Resistance 255.
//
// Optional transition, each part on or off: a fade to black (/camera fade),
// Blindness and Darkness. With any of them the sequence is 2 s in, the screen
// for the chosen time, 3 s out.
//
//   * the Loading Screen Remote (ldscr:loading_remote) opens a form for admins;
//   * commands: /execute as <players> run scriptevent ldscr:show <screen> <seconds> [fade] [ceguera] [oscuridad]
//     and /scriptevent ldscr:hide (from a command block it applies to everyone).

const ITEM = "ldscr:loading_remote";
const IN = 2, OUT = 3, AFTER = 5; // seconds
const sessions = new Map(); // player id -> the screen sequence running for them

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);

function effect(player, name, seconds, amplifier = 0) {
    try {
        player.removeEffect(name);
        if (seconds > 0) player.addEffect(name, Math.round(seconds * 20), { amplifier, showParticles: false });
    } catch {
        // left the game
    }
}

function fade(player, fadeIn, hold, fadeOut) {
    try {
        player.camera.fade({ fadeTime: { fadeInTime: fadeIn, holdTime: hold, fadeOutTime: fadeOut },
            fadeColor: { red: 0, green: 0, blue: 0 } });
    } catch {
        player.runCommand(`camera @s fade time ${fadeIn} ${hold} ${fadeOut} color 0 0 0`);
    }
}

function putUp(player, screen, seconds) {
    player.onScreenDisplay.setTitle(screen.marker, {
        fadeInDuration: 0, stayDuration: Math.max(1, Math.round(seconds * 20)), fadeOutDuration: 0,
    });
}

function takeDown(player) {
    // The HUD keeps the last title's text after it clears, and the screen is drawn
    // while that text holds its marker: replace it with a blank title.
    try {
        player.onScreenDisplay.setTitle(" ", { fadeInDuration: 0, stayDuration: 1, fadeOutDuration: 0 });
        player.onScreenDisplay.clearTitle();
    } catch {
        // left the game
    }
}

/**
 * Shows `screen` to `player` for `seconds`. `fx`: { fade, blindness, darkness }.
 * With a transition the picture appears once the 2 s entry are over.
 */
export function showLoading(player, screen, seconds, fx = {}) {
    const replaced = stopSession(player, false);
    const transition = !!(fx.fade || fx.blindness || fx.darkness);
    const lead = transition ? IN : 0;
    if (replaced && lead) takeDown(player);
    const total = lead + seconds + (transition ? OUT : 0);
    const session = { fx, timers: [] };
    sessions.set(player.id, session);
    effect(player, "resistance", lead + seconds + AFTER, 255);
    if (fx.fade) fade(player, IN, seconds, OUT);
    if (fx.blindness) effect(player, "blindness", total);
    if (fx.darkness) effect(player, "darkness", total);
    const later = (sec, fn) => session.timers.push(system.runTimeout(fn, Math.max(1, Math.round(sec * 20))));
    if (lead) later(lead, () => isValid(player) && putUp(player, screen, seconds));
    else putUp(player, screen, seconds);
    later(lead + seconds, () => {
        if (!isValid(player)) return;
        takeDown(player);
        if (!transition) sessions.delete(player.id);
    });
    if (transition) later(total, () => sessions.get(player.id) === session && sessions.delete(player.id));
}

function stopSession(player, exit) {
    const session = sessions.get(player.id);
    if (!session) return false;
    for (const t of session.timers) system.clearRun(t);
    sessions.delete(player.id);
    if (!exit || !isValid(player)) return true;
    takeDown(player);
    // leave through the 3 s exit of whatever transition was on
    if (session.fx.fade) fade(player, 0, 0, OUT);
    if (session.fx.blindness) effect(player, "blindness", OUT);
    if (session.fx.darkness) effect(player, "darkness", OUT);
    effect(player, "resistance", AFTER, 255);
    return true;
}

export function hideLoading(player) {
    if (!stopSession(player, true) && isValid(player)) takeDown(player);
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
    const form = new ModalFormData()
        .title("Pantallas de carga")
        .dropdown("Pantalla", SCREENS.map((s) => s.name), { defaultValueIndex: 0 })
        .slider("Duración de la pantalla (segundos)", 1, 60, { valueStep: 1, defaultValue: 5 })
        .dropdown("Para", [...WHO, ...names], { defaultValueIndex: 0 })
        .toggle("Fundido a negro (2 s de entrada, 3 s de salida)", { defaultValue: true })
        .toggle("Ceguera", { defaultValue: false })
        .toggle("Oscuridad", { defaultValue: false })
        .toggle("Quitar las pantallas activas en vez de mostrar", { defaultValue: false });
    const res = await form.show(admin);
    if (res.canceled || !res.formValues) return;
    const [screenIndex, seconds, who, fadeOn, blindness, darkness, remove] = res.formValues;
    const screen = SCREENS[screenIndex] ?? SCREENS[0];
    const list = targets(admin, who, names);
    if (remove) {
        for (const p of list) hideLoading(p);
        admin.sendMessage(`§7Pantallas de carga quitadas a ${list.length} jugador(es).`);
        return;
    }
    for (const p of list) showLoading(p, screen, seconds, { fade: fadeOn, blindness, darkness });
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
    const words = (message ?? "").trim().toLowerCase().split(/\s+/).filter(Boolean);
    const screen = SCREENS.find((s) => words.includes(s.id)) ?? SCREENS[0];
    const seconds = Number(words.find((w) => !Number.isNaN(Number(w)))) || 5;
    const fx = {
        fade: words.includes("fade") || words.includes("fundido"),
        blindness: words.includes("ceguera") || words.includes("blindness"),
        darkness: words.includes("oscuridad") || words.includes("darkness"),
    };
    for (const p of list) showLoading(p, screen, Math.min(600, Math.max(1, seconds)), fx);
});

world.afterEvents.playerLeave?.subscribe(({ playerId }) => sessions.delete(playerId));
