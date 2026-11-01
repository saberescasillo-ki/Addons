// Time an Thing: time of day (presets and custom) and weather.
import { WeatherType, world } from "@minecraft/server";
import { menu, modal, num, run, tell } from "./common.js";

// Minecraft ticks: 0 = 06:00, 6000 = 12:00, 18000 = 00:00.
const PRESETS = [
  ["Amanecer", 23000],
  ["Día", 1000],
  ["Mediodía", 6000],
  ["Atardecer", 12000],
  ["Noche", 13000],
  ["Medianoche", 18000],
];

function clock(ticks) {
  const total = (((ticks + 6000) % 24000) + 24000) % 24000;
  const h = Math.floor(total / 1000);
  const m = Math.floor(((total % 1000) * 60) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** "HH:MM" (clock) or a plain number (ticks). */
function parseTime(text) {
  const t = String(text).trim();
  const m = t.match(/^(\d{1,2})[:.h](\d{1,2})?$/);
  if (m) {
    const h = Math.min(23, Number(m[1]));
    const min = Math.min(59, Number(m[2] ?? 0));
    return Math.round((h * 1000 + (min * 1000) / 60 - 6000 + 24000) % 24000);
  }
  const n = num(t, NaN, 0, 23999);
  return Number.isFinite(n) ? Math.round(n) : undefined;
}

function rules() {
  try {
    return world.gameRules;
  } catch {
    return undefined;
  }
}

function setRule(name, cmdName, value) {
  try {
    world.gameRules[name] = value;
  } catch {
    run(world.getDimension("overworld"), `gamerule ${cmdName} ${value}`);
  }
}

function setTime(player, ticks) {
  world.setTimeOfDay(ticks);
  tell(player, `§aHora: ${clock(ticks)}`);
}

export async function timeMenu(player) {
  const cycle = rules()?.doDayLightCycle !== false;
  const entries = PRESETS.map(([name, ticks]) => [`${name}\n§8${clock(ticks)}`, () => setTime(player, ticks)]);
  entries.push(
    [
      "Hora personalizada...",
      async () => {
        const v = await modal(player, "§5Hora personalizada", [
          { type: "text", label: "Hora (HH:MM, por ejemplo 21:30) o ticks (0-23999)", value: clock(world.getTimeOfDay()) },
          { type: "toggle", label: "Detener el ciclo día/noche (la hora se queda fija)", value: !cycle },
        ]);
        if (!v) return;
        const ticks = parseTime(v[0]);
        if (ticks === undefined) return tell(player, "§cHora no válida");
        setTime(player, ticks);
        setRule("doDayLightCycle", "dodaylightcycle", v[1] !== true);
      },
    ],
    [
      `Ciclo día/noche: ${cycle ? "§aactivado" : "§cdetenido"}`,
      () => {
        setRule("doDayLightCycle", "dodaylightcycle", !cycle);
        tell(player, cycle ? "§eEl ciclo día/noche está detenido" : "§aEl ciclo día/noche está activado");
      },
    ],
    ["Clima...", () => weatherMenu(player)]
  );
  await menu(player, "§5Time an Thing", `§7Hora actual: §f${clock(world.getTimeOfDay())}`, entries);
}

const WEATHERS = [
  ["Despejado", WeatherType.Clear],
  ["Lluvia", WeatherType.Rain],
  ["Tormenta", WeatherType.Thunder],
];
const DURATIONS = [
  ["Aleatoria", 0],
  ["5 minutos", 5],
  ["20 minutos (un día de Minecraft)", 20],
  ["1 hora", 60],
  ["Personalizada (minutos de abajo)", -1],
];

async function weatherMenu(player) {
  const weatherCycle = rules()?.doWeatherCycle !== false;
  await menu(
    player,
    "§5Clima",
    "",
    WEATHERS.map(([name, type]) => [
      name,
      async () => {
        const v = await modal(player, `§5Clima: ${name}`, [
          { type: "dropdown", label: "Duración", options: DURATIONS.map((d) => d[0]), value: 0 },
          { type: "text", label: "Minutos (personalizada)", value: 10 },
          { type: "toggle", label: "Fijar este clima (detener el ciclo del clima)", value: !weatherCycle },
        ]);
        if (!v) return;
        let minutes = DURATIONS[v[0]][1];
        if (minutes < 0) minutes = num(v[1], 10, 0.05, 100000);
        const dim = world.getDimension("overworld");
        if (minutes > 0) dim.setWeather(type, Math.round(minutes * 60 * 20));
        else dim.setWeather(type);
        setRule("doWeatherCycle", "doweathercycle", v[2] !== true);
        tell(player, `§aClima: ${name}`);
      },
    ])
  );
}
