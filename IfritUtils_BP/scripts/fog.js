// Utilidad de Niebla: colours the fog and the sky with one of the presets, density 1-15.
//
// The fog is a /fog preset (one per colour and density). Bedrock's sky is not covered by the
// fog, so each player with fog also gets a "sky dome" (ifrit:cielo): a huge box centred on
// their camera, just past the end of the fog. The fog paints it in the fog colour, so the
// whole sky takes that colour. Only its owner sees it.
import { system, world } from "@minecraft/server";
import { CIELO, NIEBLAS, NIEBLA_DENSIDAD_MAX, NIEBLA_FIN } from "./config.js";
import { menu, modal, names, pickTargets, run, tell, valid } from "./common.js";

const TAG = "ifrit_niebla";
const LAST = "ifrit:niebla_densidad";
const STATE = "ifrit:niebla_estado"; // on the player: {"color": index in NIEBLAS, "densidad": 1-15}
const OWNER = "ifrit:dueno"; // on the dome: id of its player
const DIMENSIONS = ["overworld", "nether", "the_end"];

const domes = new Map(); // player id -> dome entity

function getState(p) {
  try {
    const s = JSON.parse(String(p.getDynamicProperty(STATE) ?? ""));
    return NIEBLAS[s.color] && s.densidad >= 1 ? s : undefined;
  } catch {
    return undefined;
  }
}

function setFog(p, color, density) {
  run(p, `fog @s remove ${TAG}`);
  if (color === undefined) {
    p.setDynamicProperty(STATE, undefined);
    removeDome(p.id);
    return;
  }
  run(p, `fog @s push ifrit:niebla_${NIEBLAS[color].id}_${density} ${TAG}`);
  p.setDynamicProperty(STATE, JSON.stringify({ color, densidad: density }));
}

function removeDome(playerId) {
  const e = domes.get(playerId);
  domes.delete(playerId);
  try {
    if (e && valid(e)) e.remove();
  } catch {}
}

// Every tick: keep each dome on its player's camera.
system.runInterval(() => {
  for (const p of world.getAllPlayers()) {
    const s = getState(p);
    // Under water the water fog is used, so the dome would show: hide it there.
    if (!s || p.isInWater) {
      if (domes.has(p.id)) removeDome(p.id);
      continue;
    }
    let dome = domes.get(p.id);
    if (dome && (!valid(dome) || dome.dimension.id !== p.dimension.id)) {
      removeDome(p.id);
      dome = undefined;
    }
    const head = p.getHeadLocation();
    try {
      if (!dome) {
        dome = p.dimension.spawnEntity(CIELO, head);
        dome.setDynamicProperty(OWNER, p.id);
        domes.set(p.id, dome);
      }
      const radius = Math.round((NIEBLA_FIN[s.densidad - 1] * 1.05 + 0.6) * 100) / 100;
      if (Math.abs((dome.getProperty("ifrit:radio") ?? 0) - radius) > 0.01) dome.setProperty("ifrit:radio", radius);
      if (dome.getProperty("ifrit:color") !== s.color) dome.setProperty("ifrit:color", s.color);
      dome.teleport(head);
    } catch {}
  }
}, 1);

// Every 2 s: remove domes left behind (player gone, world reloaded...).
system.runInterval(() => {
  for (const id of DIMENSIONS) {
    let list = [];
    try {
      list = world.getDimension(id).getEntities({ type: CIELO });
    } catch {}
    for (const e of list) {
      const owner = e.getDynamicProperty(OWNER);
      if (domes.get(owner)?.id !== e.id) {
        try {
          e.remove();
        } catch {}
      }
    }
  }
}, 40);

world.afterEvents.playerLeave.subscribe(({ playerId }) => removeDome(playerId));

export async function fogMenu(player) {
  const entries = NIEBLAS.map((n, color) => [
    `${n.boton}${n.nombre}`,
    async () => {
      const values = await modal(player, `§5Niebla: ${n.nombre}`, [
        {
          type: "slider",
          label: "Densidad (1 = poca, 15 = muy densa)",
          min: 1,
          max: NIEBLA_DENSIDAD_MAX,
          value: Number(player.getDynamicProperty(LAST) ?? 8),
        },
      ]);
      if (!values) return;
      const density = Math.round(values[0]);
      player.setDynamicProperty(LAST, density);
      const targets = await pickTargets(player, "¿Quién verá la niebla?");
      if (!targets) return;
      for (const p of targets) setFog(p, color, density);
      tell(player, `§aNiebla ${n.nombre} (densidad ${density}) para ${names(targets)}`);
    },
  ]);
  entries.push([
    "§cQuitar niebla",
    async () => {
      const targets = await pickTargets(player, "¿A quién se la quitas?");
      if (!targets) return;
      for (const p of targets) setFog(p, undefined);
      tell(player, `§aNiebla quitada a ${names(targets)}`);
    },
  ]);
  await menu(player, "§5Utilidad de Niebla", "Elige el color de la niebla y del cielo.", entries);
}
