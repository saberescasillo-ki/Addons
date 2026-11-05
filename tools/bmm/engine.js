import { world, system, EquipmentSlot, GameMode } from "@minecraft/server";
import { ITEMS, BLOCKS, GEAR, GEAR_EVENTS } from "./data.js";

// Blook's More Mob Mod on today's Minecraft. The add-on was made with the
// "Holiday Creator Features" (item and block events, removed from the game):
// this script plays those events again from the data the converter extracted
// (data.js), and replaces the player's per-tick equipment bonus system.

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const creative = (p) => {
    try {
        const m = p.getGameMode();
        return m === GameMode.Creative || m === GameMode.creative;
    } catch {
        return false;
    }
};

// --- A small Molang evaluator (the expressions the add-on's events use) ----------
function tokenize(src) {
    const out = [];
    const re = /\s*(?:(\d+\.?\d*|\.\d+)|('[^']*')|([A-Za-z_][\w.]*)|(&&|\|\||==|!=|<=|>=|[-+*/!<>?:(),]))/y;
    let m;
    re.lastIndex = 0;
    while (re.lastIndex < src.length && (m = re.exec(src))) {
        if (m[1] !== undefined) out.push({ t: "num", v: parseFloat(m[1]) });
        else if (m[2] !== undefined) out.push({ t: "str", v: m[2].slice(1, -1) });
        else if (m[3] !== undefined) out.push({ t: "id", v: m[3] });
        else out.push({ t: "op", v: m[4] });
        if (m[0] === "") break;
    }
    return out;
}

function evaluate(src, ctx) {
    if (typeof src !== "string") return src;
    const toks = tokenize(src.replace(/;\s*$/, ""));
    let i = 0;
    const peek = () => toks[i], next = () => toks[i++];
    const isOp = (v) => peek()?.t === "op" && peek().v === v;
    const num = (x) => (typeof x === "boolean" ? (x ? 1 : 0) : typeof x === "number" ? x : x ? 1 : 0);
    function primary() {
        const t = next();
        if (!t) return 0;
        if (t.t === "num") return t.v;
        if (t.t === "str") return t.v;
        if (t.t === "op" && t.v === "(") {
            const v = ternary();
            if (isOp(")")) next();
            return v;
        }
        if (t.t === "op" && t.v === "!") return !num(unary());
        if (t.t === "op" && t.v === "-") return -num(unary());
        if (t.t === "id") {
            const name = t.v.toLowerCase();
            if (name === "true") return true;
            if (name === "false") return false;
            const args = [];
            if (isOp("(")) {
                next();
                while (peek() && !isOp(")")) {
                    args.push(ternary());
                    if (isOp(",")) next();
                }
                next();
            }
            return query(name.replace(/^(query|q|math)\./, ""), args, ctx);
        }
        return 0;
    }
    function unary() {
        if (isOp("!")) { next(); return !num(unary()); }
        if (isOp("-")) { next(); return -num(unary()); }
        return primary();
    }
    function bin(sub, ops, fn) {
        return () => {
            let l = sub();
            while (peek()?.t === "op" && ops.includes(peek().v)) {
                const op = next().v;
                l = fn(op, l, sub());
            }
            return l;
        };
    }
    const mul = bin(unary, ["*", "/"], (o, a, b) => (o === "*" ? num(a) * num(b) : num(a) / num(b)));
    const add = bin(mul, ["+", "-"], (o, a, b) => (o === "+" ? num(a) + num(b) : num(a) - num(b)));
    const cmp = bin(add, ["<", ">", "<=", ">="], (o, a, b) =>
        o === "<" ? num(a) < num(b) : o === ">" ? num(a) > num(b) : o === "<=" ? num(a) <= num(b) : num(a) >= num(b));
    const eq = bin(cmp, ["==", "!="], (o, a, b) => {
        const same = typeof a === "string" || typeof b === "string" ? a === b : num(a) === num(b);
        return o === "==" ? same : !same;
    });
    const and = bin(eq, ["&&"], (o, a, b) => !!(num(a) && num(b)));
    const or = bin(and, ["||"], (o, a, b) => !!(num(a) || num(b)));
    function ternary() {
        const c = or();
        if (isOp("?")) {
            next();
            const a = ternary();
            if (isOp(":")) next();
            const b = ternary();
            return num(c) ? a : b;
        }
        return c;
    }
    try {
        return ternary();
    } catch {
        return 0;
    }
}

function facing2d(player) {
    // query.cardinal_facing_2d: 2 north, 3 south, 4 west, 5 east
    const y = ((player?.getRotation().y ?? 0) % 360 + 360) % 360;
    if (y >= 315 || y < 45) return 3;
    if (y < 135) return 4;
    if (y < 225) return 2;
    return 5;
}

const FACES = { Down: 0, Up: 1, North: 2, South: 3, West: 4, East: 5 };

function query(name, args, ctx) {
    switch (name) {
        case "block_property":
        case "block_state": {
            const perm = ctx.permutation ?? ctx.block?.permutation;
            try {
                return perm?.getState(args[0]) ?? 0;
            } catch {
                return 0;
            }
        }
        case "cardinal_facing_2d":
            return facing2d(ctx.player);
        case "target_x_rotation":
            return ctx.player?.getRotation().x ?? 0;
        case "block_face":
            return FACES[ctx.face] ?? 1;
        case "is_item_name_any": {
            const held = mainhand(ctx.player)?.typeId;
            return args.slice(2).some((n) => n === held);
        }
        case "block_neighbor_has_any_tag": {
            try {
                const b = ctx.block?.offset({ x: args[0], y: args[1], z: args[2] });
                return !!b && args.slice(3).some((t) => b.hasTag(t));
            } catch {
                return false;
            }
        }
        case "random":
            return args[0] + Math.random() * (args[1] - args[0]);
        default:
            return 0;
    }
}

// --- Event responses ------------------------------------------------------------------
function mainhand(player) {
    try {
        return player?.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand);
    } catch {
        return undefined;
    }
}

