import { system, EquipmentSlot } from "@minecraft/server";
import { C, ring, disc, burst, charge, column, beam, sound, shake } from "./fx.js";

// The Altar of the Eclipse: touching it starts a 5-second ritual, then the Eclipse
// descends. Touching it with lapis lazuli in hand calls the blue Eclipse instead.
// The arena is the circle of radius 22 around the altar.

const ALTAR = "eclipse:altar";
const BOSS = "eclipse:eclipse", AZURE = "eclipse:azure";
const RITUAL = 100;

export function setAltar(dim, pos, active) {
    try {
        const b = dim.getBlock(pos);
        if (b?.typeId === ALTAR) b.setPermutation(b.permutation.withState("eclipse:active", active));
    } catch {
        // unloaded: the altar notices next time it is touched
    }
}

function bossNear(dim, at) {
    try {
        return [BOSS, AZURE].some((type) => dim.getEntities({ type, location: at, maxDistance: 96 }).length > 0);
    } catch {
        return true;
    }
}

function ritual(block, player, type = BOSS) {
    const blue = type === AZURE;
    const dim = block.dimension;
    const pos = { ...block.location };
    const c = { x: pos.x + 0.5, y: pos.y, z: pos.z + 0.5 };
    setAltar(dim, pos, true);
    sound(dim, "block.end_portal.spawn", c, 1.5, 0.7);
    for (const p of dim.getPlayers({ location: c, maxDistance: 64 })) {
        p.onScreenDisplay.setTitle(blue ? "§9§l✦ EL ECLIPSE AZUL ✦" : "§f§l✦ §8EL ECLIPSE §f✦",
            { subtitle: blue ? "§bEl cielo se vuelve de cristal..." : "§7El cielo se oscurece...",
            fadeInDuration: 10, stayDuration: 60, fadeOutDuration: 20 });
    }
    for (let t = 0; t < RITUAL; t += 10) {
        system.runTimeout(() => {
            const k = t / 10;
            const ang = (k / 8) * 2 * Math.PI;
            const g = { x: c.x + Math.cos(ang) * 7, y: c.y + 0.06, z: c.z + Math.sin(ang) * 7 };
            beam(dim, g, C.white, 24, 0.5);
            burst(dim, { ...g, y: g.y + 0.3 }, C.gold, 10, 3);
            if (k === 0) ring(dim, { ...c, y: c.y + 0.06 }, 7, C.gold, RITUAL / 20);
            charge(dim, { x: c.x, y: c.y + 4, z: c.z }, blue ? C.azure : C.violet, 3 + k * 0.4, 0.5, 24);
            sound(dim, "note.bell", c, 1.5, 0.5 + k * 0.08);
        }, t);
    }
    system.runTimeout(() => shake(dim, c, 40, 0.15, 3), 40);
    system.runTimeout(() => {
        try {
            const at = { x: c.x, y: c.y + 0.4, z: c.z - 6 };
            const tone = blue ? C.azure : C.violet;
            const boss = dim.spawnEntity(type, at);
            boss.setDynamicProperty("eclipse:arena", JSON.stringify({ cx: c.x, cz: c.z, floor: pos.y, R: 22,
                ax: pos.x, ay: pos.y, az: pos.z }));
            beam(dim, { x: at.x, y: c.y, z: at.z }, tone, 40, 1.6);
            burst(dim, { x: at.x, y: at.y + 1, z: at.z }, C.white, 50, 8);
            disc(dim, { x: at.x, y: c.y + 0.06, z: at.z }, 1, tone, 1.2, { speed: 6, max: 5 });
            column(dim, { x: at.x, y: c.y + 0.06, z: at.z }, tone, 1, 10, 0.8, 0.4);
            sound(dim, "mob.wither.spawn", at, 2, 1.4);
        } catch {
            setAltar(dim, pos, false);
        }
    }, RITUAL);
}

system.beforeEvents.startup.subscribe(({ blockComponentRegistry }) => {
    blockComponentRegistry.registerCustomComponent("eclipse:altar", {
        onPlayerInteract({ block, player }) {
            if (!block || !player) return;
            system.run(() => {
                const center = block.center();
                const awake = bossNear(block.dimension, center);
                if (block.permutation.getState("eclipse:active")) {
                    if (awake) player.onScreenDisplay.setActionBar("§5El Eclipse ya está aquí.");
                    else setAltar(block.dimension, block.location, false); // left lit (world closed mid-fight)
                    return;
                }
                if (awake) {
                    player.onScreenDisplay.setActionBar("§5El Eclipse ya está aquí.");
                    return;
                }
                let hand;
                try {
                    hand = player.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand)?.typeId;
                } catch {
                    hand = undefined;
                }
                ritual(block, player, hand === "minecraft:lapis_lazuli" ? AZURE : BOSS);
            });
        },
    });
});
