import { world } from "@minecraft/server";
import {
  mutationTypes
} from './config.js';
world.afterEvents.entitySpawn.subscribe(({ entity }) => {
    const typeFamilyComp = entity.getComponent("minecraft:type_family");
    if (typeFamilyComp && typeFamilyComp.hasTypeFamily("terradraconis_dragon") && typeFamilyComp.hasTypeFamily("glider")){
        if (entity.getDynamicProperty("skip_autoscale")) return;
        level1(entity);
    };
});

function level1(entity) {
    const randomStamina = Math.floor(Math.random() * (2000 - 1000 + 1)) + 1000;
    const minTorpor = 2000;
    const maxTorpor = 5000;
    const minTaming = 1000;
    const maxTaming = 2000;
    const randomMaxTorpor = Math.floor(Math.random() * (maxTorpor - minTorpor + 1)) + minTorpor;
    const randomMaxTaming = Math.floor(Math.random() * (maxTaming - minTaming + 1)) + minTaming;

    entity.setDynamicProperty("max_stamina", randomStamina);
    entity.setDynamicProperty("stamina", randomStamina);
    entity.setDynamicProperty("exhause", 100);
    entity.setDynamicProperty("flying_speed", 0.2);
    entity.setDynamicProperty("max_flying_speed", 0.4);
    entity.setDynamicProperty("level", 1);
    entity.setDynamicProperty("max_level", world.getDynamicProperty("max_level_entity"));
    entity.setDynamicProperty("skill_point", 10);
    entity.setDynamicProperty("resistance", 100);
    entity.setDynamicProperty("damage", 100);
    entity.setDynamicProperty("speed", 100);

    entity.setDynamicProperty("max_torpor", randomMaxTorpor);
    entity.setDynamicProperty("max_taming", randomMaxTaming);
    entity.setDynamicProperty("torpor", 0);
    entity.setDynamicProperty("taming", 0);

    // --- Mutation logic ---
    mutationOccur(entity);
}


function mutationOccur(entity){
    const roll = Math.random();

    let chosenMutation;
    let mutationValue = 1;
    const mutationMin = world.getDynamicProperty("mutation_min") ?? 1.1;
    const mutationMax = world.getDynamicProperty("mutation_max") ?? 1.5;
    const mutation_chance = world.getDynamicProperty("mutation_chance") ?? 0.5;
    if (roll > mutation_chance) {
        // 60% chance
        chosenMutation = "none";
        entity.setDynamicProperty("mutation_value", 1); // No bonus
        entity.setDynamicProperty("mutation_type", chosenMutation);
    } else {
        // 40% split between the 4 mutation types
        chosenMutation = mutationTypes[Math.floor(Math.random() * mutationTypes.length)];

        mutationValue = Math.round(
            (Math.random() * (mutationMax - mutationMin) + mutationMin) * 100
        );
        entity.setDynamicProperty("mutation_type", chosenMutation);
        entity.setDynamicProperty("mutation_value", mutationValue);
    }
}

world.afterEvents.entitySpawn.subscribe(event => {
    const entity = event.entity;
    const typeFamily = entity.getComponent("minecraft:type_family");
    const tamed = entity.getComponent("minecraft:is_tamed");
    if (!entity) return;
    if (tamed) return;
    if (!typeFamily?.hasTypeFamily("terradraconis_dragon") || !typeFamily.hasTypeFamily("wild_dragon")) {
        if (typeFamily?.hasTypeFamily("terradraconis_dragon")) {
            if (entity.getDynamicProperty("skip_autoscale")) return;
            const typeId = entity.typeId.split(":")[1] ?? "Unknown";
            const nameWords = typeId
                .replace(/_/g, " ")
                .replace(/\b\w/g, c => c.toUpperCase());

            entity.nameTag = `§c${nameWords} Lv.1`;
            const effectLevel = 1;
            if (effectLevel > 0) {
                entity.addEffect("health_boost", 999999, {
                    amplifier: effectLevel - 1,
                    showParticles: false
                });
                entity.addEffect("instant_health", 20, {
                    amplifier: 255,
                    showParticles: false
                });
            }
        }
        return
    };

    // Prevent reapplying scaling
    const alreadyScaled = entity.getDynamicProperty("wild_scaled");
    if (alreadyScaled) return;

    const maxLevel = world.getDynamicProperty("max_level_entity") ?? 10;
    const spawnCurve = world.getDynamicProperty("wild_spawn_curve") ?? 0.4;
    const baseBias = world.getDynamicProperty("wild_spawn_bias") ?? 1.0;

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

    // === Get mutation from existing properties ===
    const mutationType = entity.getDynamicProperty("mutation_type") ?? "none";
    const mutationRaw = entity.getDynamicProperty("mutation_value") ?? 100;
    const mutationFactor = mutationRaw / 100;

    entity.setDynamicProperty("level", level);
    entity.setDynamicProperty("wild_scaled", true);

    const effectLevel = Math.min(Math.floor(level / 10), 100);
    if (effectLevel > 0) {
        entity.addEffect("health_boost", 999999, {
            amplifier: effectLevel - 1,
            showParticles: false
        });
        entity.addEffect("instant_health", 20, {
            amplifier: 255,
            showParticles: false
        });
    }

    // === Base stats ===
    const baseSpeed = 100;
    const baseDamage = 100;
    const baseResistance = 100;
    const baseStamina = 1000;
    const baseTorpor = entity.getDynamicProperty("max_torpor");
    const baseTaming = entity.getDynamicProperty("max_taming")

    // === Apply scaling and mutation ===
    const scale = (base, type) => {
        const isMutated = mutationType === type;
        const multiplier = levelBonus * (isMutated ? mutationFactor : 1);
        return Math.round(base + base * multiplier);
    };

    const newSpeed = scale(baseSpeed, "speed");
    const newDamage = scale(baseDamage, "damage");
    const newResistance = scale(baseResistance, "resistance");
    const newStamina = scale(baseStamina, "stamina");
    const newTorpor = scaleByLevel(baseTorpor, level, 0.05);
    const newTaming = scaleByLevel(baseTaming, level, 0.05);

    entity.setDynamicProperty("speed", newSpeed);
    entity.setDynamicProperty("damage", newDamage);
    entity.setDynamicProperty("resistance", newResistance);
    entity.setDynamicProperty("max_stamina", newStamina);
    entity.setDynamicProperty("stamina", newStamina);
    entity.setDynamicProperty("max_torpor", newTorpor);
    entity.setDynamicProperty("max_taming", newTaming);

    // === Optional: Name tag ===
    const typeId = entity.typeId.split(":")[1] ?? "Unknown";
    const nameWords = typeId
        .replace(/_/g, " ")
        .replace(/\b\w/g, c => c.toUpperCase());

    entity.nameTag = `§c${nameWords} Lv.${level}`;
});

function scaleByLevel(baseValue, level, perLevelBonus = 0.05) {
  const multiplier = 1 + (level - 1) * perLevelBonus;
  return Math.round(baseValue * multiplier);
}