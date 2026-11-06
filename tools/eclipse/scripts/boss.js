import { world, system, EntityDamageCause } from "@minecraft/server";
import { C, ring, safe as safe_, burst, charge, column, beam, sound, shake, flash } from "./fx.js";
import { shoot, clear, arenaPlayers, arenaTargets, arenaMobs, hurt, inPlay } from "./hazards.js";
import { ATTACKS, DECKS, ANIM, combo } from "./attacks.js";
import { level } from "./settings.js";
import { setAltar } from "./altar.js";

// The Eclipse fight: movement, the attack cycle, teleports, the three phases, the
// total eclipse (the ultimate) and the death scene.

export const BOSS = "eclipse:eclipse";
export const REMNANT = "eclipse:remnant";
const DIMENSIONS = ["overworld", "nether", "the_end"];
const ARENA_R = 22;
const HOVER = 0.4;                 // feet above the floor
const DRIFT_SPEED = 3.2;           // blocks per second
const PHASE_AT = [0.66, 0.33];
const ULT_FIRST = 300, ULT_EVERY = 1200; // ticks (15 s after phase 3 begins, then every 60 s)
const LEAVE_AFTER = 600;           // 30 s without anyone in the arena: the Eclipse withdraws
const REST = [24, 18, 14], TP_EVERY = [3, 2, 2];
// chance that the next attack starts in the last quarter of the current one
const OVERLAP = [0.5, 0.75, 1];

const fights = new Map();
const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const by = (f, list) => list[f.phase - 1];
const yawDeg = (dx, dz) => Math.atan2(-dx, dz) * (180 / Math.PI);

function titleAll(players, title, subtitle, stay = 50) {
    for (const p of players) {
        try {
            p.onScreenDisplay.setTitle(title, { subtitle, fadeInDuration: 8, stayDuration: stay, fadeOutDuration: 16 });
        } catch {
            // ignore
        }
    }
}

function findFloor(dim, loc) {
    for (let y = Math.floor(loc.y); y > Math.floor(loc.y) - 24; y--) {
        try {
            const b = dim.getBlock({ x: Math.floor(loc.x), y: y - 1, z: Math.floor(loc.z) });
            if (b && !b.isAir && !b.isLiquid) return y;
        } catch {
            break;
        }
    }
    return Math.floor(loc.y);
}

class Fight {
    constructor(boss) {
        this.boss = boss;
        this.id = boss.id;
        this.dim = boss.dimension;
        let arena;
        try {
            arena = JSON.parse(boss.getDynamicProperty("eclipse:arena") ?? "null");
        } catch {
            arena = null;
        }
        if (!arena) {
            const l = boss.location;
            arena = { cx: l.x, cz: l.z, floor: findFloor(this.dim, l), R: ARENA_R };
            boss.setDynamicProperty("eclipse:arena", JSON.stringify(arena));
        }
        this.arena = arena;
        this.phase = Math.max(1, Math.min(3, boss.getProperty("eclipse:phase") ?? 1));
        this.gen = 0;
        this.timers = new Set();
        this.busyUntil = system.currentTick + 40;
        this.attacks = 0;
        this.bag = [];
        this.last = "";
        this.goal = null;          // where an attack wants the boss; null: drift
        this.height = HOVER;
        this.orbit = Math.random() < 0.5 ? 1 : -1;
        this.empty = 0;
        this.close = 0;
        this.lockedUntil = 0;
        this.freeAt = 0;
        this.animToken = 0;
        this.goalSpeed = 7;
        this.nextUlt = this.phase === 3 ? system.currentTick + ULT_FIRST : Infinity;
        const n = Math.max(1, Math.min(4, this.players().length));
        this.hpScale = level().hp * (1 + 0.5 * (n - 1));
        if (!boss.getDynamicProperty("eclipse:intro")) {
            boss.setDynamicProperty("eclipse:intro", true);
            this.anim(ANIM.appear);
            this.after(24, () => this.anim(ANIM.idle));
            this.busyUntil = system.currentTick + 50;
        } else {
            this.anim(ANIM.idle);
            this.set("eclipse:hidden", false);
            this.set("eclipse:shield", false);
        }
    }

