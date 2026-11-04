import { system, world , GameMode, EquipmentSlot} from "@minecraft/server";
import { ActionFormData } from '@minecraft/server-ui';

world.beforeEvents.playerInteractWithEntity.subscribe(event => {
    const { player, target, itemStack } = event;

    if (itemStack?.typeId !== "terradraconis:dragon_orb") return;
    event.cancel = true;

    const typeFamily = target.getComponent("minecraft:type_family");
    const isTamed = target.getComponent("minecraft:is_tamed");
    if (typeFamily?.hasTypeFamily("terradraconis_dragon") && isTamed && !player.isSneaking) {
        let level = target.getDynamicProperty("level");
        let maxlevel = target.getDynamicProperty("max_level");
        if (level < maxlevel) {
            level++;
            target.setDynamicProperty("level", level);
            system.run(() => {
                decrementStack(player);
            });
            let skill_point = target.getDynamicProperty("skill_point");
            skill_point += 1;
            target.setDynamicProperty("skill_point", skill_point);
            target.runCommandAsync("/playsound random.levelup @a[r=16] ~~~");
            system.runTimeout(() => {
                const typeId = target.typeId.split(":")[1] ?? "Unknown";
                const nameWords = typeId
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, c => c.toUpperCase());

                const level = target.getDynamicProperty("level") ?? 1;

                target.nameTag = `§c${nameWords} Lv.${level}`;
            }, 1);
        }
    } else if (typeFamily?.hasTypeFamily("terradraconis_dragon") && isTamed && player.isSneaking) {
        system.run(() => {
            modifyDragon(target, player);
        });
    }
});


function decrementStack(source){
    if (!source) return;

    const equippable = source.getComponent("minecraft:equippable");
    if (!equippable) return;

    const mainhand = equippable.getEquipmentSlot(EquipmentSlot.Mainhand);
    if (!mainhand.hasItem()) return;

    if (source.getGameMode() !== GameMode.Creative) {
        if (mainhand.amount > 1) {
            mainhand.amount--; // Remove one item from the stack
        } else {
            mainhand.setItem(undefined); // Remove the item stack
        }
    }
}



//Skill Upgrade
function modifyDragon(entity, player) {
    const level = entity.getDynamicProperty("level") ?? 1;
    const skill_point = entity.getDynamicProperty("skill_point") ?? 0;
    const mutation = entity.getDynamicProperty("mutation_type") ?? "none";
    const mutationRaw = entity.getDynamicProperty("mutation_value") ?? 100;
    const mutationFactor = mutationRaw / 100;

    const speed = entity.getDynamicProperty("speed") ?? 100;
    const damage = entity.getDynamicProperty("damage") ?? 100;
    const resistance = entity.getDynamicProperty("resistance") ?? 100;
    const stamina = entity.getDynamicProperty("max_stamina") ?? 1000;
    const exhause = entity.getDynamicProperty("exhause") ?? 100;

    const torpor = entity.getDynamicProperty("torpor") ?? 0;
    const taming = entity.getDynamicProperty("taming") ?? 0;
    const maxTorpor = entity.getDynamicProperty("max_torpor") ?? 0;
    const maxTaming = entity.getDynamicProperty("max_taming") ?? 0;


    const levelBonus = level * 0.05;
    const basePercent = 5;
    const baseStamina = 200;

    const bonusSpeed = Math.round(basePercent * (mutation === "speed" ? mutationFactor : 1) * levelBonus);
    const bonusDamage = Math.round(basePercent * (mutation === "damage" ? mutationFactor : 1) * levelBonus);
    const bonusResistance = Math.round(basePercent * (mutation === "resistance" ? mutationFactor : 1) * levelBonus);
    const bonusStamina = Math.round(baseStamina * (mutation === "stamina" ? mutationFactor : 1) * levelBonus);

    const form = new ActionFormData()
        .title(`§l§e${entity.nameTag} Status`)
        .body(
`§6§l➤ §r§fLevel Overview
§7• §fLevel: §b${level}
§7• §fSkill Points: §d${skill_point}
§7• §fLevel Bonus: §d${(levelBonus).toFixed(2)}x

§6§l➤ §r§fTaming
§7• §fTorpor: §a${torpor}/${maxTorpor}
§7• §fTaming: §a${taming}/${maxTaming}

§6§l➤ §r§fMutation
§7• §fType: §a${mutation}
§7• §fValue: §a${mutationFactor.toFixed(2)}x (${mutationRaw}%)

§6§l➤ §r§fStats Overview
§7• §fHealth: §a${entity.getComponent("minecraft:health").currentValue.toFixed(1)}
§7• §fFlying Speed: §a${speed}%%
§7• §fDamage: §a${damage}%%
§7• §fResistance: §a${resistance}%%
§7• §fStamina: §a${stamina}
§7• §fExhaustion Multiplier: §c${(exhause / 100).toFixed(1)}x`
        )
        .button(`§6§l➤ §r§f§2Speed §3§l[+${bonusSpeed}%%] \n§c§l[-${ Math.max(1, Math.floor(1 * levelBonus))} skill points]`)
        .button(`§6§l➤ §r§f§2Damage §3§l[+${bonusDamage}%%] \n§c§l[-${ Math.max(1, Math.floor(1 * levelBonus))} skill points]`)
        .button(`§6§l➤ §r§f§2Resistance Boost §3§l[+${bonusResistance}%%] \n§c§l[-${ Math.max(1, Math.floor(1 * levelBonus))} skill points]`)
        .button(`§6§l➤ §r§f§2Stamina §3§l[+${bonusStamina} pts] \n§c§l[-${ Math.max(1, Math.floor(1 * levelBonus))} skill points]`);

    form.show(player).then(r => {
        if (r.canceled) {
            exit(player);
            return;
        };

        if (r.selection === 0 && skill_point >=  Math.max(1, Math.floor(1 * levelBonus * 2))) {
            upgradeSkill(entity, player, "speed", bonusSpeed,  Math.max(1, Math.floor(1 * levelBonus * 2)));
            exhauseHandle(entity, mutation, levelBonus);
            modifyDragon(entity, player);
            button(player);
            player.runCommand("/stopsound @s ui_popup")
        } else if (r.selection === 1 && skill_point >=  Math.max(1, Math.floor(1 * levelBonus))) {
            upgradeSkill(entity, player, "damage", bonusDamage,  Math.max(1, Math.floor(1 * levelBonus)));
            modifyDragon(entity, player);
            button(player);
            player.runCommand("/stopsound @s ui_popup")
        } else if (r.selection === 2 && skill_point >=  Math.max(1, Math.floor(1 * levelBonus))) {
            upgradeSkill(entity, player, "resistance", bonusResistance,  Math.max(1, Math.floor(1 * levelBonus)));
            modifyDragon(entity, player);
            button(player);
            player.runCommand("/stopsound @s ui_popup")
        } else if (r.selection === 3 && skill_point >=  Math.max(1, Math.floor(1 * levelBonus))) {
            upgradeSkill(entity, player, "max_stamina", bonusStamina,  Math.max(1, Math.floor(1 * levelBonus)));
            modifyDragon(entity, player);
            button(player);
            player.runCommand("/stopsound @s ui_popup")
        } else if (r.selection !== undefined) {
            player.sendMessage("§cInsufficient Skill Points!");
            player.playSound("note.bass");
            button(player);
            player.runCommand("/stopsound @s ui_popup")
        }
    });
    popup(player);
}


