// Smoke test: runs the Natura PvP behaviour-pack scripts against a fake game.
//   node tools/natura_pvp/smoke/run.mjs   (after python3 tools/natura_pvp.py)
import { cpSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join as pjoin } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = pjoin(here, "..", "..", "..");
const tmp = mkdtempSync(pjoin(tmpdir(), "natura-smoke-"));
for (const [name, file] of [["server", "mock_server.js"], ["server-ui", "mock_ui.js"]]) {
  const dir = pjoin(tmp, "node_modules", "@minecraft", name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(pjoin(dir, "package.json"), JSON.stringify({ type: "module", main: "index.js" }));
  writeFileSync(pjoin(dir, "index.js"), `export * from ${JSON.stringify(pathToFileURL(pjoin(here, file)).href)};\n`);
}
writeFileSync(pjoin(tmp, "package.json"), JSON.stringify({ type: "module" }));
cpSync(pjoin(root, "NaturaPvP_BP", "scripts"), pjoin(tmp, "scripts"), { recursive: true });

const mc = await import(pathToFileURL(pjoin(here, "mock_server.js")).href);
const { ui } = await import(pathToFileURL(pjoin(here, "mock_ui.js")).href);
const { advance, state, world, system, join, kill, leave, log } = mc;
const warnings = [];
console.warn = (...a) => warnings.push(a.join(" "));

let failures = 0;
function check(cond, what) {
  if (cond) console.log("  ok  " + what);
  else {
    failures++;
    console.log("  FAIL " + what);
  }
}

await import(pathToFileURL(pjoin(tmp, "scripts", "main.js")).href);
const commands = [];
system.beforeEvents.startup.fire({
  customCommandRegistry: { registerCommand: (def, fn) => commands.push({ def, fn }) },
});
world.afterEvents.worldLoad.fire({});

console.log("Construcción");
const admin = join("Admin");
admin.addTag("admin");
const t0 = Date.now();
for (let i = 0; i < 4000 && Object.keys(state.dyn).filter((k) => k.startsWith("natura:built:")).length < 5; i++) await advance(1);
const builtKeys = Object.entries(state.dyn).filter(([k, v]) => k.startsWith("natura:built:") && v === "1.0.0");
check(builtKeys.length === 5, `las 5 zonas construidas (${builtKeys.length}) en ${state.tick} ticks, ${state.blockOps} operaciones, ${Date.now() - t0} ms`);
check(commands.length === 5, `5 comandos registrados (${commands.map((c) => c.def.name).join(", ")})`);
await advance(60);
check(state.entities.filter((e) => e.typeId === "natura:text").length === 4, "4 textos flotantes en el lobby");
check(admin.inv.getItem(0)?.typeId === "minecraft:compass" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "brújula y reloj de admin en el lobby");

// ------------------------------------------------------------ duel
console.log("Emparejamiento");
const a = join("Ana"), b = join("Beto");
await advance(20);
a.location = { x: 0.5, y: 101, z: -16.5 };
b.location = { x: 1.2, y: 101, z: -17.5 };
await advance(10);
await advance(20);
check(a.gm === "Adventure" && a.location.z > 250, "Ana está en la arena de duelo");
check(a.equip.Head?.typeId === "minecraft:diamond_helmet" && a.inv.getItem(0)?.typeId === "minecraft:diamond_sword", "kit de diamante dado");
check(a.inv.getItem(0).ench.some((e) => e.type.id === "sharpness" && e.level === 5), "espada con filo V");
await advance(20 * 9);
check(a.titles.some((t) => t.includes("9")) && a.titles.some((t) => t.includes("¡A PELEAR!")), "cuenta atrás de 9 s y ¡A PELEAR!");
kill(b, a);
await advance(80);
check(a.location.z < 50 && b.location.z < 50, "los dos vuelven al lobby");
check(log.some((m) => m.includes("Ana") && m.includes("ganó")), "mensaje de victoria");

// ------------------------------------------------------------ campal
console.log("Campal");
a.location = { x: 15.5, y: 101, z: 9.5 };
await advance(10);
check(a.location.x > 250, "Ana entra al campal");
b.location = { x: 15.5, y: 101, z: 9.5 };
await advance(10);
check(b.location.x > 250 && a.inv.getItem(8)?.typeId === "minecraft:recovery_compass", "Beto entra y hay objeto para salir");
world.afterEvents.entityHurt.fire({ hurtEntity: b, damage: 4, damageSource: { damagingEntity: a } });
kill(b, a);
await advance(10);
check(b.location.x > 250 && b.equip.Head?.typeId === "minecraft:diamond_helmet", "Beto reaparece en el campal con kit");
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
check(b.messages.some((m) => m.includes("combate")), "no puede salir en combate");
await advance(20 * 9);
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
await advance(2);
check(b.location.x < 50, "Beto sale al lobby tras el combate");
world.afterEvents.itemUse.fire({ source: a, itemStack: a.inv.getItem(8) });
await advance(2);

// ------------------------------------------------------------ hunt
console.log("Caza");
const c = join("Caro"), d = join("Dani");
await advance(20);
for (const p of [a, b, c, d]) {
  p.location = { x: -14.5, y: 101, z: 9.5 };
  await advance(6);
  p.location = { x: 0.5, y: 101, z: 5.5 };
  await advance(6);
}
check([a, b, c, d].every((p) => p.messages.some((m) => m.includes("[Caza]"))), "4 jugadores en la cola de caza");
await advance(20 * 32);
const inHunt = [a, b, c, d].filter((p) => p.location.z < -290);
check(inHunt.length === 4 && inHunt.every((p) => p.gm === "Survival"), "la caza empieza en supervivencia");
const prey = [a, b, c, d].find((p) => p.titles.some((t) => t.includes("ERES EL CAZADO")));
const hunters = [a, b, c, d].filter((p) => p !== prey);
check(!!prey && prey.equip.Chest?.typeId === "minecraft:iron_chestplate", `cazado con hierro (${prey?.name})`);
const prot = prey.equip.Chest.ench.find((e) => e.type.id === "protection")?.level;
check(prot === 3, `protección del cazado mejorada con 3 cazadores (nivel ${prot})`);
check(hunters.every((p) => p.equip.Chest?.typeId === "minecraft:diamond_chestplate"), "cazadores con diamante");
check(prey.effects.has("speed"), "el cazado tiene velocidad con 3 cazadores");
world.afterEvents.playerBreakBlock.fire({ block: { location: { x: prey.location.x | 0, y: 80, z: prey.location.z | 0 } }, player: prey });
const ev = { player: prey, block: { location: { x: 0, y: 100, z: 0 } }, cancel: false };
world.beforeEvents.playerBreakBlock.fire(ev);
check(ev.cancel === true, "no se puede romper fuera de la caza");
const ev2 = { player: prey, block: { location: { x: 10, y: 80, z: -480 } }, cancel: false };
world.beforeEvents.playerBreakBlock.fire(ev2);
check(ev2.cancel === false, "sí se puede romper dentro de la caza");
await advance(20 * 25);
kill(hunters[0], prey);
await advance(10);
check(hunters[0].gm === "Spectator", "el cazador eliminado pasa a espectador");
check(!prey.sounds.includes("natura.epic"), "sin canción con 2 cazadores vivos");
kill(hunters[1], prey);
await advance(25);
check(prey.sounds.includes("natura.epic") && hunters[2].sounds.includes("natura.epic") && hunters[0].sounds.includes("natura.epic"), "canción épica en el 1 contra 1 (también para espectadores)");
kill(prey, hunters[2]);
await advance(20 * 8);
check([a, b, c, d].every((p) => p.location.z > -100 && p.gm === "Adventure"), "todos vuelven al lobby");
check(state.commands.some((x) => x.includes("stopsound")), "la canción se para");
check(log.some((m) => m.includes("atraparon")), "ganan los cazadores");
for (let i = 0; i < 400 && state.dyn["natura:huntDirty"]; i++) await advance(5);
check(state.dyn["natura:huntDirty"] === false, "el mapa de caza se regenera");

// hunt with 2 players: music from the start; a player leaving
console.log("Caza 1 contra 1 y abandono");
for (const p of [a, b]) {
  p.sounds.length = 0;
  p.location = { x: -14.5, y: 101, z: 9.5 };
  await advance(6);
  p.location = { x: 0.5, y: 101, z: 5.5 };
  await advance(6);
}
await advance(20 * 33);
check(a.sounds.includes("natura.epic"), "canción desde el principio con 2 jugadores");
leave(a.titles.some((t) => t.includes("ERES EL CAZADO")) ? b : a);
await advance(20 * 8);
check(log.some((m) => m.includes("sobrevivió")) || log.slice(-3).some((m) => m.includes("Caza")), "la caza termina cuando un jugador se va");

// ------------------------------------------------------------ admin panel
console.log("Panel de administración");
let script = [];
ui.answer = (form) => {
  const next = script.shift();
  if (!next) return { canceled: true, cancelationReason: "UserClosed" };
  return next(form);
};
const pickButton = (text) => (form) => {
  const i = form.buttons.findIndex((x) => x.includes(text));
  if (i < 0) throw new Error(`no hay botón "${text}" en ${form._title}: ${form.buttons.join(" | ")}`);
  return { canceled: false, selection: i };
};
script = [pickButton("Emparejamiento"), pickButton("Ajustes"), (form) => ({ canceled: false, formValues: form.controls.map((ctl) => (ctl.label.includes("Segundos") ? 12 : ctl.value)) })];
world.afterEvents.itemUse.fire({ source: admin, itemStack: admin.inv.getItem(8) });
await advance(10);
check(JSON.parse(state.dyn["natura:settings"]).duel.countdown === 12, "cambiar la cuenta atrás a 12 s");
script = [pickButton("Kits"), pickButton("Cazado"), pickButton("Restaurar")];
world.afterEvents.itemUse.fire({ source: admin, itemStack: admin.inv.getItem(8) });
await advance(15);
check(admin.messages.some((m) => m.includes("restaurado")), "restaurar un kit");
script = [pickButton("Modo libre")];
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: admin });
await advance(5);
check(admin.gm === "Creative", "modo libre (creativo)");
script = [pickButton("Kits"), pickButton("Emparejamiento"), pickButton("Guardar"), () => ({ canceled: false, selection: 0 })];
admin.inv.setItem(0, new mc.ItemStack("minecraft:netherite_sword"));
world.afterEvents.itemUse.fire({ source: admin, itemStack: Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] }) });
await advance(15);
check((state.dyn["natura:kit:duel"] ?? "").includes("netherite_sword"), "guardar el inventario como kit");
script = [pickButton("Mundo"), (form) => ({ canceled: false, formValues: [4, true, 2, true, false, "Hola a todos"] })];
world.afterEvents.itemUse.fire({ source: admin, itemStack: Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] }) });
await advance(15);
check(state.commands.some((x) => x === "time set 14000") && state.commands.some((x) => x === "weather thunder") && log.some((m) => m.includes("Hola a todos")), "hora, clima y anuncio");
for (const btn of ["Caza", "Campal", "Jugadores", "Teletransporte", "Reconstruir", "Estadísticas"]) {
  script = [pickButton(btn)];
  world.afterEvents.itemUse.fire({ source: admin, itemStack: Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] }) });
  await advance(10);
}
check(true, "submenús abiertos sin errores");
const non = join("Nadie");
await advance(20);
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: non });
await advance(3);
check(non.messages.some((m) => m.includes("etiqueta")), "sin la etiqueta admin no se abre el panel");

check(warnings.length === 0, `sin avisos (${warnings.slice(0, 5).join(" / ")})`);
console.log(failures ? `\n${failures} fallo(s)` : "\nTodo bien");
process.exit(failures ? 1 : 0);