    // --- helpers used by the attacks ---
    after(ticks, fn) {
        const gen = this.gen;
        const id = system.runTimeout(() => {
            this.timers.delete(id);
            if (gen === this.gen && isValid(this.boss)) {
                try {
                    fn();
                } catch {
                    // the boss or a target vanished
                }
            }
        }, Math.max(0, Math.round(ticks)));
        this.timers.add(id);
    }

    cancel() {
        this.gen++;
        for (const id of this.timers) system.clearRun(id);
        this.timers.clear();
    }

    set(prop, value) {
        try {
            this.boss.setProperty(prop, value);
        } catch {
            // gone
        }
    }

    /** Sets a pose; returns a token so that only its owner puts the boss back to idle. */
    pose(n) {
        this.set("eclipse:anim", n);
        return ++this.animToken;
    }

    unpose(token, toIdle = true) {
        if (token !== this.animToken) return false;
        if (toIdle) this.pose(0);
        return true;
    }

    anim(n) {
        this.pose(n);
    }

    players() {
        return arenaPlayers(this.dim, this.arena);
    }

    /** Everything it fights: players and mobs in the arena. */
    targets() {
        return arenaTargets(this.dim, this.arena);
    }

    hit(e, dmg) {
        return hurt(e, dmg, this.boss);
    }

    dashTo(x, z, speed, ticks) {
        this.goal = { x, z };
        this.goalSpeed = speed;
        this.after(ticks + 2, () => {
            this.goal = null;
            this.goalSpeed = 7;
        });
    }

    inArena(x, z) {
        return Math.hypot(x - this.arena.cx, z - this.arena.cz) <= this.arena.R - 1;
    }

    nearestTo(pos) {
        let best, bd = Infinity;
        for (const p of this.targets()) {
            const d = Math.hypot(p.location.x - pos.x, p.location.z - pos.z);
            if (d < bd) {
                best = p;
                bd = d;
            }
        }
        return best;
    }

    target() {
        if (isValid(this.tgt) && this.targets().some((p) => p.id === this.tgt.id)) return this.tgt;
        this.tgt = this.nearestTo(this.boss.location);
        return this.tgt;
    }

    pickTarget() {
        const ps = this.targets();
        this.tgt = ps.length && Math.random() < 0.4 ? ps[Math.floor(Math.random() * ps.length)] : this.nearestTo(this.boss.location);
    }

    hp() {
        try {
            const h = this.boss.getComponent("minecraft:health");
            return h.currentValue / (h.effectiveMax || 1);
        } catch {
            return 1;
        }
    }

    ground(x, z, dy = 0.06) {
        return { x, y: this.arena.floor + dy, z };
    }

    // --- movement ---
    move() {
        const b = this.boss, l = b.location, a = this.arena;
        this.lastPos = { ...l };
        const t = this.target();
        let gx, gz;
        if (this.goal) {
            gx = this.goal.x;
            gz = this.goal.z;
        } else if (t && system.currentTick >= this.busyUntil) {
            // drift: keep ~9 blocks from the target, circling it slowly
            let ang = Math.atan2(l.z - t.location.z, l.x - t.location.x) + this.orbit * 0.012;
            gx = t.location.x + Math.cos(ang) * 9;
            gz = t.location.z + Math.sin(ang) * 9;
            const d = Math.hypot(gx - a.cx, gz - a.cz), max = a.R - 3;
            if (d > max) {
                gx = a.cx + ((gx - a.cx) / d) * max;
                gz = a.cz + ((gz - a.cz) / d) * max;
                if (Math.random() < 0.01) this.orbit *= -1;
            }
        } else {
            gx = l.x;
            gz = l.z;
        }
        const dx = gx - l.x, dz = gz - l.z, dist = Math.hypot(dx, dz);
        const step = Math.min(dist, (this.goal ? this.goalSpeed : DRIFT_SPEED) / 20);
        const vy = Math.max(-0.25, Math.min(0.25, (a.floor + this.height - l.y) * 0.25));
        try {
            b.clearVelocity();
            b.applyImpulse({ x: dist > 0.01 ? (dx / dist) * step : 0, y: vy, z: dist > 0.01 ? (dz / dist) * step : 0 });
            if (t) b.setRotation({ x: 0, y: yawDeg(t.location.x - l.x, t.location.z - l.z) });
        } catch {
            // gone
        }
    }

