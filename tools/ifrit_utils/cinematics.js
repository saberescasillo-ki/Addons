// Cinematics: storage, playback and the Cinematic Creator editor.
//
// A cinematic is a list of camera points. Each point has:
//   x, y, z, pitch, yaw, dim  -> where the camera is and where it looks (saved from the player)
//   dur    -> seconds the camera takes to move from the previous point to this one
//   espera -> seconds it stays still on this point before the next movement
//   ease   -> how it moves (EASES)
//   fade   -> true: instead of moving, a camera fade hides a cut to this point
import { system, world } from "@minecraft/server";
import { ITEMS } from "./config.js";
import {
  COLORS,
  fmt,
  giveItem,
  menu,
  modal,
  names,
  num,
  online,
  pickTargets,
  removeItem,
  run,
  say,
  settingsButton,
  tell,
} from "./common.js";

export const EASES = [
  ["InOutSine", "Suave (empieza y acaba despacio)"],
  ["Linear", "Lineal (velocidad constante)"],
  ["InSine", "Acelera"],
  ["OutSine", "Frena"],
  ["InOutCubic", "Muy suave"],
  ["InOutExpo", "Rápido en medio"],
  ["OutBack", "Se pasa un poco y vuelve"],
  ["OutBounce", "Rebote"],
  ["Spring", "Muelle"],
];
const EYE = 1.62;
const INDEX = "ifrit:cines";
const DRAFT = "ifrit:borrador";
const cineKey = (id) => `ifrit:cine:${id}`;

// ------------------------------------------------------------ storage
function readJson(holder, key, def) {
  try {
    const v = holder.getDynamicProperty(key);
    return v === undefined ? def : JSON.parse(String(v));
  } catch {
    return def;
  }
}

export function listCines() {
  return readJson(world, INDEX, [])
    .map((id) => readJson(world, cineKey(id), null))
    .filter((c) => c && Array.isArray(c.puntos));
}

function saveCine(cine) {
  const ids = readJson(world, INDEX, []);
  if (!ids.includes(cine.id)) ids.push(cine.id);
  world.setDynamicProperty(cineKey(cine.id), JSON.stringify(cine));
  world.setDynamicProperty(INDEX, JSON.stringify(ids));
}

function deleteCine(id) {
  world.setDynamicProperty(cineKey(id), undefined);
  world.setDynamicProperty(INDEX, JSON.stringify(readJson(world, INDEX, []).filter((x) => x !== id)));
}

function newDraft() {
  return {
    id: null,
    nombre: `Cinemática ${listCines().length + 1}`,
    puntos: [],
    ajustes: {
      dur: 3, // defaults for new points
      espera: 0,
      ease: "InOutSine",
      fade: false,
      fadeIn: 0.5, // camera fade times (seconds) and colour
      fadeHold: 0.2,
      fadeOut: 0.5,
      color: [0, 0, 0],
      fadeInicio: true,
      fadeFinal: true,
      ocultarHud: true,
    },
  };
}

export function getDraft(player) {
  return readJson(player, DRAFT, null);
}

function setDraft(player, draft) {
  player.setDynamicProperty(DRAFT, draft ? JSON.stringify(draft) : undefined);
}

function totalTime(cine) {
  const a = cine.ajustes;
  let t = a.fadeInicio ? a.fadeIn : 0;
  cine.puntos.forEach((p, i) => {
    if (i > 0) t += p.fade ? a.fadeIn + a.fadeHold : p.dur;
    t += p.espera;
  });
  return t + (a.fadeFinal ? a.fadeIn : 0);
}

// ------------------------------------------------------------ playback
let nextRun = 1;
const runs = new Map(); // id -> { owner, ids, hud, timers }

