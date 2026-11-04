import { world } from "@minecraft/server";
world.afterEvents.entitySpawn.subscribe(event => {
    applyScalingToEntity(event.entity);
});


function applyScalingToEntity(entity) {
    const typeFamily = entity.getComponent("minecraft:type_family");
    if (!entity) return;
    if (!typeFamily?.hasTypeFamily("terradraconis_animal")) return;

    // Prevent reapplying scaling
    const alreadyScaled = entity.getDynamicProperty("scaled");
    if (alreadyScaled) return;

    const maxLevel = world.getDynamicProperty("max_level_entity") ?? 10;
    const spawnCurve = world.getDynamicProperty("wild_spawn_curve") ?? 0.4;
    const baseBias = world.getDynamicProperty("wild_spawn_bias") ?? 1.0;

    // Scale bias by world day
    // Scale bias by world day
    // Make sure day is at least 1 (so day 0 becomes 1)
    const currentDay = Math.max(1, world.getDay());

    // Adjusted bias: decreases slowly over time (higher levels more likely)
    const dayFactor = Math.log2(currentDay + 1); // log2(2) = 1 on day 1
    const adjustedBias = baseBias * dayFactor; // increase bias as day increases

    const raw = Math.random();
    const biased = Math.pow(raw, spawnCurve / adjustedBias);

    // Calculate level
    let level = Math.floor(biased * (maxLevel + 1));
    level = Math.max(level, 1); // minimum level is 1
    const levelBonus = Math.log2(level + 1) * 0.5;

    entity.setDynamicProperty("level", level);
    entity.setDynamicProperty("scaled", true);

    const effectLevel = Math.min(Math.floor(level / 10), 100);
    if (effectLevel > 0) {
        entity.addEffect("health_boost", 999999, {
            amplifier: effectLevel - 1,
            showParticles: false
        });
        entity.addEffect("speed", 999999, {
            amplifier: Math.max(effectLevel - 20, 0),
            showParticles: false
        });

        if (typeFamily?.hasTypeFamily("undead")) {
            entity.addEffect("instant_damage", 20, {
                amplifier: 255,
                showParticles: false
            });
        } else {
            entity.addEffect("instant_health", 20, {
                amplifier: 255,
                showParticles: false
            });
        }
    }

    const baseDamage = 100;
    const baseResistance = 100;

    const scale = (base) => {
        const multiplier = levelBonus;
        return Math.round(base + base * multiplier);
    };

    const newDamage = scale(baseDamage);
    const newResistance = scale(baseResistance);

    entity.setDynamicProperty("damage", newDamage);
    entity.setDynamicProperty("resistance", newResistance);

    const typeId = entity.typeId.split(":")[1] ?? "Unknown";
    const nameWords = typeId
        .replace(/_/g, " ")
        .replace(/\b\w/g, c => c.toUpperCase());

    entity.nameTag = `§c${nameWords} Lv.${level}`;
}


world.afterEvents.entityHurt.subscribe(event => {
    const target = event.hurtEntity;
    if (!target?.isValid()) return;
    const source = event.damageSource?.damagingEntity;

    // === 💢 DAMAGE BOOST SYSTEM (attacker) ===
    if (source?.isValid()) {
        const typeFamily = source.getComponent("minecraft:type_family");

        if (typeFamily?.hasTypeFamily("terradraconis_animal")) {
            const baseDamage = event.damage;
            const damagePercent = source.getDynamicProperty("damage") ?? 100;
            const damageFactor = damagePercent / 100;

            const finalDamage = baseDamage * damageFactor;
            const extraDamage = finalDamage - baseDamage;

            if (extraDamage > 0) {
                if (target.isValid()) target.applyDamage(extraDamage);
            }
        }
    }

    // === 🛡️ RESISTANCE SYSTEM (defender) ===
    const targetType = target.getComponent("minecraft:type_family");

    if (targetType?.hasTypeFamily("terradraconis_animal")) {
        const baseDamage = event.damage;
        const resistance = target.getDynamicProperty("resistance") ?? 100;

        const resistanceFactor = 1 / (1 + (resistance / 100));
        const actualDamage = baseDamage * resistanceFactor;
        const damageReduced = baseDamage - actualDamage;

        const healthComp = target.getComponent("minecraft:health");
        if (!healthComp) return;

        const currentHealth = healthComp.currentValue;
        const maxHealth = healthComp.effectiveMax;

        const healAmount = Math.min(damageReduced, maxHealth - currentHealth);
        healthComp.setCurrentValue(currentHealth + healAmount);
    }
});