    relocate(x, z, height = this.height) {
        this.height = height;
        try {
            this.boss.teleport({ x, y: this.arena.floor + height, z }, { keepVelocity: false });
        } catch {
            // ignore
        }
    }

    // --- the cycle ---
    tick() {
        const now = system.currentTick;
        const players = this.players();
        if (!players.length) {
            this.empty++;
            if (this.empty > LEAVE_AFTER) return this.leave();
            if (now % 20 === 0) heal(this.boss, 2);
        } else {
            this.empty = 0;
        }
        this.move();
        // a phase change interrupts whatever the boss is doing (but not another
        // phase change or the total eclipse)
        const hp = this.hp();
        const want = hp <= PHASE_AT[1] ? 3 : hp <= PHASE_AT[0] ? 2 : 1;
        if (want > this.phase && now >= this.lockedUntil) {
            const d = transition(this, this.phase + 1);
            this.lockedUntil = now + d;
            return this.busy(d);
        }
        const targets = this.targets();
        if (now < this.busyUntil || !targets.length) return;
        if (this.phase === 3 && now >= this.nextUlt) {
            this.nextUlt = now + ULT_EVERY;
            const d = ultimate(this);
            this.lockedUntil = now + d;
            return this.busy(d);
        }
        // someone glued to the boss: push them away, then vanish
        const near = targets.some((p) => Math.hypot(p.location.x - this.boss.location.x, p.location.z - this.boss.location.z) < 3.2);
        this.close = near ? this.close + 1 : 0;
        if (this.close > 30) {
            this.close = 0;
            this.attacks = 99;
            return this.busy(ATTACKS.repel(this, {}), 6);
        }
        if (this.attacks >= by(this, TP_EVERY)) {
            if (now < this.freeAt) return; // never vanish in the middle of an attack
            this.attacks = 0;
            return this.busy(teleport(this), 4);
        }
        this.pickTarget();
        this.attacks++;
        const entry = this.draw();
        const dur = Array.isArray(entry) ? combo(this, ...entry) : ATTACKS[entry](this, {});
        // the next attack may begin in this one's last quarter
        if (Math.random() < by(this, OVERLAP) && this.attacks < by(this, TP_EVERY)) {
            this.freeAt = now + dur;
            this.busyUntil = now + Math.ceil(dur * 0.75);
        } else {
            this.busy(dur);
        }
    }

    busy(ticks, rest = by(this, REST)) {
        this.busyUntil = system.currentTick + ticks + rest;
        this.freeAt = system.currentTick + ticks;
    }

    draw() {
        if (!this.bag.length) {
            for (const [entry, w] of DECKS[this.phase - 1]) for (let i = 0; i < w; i++) this.bag.push(entry);
            for (let i = this.bag.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [this.bag[i], this.bag[j]] = [this.bag[j], this.bag[i]];
            }
        }
        let i = this.bag.findIndex((e) => JSON.stringify(e) !== this.last);
        if (i < 0) i = 0;
        const entry = this.bag.splice(i, 1)[0];
        this.last = JSON.stringify(entry);
        return entry;
    }

