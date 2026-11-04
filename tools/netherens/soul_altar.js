import { world, system, EquipmentSlot, GameMode } from "@minecraft/server";

// The Soul Altar of the Soul Fortress: a Wither Skeleton Skull wakes the Nether Lord.
// (It replaces the Trapped Soul Energy item, which is gone.)

const ALTAR = "netherens:soul_altar";
const BOSS = "low:netherboss";
const SKULLS = new Set(["minecraft:wither_skeleton_skull"]);
const ALTAR_PROPERTY = "netherens:altar";
const SUMMON_TICKS = 60;
const cooldown = new Map();

const isValid = (e) => !!e && (typeof e.isValid === "function" ? e.isValid() : e.isValid);
const isCreative = (p) => {
    const mode = p.getGameMode();
    return mode === GameMode.creative || mode === GameMode.Creative;
};

// The skull-tracking function scores skulls on this objective: create it once
// here (the function used to run "scoreboard objectives add" every tick).
system.run(() => {
    if (!world.scoreboard.getObjective("NetherBossDistance")) {
        world.scoreboard.addObjective("NetherBossDistance", "NetherBossDistance");
    }
});

function bossNear(dimension, location, radius) {
    return dimension.getEntities({ type: BOSS, location, maxDistance: radius }).length > 0;
}

function setLit(block, lit) {
    block.setPermutation(block.permutation.withState("netherens:lit", lit));
}

function consumeSkull(player) {
    if (isCreative(player)) return;
    const slot = player.getComponent("minecraft:equippable")?.getEquipmentSlot(EquipmentSlot.Mainhand);
    const item = slot?.getItem();
    if (!item) return;
    if (item.amount > 1) {
        item.amount -= 1;
        slot.setItem(item);
    } else {
        slot.setItem(undefined);
    }
}

function use(block, player, item) {
    if (!isValid(player) || block.typeId !== ALTAR) return;
    const dimension = block.dimension;
    const at = block.location;
    const top = { x: at.x + 0.5, y: at.y + 1, z: at.z + 0.5 };

    if (block.permutation.getState("netherens:lit")) {
        if (!bossNear(dimension, top, 128)) {
            setLit(block, false); // left lit when the world closed mid-fight
            player.onScreenDisplay.setActionBar("§7The soul flames die down.");
        } else {
            player.onScreenDisplay.setActionBar("§cThe Nether Lord is already here.");
        }
        return;
    }
    if (!item || !SKULLS.has(item.typeId)) {
        player.onScreenDisplay.setActionBar("§3The altar waits for a §fWither Skeleton Skull§3.");
        return;
    }
    if (bossNear(dimension, top, 128)) {
        player.onScreenDisplay.setActionBar("§cThe Nether Lord is already here.");
        return;
    }

    consumeSkull(player);
    setLit(block, true);
    dimension.playSound("mob.wither.spawn", top, { volume: 2, pitch: 0.7 });
    dimension.playSound("netherboss.half_health_wrap", top);
    for (let i = 0; i < 24; i++) {
        const a = (i / 24) * Math.PI * 2;
        dimension.spawnParticle("minecraft:soul_particle", { x: top.x + Math.cos(a) * 2.5, y: top.y + 0.2, z: top.z + Math.sin(a) * 2.5 });
    }
    player.runCommand(`camerashake add @a[r=40] 0.3 3 positional`);
    player.runCommand(`tellraw @a[r=60] {"rawtext":[{"text":"§8§oThe soul fire answers the skull..."}]}`);

    system.runTimeout(() => {
        let altar;
        try {
            altar = dimension.getBlock(at);
        } catch {
            return;
        }
        if (!altar || altar.typeId !== ALTAR) return;
        const boss = dimension.spawnEntity(BOSS, { x: top.x, y: top.y + 1, z: top.z });
        boss.setDynamicProperty(ALTAR_PROPERTY, JSON.stringify({ d: dimension.id, x: at.x, y: at.y, z: at.z }));
        for (const p of dimension.getPlayers({ location: top, maxDistance: 60 })) {
            p.runCommand(`playsound music.boss.music.battle @s`);
            p.sendMessage("§oYou wanted my attention Vermin? You have it now.");
        }
    }, SUMMON_TICKS);
}

world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
    const { block, player } = event;
    if (block.typeId !== ALTAR) return;
    event.cancel = true; // nothing gets placed on the altar
    const now = system.currentTick;
    if ((cooldown.get(player.id) ?? -100) > now - 10) return;
    cooldown.set(player.id, now);
    const item = event.itemStack;
    system.run(() => use(block, player, item));
});

// The altar can be used again once the Nether Lord is gone.
function releaseAltar(entity) {
    let raw;
    try {
        raw = entity.getDynamicProperty(ALTAR_PROPERTY);
    } catch {
        return;
    }
    if (typeof raw !== "string") return;
    system.run(() => {
        try {
            const a = JSON.parse(raw);
            const block = world.getDimension(a.d).getBlock({ x: a.x, y: a.y, z: a.z });
            if (block?.typeId === ALTAR) setLit(block, false);
        } catch {
            // unloaded: the altar notices on its next use
        }
    });
}

world.afterEvents.entityDie.subscribe(({ deadEntity }) => {
    if (deadEntity.typeId === BOSS) releaseAltar(deadEntity);
});
world.beforeEvents.entityRemove?.subscribe(({ removedEntity }) => {
    if (removedEntity.typeId === BOSS) releaseAltar(removedEntity);
});
