import { world, BlockPermutation } from "@minecraft/server";

// Nature's Touch (optimised): on each random tick, the fruit leaves, berry bushes,
// crops and petal leaves used to summon a short-lived entity that did one small job
// and vanished. The same jobs, with the same chances, done here directly: no entity.

const FRUIT = {
    "mob:apple_orchard_leaves": "block:apple", "mob:orange_orchard_leaves": "block:orange",
    "mob:lime_orchard_leaves": "block:lime", "mob:lemon_orchard_leaves": "block:lemon",
    "mob:pear_orchard_leaves": "block:pear", "mob:durian_orchard_leaves": "block:durian",
    "mob:banana_orchard_leaves": "block:banana",
};
const FRUIT_CHANCE = 1 / 31;           // the entity's randomize: 30 nothing, 1 fruit
const PETALS = {
    "mob:cassia_leaves": "yellowpetals", "mob:crape_myrtle_leaves": "redpetals",
    "mob:white_cherry_leaves": "white_cherry_leaves", "mob:pale_flower": "resinspores",
};
const FUNCTIONS = {
    "mob:gooseberry_bush": "gooseberrybush", "mob:blueberry_bush": "blueberrybush",
    "mob:yew_berry_bush": "yewberrybush", "mob:fireeye_bush": "fireeye",
};
const GROW_CHANCE = 1 / 8;             // the crop entity's randomize: 7 nothing, 1 grow
// one stage up (the crop entity's fill commands)
const GROW = {
    "block:cotton_plant_1": "block:cotton_plant_2", "block:cotton_plant_2": "block:cotton_plant_3",
    "block:coffee_plant_1": "block:coffee_plant_2", "block:coffee_plant_2": "block:coffee_plant_3",
    "block:lettuce_1": "block:lettuce_2", "block:lettuce_2": "block:lettuce_3",
    "block:vanilla_plant_1": "block:vanilla_plant_2", "block:vanilla_plant_2": "block:vanilla_plant_3",
    "block:blueberry_1": "block:blueberry_2", "block:blueberry_2": "block:blueberry_bush",
    "block:gooseberry_1": "block:gooseberry_2", "block:gooseberry_2": "block:gooseberry_bush",
    "block:yew_berry_1": "block:yew_berry_2", "block:yew_berry_2": "block:yew_berry_bush",
};

const isDay = () => {
    const t = world.getTimeOfDay();
    return t < 12000 || t >= 23500;
};

function run(dim, at, command) {
    const full = `execute positioned ${at.x} ${at.y} ${at.z} run ${command}`;
    try {
        if (typeof dim.runCommand === "function") dim.runCommand(full);
        else dim.runCommandAsync(full);
    } catch {
        // nothing to do there
    }
}

export function natureTick(block, kind) {
    const dim = block.dimension;
    const overworld = dim.id === "minecraft:overworld";
    try {
        if (FRUIT[kind]) {
            if (!overworld || Math.random() >= FRUIT_CHANCE) return;
            const l = block.location;
            const below = dim.getBlock({ x: l.x, y: l.y - 2, z: l.z });
            if (below && below.isAir) below.setPermutation(BlockPermutation.resolve(FRUIT[kind], { "minecraft:block_face": "up" }));
        } else if (kind === "mob:crop_growth_nt") {
            if (!overworld || Math.random() >= GROW_CHANCE) return;
            const next = GROW[block.typeId];
            if (next) block.setPermutation(BlockPermutation.resolve(next));
        } else if (PETALS[kind]) {
            dim.spawnParticle(PETALS[kind], block.center());
        } else if (FUNCTIONS[kind]) {
            if (kind === "mob:fireeye_bush" && isDay()) return;   // it only glows at night
            run(dim, block.center(), `function ${FUNCTIONS[kind]}`);
        }
    } catch {
        // unloaded or replaced meanwhile
    }
}
