// Natura PvP: every area of the map (lobby, Emparejamiento maps, Campal and
// hunting maps), as used by the script, the previews and the world writer.
import { box, PALETTE } from "./core.js";
import { LOBBY, LOBBY_AREA, PARKOUR } from "./lobby.js";
import { DUEL, DUELS } from "./duels.js";
import { CAMPAL, CAMPAL_AREA, campalSpawns } from "./campal.js";
import { HUNT, HUNTS } from "./hunts.js";

export { CAMPAL, campalSpawns, DUEL, DUELS, HUNT, HUNTS, LOBBY, PALETTE, PARKOUR };

export const AREAS = [
  LOBBY_AREA,
  ...DUELS.map((d) => ({ id: d.id, name: `Emparejamiento: ${d.name}`, ...box(d.cx, d.cz, DUEL.half, DUEL.thick), bottom: DUEL.y - 6, clearTop: DUEL.wallTop + 16, column: d.column })),
  CAMPAL_AREA,
  ...HUNTS.map((m) => ({ id: m.id, name: `Caza: ${m.name}`, x0: m.x0 - HUNT.wallThick, z0: m.z0 - HUNT.wallThick, x1: m.x1 + HUNT.wallThick, z1: m.z1 + HUNT.wallThick, bottom: HUNT.floor, clearTop: HUNT.clearTop, column: m.column })),
];

export const AREA = Object.fromEntries(AREAS.map((a) => [a.id, a]));

export function insideArea(id, x, z, margin = 0) {
  const a = AREA[id];
  return x >= a.x0 - margin && x <= a.x1 + margin && z >= a.z0 - margin && z <= a.z1 + margin;
}