    leave() {
        this.cancel();
        clear(this.id, true);
        const l = this.boss.location;
        burst(this.dim, { x: l.x, y: l.y + 1, z: l.z }, C.violet, 30, 4);
        sound(this.dim, "mob.endermen.portal", l, 2, 0.5);
        for (const p of this.dim.getPlayers({ location: l, maxDistance: 64 })) {
            p.sendMessage("§8[Eclipse] §7El Eclipse se retira... El altar vuelve a estar en calma.");
        }
        resetAltar(this);
        fights.delete(this.id);
        try {
            this.boss.remove();
        } catch {
            // gone
        }
    }
}

function heal(boss, amount) {
    try {
        const h = boss.getComponent("minecraft:health");
        h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + amount));
    } catch {
        // gone
    }
}

function resetAltar(f) {
    const a = f.arena;
    if (a.ax !== undefined) setAltar(f.dim, { x: a.ax, y: a.ay, z: a.az }, false);
}

// --- teleport ----------------------------------------------------------------------------
function spot(f) {
    const a = f.arena, ps = f.targets(), t = f.target();
    let best, bestScore = -Infinity;
    for (let i = 0; i < 24; i++) {
        const ang = Math.random() * 2 * Math.PI, d = Math.sqrt(Math.random()) * (a.R - 4);
        const p = { x: a.cx + Math.cos(ang) * d, z: a.cz + Math.sin(ang) * d };
        const near = Math.min(...ps.map((q) => Math.hypot(q.location.x - p.x, q.location.z - p.z)), 99);
        const td = t ? Math.hypot(t.location.x - p.x, t.location.z - p.z) : 10;
        const score = (near >= 6 ? 10 : 0) - Math.abs(td - 11) + Math.random() * 3;
        if (score > bestScore) {
            best = p;
            bestScore = score;
        }
    }
    return best;
}

/** Vanish (8 ticks), the destination glows and hums (the warning), reappear. */
export function teleport(f, dest = spot(f), o = {}) {
    const warn = o.warn ?? by(f, [18, 15, 13]);
    const from = { ...f.boss.location };
    f.anim(ANIM.vanish);
    f.goal = { x: from.x, z: from.z };
    sound(f.dim, "mob.endermen.portal", from, 1.5, 0.7);
    charge(f.dim, { x: from.x, y: from.y + 1, z: from.z }, C.violet, 1.8, 0.4, 20);
    let t = 0;
    const g = f.ground(dest.x, dest.z);
    // the warning at the destination
    f.after(2, () => sound(f.dim, "mob.shulker.teleport", { ...g, y: g.y + 1 }, 2, 0.6));
    column(f.dim, g, C.violet, (8 + warn) / 20, 5, 0.4, 0.5);
    ring(f.dim, g, 2, C.white, (8 + warn) / 20, { speed: -2 / ((8 + warn) / 20) });
    ring(f.dim, { ...g, y: g.y + 0.02 }, 1.3, C.violet, (8 + warn) / 20);
    f.after(8, () => {
        f.set("eclipse:hidden", true);
        f.relocate(dest.x, dest.z, o.height ?? HOVER);
        f.goal = { x: dest.x, z: dest.z };
    });
    f.after(8 + warn, () => {
        f.set("eclipse:hidden", false);
        f.anim(ANIM.appear);
        burst(f.dim, { x: dest.x, y: g.y + 1.2, z: dest.z }, C.violet, 26, 4);
        sound(f.dim, "mob.endermen.portal", g, 1.5, 1.4);
        if (f.phase >= 2 && !o.quiet) {
            for (let k = 0; k < 12; k++) shoot(f, { x: dest.x, z: dest.z, angle: (k / 12) * 2 * Math.PI, speed: 4.5, color: C.violet, dmg: 4 });
        }
    });
    f.after(8 + warn + 12, () => {
        f.anim(ANIM.idle);
        f.goal = null;
    });
    return 8 + warn + 12;
}

// --- phases -----------------------------------------------------------------------------
const PHASE_TEXT = {
    2: ["§d§l✦ FASE II ✦", "§7El Eclipse se acelera", "mob.enderdragon.growl", C.violet],
    3: ["§c§l✦ FASE III ✦", "§7La oscuridad lo cubre todo", "mob.wither.spawn", C.crimson],
};

