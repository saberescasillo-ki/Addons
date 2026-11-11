// Dumps every segment of a region (for tools/natura_pvp.py --preview: the 3D views).
import { AREA } from "./gen/index.js";
import { writeFileSync } from "node:fs";
const [, , id, x0, z0, x1, z1, out] = process.argv;
const a = AREA[id];
const cols = [];
for (let x = +x0; x <= +x1; x++) for (let z = +z0; z <= +z1; z++) cols.push([x, z, a.column(x, z).filter((s) => s[2] !== "barrier")]);
writeFileSync(out, JSON.stringify(cols));
