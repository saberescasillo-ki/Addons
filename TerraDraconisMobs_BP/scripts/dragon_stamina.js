import { system } from "@minecraft/server";

system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  if (!entity || entity.typeId !== "terradraconis:crimson_racer") return;

  if (event.id === "terradraconis:dragon_stamina") {
    let stamina = entity.getDynamicProperty("stamina");
    let level = entity.getDynamicProperty("level");
    let max_stamina = entity.getDynamicProperty("max_stamina");
    if (entity.isOnGround) {
      stamina += 100 * level * 0.5;
    }
    const riders = entity.getComponent("rideable")?.getRiders() ?? [];
    const player = riders[0];
    if (!player) return;

    // Clamp stamina between 0 and max
    if (stamina <= 0) stamina = 0;
    if (stamina > max_stamina) stamina = max_stamina;

    // Update property after all logic
    entity.setDynamicProperty("stamina", stamina);

    // Show stamina to player
    player.runCommandAsync(
      `/title @s actionbar Dragon's Stamina: ${Math.floor(stamina)}/${max_stamina}`
    );
  }
});
