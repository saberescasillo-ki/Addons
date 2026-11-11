// Smoke test: runs the Natura PvP behaviour-pack scripts against a fake game.
//   node tools/natura_pvp/smoke/run.mjs            (prebuilt world, like the .mcworld)
//   node tools/natura_pvp/smoke/run.mjs --build    (empty world: the script builds the map)
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
const gen = await import(pathToFileURL(pjoin(tmp, "scripts", "gen", "index.js")).href);
const { advance, state, world, system, join, kill, leave, log } = mc;
const warnings = [];
console.warn = (...a) => warnings.push(a.join(" "));
state.prebuilt = !process.argv.includes("--build");

let failures = 0;
function check(cond, what) {
  if (cond) console.log("  ok  " + what);
  else {
    failures++;
    console.log("  FAIL " + what);
  }
}
const at = (p, x, z, y = 101) => (p.location = { x, y, z });
const L = gen.LOBBY;
const pad = (k) => [L.pads[k].x + 0.5, L.pads[k].z + 0.5];
const toLobby = async (p) => {
  at(p, L.spawn.x, L.spawn.z);
  await advance(6);
};
const huntOf = (p) => gen.HUNTS.findIndex((m) => m.inside(Math.floor(p.location.x), Math.floor(p.location.z)));

await import(pathToFileURL(pjoin(tmp, "scripts", "main.js")).href);
const commands = [];
system.beforeEvents.startup.fire({ customCommandRegistry: { registerCommand: (def, fn) => commands.push({ def, fn }) } });
world.afterEvents.worldLoad.fire({});

let script = [];
ui.answer = (form) => {
  const next = script.shift();
  if (!next) return { canceled: true, cancelationReason: "UserClosed" };
  return next(form);
};
const pick = (text) => (form) => {
  const i = form.buttons.findIndex((x) => x.includes(text));
  if (i < 0) throw new Error(`no hay botón "${text}" en ${form._title}: ${form.buttons.join(" | ")}`);
  return { canceled: false, selection: i };
};
const yes = () => ({ canceled: false, selection: 0 });
const clock = () => Object.assign(new mc.ItemStack("minecraft:clock"), { lore: ["§8natura:menu"] });

console.log(state.prebuilt ? "Mundo prebuilt" : "Construcción por el script");
const admin = join("Admin");
admin.addTag("admin");
const t0 = Date.now();
for (let i = 0; i < 6000 && gen.AREAS.some((a) => state.dyn[`natura:built:${a.id}`] !== "1.2.0"); i++) await advance(1);
check(gen.AREAS.every((a) => state.dyn[`natura:built:${a.id}`] === "1.2.0"), `las ${gen.AREAS.length} zonas listas en ${state.tick} ticks (${state.blockOps} operaciones de bloques, ${Date.now() - t0} ms)`);
if (state.prebuilt) check(state.blockOps < 100, "con el mundo prebuilt no se coloca ningún bloque");
check(commands.length === 6, `6 comandos registrados`);
await advance(60);
check(state.entities.filter((e) => e.typeId === "natura:text").length === 5, "5 textos flotantes en el lobby");
check(admin.inv.getItem(0)?.typeId === "minecraft:compass" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "brújula y reloj de admin en el lobby");

// ------------------------------------------------------------ parkour
console.log("Parkour");
const pk = gen.PARKOUR;
at(admin, pk.startPad.x + 0.5, pk.startPad.z + 0.5);
await advance(6);
check(admin.titles.some((t) => t.includes("PARKOUR")) && admin.inv.getItem(4)?.typeId === "minecraft:recovery_compass", "pisar la plataforma azul empieza el parkour");
at(admin, pk.checkpoints[1].x, pk.checkpoints[1].z, pk.checkpoints[1].y);
await advance(6);
check(admin.titles.some((t) => t.includes("PUNTO DE CONTROL")), "punto de control");
at(admin, pk.checkpoints[1].x + 3, pk.checkpoints[1].z, pk.checkpoints[1].y - 10);
await advance(6);
check(Math.abs(admin.location.y - pk.checkpoints[1].y) < 0.01, "al caer vuelve al punto de control");
await advance(40);
at(admin, pk.finish.x, pk.finish.z, pk.finish.y);
await advance(6);
check(admin.titles.some((t) => t.includes("PARKOUR COMPLETADO")) && log.some((m) => m.includes("Árbol del Mundo")), "llegar a la meta");
await toLobby(admin);