function setMainhand(player, item) {
    player.getComponent("minecraft:equippable")?.setEquipment(EquipmentSlot.Mainhand, item);
}

function pick(target, ctx) {
    switch (target) {
        case "other": return ctx.other;
        case "holder": case "player": return ctx.player;
        case "block": return undefined;
        default: return ctx.self ?? ctx.player;
    }
}

function runCommands(cmds, target, ctx) {
    for (const c of Array.isArray(cmds) ? cmds : [cmds]) {
        if (!c) continue;
        try {
            const who = target === "other" || target === "holder" || target === "player" ? pick(target, ctx) : undefined;
            if (who) who.runCommand(c);
            else if (ctx.block) {
                // block events ran their commands at the block
                const { x, y, z } = ctx.block.location;
                ctx.dimension.runCommand(`execute positioned ${x} ${y} ${z} run ${c}`);
            } else ctx.player?.runCommand(c);
        } catch {
            // a command that fails here failed in the original too
        }
    }
}

function durabilityHit(ctx, amount) {
    const player = ctx.player;
    const item = mainhand(player);
    if (!item || creative(player)) return;
    const d = item.getComponent("minecraft:durability");
    if (!d) return;
    const unbreaking = item.getComponent("minecraft:enchantable")?.getEnchantment("unbreaking")?.level ?? 0;
    if (Math.random() * (unbreaking + 1) >= 1) return;
    if (d.damage + amount >= d.maxDurability) {
        setMainhand(player, undefined);
        player.playSound("random.break");
    } else {
        d.damage += amount;
        setMainhand(player, item);
    }
}

/** Plays an event; block state changes are applied once, when it is over. */
function play(ev, ctx) {
    if (!ev) return;
    const start = ctx.placing ? ctx.placing.permutationToPlace : ctx.block?.permutation;
    ctx.write = start;
    respond(ev, ctx);
    if (!start || ctx.write === start) return;
    if (ctx.placing) ctx.placing.permutationToPlace = ctx.write;
    else {
        try {
            ctx.block.setPermutation(ctx.write);
        } catch {
            // the block is gone
        }
    }
}

