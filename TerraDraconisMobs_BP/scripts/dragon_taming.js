import { system, world } from "@minecraft/server";
import { ModalFormData } from "@minecraft/server-ui";
import {
  tamingByItem,
  torporBySource,
  unconciousByItem,
} from './config.js';

system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  const typeFamily = entity.getComponent("minecraft:type_family");
  if (!entity) return;
  if (!typeFamily?.hasTypeFamily("terradraconis_dragon") || !typeFamily.hasTypeFamily("tameable_mob")) return;

  if (event.id === "terradraconis:dragon_taming") {
    const inventoryComp = entity.getComponent("minecraft:inventory");
    if (!inventoryComp) return;

    const container = inventoryComp.container;

    let taming = entity.getDynamicProperty("taming") ?? 0;
    let torpor = entity.getDynamicProperty("torpor") ?? 0;
    const maxTaming = entity.getDynamicProperty("max_taming") ?? 100;
    const maxTorpor = entity.getDynamicProperty("max_torpor") ?? 100;

    let foodConsumed = false;
    let narcoConsumed = false;

    // 🥩 1️⃣ First loop: Look for food (taming items)
    for (let i = 0; i < container.size; i++) {
      if (foodConsumed || taming >= maxTaming) break;

      const item = container.getItem(i);
      if (!item) continue;

      const tamingValue = tamingByItem[item.typeId];
      if (tamingValue === undefined) continue;

      // Apply taming
      taming = Math.min(taming + tamingValue, maxTaming);
      entity.setDynamicProperty("taming", taming);
      foodConsumed = true;

      // Play animation
      entity.runCommand("/playanimation @s faint_eat");

      // Consume item
      if (item.amount > 1) {
        item.amount -= 1;
        container.setItem(i, item);
      } else {
        container.setItem(i, undefined);
      }

      // 🐉 Taming success check
      if (taming >= maxTaming) {
        handleTamingSuccess(entity);
        return;
      }
    }

    // 💊 2️⃣ Second loop: Look for narcotic (torpor items)
    for (let i = 0; i < container.size; i++) {
      if (narcoConsumed || torpor >= maxTorpor) break;

      const item = container.getItem(i);
      if (!item) continue;

      const narcoValue = unconciousByItem[item.typeId];
      if (narcoValue === undefined) continue;

      // Apply torpor
      torpor = Math.min(torpor + narcoValue, maxTorpor);
      entity.setDynamicProperty("torpor", torpor);
      narcoConsumed = true;

      // Play animation
      entity.runCommand("/playanimation @s faint_eat");

      // Consume item
      if (item.amount > 1) {
        item.amount -= 1;
        container.setItem(i, item);
      } else {
        container.setItem(i, undefined);
      }
    }
  }


    if (event.id === "terradraconis:dragon_wake"){
      let torpor = entity.getDynamicProperty("torpor") ?? 0;
      let maxTorpor = entity.getDynamicProperty("max_torpor") ?? 1000;

      // 🔻 Reduce torpor by 5% of maxTorpor
      const torporDrain = Math.floor(maxTorpor * 0.005);
      torpor = Math.max(torpor - torporDrain, 0);
      entity.setDynamicProperty("torpor", torpor);

      // 💤 If torpor runs out
      if (torpor <= 0 && entity.getProperty("faint:property")) {
      entity.setDynamicProperty("taming", 0);
      entity.runCommandAsync("event entity @s wake"); // Replace with your custom wake-up event
      }
    }
  });

