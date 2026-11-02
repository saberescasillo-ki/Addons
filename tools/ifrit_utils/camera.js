// Camera item: fade, free (cinematics) and shake.
import { COLORS, menu, modal, names, num, pickTargets, run, settingsButton, tell } from "./common.js";
import { freeMenu } from "./cinematics.js";

const FADE = "ifrit:fade";
const SHAKE = "ifrit:shake";

function saved(player, key, def) {
  try {
    return { ...def, ...JSON.parse(String(player.getDynamicProperty(key) ?? "{}")) };
  } catch {
    return def;
  }
}

export async function cameraMenu(player) {
  await menu(player, "§5Camera", "Efectos de cámara.", [
    ["Fade\n§8Fundido a un color", () => fadeMenu(player)],
    ["Free\n§8Cinemáticas", () => freeMenu(player)],
    ["Shake\n§8Temblor de cámara", () => shakeMenu(player)],
    settingsButton(player),
  ]);
}

// /camera <players> fade time <in> <hold> <out> color <r> <g> <b>
async function fadeMenu(player) {
  const s = saved(player, FADE, { fadeIn: 1, hold: 0.5, fadeOut: 1, color: 0, rgb: [0, 0, 0] });
  const v = await modal(player, "§5Camera: Fade", [
    { type: "text", label: "Tiempo de entrada (segundos, 0-10)", value: s.fadeIn },
    { type: "text", label: "Tiempo en pantalla completa (segundos, 0-10)", value: s.hold },
    { type: "text", label: "Tiempo de salida (segundos, 0-10)", value: s.fadeOut },
    { type: "dropdown", label: "Color", options: COLORS.map((c) => c[0]), value: s.color },
    { type: "slider", label: "Rojo (personalizado)", min: 0, max: 255, value: s.rgb[0] },
    { type: "slider", label: "Verde (personalizado)", min: 0, max: 255, value: s.rgb[1] },
    { type: "slider", label: "Azul (personalizado)", min: 0, max: 255, value: s.rgb[2] },
  ]);
  if (!v) return;
  const fadeIn = num(v[0], 1, 0, 10);
  const hold = num(v[1], 0.5, 0, 10);
  const fadeOut = num(v[2], 1, 0, 10);
  const rgb = [v[4], v[5], v[6]].map((x) => Math.round(x));
  const color = COLORS[v[3]][1] ?? rgb;
  player.setDynamicProperty(FADE, JSON.stringify({ fadeIn, hold, fadeOut, color: v[3], rgb }));
  const targets = await pickTargets(player, "¿Para quién es el fade?");
  if (!targets) return;
  for (const p of targets) {
    try {
      p.camera.fade({
        fadeTime: { fadeInTime: fadeIn, holdTime: hold, fadeOutTime: fadeOut },
        fadeColor: { red: color[0] / 255, green: color[1] / 255, blue: color[2] / 255 },
      });
    } catch {
      run(p, `camera @s fade time ${fadeIn} ${hold} ${fadeOut} color ${color.join(" ")}`);
    }
  }
  tell(player, `§aFade para ${names(targets)}`);
}

// /camerashake add <players> <intensity> <seconds> <positional|rotational> and /camerashake stop
async function shakeMenu(player) {
  await menu(player, "§5Camera: Shake", "", [
    [
      "Añadir temblor",
      async () => {
        const s = saved(player, SHAKE, { intensity: 0.5, seconds: 2, type: 0 });
        const v = await modal(player, "§5Camera: Shake", [
          { type: "text", label: "Intensidad (0 - 4)", value: s.intensity },
          { type: "text", label: "Duración (segundos)", value: s.seconds },
          { type: "dropdown", label: "Tipo", options: ["Posicional (se mueve)", "Rotacional (gira)"], value: s.type },
        ]);
        if (!v) return;
        const intensity = num(v[0], 0.5, 0, 4);
        const seconds = num(v[1], 2, 0.05, 3600);
        const type = v[2] === 1 ? "rotational" : "positional";
        player.setDynamicProperty(SHAKE, JSON.stringify({ intensity, seconds, type: v[2] }));
        const targets = await pickTargets(player, "¿A quién le tiembla la cámara?");
        if (!targets) return;
        for (const p of targets) run(p, `camerashake add @s ${intensity} ${seconds} ${type}`);
        tell(player, `§aShake para ${names(targets)}`);
      },
    ],
    [
      "§cDetener temblor",
      async () => {
        const targets = await pickTargets(player, "¿A quién se lo quitas?");
        if (!targets) return;
        for (const p of targets) run(p, "camerashake stop @s");
        tell(player, `§aShake detenido para ${names(targets)}`);
      },
    ],
  ]);
}