function respond(ev, ctx) {
    if (!ev) return;
    if (ev.condition !== undefined && !evaluate(ev.condition, ctx)) return;
    if (ev.sequence) for (const step of ev.sequence) respond(step, ctx);
    if (ev.randomize) {
        const total = ev.randomize.reduce((s, r) => s + (r.weight ?? 1), 0);
        let roll = Math.random() * total;
        for (const r of ev.randomize) {
            roll -= r.weight ?? 1;
            if (roll <= 0) {
                respond(r, ctx);
                break;
            }
        }
    }
    if (ev.set_block_property && ctx.write) {
        // like the old events: conditions read the state as it was, writes land at the end
        let perm = ctx.write;
        for (const [k, v] of Object.entries(ev.set_block_property)) {
            let val = evaluate(v, ctx);
            try {
                const cur = perm.getState(k);
                if (typeof cur === "boolean") val = !!val;
                else if (typeof cur === "number") val = Math.round(Number(val));
                perm = perm.withState(k, val);
            } catch {
                // a value the state does not take
            }
        }
        ctx.write = perm;
    }
    if (ev.run_command) runCommands(ev.run_command.command, ev.run_command.target, ctx);
    if (ev.add_mob_effect) {
        const e = ev.add_mob_effect, who = pick(e.target, ctx);
        try {
            who?.addEffect(e.effect, Math.round((e.duration ?? 5) * 20), { amplifier: Math.floor(e.amplifier ?? 0) });
        } catch {
            // unknown effect
        }
    }
    if (ev.remove_mob_effect) {
        try {
            pick(ev.remove_mob_effect.target, ctx)?.removeEffect(ev.remove_mob_effect.effect);
        } catch {
            // ignore
        }
    }
    if (ev.damage) {
        const d = ev.damage;
        if (d.target === "self" || d.type === "durability") durabilityHit(ctx, d.amount ?? 1);
        else {
            try {
                pick(d.target, ctx)?.applyDamage(d.amount ?? 1, { cause: d.type ?? "magic", damagingEntity: ctx.player });
            } catch {
                // ignore
            }
        }
    }
    if (ev.decrement_stack !== undefined && ctx.player && !creative(ctx.player)) {
        const item = mainhand(ctx.player);
        if (item) {
            if (item.amount > 1) {
                item.amount -= 1;
                setMainhand(ctx.player, item);
            } else setMainhand(ctx.player, undefined);
        }
    }
}

// --- Items ---------------------------------------------------------------------------------
function fireItem(item, trigger, ctx) {
    const def = ITEMS[item.typeId];
    const name = def?.triggers?.[trigger];
    if (!name) return;
    system.run(() => play(def.events[name], ctx));
}

function onCooldown(item, player) {
    try {
        const cd = item.getComponent("minecraft:cooldown");
        if (!cd) return false;
        if (cd.getCooldownTicksRemaining(player) > 0) return true;
        cd.startCooldown(player);
    } catch {
        // no cooldown API
    }
    return false;
}

const itemComponent = {
    onUse({ source, itemStack }) {
        if (!itemStack || onCooldown(itemStack, source)) return;
        fireItem(itemStack, "use", { player: source, self: source });
    },
    onUseOn({ source, itemStack, block, blockFace }) {
        const def = ITEMS[itemStack?.typeId];
        if (def?.use_on && !def.use_on.some((b) => block.typeId === b || block.typeId === `minecraft:${b}`)) return;
        fireItem(itemStack, "use_on", { player: source, self: source, block, face: blockFace, dimension: block.dimension });
    },
    onHitEntity({ attackingEntity, hitEntity, hadEffect, itemStack }) {
        if (!itemStack) return;
        fireItem(itemStack, hadEffect === false ? "not_hurt" : "hurt", { player: attackingEntity, self: attackingEntity, other: hitEntity });
    },
    onMineBlock({ source, itemStack, block }) {
        if (!itemStack) return;
        const def = ITEMS[itemStack.typeId];
        const dig = def?.dig?.[block?.typeId] ?? def?.triggers?.hit_block;
        if (dig) system.run(() => play(def.events[dig], { player: source, self: source }));
    },
    onConsume({ source, itemStack }) {
        if (itemStack) fireItem(itemStack, "consume", { player: source, self: source });
    },
};

// --- Blocks ------------------------------------------------------------------------------------
function blockTrigger(block, trigger, permutation) {
    const def = BLOCKS[block?.typeId ?? permutation?.type?.id];
    if (!def) return undefined;
    let found = def.triggers[trigger];
    const perm = permutation ?? block.permutation;
    for (const p of def.perms) {
        if (p.triggers[trigger] && evaluate(p.condition, { permutation: perm, block })) found = p.triggers[trigger];
    }
    return found ? { def, t: found } : undefined;
}

