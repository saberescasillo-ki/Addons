// Effects: gives effects to the chosen players, ordered in sections.
import { menu, modal, names, num, pickTargets, run, tell } from "./common.js";

const POSITIVE = [
  ["speed", "Velocidad"],
  ["haste", "Prisa minera"],
  ["strength", "Fuerza"],
  ["instant_health", "Curación instantánea"],
  ["jump_boost", "Salto"],
  ["regeneration", "Regeneración"],
  ["resistance", "Resistencia"],
  ["fire_resistance", "Resistencia al fuego"],
  ["water_breathing", "Respiración acuática"],
  ["invisibility", "Invisibilidad"],
  ["night_vision", "Visión nocturna"],
  ["health_boost", "Vida extra"],
  ["absorption", "Absorción"],
  ["saturation", "Saturación"],
  ["slow_falling", "Caída lenta"],
  ["conduit_power", "Poder del conducto"],
  ["village_hero", "Héroe de la aldea"],
];
const NEGATIVE = [
  ["slowness", "Lentitud"],
  ["mining_fatigue", "Fatiga minera"],
  ["instant_damage", "Daño instantáneo"],
  ["nausea", "Náuseas"],
  ["blindness", "Ceguera"],
  ["darkness", "Oscuridad"],
  ["hunger", "Hambre"],
  ["weakness", "Debilidad"],
  ["poison", "Veneno"],
  ["fatal_poison", "Veneno mortal"],
  ["wither", "Wither"],
  ["levitation", "Levitación"],
  ["bad_omen", "Mal presagio"],
  ["wind_charged", "Carga de viento"],
  ["weaving", "Tejedor"],
  ["oozing", "Supurante"],
  ["infested", "Infestado"],
];
const DURATIONS = [
  ["1 minuto", 60],
  ["10 minutos", 600],
  ["1 hora", 3600],
  ["Infinito", "infinite"],
  ["Personalizado (segundos de abajo)", null],
];
const LAST = "ifrit:efecto";

function last(player) {
  try {
    return { dur: 0, custom: 30, level: 1, hide: false, ...JSON.parse(String(player.getDynamicProperty(LAST) ?? "{}")) };
  } catch {
    return { dur: 0, custom: 30, level: 1, hide: false };
  }
}

export async function effectsMenu(player) {
  await menu(player, "§5Effects", "Da efectos a los jugadores que elijas.", [
    ["§aPositivos", () => listMenu(player, "Positivos", POSITIVE)],
    ["§cNegativos", () => listMenu(player, "Negativos", NEGATIVE)],
    [
      "Quitar todos los efectos",
      async () => {
        const targets = await pickTargets(player, "¿A quién le quitas los efectos?");
        if (!targets) return;
        for (const p of targets) run(p, "effect @s clear");
        tell(player, `§aEfectos quitados a ${names(targets)}`);
      },
    ],
  ]);
}

async function listMenu(player, title, list) {
  await menu(
    player,
    `§5Effects: ${title}`,
    "",
    list.map(([id, name]) => [name, () => effectForm(player, id, name)])
  );
}

async function effectForm(player, id, name) {
  const s = last(player);
  const v = await modal(player, `§5${name}`, [
    { type: "dropdown", label: "Duración", options: DURATIONS.map((d) => d[0]), value: s.dur },
    { type: "text", label: "Segundos (personalizado)", value: s.custom },
    { type: "slider", label: "Nivel del efecto", min: 1, max: 10, value: Math.min(10, s.level) },
    { type: "text", label: "Nivel personalizado §7(1-255, opcional: sustituye al de arriba)", value: "" },
    { type: "toggle", label: "Ocultar partículas", value: s.hide },
  ]);
  if (!v) return;
  const custom = Math.round(num(v[1], 30, 1, 1000000));
  const duration = DURATIONS[v[0]][1] ?? custom;
  const level = String(v[3]).trim() ? Math.round(num(v[3], v[2], 1, 255)) : Math.round(v[2]);
  const hide = v[4] === true;
  player.setDynamicProperty(LAST, JSON.stringify({ dur: v[0], custom, level, hide }));
  const targets = await pickTargets(player, `¿Quién recibe ${name}?`);
  if (!targets) return;
  let ok = 0;
  for (const p of targets) if (run(p, `effect @s ${id} ${duration} ${level - 1} ${hide}`)) ok++;
  if (ok) tell(player, `§a${name} ${level} para ${names(targets)}`);
  else tell(player, `§cNo se pudo dar ${name} (¿tu versión de Minecraft lo tiene?)`);
}
