import { world, system } from "@minecraft/server";
import { ActionFormData , ModalFormData} from "@minecraft/server-ui";

// Raycast function
function raycastFromPlayer(player, maxDistance = 128) {
    const viewDir = player.getViewDirection();
    const origin = player.getHeadLocation();
    const dimension = player.dimension;

    for (let i = 7; i <= maxDistance; i++) {
        const pos = {
            x: origin.x + viewDir.x * i,
            y: origin.y + viewDir.y * i,
            z: origin.z + viewDir.z * i
        };

        const block = dimension.getBlock(pos);
        if (block && block.typeId !== "minecraft:air") break; // Stop if hit a block

        const hitEntities = dimension.getEntities({
            location: pos,
            maxDistance: 6,
        });

        for (const entity of hitEntities) {
            if (entity.typeId.includes("crimson")) return entity;
            console.warn(entity.nameTag)
        }
    }
    return null;
}

// Handle item use
world.afterEvents.itemUse.subscribe(event => {
    const { itemStack, source: player } = event;

    if (player && itemStack?.typeId == "minecraft:spyglass") {
        const dragon = raycastFromPlayer(player, 128);
        if (!dragon) {
            player.sendMessage("§cNo dragon detected in sight.");
            return;
        }

        system.run(() => {
            showDragonStatsForm(dragon, player);
        });
    }

    if (player && itemStack?.typeId == "minecraft:compass") {
        system.run(() => {
            settingForm(player);
        });
    }
});

function settingForm(player) {
    // Get current values or use defaults
    let max_level_entity = world.getDynamicProperty("max_level_entity") ?? 100;
    let wild_spawn_curve = world.getDynamicProperty("wild_spawn_curve") ?? 0.4;
    let wild_spawn_bias = world.getDynamicProperty("wild_spawn_bias") ?? 1.0;
    let mutation_min = world.getDynamicProperty("mutation_min") ?? 1.1;
    let mutation_max = world.getDynamicProperty("mutation_max") ?? 1.5;
    let mutation_chance = world.getDynamicProperty("mutation_chance") ?? 0.3;

    // Scale decimals to integers for slider
    const scaledCurve = Math.round(wild_spawn_curve * 10);
    const scaledBias = Math.round(wild_spawn_bias * 10);
    const scaledMutationMin = Math.round(mutation_min * 10);
    const scaledMutationMax = Math.round(mutation_max * 10);
    const scaledMutationChance = Math.round(mutation_chance * 10); // 0.3 → 3

    const modalForm = new ModalFormData().title('⚙ Wild Dragon Settings');

    modalForm.slider('🐉 Max Level Entity', 10, 720, 1, max_level_entity);

    modalForm.slider(
        'Spawn Curve (x0.1)\n- Lower = More High Levels\n- Higher = More Low Levels',
        1, 10, 1, scaledCurve
    );

    modalForm.slider(
        'Spawn Bias (x0.1)\n- >1.0 = Favor High Levels\n- <1.0 = Favor Low Levels',
        1, 30, 1, scaledBias
    );

    modalForm.slider(
        'Mutation Min (x0.1)\n- Min mutation multiplier (e.g. 1.1 = 110%%)',
        5, 30, 1, scaledMutationMin
    );

    modalForm.slider(
        'Mutation Max (x0.1)\n- Max mutation multiplier (e.g. 1.5 = 150%%)',
        10, 40, 1, scaledMutationMax
    );

    modalForm.slider(
        'Mutation Chance (x0.1)\n- Chance for mob to mutate (e.g. 1.0 = 100%%)',
        0, 10, 1, scaledMutationChance
    );

    modalForm.show(player).then(formData => {
        if (formData.canceled) {
            exit(player);
            return
        };

        const newMaxLevel = formData.formValues[0];
        const newCurve = formData.formValues[1] / 10;
        const newBias = formData.formValues[2] / 10;
        let newMutationMin = formData.formValues[3] / 10;
        let newMutationMax = formData.formValues[4] / 10;
        const newMutationChance = formData.formValues[5] / 10;

        player.sendMessage(`§l§6||--- Settings Updated ---||`);

        // Prevent invalid mutation range
        if (newMutationMin > newMutationMax) {
            const temp = newMutationMin;
            newMutationMin = newMutationMax;
            newMutationMax = temp;
            player.sendMessage("§e⚠ Mutation Min was higher than Max — values swapped.");
        }

        if (newMaxLevel !== max_level_entity) {
            world.setDynamicProperty("max_level_entity", newMaxLevel);
            player.sendMessage(`§aMax Level set to: §e${newMaxLevel}`);
        }

        if (newCurve !== wild_spawn_curve) {
            world.setDynamicProperty("wild_spawn_curve", newCurve);
            player.sendMessage(`§aSpawn Curve set to: §e${newCurve.toFixed(1)}`);
        }

        if (newBias !== wild_spawn_bias) {
            world.setDynamicProperty("wild_spawn_bias", newBias);
            player.sendMessage(`§aSpawn Bias set to: §e${newBias.toFixed(1)}`);
        }

        if (newMutationMin !== mutation_min) {
            world.setDynamicProperty("mutation_min", newMutationMin);
            player.sendMessage(`§aMutation Min set to: §e${newMutationMin.toFixed(1)}`);
        }

        if (newMutationMax !== mutation_max) {
            world.setDynamicProperty("mutation_max", newMutationMax);
            player.sendMessage(`§aMutation Max set to: §e${newMutationMax.toFixed(1)}`);
        }

        if (newMutationChance !== mutation_chance) {
            world.setDynamicProperty("mutation_chance", newMutationChance);
            player.sendMessage(`§aMutation Chance set to: §e${(newMutationChance * 100).toFixed(0)}%%`);
        }

        save(player);
    });
    popup(player)
}


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


function showDragonStatsForm(entity, player) {
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

    const levelBonus = level * 0.15;
    const health = entity.getComponent("minecraft:health")?.currentValue ?? 0;
    const maxhealth = entity.getComponent("minecraft:health")?.effectiveMax ?? 0;

    const form = new ActionFormData()
        .title(`§e${entity.nameTag || "Dragon"} Stats`)
        .body(
`§6§l➤ §r§fLevel Overview
§7• §fLevel: §b${level}
§7• §fSkill Points: §d${skill_point}
§7• §fLevel Bonus: §d${levelBonus.toFixed(2)}x

§6§l➤ §r§fTaming
§7• §fTorpor: §a${torpor}/${maxTorpor}
§7• §fTaming: §a${taming}/${maxTaming}

§6§l➤ §r§fMutation
§7• §fType: §a${mutation}
§7• §fValue: §a${mutationFactor.toFixed(2)}x (${mutationRaw}%)

§6§l➤ §r§fStats Overview
§7• §fHealth: §a${health.toFixed(1)}/${maxhealth.toFixed(1)}
§7• §fFlying Speed: §a${speed}%%
§7• §fDamage: §a${damage}%%
§7• §fResistance: §a${resistance}%%
§7• §fStamina: §a${stamina}
§7• §fExhaustion Multiplier: §c${(exhause / 100).toFixed(1)}x`
        )
        .button("§aClose");

    form.show(player).then(r => {
        if (r.canceled) {
            exit(player);
            return;
        };

        if (r.selection === 0) {
            button(player)
        }
    });
    popup(player)
}