export function playCine(owner, cine, targets) {
  if (!cine.puntos.length) return tell(owner, "§cLa cinemática no tiene puntos");
  const a = cine.ajustes;
  const id = nextRun++;
  const r = { owner: owner.id, ids: targets.map((p) => p.id), hud: a.ocultarHud, timers: [] };
  runs.set(id, r);
  const each = (fn) => {
    for (const pid of r.ids) {
      const p = online(pid);
      if (p) {
        try {
          fn(p);
        } catch {}
      }
    }
  };
  // Every camera change at least 1 tick after the previous one, so an eased move starts from the last point.
  let lastTick = -1;
  const at = (sec, fn) => {
    const tick = Math.max(lastTick + 1, Math.round(sec * 20));
    lastTick = tick;
    r.timers.push(system.runTimeout(fn, tick));
  };
  const color = { red: a.color[0] / 255, green: a.color[1] / 255, blue: a.color[2] / 255 };
  const fade = () =>
    each((p) =>
      p.camera.fade({
        fadeTime: { fadeInTime: a.fadeIn, holdTime: a.fadeHold, fadeOutTime: a.fadeOut },
        fadeColor: color,
      })
    );
  const place = (pt, ease) =>
    each((p) =>
      p.camera.setCamera("minecraft:free", {
        location: { x: pt.x, y: pt.y, z: pt.z },
        rotation: { x: pt.pitch, y: pt.yaw },
        ...(ease ? { easeOptions: { easeTime: ease.time, easeType: ease.type } } : {}),
      })
    );

  if (a.ocultarHud) each((p) => run(p, "hud @s hide"));
  let t = 0;
  if (a.fadeInicio) {
    fade();
    t = a.fadeIn;
  }
  const first = cine.puntos[0];
  at(t, () => place(first));
  t += first.espera;
  for (const pt of cine.puntos.slice(1)) {
    if (pt.fade) {
      at(t, fade);
      t += a.fadeIn;
      at(t, () => place(pt));
      t += a.fadeHold;
    } else {
      const time = Math.max(0.05, pt.dur);
      at(t, () => place(pt, { time, type: pt.ease }));
      t += time;
    }
    t += pt.espera;
  }
  if (a.fadeFinal) {
    at(t, fade);
    t += a.fadeIn;
  }
  at(t, () => endRun(id));
  tell(owner, `§aCinemática "${cine.nombre}" para ${names(targets)}`);
}

function endRun(id) {
  const r = runs.get(id);
  if (!r) return;
  runs.delete(id);
  for (const t of r.timers) system.clearRun(t);
  for (const pid of r.ids) {
    const p = online(pid);
    if (!p) continue;
    try {
      p.camera.clear();
    } catch {}
    if (r.hud) run(p, "hud @s reset");
  }
}

export function stopRuns(owner) {
  let n = 0;
  for (const [id, r] of [...runs]) {
    if (r.owner === owner.id || r.ids.includes(owner.id)) {
      endRun(id);
      n++;
    }
  }
  tell(owner, n ? "§aCinemáticas detenidas" : "§7No hay cinemáticas en curso");
}

// ------------------------------------------------------------ "Free" menu of the Camera item
export async function freeMenu(player) {
  const draft = getDraft(player);
  const cines = listCines();
  await menu(player, "§5Camera: Free", "Crea cinemáticas con el Cinematic Creator y ejecútalas aquí.", [
    [draft ? `Crear animación\n§8Seguir con "${draft.nombre}"` : "Crear animación", () => startCreating(player)],
    [`Ejecutar animación\n§8${cines.length} guardadas`, () => cinesMenu(player)],
    ["§cDetener cinemáticas en curso", () => stopRuns(player)],
  ]);
}

function startCreating(player, draft) {
  if (draft) setDraft(player, draft);
  else if (!getDraft(player)) setDraft(player, newDraft());
  giveItem(player, ITEMS.creador);
  say(
    player,
    "§d[Cinematic Creator] §fUsa el objeto para abrir el editor. §7Agáchate y úsalo para guardar tu posición como un punto."
  );
}

async function cinesMenu(player) {
  const cines = listCines();
  if (!cines.length) return tell(player, "§7Aún no hay cinemáticas. Créalas con «Crear animación».");
  await menu(
    player,
    "§5Cinemáticas",
    "",
    cines.map((c) => [
      `${c.nombre}\n§8${c.puntos.length} puntos, ${fmt(totalTime(c))} s`,
      () => cineMenu(player, c),
    ])
  );
}

