// A tiny fake of @minecraft/server, enough to run the Natura PvP scripts in Node.
export const log = [];
export const state = { tick: 0, timers: [], jobs: [], players: [], entities: [], dyn: {}, commands: [], blockOps: 0, nextId: 1 };

class Signal {
  constructor() {
    this.l = [];
  }
  subscribe(fn, opts) {
    this.l.push({ fn, opts });
    return fn;
  }
  unsubscribe() {}
  fire(ev) {
    for (const { fn, opts } of this.l) {
      if (opts?.entityTypes) {
        const e = ev.deadEntity ?? ev.hurtEntity;
        if (e && !opts.entityTypes.includes(e.typeId)) continue;
      }
      fn(ev);
    }
  }
}

export const system = {
  get currentTick() {
    return state.tick;
  },
  runInterval(fn, every = 1) {
    const t = { fn, every, at: state.tick + every, repeat: true, id: state.nextId++ };
    state.timers.push(t);
    return t.id;
  },
  runTimeout(fn, delay = 1) {
    const t = { fn, at: state.tick + Math.max(1, delay), repeat: false, id: state.nextId++ };
    state.timers.push(t);
    return t.id;
  },
  run(fn) {
    return this.runTimeout(fn, 1);
  },
  clearRun(id) {
    state.timers = state.timers.filter((t) => t.id !== id);
  },
  runJob(gen) {
    state.jobs.push(gen);
    return state.nextId++;
  },
  beforeEvents: { startup: new Signal() },
};

export async function advance(ticks, jobSteps = 50000) {
  for (let i = 0; i < ticks; i++) {
    state.tick++;
    for (const t of [...state.timers]) {
      if (t.at > state.tick) continue;
      if (t.repeat) t.at += t.every;
      else state.timers.splice(state.timers.indexOf(t), 1);
      t.fn();
    }
    for (const job of [...state.jobs]) {
      for (let n = 0; n < jobSteps; n++) {
        if (job.next().done) {
          state.jobs.splice(state.jobs.indexOf(job), 1);
          break;
        }
      }
    }
    await new Promise((r) => setImmediate(r));
  }
}

const enumOf = (...names) => Object.fromEntries(names.map((n) => [n, n]));
export const GameMode = enumOf("Adventure", "Survival", "Spectator", "Creative");
export const EquipmentSlot = enumOf("Head", "Chest", "Legs", "Feet", "Offhand", "Mainhand");
export const ItemLockMode = { slot: "slot", inventory: "inventory", none: "none" };
export const DisplaySlotId = enumOf("Sidebar", "List", "BelowName");
export const ObjectiveSortOrder = enumOf("Ascending", "Descending");
export const CustomCommandStatus = enumOf("Success", "Failure");
export const CommandPermissionLevel = enumOf("Any", "GameDirectors", "Admin");
export const CustomCommandParamType = enumOf("PlayerSelector", "String", "Integer");

export class BlockPermutation {
  static resolve(id, states) {
    if (typeof id !== "string" || !id.startsWith("minecraft:")) throw new Error("bad id " + id);
    return { id, states };
  }
}
export class BlockVolume {
  constructor(from, to) {
    this.from = from;
    this.to = to;
  }
}
export const EnchantmentTypes = { get: (id) => ({ id, maxLevel: id === "sharpness" || id === "power" ? 5 : 4 }) };

export class ItemStack {
  constructor(typeId, amount = 1) {
    if (!typeId.includes(":")) throw new Error("bad item");
    this.typeId = typeId;
    this.amount = amount;
    this.lore = [];
    this.ench = [];
  }
  setLore(l) {
    this.lore = [...l];
  }
  getLore() {
    return [...this.lore];
  }
  getComponent(name) {
    if (name !== "minecraft:enchantable") return undefined;
    const self = this;
    return {
      canAddEnchantment: () => true,
      addEnchantment(e) {
        if (e.level > e.type.maxLevel) throw new Error("level");
        self.ench.push(e);
      },
      getEnchantments: () => self.ench,
    };
  }
}

class Container {
  constructor(size) {
    this.size = size;
    this.items = new Array(size).fill(undefined);
  }
  getItem(i) {
    return this.items[i];
  }
  setItem(i, item) {
    if (i < 0 || i >= this.size) throw new Error("slot");
    this.items[i] = item;
  }
  addItem(item) {
    const i = this.items.findIndex((x) => !x);
    if (i >= 0) this.items[i] = item;
  }
  clearAll() {
    this.items.fill(undefined);
  }
}

class Block {
  constructor(dim, location) {
    this.dimension = dim;
    this.location = location;
  }
  setPermutation() {
    state.blockOps++;
  }
  setType() {
    state.blockOps++;
  }
}

class Entity {
  constructor(typeId, location) {
    this.id = String(state.nextId++);
    this.typeId = typeId;
    this.location = { ...location };
    this.tags = new Set();
    this.nameTag = "";
    this.isValid = true;
  }
  hasTag(t) {
    return this.tags.has(t);
  }
  addTag(t) {
    this.tags.add(t);
  }
  removeTag(t) {
    this.tags.delete(t);
  }
  teleport(loc) {
    this.location = { ...loc };
  }
  remove() {
    this.isValid = false;
    state.entities = state.entities.filter((e) => e !== this);
  }
}

