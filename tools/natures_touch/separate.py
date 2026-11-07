"""Second stage of tools/natures_touch_opt.py: the biomes as separate biomes, no mosquitoes,
no wind, leaves that do not vanish in the distance.

  * Custom biomes removed except the Lavender Forest; the Sand Savanna removed too.
  * The kept ones (the remakes and the Lavender Forest) become biomes of their own:
    they take SHARE of the vanilla biomes they replaced (it was 90 %), carry the tag
    "nt_biome", and every decoration of the add-on needs that tag: vanilla biomes go
    back to plain vanilla generation. The add-on's overrides of vanilla biomes (river,
    frozen river, pale garden, their client colours) are dropped.
  * Feature rules that no kept biome can use, and the features and structures nothing
    places any more, are removed.
  * Mosquitoes removed (entity, spawning, model, animations, textures, sounds, name).
  * Wind removed (entity, particle, sounds and their files; no script plays it).
  * Leaves used the "alpha_test" render method, which Bedrock stops drawing beyond a
    distance: now "alpha_test_to_opaque", like vanilla leaves (format 1.21.80).
"""
import json
import os
import re
import shutil

from dungeons_mobs import load, dump, read

SHARE = 0.35
KEEP_CUSTOM = {"nt:lavender_forest"}
DROP = {"nt:sand_savanna_remake"}
TAG = "nt_biome"
VANILLA_TAGS = json.loads("""{
 "birch_forest": ["animal", "birch", "forest", "monster", "overworld", "bee_habitat", "has_structure_abandoned_camp"],
 "cherry_grove": ["mountains", "monster", "overworld", "cherry_grove", "bee_habitat", "has_structure_abandoned_camp"],
 "desert": ["desert", "monster", "overworld", "spawns_gold_rabbits", "spawns_warm_variant_farm_animals", "spawns_warm_variant_frogs"],
 "extreme_hills": ["animal", "extreme_hills", "monster", "overworld", "spawns_cold_variant_farm_animals"],
 "extreme_hills_plus_trees": ["animal", "extreme_hills", "forest", "monster", "mountain", "overworld", "spawns_cold_variant_farm_animals", "has_structure_abandoned_camp"],
 "forest": ["animal", "forest", "monster", "overworld", "bee_habitat", "has_structure_abandoned_camp", "oak_forest"],
 "jagged_peaks": ["mountains", "monster", "overworld", "frozen", "jagged_peaks", "spawns_cold_variant_farm_animals", "spawns_cold_variant_frogs", "spawns_snow_foxes", "spawns_white_rabbits"],
 "jungle": ["animal", "has_structure_trail_ruins", "jungle", "monster", "overworld", "rare", "spawns_jungle_mobs", "spawns_warm_variant_farm_animals"],
 "jungle_edge": ["animal", "edge", "jungle", "monster", "overworld", "spawns_jungle_mobs", "spawns_warm_variant_farm_animals", "has_structure_abandoned_camp"],
 "meadow": ["mountains", "monster", "overworld", "meadow", "bee_habitat", "has_structure_abandoned_camp"],
 "mega_taiga": ["animal", "forest", "mega", "monster", "overworld", "rare", "taiga", "has_structure_trail_ruins", "spawns_cold_variant_farm_animals", "has_structure_abandoned_camp"],
 "mesa": ["animal", "mesa", "monster", "overworld", "spawns_mesa_mobs", "spawns_warm_variant_farm_animals", "surface_mineshaft"],
 "pale_garden": ["monster", "overworld", "pale_garden", "has_structure_abandoned_camp"],
 "plains": ["animal", "monster", "overworld", "plains", "bee_habitat"],
 "river": ["overworld", "spawns_more_frequent_drowned", "spawns_reduced_water_ambient_mobs", "spawns_river_mobs", "river"],
 "roofed_forest": ["animal", "forest", "monster", "no_legacy_worldgen", "overworld", "roofed"],
 "savanna": ["animal", "monster", "overworld", "savanna", "spawns_savanna_mobs", "spawns_warm_variant_farm_animals", "has_structure_abandoned_camp"],
 "sunflower_plains": ["animal", "monster", "mutated", "overworld", "plains", "bee_habitat"],
 "swampland": ["animal", "monster", "overworld", "swamp", "spawns_slimes_on_surface", "slime", "swamp_water_huge_mushroom", "has_structure_abandoned_camp"],
 "taiga": ["animal", "forest", "monster", "overworld", "taiga", "has_structure_trail_ruins", "spawns_cold_variant_farm_animals", "has_structure_abandoned_camp"]
}""")


