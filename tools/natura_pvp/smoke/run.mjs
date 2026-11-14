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

const MAIN = readFileSync(pjoin(root, "NaturaPvP_BP", "scripts", "main.js"), "utf8");
const BUILD = MAIN.match(/"buildVersion": ?"([^"]+)"/)[1];
const TRACKS = JSON.parse(MAIN.match(/const CFG = (\{.*\});/)[1]).tracks;
const SONG = (use) => TRACKS.find((t) => t.use === use).id;
const songOf = (p) => p.sounds.filter((x) => x.startsWith("natura.song.")).at(-1);
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
const inLobby = (p) => Math.hypot(p.location.x, p.location.z) < 80 && p.location.y > 95 && p.location.y < 120;
const huntOf = (p) => gen.HUNTS.findIndex((m) => m.inside(Math.floor(p.location.x), Math.floor(p.location.z)));
// a player joins and walks out of the epic view
const enter = async (name) => {
  const p = join(name);
  await advance(20);
  at(p, p.location.x, p.location.z - 1.2, p.location.y);
  await advance(12);
  return p;
};

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
for (let i = 0; i < 6000 && gen.AREAS.some((a) => state.dyn[`natura:built:${a.id}`] !== BUILD); i++) await advance(1);
check(gen.AREAS.every((a) => state.dyn[`natura:built:${a.id}`] === BUILD), `las ${gen.AREAS.length} zonas listas en ${state.tick} ticks (${state.blockOps} operaciones de bloques, ${Date.now() - t0} ms)`);
if (state.prebuilt) check(state.blockOps < 100, "con el mundo prebuilt no se coloca ningún bloque");
check(commands.length === 5 && !commands.some((c) => c.def.name === "natura:musica"), "5 comandos (sin el de música)");
check(state.commands.includes("gamerule sendcommandfeedback false") && state.commands.includes("gamerule commandblockoutput false"), "sin avisos de comandos");

// ------------------------------------------------------------ joining: the epic view
console.log("Vista épica al entrar");
await advance(20);
check(admin.cams.some((c) => c.location.x === -58 && c.location.y === 146) && admin.bars.some((b) => b.includes("un bloque hacia delante")), "al entrar, cámara quieta en el lobby y aviso en la barra de acción");
const clearsBefore = admin.camClears;
at(admin, admin.location.x, admin.location.z - 0.5, admin.location.y);
await advance(12);
check(admin.camClears === clearsBefore, "moverse menos de un bloque no la quita");
at(admin, admin.location.x, admin.location.z - 0.8, admin.location.y);
await advance(12);
check(admin.camClears > clearsBefore, "al moverse un bloque, fundido y entra al lobby");
check(songOf(admin) === SONG("lobby") && Math.abs(admin.volumes[SONG("lobby")] - 0.45) < 1e-9, "en el lobby suena Your New Forever (volumen 45)");
check(state.entities.filter((e) => e.typeId === "natura:text").length === 5 && state.entities.some((e) => e.nameTag.includes("SALA DE APUESTAS") && e.nameTag.includes("mantenimiento")), "textos del lobby (sala de apuestas en mantenimiento)");
check(admin.inv.getItem(0)?.typeId === "minecraft:compass" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "brújula y reloj de admin");

// ------------------------------------------------------------ the betting room (closed)
console.log("Sala de apuestas");
const door = gen.AREA.lobby.column(0, Math.floor(gen.BETTING.door.z) - 1);
check(door.some((s) => s[2] === "yellowC") && door.some((s) => s[2] === "blackC"), "la puerta del tronco está cerrada con bloques amarillos y negros");
check(!("PARKOUR" in gen), "ya no hay parkour");
script = [pick("SALA DE APUESTAS")];
world.afterEvents.itemUse.fire({ source: admin, itemStack: admin.inv.getItem(0) });
await advance(12);
check(admin.messages.some((m) => m.includes("mantenimiento")), "en el menú: sala de apuestas en mantenimiento");

