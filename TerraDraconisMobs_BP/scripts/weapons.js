import { world, Player, EquipmentSlot, GameMode } from "@minecraft/server";
import { chargableItem , ShootableItem} from "./config";

const SteelCrossbowShoot = {
    onUse({ source, itemStack }) {
        const player = source;
        if (!player || !itemStack) return;

        const equippable = player.getComponent("minecraft:equippable");
        if (!equippable) return;

        const mainhand = equippable.getEquipmentSlot(EquipmentSlot.Mainhand);
        if (!mainhand.hasItem()) return;

        let mainhandItem = mainhand.getItem();
        const durability = mainhandItem.getComponent("minecraft:durability");
        if (!durability) return;

        const inventory = player.getComponent("minecraft:inventory");
        let hasArrow = false;
        let arrowType = "";
        let arrowSlot = -1;

        if (inventory) {
            for (let i = 0; i < inventory.container.size; i++) {
                const item = inventory.container.getItem(i);
                if (item?.typeId === "terradraconis:steel_arrow_it") {
                    hasArrow = true;
                    arrowSlot = i;
                    arrowType = "steel";
                    
                    break;
                } else if (item?.typeId === "terradraconis:tranq_steel_arrow_it") {
                    hasArrow = true;
                    arrowType = "tranq";
                    arrowSlot = i;
                    break;
                }
            }
        }

        if (hasArrow) {
            const power = mainhandItem.getDynamicProperty("power") ?? 100;
            Shoot(player, arrowType, mainhandItem, power);
            // Handle durability if not in creative mode
            if (player.getGameMode?.() !== "creative") {
                arrowDeplete(inventory, arrowSlot );
                reduceDur(player);
            }

        } else {
            player.sendMessage(`No ammo to reload!`);
            player.playSound("note.bass");
        }
    }
};

// Register the custom component
world.beforeEvents.worldInitialize.subscribe(({ itemComponentRegistry }) => {
    itemComponentRegistry.registerCustomComponent("terradraconis:steel_crossbow_shoot", SteelCrossbowShoot);
});

const LongNeckRifleShoot = {
    onUse({ source, itemStack }) {
        const player = source;
        if (!player || !itemStack) return;

        const equippable = player.getComponent("minecraft:equippable");
        if (!equippable) return;

        const mainhand = equippable.getEquipmentSlot(EquipmentSlot.Mainhand);
        if (!mainhand.hasItem()) return;

        let mainhandItem = mainhand.getItem();
        const durability = mainhandItem.getComponent("minecraft:durability");
        if (!durability) return;

        const inventory = player.getComponent("minecraft:inventory");
        let hasArrow = false;
        let arrowType = "";
        let arrowSlot = -1;

        if (inventory) {
            for (let i = 0; i < inventory.container.size; i++) {
                const item = inventory.container.getItem(i);
                if (item?.typeId === "terradraconis:steel_bullet_it") {
                    hasArrow = true;
                    arrowSlot = i;
                    arrowType = "steel";
                    
                    break;
                } else if (item?.typeId === "terradraconis:tranq_bullet_it") {
                    hasArrow = true;
                    arrowType = "tranq";
                    arrowSlot = i;
                    break;
                }
            }
        }

        if (hasArrow) {
            const power = mainhandItem.getDynamicProperty("power") ?? 100;
            Shoot2(player, arrowType, mainhandItem, power);
            // Handle durability if not in creative mode
            if (player.getGameMode?.() !== "creative") {
                arrowDeplete(inventory, arrowSlot );
                reduceDur(player);
            }

        } else {
            player.sendMessage(`No ammo to reload!`);
            player.playSound("note.bass");
        }
    }
};

// Register the custom component
world.beforeEvents.worldInitialize.subscribe(({ itemComponentRegistry }) => {
    itemComponentRegistry.registerCustomComponent("terradraconis:long_neck_rifle_shoot", LongNeckRifleShoot);
});


function arrowDeplete(inventory, arrowSlot){
    const arrowItem = inventory.container.getItem(arrowSlot);
    if (arrowItem.amount > 1) {
        arrowItem.amount--;
        inventory.container.setItem(arrowSlot, arrowItem);
    } else {
        inventory.container.setItem(arrowSlot, undefined); // Remove item completely
    }
}

