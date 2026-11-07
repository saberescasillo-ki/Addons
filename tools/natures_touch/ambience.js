import { world, system } from "@minecraft/server";

// Nature's Touch (optimised): the biome ambience and the wind.
//  * Ambience: tick.json used to summon mechanic:biome_ambience_tcf above a random
//    player EVERY tick (20 entities a second, everywhere) only to show the Pale
//    Garden haze. Now one every AMBIENCE_EVERY ticks per player in the Overworld; its
//    particle emits AMBIENCE_EVERY times more, so the haze looks the same.
//  * Wind: mechanic:wind_noise used to spawn naturally as a monster all over the
//    Overworld (and 100 out of 101 vanished at once). Now, on the surface, a gust now
//    and then: about once every WIND_SECONDS seconds per player.

const AMBIENCE_EVERY = 10;
const WIND_SECONDS = 60;

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

system.runInterval(() => {
    for (const p of world.getAllPlayers()) {
        try {
            if (p.dimension.id !== "minecraft:overworld" || p.location.y < 58) continue;
            if (Math.random() >= 1 / WIND_SECONDS) continue;
            p.playSound("wind_effect");
            p.dimension.spawnParticle("windeffect", p.location);
        } catch {
            // ignore
        }
    }
}, 20);
