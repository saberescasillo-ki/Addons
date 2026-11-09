import { world, system, GameMode } from "@minecraft/server";

// The Torpendo (TEU Mobs): instead of firing a dash entity it rode, it hovers facing its
// target and every 2 seconds lunges at it; the lunge hurts once if it reaches the target.
const EVERY = 40;            // ticks between lunges
const WINDUP = 8;            // ticks of warning before the lunge
const SPEED = 1.6;           // impulse of the lunge
const DAMAGE = 7.2;          // the add-on's dash did 10: -15 %, then -15 % for every mob
const RANGE = 20;
const state = new Map();     // id -> {next, lunge, hit}

function targetOf(t) {
    try {
        const tg = t.target;
        if (tg && tg.isValid()) return tg;
    } catch {
        // no target property in this version
    }
    const ps = t.dimension.getPlayers({ location: t.location, maxDistance: RANGE,
        excludeGameModes: [GameMode.creative, GameMode.spectator] });
    let best, bd = Infinity;
    for (const p of ps) {
        const d = (p.location.x - t.location.x) ** 2 + (p.location.y - t.location.y) ** 2 + (p.location.z - t.location.z) ** 2;
        if (d < bd) {
            bd = d;
            best = p;
        }
    }
    return best;
}

system.runInterval(() => {
    const now = system.currentTick;
    for (const dim of ["overworld", "nether", "the_end"]) {
        let list = [];
        try {
            list = world.getDimension(dim).getEntities({ type: "mob:torpendo" });
        } catch {
            continue;
        }
        for (const t of list) {
            let s = state.get(t.id);
            if (!s) {
                s = { next: now + EVERY + (Math.abs(Number(t.id)) % 20 || 0), lunge: -1, hit: false, warned: false };
                state.set(t.id, s);
            }
            const tg = targetOf(t);
            if (!tg) continue;
            const a = t.location, b = tg.location;
            const dx = b.x - a.x, dy = b.y + 0.9 - (a.y + 0.6), dz = b.z - a.z;
            const len = Math.hypot(dx, dy, dz) || 1;
            try {
                t.setRotation({ x: -Math.asin(dy / len) * 57.3, y: Math.atan2(-dx, dz) * 57.3 });
            } catch {
                // ignore
            }
            if (!s.warned && now >= s.next - WINDUP) {
                s.warned = true;
                try {
                    t.dimension.playSound("mob.phantom.swoop", a, { volume: 1, pitch: 1.4 });
                    t.runCommand("playanimation @s animation.torpendo.dash");
                } catch {
                    // ignore
                }
            }
            if (now >= s.next) {
                s.next = now + EVERY;
                s.warned = false;
                s.lunge = now;
                s.hit = false;
                try {
                    t.applyImpulse({ x: dx / len * SPEED, y: dy / len * SPEED, z: dz / len * SPEED });
                } catch {
                    // ignore
                }
            }
            if (!s.hit && s.lunge >= 0 && now - s.lunge <= 12 && len < 2.2) {
                s.hit = true;
                try {
                    tg.applyDamage(DAMAGE, { cause: "entityAttack", damagingEntity: t });
                    tg.applyKnockback(dx / len, dz / len, 1.2, 0.35);
                } catch {
                    // ignore
                }
            }
        }
    }
    if (now % 600 === 0) {
        for (const [id, s] of state) if (now - s.next > 1200) state.delete(id);
    }
}, 2);
