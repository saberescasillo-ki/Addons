import { system, world } from "@minecraft/server";
//Taming Setup || Can change and update this session
export const tamingByItem = {
  "minecraft:porkchop": 200,
  "minecraft:chicken": 10,
  "minecraft:beef": 20,
  "minecraft:mutton": 50,
  "minecraft:salmon": 10,
  "minecraft:cod": 10,
  "minecraft:cooked_porkchop": 10,
  "minecraft:cooked_chicken": 5,
  "minecraft:cooked_beef": 10,
  "minecraft:cooked_mutton": 25,
  "minecraft:cooked_salmon": 5,
  "minecraft:cooked_cod": 5
};

export const unconciousByItem = {
  "terradraconis:narcotic": 120,
};
export const torporBySource = {
    "terradraconis:tranq_steel_arrow": 120,
    "terradraconis:tranq_bullet": 520
};
//World Setup || Do Not Changing Any Things Here
export const defaultWorldProperties = {
  max_level_entity: 10,
  wild_spawn_curve: 0.8,
  wild_spawn_bias: 0.1,
  mutation_min: 1.1,
  mutation_max: 1.5,
  mutation_chance: 0.2
};

world.afterEvents.playerSpawn.subscribe((event) => {
    const player = event.player;
    for (const [key, value] of Object.entries(defaultWorldProperties)) {
        const existing = world.getDynamicProperty(key);
        if (existing === undefined) {
            world.setDynamicProperty(key, value);
        }
    }
});

export const mutationTypes = [ "speed", "damage", "resistance", "stamina" ];

//Weapon And Workbench Setup || Can change and update this session
export const chargableItem = {
  "steel_long_bow:bow": {
    chargeTime: 1.2,
    power: 5
  },
};

export const ShootableItem = {
  "steel_crossbow:bow": 7,
  "long_neck_rifle:bow": 12
};
