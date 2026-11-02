// Shared helpers: forms, the "who?" picker, commands and numbers.
import { ItemStack, system, world } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

export function valid(e) {
  try {
    return typeof e.isValid === "function" ? e.isValid() : e.isValid !== false;
  } catch {
    return false;
  }
}

export function online(id) {
  return world.getAllPlayers().find((p) => p.id === id);
}

export function run(entity, cmd) {
  try {
    entity.runCommand(cmd);
    return true;
  } catch {
    return false;
  }
}

// Message settings, saved on each player (Ajustes de mensajes, at the end of every menu).
const NO_ACTIONBAR = "ifrit:sin_actionbar";
const NO_CHAT = "ifrit:sin_chat";

/** Action bar message (unless the player turned them off). */
export function tell(player, msg) {
  try {
    if (player.getDynamicProperty(NO_ACTIONBAR) === true) return;
    player.onScreenDisplay.setActionBar(msg);
  } catch {}
}

/** Chat message (unless the player turned them off). */
export function say(player, msg) {
  try {
    if (player.getDynamicProperty(NO_CHAT) === true) return;
    player.sendMessage(msg);
  } catch {}
}

export async function messagesMenu(player) {
  const v = await modal(
    player,
    "§5Ajustes de mensajes",
    [
      { type: "toggle", label: "Mostrar mensajes en la barra de acción §7(encima de la barra de objetos)", value: player.getDynamicProperty(NO_ACTIONBAR) !== true },
      { type: "toggle", label: "Mostrar mensajes en el chat", value: player.getDynamicProperty(NO_CHAT) !== true },
    ],
    "Guardar"
  );
  if (!v) return;
  player.setDynamicProperty(NO_ACTIONBAR, v[0] !== true);
  player.setDynamicProperty(NO_CHAT, v[1] !== true);
}

/** The last button of every item menu. */
export function settingsButton(player) {
  return ["§8Ajustes de mensajes", () => messagesMenu(player)];
}

export function wait(ticks) {
  return new Promise((resolve) => system.runTimeout(resolve, ticks));
}

/** Parses "1,5" or "1.5"; returns def when it is not a number, and clamps to [min, max]. */
export function num(value, def, min, max) {
  const n = parseFloat(String(value ?? "").trim().replace(",", "."));
  if (!Number.isFinite(n)) return def;
  return Math.min(max, Math.max(min, n));
}

export function fmt(n) {
  return String(Math.round(n * 100) / 100);
}

/** Shows a form; waits and tries again while the player has another screen open (chat...). */
export async function show(form, player) {
  for (let i = 0; i < 20; i++) {
    if (!valid(player)) return undefined;
    const res = await form.show(player);
    if (res.canceled && res.cancelationReason === "UserBusy") {
      await wait(10);
      continue;
    }
    return res;
  }
  return undefined;
}

/** Action form from a list of [label, action] pairs. Returns false if it was closed. */
export async function menu(player, title, body, entries) {
  const form = new ActionFormData().title(title);
  if (body) form.body(body);
  for (const [label] of entries) form.button(label);
  const res = await show(form, player);
  if (!res || res.canceled || res.selection === undefined) return false;
  await entries[res.selection][1]();
  return true;
}

/** Modal form. `fields` is a list of { type, label, ... }; returns the values or undefined. */
export async function modal(player, title, fields, submit = "Aceptar") {
  const form = new ModalFormData().title(title);
  for (const f of fields) {
    if (f.type === "toggle") form.toggle(f.label, { defaultValue: !!f.value });
    else if (f.type === "slider")
      form.slider(f.label, f.min, f.max, { defaultValue: f.value ?? f.min, valueStep: f.step ?? 1 });
    else if (f.type === "dropdown") form.dropdown(f.label, f.options, { defaultValueIndex: f.value ?? 0 });
    else form.textField(f.label, f.placeholder ?? "", { defaultValue: f.value === undefined ? "" : String(f.value) });
  }
  form.submitButton(submit);
  const res = await show(form, player);
  if (!res || res.canceled || !res.formValues) return undefined;
  return res.formValues;
}

/** "Solo yo / Todos / Jugadores seleccionados". Returns a list of players, or null if cancelled. */
export async function pickTargets(player, title = "¿Para quién?") {
  let result = null;
  await menu(player, `§5${title}`, "", [
    ["Solo yo", () => (result = [player])],
    ["Todos", () => (result = world.getAllPlayers())],
    ["Jugadores seleccionados...", async () => (result = await pickPlayers(player, title))],
  ]);
  return result && result.length ? result.filter(valid) : null;
}

export async function pickPlayers(player, title = "Elegir jugadores", includeSelf = true) {
  const players = world.getAllPlayers().filter((p) => includeSelf || p.id !== player.id);
  if (players.length === 0) {
    tell(player, "§cNo hay otros jugadores conectados");
    return null;
  }
  const values = await modal(
    player,
    `§5${title}`,
    players.map((p) => ({ type: "toggle", label: p.id === player.id ? `${p.name} §7(tú)` : p.name })),
    "Aceptar"
  );
  if (!values) return null;
  const chosen = players.filter((p, i) => values[i] === true && valid(p));
  if (chosen.length === 0) tell(player, "§cNo elegiste a nadie");
  return chosen;
}

export function names(players) {
  if (players.length === world.getAllPlayers().length && players.length > 1) return "todos";
  return players.map((p) => p.name).join(", ");
}

export function inventory(player) {
  return player.getComponent("minecraft:inventory")?.container;
}

export function hasItem(player, typeId) {
  const inv = inventory(player);
  if (!inv) return false;
  for (let i = 0; i < inv.size; i++) if (inv.getItem(i)?.typeId === typeId) return true;
  return false;
}

export function giveItem(player, typeId) {
  if (hasItem(player, typeId)) return;
  const left = inventory(player)?.addItem(new ItemStack(typeId, 1));
  if (left) player.dimension.spawnItem(left, player.location);
}

export function removeItem(player, typeId) {
  const inv = inventory(player);
  if (!inv) return;
  for (let i = 0; i < inv.size; i++) if (inv.getItem(i)?.typeId === typeId) inv.setItem(i, undefined);
}

/** Color presets for fades. */
export const COLORS = [
  ["Negro", [0, 0, 0]],
  ["Blanco", [255, 255, 255]],
  ["Rojo", [220, 20, 30]],
  ["Rojo sangre", [90, 0, 6]],
  ["Verde claro", [150, 240, 140]],
  ["Celeste frío", [150, 215, 245]],
  ["Personalizado (RGB de abajo)", null],
];
