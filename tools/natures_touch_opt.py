"""Optimises and fixes Nature's Touch (v2.6.5 Hotfix 2), for personal use: the packs go to
the git-ignored private/ folder (the add-on is not ours to share).

    python3 tools/natures_touch_opt.py path/to/NaturesTouch.mcaddon

Optimisations (same look and behaviour as far as possible):
  * tick.json summoned an ambience entity EVERY tick (20 a second, everywhere) only
    for the Pale Garden haze: now one every 10 ticks per player, with a haze particle
    that emits 10 times more (tools/natures_touch/ambience.js);
  * the wind (a "monster" that spawned naturally all over the Overworld, 100 of 101
    vanishing at once, with its sounds) is gone;
  * fruit leaves, berry bushes, crops, petal leaves and the pale flower summoned an
    entity on every random tick: the script does the same job directly
    (tools/natures_touch/nature_ticks.js), no entity is created;
  * world generation: the surface replacements (dead grass, coarse dirt, no leaf
    litter, stone and cobblestone patches, moss, dead leaves) picked a random height
    over up to 320 blocks, so nearly every try landed in air or rock: they now aim at
    the surface (the heightmap) with as many tries as were actually landing there.
    Clovers, orchard flowers, grass and cotton make fewer tries, clovers nearby only.
Then tools/natures_touch/separate.py: custom biomes removed except the Lavender Forest
(and the Sand Savanna), the remakes and the Lavender Forest as separate biomes (vanilla
biomes back to vanilla), no mosquitoes, leaves that do not vanish in the distance.

Fixes: four JSON files with a missing comma or brace (pale grass and mushrooms never
generated), two feature rules placing features that do not exist (poplar leaf litter,
chorus lavender), unregistered block
components (redwood trapdoor, large green brick stairs) and a missing texture, events
and component groups that do not exist (bee, queen bee, mosquito, wasp), loot tables
that do not exist (raccoon, wasp), the phantom summoning a mob that does not exist, the
deer's death sound, the zombified pig's step sound (nested inside another sound), two
textures that do not exist, and the names of nine mobs.
"""
import json
import math
import os
import re
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dungeons_mobs as dm  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "natures_touch"))
import separate  # noqa: E402
from dungeons_mobs import load, dump, read  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "private")
BP = os.path.join(OUT, "NaturesTouchOpt_BP")
RP = os.path.join(OUT, "NaturesTouchOpt_RP")
MCADDON = os.path.join(OUT, "NaturesTouchOpt.mcaddon")
JS = os.path.join(HERE, "natures_touch")
AMBIENCE_EVERY = 10   # keep in step with ambience.js

# Surface replacements: feature rule -> y of the surface layer they change.
SURFACE = {
    "no_leaf_litter_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_coarse_dirt_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_coarse_dirt_2_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_coarse_dirt_3_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_dead_grass_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_grass_moss_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 1",
    "overworld_underground_stone_replace_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 2",
    "overworld_underground_stone_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 3",
    "overworld_underground_cobblestone_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 3",
    "dead_leaves_feature.json": "query.heightmap(variable.worldx, variable.worldz) - 2",
}
# Plain decoration: fewer tries.
FEWER = {"clovers_feature.json": 60, "warm_orchard_plants_feature.json": 60, "cold_orchard_plants_feature.json": 60,
         "grass_overworld_feature.json": 50, "cotton_feature.json": 50}
# Text fixes of broken JSON (file -> [(old, new)]).
TEXT_FIXES = {
    "features/pale_grass2_feature.json": [('"minecraft:pale_moss_block"\n', '"minecraft:pale_moss_block",\n')],
    "features/pale_mushroom2_feature.json": [('"minecraft:pale_moss_block"\n', '"minecraft:pale_moss_block",\n')],
    "feature_rules/pale_mushroom_feature.json": [(re.compile(r'("value": "pale_plains")(\s*)\]'), r'\1}\2]')],
    "feature_rules/grass_overworld_feature2.json": [(re.compile(r'("value": "redwood_forest")(\s*)\]'), r'\1}\2]')],
}
TEXTURE_FIXES = {"block_cherry_leaf_litter": "textures/blocks/block_pink_sakura_leaf_litter",
                 "block_giant_lillypad_placer": "textures/blocks/block_giant_lillypad"}
