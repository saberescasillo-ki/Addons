// @ts-check
// BOMD Bedrock, reduced to the Void Blossom (tools/bomd_void.py). The other three
// bosses, their items and structures are gone; the settings menu stays.

import { system, world } from "@minecraft/server";
import { forgetVoidBlossom, startVoidBlossomManager } from "./bosses/void_blossom.js";
import { VOID_BLOSSOM_TYPE, VOID_PETAL_PARTICLE } from "./core/config.js";
import { registerBalanceProfileCommands } from "./core/balance.js";
import { registerDamagePipeline } from "./core/damage_pipeline.js";
import { registerConfigSystem } from "./ui/config_command.js";
import { startImmersiveCombatCompatibility } from "./core/immersive_combat_compat.js";
import { runSafely } from "./core/safe.js";
import { registerProjectileEvents } from "./projectiles/projectile_events.js";
import { dropBossLoot } from "./progression/boss_loot.js";
import { recordVoidCavernDefeated, registerVoidCavernComponents } from "./progression/void_cavern.js";
import { registerVoidItems } from "./progression/void_items.js";
import { playSound, spawnBurst } from "./visuals/frost.js";

// The damage pipeline must subscribe before every boss damage handler.
registerDamagePipeline();
registerConfigSystem();
registerProjectileEvents();
registerBalanceProfileCommands();
startImmersiveCombatCompatibility();

system.beforeEvents.startup.subscribe((event) => {
  runSafely(() => registerVoidCavernComponents(event.blockComponentRegistry), "register Void Blossom cavern");
  runSafely(() => registerVoidItems(event.itemComponentRegistry), "register Void Blossom items");
});

world.afterEvents.entityDie.subscribe((event) => {
  if (event.deadEntity.typeId !== VOID_BLOSSOM_TYPE) return;
  const location = { ...event.deadEntity.location };
  const dimension = event.deadEntity.dimension;
  forgetVoidBlossom(event.deadEntity.id);
  dropBossLoot(VOID_BLOSSOM_TYPE, dimension, location);
  recordVoidCavernDefeated(dimension, location);
  spawnBurst(dimension, location, 64, 4.5, VOID_PETAL_PARTICLE);
  playSound(dimension, "bomd.void_blossom.fall", location, 2.2, 0.9);
});

system.run(() => {
  runSafely(startVoidBlossomManager, "start Void Blossom manager");
});
