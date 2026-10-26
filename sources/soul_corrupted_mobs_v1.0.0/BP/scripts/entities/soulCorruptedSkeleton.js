import { world } from "@minecraft/server";

const SOUL_CORRUPTED_SKELETON = "eu_sc:soul_corrupted_skeleton";
const ARROW = "minecraft:arrow";
const LIGHTNING_BOLT = "minecraft:lightning_bolt";

function isSoulCorruptedSkeletonArrow(event) {
  return (
    event.projectile.typeId === ARROW &&
    event.source?.typeId === SOUL_CORRUPTED_SKELETON
  );
}

function summonLightningOnImpact(event) {
  if (!isSoulCorruptedSkeletonArrow(event)) return;

  event.projectile.remove();
  event.dimension.spawnEntity(LIGHTNING_BOLT, event.location);
}

world.afterEvents.projectileHitEntity.subscribe(summonLightningOnImpact);
world.afterEvents.projectileHitBlock.subscribe(summonLightningOnImpact);