function transition(f, phase) {
    f.cancel();
    clear(f.id, true);
    f.bag = [];
    f.attacks = 0;
    const [title, sub, roar, color] = PHASE_TEXT[phase];
    const a = f.arena;
    f.set("eclipse:shield", true);
    teleport(f, { x: a.cx, z: a.cz }, { warn: 8, quiet: true });
    f.after(20, () => {
        f.anim(ANIM.phase);
        f.height = 2.2;
        sound(f.dim, "beacon.power", f.boss.location, 3, 0.5);
        titleAll(f.players(), title, sub);
    });
    for (let t = 24; t < 84; t += 6) {
        f.after(t, () => {
            const l = f.boss.location;
            charge(f.dim, { x: l.x, y: l.y + 1.2, z: l.z }, color, 4, 0.5, 26);
            if (t % 18 === 0) ring(f.dim, f.ground(l.x, l.z), 2, color, 0.8, { speed: 18 });
        });
    }
    f.after(40, () => shake(f.dim, f.boss.location, a.R + 10, 0.2, 2.5));
    f.after(88, () => {
        const l = f.boss.location;
        f.phase = phase;
        f.set("eclipse:phase", phase);
        sound(f.dim, roar, l, 3, 1);
        sound(f.dim, "random.explode", l, 2, 0.6);
        burst(f.dim, { x: l.x, y: l.y + 1.2, z: l.z }, color, 60, 9);
        ring(f.dim, f.ground(l.x, l.z), 1.5, color, 1.4, { speed: 22 });
        beam(f.dim, f.ground(l.x, l.z), color, 30, 1.4);
        for (const p of f.targets()) {
            if (p.typeId === "minecraft:player") flash(p, color[0] * 255, color[1] * 255, color[2] * 255, 0.1);
            const d = Math.max(0.5, Math.hypot(p.location.x - l.x, p.location.z - l.z));
            try {
                p.applyKnockback({ x: ((p.location.x - l.x) / d) * 1.4, z: ((p.location.z - l.z) / d) * 1.4 }, 0.35);
            } catch {
                // ignore
            }
        }
        if (phase === 3) f.nextUlt = system.currentTick + ULT_FIRST;
    });
    f.after(110, () => {
        f.height = HOVER;
        f.set("eclipse:shield", false);
        f.anim(ANIM.idle);
    });
    return 120;
}

// --- the total eclipse --------------------------------------------------------------------------
const ULT_CHARGE = 130, ULT_DAMAGE = 18, SAFE_R = 3.2;