// ------------------------------------------------------------ duel
console.log("Emparejamiento");
const a = join("Ana"), b = join("Beto");
await advance(20);
music(a, { mode: "one", one: 4, list: [] }, { mode: "one", one: 1, list: [] }, 6);
music(b, { mode: "list", one: 0, list: [0, 4] }, { mode: "one", one: 2, list: [] }, 6);
at(a, ...pad("duel"));
at(b, pad("duel")[0] + 0.7, pad("duel")[1] - 0.6);
await advance(30);
const duelMap = gen.DUELS.findIndex((d) => Math.abs(a.location.x - d.cx) < 40 && Math.abs(a.location.z - d.cz) < 40);
check(duelMap >= 0 && a.gm === "Adventure", `Ana está en un mapa de duelo (${gen.DUELS[duelMap]?.name})`);
check(a.equip.Head?.typeId === "minecraft:diamond_helmet" && a.inv.getItem(0)?.ench.some((e) => e.type.id === "sharpness" && e.level === 5), "kit de diamante encantado");
check(songOf(a) === SONG(4) && songOf(b) === SONG(0), "cada jugador oye su propia canción");
await advance(20 * 3);
check(a.cams.length >= 2 && a.hud === "Hide" && a.titles.some((t) => t.includes(gen.DUELS[duelMap].name.toUpperCase())), "cinemática de inicio con el nombre del mapa");
await advance(20 * 6);
check(a.camClears > 0 && a.hud === "Reset", "la cinemática termina");
check(!a.titles.some((t) => t.includes("¡A PELEAR!")), "aún no se pelea (aliste)");
await advance(20 * 6);
const counts = a.titles.filter((t) => /^§.§l[1-9] /.test(t + " ")).map((t) => t.match(/§l([1-9])/)[1]);
check(a.titles.some((t) => t.includes("¡A PELEAR!")) && counts.join("") === "54321", `5 segundos de aliste tras la cinemática (${counts.join(",")})`);
kill(b, a);
await advance(80);
check(Math.hypot(a.location.x, a.location.z) < 80 && Math.hypot(b.location.x, b.location.z) < 80, "los dos vuelven al lobby");
check(log.some((x) => x.includes("Ana") && x.includes("ganó") && x.includes(gen.DUELS[duelMap].name)), "mensaje de victoria con el mapa");

// ------------------------------------------------------------ campal
console.log("Campal");
const camsBefore = a.cams.length;
at(a, ...pad("campal"));
await advance(10);
at(b, ...pad("campal"));
await advance(10);
check(a.location.x > 250 && b.location.x > 250 && a.inv.getItem(8)?.typeId === "minecraft:recovery_compass", "entran al campal");
world.afterEvents.entityHurt.fire({ hurtEntity: b, damage: 4, damageSource: { damagingEntity: a } });
kill(b, a);
await advance(10);
check(b.location.x > 250 && b.equip.Head?.typeId === "minecraft:diamond_helmet" && a.cams.length === camsBefore, "reaparece en el campal con kit (y sin cinemática)");
world.afterEvents.entityHurt.fire({ hurtEntity: b, damage: 4, damageSource: { damagingEntity: a } });
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
check(b.messages.some((x) => x.includes("combate")), "no puede salir en combate");
await advance(20 * 9);
world.afterEvents.itemUse.fire({ source: b, itemStack: b.inv.getItem(8) });
await advance(2);
world.afterEvents.itemUse.fire({ source: a, itemStack: a.inv.getItem(8) });
await advance(10);
check(Math.hypot(a.location.x, a.location.z) < 80 && Math.hypot(b.location.x, b.location.z) < 80, "salen al lobby");

