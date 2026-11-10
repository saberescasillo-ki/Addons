// Smoke test: runs the Natura PvP behaviour-pack scripts against a fake game.
//   node tools/natura_pvp/smoke/run.mjs   (after python3 tools/natura_pvp.py)
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
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

const SONGS = Object.keys(JSON.parse(readFileSync(pjoin(root, "NaturaPvP_RP", "sounds", "sound_definitions.json"))).sound_definitions);
const SONG = (i) => SONGS[i];
const songOf = (p) => p.sounds.filter((x) => x.startsWith("natura.song.")).at(-1);
const music = (p, normal, hunt, final = 0, volume = 80) => p.setDynamicProperty("natura:music", JSON.stringify({ volume, normal, hunt, final }));
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
const builtKeys = Object.entries(state.dyn).filter(([k, v]) => k.startsWith("natura:built:") && typeof v === "string" && v !== "rebuilding");
check(builtKeys.length === 5, `las 5 zonas construidas (${builtKeys.length}) en ${state.tick} ticks, ${state.blockOps} operaciones, ${Date.now() - t0} ms`);
check(commands.length === 6, `6 comandos registrados (${commands.map((c) => c.def.name).join(", ")})`);
await advance(60);
check(state.entities.filter((e) => e.typeId === "natura:text").length === 4, "4 textos flotantes en el lobby");
check(admin.inv.getItem(0)?.typeId === "minecraft:compass" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "brújula y reloj de admin en el lobby");

// ------------------------------------------------------------ duel
console.log("Emparejamiento");
const a = join("Ana"), b = join("Beto");
await advance(20);
music(a, { mode: "one", one: 4, list: [] }, { mode: "one", one: 1, list: [] }, 6);
music(b, { mode: "list", one: 0, list: [0, 4] }, { mode: "one", one: 2, list: [] }, 6);
a.location = { x: 0.5, y: 101, z: -16.5 };
b.location = { x: 1.2, y: 101, z: -17.5 };
await advance(10);
await advance(20);
check(a.gm === "Adventure" && a.location.z > 250, "Ana está en la arena de duelo");
check(a.equip.Head?.typeId === "minecraft:diamond_helmet" && a.inv.getItem(0)?.typeId === "minecraft:diamond_sword", "kit de diamante dado");
check(a.inv.getItem(0).ench.some((e) => e.type.id === "sharpness" && e.level === 5), "espada con filo V");
check(songOf(a) === SONG(4) && songOf(b) === SONG(0), "cada jugador oye su propia canción en el duelo");
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
check(songOf(b) === SONG(0) && songOf(a) === SONG(4), "música propia en el campal (cada uno la suya)");
const aPlays = a.sounds.filter((x) => x === SONG(4)).length;
await advance(20 * 76);
check(b.sounds.includes(SONG(4)), "la lista de Beto pasa a la siguiente canción");
check(a.sounds.filter((x) => x === SONG(4)).length === aPlays + 1, "la canción única de Ana vuelve a empezar (bucle)");
world.afterEvents.entityHurt.fire({ hurtEntity: b, damage: 4, damageSource: { damagingEntity: a } });
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
check(b.messages.some((m) => m.includes("combate")), "no puede salir en combate");
await advance(20 * 9);
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
await advance(2);
check(b.location.x < 50, "Beto sale al lobby tras el combate");
check(state.commands.some((x) => x.startsWith("Beto: stopsound @s natura.song.")), "la música se para al volver al lobby");
world.afterEvents.itemUse.fire({ source: a, itemStack: a.inv.getItem(8) });
await advance(2);

