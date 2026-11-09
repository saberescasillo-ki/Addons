import { world, system, GameMode } from "@minecraft/server";

// TEU Mobs: one new attack per boss, with a warning before it lands. Every boss uses it
// every COOLDOWN ticks while a player is within RANGE blocks. Vanilla particles only.
const COOLDOWN = 280, RANGE = 24;
const next = new Map();

const P = (dim, id, at) => {
    try {
        dim.spawnParticle(id, at);
    } catch {
        // unloaded
    }
};
const hurt = (p, n, boss) => {
    try {
        p.applyDamage(n, { cause: "entityAttack", damagingEntity: boss });
    } catch {
        // gone
    }
};
const effect = (p, id, s, amp = 0) => {
    try {
        p.addEffect(id, Math.round(s * 20), { amplifier: amp, showParticles: false });
    } catch {
        // gone
    }
};
const later = (ticks, fn) => system.runTimeout(() => {
    try {
        fn();
    } catch {
        // the boss or the players left
    }
}, ticks);
const dist2 = (a, b) => (a.x - b.x) ** 2 + (a.z - b.z) ** 2;
const ground = (p) => {
    try {
        return p.isOnGround;
    } catch {
        return true;
    }
};

function players(boss, r = RANGE) {
    return boss.dimension.getPlayers({ location: boss.location, maxDistance: r,
        excludeGameModes: [GameMode.creative, GameMode.spectator] });
}

function ring(dim, c, r, id, n = 16) {
    for (let k = 0; k < n; k++) {
        const a = k / n * Math.PI * 2;
        P(dim, id, { x: c.x + r * Math.cos(a), y: c.y + 0.2, z: c.z + r * Math.sin(a) });
    }
}

function spotsAround(ps, extra, spread) {
    const out = ps.map((p) => ({ ...p.location }));
    for (let i = 0; i < extra; i++) {
        const b = ps[i % ps.length].location;
        out.push({ x: b.x + (Math.random() - 0.5) * spread, y: b.y, z: b.z + (Math.random() - 0.5) * spread });
    }
    return out;
}

// marked spots that go off after a warning
function delayedSpots(boss, spots, warnId, warnR, hitId, hitR, onHit) {
    const dim = boss.dimension;
    for (let t = 0; t < 30; t += 6) later(t, () => spots.forEach((s) => ring(dim, s, warnR, warnId, 10)));
    later(32, () => {
        for (const s of spots) {
            P(dim, hitId, { x: s.x, y: s.y + 0.5, z: s.z });
            for (const p of players(boss, RANGE + 8)) if (dist2(p.location, s) <= hitR * hitR) onHit(p);
        }
    });
}