async function cineMenu(player, cine) {
  await menu(player, `§5${cine.nombre}`, `${cine.puntos.length} puntos, ${fmt(totalTime(cine))} s`, [
    [
      "§aEjecutar",
      async () => {
        const targets = await pickTargets(player, "¿Quién verá la cinemática?");
        if (targets) playCine(player, cine, targets);
      },
    ],
    [
      "Editar",
      async () => {
        const d = getDraft(player);
        if (d && d.puntos.length && d.id !== cine.id) {
          let ok = false;
          await menu(player, "§5¿Seguro?", `Tienes un borrador sin exportar ("${d.nombre}"). Se perderá.`, [
            ["§cSí, editar esta", () => (ok = true)],
            ["Cancelar", () => {}],
          ]);
          if (!ok) return;
        }
        startCreating(player, JSON.parse(JSON.stringify(cine)));
      },
    ],
    [
      "Borrar puntos...\n§8Sin pasar por el editor",
      async () => {
        const kept = await deletePoints(player, cine.puntos);
        if (!kept) return;
        if (!kept.length) return tell(player, "§cUna cinemática necesita al menos un punto: usa «Borrar cinemática»");
        cine.puntos = kept;
        saveCine(cine);
        await cineMenu(player, cine);
      },
    ],
    [
      "§cBorrar cinemática",
      async () => {
        await menu(player, "§5¿Borrar?", `Se borrará "${cine.nombre}" para siempre.`, [
          ["§cSí, borrar", () => deleteCine(cine.id)],
          ["Cancelar", () => {}],
        ]);
      },
    ],
  ]);
}

// ------------------------------------------------------------ Cinematic Creator
export function addPoint(player) {
  const draft = getDraft(player) ?? newDraft();
  const a = draft.ajustes;
  const head = player.getHeadLocation();
  const rot = player.getRotation();
  draft.puntos.push({
    x: Math.round(head.x * 100) / 100,
    y: Math.round(head.y * 100) / 100,
    z: Math.round(head.z * 100) / 100,
    pitch: Math.round(rot.x * 10) / 10,
    yaw: Math.round(rot.y * 10) / 10,
    dim: player.dimension.id,
    dur: a.dur,
    espera: a.espera,
    ease: a.ease,
    fade: a.fade,
  });
  setDraft(player, draft);
  tell(player, `§aPunto ${draft.puntos.length} guardado`);
}

export async function creatorMenu(player) {
  const draft = getDraft(player) ?? newDraft();
  setDraft(player, draft);
  const body =
    `§7Puntos: §f${draft.puntos.length}   §7Duración: §f${fmt(totalTime(draft))} s` +
    "\n§7Agáchate y usa el objeto para guardar un punto sin abrir el menú.";
  await menu(player, `§5${draft.nombre}`, body, [
    ["§aGuardar posición actual\n§8Tu posición y hacia dónde miras", () => addPoint(player)],
    [`Puntos (${draft.puntos.length})\n§8Editar, mover o borrar uno`, () => pointsMenu(player)],
    ...(draft.puntos.length
      ? [
          [
            `§cBorrar último punto\n§8Punto ${draft.puntos.length}`,
            async () => {
              draft.puntos.pop();
              setDraft(player, draft);
              tell(player, `§ePunto ${draft.puntos.length + 1} borrado`);
              await creatorMenu(player);
            },
          ],
          [
            "§cBorrar puntos...\n§8Marca los que quieres borrar",
            async () => {
              const kept = await deletePoints(player, draft.puntos);
              if (kept) {
                draft.puntos = kept;
                setDraft(player, draft);
              }
              await creatorMenu(player);
            },
          ],
        ]
      : []),
    [
      "Ajustes de la cinemática",
      async () => {
        await settingsMenu(player);
        await creatorMenu(player);
      },
    ],
    ["Previsualizar\n§8Solo para ti", () => playCine(player, draft, [player])],
    ["§aExportar\n§8Aparece en Camera > Free", () => exportDraft(player)],
    ["§cDescartar borrador", () => discardDraft(player)],
    settingsButton(player),
  ]);
}

