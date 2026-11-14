// Smoke test: runs the Natura PvP behaviour-pack scripts against a fake game.
//   node tools/natura_pvp/smoke/run.mjs                    (everything, prebuilt world like the .mcworld)
//   node tools/natura_pvp/smoke/run.mjs victoria caza      (only some parts)
//   node tools/natura_pvp/smoke/run.mjs --build            (empty world: the script builds the map)
//   node tools/natura_pvp/smoke/run.mjs --lista            (the parts)
// Every part makes its own players, so each one can run alone.
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
const { advance, state, world, system, join, kill, log } = mc;
const warnings = [];
console.warn = (...a) => warnings.push(a.join(" "));
const args = process.argv.slice(2);
state.prebuilt = !args.includes("--build");

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
const V = gen.VICTORY;
const pad = (k) => [L.pads[k].x + 0.5, L.pads[k].z + 0.5];
const toLobby = async (p) => {
  at(p, L.spawn.x, L.spawn.z);
  await advance(6);
};
const inLobby = (p) => Math.hypot(p.location.x, p.location.z) < 80 && p.location.y > 95 && p.location.y < 120;
const nearRoom = (p) => Math.abs(p.location.x - V.room.x) < 20 && Math.abs(p.location.z - V.room.z) < 20;
const huntOf = (p) => gen.HUNTS.findIndex((m) => m.inside(Math.floor(p.location.x), Math.floor(p.location.z)));
let n = 0;
// a player joins and walks out of the epic view
const enter = async (name) => {
  const p = join(`${name}${++n}`);
  await advance(20);
  at(p, p.location.x, p.location.z - 1.2, p.location.y);
  await advance(12);
  return p;
};
const isPrey = (p) => p.messages.some((x) => x.includes("Eres el §ccazado"));
// gives the hunt of the part before time to end
const huntIdle = () => advance(40);
const joinHunt = async (players) => {
  for (const p of players) {
    at(p, ...pad("hunt"));
    await advance(6);
    await toLobby(p);
  }
  await advance(20 * 32);
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

// ------------------------------------------------------------ always: the world and an admin
console.log(state.prebuilt ? "Mundo prebuilt" : "Construcción por el script");
const admin = join("Admin");
admin.addTag("admin");
const t0 = Date.now();
for (let i = 0; i < 6000 && gen.AREAS.some((a) => state.dyn[`natura:built:${a.id}`] !== BUILD); i++) await advance(1);
check(gen.AREAS.every((a) => state.dyn[`natura:built:${a.id}`] === BUILD), `las ${gen.AREAS.length} zonas listas en ${state.tick} ticks (${state.blockOps} operaciones de bloques, ${Date.now() - t0} ms)`);
if (state.prebuilt) check(state.blockOps < 100, "con el mundo prebuilt no se coloca ningún bloque");
await advance(20);
at(admin, admin.location.x, admin.location.z - 1.2, admin.location.y);
await advance(12);
const useClock = async (steps) => {
  script = steps;
  world.afterEvents.itemUse.fire({ source: admin, itemStack: clock() });
  await advance(12);
};

const PARTS = {
  // ---------------------------------------------------------- joining
  async entrada() {
    check(commands.length === 5 && !commands.some((c) => c.def.name === "natura:musica"), "5 comandos (sin el de música)");
    check(state.commands.includes("gamerule sendcommandfeedback false") && state.commands.includes("gamerule commandblockoutput false"), "sin avisos de comandos");
    const p = join(`Nuevo${++n}`);
    await advance(20);
    check(p.cams.some((c) => c.location.x === -58 && c.location.y === 146) && p.bars.some((b) => b.includes("un bloque hacia delante")), "al entrar, cámara quieta en el lobby y aviso en la barra de acción");
    const clears = p.camClears;
    at(p, p.location.x, p.location.z - 0.5, p.location.y);
    await advance(12);
    check(p.camClears === clears, "moverse menos de un bloque no la quita");
    at(p, p.location.x, p.location.z - 0.8, p.location.y);
    await advance(12);
    check(p.camClears > clears, "al moverse un bloque, fundido y entra al lobby");
    check(songOf(p) === SONG("lobby") && Math.abs(p.volumes[SONG("lobby")] - 0.45) < 1e-9, "en el lobby suena Your New Forever (volumen 45)");
    check(state.entities.filter((e) => e.typeId === "natura:text").length === 5, "5 textos en el lobby");
    check(p.inv.getItem(0)?.typeId === "minecraft:compass" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "brújula, y reloj para el admin");
  },

  // ---------------------------------------------------------- the betting room
  async apuestas() {
    await advance(45); // the texts of the lobby appear every 2 s
    const door = gen.AREA.lobby.column(0, Math.floor(gen.BETTING.door.z) - 1);
    check(door.some((s) => s[2] === "yellowC") && door.some((s) => s[2] === "blackC"), "la puerta del tronco está cerrada con bloques amarillos y negros");
    check(!("PARKOUR" in gen), "ya no hay parkour");
    check(state.entities.some((e) => e.nameTag.includes("SALA DE APUESTAS") && e.nameTag.includes("mantenimiento")), "texto: sala de apuestas (mantenimiento)");
    const p = await enter("Apostador");
    script = [pick("SALA DE APUESTAS")];
    world.afterEvents.itemUse.fire({ source: p, itemStack: p.inv.getItem(0) });
    await advance(12);
    check(p.messages.some((m) => m.includes("mantenimiento")), "en el menú: en mantenimiento");
  },

  // ---------------------------------------------------------- Emparejamiento
  async duelo() {
    const a = await enter("Ana"), b = await enter("Beto");
    at(a, ...pad("duel"));
    at(b, pad("duel")[0] + 0.7, pad("duel")[1] - 0.6);
    await advance(30);
    const i = gen.DUELS.findIndex((d) => Math.abs(a.location.x - d.cx) < 40 && Math.abs(a.location.z - d.cz) < 40);
    check(i >= 0, `en un mapa de duelo (${gen.DUELS[i]?.name})`);
    check(a.inv.getItem(3)?.amount === 16 && a.inv.getItem(5)?.amount === 8, "kit: 16 manzanas y 8 perlas");
    check(state.commands.includes(`${a.name}: stopsound @s ${SONG("lobby")}`), "se para la música del lobby (el duelo no tiene)");
    await advance(20 * 15);
    check(a.titles.some((t) => t.includes("VS")) && a.titles.some((t) => t.includes("¡A PELEAR!")), "cinemática, aliste y pelea");
    kill(b, a);
    await advance(80);
    check(inLobby(a) && inLobby(b), "los dos vuelven al lobby");
    check(![a, b].some((p) => p.bars.some((x) => x.includes("⚔") || x.includes("Emparejamiento") || x.includes("♪"))), "sin avisos en la barra de acción");
  },

  // ---------------------------------------------------------- Campal
  async campal() {
    const a = await enter("Cam");
    at(a, ...pad("campal"));
    await advance(10);
    check(a.location.x > 250, "entra al campal");
    check(a.inv.getItem(1)?.typeId === "minecraft:mace" && a.inv.getItem(2)?.typeId === "minecraft:diamond_spear" && a.inv.getItem(3)?.amount === 16, "mazo, lanza y 16 cargas de viento");
    check(["slot.inventory 1 splash_potion 1 22", "slot.inventory 2 splash_potion 1 31", "slot.inventory 3 splash_potion 1 16"].every((c) => state.commands.includes(`${a.name}: replaceitem entity @s ${c}`)), "3 pociones");
    world.afterEvents.itemUse.fire({ source: a, itemStack: a.inv.getItem(8) });
    await advance(10);
    check(inLobby(a), "sale al lobby");
  },

  // ---------------------------------------------------------- Caza (the hunters win)
  async caza() {
    await huntIdle();
    const ps = [await enter("Ca"), await enter("Cb"), await enter("Cc"), await enter("Cd")];
    await joinHunt(ps);
    const m = huntOf(ps[0]);
    check(m >= 0 && ps.every((p) => huntOf(p) === m), `la caza empieza (${gen.HUNTS[m]?.name})`);
    const prey = ps.find(isPrey);
    const hunters = ps.filter((p) => p !== prey);
    check(prey.equip.Offhand?.typeId === "minecraft:totem_of_undying", "el cazado lleva un tótem en lugar del escudo");
    check(prey.inv.getItem(3)?.amount === 8, `perlas del cazado: 6 (+1 por cazador extra) = ${prey.inv.getItem(3)?.amount}`);
    check(hunters.every((p) => p.inv.getItem(4)?.typeId === "minecraft:spyglass" && p.inv.getItem(5)?.typeId === "minecraft:wind_charge"), "cazadores: catalejo y cargas de viento");
    check(hunters.every((p) => ["slot.inventory 1 splash_potion 2 16", "slot.inventory 2 splash_potion 1 22", "slot.inventory 3 splash_potion 2 17"].every((x) => state.commands.includes(`${p.name}: replaceitem entity @s ${x}`))), "cazadores: pociones arrojadizas");
    check(ps.every((p) => songOf(p) === SONG("hunt")), "suena Find Your Flame");
    const plays = prey.sounds.filter((x) => x === SONG("hunt")).length;
    await advance(20 * 30);
    kill(hunters[0], prey);
    await advance(10);
    kill(hunters[1], prey);
    await advance(25);
    check(prey.titles.some((t) => t.includes("DUELO FINAL")) && prey.sounds.filter((x) => x === SONG("hunt")).length === plays, "duelo final: la canción no se para ni vuelve a empezar");
    check(/^§e\d+:\d\d §8· §f(~\d+|\+100) bloques$/.test(prey.bars.at(-1)), "barra de la caza: tiempo y distancia");
    await useClock([pick("PARTIDAS"), pick("ÚLTIMO EN PIE"), yes]);
    await advance(20);
    check(log.some((x) => x.includes("Último en pie")) && /^§e(3:00|2:5\d)/.test(prey.bars.at(-1)), "forzar último en pie: 3 minutos");
    kill(prey, hunters[2]);
    await advance(20 * 8);
    check(ps.every(inLobby) && ps.every((p) => songOf(p) === SONG("lobby")), "vuelven al lobby y vuelve su música");
  },

  // ---------------------------------------------------------- the victory of the hunted
  async victoria() {
    await huntIdle();
    const ps = [await enter("Va"), await enter("Vb"), await enter("Vc")];
    await joinHunt(ps);
    const prey = ps.find(isPrey);
    const others = ps.filter((p) => p !== prey);
    const watcher = await enter("Mirón");
    await advance(20 * 10);
    for (const h of others) kill(h, prey);
    await advance(20);
    check(nearRoom(prey) && others.every(nearRoom) && others.every((p) => p.gm === "Spectator"), "los de la ronda van a la sala segura (los demás como espectadores)");
    check(!nearRoom(watcher) && inLobby(watcher), "el que está en el lobby no la ve");
    check(ps.every((p) => p.locked.has(mc.InputPermissionCategory.Movement) && p.locked.has(mc.InputPermissionCategory.Camera)), "nadie se puede mover");
    const z0 = prey.location.z;
    await advance(40);
    check(ps.every((p) => songOf(p) === SONG("win") && Math.abs(p.volumes[SONG("win")] - 0.65) < 1e-9), "suena Biast Win (volumen 65)");
    check(prey.location.z < z0 - 2, "el cazado camina hacia la habitación");
    await advance(20 * 6);
    check(ps.every((p) => p.sounds.includes("random.door_close")), "la puerta se cierra (con sonido)");
    await advance(20 * 5);
    check(prey.titles.some((t) => t.includes("VICTORIA")) && others.every((p) => p.titles.some((t) => t.includes("GANA EL CAZADO"))), "pantalla de victoria para el cazado");
    check(prey.cams.at(-1).facingLocation.y > prey.cams.at(-1).location.y + 20, "la cámara termina mirando al sol");
    await advance(20 * 3);
    check(ps.every((p) => inLobby(p) && p.locked.size === 0 && p.hud === "Reset"), "todos al lobby con el control devuelto");
  },

  // ---------------------------------------------------------- spectating
  async espectador() {
    const e = await enter("Eva"), f = await enter("Fer"), w = await enter("Wal");
    at(e, ...pad("duel"));
    at(f, pad("duel")[0] + 0.5, pad("duel")[1]);
    await advance(30);
    script = [pick("ESPECTAR"), pick(`${e.name} vs ${f.name}`)];
    world.afterEvents.itemUse.fire({ source: w, itemStack: w.inv.getItem(0) });
    await advance(10);
    check(w.gm === "Spectator" && !inLobby(w), "mira el duelo como espectador");
    const before = { ...w.location };
    w.isSneaking = true;
    await advance(10);
    w.isSneaking = false;
    await advance(5);
    check(w.location.x !== before.x || w.location.z !== before.z, "agacharse pasa al otro jugador");
    kill(f, e);
    await advance(80);
    check(inLobby(w), "vuelve al lobby al acabar");
  },

  // ---------------------------------------------------------- the admin panel
  async panel() {
    await useClock([pick("EMPAREJAMIENTO"), pick("AJUSTES"), (form) => ({ canceled: false, formValues: form.controls.map((c) => (c.label.includes("aliste") ? 8 : c.value)) })]);
    check(JSON.parse(state.dyn["natura:settings"]).duel.countdown === 8, "cambiar los segundos de aliste");
    await useClock([pick("EMPAREJAMIENTO"), pick("AJUSTES"), (form) => ({ canceled: false, formValues: form.controls.map((c) => (c.label.includes("aliste") ? 5 : c.value)) })]);
    await useClock([pick("MUNDO"), () => ({ canceled: false, formValues: [4, true, false, "Hola a todos"] })]);
    check(state.commands.includes("time set 14000") && log.some((x) => x.includes("Hola a todos")), "hora y anuncio");
    await useClock([pick("MUNDO"), () => ({ canceled: false, formValues: [2, true, false, ""] })]);
    await useClock([pick("KITS"), pick("CAZADO"), pick("RESTAURAR")]);
    check(admin.messages.some((x) => x.includes("restaurado")), "restaurar un kit");
    for (const btn of ["PARTIDAS", "CAZA", "CAMPAL", "JUGADORES", "IR A UNA ZONA", "PRUEBAS", "MÁS"]) await useClock([pick(btn), pick("Volver"), () => ({ canceled: true })]);
    check(true, "todos los submenús se abren y vuelven atrás");
    await useClock([pick("MODO LIBRE")]);
    check(admin.gm === "Creative" && admin.inv.getItem(8)?.typeId === "minecraft:clock", "modo libre con el reloj del panel");
    await useClock([pick("IR A UNA ZONA"), pick("SALA DE LA VICTORIA")]);
    check(nearRoom(admin), "ir a la sala de la victoria");
    await commands.find((x) => x.def.name === "natura:lobby").fn({ sourceEntity: admin });
    await advance(10);
    const non = await enter("Nadie");
    await commands.find((x) => x.def.name === "natura:admin").fn({ sourceEntity: non });
    await advance(3);
    check(non.messages.some((x) => x.includes("etiqueta")), "sin la etiqueta admin no se abre el panel");
  },

  // ---------------------------------------------------------- the admin tests (Pruebas)
  async pruebas() {
    await toLobby(admin);
    await useClock([pick("PRUEBAS"), pick("CINEMÁTICA DE VICTORIA")]);
    await advance(30);
    check(nearRoom(admin) && admin.locked.has(mc.InputPermissionCategory.Movement) && songOf(admin) === SONG("win"), "prueba: cinemática de victoria sobre ti");
    await advance(20 * 17);
    check(inLobby(admin) && admin.locked.size === 0 && admin.titles.some((t) => t.includes("VICTORIA")), "termina y vuelves al lobby");
    const p = await enter("Espectadora");
    await useClock([pick("PRUEBAS"), pick("VICTORIA CON ESPECTADORES")]);
    await advance(30);
    check(nearRoom(admin) && nearRoom(p) && p.gm === "Spectator", "con espectadores: también la ven los del lobby");
    await advance(20 * 18);
    check(inLobby(admin) && inLobby(p), "y todos vuelven al lobby");
    await useClock([pick("PRUEBAS"), pick("VISTA ÉPICA")]);
    await advance(10);
    check(admin.cams.at(-1)?.location.x === -58 && admin.bars.at(-1).includes("un bloque"), "prueba: vista épica");
    at(admin, admin.location.x, admin.location.z - 1.2, admin.location.y);
    await advance(12);
    await useClock([pick("PRUEBAS"), pick("CINEMÁTICA DE DUELO"), pick(gen.DUELS[2].name)]);
    await advance(20);
    check(Math.abs(admin.location.x - gen.DUELS[2].cx) < 40 && admin.locked.size > 0, `prueba: cinemática de duelo en ${gen.DUELS[2].name}`);
    await advance(20 * 18);
    check(inLobby(admin) && admin.titles.some((t) => t.includes(gen.DUELS[2].name.toUpperCase())) && admin.titles.some((t) => t.includes("§l1")), "con la cinemática y los 5 s de aliste, y vuelta al lobby");
    await useClock([pick("PRUEBAS"), pick("CINEMÁTICA DE CAZA"), pick(`${gen.HUNTS[2].name}\n§8como cazado`)]);
    await advance(40);
    check(gen.HUNTS[2].inside(Math.floor(admin.location.x), Math.floor(admin.location.z)), `prueba: cinemática de caza en ${gen.HUNTS[2].name}`);
    await advance(20 * 12);
    check(inLobby(admin) && admin.titles.some((t) => t.includes("ERES EL CAZADO")), "como cazado, y vuelta al lobby");
    for (const t of TRACKS) {
      await useClock([pick("PRUEBAS"), pick(t.name.toUpperCase())]);
      await advance(6);
      check(songOf(admin) === t.id && Math.abs(admin.volumes[t.id] - t.volume) < 1e-9, `prueba: suena ${t.name} (volumen ${Math.round(t.volume * 100)})`);
    }
    await useClock([pick("PRUEBAS"), pick("PARAR LA CANCIÓN")]);
    await advance(6);
    check(songOf(admin) === SONG("lobby"), "parar: vuelve la del lobby");
  },
};

if (args.includes("--lista")) {
  console.log("Partes:", Object.keys(PARTS).join(", "));
  process.exit(0);
}
const wanted = args.filter((a) => !a.startsWith("--"));
const unknown = wanted.filter((w) => !(w in PARTS));
if (unknown.length) {
  console.log(`No existe: ${unknown.join(", ")}. Partes: ${Object.keys(PARTS).join(", ")}`);
  process.exit(2);
}
for (const [name, fn] of Object.entries(PARTS)) {
  if (wanted.length && !wanted.includes(name)) continue;
  console.log(name[0].toUpperCase() + name.slice(1));
  await fn();
}
check(warnings.length === 0, `sin avisos (${warnings.slice(0, 5).join(" / ")})`);
console.log(failures ? `\n${failures} fallo(s)` : "\nTodo bien");
process.exit(failures ? 1 : 0);
