import { world } from "@minecraft/server";

world.afterEvents.entityHurt.subscribe(event => {
    const target = event.hurtEntity;
    if (!target?.isValid()) return;
    const targetType = target.getComponent("minecraft:type_family");
    if (!targetType?.hasTypeFamily("terradraconis")) return;

    const healthComp = target.getComponent("minecraft:health");
    if (!healthComp) return;

    const currentHealth = healthComp.currentValue;

    if (currentHealth <= 0) {
        const source = target;
        if (!source) return;

        const level = source.getDynamicProperty("level") ?? 1;

        const orbCount = Math.min(100, Math.floor(level / 10));

        const dimension = target.dimension;
        const location = target.location;

        for (let i = 0; i < orbCount; i++) {
            // Slight random offset so orbs don't stack perfectly
            const offsetX = (Math.random() - 0.5) * 0.5;
            const offsetZ = (Math.random() - 0.5) * 0.5;

            dimension.spawnEntity("minecraft:xp_orb", {
                x: location.x + offsetX,
                y: location.y + 0.5,
                z: location.z + offsetZ
            });
        }
    }
});
