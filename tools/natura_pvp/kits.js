// Natura PvP: the kits. The admins can replace them with their own inventory.
import * as mc from "@minecraft/server";

const { ItemStack, world } = mc;

// slot: 0..35 (inventory) or head / chest / legs / feet / offhand
const DIAMOND_FULL = [
  { slot: "head", id: "minecraft:diamond_helmet", ench: { protection: 4, unbreaking: 3 } },
  { slot: "chest", id: "minecraft:diamond_chestplate", ench: { protection: 4, unbreaking: 3 } },
  { slot: "legs", id: "minecraft:diamond_leggings", ench: { protection: 4, unbreaking: 3 } },
  { slot: "feet", id: "minecraft:diamond_boots", ench: { protection: 4, feather_falling: 4, unbreaking: 3 } },
  { slot: "offhand", id: "minecraft:shield", ench: { unbreaking: 3 } },
  { slot: 0, id: "minecraft:diamond_sword", ench: { sharpness: 5, fire_aspect: 2, unbreaking: 3 } },
  { slot: 1, id: "minecraft:diamond_axe", ench: { sharpness: 5, unbreaking: 3 } },
  { slot: 2, id: "minecraft:bow", ench: { power: 5, punch: 1, flame: 1, infinity: 1, unbreaking: 3 } },
  { slot: 3, id: "minecraft:golden_apple", count: 8 },
  { slot: 4, id: "minecraft:cooked_beef", count: 32 },
  { slot: 9, id: "minecraft:arrow", count: 1 },
];

export const DEFAULT_KITS = {
  duel: {
    name: "Emparejamiento",
    desc: "Kit completo de diamante encantado.",
    items: DIAMOND_FULL,
  },
  campal: {
    name: "Campal",
    desc: "Kit de diamante encantado para la arena siempre activa.",
    items: [
      { slot: "head", id: "minecraft:diamond_helmet", ench: { protection: 3, unbreaking: 3 } },
      { slot: "chest", id: "minecraft:diamond_chestplate", ench: { protection: 3, unbreaking: 3 } },
      { slot: "legs", id: "minecraft:diamond_leggings", ench: { protection: 3, unbreaking: 3 } },
      { slot: "feet", id: "minecraft:diamond_boots", ench: { protection: 3, feather_falling: 3, unbreaking: 3 } },
      { slot: "offhand", id: "minecraft:shield" },
      { slot: 0, id: "minecraft:diamond_sword", ench: { sharpness: 4, unbreaking: 3 } },
      { slot: 1, id: "minecraft:bow", ench: { power: 3, unbreaking: 3 } },
      { slot: 2, id: "minecraft:golden_apple", count: 4 },
      { slot: 3, id: "minecraft:cooked_beef", count: 16 },
      { slot: 9, id: "minecraft:arrow", count: 32 },
    ],
  },
  hunter: {
    name: "Cazador",
    desc: "Kit de diamante de los cazadores, con utilidades para perseguir.",
    items: [
      { slot: "head", id: "minecraft:diamond_helmet" },
      { slot: "chest", id: "minecraft:diamond_chestplate" },
      { slot: "legs", id: "minecraft:diamond_leggings" },
      { slot: "feet", id: "minecraft:diamond_boots" },
      { slot: "offhand", id: "minecraft:shield" },
      { slot: 0, id: "minecraft:diamond_sword" },
      { slot: 1, id: "minecraft:bow" },
      { slot: 2, id: "minecraft:diamond_pickaxe" },
      { slot: 3, id: "minecraft:diamond_axe" },
      { slot: 4, id: "minecraft:shears" },
      { slot: 5, id: "minecraft:water_bucket" },
      { slot: 6, id: "minecraft:ender_pearl", count: 2 },
      { slot: 7, id: "minecraft:golden_apple", count: 3 },
      { slot: 8, id: "minecraft:oak_planks", count: 64 },
      { slot: 9, id: "minecraft:arrow", count: 24 },
      { slot: 10, id: "minecraft:cooked_beef", count: 32 },
      { slot: 11, id: "minecraft:ladder", count: 8 },
      { slot: 12, id: "minecraft:diamond_shovel" },
    ],
  },
  hunted: {
    name: "Cazado",
    desc: "Kit de hierro encantado con muchas utilidades para escapar; mejora con cada cazador extra.",
    items: [
      { slot: "head", id: "minecraft:iron_helmet", ench: { protection: 1 } },
      { slot: "chest", id: "minecraft:iron_chestplate", ench: { protection: 1 } },
      { slot: "legs", id: "minecraft:iron_leggings", ench: { protection: 1 } },
      { slot: "feet", id: "minecraft:iron_boots", ench: { protection: 1, feather_falling: 1 } },
      { slot: "offhand", id: "minecraft:shield" },
      { slot: 0, id: "minecraft:iron_sword", ench: { sharpness: 1 } },
      { slot: 1, id: "minecraft:bow", ench: { power: 1 } },
      { slot: 2, id: "minecraft:iron_pickaxe", ench: { efficiency: 2 } },
      { slot: 3, id: "minecraft:iron_axe", ench: { efficiency: 1 } },
      { slot: 4, id: "minecraft:web|minecraft:cobweb", count: 16 },
      { slot: 5, id: "minecraft:water_bucket" },
      { slot: 6, id: "minecraft:ender_pearl", count: 4 },
      { slot: 7, id: "minecraft:golden_apple", count: 3 },
      { slot: 8, id: "minecraft:oak_planks", count: 64 },
      { slot: 9, id: "minecraft:arrow", count: 32 },
      { slot: 10, id: "minecraft:cobblestone", count: 64 },
      { slot: 11, id: "minecraft:lava_bucket" },
      { slot: 12, id: "minecraft:cooked_beef", count: 32 },
      { slot: 13, id: "minecraft:iron_shovel", ench: { efficiency: 2 } },
      { slot: 14, id: "minecraft:shears" },
      { slot: 15, id: "minecraft:fishing_rod" },
      { slot: 16, id: "minecraft:ladder", count: 16 },
      { slot: 17, id: "minecraft:scaffolding", count: 16 },
      { slot: 18, id: "minecraft:snowball", count: 16 },
      { slot: 19, id: "minecraft:crossbow", ench: { quick_charge: 1 } },
      { slot: 20, id: "minecraft:water_bucket" },
      { slot: 21, id: "minecraft:web|minecraft:cobweb", count: 8 },
    ],
  },
};