// ------------------------------------------------------------ hunt
console.log("Caza");
const c = join("Caro"), d = join("Dani");
music(c, { mode: "all" }, { mode: "one", one: 3, list: [] }, 6);
music(d, { mode: "all" }, { mode: "list", one: 0, list: [5, 4] }, 6);
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
check(prey.inv.getItem(4)?.typeId === "minecraft:web" && prey.inv.getItem(4).amount === 24 && prey.inv.getItem(11)?.typeId === "minecraft:lava_bucket", "utilidades del cazado (24 telarañas con 3 cazadores, cubo de lava)");
check(hunters.every((p) => p.inv.getItem(4)?.typeId === "minecraft:shears" && p.inv.getItem(5)?.typeId === "minecraft:water_bucket"), "utilidades de los cazadores (tijeras, cubo de agua)");
const preyChoice = { Ana: 1, Beto: 2, Caro: 3, Dani: 5 }[prey.name];
check([a, b, c, d].every((p) => songOf(p) === SONG(preyChoice)), `todos oyen la música que eligió el cazado (${prey.name})`);
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
check(!prey.sounds.includes(SONG(6)), "aún no suena la del duelo final con 2 cazadores vivos");
let script = [];
const pickButton = (text) => (form) => {
  const i = form.buttons.findIndex((x) => x.includes(text));
  if (i < 0) throw new Error(`no hay botón "${text}" en ${form._title}: ${form.buttons.join(" | ")}`);
  return { canceled: false, selection: i };
};
ui.answer = (form) => {
  const next = script.shift();
  if (!next) return { canceled: true, cancelationReason: "UserClosed" };
  return next(form);
};
script = [pickButton("Caza"), pickButton("Forzar último en pie"), () => ({ canceled: false, selection: 0 })];
world.afterEvents.itemUse.fire({ source: admin, itemStack: admin.inv.getItem(8) });
await advance(25);
check(log.some((m) => m.includes("Último en pie")) && prey.bars.at(-1).includes("ÚLTIMO EN PIE") && /3:00|2:5\d/.test(prey.bars.at(-1)), "forzar último en pie: 3 minutos");
kill(hunters[1], prey);
await advance(25);
check([prey, hunters[2], hunters[0]].every((p) => songOf(p) === SONG(6)), "en el 1 contra 1 suena la canción del duelo final del cazado (también para espectadores)");
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
check(songOf(a) === SONG(6) && songOf(b) === SONG(6), "con 2 jugadores suena desde el principio la del duelo final");
leave(a.titles.some((t) => t.includes("ERES EL CAZADO")) ? b : a);
await advance(20 * 8);
check(log.some((m) => m.includes("sobrevivió")) || log.slice(-3).some((m) => m.includes("Caza")), "la caza termina cuando un jugador se va");

// ------------------------------------------------------------ admin panel
console.log("Panel de administración");
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
script = [pickButton("Mundo"), (form) => ({ canceled: false, formValues: [4, true, false, "Hola a todos"] })];
world.afterEvents.itemUse.fire({ source: admin, itemStack: Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] }) });
await advance(15);
check(state.commands.some((x) => x === "time set 14000") && log.some((m) => m.includes("Hola a todos")), "hora y anuncio");
check(!state.commands.some((x) => /weather (rain|thunder)/.test(x)) && state.commands.filter((x) => x === "weather clear").length >= 2, "clima desactivado (siempre despejado)");
for (const btn of ["Caza", "Campal", "Jugadores", "Teletransporte", "Reconstruir", "Estadísticas"]) {
  script = [pickButton(btn)];
  world.afterEvents.itemUse.fire({ source: admin, itemStack: Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] }) });
  await advance(10);
}
check(true, "submenús abiertos sin errores");
console.log("Música");
const m = join("Mel");
await advance(20);
script = [pickButton("Volumen"), () => ({ canceled: false, formValues: [40] })];
await commands.find((x) => x.def.name === "natura:musica").fn({ sourceEntity: m });
await advance(10);
check(JSON.parse(m.getDynamicProperty("natura:music")).volume === 40, "volumen al 40 %");
script = [pickButton("Emparejamiento y Campal"), (form) => ({ canceled: false, formValues: [1, 0, 4, 0, 2, ...new Array(SONGS.length - 3).fill(0)] })];
await commands.find((x) => x.def.name === "natura:musica").fn({ sourceEntity: m });
await advance(10);
check(JSON.stringify(JSON.parse(m.getDynamicProperty("natura:music")).normal) === JSON.stringify({ mode: "list", one: 0, list: [3, 1] }), "lista propia en el orden elegido");
script = [pickButton("Mi caza"), (form) => ({ canceled: false, formValues: [2, 0, ...new Array(SONGS.length).fill(0), 0] })];
await commands.find((x) => x.def.name === "natura:musica").fn({ sourceEntity: m });
await advance(10);
const mp = JSON.parse(m.getDynamicProperty("natura:music"));
check(mp.hunt.mode === "all" && mp.final === -1, "caza con todas y sin cambiar en el duelo final");
script = [pickButton("Escuchar"), pickButton("Todas, en orden")];
await commands.find((x) => x.def.name === "natura:musica").fn({ sourceEntity: m });
await advance(10);
check(songOf(m) === SONG(0) && Math.abs(m.lastVolume - 0.4) < 1e-9, "escuchar todas en el lobby, al 40 %");
await advance(20 * 60);
check(songOf(m) === SONG(1), "pasa a la siguiente canción");
const non = join("Nadie");
await advance(20);
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: non });
await advance(3);
check(non.messages.some((m) => m.includes("etiqueta")), "sin la etiqueta admin no se abre el panel");

check(warnings.length === 0, `sin avisos (${warnings.slice(0, 5).join(" / ")})`);
console.log(failures ? `\n${failures} fallo(s)` : "\nTodo bien");
process.exit(failures ? 1 : 0);