// ------------------------------------------------------------ hunt
console.log("Caza");
const c = join("Caro"), d = join("Dani");
music(c, { mode: "all" }, { mode: "one", one: 3, list: [] }, 6);
music(d, { mode: "all" }, { mode: "list", one: 0, list: [5, 4] }, 6);
await advance(20);
for (const p of [a, b, c, d]) {
  at(p, ...pad("hunt"));
  await advance(6);
  await toLobby(p);
}
await advance(20 * 32);
const mapIdx = huntOf(a);
check(mapIdx >= 0 && [a, b, c, d].every((p) => huntOf(p) === mapIdx && p.gm === "Adventure"), `la caza empieza en modo aventura (${gen.HUNTS[mapIdx]?.name})`);
const prey = [a, b, c, d].find((p) => p.titles.some((t) => t.includes("ERES EL CAZADO")) || p.messages.some((x) => x.includes("Eres el §ccazado")));
const hunters = [a, b, c, d].filter((p) => p !== prey);
check(!!prey && prey.equip.Chest?.typeId === "minecraft:iron_chestplate", `cazado con hierro (${prey?.name})`);
check(prey.equip.Chest.ench.find((e) => e.type.id === "protection")?.level === 3, "protección mejorada con 3 cazadores");
check(hunters.every((p) => p.equip.Chest?.typeId === "minecraft:diamond_chestplate"), "cazadores con diamante");
const web = prey.inv.getItem(2);
check(web?.typeId === "minecraft:web" && web.amount === 24 && web.placeOn?.includes("minecraft:grass_block"), "24 telarañas que solo se ponen sobre el suelo");
check(hunters.every((p) => p.inv.getItem(2)?.typeId === "minecraft:shears" && p.inv.getItem(2).destroy?.includes("minecraft:web")), "tijeras que cortan telarañas");
const chests = [...state.blocks.values()].filter((v) => v.id === "minecraft:chest");
check(chests.length === gen.HUNTS[mapIdx].chests().length && chests.every((v) => v.inv.items.some(Boolean)), `cofres con botín (${chests.length})`);
const preyChoice = { Ana: 1, Beto: 2, Caro: 3, Dani: 5 }[prey.name];
check([a, b, c, d].every((p) => songOf(p) === SONG(preyChoice)), `todos oyen la música del cazado (${prey.name})`);
const lockAt = { ...prey.location };
check(prey.cams.length >= 2, "cinemática de la caza");
await advance(20 * 8);
check(prey.titles.some((t) => t.includes("¡CORRE!")), "tras la cinemática el cazado sale corriendo");
const ev = { player: prey, block: { location: { x: Math.floor(lockAt.x), y: Math.floor(lockAt.y) - 1, z: Math.floor(lockAt.z) } }, cancel: false };
world.beforeEvents.playerBreakBlock.fire(ev);
check(ev.cancel === true, "no se pueden romper bloques en la caza");
const wpos = { x: Math.floor(lockAt.x) + 1, y: Math.floor(lockAt.y), z: Math.floor(lockAt.z) };
world.afterEvents.playerPlaceBlock.fire({ player: prey, block: { location: wpos, typeId: "minecraft:web", setType() {} } });
const ev2 = { player: hunters[0], block: { location: wpos }, cancel: false };
world.beforeEvents.playerBreakBlock.fire(ev2);
check(ev2.cancel === false, "una telaraña puesta por un jugador sí se puede cortar");
await advance(20 * 25);
kill(hunters[0], prey);
await advance(10);
check(hunters[0].gm === "Spectator", "el cazador eliminado pasa a espectador");
check(songOf(prey) !== SONG(6), "aún no suena la del duelo final");
script = [pick("PARTIDAS"), pick("ÚLTIMO EN PIE"), yes];
world.afterEvents.itemUse.fire({ source: admin, itemStack: admin.inv.getItem(8) });
await advance(25);
check(log.some((x) => x.includes("Último en pie")) && prey.bars.at(-1).includes("ÚLTIMO EN PIE") && /3:00|2:5\d/.test(prey.bars.at(-1)), "forzar último en pie: 3 minutos");
kill(hunters[1], prey);
await advance(25);
check([prey, hunters[2], hunters[0]].every((p) => songOf(p) === SONG(6)), "en el 1 contra 1 suena la canción del duelo final del cazado");
const opsBefore = state.blockOps;
kill(prey, hunters[2]);
await advance(20 * 8);
check([a, b, c, d].every((p) => Math.hypot(p.location.x, p.location.z) < 80 && p.gm === "Adventure"), "todos vuelven al lobby");
check(state.commands.some((x) => x.includes("stopsound")), "la canción se para");
for (let i = 0; i < 100 && state.blockOps === opsBefore; i++) await advance(5);
check(state.blockOps > opsBefore && state.dyn["natura:huntPlaced"] === undefined, "se quitan las telarañas puestas");

console.log("Caza 1 contra 1 y abandono");
await advance(40);
for (const p of [a, b]) {
  p.sounds.length = 0;
  at(p, ...pad("hunt"));
  await advance(6);
  await toLobby(p);
}
await advance(20 * 33 + 20 * 9);
check(songOf(a) === SONG(6) && songOf(b) === SONG(6), "con 2 jugadores suena la del duelo final al acabar la cinemática");
leave(a.messages.some((x) => x.includes("Eres el §ccazado")) ? b : a);
await advance(20 * 8);
check(log.slice(-4).some((x) => x.includes("Caza")), "la caza termina cuando un jugador se va");