function Shoot(player, arrowType, itemStack, power) {
    const playerHeadLocation = player.getHeadLocation();
    const viewDirection = player.getViewDirection();
    const accuracy = 1;
    const bullet_speed = ShootableItem[itemStack.typeId] ?? 3; // fallback if undefined

    const spawnDistance = 2;
    const spawnLocation = {
        x: playerHeadLocation.x + viewDirection.x * spawnDistance,
        y: playerHeadLocation.y + viewDirection.y * spawnDistance,
        z: playerHeadLocation.z + viewDirection.z * spawnDistance
    };
    let projectile = null;

    switch (arrowType) {
        case "tranq":
            projectile = player.dimension.spawnEntity("terradraconis:tranq_steel_arrow", spawnLocation);
            break;
        case "steel":
            projectile = player.dimension.spawnEntity("terradraconis:steel_arrow", spawnLocation);
            break;
        default:
            projectile = player.dimension.spawnEntity("terradraconis:steel_arrow", spawnLocation);
            break;
    }

    if (projectile) {
        const spreadAmount = (1 - accuracy) * (player.isSneaking ? 0.2 : 0.5) * bullet_speed;
        const randomSpread = () => (Math.random() - 0.5) * spreadAmount * 2;

        const baseVelocity = {
            x: viewDirection.x * bullet_speed,
            y: viewDirection.y * bullet_speed,
            z: viewDirection.z * bullet_speed
        };

        const velocity = {
            x: baseVelocity.x + randomSpread(),
            y: baseVelocity.y + randomSpread(),
            z: baseVelocity.z + randomSpread()
        };

        const projectileComp = projectile.getComponent("minecraft:projectile");
        if (projectileComp) {
            projectileComp.shoot(velocity);
        }

        player.runCommandAsync(`/camerashake add @s 0.2 0.2 rotational`);
        player.runCommandAsync(`/playsound steel_crossbow_shoot @a[r=16]`);

        const shooterId = player.name; // or shooter.nameTag if you prefer
        projectile.setDynamicProperty("shooter_id", shooterId);
        projectile.setDynamicProperty("power", power);
    }
}

function Shoot2(player, arrowType, itemStack, power) {
    const playerHeadLocation = player.getHeadLocation();
    const viewDirection = player.getViewDirection();
    const bullet_speed = ShootableItem[itemStack.typeId] ?? 3; // fallback if undefined

    const spawnDistance = 2;
    const spawnLocation = {
        x: playerHeadLocation.x + viewDirection.x * spawnDistance,
        y: playerHeadLocation.y + viewDirection.y * spawnDistance,
        z: playerHeadLocation.z + viewDirection.z * spawnDistance
    };
    let projectile = null;
    let shoot_sound = null;

    switch (arrowType) {
        case "tranq":
            projectile = player.dimension.spawnEntity("terradraconis:tranq_bullet", spawnLocation);
            shoot_sound = "long_neck_rifle_shoot_tranq"
            break;
        case "steel":
            projectile = player.dimension.spawnEntity("terradraconis:steel_bullet", spawnLocation);
            shoot_sound = "long_neck_rifle_shoot"
            player.runCommandAsync(`/particle terradraconis_pa:shoot_effect ^^1^3`);
            break;
        default:
            projectile = player.dimension.spawnEntity("terradraconis:steel_bullet", spawnLocation);
            player.runCommandAsync(`/particle terradraconis_pa:shoot_effect ^^1^3`);
            shoot_sound = "long_neck_rifle_shoot"
            break;
    }

    if (projectile) {

        const baseVelocity = {
            x: viewDirection.x * bullet_speed,
            y: viewDirection.y * bullet_speed,
            z: viewDirection.z * bullet_speed
        };

        const velocity = {
            x: baseVelocity.x,
            y: baseVelocity.y,
            z: baseVelocity.z
        };

        const projectileComp = projectile.getComponent("minecraft:projectile");
        if (projectileComp) {
            projectileComp.shoot(velocity);
        }

        player.runCommandAsync(`/camerashake add @s 0.4 0.2 rotational`);
        player.runCommandAsync(`/playsound ${shoot_sound} @a[r=32]`);

        const shooterId = player.name; // or shooter.nameTag if you prefer
        projectile.setDynamicProperty("shooter_id", shooterId);
        projectile.setDynamicProperty("power", power);
    }
}


world.afterEvents.projectileHitEntity.subscribe((event) => {
    const hitInfo = event.getEntityHit();
    if (!hitInfo) return;

    const target = hitInfo.entity;
    const projectile = event.projectile;
    if (!target || !projectile) return;
    const typeFamilyComp = projectile.getComponent("minecraft:type_family");
    if (!typeFamilyComp || !typeFamilyComp.hasTypeFamily("tranq")) return;
    
    const shooterId = projectile.getDynamicProperty("shooter_id");
    target.runCommand(`/damage @s 1 entity_attack entity ${shooterId}`)
});


world.afterEvents.itemReleaseUse.subscribe((event) => {
    const { source, itemStack, useDuration } = event;
    if (!source || !itemStack) return;

    const itemTypeId = itemStack.typeId;
    const itemConfig = chargableItem[itemTypeId];
    if (!itemConfig) return;

    const maxSeconds = itemConfig.chargeTime ?? 1;
    const rawSeconds = ((200000 - useDuration) / 20) - 1;
    const clampedSeconds = Math.min(rawSeconds, maxSeconds);
    const chargeSeconds = clampedSeconds.toFixed(2);
    const chargeRatio = chargeSeconds / maxSeconds;

    const inventory = source.getComponent("minecraft:inventory");
    if (!inventory) return;

    let hasArrow = false;
    let arrowType = "";
    let arrowSlot = -1;

    for (let i = 0; i < inventory.container.size; i++) {
        const item = inventory.container.getItem(i);
        if (!item) continue;

        if (item.typeId === "terradraconis:steel_arrow_it") {
            hasArrow = true;
            arrowType = "steel";
            arrowSlot = i;
            break;
        } else if (item.typeId === "terradraconis:tranq_steel_arrow_it") {
            hasArrow = true;
            arrowType = "tranq";
            arrowSlot = i;
            break;
        }
    }

    if (!hasArrow) {
        source.sendMessage("§cNo arrows to shoot!");
        source.playSound("note.bass");
        return;
    }
    const power = itemStack.getDynamicProperty("power") ?? 100;

    shootChargedArrow(source, arrowType, chargeRatio, itemConfig.power ?? 2.5, power);

    if (source.getGameMode?.() !== "creative") {
        reduceDur(source);
        arrowDeplete(inventory, arrowSlot);
    }
});