def files(root, folder, ext=".json"):
    for r, _, fs in os.walk(os.path.join(root, folder)):
        for f in fs:
            if f.endswith(ext):
                yield os.path.join(r, f)


def biome_index(bp):
    out = {}
    for p in files(bp, "biomes"):
        d = load(p)["minecraft:biome"]
        c = d.get("components", {})
        out[d["description"]["identifier"]] = {
            "path": p, "tags": set(c.get("minecraft:tags", {}).get("tags", [])),
            "targets": [(t, r.get("amount", 1)) for r in c.get("minecraft:replace_biomes", {}).get("replacements", [])
                        for t in r.get("targets", [])]}
    return out


def kept(ident):
    if ident in DROP or ident.startswith("minecraft:"):
        return False
    return ident in KEEP_CUSTOM or ident.endswith("_remake")


# --- biomes ---------------------------------------------------------------------------------
def separate_biomes(bp, rp, matches, log):
    biomes = biome_index(bp)
    keep = {i for i in biomes if kept(i)}
    for ident, b in biomes.items():
        if ident not in keep:
            os.remove(b["path"])
            continue
        d = load(b["path"])
        c = d["minecraft:biome"]["components"]
        for r in c.get("minecraft:replace_biomes", {}).get("replacements", []):
            r["amount"] = min(r.get("amount", 1), SHARE)
        tags = c.setdefault("minecraft:tags", {}).setdefault("tags", [])
        if TAG not in tags:
            tags.append(TAG)
        dump(b["path"], d)
    log(f"  biomas: {len(keep)} quedan ({', '.join(sorted(keep))}), {len(biomes) - len(keep)} quitados")
    keep_tags = [biomes[i]["tags"] | {TAG} for i in keep]

    # every decoration of the add-on only in its own biomes
    removed = 0
    for p in list(files(bp, "feature_rules")):
        d = load(p)
        rule = d["minecraft:feature_rules"]
        cond = rule.setdefault("conditions", {})
        old = cond.get("minecraft:biome_filter")
        new = {"all_of": ([old] if isinstance(old, dict) else (old or [])) + [{"test": "has_biome_tag", "operator": "==", "value": TAG}]}
        if not any(matches(new, t) for t in keep_tags):
            os.remove(p)
            removed += 1
            continue
        cond["minecraft:biome_filter"] = new
        dump(p, d)
    log(f"  reglas de generación quitadas (ningún bioma que quede las usa): {removed}")
    prune_features(bp, log)

    # client side: colours and fogs of the biomes that remain
    kept_short = {i.split(":")[-1] for i in keep}
    fogs_used = set()
    for p in list(files(rp, "biomes")):
        d = load(p)
        k = [x for x in d if "biome" in x][0]
        ident = d[k]["description"]["identifier"]
        if ident.split(":")[-1] not in kept_short or ":" not in ident:
            os.remove(p)
        else:
            fogs_used |= set(re.findall(r'"([a-z0-9_]+:[a-z0-9_]+)"', json.dumps(d)))
    for p in list(files(rp, "fogs")):
        ident = load(p)["minecraft:fog_settings"]["description"]["identifier"]
        if ident not in fogs_used:
            os.remove(p)
    return keep


def prune_features(bp, log):
    feats = {}
    for p in files(bp, "features"):
        d = load(p)
        k = [x for x in d if x.startswith("minecraft:")][0]
        feats[d[k]["description"]["identifier"]] = (p, d[k])
    used, todo = set(), [load(p)["minecraft:feature_rules"]["description"]["places_feature"] for p in files(bp, "feature_rules")]
    while todo:
        f = todo.pop()
        if f in used or f not in feats:
            continue
        used.add(f)
        todo += [s for s in re.findall(r'"([a-z0-9_]+:[a-z0-9_.]+)"', json.dumps(feats[f][1])) if s in feats]
    for f, (p, _) in feats.items():
        if f not in used:
            os.remove(p)
    # structures placed by the remaining features (or named in functions / scripts)
    names = set()
    for f in used:
        for n in re.findall(r'"structure_name":\s*"([^"]+)"', json.dumps(feats[f][1])):
            # "mystructure:x" is structures/x.mcstructure; "ns:x" is structures/ns/x.mcstructure
            names.add(n.split(":", 1)[1] if n.startswith("mystructure:") else n.replace(":", "/", 1))
    other = " ".join(read(p) for ext in (".mcfunction", ".js") for p in files(bp, "", ext))
    gone = 0
    for p in list(files(bp, "structures", ".mcstructure")):
        rel = os.path.relpath(p, os.path.join(bp, "structures"))[:-len(".mcstructure")].replace(os.sep, "/")
        if rel not in names and rel not in other and rel.replace("/", ":", 1) not in other:
            os.remove(p)
            gone += 1
    log(f"  features quitadas: {len(feats) - len(used)} de {len(feats)}; estructuras quitadas: {gone}")


