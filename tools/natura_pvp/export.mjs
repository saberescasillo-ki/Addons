// Writes every column of every area, for the world writer (tools/natura_pvp/world.py).
//   node export.mjs <out-dir>
// <out-dir>/areas.json: [{ id, x0, z0, x1, z1, file }] and the palette keys;
// <id>.bin: per column int32 x, int32 z, uint16 n, then n x (int16 y0, int16 y1, uint16 key).
import { AREAS, PALETTE } from "./gen/index.js";
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const out = process.argv[2];
const keys = Object.keys(PALETTE);
const keyIndex = new Map(keys.map((k, i) => [k, i]));
const list = [];
for (const a of AREAS) {
  const chunks = [];
  let size = 0;
  let buf = Buffer.alloc(1 << 20);
  let pos = 0;
  const ensure = (n) => {
    if (pos + n <= buf.length) return;
    chunks.push(buf.subarray(0, pos));
    size += pos;
    buf = Buffer.alloc(Math.max(1 << 20, n));
    pos = 0;
  };
  for (let x = a.x0; x <= a.x1; x++)
    for (let z = a.z0; z <= a.z1; z++) {
      const segs = a.column(x, z);
      if (!segs.length) continue;
      ensure(10 + segs.length * 6);
      buf.writeInt32LE(x, pos); buf.writeInt32LE(z, pos + 4); buf.writeUInt16LE(segs.length, pos + 8);
      pos += 10;
      for (const [y0, y1, k] of segs) {
        if (!keyIndex.has(k)) throw new Error(`${a.id}: ${k}`);
        buf.writeInt16LE(y0, pos); buf.writeInt16LE(y1, pos + 2); buf.writeUInt16LE(keyIndex.get(k), pos + 4);
        pos += 6;
      }
    }
  chunks.push(buf.subarray(0, pos));
  writeFileSync(join(out, `${a.id}.bin`), Buffer.concat(chunks));
  list.push({ id: a.id, x0: a.x0, z0: a.z0, x1: a.x1, z1: a.z1, file: `${a.id}.bin` });
}
writeFileSync(join(out, "areas.json"), JSON.stringify({ keys, palette: PALETTE, areas: list }));
