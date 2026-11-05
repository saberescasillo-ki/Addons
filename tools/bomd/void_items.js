// @ts-check
// The Void Blossom's Crystal Fruit (taken from progression/artifacts.js, which
// held the other bosses' artifacts too).

import { isEntityUsable } from "../core/safe.js";

export function registerVoidItems(itemRegistry) {
  itemRegistry.registerCustomComponent("bomd:crystal_fruit", {
    onConsume(event) {
      const entity = event.source;
      if (!isEntityUsable(entity)) return;
      entity.addEffect("regeneration", 300, { amplifier: 1, showParticles: true });
      entity.addEffect("instant_health", 1, { amplifier: 0, showParticles: true });
      entity.addEffect("resistance", 600, { amplifier: 0, showParticles: true });
    }
  });
}
