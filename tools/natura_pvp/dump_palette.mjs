// Prints the block ids the generator can use (for update_block_states in natura_pvp.py).
import { PALETTE } from "./gen/index.js";
console.log(JSON.stringify(Object.fromEntries(Object.entries(PALETTE).map(([k, v]) => [k, v]))));