/** Form with a checkbox per point. Returns the points that are kept, or undefined if cancelled. */
async function deletePoints(player, puntos) {
  const v = await modal(
    player,
    "§5Borrar puntos",
    [
      { type: "toggle", label: "§cBorrar TODOS los puntos" },
      ...puntos.map((p, i) => ({
        type: "toggle",
        label: `Punto ${i + 1} §7(${Math.round(p.x)} ${Math.round(p.y)} ${Math.round(p.z)}, ${p.fade ? "fade" : fmt(p.dur) + " s"})`,
      })),
    ],
    "Borrar"
  );
  if (!v) return undefined;
  const kept = v[0] === true ? [] : puntos.filter((p, i) => v[i + 1] !== true);
  const gone = puntos.length - kept.length;
  tell(player, gone ? `§e${gone} punto${gone > 1 ? "s" : ""} borrado${gone > 1 ? "s" : ""}` : "§7No se borró nada");
  return kept;
}

async function pointsMenu(player) {
  const draft = getDraft(player);
  if (!draft?.puntos.length) return tell(player, "§7No hay puntos todavía");
  await menu(
    player,
    "§5Puntos",
    "§7Toca un punto para editarlo, moverlo o borrarlo.",
    draft.puntos.map((p, i) => [
      `Punto ${i + 1}\n§8${p.fade ? "fade" : fmt(p.dur) + " s"} · espera ${fmt(p.espera)} s · ${Math.round(p.x)} ${Math.round(p.y)} ${Math.round(p.z)}`,
      async () => {
        if (await pointMenu(player, i)) await pointsMenu(player);
      },
    ])
  );
}

async function pointMenu(player, i) {
  const draft = getDraft(player);
  const p = draft.puntos[i];
  if (!p) return false;
  let back = false;
  const save = () => {
    setDraft(player, draft);
    back = true;
  };
  await menu(player, `§5Punto ${i + 1}`, i === 0 ? "§7El primer punto es donde empieza la cámara." : "", [
    [
      "Editar tiempos y movimiento",
      async () => {
        const easeIndex = Math.max(0, EASES.findIndex(([id]) => id === p.ease));
        const v = await modal(player, `§5Punto ${i + 1}`, [
          { type: "text", label: "Duración del movimiento hasta este punto (segundos)", value: p.dur },
          { type: "text", label: "Espera en este punto antes del siguiente (segundos)", value: p.espera },
          { type: "dropdown", label: "Tipo de movimiento", options: EASES.map((e) => e[1]), value: easeIndex },
          { type: "toggle", label: "Camera fade: llegar con un fundido (corte) en vez de moverse", value: p.fade },
        ]);
        if (!v) return;
        p.dur = num(v[0], p.dur, 0, 600);
        p.espera = num(v[1], p.espera, 0, 600);
        p.ease = EASES[v[2]][0];
        p.fade = v[3] === true;
        save();
      },
    ],
    [
      "Mover el punto a mi posición",
      () => {
        const head = player.getHeadLocation();
        const rot = player.getRotation();
        Object.assign(p, { x: head.x, y: head.y, z: head.z, pitch: rot.x, yaw: rot.y, dim: player.dimension.id });
        save();
        tell(player, `§aPunto ${i + 1} movido`);
      },
    ],
    [
      "Ir a este punto",
      () => {
        try {
          player.teleport(
            { x: p.x, y: p.y - EYE, z: p.z },
            { dimension: world.getDimension(p.dim ?? "overworld"), rotation: { x: p.pitch, y: p.yaw } }
          );
        } catch {}
      },
    ],
    [
      "Ver desde aquí\n§8La cámara salta 2 s a este punto",
      () => {
        try {
          player.camera.setCamera("minecraft:free", {
            location: { x: p.x, y: p.y, z: p.z },
            rotation: { x: p.pitch, y: p.yaw },
          });
          system.runTimeout(() => player.camera.clear(), 40);
        } catch {}
      },
    ],
    [
      "Subir (antes)",
      () => {
        if (i > 0) [draft.puntos[i - 1], draft.puntos[i]] = [draft.puntos[i], draft.puntos[i - 1]];
        save();
      },
    ],
    [
      "Bajar (después)",
      () => {
        if (i < draft.puntos.length - 1) [draft.puntos[i + 1], draft.puntos[i]] = [draft.puntos[i], draft.puntos[i + 1]];
        save();
      },
    ],
    [
      "§cBorrar punto",
      () => {
        draft.puntos.splice(i, 1);
        save();
      },
    ],
  ]);
  return back;
}

