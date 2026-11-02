// Killer Sure: kills any player at once, like /kill.
import { world } from "@minecraft/server";
import { menu, pickPlayers, run, settingsButton, tell, valid } from "./common.js";

export function kill(player, targets) {
  const dead = targets.filter((p) => valid(p) && run(p, "kill @s"));
  if (dead.length) tell(player, `§c${dead.map((p) => p.name).join(", ")} §7eliminado${dead.length > 1 ? "s" : ""}`);
}

export async function killerMenu(player) {
  const others = world.getAllPlayers().filter((p) => p.id !== player.id);
  const entries = others.map((p) => [`§c${p.name}`, () => kill(player, [p])]);
  entries.push(
    ["Elegir varios...", async () => kill(player, (await pickPlayers(player, "¿A quién matas?")) ?? [])],
    ["§4Todos menos yo", () => kill(player, others)],
    ["Yo", () => kill(player, [player])],
    settingsButton(player)
  );
  await menu(
    player,
    "§4Killer Sure",
    "Toca un jugador para matarlo al instante.\n§7También puedes golpear a un jugador con el objeto.",
    entries
  );
}
