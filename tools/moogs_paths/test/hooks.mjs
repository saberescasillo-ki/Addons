export async function resolve(spec, ctx, next) {
  if (spec === "@minecraft/server") return { url: new URL("./mock-server.mjs", import.meta.url).href, shortCircuit: true };
  return next(spec, ctx);
}
