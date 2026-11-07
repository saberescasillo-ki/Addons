import { world, system } from "@minecraft/server";

// Nature's Touch (optimised): the biome ambience.
// tick.json used to summon mechanic:biome_ambience_tcf above a random player EVERY tick
// (20 entities a second, everywhere) only to show the Pale Garden haze. Now one every
// AMBIENCE_EVERY ticks per player in the Overworld; its particle emits AMBIENCE_EVERY
// times more, so the haze looks the same. (The wind is gone altogether.)

const AMBIENCE_EVERY = 10;

system.runInterval(() => {
    for (const p of world.getAllPlayers()) {
        try {
            if (p.dimension.id !== "minecraft:overworld") continue;
            const l = p.location;
            p.dimension.spawnEntity("mechanic:biome_ambience_tcf", { x: l.x, y: l.y + 7, z: l.z });
        } catch {
            // ignore
        }
    }
}, AMBIENCE_EVERY);