async function settingsMenu(player) {
  const draft = getDraft(player);
  const a = draft.ajustes;
  const easeIndex = Math.max(0, EASES.findIndex(([id]) => id === a.ease));
  const colorIndex = COLORS.findIndex(([, c]) => c && c.join() === a.color.join());
  const v = await modal(player, "§5Ajustes de la cinemática", [
    { type: "text", label: "Nombre", value: draft.nombre },
    { type: "text", label: "Duración de cada movimiento (s) §7- para los puntos nuevos", value: a.dur },
    { type: "text", label: "Tiempo entre movimientos / espera (s) §7- para los puntos nuevos", value: a.espera },
    { type: "dropdown", label: "Tipo de movimiento §7- para los puntos nuevos", options: EASES.map((e) => e[1]), value: easeIndex },
    { type: "toggle", label: "Camera fade entre movimientos §7- para los puntos nuevos", value: a.fade },
    { type: "toggle", label: "§eAplicar estos 4 valores a TODOS los puntos ya guardados", value: false },
    { type: "text", label: "Fade: tiempo de entrada (s)", value: a.fadeIn },
    { type: "text", label: "Fade: tiempo de pantalla completa (s)", value: a.fadeHold },
    { type: "text", label: "Fade: tiempo de salida (s)", value: a.fadeOut },
    { type: "dropdown", label: "Fade: color", options: COLORS.map((c) => c[0]), value: colorIndex < 0 ? COLORS.length - 1 : colorIndex },
    { type: "slider", label: "Rojo (personalizado)", min: 0, max: 255, value: a.color[0] },
    { type: "slider", label: "Verde (personalizado)", min: 0, max: 255, value: a.color[1] },
    { type: "slider", label: "Azul (personalizado)", min: 0, max: 255, value: a.color[2] },
    { type: "toggle", label: "Fade al empezar", value: a.fadeInicio },
    { type: "toggle", label: "Fade al terminar", value: a.fadeFinal },
    { type: "toggle", label: "Ocultar el HUD durante la cinemática", value: a.ocultarHud },
  ]);
  if (!v) return;
  draft.nombre = String(v[0]).trim().slice(0, 40) || draft.nombre;
  a.dur = num(v[1], a.dur, 0, 600);
  a.espera = num(v[2], a.espera, 0, 600);
  a.ease = EASES[v[3]][0];
  a.fade = v[4] === true;
  if (v[5] === true) for (const p of draft.puntos) Object.assign(p, { dur: a.dur, espera: a.espera, ease: a.ease, fade: a.fade });
  a.fadeIn = num(v[6], a.fadeIn, 0, 10);
  a.fadeHold = num(v[7], a.fadeHold, 0, 10);
  a.fadeOut = num(v[8], a.fadeOut, 0, 10);
  a.color = COLORS[v[9]][1] ?? [Math.round(v[10]), Math.round(v[11]), Math.round(v[12])];
  a.fadeInicio = v[13] === true;
  a.fadeFinal = v[14] === true;
  a.ocultarHud = v[15] === true;
  setDraft(player, draft);
  tell(player, "§aAjustes guardados");
}

function exportDraft(player) {
  const draft = getDraft(player);
  if (!draft?.puntos.length) return tell(player, "§cGuarda al menos un punto antes de exportar");
  draft.id = draft.id ?? Date.now().toString(36);
  saveCine(draft);
  setDraft(player, null);
  removeItem(player, ITEMS.creador);
  say(player, `§d[Cinematic Creator] §a"${draft.nombre}" exportada. §7Está en Camera > Free > Ejecutar animación.`);
}

async function discardDraft(player) {
  await menu(player, "§5¿Descartar?", "Se borrará el borrador (las cinemáticas exportadas no se tocan).", [
    [
      "§cSí, descartar",
      () => {
        setDraft(player, null);
        removeItem(player, ITEMS.creador);
      },
    ],
    ["Cancelar", () => {}],
  ]);
}
