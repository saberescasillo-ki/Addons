import { world, system } from "@minecraft/server";

system.afterEvents.scriptEventReceive.subscribe((event) => {
  const entity = event.sourceEntity;
  if (!entity) return;

  if (event.id === "terradraconis:nest_summon") {
    let summonType = entity.typeId.replace("_nest", "");
    const packSize = 4;
    const dimension = entity.dimension;
    const origin = entity.location;

    for (let i = 0; i < packSize; i++) {
      let gender = Math.random() < 0.5 ? "male" : "female";
      let summonEntity = `terradraconis:${gender}_${summonType.replace("terradraconis:","")}`;
    // Random offset: -2 to 2 in X and Z, Y stays the same
        const offsetX = (Math.random() * 4) - 2;
        const offsetZ = (Math.random() * 4) - 2;
        const spawnLocation = {
        x: origin.x + offsetX,
        y: origin.y,
        z: origin.z + offsetZ
        };

        try {
        dimension.spawnEntity(summonEntity, spawnLocation);
        } catch (e) {
        console.warn(`Failed to summon ${summonEntity} at random location:`, e);
        }
    }
  }

  if (!entity || event.id !== "terradraconis:bait_summon") return;

  const origin = entity.location;
  const dimension = entity.dimension;

  // Search nearby entities
  const nearbyEntities = dimension.getEntities({
    location: origin,
    maxDistance: 32
  });

  // Find the nearest nest entity
  let nearestNest = null;
  let nearestDistSq = Number.MAX_SAFE_INTEGER;

  for (const other of nearbyEntities) {
    const typeId = other.typeId;
    if (!typeId.startsWith("terradraconis:") || !typeId.endsWith("_nest")) continue;

    const dx = other.location.x - origin.x;
    const dy = other.location.y - origin.y;
    const dz = other.location.z - origin.z;
    const distSq = dx * dx + dy * dy + dz * dz;

    if (distSq < nearestDistSq) {
      nearestNest = other;
      nearestDistSq = distSq;
    }
  }

  if (!nearestNest) {
    console.warn("❌ No nearby nest entity found.");
    return;
  }

  // Derive entity type from nest
  const baseType = nearestNest.typeId.replace("terradraconis:", "").replace("_nest", "");
  const gender = Math.random() < 0.5 ? "male" : "female";
  const summonType = `terradraconis:${gender}_${baseType}`;

  try {
    dimension.spawnEntity(summonType, origin);
  } catch (e) {
    console.warn(`❌ Failed to summon ${summonType}:`, e);
  }
});