// ------------------------------------------------------------ duel
console.log("Emparejamiento");
const a = await enter("Ana"), b = await enter("Beto");
at(a, ...pad("duel"));
at(b, pad("duel")[0] + 0.7, pad("duel")[1] - 0.6);
await advance(30);
const duelMap = gen.DUELS.findIndex((d) => Math.abs(a.location.x - d.cx) < 40 && Math.abs(a.location.z - d.cz) < 40);
check(duelMap >= 0, `Ana está en un mapa de duelo (${gen.DUELS[duelMap]?.name})`);
check(a.inv.getItem(3)?.amount === 16 && a.inv.getItem(5)?.amount === 8, "kit de duelo: 16 manzanas y 8 perlas");
check(state.commands.includes(`Ana: stopsound @s ${SONG("lobby")}`) && songOf(a) === SONG("lobby"), "en el duelo se para la música del lobby (y no suena otra)");
await advance(20 * 15);
check(a.titles.some((t) => t.includes("VS")) && a.titles.some((t) => t.includes("¡A PELEAR!")), "cinemática, aliste y pelea");
kill(b, a);
await advance(80);
check(inLobby(a) && inLobby(b), "los dos vuelven al lobby");
check(![a, b].some((p) => p.bars.some((x) => x.includes("⚔") || x.includes("Emparejamiento") || x.includes("♪"))), "sin avisos en la barra de acción del duelo");

// ------------------------------------------------------------ campal
console.log("Campal");
at(a, ...pad("campal"));
await advance(10);
check(a.location.x > 250 && a.inv.getItem(1)?.typeId === "minecraft:mace" && a.inv.getItem(2)?.typeId === "minecraft:diamond_spear", "campal con mazo y lanza");
world.afterEvents.itemUse.fire({ source: a, itemStack: a.inv.getItem(8) });
await advance(10);
check(inLobby(a), "sale al lobby");

// ------------------------------------------------------------ hunt (the hunters win)
console.log("Caza");
const c = await enter("Caro"), d = await enter("Dani");
for (const p of [a, b, c, d]) {
  at(p, ...pad("hunt"));
  await advance(6);
  await toLobby(p);
}
await advance(20 * 32);
const mapIdx = huntOf(a);
check(mapIdx >= 0 && [a, b, c, d].every((p) => huntOf(p) === mapIdx), `la caza empieza (${gen.HUNTS[mapIdx]?.name})`);
const prey = [a, b, c, d].find((p) => p.messages.some((x) => x.includes("Eres el §ccazado")));
const hunters = [a, b, c, d].filter((p) => p !== prey);
check(prey.equip.Offhand?.typeId === "minecraft:totem_of_undying" && prey.equip.Offhand !== undefined, "el cazado lleva un tótem en lugar del escudo");
check(prey.inv.getItem(3)?.amount === 8, `perlas del cazado: 6 (+1 por cazador extra) = ${prey.inv.getItem(3)?.amount}`);
check(hunters.every((p) => p.inv.getItem(4)?.typeId === "minecraft:spyglass" && p.inv.getItem(5)?.typeId === "minecraft:wind_charge"), "utilidades de los cazadores: catalejo y cargas de viento");
check(hunters.every((p) => ["slot.inventory 1 splash_potion 2 16", "slot.inventory 2 splash_potion 1 22", "slot.inventory 3 splash_potion 2 17"].every((x) => state.commands.includes(`${p.name}: replaceitem entity @s ${x}`))), "y pociones arrojadizas (velocidad II, curación II, lentitud)");
check([a, b, c, d].every((p) => songOf(p) === SONG("hunt")), "en la caza suena Find Your Flame");
const huntPlays = prey.sounds.filter((x) => x === SONG("hunt")).length;
await advance(20 * 30);
kill(hunters[0], prey);
await advance(10);
kill(hunters[1], prey);
await advance(25);
check(prey.titles.some((t) => t.includes("DUELO FINAL")) && prey.sounds.filter((x) => x === SONG("hunt")).length === huntPlays, "duelo final: la canción no se para ni vuelve a empezar");
check(/^§e\d+:\d\d §8· §f(~\d+|\+100) bloques$/.test(prey.bars.at(-1)), "barra de la caza: tiempo y distancia");
kill(prey, hunters[2]);
await advance(20 * 8);
check([a, b, c, d].every(inLobby) && [a, b, c, d].every((p) => songOf(p) === SONG("lobby")), "vuelven al lobby y vuelve su música");

