import { system } from "@minecraft/server";
// Start flying logic
system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  if (!entity || entity.typeId !== "terradraconis:crimson_racer") return;

  if (event.id === "terradraconis:start_flight") {

    const riders = entity.getComponent("rideable")?.getRiders() ?? [];
    const player = riders[0];
    if (!player) return;
    let stamina = entity.getDynamicProperty("stamina");
    let max_stamina = entity.getDynamicProperty("max_stamina");
    let speed = entity.getDynamicProperty("speed");
    let flying_speed = entity.getDynamicProperty("flying_speed");
    let exhause = entity.getDynamicProperty("exhause") ?? 1;

    const view = player.getViewDirection();
    let impulseY = 0;
    if (stamina <= 0) {
        return;
    }
    if (view.y >= 0) {
        impulseY = view.y * 0.35;
        stamina -= 10 * exhause / 100;
        flying_speed += 0.2 + (speed / 100)  * 0.01
    }
    else if (view.y < 0 && view.y > -0.8) {
        impulseY = view.y * 0.15;
        entity.addEffect("levitation", 10, {
            amplifier: 0,
            showParticles: false,
        });
        flying_speed += (speed / 100) * 0.01
        stamina -= 5 * exhause / 100;
    }
    else {
        impulseY = view.y * 0.2;
        flying_speed += 0.5 + (speed / 100) * 0.01
    }

    const impulse = {
        x: view.x * flying_speed,
        y: impulseY,
        z: view.z * flying_speed
    };

    entity.applyImpulse(impulse);
    entity.addEffect("slow_falling", 20, {
      amplifier: 1,
      showParticles: false,
    });
    entity.setDynamicProperty("stamina", stamina);
    player.runCommandAsync(
      `/title @s actionbar Dragon's Stamina: ${Math.floor(stamina)}/${max_stamina}`
    );
  }
});
