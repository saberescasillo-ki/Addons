// Natura PvP: structures for the hunting maps. Both sides can use them: they
// cannot be broken, but they have ladders to climb, places to hide and a chest
// (the script fills it with loot when a hunt starts).
// y = 0 is the ground level of the structure (its floor replaces the ground).
import { hash, makeStamp } from "./core.js";

// A wooden watchtower with a ladder up to a lookout deck.
export const watchtower = (wood = "spruce", planks = "planks") => makeStamp(({ set, box, marker }) => {
  box(-2, 0, -2, 2, 0, 2, "sbrick");
  for (const [x, z] of [[-2, -2], [2, -2], [-2, 2], [2, 2]]) box(x, 1, z, x, 19, z, wood);
  box(0, 1, 0, 0, 15, 0, wood); // the post that holds the ladder
  box(0, 1, 1, 0, 16, 1, "ladderN");
  box(-2, 16, -2, 2, 16, 2, planks);
  set(0, 16, 1, "ladderN");
  set(0, 16, 0, wood);
  for (let i = -1; i <= 1; i++) {
    set(i, 17, -2, "sfence");
    set(i, 17, 2, i === 0 ? "air" : "sfence");
    set(-2, 17, i, "sfence");
    set(2, 17, i, "sfence");
  }
  box(-2, 20, -2, 2, 20, 2, "slab");
  set(0, 19, 0, "lantern");
  set(-1, 0, 3, "hay");
  set(1, 1, -3, "hay");
  marker(-1, 17, -1, "chest", { dir: "south" });
});

// A stone hideout half buried in the ground, with a door, windows and a chest.
export const hideout = (wall = "mcobble", roof = "moss", floor = "planks") => makeStamp(({ set, box, marker }) => {
  box(-3, -1, -3, 3, 0, 3, "sbrick");
  box(-3, 1, -3, 3, 3, 3, wall);
  box(-2, 0, -2, 2, 0, 2, floor);
  box(-2, 1, -2, 2, 3, 2, "air");
  box(-3, 4, -3, 3, 4, 3, roof);
  box(-2, 5, -2, 2, 5, 2, "air");
  set(0, 1, 3, "air");
  set(0, 2, 3, "air");
  set(-3, 2, 0, "air");
  set(3, 2, 0, "air");
  set(2, 1, -2, "lantern");
  for (let x = -3; x <= 3; x++) for (let z = -3; z <= 3; z++) if (hash(x, z, 701) < 0.35 && roof === "moss") set(x, 5, z, "tgrass");
  marker(0, 1, -2, "chest", { dir: "south" });
});

// A snow igloo with a tunnel entrance.
export const igloo = () => makeStamp(({ set, box, marker }) => {
  for (let x = -5; x <= 5; x++)
    for (let y = 0; y <= 5; y++)
      for (let z = -5; z <= 5; z++) {
        const d = Math.hypot(x, y * 1.15, z);
        if (y === 0 && d <= 4.2) set(x, 0, z, "snow");
        else if (d >= 3.1 && d <= 4.2) set(x, y, z, "snow");
        else if (d < 3.1 && y >= 1) set(x, y, z, "air");
      }
  box(-1, 1, 3, 1, 3, 5, "snow");
  box(0, 1, 3, 0, 2, 6, "air");
  set(0, 0, 4, "snow");
  set(0, 0, 5, "snow");
  set(2, 1, 0, "lantern");
  marker(0, 1, -2, "chest", { dir: "south" });
});

// A big oak with a platform and a ladder up the trunk.
export const treehouse = (leaf = "oakL") => makeStamp(({ set, box, marker }) => {
  box(0, 1, 0, 0, 15, 0, "oak");
  for (let x = -6; x <= 6; x++)
    for (let z = -6; z <= 6; z++)
      for (let y = 11; y <= 19; y++) {
        const d = Math.hypot(x, (y - 15) * 1.4, z);
        if (d <= 5.4 && !(d > 4.4 && hash(x * 7 + y, z, 702) < 0.3) && !(x === 0 && z === 0 && y <= 15)) set(x, y, z, leaf);
      }
  for (let x = -3; x <= 3; x++)
    for (let z = -3; z <= 3; z++) {
      if (Math.hypot(x, z) > 3.3 || (x === 0 && z === 0)) continue;
      set(x, 8, z, "oplanks");
      if (Math.hypot(x, z) > 2.4) set(x, 9, z, "fence");
      for (let y = 9; y <= 11; y++) if (Math.hypot(x, z) <= 2.4) set(x, y, z, "air");
    }
  box(0, 1, 1, 0, 8, 1, "ladderN");
  set(0, 9, 3, "air");
  set(0, 9, 1, "air");
  set(-1, 9, -1, "lantern");
  for (const [x, z] of [[1, 0], [-1, 0], [0, -1]]) set(x, 1, z, x ? "oak_x" : "oak_z");
  marker(2, 9, 0, "chest", { dir: "west" });
});

// The old stone tower: hollow, a ladder inside and a deck with battlements.
export const stoneTower = () => makeStamp(({ set, box, marker }) => {
  box(-3, 0, -3, 3, 0, 3, "sbrick");
  for (let x = -3; x <= 3; x++)
    for (let z = -3; z <= 3; z++) {
      if (Math.abs(x) !== 3 && Math.abs(z) !== 3) {
        box(x, 1, z, x, 21, z, "air");
        continue;
      }
      for (let y = 1; y <= 22; y++) set(x, y, z, hash(x * 5 + y, z, 703) < 0.45 ? "msbrick" : hash(x, y * 3 + z, 704) < 0.15 ? "cbrick" : "sbrick");
      if ((Math.abs(x) + Math.abs(z)) % 2 === 0) set(x, 23, z, "msbrick");
    }
  box(0, 1, 3, 0, 2, 3, "air");
  for (const y of [7, 14, 19]) {
    set(-3, y, 0, "air");
    set(3, y, 0, "air");
    set(0, y, 3, "air");
  }
  box(-2, 22, -2, 2, 22, 2, "planks");
  box(-2, 11, -2, 2, 11, 2, "planks");
  box(0, 11, -2, 0, 11, -2, "ladderN");
  box(0, 1, -2, 0, 22, -2, "ladderN");
  set(2, 12, 2, "lantern");
  set(-2, 23, 2, "lantern");
  marker(1, 23, 1, "chest", { dir: "north" });
  marker(-1, 12, 1, "chest", { dir: "north" });
});

// A wooden bridge `len` blocks long along z (centered), deck at y = 0.
export const bridge = (len) => makeStamp(({ set, box }) => {
  const h = Math.floor(len / 2);
  box(-1, 0, -h, 1, 0, h, "planks");
  for (let z = -h; z <= h; z++) {
    set(-2, 1, z, "sfence");
    set(2, 1, z, "sfence");
    set(-2, 0, z, "spruce_z");
    set(2, 0, z, "spruce_z");
    if (z % 6 === 0) {
      set(-2, 2, z, "lantern");
      set(2, 2, z, "sfence");
    }
  }
});

// A small spruce cabin (for the snowy map).
export const cabin = () => hideout("planks", "snow", "oplanks");
