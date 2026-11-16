// Tiny stand-in for @minecraft/server: a noise heightmap world, enough to run the addon outside the game.
const blocks = new Map();
const K = (x, y, z) => `${x},${y},${z}`;
const noise = (x, z) => Math.sin(x / 37) * 6 + Math.cos(z / 29) * 5 + Math.sin((x + z) / 90) * 9 + Math.sin(x / 11 + z / 13) * 1.5;
export const SEA = 62;
export const heightAt = (x, z) => Math.round(66 + noise(x, z));
const natural = (x, y, z) => {
  const h = heightAt(x, z);
  if (y <= h) return y === h && h >= SEA ? "minecraft:grass_block" : "minecraft:dirt";
  if (y <= SEA) return "minecraft:water";
  if (y === h + 1 && (x * 7 + z * 13) % 11 === 0) return "minecraft:short_grass";
  return "minecraft:air";
};
export const typeAt = (x, y, z) => blocks.get(K(x, y, z)) ?? natural(x, y, z);
export const stats = { sets: 0, placed: blocks, loadedRadius: 96, center: { x: 0, z: 0 }, props: new Map(), messages: [] };
const isLoaded = (x, z) => Math.max(Math.abs((x >> 4) - (stats.center.x >> 4)), Math.abs((z >> 4) - (stats.center.z >> 4))) <= stats.loadedRadius >> 4;
const block = (x, y, z) => ({
  x, y, z, get typeId() { return typeAt(x, y, z); }, below: () => block(x, y - 1, z),
  getComponent: () => ({ setText() {} }),
});
export const dimension = {
  id: "minecraft:overworld",
  getTopmostBlock({ x, z }) { if (!isLoaded(x, z)) throw new Error("unloaded"); for (let y = 100; y > 0; y--) if (typeAt(x, y, z) !== "minecraft:air") return block(x, y, z); },
  getBlock({ x, y, z }) { return isLoaded(x, z) ? block(x, y, z) : undefined; },
  setBlockPermutation({ x, y, z }, p) { if (!isLoaded(x, z)) throw new Error("unloaded"); if (!Number.isInteger(x + y + z)) throw new Error("non-integer position"); stats.sets++; blocks.set(K(x, y, z), p.name); },
  getBiome({ x, z }) { return { id: heightAt(x, z) < SEA - 3 ? "minecraft:ocean" : "minecraft:plains" }; },
  isChunkLoaded({ x, z }) { return isLoaded(x, z); },
  getEntities() { return []; },
};
export const BlockPermutation = { resolve: (name, states) => { if (!/^minecraft:[a-z_]+$/.test(name)) throw new Error("bad " + name); return { name, states }; } };
const player = { dimension, get location() { return { x: stats.center.x, y: 70, z: stats.center.z }; }, sendMessage(m) { stats.messages.push(m); } };
const handlers = {};
export const world = {
  seed: "12345",
  getDimension: () => dimension, getPlayers: () => [player], sendMessage(m) { stats.messages.push(m); },
  getDynamicProperty: (k) => stats.props.get(k), setDynamicProperty: (k, v) => v === undefined ? stats.props.delete(k) : stats.props.set(k, v),
  getDynamicPropertyIds: () => [...stats.props.keys()],
  afterEvents: { worldLoad: { subscribe: (f) => (handlers.load = f) } },
};
export const system = {
  currentTick: 0,
  runInterval: (f) => (handlers.tick = f),
  runJob(gen) { handlers.job = gen; },
  afterEvents: { scriptEventReceive: { subscribe: (f) => (handlers.script = f) } },
};
export const driver = { handlers, player };