function upgradeSkill(entity, player, type, value, cost) {
    const currentValue = entity.getDynamicProperty(type) ?? 0;
    const newValue = currentValue + value;
    const currentSkillPoints = entity.getDynamicProperty("skill_point");
    const newCost = currentSkillPoints - cost;
    entity.setDynamicProperty("skill_point", newCost);
    entity.setDynamicProperty(type, newValue);
    // console.warn(`Entity upgraded: ${type} increased by ${value.toFixed(2)} → total: ${newValue.toFixed(2)}`);
}

function exhauseHandle(entity, mutation, levelBonus) {
    const currentExhause = entity.getDynamicProperty("exhause") ?? 1.0;

    const baseIncrease = mutation === "speed" ? 1 : 2;

    // Make it scale more noticeably at higher levelBonus
    const multiplier = 5; // <-- increase this to boost growth
    const adjustedIncrease = baseIncrease * (1 + levelBonus * multiplier);

    const newExhause = currentExhause + adjustedIncrease;

    entity.setDynamicProperty("exhause", newExhause);

    // console.warn(`Exhause +${adjustedIncrease.toFixed(3)} (Bonus ${levelBonus}) → Total: ${newExhause.toFixed(3)}`);
}



world.afterEvents.entityHurt.subscribe(event => {
    const target = event.hurtEntity;
    const source = event.damageSource?.damagingEntity;

    // === 💢 DAMAGE BOOST SYSTEM (attacker) ===
    if (source) {
        const typeFamily = source.getComponent("minecraft:type_family");

        if (typeFamily?.hasTypeFamily("terradraconis_dragon")) {
            const baseDamage = event.damage;
            const damagePercent = source.getDynamicProperty("damage") ?? 100;
            const damageFactor = damagePercent / 100;

            const finalDamage = baseDamage * damageFactor;
            const extraDamage = finalDamage - baseDamage;

            if (extraDamage > 0) {
                target.applyDamage(extraDamage);
            }
        }
    }

    // === 🛡️ RESISTANCE SYSTEM (defender) ===
    const targetType = target.getComponent("minecraft:type_family");

    if (targetType?.hasTypeFamily("terradraconis_dragon")) {
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

function popup(player){
    player.playSound("ui_popup")
}

function exit(player){
    player.runCommand("/stopsound @s random.click")
    player.playSound("ui_exit")
}

function save(player){
    player.runCommand("/stopsound @s random.click")
    player.playSound("ui_save")
}

function button(player){
    player.runCommand("/stopsound @s random.click")
    player.playSound("button")
}