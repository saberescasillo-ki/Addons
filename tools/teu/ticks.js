import { world, system, EquipmentSlot } from "@minecraft/server";

// The Everything Update summoned two entities from tick.json:
//   * mechanic:equipment_commands next to EVERY player EVERY tick, whose entity sensor
//     looked at the player's armour, hands and the block they stand in, and ran
//     commands for what it found;
//   * mechanic:biome_ambience_tif next to a random player every tick, 4 out of 5
//     of them removed again at once (biome particles and fogs).
// This does the first one directly (same checks, same commands, every tick, no entity)
// and the second one every few ticks, keeping only the ambience entities that did work.

const SENSORS = __SENSORS__; // [{f: entity filter, fn: function to run as the player}]
const ALWAYS = "__ALWAYS__"; // what every equipment entity ran when it appeared
const AMBIENCE_EVERY = __AMBIENCE_EVERY__;

const SLOTS = {
    head: [EquipmentSlot.Head],
    torso: [EquipmentSlot.Chest],
    leg: [EquipmentSlot.Legs],
    feet: [EquipmentSlot.Feet],
    hand: [EquipmentSlot.Mainhand, EquipmentSlot.Offhand],
    any: [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet, EquipmentSlot.Mainhand,
        EquipmentSlot.Offhand],
};
const full = (id) => (id.includes(":") ? id : `minecraft:${id}`);

function test(f, ctx) {
    if (Array.isArray(f)) return f.every((x) => test(x, ctx));
    if (f.all_of) return f.all_of.every((x) => test(x, ctx));
    if (f.any_of) return f.any_of.some((x) => test(x, ctx));
    if (f.none_of) return !f.none_of.some((x) => test(x, ctx));
    let r;
    switch (f.test) {
        case "is_family":
            r = f.value === "player";
            break;
        case "has_equipment":
            r = (SLOTS[f.domain ?? "any"] ?? SLOTS.any).some((s) => ctx.eq(s) === full(f.value));
            break;
        case "in_block":
            r = ctx.block() === full(f.value);
            break;
        default:
            r = false;
    }
    const op = f.operator ?? "==";
    return op === "==" || op === "=" || op === "equals" ? r : !r;
}

function run(p, fn) {
    try {
        p.runCommand(`function ${fn}`);
    } catch {
        // the player left or the chunk is not ready
    }
}

system.runInterval(() => {
    for (const p of world.getAllPlayers()) {
        let equippable, items = {}, block;
        const ctx = {
            eq(slot) {
                if (!(slot in items)) {
                    try {
                        equippable ??= p.getComponent("minecraft:equippable");
                        items[slot] = equippable?.getEquipment(slot)?.typeId;
                    } catch {
                        items[slot] = undefined;
                    }
                }
                return items[slot];
            },
            block() {
                if (block === undefined) {
                    try {
                        block = p.dimension.getBlock(p.location)?.typeId ?? null;
                    } catch {
                        block = null;
                    }
                }
                return block;
            },
        };
        run(p, ALWAYS);
        for (const s of SENSORS) if (test(s.f, ctx)) run(p, s.fn);
    }
}, 1);

system.runInterval(() => {
    const players = world.getAllPlayers();
    if (!players.length) return;
    const p = players[Math.floor(Math.random() * players.length)];
    try {
        p.runCommand("summon mechanic:biome_ambience_tif ^^^0.2");
    } catch {
        // ignore
    }
}, AMBIENCE_EVERY);
