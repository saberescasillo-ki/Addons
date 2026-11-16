// Validates every block id / state used by the addon against @minecraft/vanilla-data typings.
// usage: node check_blocks.mjs <path to vanilla-data/lib/mojang-block.d.ts>
import fs from "node:fs";
import * as D from "../../MoogsPaths_BP/scripts/data.js";
const dts = fs.readFileSync(process.argv[2], "utf8");
const ids = new Set([...dts.matchAll(/= "minecraft:([a-z0-9_]+)"/g)].map((m) => m[1]));
const stateOf = (pascal) => {
  const m = dts.match(new RegExp(`export type ${pascal}States = Pick<BlockStateSuperset,([^>]*)>`));
  return m ? [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1]) : [];
};
const superset = {};
const sup = dts.match(/export type BlockStateSuperset = \{([\s\S]*?)\n\};/)[1];
for (const m of sup.matchAll(/\['([^']+)'\]\?:\s*([^;]+);/g)) superset[m[1]] = m[2];
const pascal = (n) => n.split("_").map((p) => p[0].toUpperCase() + p.slice(1)).join("");
let bad = 0;
const check = (name, states = {}) => {
  if (!name) return;
  const n = name.replace("minecraft:", "");
  if (!ids.has(n)) { bad++; return console.log("UNKNOWN BLOCK", n); }
  const allowed = stateOf(pascal(n));
  for (const [k, v] of Object.entries(states)) {
    if (!allowed.includes(k)) { bad++; console.log("BAD STATE", n, k, "allowed:", allowed.join(",")); continue; }
    const t = superset[k];
    const ok = t.trim() === typeof v;
    if (!ok) { bad++; console.log("BAD VALUE", n, k, v, "type:", t); }
  }
};
for (const p of D.PALETTE) check(p.n, p.s);
for (const t of Object.values(D.PATH_TYPES)) {
  check(t.fill);
  for (const l of [t.surface, t.edge, t.water?.surface ?? [], t.water?.edge ?? []]) for (const [b] of l) check(b);
}
for (const b of Object.values(D.BUSH_SETS)) for (const [n] of b.blocks) check(n, /leaves/.test(n) ? { persistent_bit: true } : {});
const gen = fs.readFileSync(new URL("../../MoogsPaths_BP/scripts/gen.js", import.meta.url), "utf8");
for (const m of gen.matchAll(/p: \[([^\]]+)\]/g)) for (const q of m[1].matchAll(/"([a-z_]+)"/g)) check(q[1]);
for (const m of gen.matchAll(/perm\("minecraft:([a-z_]+)"\)/g)) check(m[1]);
console.log(bad ? `${bad} problems` : `all blocks and states valid (${ids.size} known ids)`);