export class Player extends Entity {
  constructor(name) {
    super("minecraft:player", { x: 0, y: 101, z: 5 });
    this.name = name;
    this.gm = "Adventure";
    this.effects = new Map();
    this.inv = new Container(36);
    this.equip = {};
    this.hp = 20;
    this.titles = [];
    this.bars = [];
    this.messages = [];
    this.sounds = [];
    const self = this;
    this.onScreenDisplay = {
      setTitle: (t, o) => self.titles.push(t + (o?.subtitle ? " / " + o.subtitle : "")),
      setActionBar: (t) => self.bars.push(t),
    };
  }
  getComponent(name) {
    const self = this;
    if (name === "minecraft:inventory") return { container: this.inv };
    if (name === "minecraft:equippable") return {
      setEquipment: (s, i) => (self.equip[s] = i),
      getEquipment: (s) => self.equip[s],
    };
    if (name === "minecraft:health") return {
      get currentValue() {
        return self.hp;
      },
      effectiveMax: 20,
      resetToMaxValue: () => (self.hp = 20),
      setCurrentValue: (v) => (self.hp = v),
    };
    return undefined;
  }
  addEffect(id, duration, o) {
    if (o.amplifier > 255) throw new Error("amp");
    this.effects.set(id, o.amplifier);
  }
  removeEffect(id) {
    this.effects.delete(id);
  }
  getEffects() {
    return [...this.effects.keys()].map((typeId) => ({ typeId }));
  }
  extinguishFire() {}
  setGameMode(g) {
    if (!g) throw new Error("gamemode undefined");
    this.gm = g;
  }
  getGameMode() {
    return this.gm;
  }
  sendMessage(m) {
    this.messages.push(m);
  }
  playSound(id) {
    this.sounds.push(id);
  }
  runCommand(c) {
    state.commands.push(`${this.name}: ${c}`);
    return { successCount: 1 };
  }
  setSpawnPoint() {}
}

const dimension = {
  id: "minecraft:overworld",
  getBlock: (loc) => new Block(dimension, loc),
  fillBlocks: (vol, perm) => {
    if (!(vol instanceof BlockVolume) || !perm) throw new Error("fill");
    state.blockOps++;
  },
  runCommand: (c) => {
    state.commands.push(c);
    return { successCount: 1 };
  },
  getEntities: (q = {}) => state.entities.filter((e) => (!q.type || e.typeId === q.type)),
  spawnEntity: (id, loc) => {
    const e = new Entity(id, loc);
    state.entities.push(e);
    return e;
  },
};

class Objective {
  constructor(id) {
    this.id = id;
    this.scores = new Map();
  }
  hasParticipant(p) {
    return this.scores.has(p.id ?? p);
  }
  setScore(p, v) {
    this.scores.set(p.id ?? p, v);
  }
  addScore(p, v) {
    this.scores.set(p.id ?? p, (this.scores.get(p.id ?? p) ?? 0) + v);
  }
}
const objectives = new Map();

export const world = {
  afterEvents: Object.fromEntries(["worldLoad", "playerSpawn", "entityDie", "entityHurt", "playerLeave", "playerBreakBlock",
    "playerPlaceBlock", "blockExplode", "itemUse"].map((k) => [k, new Signal()])),
  beforeEvents: { playerBreakBlock: new Signal() },
  getDimension: () => dimension,
  getPlayers: () => state.players.filter((p) => p.isValid),
  getAllPlayers: () => state.players.filter((p) => p.isValid),
  getEntity: (id) => state.players.find((p) => p.id === id && p.isValid) ?? state.entities.find((e) => e.id === id),
  sendMessage: (m) => log.push(m),
  getDynamicProperty: (k) => state.dyn[k],
  setDynamicProperty: (k, v) => {
    if (typeof v === "string" && v.length > 32767) throw new Error("too long");
    if (v === undefined) delete state.dyn[k];
    else state.dyn[k] = v;
  },
  setDefaultSpawnLocation() {},
  scoreboard: {
    getObjective: (id) => objectives.get(id),
    addObjective: (id) => {
      const o = new Objective(id);
      objectives.set(id, o);
      return o;
    },
    removeObjective: (id) => objectives.delete(id),
    setObjectiveAtDisplaySlot() {},
    clearObjectiveAtDisplaySlot() {},
  },
};

export function join(name) {
  const p = new Player(name);
  state.players.push(p);
  world.afterEvents.playerSpawn.fire({ player: p, initialSpawn: true });
  return p;
}

export function kill(p, killer) {
  p.hp = 0;
  world.afterEvents.entityDie.fire({ deadEntity: p, damageSource: { damagingEntity: killer, cause: "entityAttack" } });
  system.runTimeout(() => {
    p.hp = 20;
    p.location = { x: 0.5, y: 101, z: 5.5 };
    world.afterEvents.playerSpawn.fire({ player: p, initialSpawn: false });
  }, 2);
}

export function leave(p) {
  p.isValid = false;
  world.afterEvents.playerLeave.fire({ playerId: p.id, playerName: p.name });
}