function handleTamingSuccess(entity) {
  const dimension = entity.dimension;
  const location = entity.location;
  if (!dimension || !location) return;
  spawnInventoryBag(entity);

  const propsToTransfer = [
    "max_stamina", "stamina", "exhause", "flying_speed", "max_flying_speed",
    "level", "max_level", "skill_point", "resistance", "damage", "speed",
    "max_torpor", "torpor", "max_taming", "taming", "mutation_type", "mutation_value"
  ];

  const transferredProps = {};
  for (const prop of propsToTransfer) {
    transferredProps[prop] = entity.getDynamicProperty(prop);
  }

  const newEntity = dimension.spawnEntity("terradraconis:crimson_racer", location);
  if (!newEntity) return;
  newEntity.setProperty("terradraconis:color", entity.getProperty("terradraconis:color") ?? 0);

  newEntity.setDynamicProperty("skip_autoscale", true);
  for (const [key, value] of Object.entries(transferredProps)) {
    if (value !== undefined) {
      newEntity.setDynamicProperty(key, value);
    }
  }

  newEntity.setDynamicProperty("torpor", 0); // Reset torpor
  if (entity.nameTag) newEntity.nameTag = entity.nameTag;

  const tameComp = entity.getComponent("minecraft:tameable");
  const owner = tameComp?.tamedToPlayer;
  if (owner) {
    const newTameComp = newEntity.getComponent("minecraft:tameable");
    try {
      newTameComp?.tame(owner);
    } catch (err) {
      console.warn("Failed to transfer ownership:", err);
    }
  }

  newEntity.runCommandAsync("/event entity @s adult");
  system.runTimeout(() => {
    newEntity.runCommandAsync("/playanimation @s wake");
    let level = newEntity.getDynamicProperty("level") ?? 10;
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
  }, 1);

  entity.remove();

  // Prompt naming if owner is nearby
  const dx = owner.location.x - location.x;
  const dy = owner.location.y - location.y;
  const dz = owner.location.z - location.z;
  const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (distance <= 32) {
    promptDragonNaming(owner, newEntity);
  } else {
    console.warn("⚠️ Owner too far — skipping dragon naming.");
  }
}


function spawnInventoryBag(entity) {
  const inventoryComp = entity.getComponent("minecraft:inventory");
  if (!inventoryComp) return;

  const container = inventoryComp.container;
  const dimension = entity.dimension;
  const location = entity.location;

  const bag = dimension.spawnEntity("terradraconis:lootbag", {
    x: location.x,
    y: location.y + 0.5,
    z: location.z
  });

  if (!bag) {
    console.warn("❌ Failed to spawn loot bag.");
    return;
  }

  const bagInventory = bag.getComponent("minecraft:inventory")?.container;
  if (!bagInventory) {
    console.warn("❌ Loot bag has no inventory.");
    return;
  }

  let slot = 0;

  for (let i = 0; i < container.size; i++) {
    const item = container.getItem(i);
    if (!item) continue;

    if (slot < bagInventory.size) {
      bagInventory.setItem(slot++, item);
    } else {
      dimension.spawnItem(item, {
        x: location.x + 0.5,
        y: location.y + 1,
        z: location.z + 0.5
      });
    }

    container.setItem(i, undefined);
  }

  bag.nameTag = "§6Dragon Loot Bag";
}


world.afterEvents.projectileHitEntity.subscribe((event) => {
    const hitInfo = event.getEntityHit();
    if (!hitInfo) return;

    const target = hitInfo.entity;
    const projectile = event.projectile;
    if (!target || !projectile) return;

    const typeFamilyComp = projectile.getComponent("minecraft:type_family");
    if (!typeFamilyComp || !typeFamilyComp.hasTypeFamily("tranq")) return;

    const targetFamily = target.getComponent("minecraft:type_family");
    if (!targetFamily?.hasTypeFamily("terradraconis_dragon") || !targetFamily.hasTypeFamily("tameable_mob")) return;

    const typeId = projectile.typeId;
    const torporIncrease = torporBySource[typeId];
    if (torporIncrease === undefined) return;

    const power = projectile.getDynamicProperty("power") ?? 100;
    const newTorpor = Math.floor(torporIncrease * power / 100);

    let torpor = target.getDynamicProperty("torpor") ?? 0;
    const maxTorpor = target.getDynamicProperty("max_torpor") ?? 1000;

    if (torpor < maxTorpor) {
        torpor = Math.min(torpor + newTorpor, maxTorpor);
        target.setDynamicProperty("torpor", torpor);
    }

    if (torpor >= maxTorpor) {
        target.runCommandAsync(`/event entity @s start_faint`);
    }
});



function promptDragonNaming(player, dragon) {
  const level = dragon.getDynamicProperty("level") ?? 1;

  const form = new ModalFormData()
    .title("🐉 Name Your Dragon")
    .textField("Enter a name for your dragon:", "e.g. Ember, Shadowfang");

  form.show(player).then(response => {
    if (response.canceled) {
      player.sendMessage("❌ You skipped naming your dragon.");
      exit(player)
      return;
    }

    const inputName = response.formValues[0].trim();
    if (!inputName) {
      player.sendMessage("❗Dragon name was empty. Keeping the current name.");
      exit(player)
      return;
    }

    const formattedName = `§b${inputName} Lv.${level}`;
    dragon.nameTag = formattedName;
    save(player);
    player.sendMessage(`✅ Your dragon is now named: ${formattedName}`);
  }).catch(err => {
    console.warn("Failed to show naming form:", err);
  });
  popup(player);
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