# --- mosquito and wind ---------------------------------------------------------------------------
def remove_entity(bp, rp, ident, log, extra_sounds=()):
    """Removes an entity and everything only it uses (client, model, animations, textures,
    sounds, spawn rules, names)."""
    short = ident.split(":")[-1]
    gone = []
    for p in list(files(bp, "entities")) + list(files(bp, "spawn_rules")):
        d = load(p)
        k = "minecraft:entity" if "minecraft:entity" in d else "minecraft:spawn_rules"
        if d.get(k, {}).get("description", {}).get("identifier") == ident:
            os.remove(p)
            gone.append(os.path.relpath(p, bp))
    for p in list(files(rp, "entity")):
        d = load(p)
        desc = d.get("minecraft:client_entity", {}).get("description", {})
        if desc.get("identifier") != ident:
            continue
        os.remove(p)
        refs = set(desc.get("textures", {}).values()) | set(desc.get("geometry", {}).values()) | set(desc.get("animations", {}).values())
        for q in list(files(rp, "models")) + list(files(rp, "animations")) + list(files(rp, "animation_controllers")):
            text = read(q)
            if any(f'"{r}"' in text for r in refs) and short in os.path.basename(q):
                os.remove(q)
        for t in refs:
            for ext in (".png", ".tga"):
                tp = os.path.join(rp, t + ext)
                if t.startswith("textures/") and os.path.isfile(tp):
                    os.remove(tp)
    sj = os.path.join(rp, "sounds.json")
    d = load(sj)
    ents = d.get("entity_sounds", {}).get("entities", {})
    sound_names = set(extra_sounds)
    if ident in ents:
        sound_names |= set(re.findall(r'"([a-z0-9_.]+)"', json.dumps(ents.pop(ident))))
    dump(sj, d)
    sd_path = os.path.join(rp, "sounds", "sound_definitions.json")
    defs = load(sd_path)
    sd = defs.get("sound_definitions", defs)
    for k in [k for k in sd if k in sound_names or short in k]:
        for s in sd[k].get("sounds", []):
            name = s if isinstance(s, str) else s.get("name", "")
            for ext in (".ogg", ".wav", ".fsb"):
                if os.path.isfile(os.path.join(rp, name + ext)):
                    os.remove(os.path.join(rp, name + ext))
        del sd[k]
    dump(sd_path, defs)
    lang = os.path.join(rp, "texts", "en_US.lang")
    lines = [l for l in read(lang).splitlines() if f"{ident}." not in l and f"{ident}=" not in l]
    with open(lang, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log(f"  {ident} quitado ({len(gone)} archivos BP)")


def remove_wind(bp, rp, log):
    remove_entity(bp, rp, "mechanic:wind_noise", log, extra_sounds=("wind_effect",))
    for p in list(files(rp, "particles")):
        d = load(p)
        if d.get("particle_effect", {}).get("description", {}).get("identifier") == "windeffect":
            os.remove(p)
    log("  viento quitado (entidad, partícula y sonidos)")


# --- leaves -----------------------------------------------------------------------------------------
def opaque_leaves(bp, log):
    n = 0
    for p in files(bp, "blocks"):
        d = load(p)
        b = d.get("minecraft:block", {})
        ident = b.get("description", {}).get("identifier", "")
        if not re.search(r"leaves$|_leaf$", ident):
            continue
        changed = False
        for holder in [b.get("components", {})] + [x.get("components", {}) for x in b.get("permutations", [])]:
            for m in holder.get("minecraft:material_instances", {}).values():
                if isinstance(m, dict) and m.get("render_method") == "alpha_test":
                    m["render_method"] = "alpha_test_to_opaque"
                    changed = True
        if changed:
            v = [int(x) for x in d["format_version"].split(".")]
            if v < [1, 21, 80]:
                d["format_version"] = "1.21.80"
            dump(p, d)
            n += 1
    log(f"  hojas que ya no desaparecen a lo lejos: {n} bloques")
