// Utilidad de Niebla: colours the fog (and with it the sky) with one of the presets, density 1-15.
import { NIEBLAS, NIEBLA_DENSIDAD_MAX } from "./config.js";
import { menu, modal, names, pickTargets, run, tell } from "./common.js";

const TAG = "ifrit_niebla";
const LAST = "ifrit:niebla_densidad";

function setFog(p, fogId) {
  run(p, `fog @s remove ${TAG}`);
  if (fogId) run(p, `fog @s push ${fogId} ${TAG}`);
}

export async function fogMenu(player) {
  const entries = NIEBLAS.map((n) => [
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
      for (const p of targets) setFog(p, `ifrit:niebla_${n.id}_${density}`);
      tell(player, `§aNiebla ${n.nombre} (densidad ${density}) para ${names(targets)}`);
    },
  ]);
  entries.push([
    "§cQuitar niebla",
    async () => {
      const targets = await pickTargets(player, "¿A quién se la quitas?");
      if (!targets) return;
      for (const p of targets) setFog(p, null);
      tell(player, `§aNiebla quitada a ${names(targets)}`);
    },
  ]);
  await menu(player, "§5Utilidad de Niebla", "Elige el color de la niebla y del cielo.", entries);
}