function fireBlock(block, trigger, ctx, permutation) {
    const hit = blockTrigger(block, trigger, permutation);
    if (!hit) return;
    const full = { block, dimension: block?.dimension ?? ctx.dimension, ...ctx };
    if (hit.t.condition !== undefined && !evaluate(hit.t.condition, full)) return;
    play(hit.def.events[hit.t.event], full);
}

const blockComponent = {
    beforeOnPlayerPlace(ev) {
        const id = ev.permutationToPlace.type.id;
        const def = BLOCKS[id];
        const t = def?.triggers.place_player;
        if (!t) return;
        const ctx = { player: ev.player, placing: ev, block: ev.block, face: ev.face, dimension: ev.dimension };
        if (t.condition !== undefined && !evaluate(t.condition, ctx)) return;
        play(def.events[t.event], ctx);
    },
    onPlace({ block, dimension }) {
        fireBlock(block, "placed", { dimension });
    },
    onPlayerInteract({ block, player, face, dimension }) {
        system.run(() => fireBlock(block, "interact", { player, other: player, face, dimension }));
    },
    onPlayerBreak({ block, brokenBlockPermutation, player, dimension }) {
        const hit = blockTrigger(undefined, "destroyed", brokenBlockPermutation);
        if (!hit) return;
        const ctx = { block, player, other: player, dimension, permutation: brokenBlockPermutation };
        system.run(() => play(hit.def.events[hit.t.event], ctx));
    },
    onStepOn({ block, entity, dimension }) {
        fireBlock(block, "step_on", { other: entity, player: entity, dimension });
    },
    onStepOff({ block, entity, dimension }) {
        fireBlock(block, "step_off", { other: entity, player: entity, dimension });
    },
    onEntityFallOn({ block, entity, dimension }) {
        fireBlock(block, "fall_on", { other: entity, player: entity, dimension });
    },
    onTick({ block, dimension }) {
        fireBlock(block, "tick", { dimension });
    },
    onRandomTick({ block, dimension }) {
        fireBlock(block, "random_tick", { dimension });
    },
};

system.beforeEvents.startup.subscribe(({ itemComponentRegistry, blockComponentRegistry }) => {
    itemComponentRegistry.registerCustomComponent("mo:item_events", itemComponent);
    blockComponentRegistry.registerCustomComponent("mo:block_events", blockComponent);
});

// --- Equipment bonuses ---------------------------------------------------------------------------
// The original gave the player, every tick, the health, speed and effects of the last
// matching item (held or worn) and removed every effect otherwise, which also wiped
// potions and beacons. Now: the bonus group changes only when the gear changes,
// and the item's effects are refreshed in short bursts (they fade when it is taken off).
const current = new Map(); // player id -> gear key

function gearOf(player) {
    const eq = player.getComponent("minecraft:equippable");
    if (!eq) return undefined;
    const hand = [EquipmentSlot.Mainhand, EquipmentSlot.Offhand].map((s) => eq.getEquipment(s)?.typeId);
    const armor = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet]
        .map((s) => eq.getEquipment(s)?.typeId);
    let found;
    for (const g of GEAR) {
        if ((g.domain === "armor" ? armor : hand).includes(g.item)) found = g; // the last match wins
    }
    return found;
}

system.runInterval(() => {
    for (const player of world.getAllPlayers()) {
        if (!isValid(player)) continue;
        let g;
        try {
            g = gearOf(player);
        } catch {
            continue;
        }
        const key = g?.group ?? "";
        if (current.get(player.id) !== key) {
            current.set(player.id, key);
            try {
                player.triggerEvent(g ? GEAR_EVENTS[g.group] : "mo:gear_none");
            } catch {
                // ignore
            }
        }
        for (const e of g?.effects ?? []) {
            try {
                player.addEffect(e.effect, 50, { amplifier: Math.max(0, Math.floor(e.amplifier ?? 0)), showParticles: false });
            } catch {
                // unknown effect
            }
        }
    }
}, 10);

world.afterEvents.playerSpawn.subscribe(({ player }) => current.delete(player.id));
world.afterEvents.playerLeave?.subscribe(({ playerId }) => current.delete(playerId));
