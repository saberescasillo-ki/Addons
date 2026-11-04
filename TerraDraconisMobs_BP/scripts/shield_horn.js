import { world, Player, EquipmentSlot, GameMode, system} from "@minecraft/server";

system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  if (!entity) return;
  if (event.id === "terradraconis:flee") {
    const view = entity.getViewDirection();
    let speed = 0.3
    let impulseY = 0;
    const impulse = {
        x: view.x * speed,
        y: impulseY,
        z: view.z * speed
    };
    if (entity.isOnGround){
        entity.applyImpulse(impulse);
    }
  }
});