import { world, system, EquipmentSlot } from "@minecraft/server";

// Boss compasses (TEU Mobs). Each boss arena is generated where the same formula as its
// feature rule puts it: one per region of REGION x REGION chunks, in its own quarter of
// the region. Holding a compass shows the way to the nearest arena of its boss.
const REGION = __REGION__, QUARTER = __QUARTER__, SPAN = __SPAN__, MARGIN = __MARGIN__, OFFSET = __OFFSET__;
const END_SKIP = __END_SKIP__;
const ARENAS = __ARENAS__; // item -> {label, dim, k1, k2, qx, qz, cx, cz, y}

const mod = (a, n) => ((a % n) + n) % n;

function arenaIn(a, rx, rz) {
    const ox = mod(rx * 37 + rz * 91 + a.k1 + OFFSET, SPAN) + MARGIN + a.qx;
    const oz = mod(rx * 71 + rz * 29 + a.k2 + OFFSET, SPAN) + MARGIN + a.qz;
    const x = (rx * REGION + ox) * 16, z = (rz * REGION + oz) * 16;
    if (a.dim === "minecraft:the_end" && Math.abs(x) <= END_SKIP && Math.abs(z) <= END_SKIP) return undefined;
    return { x: x + a.cx, y: a.y, z: z + a.cz };
}

function nearest(a, loc) {
    const rx0 = Math.floor(loc.x / 16 / REGION), rz0 = Math.floor(loc.z / 16 / REGION);
    let best, bd = Infinity;
    for (let rx = rx0 - 1; rx <= rx0 + 1; rx++) {
        for (let rz = rz0 - 1; rz <= rz0 + 1; rz++) {
            const p = arenaIn(a, rx, rz);
            if (!p) continue;
            const d = Math.hypot(p.x - loc.x, p.z - loc.z);
            if (d < bd) {
                bd = d;
                best = p;
            }
        }
    }
    return best;
}

const DIMS = { "minecraft:overworld": "el Overworld", "minecraft:nether": "el Nether", "minecraft:the_end": "el End" };
const ARROWS = ["↑ adelante", "↗ adelante a la derecha", "→ a la derecha", "↘ atrás a la derecha", "↓ atrás",
    "↙ atrás a la izquierda", "← a la izquierda", "↖ adelante a la izquierda"];

function guide(p, a) {
    if (p.dimension.id !== a.dim) return `§e${a.label}§r: está en ${DIMS[a.dim]}`;
    const t = nearest(a, p.location);
    if (!t) return `§e${a.label}§r: no hay ninguno cerca`;
    const dx = t.x - p.location.x, dz = t.z - p.location.z;
    const dist = Math.round(Math.hypot(dx, dz));
    if (dist < 12) return `§e${a.label}§r: §aestás encima de su arena§r (Y ${t.y})`;
    const want = Math.atan2(-dx, dz) * 180 / Math.PI;
    const diff = mod(want - p.getRotation().y + 22.5, 360);
    const dy = t.y - Math.floor(p.location.y);
    const height = Math.abs(dy) < 6 ? "" : dy < 0 ? ` · ${-dy} bloques más abajo` : ` · ${dy} bloques más arriba`;
    return `§e${a.label}§r: ${ARROWS[Math.floor(diff / 45) % 8]} · ${dist} bloques${height}`;
}

system.runInterval(() => {
    for (const p of world.getAllPlayers()) {
        let item;
        try {
            item = p.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand);
        } catch {
            continue;
        }
        const a = item && ARENAS[item.typeId];
        if (!a) continue;
        try {
            p.onScreenDisplay.setActionBar(guide(p, a));
        } catch {
            // ignore
        }
    }
}, 10);
