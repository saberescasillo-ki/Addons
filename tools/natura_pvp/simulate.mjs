// Runs gen.js in Node: checks every column and writes a top view of each area
// (JSON with the top block of every column) for tools/natura_pvp.py --preview.
import { AREAS, PALETTE } from "./gen/index.js";
import { writeFileSync } from "node:fs";

const out = {};
for (const a of AREAS) {
  let ops = 0, cols = 0;
  const w = a.x1 - a.x0 + 1, h = a.z1 - a.z0 + 1;
  const top = new Array(w * h).fill(null);
  const ys = new Array(w * h).fill(0);
  for (let x = a.x0; x <= a.x1; x++)
    for (let z = a.z0; z <= a.z1; z++) {
      const segs = a.column(x, z);
      cols++;
      let best = null, by = -1;
      for (const [y0, y1, k] of segs) {
        ops++;
        if (!(k in PALETTE)) throw new Error(`${a.id}: bloque ${k}`);
        if (!(y0 <= y1) || !Number.isInteger(y0) || !Number.isInteger(y1)) throw new Error(`${a.id}: ${x},${z} ${y0}..${y1} ${k}`);
        if (k === "air" && by >= y0 && by <= y1) { by = y0 - 1; best = null; }
        else if (k !== "barrier" && k !== "air" && y1 >= by) { by = y1; best = k; }
      }
      top[(z - a.z0) * w + (x - a.x0)] = best;
      ys[(z - a.z0) * w + (x - a.x0)] = by;
    }
  out[a.id] = { x0: a.x0, z0: a.z0, w, h, top, ys };
  console.log(`${a.id}: ${cols} columnas, ${ops} operaciones`);
}
if (process.argv[2]) writeFileSync(process.argv[2], JSON.stringify(out));