const ATTACKS = {
    // the garden: roots burst out under you
    "boss:floral_amalgam": (boss, ps) => delayedSpots(boss, spotsAround(ps, 4, 10), "minecraft:villager_happy", 1.5,
        "minecraft:totem_particle", 1.8, (p) => {
            hurt(p, 6, boss);
            effect(p, "slowness", 3, 1);
        }),
    // the whirlpool: pulls everyone to the wyrm, then bites
    "boss:primordial_wyrm": (boss) => {
        for (let t = 0; t < 60; t += 4) {
            later(t, () => {
                const c = boss.location;
                ring(boss.dimension, c, 3 + (t % 12) / 2, "minecraft:basic_bubble_particle", 14);
                for (const p of players(boss, 16)) {
                    const dx = c.x - p.location.x, dz = c.z - p.location.z, l = Math.hypot(dx, dz) || 1;
                    try {
                        p.applyKnockback(dx / l, dz / l, 0.35, 0.02);
                    } catch {
                        // ignore
                    }
                }
            });
        }
        later(62, () => {
            for (const p of players(boss, 4)) hurt(p, 5, boss);
        });
    },
    // forge meteors: burning spots round the players
    "boss:pyrogen": (boss, ps) => delayedSpots(boss, spotsAround(ps, 5, 12), "minecraft:lava_particle", 1.6,
        "minecraft:huge_explosion_emitter", 2.5, (p) => {
            hurt(p, 7, boss);
            try {
                p.setOnFire(3, true);
            } catch {
                // ignore
            }
        }),
    // sculk pulse: three waves that grow from the boss; jump over them
    "boss:sculk_boss": (boss) => {
        const c = { ...boss.location };
        [4, 8, 12].forEach((r, i) => {
            later(i * 10, () => ring(boss.dimension, c, r, "minecraft:sculk_soul_particle", 8 + r * 3));
            later(i * 10 + 12, () => {
                ring(boss.dimension, c, r, "minecraft:sonic_explosion", 6);
                for (const p of players(boss, 16)) {
                    if (ground(p) && Math.abs(Math.sqrt(dist2(p.location, c)) - r) < 1.3) {
                        hurt(p, 6, boss);
                        effect(p, "darkness", 3);
                    }
                }
            });
        });
    },
    // gravitational eclipse: everyone floats up, then is slammed down
    "boss:astrageldon": (boss, ps) => {
        for (const p of ps) {
            effect(p, "levitation", 1.5, 2);
            ring(boss.dimension, p.location, 1.2, "minecraft:endrod", 12);
        }
        later(32, () => {
            for (const p of players(boss)) {
                try {
                    p.applyKnockback(0, 0, 0, -2.5);
                } catch {
                    // ignore
                }
                P(boss.dimension, "minecraft:totem_particle", p.location);
            }
        });
        later(42, () => {
            for (const p of players(boss)) hurt(p, 5, boss);
        });
    },
    // radioactive rain: toxic spots
    "boss:irradiated_ghast": (boss, ps) => delayedSpots(boss, spotsAround(ps, 7, 14), "minecraft:electric_spark_particle", 2,
        "minecraft:villager_happy", 2, (p) => {
            hurt(p, 4, boss);
            effect(p, "poison", 4);
        }),
    // gaze of the void: a beam aimed where you stood
    "boss:sightful_obelisk_of_ender": (boss, ps) => {
        const from = { x: boss.location.x, y: boss.location.y + 6, z: boss.location.z };
        const lines = ps.map((p) => ({ x: p.location.x, y: p.location.y + 1, z: p.location.z }));
        const draw = (id) => lines.forEach((to) => {
            const n = Math.ceil(Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z) * 1.5);
            for (let k = 0; k <= n; k++) {
                const t = k / n;
                P(boss.dimension, id, { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t,
                    z: from.z + (to.z - from.z) * t });
            }
        });
        for (let t = 0; t < 24; t += 6) later(t, () => draw("minecraft:endrod"));
        later(26, () => {
            draw("minecraft:dragon_breath_trail");
            for (const p of players(boss, RANGE + 8)) {
                for (const to of lines) {
                    // distance from the player to the beam
                    const vx = to.x - from.x, vy = to.y - from.y, vz = to.z - from.z;
                    const wx = p.location.x - from.x, wy = p.location.y + 1 - from.y, wz = p.location.z - from.z;
                    const t = Math.max(0, Math.min(1, (wx * vx + wy * vy + wz * vz) / (vx * vx + vy * vy + vz * vz || 1)));
                    const d = Math.hypot(wx - vx * t, wy - vy * t, wz - vz * t);
                    if (d < 1.6) {
                        hurt(p, 8, boss);
                        break;
                    }
                }
            }
        });
    },
    // void rifts: three rifts round you collapse into one point
    "boss:void_pope": (boss, ps) => {
        for (const p of ps) {
            const c = { ...p.location };
            for (let t = 0; t < 26; t += 4) {
                later(t, () => {
                    const r = 4 - t / 8;
                    for (let k = 0; k < 3; k++) {
                        const a = k * 2.094 + t / 6;
                        P(boss.dimension, "minecraft:dragon_breath_trail", { x: c.x + r * Math.cos(a), y: c.y + 1, z: c.z + r * Math.sin(a) });
                    }
                });
            }
            later(28, () => {
                P(boss.dimension, "minecraft:huge_explosion_emitter", c);
                for (const q of players(boss, RANGE + 8)) {
                    if (dist2(q.location, c) <= 6.25) {
                        hurt(q, 6, boss);
                        effect(q, "blindness", 2);
                    }
                }
            });
        }
    },
};

system.runInterval(() => {
    const now = system.currentTick;
    for (const dim of ["overworld", "nether", "the_end"]) {
        for (const [type, attack] of Object.entries(ATTACKS)) {
            let bosses = [];
            try {
                bosses = world.getDimension(dim).getEntities({ type });
            } catch {
                continue;
            }
            for (const b of bosses) {
                const t = next.get(b.id);
                if (t === undefined) {
                    next.set(b.id, now + 120);
                    continue;
                }
                if (now < t) continue;
                const ps = players(b);
                if (!ps.length) continue;
                next.set(b.id, now + COOLDOWN + Math.floor(Math.random() * 80));
                try {
                    attack(b, ps);
                } catch {
                    // ignore
                }
            }
        }
    }
    if (now % 1200 === 0) for (const [id, t] of next) if (now - t > 6000) next.delete(id);
}, 20);