function ultimate(f) {
    f.cancel();
    clear(f.id, true);
    const a = f.arena;
    f.set("eclipse:shield", true);
    teleport(f, { x: a.cx, z: a.cz }, { warn: 8, quiet: true });
    const base = Math.random() * 2 * Math.PI;
    const safe = [0, 1, 2].map((k) => {
        const ang = base + (k / 3) * 2 * Math.PI;
        return { x: a.cx + Math.cos(ang) * a.R * 0.58, z: a.cz + Math.sin(ang) * a.R * 0.58 };
    });
    const start = 22;
    f.after(start, () => {
        f.anim(ANIM.ultCharge);
        f.height = 6;
        titleAll(f.players(), "§5§l✦ ECLIPSE TOTAL ✦", "§eRefúgiate en los círculos de luz", 70);
        sound(f.dim, "mob.warden.sonic_charge", f.boss.location, 3, 0.5);
        sound(f.dim, "ambient.cave", f.boss.location, 3, 0.6);
    });
    // safe zones: golden suns and columns of light, shown for the whole charge; the
    // darkness (a red ring) closes in from the edge
    f.after(start, () => {
        const life = ULT_CHARGE / 20 + 0.3;
        for (const s of safe) {
            const g = f.ground(s.x, s.z);
            safe_(f.dim, g, SAFE_R, C.safe, life);
            column(f.dim, g, C.safe, life, 10, SAFE_R, 0.22);
            column(f.dim, g, C.white, life, 14, 0.25, 0.6);
        }
        ring(f.dim, f.ground(a.cx, a.cz), a.R, C.danger, life, { speed: -(a.R * 0.15) / life });
    });
    for (let t = start; t < start + ULT_CHARGE; t += 10) {
        f.after(t, () => {
            const l = f.boss.location;
            charge(f.dim, { x: l.x, y: l.y + 1.2, z: l.z }, C.violet, 7, 0.55, 40);
        });
    }
    for (let s = 3; s >= 1; s--) {
        f.after(start + ULT_CHARGE - s * 20, () => {
            for (const p of f.players()) p.onScreenDisplay.setActionBar(`§c§l${s}...  §r§eA la luz`);
            sound(f.dim, "note.bell", f.boss.location, 3, 0.5 + (3 - s) * 0.2);
        });
    }
    f.after(start + ULT_CHARGE, () => {
        f.anim(ANIM.ultRelease);
        const l = f.boss.location;
        sound(f.dim, "mob.warden.sonic_boom", l, 4, 0.6);
        sound(f.dim, "random.explode", l, 3, 0.5);
        shake(f.dim, l, a.R + 20, 0.5, 1.2);
        ring(f.dim, f.ground(l.x, l.z), 1, C.violet, 1.2, { speed: 26 });
        burst(f.dim, { x: l.x, y: l.y + 1, z: l.z }, C.violet, 80, 12);
        for (let i = 0; i < 14; i++) {
            const ang = Math.random() * 2 * Math.PI, d = 4 + Math.random() * (a.R - 4);
            const x = a.cx + Math.cos(ang) * d, z = a.cz + Math.sin(ang) * d;
            if (safe.every((s) => Math.hypot(s.x - x, s.z - z) > SAFE_R + 1)) beam(f.dim, f.ground(x, z), C.violet, 28, 1);
        }
        const everyone = [...f.dim.getPlayers({ location: { x: a.cx, y: a.floor, z: a.cz }, maxDistance: a.R + 24 }).filter(inPlay),
            ...arenaMobs(f.dim, a)];
        for (const p of everyone) {
            const ok = safe.some((s) => Math.hypot(s.x - p.location.x, s.z - p.location.z) <= SAFE_R + 0.4);
            const player = p.typeId === "minecraft:player";
            if (ok) {
                if (player) {
                    flash(p, 255, 230, 140, 0.05);
                    p.onScreenDisplay.setActionBar("§e✦ La luz te protege ✦");
                }
            } else {
                if (player) flash(p, 40, 0, 60, 0.3);
                hurt(p, ULT_DAMAGE, f.boss, EntityDamageCause.magic);
            }
        }
    });
    // spent: it falls to the floor and kneels; the moment to strike
    f.after(start + ULT_CHARGE + 16, () => {
        f.height = 0;
        f.set("eclipse:shield", false);
        f.anim(ANIM.exhausted);
        for (const p of f.players()) p.onScreenDisplay.setActionBar("§7El Eclipse está agotado: ¡ataca!");
    });
    f.after(start + ULT_CHARGE + 110, () => {
        f.height = HOVER;
        f.anim(ANIM.idle);
    });
    return start + ULT_CHARGE + 116;
}

// --- the loop -----------------------------------------------------------------------------------
system.runInterval(() => {
    for (const id of DIMENSIONS) {
        let list;
        try {
            list = world.getDimension(id).getEntities({ type: BOSS });
        } catch {
            continue;
        }
        for (const b of list) if (!fights.has(b.id)) fights.set(b.id, new Fight(b));
    }
}, 20);

system.runInterval(() => {
    for (const [id, f] of fights) {
        if (!isValid(f.boss)) {
            f.cancel();
            clear(id, false);
            fights.delete(id);
            continue;
        }
        try {
            f.tick();
        } catch (e) {
            console.warn(`[Eclipse] ${e}`);
        }
    }
}, 1);