export const KIT_IDS = Object.keys(DEFAULT_KITS);

// ------------------------------------------------------------ stored kits
const kitKey = (id) => `natura:kit:${id}`;

export function getKit(id) {
  const raw = world.getDynamicProperty(kitKey(id));
  if (typeof raw === "string") {
    try {
      const kit = JSON.parse(raw);
      if (Array.isArray(kit.items)) return { ...DEFAULT_KITS[id], ...kit, custom: true };
    } catch {}
  }
  return DEFAULT_KITS[id];
}

export function resetKit(id) {
  world.setDynamicProperty(kitKey(id), undefined);
}

// ------------------------------------------------------------ enchantments
const ARMOR = /_(helmet|chestplate|leggings|boots)$/;
const MELEE = /_(sword|axe)$/;

function clampLevel(type, level) {
  const max = type?.maxLevel ?? 5;
  return Math.max(1, Math.min(max, Math.round(level)));
}

function makeItem(spec) {
  let item;
  for (const id of spec.id.split("|")) {
    try {
      item = new ItemStack(id, Math.max(1, Math.min(255, spec.count ?? 1)));
      break;
    } catch {}
  }
  if (!item) return undefined;
  if (spec.name) item.nameTag = spec.name;
  if (spec.lore?.length) {
    try {
      item.setLore(spec.lore);
    } catch {}
  }
  const enchantable = spec.ench ? item.getComponent("minecraft:enchantable") : undefined;
  if (enchantable) {
    for (const [name, level] of Object.entries(spec.ench)) {
      try {
        const type = mc.EnchantmentTypes.get(name);
        if (!type) continue;
        const ench = { type, level: clampLevel(type, level) };
        if (enchantable.canAddEnchantment(ench)) enchantable.addEnchantment(ench);
      } catch {}
    }
  }
  return item;
}