NAMES = {"mob:cluckshroom": "Cluckshroom", "mob:musk": "Musk", "mob:zombified_pig": "Zombified Pig", "mob:deer": "Deer",
         "mob:bird": "Bird", "mob:ruby_turtle": "Ruby Turtle", "mob:turkey": "Turkey", "mob:wasp": "Wasp", "mob:duck": "Duck"}


# --- cost model (how many block placements a chunk's generation tries) -----------------------
def blob_span(count):
    """Rough height of an ore blob of `count` blocks."""
    return max(2.0, 1.5 * count ** (1 / 3))


def chance(dist):
    sc = dist.get("scatter_chance", 100)
    if isinstance(sc, dict):
        return sc.get("numerator", 1) / max(1, sc.get("denominator", 1))
    try:
        return float(sc) / 100
    except (TypeError, ValueError):
        return 1.0


def as_num(v, default=1.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class Features:
    def __init__(self, bp):
        self.f = {}
        for r, _, fs in os.walk(os.path.join(bp, "features")):
            for n in fs:
                try:
                    d = load(os.path.join(r, n))
                except ValueError:
                    continue
                k = [x for x in d if x.startswith("minecraft:")][0]
                self.f[d[k]["description"]["identifier"]] = (k, d[k])

    def cost(self, ident, depth=0):
        if ident not in self.f or depth > 8:
            return 0.0
        kind, d = self.f[ident]
        if kind == "minecraft:ore_feature":
            return as_num(d.get("count"), 1)
        if kind == "minecraft:scatter_feature":
            return as_num(d.get("iterations"), 1) * chance(d) * self.cost(d.get("places_feature"), depth + 1)
        if kind == "minecraft:weighted_random_feature":
            fs = d.get("features", [])
            tot = sum(w for _, w in fs) or 1
            return sum(w * self.cost(f, depth + 1) for f, w in fs) / tot
        if kind in ("minecraft:aggregate_feature", "minecraft:sequence_feature"):
            return sum(self.cost(f, depth + 1) for f in d.get("features", []))
        if kind == "minecraft:structure_template_feature":
            return 50.0
        if kind == "minecraft:vegetation_patch_feature":
            return 60.0
        return 1.0


def matches(flt, tags):
    if flt is None:
        return True
    if isinstance(flt, list):
        return all(matches(f, tags) for f in flt)
    if "all_of" in flt:
        return all(matches(f, tags) for f in flt["all_of"])
    if "any_of" in flt:
        return any(matches(f, tags) for f in flt["any_of"])
    if "none_of" in flt:
        return not any(matches(f, tags) for f in flt["none_of"])
    if flt.get("test") == "has_biome_tag":
        has = flt.get("value") in tags
        return has if flt.get("operator", "==") in ("==", "equals") else not has
    return True


def gen_cost(bp, tags):
    feats = Features(bp)
    total = 0.0
    for r, _, fs in os.walk(os.path.join(bp, "feature_rules")):
        for n in fs:
            try:
                d = load(os.path.join(r, n))["minecraft:feature_rules"]
            except ValueError:
                continue
            if not matches(d.get("conditions", {}).get("minecraft:biome_filter"), tags):
                continue
            dist = d.get("distribution", {})
            total += as_num(dist.get("iterations"), 1) * chance(dist) * feats.cost(d["description"]["places_feature"])
    return total


# --- build --------------------------------------------------------------------------------------
def optimise_generation(src_bp):
    feats = Features(src_bp)
    rules = os.path.join(BP, "feature_rules")
    # a rule placing a feature that does not exist: removed
    for n in os.listdir(rules):
        d = load(os.path.join(rules, n))["minecraft:feature_rules"]
        pf = d["description"]["places_feature"]
        if not pf.startswith("minecraft:") and pf not in feats.f:   # vanilla features are fine
            os.remove(os.path.join(rules, n))
            print(f"  regla quitada (su feature no existe): {n}")
    for n, y in SURFACE.items():
        path = os.path.join(rules, n)
        data = load(path)
        rule = data["minecraft:feature_rules"]
        dist = rule["distribution"]
        kind, f = feats.f[rule["description"]["places_feature"]]
        yr = dist.get("y")
        rng = (yr["extent"][1] - yr["extent"][0]) if isinstance(yr, dict) else 1
        landing = as_num(dist.get("iterations"), 1) * blob_span(as_num(f.get("count"), 1)) / max(1, rng)
        want = landing * 1.25           # a blob centred on the surface covers more than one grazing it
        dist["y"] = y
        if want >= 1:
            dist["iterations"] = int(math.ceil(want))
            dist.pop("scatter_chance", None)
        else:
            dist["iterations"] = 1
            dist["scatter_chance"] = {"numerator": max(1, round(want * 100)), "denominator": 100}
        dump(path, data)
    for n, it in FEWER.items():
        path = os.path.join(rules, n)
        data = load(path)
        data["minecraft:feature_rules"]["distribution"]["iterations"] = it
        dump(path, data)
    # clovers: their scatter reached 64 blocks away (into chunks not yet generated)
    for r, _, fs in os.walk(os.path.join(BP, "features")):
        for n in fs:
            path = os.path.join(r, n)
            d = load(path)
            sc = d.get("minecraft:scatter_feature")
            if sc and sc["description"]["identifier"] == "gen:scatter_clovers_feature":
                for axis in ("x", "z"):
                    sc[axis] = {"distribution": "triangle", "extent": [-12, 12]}
                dump(path, d)


def edit_json(path, fn):
    data = load(path)
    fn(data)
    dump(path, data)


def fix_entities():
    ents = os.path.join(BP, "entities")

    def find(ident):
        for r, _, fs in os.walk(ents):
            for n in fs:
                p = os.path.join(r, n)
                try:
                    if load(p)["minecraft:entity"]["description"]["identifier"] == ident:
                        return p
                except (ValueError, KeyError):
                    pass
        sys.exit(f"no encuentro {ident}")

    def drop_group(name):
        def f(d):
            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k in ("add", "remove") and isinstance(v, dict) and isinstance(v.get("component_groups"), list):
                            v["component_groups"] = [g for g in v["component_groups"] if g != name]
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(d["minecraft:entity"].get("events", {}))
        return f
    for i in ("minecraft:bee", "mob:queen_bee"):
        edit_json(find(i), drop_group("collect_nectar"))
    for i in ("mob:mosquito", "mob:wasp"):
        edit_json(find(i), lambda d: d["minecraft:entity"].setdefault("events", {}).setdefault("attacked", {}))
    def no_missing_loot(d):   # fox.json / bee.json do not exist (not even in vanilla)
        e = d["minecraft:entity"]
        for holder in [e.get("components", {})] + list(e.get("component_groups", {}).values()):
            t = holder.get("minecraft:loot", {}).get("table", "")
            if t.endswith(("entities/fox.json", "entities/bee.json")):
                del holder["minecraft:loot"]
    for i in ("mob:raccoon", "mob:wasp"):
        edit_json(find(i), no_missing_loot)

    def phantom(d):
        for e in d["minecraft:entity"]["events"]["minecraft:entity_spawned"]["randomize"]:
            qc = e.get("queue_command", {}).get("command")
            if qc and any("mob:specter" in c for c in qc):
                del e["queue_command"]
    edit_json(find("minecraft:phantom"), phantom)


def fix_blocks():
    def trapdoor(d):
        c = d["minecraft:block"]["components"]
        c["minecraft:custom_components"] = [x for x in c["minecraft:custom_components"] if x != "kai:on_tick"]
        c.pop("minecraft:tick", None)   # it only drove the missing kai:on_tick (every 2 ticks)
    edit_json(os.path.join(BP, "blocks", "block_redwood_trapdoor.json"), trapdoor)

    def stairs(d):
        c = d["minecraft:block"]["components"]
        c.pop("block_large_green_brick_stairs:trigger", None)
        for m in c.get("minecraft:material_instances", {}).values():
            if m.get("texture") == "block_large_green_brick_stairs":
                m["texture"] = "block_large_green_bricks"
        for p in d["minecraft:block"].get("permutations", []):
            p.get("components", {}).pop("block_large_green_brick_stairs:trigger", None)
    edit_json(os.path.join(BP, "blocks", "stairs", "block_large_green_brick_stairs.json"), stairs)


def scripts():
    path = os.path.join(BP, "scripts", "blockcomponents.js")
    text = read(path)
    n = len(re.findall(r'e\.block\.dimension\.spawnEntity\(\("(mob:[a-z_]+)"\), e\.block\.center\(\)\);', text))
    text = re.sub(r'e\.block\.dimension\.spawnEntity\(\("(mob:[a-z_]+)"\), e\.block\.center\(\)\);',
                  r'natureTick(e.block, "\1");', text)
    text = "import { natureTick } from './nature_ticks';\n" + text
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    for name in ("nature_ticks.js", "ambience.js"):
        shutil.copyfile(os.path.join(JS, name), os.path.join(BP, "scripts", name))
    main = os.path.join(BP, "scripts", "main.js")
    with open(main, "a", encoding="utf-8", newline="\n") as f:
        f.write("\nimport 'ambience'\n")
    return n


def particles():
    def haze(d):   # one ambience entity every AMBIENCE_EVERY ticks instead of every tick
        r = d["particle_effect"]["components"]["minecraft:emitter_rate_steady"]
        r["spawn_rate"] = r["spawn_rate"] * AMBIENCE_EVERY
        r["max_particles"] = r["max_particles"] * AMBIENCE_EVERY
    edit_json(os.path.join(RP, "particles", "palegardeneffect.particle.json"), haze)



def resources():
    def sounds(d):
        ev = d["entity_sounds"]["entities"].get("mob:deer", {}).get("events", {})
        for k, v in ev.items():
            if v == "deer_death" or (isinstance(v, dict) and v.get("sound") == "deer_death"):
                ev[k] = "deer_hurt"   # 'deer_death' is not defined: the hurt sound, as many mobs do
    edit_json(os.path.join(RP, "sounds.json"), sounds)
    def step(d):   # zombified_pig_step was written inside zombified_pig_death (a brace too few)
        sd = d.get("sound_definitions", d)
        inner = sd.get("zombified_pig_death", {}).pop("zombified_pig_step", None)
        if inner:
            sd["zombified_pig_step"] = inner
    edit_json(os.path.join(RP, "sounds", "sound_definitions.json"), step)

    def textures(d):   # atlas entries pointing at images that do not exist
        for k, v in d.get("texture_data", {}).items():
            if k in TEXTURE_FIXES:
                v["textures"] = TEXTURE_FIXES[k]
    for atlas in ("terrain_texture.json", "item_texture.json"):
        edit_json(os.path.join(RP, "textures", atlas), textures)
    lang = os.path.join(RP, "texts", "en_US.lang")
    text = read(lang)
    add = [f"entity.{i}.name={n}" for i, n in NAMES.items() if not re.search(rf"^entity\.{re.escape(i)}\.name=", text, re.M)]
    with open(lang, "a", encoding="utf-8", newline="\n") as f:
        f.write(("" if text.endswith("\n") else "\n") + "\n".join(add) + "\n")


def manifests():
    for pack in (BP, RP):
        def f(m):
            m["header"]["name"] += " (optimizado)"
            v = m["header"]["version"]
            m["header"]["version"] = v[:2] + [v[2] + 1]   # imports over the original
            for mod in m["modules"]:
                mod["version"] = m["header"]["version"]
            for dep in m.get("dependencies", []):
                if "uuid" in dep:
                    dep["version"] = m["header"]["version"]
        edit_json(os.path.join(pack, "manifest.json"), f)


def report(src_bp):
    biomes = {}
    for r, _, fs in os.walk(os.path.join(src_bp, "biomes")):
        for n in fs:
            try:
                d = load(os.path.join(r, n))["minecraft:biome"]
            except (ValueError, KeyError):
                continue
            tags = set(d.get("components", {}).get("minecraft:tags", {}).get("tags", []))
            biomes[d["description"]["identifier"]] = tags
    rows = []
    for b, tags in sorted(biomes.items()):
        before, after = gen_cost(src_bp, tags), gen_cost(BP, tags)
        if before > 0:
            rows.append((b, before, after))
    print("\nGeneración: bloques que se intentan colocar por chunk (estimado)")
    for b, x, y in sorted(rows, key=lambda r: -r[1]):
        print(f"  {b:40} {x:9.0f} -> {y:7.0f}  (-{100 * (1 - y / x):.0f} %)")
    tb, ta = sum(r[1] for r in rows), sum(r[2] for r in rows)
    print(f"  media de los {len(rows)} biomas: -{100 * (1 - ta / tb):.0f} %")
    return rows


def area_cost(bp, vanilla):
    """Generation work the add-on adds, per chunk, where the world would have `vanilla`:
    the share each add-on biome takes of it, at that biome's cost; the rest at the cost
    of the add-on's decoration on the vanilla biome itself."""
    biomes = separate.biome_index(bp)
    share, cost = 0.0, 0.0
    for ident, b in biomes.items():
        amounts = [a for t, a in b["targets"] if t == "minecraft:" + vanilla]
        if amounts and not ident.startswith("minecraft:"):
            share += amounts[0]
            cost += amounts[0] * gen_cost(bp, b["tags"])
    if share > 1:              # several biomes compete for it: they split it
        cost, share = cost / share, 1.0
    return cost + (1 - share) * gen_cost(bp, set(separate.VANILLA_TAGS[vanilla]))


def world_report(src_bp, stage1):
    print("\nGeneración que añade el addon, por chunk, según el bioma vanilla de la zona (estimado)")
    print(f"  {'zona':26} {'original':>9} {'1.ª optim.':>10} {'ahora':>8}")
    tot = [0.0, 0.0, 0.0]
    for v in sorted(separate.VANILLA_TAGS):
        row = [area_cost(src_bp, v), area_cost(stage1, v), area_cost(BP, v)]
        tot = [a + b for a, b in zip(tot, row)]
        print(f"  {v:26} {row[0]:9.0f} {row[1]:10.0f} {row[2]:8.0f}")
    print(f"  {'media':26} {tot[0] / 20:9.0f} {tot[1] / 20:10.0f} {tot[2] / 20:8.0f}")
    print(f"  ahora frente al original: -{100 * (1 - tot[2] / tot[0]):.0f} %; frente a la 1.ª optimización: "
          f"-{100 * (1 - tot[2] / tot[1]):.0f} %")


def build(src_dir):
    src_bp, src_rp = dm.find_packs(src_dir)
    for d in (BP, RP):
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(src_bp, BP)
    shutil.copytree(src_rp, RP)
    for rel, fixes in TEXT_FIXES.items():
        path = os.path.join(BP, rel)
        text = read(path).replace("\r\n", "\n")
        for old, new in fixes:
            text = old.sub(new, text, count=1) if hasattr(old, "sub") else text.replace(old, new, 1)
        json.loads(dm._strip(text))   # must parse now
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    # ambience every tick -> script; the wind no longer spawns as a mob
    os.remove(os.path.join(BP, "functions", "tick.json"))
    for r, _, fs in os.walk(os.path.join(BP, "spawn_rules")):
        for n in fs:
            if load(os.path.join(r, n))["minecraft:spawn_rules"]["description"]["identifier"] == "mechanic:wind_noise":
                os.remove(os.path.join(r, n))
    n = scripts()
    print(f"  {n} bloques ya no invocan entidades")
    particles()
    optimise_generation(src_bp)
    fix_entities()
    fix_blocks()
    resources()
    manifests()
    stage1 = tempfile.mkdtemp()
    for folder in ("feature_rules", "features", "biomes"):
        shutil.copytree(os.path.join(BP, folder), os.path.join(stage1, folder))
    print("Segunda etapa: biomas aparte, sin mosquitos ni viento")
    separate.separate_biomes(BP, RP, matches, print)
    separate.remove_entity(BP, RP, "mob:mosquito", print)
    separate.remove_wind(BP, RP, print)
    separate.opaque_leaves(BP, print)
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
    world_report(src_bp, stage1)
    shutil.rmtree(stage1, ignore_errors=True)
    print(f"OK -> {os.path.relpath(MCADDON, ROOT)} ({os.path.getsize(MCADDON) / 1e6:.1f} MB)")


def unpack(path, into):
    with zipfile.ZipFile(path) as z:
        z.extractall(into)
    for dirpath, _, files in os.walk(into):
        for name in files:
            if name.endswith(".mcpack"):
                with zipfile.ZipFile(os.path.join(dirpath, name)) as z:
                    z.extractall(os.path.join(dirpath, name[:-7]))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    if os.path.isdir(sys.argv[1]):
        build(sys.argv[1])
        return
    with tempfile.TemporaryDirectory() as tmp:
        unpack(sys.argv[1], tmp)
        build(tmp)


if __name__ == "__main__":
    main()