// More players (and the difficulty) make the Eclipse tougher: part of each hit is
// healed back (or, on Easy, hits count for more).
const extra = new Set();
world.afterEvents.entityHurt.subscribe(({ hurtEntity: e, damage }) => {
    if (e.typeId !== BOSS || damage <= 0 || extra.has(e.id)) return;
    const f = fights.get(e.id);
    if (!f) return;
    const k = 1 / f.hpScale;
    if (k < 1) heal(e, damage * (1 - k));
    else if (k > 1) {
        extra.add(e.id);
        try {
            e.applyDamage(damage * (k - 1), { cause: EntityDamageCause.override });
        } catch {
            // ignore
        } finally {
            extra.delete(e.id);
        }
    }
});

// --- death ---------------------------------------------------------------------------------------
world.afterEvents.entityDie.subscribe(({ deadEntity: e }) => {
    if (e.typeId !== BOSS) return;
    const f = fights.get(e.id);
    let at = f?.lastPos, dim = f?.dim, rot = { x: 0, y: 0 };
    try {
        at = { ...e.location };
        dim = e.dimension;
        rot = e.getRotation();
    } catch {
        // already gone: use what the fight remembers
    }
    if (!at || !dim) return;
    if (f) {
        f.cancel();
        clear(f.id, true);
        resetAltar(f);
        fights.delete(f.id);
    }
    deathScene(dim, at, rot, f?.arena);
});

function deathScene(dim, at, rot, arena) {
    let remnant;
    try {
        remnant = dim.spawnEntity(REMNANT, at);
        remnant.setRotation(rot);
    } catch {
        return;
    }
    const colors = [C.white, C.gold, C.violet];
    sound(dim, "mob.wither.death", at, 2, 0.7);
    for (let t = 0; t < 64; t += 5) {
        system.runTimeout(() => {
            const h = 1 + t / 30;
            burst(dim, { x: at.x + (Math.random() - 0.5) * 1.2, y: at.y + h + Math.random(), z: at.z + (Math.random() - 0.5) * 1.2 },
                colors[t % 3], 10, 3);
            if (t % 15 === 0) sound(dim, "random.glass", at, 1.5, 0.6 + t / 80);
        }, t);
    }
    system.runTimeout(() => shake(dim, at, 40, 0.25, 2), 20);
    system.runTimeout(() => {
        const top = { x: at.x, y: at.y + 3, z: at.z };
        sound(dim, "mob.warden.sonic_boom", at, 3, 1.2);
        sound(dim, "random.totem", at, 2, 0.8);
        burst(dim, top, C.white, 80, 10);
        ring(dim, { x: at.x, y: (arena?.floor ?? at.y) + 0.06, z: at.z }, 1, C.gold, 1.4, { speed: 20 });
        beam(dim, { x: at.x, y: arena?.floor ?? at.y, z: at.z }, C.white, 40, 1.6);
        for (const p of dim.getPlayers({ location: at, maxDistance: 48 })) {
            flash(p, 255, 255, 255, 0.2);
            p.onScreenDisplay.setTitle("§f§l✦ El Eclipse se disipa ✦", { subtitle: "§7La luz vuelve al cielo",
                fadeInDuration: 6, stayDuration: 50, fadeOutDuration: 20 });
        }
        try {
            dim.runCommand(`loot spawn ${top.x} ${top.y - 1} ${top.z} loot "eclipse/boss"`);
            for (let i = 0; i < 25; i++) dim.spawnEntity("minecraft:xp_orb", { x: at.x + (Math.random() - 0.5) * 2, y: at.y + 1, z: at.z + (Math.random() - 0.5) * 2 });
        } catch {
            // ignore
        }
        try {
            remnant.remove();
        } catch {
            // gone
        }
    }, 72);
}

export { fights };
