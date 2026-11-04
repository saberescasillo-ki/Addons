import { world, system } from "@minecraft/server";

// The Nether Lord calls Soul Knights now and then while players fight it: two at a
// time, up to 3 (4 once it is below half health). None of its attacks hurt them
// (their damage sensor). They crumble when their Lord dies or leaves.

const BOSS = "low:netherboss";
const KNIGHT = "netherens:soul_knight";
const OWNER = "netherens:owner";
const FIRST = 20 * 25, MIN_GAP = 20 * 30, MAX_GAP = 20 * 42;
const next = new Map(); // boss id -> tick of its next call

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);

function bosses() {
    const out = [];
    for (const id of ["overworld", "nether", "the_end"]) {
        try {
            out.push(...world.getDimension(id).getEntities({ type: BOSS }));
        } catch {
            // not loaded
        }
    }
    return out;
}

function knightsOf(boss) {
    try {
        return boss.dimension.getEntities({ type: KNIGHT, location: boss.location, maxDistance: 96 })
            .filter((k) => k.getDynamicProperty(OWNER) === boss.id);
    } catch {
        return [];
    }
}

function crumble(knight) {
    try {
        const at = knight.location;
        knight.dimension.spawnParticle("minecraft:soul_particle", { x: at.x, y: at.y + 1, z: at.z });
        knight.dimension.spawnParticle("minecraft:large_explosion", { x: at.x, y: at.y + 1, z: at.z });
        knight.remove();
    } catch {
        // gone
    }
}

function freeSpot(dim, at) {
    for (let i = 0; i < 6; i++) {
        const a = Math.random() * 2 * Math.PI, d = 2.5 + Math.random() * 2;
        const p = { x: at.x + Math.cos(a) * d, y: at.y, z: at.z + Math.sin(a) * d };
        try {
            const feet = dim.getBlock(p), head = feet?.above();
            if (feet?.isAir && head?.isAir) return p;
        } catch {
            // unloaded
        }
    }
    return { ...at };
}

function callKnights(boss) {
    const half = !!boss.getProperty("nxmberscib:half_health");
    const room = (half ? 4 : 3) - knightsOf(boss).length;
    if (room <= 0) return;
    const dim = boss.dimension, at = { ...boss.location };
    dim.playSound("mob.evocation_illager.prepare_summon", at, { volume: 2, pitch: 0.7 });
    for (let i = 0; i < Math.min(2, room); i++) {
        const p = freeSpot(dim, at);
        for (let k = 0; k < 4; k++) {
            dim.spawnParticle("minecraft:soul_particle", { x: p.x + (Math.random() - 0.5), y: p.y + Math.random() * 2, z: p.z + (Math.random() - 0.5) });
        }
        dim.spawnParticle("minecraft:blue_flame_particle", p);
        system.runTimeout(() => {
            if (!isValid(boss)) return;
            try {
                const knight = dim.spawnEntity(KNIGHT, p);
                knight.setDynamicProperty(OWNER, boss.id);
            } catch {
                // blocked
            }
        }, 20);
    }
}

system.runInterval(() => {
    const now = system.currentTick;
    const alive = new Set();
    for (const boss of bosses()) {
        if (!isValid(boss) || boss.location.y <= -60) continue; // dying (moved below the world)
        alive.add(boss.id);
        let fighting = false;
        try {
            // a player within 32 blocks (not creative/spectator) and no area attack running
            fighting = boss.dimension.getPlayers({ location: boss.location, maxDistance: 32,
                excludeGameModes: ["creative", "spectator"] }).length > 0
                && !boss.getProperty("nxmberscib:aoe_attack");
        } catch {
            fighting = false;
        }
        if (!fighting) {
            next.delete(boss.id);
            continue;
        }
        if (!next.has(boss.id)) next.set(boss.id, now + FIRST);
        if (now < next.get(boss.id)) continue;
        next.set(boss.id, now + MIN_GAP + Math.floor(Math.random() * (MAX_GAP - MIN_GAP)));
        try {
            callKnights(boss);
        } catch {
            // unloaded
        }
    }
    for (const id of ["overworld", "nether", "the_end"]) {
        let list = [];
        try {
            list = world.getDimension(id).getEntities({ type: KNIGHT });
        } catch {
            continue;
        }
        for (const k of list) {
            const owner = k.getDynamicProperty(OWNER);
            if (owner && !alive.has(owner)) crumble(k);
        }
    }
    for (const id of next.keys()) if (!alive.has(id)) next.delete(id);
}, 20);
