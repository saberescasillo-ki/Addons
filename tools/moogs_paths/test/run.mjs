// node --import ./register.mjs run.mjs  -> runs main.js against the mock world and prints a map
import { stats, driver, typeAt, heightAt, SEA } from "./mock-server.mjs";
await import("../../../MoogsPaths_BP/scripts/main.js");
const { handlers, player } = driver;
handlers.load();
const pump = () => { for (let i = 0; handlers.job && i < 1e6; i++) { const j = handlers.job; if (j.next().done && handlers.job === j) handlers.job = null; } };
handlers.script({ id: "moogs:path", message: process.argv[2] ?? "", sourceEntity: player });
handlers.script({ id: "moogs:path", message: "desert_highway", sourceEntity: player });
// the player walks east; chunks load around them
for (let step = 0; step < 500; step++) { stats.center.x = step * 2; stats.center.z = Math.round(Math.sin(step / 40) * 60); handlers.tick(); pump(); }
handlers.script({ id: "moogs:info", message: "", sourceEntity: player });
console.log(stats.messages.join("\n").replace(/§./g, ""));
const kinds = {};
for (const v of stats.placed.values()) kinds[v] = (kinds[v] ?? 0) + 1;
console.log("blocks set:", stats.sets, JSON.stringify(kinds));
console.log("dynamic properties:", stats.props.size, [...stats.props.keys()].filter((k) => k.includes(":p:")));
const xs = [], zs = [];
for (const k of stats.placed.keys()) { const [x, , z] = k.split(",").map(Number); xs.push(x); zs.push(z); }
const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
console.log(`extent x ${x0}..${x1} z ${z0}..${z1}`);
const top = new Map();
for (const [k, v] of stats.placed) { const [x, y, z] = k.split(",").map(Number); const q = x + "," + z; if (v !== "minecraft:air" && !(top.get(q)?.y > y)) top.set(q, { y, v }); }
const ch = (v) => /leaves/.test(v) ? "&" : /lantern|torch|lamp|candle/.test(v) ? "*" : /log|fence|wall|slab|planks?$/.test(v) ? "+" : /dandelion|poppy|bluet|daisy|cornflower|tulip|allium|grass$|deadbush|fern/.test(v) ? "'" : /podzol|grass_block/.test(v) ? ":" : "#";
let dh = {}; for (const [q, t] of top) { const [x, z] = q.split(",").map(Number); if (ch(t.v) === "#" || ch(t.v) === ":") { const d = t.y - Math.max(heightAt(x, z), SEA); dh[d] = (dh[d] ?? 0) + 1; } }
console.log("path surface height vs terrain:", JSON.stringify(dh));
const S = 1;
const [wx, wz] = (process.argv[3] ?? `${x0},${z0}`).split(",").map(Number);
for (let z = wz; z <= wz + 62; z += S) {
  let row = "";
  for (let x = wx; x <= wx + 165; x += S) { const t = top.get(x + "," + z); row += t ? ch(t.v) : heightAt(x, z) < SEA ? "~" : " "; }
  console.log(row.replace(/\s+$/, ""));
}