// The hunted player's kit gets better with every extra hunter (bonus 0..3).
export function scaledHuntedKit(hunters) {
  const bonus = Math.max(0, Math.min(3, hunters - 1));
  const base = getKit("hunted");
  const items = base.items.map((s) => {
    const ench = { ...(s.ench ?? {}) };
    const add = (k, n) => (ench[k] = (ench[k] ?? 0) + n);
    if (bonus > 0) {
      if (ARMOR.test(s.id)) {
        add("protection", bonus);
        ench.unbreaking = Math.max(ench.unbreaking ?? 0, bonus);
        if (s.id.endsWith("_boots")) add("feather_falling", bonus);
      } else if (MELEE.test(s.id)) {
        add("sharpness", bonus);
        if (bonus >= 2) ench.fire_aspect = bonus - 1;
        if (bonus >= 3 && s.id.endsWith("_sword")) ench.knockback = 1;
        ench.unbreaking = Math.max(ench.unbreaking ?? 0, bonus);
      } else if (s.id === "minecraft:bow") {
        add("power", bonus);
        if (bonus >= 2) ench.infinity = 1;
        if (bonus >= 3) Object.assign(ench, { flame: 1, punch: 1 });
      } else if (s.id === "minecraft:shield") {
        ench.unbreaking = Math.max(ench.unbreaking ?? 0, bonus);
      }
    }
    // more apples, cobwebs and pearls with every extra hunter
    const per = { "minecraft:golden_apple": 2, "minecraft:web|minecraft:cobweb": 4, "minecraft:ender_pearl": 1 }[s.id] ?? 0;
    const count = per ? Math.min(64, (s.count ?? 1) + bonus * per) : s.count;
    return { ...s, ench, count };
  });
  if (bonus >= 3) items.push({ slot: 22, id: "minecraft:enchanted_golden_apple", count: 1 });
  // and some effects for the whole hunt
  const effects = [];
  if (bonus >= 2) effects.push({ id: "speed", amp: 0 });
  if (bonus >= 3) effects.push({ id: "health_boost", amp: 1 });
  return { ...base, items, effects, bonus };
}

// ------------------------------------------------------------ giving kits
const SLOTS = { head: "Head", chest: "Chest", legs: "Legs", feet: "Feet", offhand: "Offhand" };

export function clearPlayer(player) {
  try {
    player.getComponent("minecraft:inventory")?.container?.clearAll();
  } catch {}
  const eq = player.getComponent("minecraft:equippable");
  for (const s of Object.values(SLOTS)) {
    try {
      eq?.setEquipment(mc.EquipmentSlot[s], undefined);
    } catch {}
  }
}

export function giveKit(player, kit) {
  clearPlayer(player);
  const inv = player.getComponent("minecraft:inventory")?.container;
  const eq = player.getComponent("minecraft:equippable");
  for (const spec of kit.items) {
    const item = makeItem(spec);
    if (!item) continue;
    try {
      if (typeof spec.slot === "string") eq?.setEquipment(mc.EquipmentSlot[SLOTS[spec.slot]], item);
      else if (inv && spec.slot >= 0 && spec.slot < inv.size) inv.setItem(spec.slot, item);
      else inv?.addItem(item);
    } catch {}
  }
  for (const e of kit.effects ?? []) {
    try {
      player.addEffect(e.id, 20 * 60 * 60, { amplifier: e.amp, showParticles: false });
    } catch {}
  }
}

// ------------------------------------------------------------ saving an admin's inventory
function readItem(item, slot) {
  if (!item) return undefined;
  const spec = { slot, id: item.typeId };
  if (item.amount > 1) spec.count = item.amount;
  if (item.nameTag) spec.name = item.nameTag;
  try {
    const lore = item.getLore();
    if (lore?.length) spec.lore = lore;
  } catch {}
  try {
    const list = item.getComponent("minecraft:enchantable")?.getEnchantments() ?? [];
    if (list.length) spec.ench = Object.fromEntries(list.map((e) => [e.type.id.replace("minecraft:", ""), e.level]));
  } catch {}
  return spec;
}

export const MENU_LORE = "§8natura:menu";

export function saveKitFrom(player, id) {
  const items = [];
  const inv = player.getComponent("minecraft:inventory")?.container;
  const eq = player.getComponent("minecraft:equippable");
  for (const [slot, s] of Object.entries(SLOTS)) {
    try {
      const spec = readItem(eq?.getEquipment(mc.EquipmentSlot[s]), slot);
      if (spec) items.push(spec);
    } catch {}
  }
  for (let i = 0; i < (inv?.size ?? 0); i++) {
    const item = inv.getItem(i);
    let lore = [];
    try {
      lore = item?.getLore() ?? [];
    } catch {}
    if (!item || lore.includes(MENU_LORE)) continue;
    items.push(readItem(item, i));
  }
  if (!items.length) return 0;
  const json = JSON.stringify({ items });
  if (json.length > 30000) throw new Error("El kit es demasiado grande.");
  world.setDynamicProperty(kitKey(id), json);
  return items.length;
}

export function describeKit(kit) {
  const names = kit.items.map((s) => {
    const n = s.id.split("|")[0].replace("minecraft:", "").replace(/_/g, " ");
    const e = s.ench && Object.keys(s.ench).length ? ` (${Object.entries(s.ench).map(([k, v]) => `${k} ${v}`).join(", ")})` : "";
    return `§7- §f${s.count > 1 ? s.count + "x " : ""}${n}§8${e}`;
  });
  return names.join("\n");
}
