import { system } from "@minecraft/server";

// The seals at the heart of each boss's structure. The first time a player comes
// near, the seal raises the boss's dormant statue (touching the statue starts the
// fight, as in the original). Once used, touching the seal raises it again, if no
// statue or boss is around.

const SEALS = {
    "xrworks:baron_seal": { statue: "xrworks:blackbaron_dummy_standby", boss: "xrworks:blackbaron",
        sound: "ambient.weather.thunder", particle: "minecraft:electric_spark_particle" },
    "xrworks:lantern_seal": { statue: "xrworks:doctor_lantern_dummy_standby", boss: "xrworks:doctor_lantern",
        sound: "mob.warden.nearby_closer", particle: "minecraft:basic_flame_particle" },
};

function present(dim, loc, types, radius) {
    try {
        return types.some((type) => dim.getEntities({ type, location: loc, maxDistance: radius }).length > 0);
    } catch {
        return true;
    }
}

function raise(block, seal) {
    const dim = block.dimension;
    const c = block.center();
    const at = { x: c.x, y: block.location.y + 1, z: c.z };
    if (present(dim, at, [seal.statue, seal.boss, seal.statue.replace("standby", "spawn")], 48)) return false;
    try {
        dim.spawnEntity(seal.statue, at);
        dim.playSound(seal.sound, at, { volume: 2, pitch: 0.6 });
        for (let i = 0; i < 12; i++) {
            dim.spawnParticle(seal.particle, { x: at.x + (Math.random() - 0.5) * 2, y: at.y + Math.random() * 3, z: at.z + (Math.random() - 0.5) * 2 });
        }
        return true;
    } catch {
        return false;
    }
}

function component(seal) {
    return {
        onTick({ block }) {
            if (block.permutation.getState("xrworks:used")) return;
            const near = block.dimension.getPlayers({ location: block.center(), maxDistance: 28 })
                .some((p) => ["survival", "adventure"].includes(p.getGameMode().toLowerCase()));
            if (!near) return;
            if (raise(block, seal) || present(block.dimension, block.center(), [seal.statue, seal.boss], 48)) {
                block.setPermutation(block.permutation.withState("xrworks:used", true));
            }
        },
        onPlayerInteract({ block, player }) {
            system.run(() => {
                if (!raise(block, seal)) player.onScreenDisplay.setActionBar("§7El sello ya está despierto.");
                else if (!block.permutation.getState("xrworks:used")) {
                    block.setPermutation(block.permutation.withState("xrworks:used", true));
                }
            });
        },
    };
}

system.beforeEvents.startup.subscribe(({ blockComponentRegistry }) => {
    blockComponentRegistry.registerCustomComponent("xrworks:baron_seal", component(SEALS["xrworks:baron_seal"]));
    blockComponentRegistry.registerCustomComponent("xrworks:lantern_seal", component(SEALS["xrworks:lantern_seal"]));
});