// ------------------------------------------------------------ hunt (the hunted wins): the victory cinematic
console.log("Victoria del cazado");
for (const p of [a, b, c]) {
  at(p, ...pad("hunt"));
  await advance(6);
  await toLobby(p);
}
await advance(20 * 32);
const prey2 = [a, b, c].find((p) => p.messages.filter((x) => x.includes("Eres el §ccazado")).length === (p === prey ? 2 : 1));
const others = [a, b, c].filter((p) => p !== prey2);
const watcher = await enter("Wal");
check(inLobby(watcher), "un jugador que está en el lobby no forma parte de la ronda");
await advance(20 * 10);
for (const h of others) kill(h, prey2);
await advance(20);
const V = gen.VICTORY;
const nearRoom = (p) => Math.abs(p.location.x - V.room.x) < 20 && Math.abs(p.location.z - V.room.z) < 20;
check(nearRoom(prey2) && others.every(nearRoom) && others.every((p) => p.gm === "Spectator"), "todos los de la ronda van a la sala segura (los demás como espectadores)");
check(!nearRoom(watcher) && inLobby(watcher), "el del lobby no la ve");
check([prey2, ...others].every((p) => p.locked.has(mc.InputPermissionCategory.Movement) && p.locked.has(mc.InputPermissionCategory.Camera)), "nadie se puede mover durante la cinemática");
const z0 = prey2.location.z;
await advance(40);
check([prey2, ...others].every((p) => songOf(p) === SONG("win") && Math.abs(p.volumes[SONG("win")] - 0.65) < 1e-9), "suena Biast Win (volumen 65)");
check(prey2.location.z < z0 - 2, "el cazado camina hacia la habitación");
await advance(20 * 6);
check(state.commands.some((x) => x.includes("random.door_close")) || [prey2, ...others].every((p) => p.sounds.includes("random.door_close")), "la puerta se cierra (con sonido)");
await advance(20 * 5);
check(prey2.titles.some((t) => t.includes("VICTORIA")) && others.every((p) => p.titles.some((t) => t.includes("GANA EL CAZADO"))), "pantalla de victoria para el cazado");
check(prey2.cams.at(-1).facingLocation.y > prey2.cams.at(-1).location.y + 20, "la cámara termina mirando al sol");
await advance(20 * 3);
check([prey2, ...others].every((p) => inLobby(p) && p.locked.size === 0 && p.hud === "Reset"), "al acabar, todos al lobby con el control devuelto");

// ------------------------------------------------------------ spectator + admin
console.log("Espectador y panel");
const e1 = await enter("Eva"), f1 = await enter("Fer");
at(e1, ...pad("duel"));
at(f1, pad("duel")[0] + 0.5, pad("duel")[1]);
await advance(30);
script = [pick("ESPECTAR"), pick("Eva vs Fer")];
world.afterEvents.itemUse.fire({ source: watcher, itemStack: watcher.inv.getItem(0) });
await advance(10);
check(watcher.gm === "Spectator" && !nearRoom(watcher), "espectar un duelo");
kill(f1, e1);
await advance(80);
check(inLobby(watcher), "el espectador vuelve al lobby al acabar");
script = [pick("PARTIDAS"), pick("Volver"), () => ({ canceled: true })];
world.afterEvents.itemUse.fire({ source: admin, itemStack: clock() });
await advance(12);
script = [pick("MODO LIBRE")];
await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: admin });
await advance(12);
check(admin.gm === "Creative" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "modo libre con el reloj del panel");
script = [pick("IR A UNA ZONA"), pick("SALA DE LA VICTORIA")];
world.afterEvents.itemUse.fire({ source: admin, itemStack: clock() });
await advance(12);
check(nearRoom(admin), "el admin puede ir a la sala de la victoria");

check(warnings.length === 0, `sin avisos (${warnings.slice(0, 5).join(" / ")})`);
console.log(failures ? `\n${failures} fallo(s)` : "\nTodo bien");
process.exit(failures ? 1 : 0);