// ------------------------------------------------------------ admin panel
console.log("Panel de administración");
const useClock = async () => {
  world.afterEvents.itemUse.fire({ source: admin, itemStack: clock() });
  await advance(12);
};
script = [pick("EMPAREJAMIENTO"), pick("AJUSTES"), (form) => ({ canceled: false, formValues: form.controls.map((ctl) => (ctl.label.includes("aliste") ? 8 : ctl.value)) })];
await useClock();
check(JSON.parse(state.dyn["natura:settings"]).duel.countdown === 8, "cambiar los segundos de aliste");
script = [pick("EMPAREJAMIENTO"), pick("MAPAS"), () => ({ canceled: false, formValues: [true, true, true, true, 3] })];
await useClock();
const e1 = join("Eva"), f1 = join("Fer");
await advance(20);
at(e1, ...pad("duel"));
at(f1, pad("duel")[0] + 0.5, pad("duel")[1]);
await advance(30);
check(Math.abs(e1.location.x - gen.DUELS[2].cx) < 40, "el administrador elige el siguiente mapa (Cerezal)");
kill(f1, e1);
await advance(80);
script = [pick("KITS"), pick("CAZADO"), pick("RESTAURAR")];
await useClock();
check(admin.messages.some((x) => x.includes("restaurado")), "restaurar un kit");
script = [pick("MODO LIBRE")];
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: admin });
await advance(12);
check(admin.gm === "Creative" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "modo libre (creativo) con el reloj del panel");
admin.inv.setItem(0, new mc.ItemStack("minecraft:netherite_sword"));
script = [pick("KITS"), pick("EMPAREJAMIENTO"), pick("GUARDAR"), yes];
await useClock();
check((state.dyn["natura:kit:duel"] ?? "").includes("netherite_sword"), "guardar el inventario como kit");
script = [pick("MUNDO"), () => ({ canceled: false, formValues: [4, true, false, "Hola a todos"] })];
await useClock();
check(state.commands.includes("time set 14000") && log.some((x) => x.includes("Hola a todos")), "hora y anuncio");
check(!state.commands.some((x) => /weather (rain|thunder)/.test(x)), "clima desactivado");
for (const btn of ["PARTIDAS", "CAZA", "CAMPAL", "JUGADORES", "IR A UNA ZONA", "MÁS"]) {
  script = [pick(btn), pick("Volver"), () => ({ canceled: true })];
  await useClock();
}
check(true, "todos los submenús se abren y vuelven atrás");

// ------------------------------------------------------------ music menu
console.log("Música");
const m = join("Mel");
await advance(20);
const musicCmd = () => commands.find((x) => x.def.name === "natura:musica").fn({ sourceEntity: m });
script = [pick("VOLUMEN"), pick("OTRO VALOR"), () => ({ canceled: false, formValues: [40] })];
await musicCmd();
await advance(10);
check(JSON.parse(m.getDynamicProperty("natura:music")).volume === 40, "volumen al 40 %");
script = [pick("EMPAREJAMIENTO Y CAMPAL"), pick("MI LISTA"), pick("AÑADIR"), pick("Teapot"), pick("AÑADIR"), pick("Duelo Final"), pick("USAR ESTA LISTA")];
await musicCmd();
await advance(10);
check(JSON.stringify(JSON.parse(m.getDynamicProperty("natura:music")).normal.list) === JSON.stringify([4, 0]), "lista propia en el orden elegido");
script = [pick("MI CAZA"), pick("TODAS, EN ORDEN")];
await musicCmd();
await advance(10);
script = [pick("DUELO FINAL"), pick("SEGUIR CON MI MÚSICA")];
await musicCmd();
await advance(10);
const mp = JSON.parse(m.getDynamicProperty("natura:music"));
check(mp.hunt.mode === "all" && mp.final === -1, "caza con todas y sin cambiar en el duelo final");
script = [pick("ESCUCHAR"), pick("TODAS, EN ORDEN")];
await musicCmd();
await advance(10);
check(songOf(m) === SONG(0) && Math.abs(m.lastVolume - 0.4) < 1e-9, "escuchar todas en el lobby, al 40 %");
await advance(20 * 60);
check(songOf(m) === SONG(1), "pasa a la siguiente canción");
const stops = state.commands.filter((x) => x.startsWith("Mel: stopsound")).length;
const plays = m.sounds.length;
script = [pick("VOLVER A PONER")];
await musicCmd();
await advance(10);
check(state.commands.filter((x) => x.startsWith("Mel: stopsound")).length === stops + 1 && m.sounds.length === plays + 1 && songOf(m) === SONG(1), "volver a poner la canción (primero para y luego suena)");

const non = join("Nadie");
await advance(20);
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: non });
await advance(3);
check(non.messages.some((x) => x.includes("etiqueta")), "sin la etiqueta admin no se abre el panel");

check(warnings.length === 0, `sin avisos (${warnings.slice(0, 5).join(" / ")})`);
console.log(failures ? `\n${failures} fallo(s)` : "\nTodo bien");
process.exit(failures ? 1 : 0);