function shootChargedArrow(player, arrowType, chargeRatio, power, powerMul) {
    const headPos = player.getHeadLocation();
    const dir = player.getViewDirection();
    const spawnDist = 2;
    const spawnLoc = {
        x: headPos.x + dir.x * spawnDist,
        y: headPos.y + dir.y * spawnDist,
        z: headPos.z + dir.z * spawnDist
    };

    const entityId = arrowType === "tranq" ? "terradraconis:tranq_steel_arrow" : "terradraconis:steel_arrow";
    const projectile = player.dimension.spawnEntity(entityId, spawnLoc);
    if (!projectile) return;

    const velocity = {
        x: dir.x * power * chargeRatio,
        y: dir.y * power * chargeRatio,
        z: dir.z * power * chargeRatio
    };

    const projectileComp = projectile.getComponent("minecraft:projectile");
    if (projectileComp) {
        projectileComp.shoot(velocity);
    }

    projectile.setDynamicProperty("shooter_id", player.name);
    projectile.setDynamicProperty("power", powerMul);
    player.runCommandAsync(`/camerashake add @s ${0.1 + 0.02 * chargeRatio} ${0.1 + 0.02 * chargeRatio} rotational`);
}

world.afterEvents.entityHurt.subscribe(event => {
    const target = event.hurtEntity;
    const source = event.damageSource?.damagingEntity;

    // === 💢 DAMAGE BOOST SYSTEM (attacker) ===
    if (source) {
        if (source.getComponent("minecraft:projectile")) {
            if (source.getDynamicProperty("power")) {
                const baseDamage = event.damage;
                const damagePercent = source.getDynamicProperty("power") ?? 100;
                const damageFactor = damagePercent / 100;

                const finalDamage = baseDamage * damageFactor;
                const extraDamage = finalDamage - baseDamage;

                if (extraDamage > 0) {
                    target.applyDamage(extraDamage);
                }
            }
        }

        if (source.typeId === "minecraft:player"){
            const equippable = source.getComponent("minecraft:equippable");
            if (!equippable) return;

            const mainhand = equippable.getEquipmentSlot(EquipmentSlot.Mainhand);
            if (!mainhand.hasItem()) return;

            if (source.getGameMode() === "creative") return;

            const itemStack = mainhand.getItem();
            const power = itemStack.getDynamicProperty("power") ?? 100;
            powerScale(event.damage, target, power);
        }
    }
});

const toolDur = {
    onMineBlock({ source }) {
        if (!(source instanceof Player)) return;
        reduceDur(source);
    },
    onHitEntity({attackingEntity}) {
        if (!(attackingEntity instanceof Player)) return;
        reduceDur(attackingEntity);
    },
    onBeforeDurabilityDamage(event) {
        event.durabilityDamage = 0;
    }
};


// Register the custom component
world.beforeEvents.worldInitialize.subscribe(({ itemComponentRegistry }) => {
    itemComponentRegistry.registerCustomComponent("terradraconis:tooldur", toolDur);
});


export function reduceDur(source){
    const equippable = source.getComponent("minecraft:equippable");
    if (!equippable) return;

    const mainhand = equippable.getEquipmentSlot(EquipmentSlot.Mainhand);
    if (!mainhand.hasItem()) return;

    if (source.getGameMode() === "creative") return;

    const itemStack = mainhand.getItem();
    const durability = itemStack.getComponent("minecraft:durability");
    if (!durability) return;

    // Get power (default 100%)
    const power = itemStack.getDynamicProperty("power") ?? 100;

    // Damage chance: 1 at power=100, 0.5 at power=200, etc.
    const damageChance = 100 / power;

    if (Math.random() > damageChance) return; // Skip damage based on chance

    durability.damage += 1;

    if (durability.damage >= durability.maxDurability) {
        mainhand.setItem(undefined); // Break
        source.playSound("random.break");
    } else {
        mainhand.setItem(itemStack); // Update item
    }
}

function powerScale(damage, target, power) {
    const baseDamage = damage;
    const damagePercent = power;
    const damageFactor = damagePercent / 100;

    const finalDamage = baseDamage * damageFactor;
    const extraDamage = finalDamage - baseDamage;

    if (extraDamage > 0) {
        target.applyDamage(extraDamage);
    }
}