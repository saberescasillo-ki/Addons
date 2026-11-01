// Útils for Ifrit: utilities activated with items.
import { EquipmentSlot, system, world } from "@minecraft/server";
import { ITEMS } from "./config.js";
import { cameraMenu } from "./camera.js";
import { addPoint, creatorMenu } from "./cinematics.js";
import { effectsMenu } from "./effects.js";
import { fogMenu } from "./fog.js";
import { kill, killerMenu } from "./killer.js";
import { timeMenu } from "./time.js";

const MENUS = {
  [ITEMS.niebla]: fogMenu,
  [ITEMS.camara]: cameraMenu,
  [ITEMS.creador]: creatorMenu,
  [ITEMS.killer]: killerMenu,
  [ITEMS.tiempo]: timeMenu,
  [ITEMS.efectos]: effectsMenu,
};
const lastUse = new Map();

world.afterEvents.itemUse.subscribe(({ source: player, itemStack }) => {
  const open = MENUS[itemStack?.typeId];
  if (!open) return;
  const now = system.currentTick;
  if (now - (lastUse.get(player.id) ?? -100) < 8) return;
  lastUse.set(player.id, now);
  // Cinematic Creator: sneak + use saves a point without opening the menu.
  if (itemStack.typeId === ITEMS.creador && player.isSneaking) return addPoint(player);
  open(player).catch((e) => console.warn(`[Utils for Ifrit] ${e}`));
});

// Killer Sure: hitting a player with it kills them at once.
world.afterEvents.entityHitEntity.subscribe(({ damagingEntity, hitEntity }) => {
  if (damagingEntity?.typeId !== "minecraft:player" || hitEntity?.typeId !== "minecraft:player") return;
  let held;
  try {
    held = damagingEntity.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand);
  } catch {}
  if (held?.typeId === ITEMS.killer) kill(damagingEntity, [hitEntity]);
});

world.afterEvents.playerLeave.subscribe(({ playerId }) => lastUse.delete(playerId));
