"""Optimises and fixes The Everything Update Remastered (v1.6.5 Hotfix 1), for personal use:
the packs go to the git-ignored private/ folder (the add-on is not ours to share).

    python3 tools/teu_opt.py RES.mcpack BEH.mcpack      (or one .mcaddon, or a folder)

Output: private/TEU_Opt_BP, private/TEU_Opt_RP and one private/TEU_Opt.mcaddon.

Optimisations (same look and behaviour as far as possible):
  * tick.json summoned an entity next to every player every tick only to look at their
    armour, hands and the block they stand in: tools/teu/ticks.js does the same checks
    and runs the same commands (as .mcfunction files) without creating any entity;
  * the biome ambience entity was summoned every tick and 4 of 5 were removed at once:
    now one every 5 ticks, all of them kept;
  * moons.js ran "event entity @e[type=mechanic:meteor_shower] spawn_meteor" every tick
    for every player on the meteor-shower night (its own comment says every second):
    now every second, once; the meteor-shower markers spawn 32 at a time, not 256;
  * the meteor spawner (spawned all over the Overworld, 500 of 501 removed at once)
    spawns 10 times less and drops a meteor 10 times more often: the same meteors;
  * the wind (spawned as a mob all over the Overworld, 100 of 101 removed at once,
    with its sounds and particle) is gone;
  * leaves no longer vanish in the distance (alpha_test -> alpha_test_to_opaque);
  * the forests' leaf-litter removal and the wasteland's dead grass picked a random height
    over 17 and 100 blocks: they aim at the surface, with as many tries as were landing.
Fixes: ten JSON files with a missing comma, brace, quote or a broken first line,
custom biomes whose replace_biomes targets carried "minecraft:" (targets must not
have a namespace, so the biome never generated), legacy blocks.json textures for blocks
with their own geometry (a warning per block), block loot tables that do not exist.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeons_mobs as dm  # noqa: E402
import natures_touch_opt as nto  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "natures_touch"))
import separate  # noqa: E402
from dungeons_mobs import load, dump, read  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "TEU_Opt_BP")
RP = os.path.join(OUT, "TEU_Opt_RP")
MCADDON = os.path.join(OUT, "TEU_Opt.mcaddon")
TICKS_JS = os.path.join(HERE, "teu", "ticks.js")
AMBIENCE_EVERY = 5      # the ambience entity survived 1 time in 5
SPAWNER_DIV = 10        # meteor spawner: 10 times fewer, each 10 times likelier
SHOWER_DENSITY = 32
FN = "teu_opt"          # folder of the generated functions


def files(root, folder, ext=".json"):
    for r, _, fs in os.walk(os.path.join(root, folder)):
        for f in sorted(fs):
            if f.endswith(ext):
                yield os.path.join(r, f)


def by_id(root, folder, key, ident):
    for p in files(root, folder):
        try:
            d = load(p)
        except ValueError:
            continue
        if d.get(key, {}).get("description", {}).get("identifier") == ident:
            return p, d
    raise SystemExit(f"no encuentro {ident}")


# --- broken JSON ------------------------------------------------------------------------------
def fix_json():
    """Missing commas are inserted where the parser expects one; the rest by hand."""
    fixed = []
    for root in (BP, RP):
        for p in files(root, ""):
            try:
                load(p)        # comments and trailing commas are fine for the game
                continue
            except ValueError:
                pass
            raw = read(p)
            text = raw.replace("\r\n", "\n")
            text = re.sub(r'^"//[^\n]*\n', "", text)                                   # '"//bridge-file-version'
            text = re.sub(r'("format_version"\s*:\s*)(\d+\.\d+\.\d+)', r'\1"\2"', text)  # unquoted version
            text = re.sub(r'("value": "pale_plains")(\s*)\]', r'\1}\2]', text)          # missing brace
            text = dm._strip(text)
            for _ in range(20):
                try:
                    json.loads(text)
                    break
                except json.JSONDecodeError as e:
                    if not e.msg.startswith("Expecting ',' delimiter"):
                        raise SystemExit(f"{p}: {e}")
                    i = e.pos - 1
                    while text[i].isspace():
                        i -= 1
                    text = text[:i + 1] + "," + text[i + 1:]
            else:
                raise SystemExit(f"{p}: no se puede arreglar")
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            fixed.append(os.path.relpath(p, OUT))
    print(f"  JSON roto arreglado: {len(fixed)} archivos")
    for f in fixed:
        print("    " + f)


# --- tick.json -> script ----------------------------------------------------------------------
SELECTOR = re.compile(r"@[prae]\[r=1\.2(\]|,)")


def as_player(cmd):
    """Commands of an entity standing next to the player, run by the player itself."""
    out = SELECTOR.sub(lambda m: "@s" if m.group(1) == "]" else "@s[", cmd).lstrip("/")
    if "r=1.2" in out:
        raise SystemExit(f"selector sin convertir: {cmd}")
    return out


def commands(event):
    if not isinstance(event, (dict, list)):
        return []
    if isinstance(event, list):
        return [c for x in event for c in commands(x)]
    out = []
    qc = event.get("queue_command", {}).get("command")
    if qc:
        out += [qc] if isinstance(qc, str) else qc
    for k in ("sequence", "randomize"):
        out += commands(event.get(k, []))
    return out


def write_fn(name, cmds):
    path = os.path.join(BP, "functions", FN, name + ".mcfunction")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(as_player(c) for c in cmds) + "\n")
    return f"{FN}/{name}"


def ticks():
    tick = os.path.join(BP, "functions", "tickingthing.mcfunction")
    lines = read(tick).splitlines()
    keep = [l for l in lines if "summon mechanic:biome_ambience_tif" not in l and "summon mechanic:equipment_commands" not in l]
    assert len(keep) == len(lines) - 2, "tickingthing cambió"
    with open(tick, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(keep) + "\n")

    path, d = by_id(BP, "entities", "minecraft:entity", "mechanic:equipment_commands")
    e = d["minecraft:entity"]
    events = e["events"]
    sensors = []
    for s in e["components"]["minecraft:entity_sensor"]["subsensors"]:
        ev = events[s["event"]]
        assert set(ev) == {"queue_command"}, s["event"]
        sensors.append({"f": s["event_filters"], "fn": write_fn("equip_" + s["event"], commands(ev))})
    spawned = events["minecraft:entity_spawned"]["sequence"][0]
    always = write_fn("equip_always", commands(spawned))
    os.remove(path)

    path, d = by_id(BP, "entities", "minecraft:entity", "mechanic:biome_ambience_tif")
    ev = d["minecraft:entity"]["events"]
    assert ev["minecraft:entity_spawned"] == {"randomize": [{"add": {"component_groups": ["despawn"]}, "weight": 4}, {"weight": 1}]}
    del ev["minecraft:entity_spawned"]
    dump(path, d)

    js = read(TICKS_JS).replace("__SENSORS__", json.dumps(sensors, separators=(",", ":"))) \
        .replace("__ALWAYS__", always).replace("__AMBIENCE_EVERY__", str(AMBIENCE_EVERY))
    with open(os.path.join(BP, "scripts", "teu_ticks.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    main = os.path.join(BP, "scripts", "main.js")
    text = read(main).rstrip() + "\nimport 'teu_ticks'\n"
    with open(main, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"  tick: {len(sensors)} comprobaciones de equipo por script, ambiente cada {AMBIENCE_EVERY} ticks")


# --- meteors -------------------------------------------------------------------------------------
def meteors():
    moons = os.path.join(BP, "scripts", "moons.js")
    text = read(moons)
    old = """    for (const player of world.getPlayers()) {
        player.runCommand(COMMAND);
    }
}, 0);"""
    assert old in text, "moons.js cambió"
    text = text.replace(old, """    try {
        world.getDimension("overworld").runCommand(COMMAND);
    } catch {
        // no meteor shower markers loaded
    }
}, 20);""")
    with open(moons, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    p, d = by_id(BP, "spawn_rules", "minecraft:spawn_rules", "mechanic:meteor_shower")
    for c in d["minecraft:spawn_rules"]["conditions"]:
        if "minecraft:density_limit" in c:
            c["minecraft:density_limit"]["surface"] = min(c["minecraft:density_limit"].get("surface", 0), SHOWER_DENSITY)
    dump(p, d)

    p, d = by_id(BP, "spawn_rules", "minecraft:spawn_rules", "mechanic:meteor_spawner")
    for c in d["minecraft:spawn_rules"]["conditions"]:
        w = c["minecraft:weight"]
        w["default"] = max(1, round(w["default"] / SPAWNER_DIV))
    dump(p, d)
    p, d = by_id(BP, "entities", "minecraft:entity", "mechanic:meteor_spawner")
    opts = d["minecraft:entity"]["events"]["meteor_rng"]["randomize"]
    for o in opts:
        if o.get("weight", 1) >= 100:      # the "nothing happens" option
            o["weight"] = round(o["weight"] / SPAWNER_DIV)
    dump(p, d)
    print(f"  meteoritos: lluvia cada segundo (no cada tick), {SHOWER_DENSITY} marcadores como mucho, "
          f"generador {SPAWNER_DIV} veces menos frecuente con la misma cantidad de meteoritos")


# --- biomes -------------------------------------------------------------------------------------
def biomes():
    n = 0
    for p in files(BP, "biomes"):
        d = load(p)
        r = d.get("minecraft:biome", {}).get("components", {}).get("minecraft:replace_biomes")
        if not r:
            continue
        changed = False
        for x in r.get("replacements", []):
            new = [t.split(":", 1)[1] if t.startswith("minecraft:") else t for t in x.get("targets", [])]
            if new != x.get("targets"):
                x["targets"] = new
                changed = True
        if changed:
            dump(p, d)
            n += 1
    print(f"  biomas con destinos sin namespace (ahora se pueden generar): {n}")


# Surface replacements that picked a random height over many blocks (most tries landed in
# air or rock): they aim at the surface with as many tries as were landing there.
SURFACE = {
    "no_leaf_litter_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_dead_grass_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
}


def gen_average(bp):
    tags = separate.VANILLA_TAGS
    return sum(nto.gen_cost(bp, set(t)) for t in tags.values()) / len(tags)


def generation():
    feats = nto.Features(BP)
    before = gen_average(BP)
    for n, y in SURFACE.items():
        path = os.path.join(BP, "feature_rules", n)
        data = load(path)
        dist = data["minecraft:feature_rules"]["distribution"]
        f = feats.f[data["minecraft:feature_rules"]["description"]["places_feature"]][1]
        ext = dist["y"]["extent"]
        landing = nto.as_num(dist.get("iterations"), 1) * nto.blob_span(nto.as_num(f.get("count"), 1)) / max(1, ext[1] - ext[0])
        dist["y"] = y
        dist["iterations"] = max(1, int(-(-landing * 1.25 // 1)))
        dump(path, data)
    after = gen_average(BP)
    print(f"  generación (zonas vanilla, por chunk): {before:.0f} -> {after:.0f} ({(after / before - 1) * 100:+.0f} %)")


def manifests():
    for pack in (BP, RP):
        def f(m):
            m["header"]["name"] += " (optimizado)"
            v = m["header"]["version"]
            m["header"]["version"] = v[:2] + [v[2] + 1]
            for mod in m["modules"]:
                if mod.get("type") != "script":
                    mod["version"] = m["header"]["version"]
            for dep in m.get("dependencies", []):
                if "uuid" in dep:
                    dep["version"] = m["header"]["version"]
        nto.edit_json(os.path.join(pack, "manifest.json"), f)


def build(src_dir):
    src_bp, src_rp = dm.find_packs(src_dir)
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    nto.BP, nto.RP = BP, RP          # reuse its block fixes on these packs
    fix_json()
    ticks()
    meteors()
    separate.remove_wind(BP, RP, print)
    biomes()
    generation()
    separate.opaque_leaves(BP, print)
    nto.block_loot()
    nto.blocks_json()
    manifests()
    with zipfile.ZipFile(MCADDON, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pack in (BP, RP):
            for dirpath, dirs, fs in os.walk(pack):
                dirs.sort()
                for name in sorted(fs):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(full, OUT), date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for i, src in enumerate(sys.argv[1:]):
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(tmp, str(i)))
            else:
                nto.unpack(src, os.path.join(tmp, str(i)))
        build(tmp)


if __name__ == "__main__":
    main()
