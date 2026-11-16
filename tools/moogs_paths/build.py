#!/usr/bin/env python3
"""Converts the data of the Java mod "Moog's Paths" (CC0) into scripts/data.js for the Bedrock port.

usage: python3 -I build.py <extracted-jar-dir> <behavior-pack-dir>
"""
import sys, os, json, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbt

SRC, OUT = sys.argv[1], sys.argv[2]
DATA = os.path.join(SRC, "data", "moogs_paths")
short = lambda s: s.split(":", 1)[1] if ":" in s else s

# ---------------------------------------------------------------- biomes
JAVA_BIOME = {  # java biome id -> bedrock biome ids
    "plains": ["plains"], "sunflower_plains": ["sunflower_plains"], "meadow": ["meadow"],
    "cherry_grove": ["cherry_grove"], "desert": ["desert", "desert_hills", "desert_mutated"],
    "taiga": ["taiga", "taiga_hills", "taiga_mutated"],
    "old_growth_pine_taiga": ["mega_taiga", "mega_taiga_hills"],
    "old_growth_spruce_taiga": ["redwood_taiga_mutated", "redwood_taiga_hills_mutated"],
    "dark_forest": ["roofed_forest", "roofed_forest_mutated"],
    "mushroom_fields": ["mushroom_island", "mushroom_island_shore"],
    "snowy_plains": ["ice_plains"], "snowy_taiga": ["cold_taiga", "cold_taiga_hills", "cold_taiga_mutated"],
    "ice_spikes": ["ice_plains_spikes"], "snowy_beach": ["cold_beach"],
    "swamp": ["swampland", "swampland_mutated"], "mangrove_swamp": ["mangrove_swamp"],
    "windswept_hills": ["extreme_hills", "extreme_hills_edge"],
    "windswept_gravelly_hills": ["extreme_hills_mutated"],
    "windswept_forest": ["extreme_hills_plus_trees", "extreme_hills_plus_trees_mutated"],
    "windswept_savanna": ["savanna_mutated", "savanna_plateau_mutated"],
}
JAVA_TAG = {
    "minecraft:is_badlands": ["mesa", "mesa_bryce", "mesa_plateau", "mesa_plateau_mutated",
                              "mesa_plateau_stone", "mesa_plateau_stone_mutated"],
    "minecraft:is_taiga": ["taiga", "taiga_hills", "taiga_mutated", "cold_taiga", "cold_taiga_hills",
                           "cold_taiga_mutated", "mega_taiga", "mega_taiga_hills",
                           "redwood_taiga_mutated", "redwood_taiga_hills_mutated"],
    "minecraft:is_savanna": ["savanna", "savanna_plateau", "savanna_mutated", "savanna_plateau_mutated"],
    "minecraft:is_hill": ["extreme_hills", "extreme_hills_edge", "extreme_hills_mutated",
                          "extreme_hills_plus_trees", "extreme_hills_plus_trees_mutated"],
    "minecraft:is_jungle": ["jungle", "jungle_hills", "jungle_edge", "jungle_mutated", "jungle_edge_mutated",
                            "bamboo_jungle", "bamboo_jungle_hills"],
    "minecraft:is_mountain": ["meadow", "frozen_peaks", "jagged_peaks", "stony_peaks", "snowy_slopes", "cherry_grove"],
}

def resolve_biomes(ref):
    if ref == "#minecraft:is_overworld":
        return None  # any overworld biome
    if ref in ("#" + k for k in JAVA_TAG):
        return sorted(set(JAVA_TAG[ref[1:]]))
    assert ref.startswith("#moogs_paths:"), ref
    tag = json.load(open(os.path.join(DATA, "tags/worldgen/biome", ref.split(":")[1] + ".json")))
    out = set()
    for v in tag["values"]:
        if isinstance(v, dict):
            continue  # optional entries only exist for other Java mods
        if v.startswith("#"):
            out.update(JAVA_TAG[v[1:]])
        else:
            out.update(JAVA_BIOME[short(v)])
    return sorted(out)

# ---------------------------------------------------------------- blocks
RENAME = {
    "dirt_path": "grass_path", "rooted_dirt": "dirt_with_roots", "snow_block": "snow", "bricks": "brick_block",
    "terracotta": "hardened_clay", "flowering_azalea_leaves": "azalea_leaves_flowered",
    "oak_trapdoor": "trapdoor", "oak_button": "wooden_button", "oak_pressure_plate": "wooden_pressure_plate",
    "cobblestone_stairs": "stone_stairs", "stone_stairs": "normal_stone_stairs", "stone_slab": "normal_stone_slab",
    "wall_torch": "torch",
}
def simple_block(java_id):
    n = short(java_id)
    if n == "structure_void":
        return None
    return "minecraft:" + RENAME.get(n, n)

HORIZ = ["north", "east", "south", "west"]
rot_dir = lambda d, k: HORIZ[(HORIZ.index(d) + k) % 4] if d in HORIZ else d
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}
DIR4 = {"east": 0, "west": 1, "south": 2, "north": 3}
FACE6 = {"north": 2, "south": 3, "west": 4, "east": 5}
ATTACHED = ("torch", "button", "lever", "lantern", "pressure_plate", "candle", "hanging_sign")

def rotate_props(p, k):
    p = dict(p)
    if k == 0:
        return p
    if "facing" in p:
        p["facing"] = rot_dir(p["facing"], k)
    if "axis" in p and p["axis"] != "y" and k % 2:
        p["axis"] = "z" if p["axis"] == "x" else "x"
    if "rotation" in p:
        p["rotation"] = str((int(p["rotation"]) + 4 * k) % 16)
    sides = {d: p[d] for d in HORIZ if d in p}
    for d, v in sides.items():
        p[rot_dir(d, k)] = v
    return p

def to_bedrock(java_id, p):
    """java block id + (already rotated) properties -> (bedrock id, states) or None for structure_void."""
    n = short(java_id)
    if n == "structure_void":
        return None
    name = "minecraft:" + RENAME.get(n, n)
    s = {}
    b = lambda v: v == "true"
    if n.endswith("_log") or n == "hay_block":
        s["pillar_axis"] = p.get("axis", "y")
    elif n.endswith("_slab"):
        s["minecraft:vertical_half"] = p["type"] if p["type"] in ("top", "bottom") else "bottom"
    elif n.endswith("_stairs"):
        s = {"weirdo_direction": DIR4[p["facing"]], "upside_down_bit": p["half"] == "top"}
    elif n.endswith("_wall"):
        s = {"wall_post_bit": b(p["up"])}
        for d in HORIZ:
            s["wall_connection_type_" + d] = {"none": "none", "low": "short", "tall": "tall"}[p[d]]
    elif n.endswith("_trapdoor"):
        s = {"direction": DIR4[p["facing"]], "open_bit": b(p["open"]), "upside_down_bit": p["half"] == "top"}
    elif n.endswith("_button"):
        f = {"floor": 1, "ceiling": 0}.get(p["face"], FACE6[p["facing"]])
        s = {"facing_direction": f, "button_pressed_bit": False}
    elif n == "lever":
        ew = p["facing"] in ("east", "west")
        d = {"floor": "up_east_west" if ew else "up_north_south",
             "ceiling": "down_east_west" if ew else "down_north_south"}.get(p["face"], p["facing"])
        s = {"lever_direction": d, "open_bit": b(p["powered"])}
    elif n in ("lantern", "soul_lantern"):
        s = {"hanging": b(p["hanging"])}
    elif n.endswith("candle"):
        s = {"candles": int(p["candles"]) - 1, "lit": b(p["lit"])}
    elif n == "wall_torch":
        s = {"torch_facing_direction": OPP[p["facing"]]}
    elif n == "campfire":
        s = {"minecraft:cardinal_direction": p["facing"], "extinguished": not b(p["lit"])}
    elif n in ("brown_mushroom_block", "red_mushroom_block"):
        s = {"huge_mushroom_bits": 14}
    elif n == "mushroom_stem":
        s = {"huge_mushroom_bits": 15}
    elif n == "redstone_lamp":
        name = "minecraft:lit_redstone_lamp" if b(p["lit"]) else name
    elif n.endswith("_hanging_sign"):
        s = {"attached_bit": b(p["attached"]), "hanging": True, "ground_sign_direction": int(p["rotation"]), "facing_direction": 2}
    return name, s

palette, palette_ix = [], {}
def pal(name, states):
    key = name + json.dumps(states, sort_keys=True)
    if key not in palette_ix:
        palette_ix[key] = len(palette)
        e = {"n": name}
        if states:
            e["s"] = states
        palette.append(e)
    return palette_ix[key]

def convert_structure(path):
    d = nbt.read_java(path)
    texts = {}
    for blk in d["blocks"]:
        t = blk.get("nbt", {}).get("front_text")
        if t:
            texts[tuple(blk["pos"])] = "\n".join(m.get("text", "") if isinstance(m, dict) else str(m) for m in t["messages"])
    rots = []
    for k in range(4):
        cells = []
        for blk in d["blocks"]:
            st = d["palette"][blk["state"]]
            conv = to_bedrock(st["id"], rotate_props(st.get("properties", {}), k))
            if conv is None:
                continue
            x, y, z = blk["pos"]
            for _ in range(k):
                x, z = -z, x  # clockwise 90
            cells.append([x, y, z, pal(*conv), texts.get(tuple(blk["pos"]))])
        mx, mz = min(c[0] for c in cells), min(c[2] for c in cells)
        for c in cells:
            c[0] -= mx; c[2] -= mz
        attached = lambda c: any(a in palette[c[3]]["n"] for a in ATTACHED)
        cells.sort(key=lambda c: (attached(c), c[1]))
        out = {"x": max(c[0] for c in cells) + 1, "z": max(c[2] for c in cells) + 1,
               "b": [c[:4] for c in cells]}
        t = [[c[0], c[1], c[2], c[4]] for c in cells if c[4]]
        if t:
            out["t"] = t
        rots.append(out)
    return rots

# ---------------------------------------------------------------- data files
def load_dir(sub):
    return {os.path.basename(f)[:-5]: json.load(open(f))
            for f in sorted(glob.glob(os.path.join(DATA, "moogs_paths", sub, "*.json")))}

def weighted(lst, key="block"):
    return [[simple_block(e[key]), e["weight"]] for e in lst]

path_types = {}
for name, j in load_dir("path_type").items():
    t = {"surface": weighted(j["surface_blocks"]), "edge": weighted(j.get("edge_blocks", [])),
         "fill": simple_block(j["fill_block"]), "width": [j["width"]["min"], j["width"]["max"]],
         "rigidness": j["rigidness"], "carver": j["carver"],
         "length": [j["length"]["min_inclusive"], j["length"]["max_inclusive"]],
         "fade": [j["fade"]["start_blocks"], j["fade"]["end_blocks"]],
         "waterCost": j.get("water_cost", 4.0)}
    if "water_settings" in j:
        t["water"] = {"surface": weighted(j["water_settings"]["surface_blocks"]),
                      "edge": weighted(j["water_settings"].get("edge_blocks", []))}
    path_types[name] = t

networks, village_networks, skipped = [], {}, []
for name, j in load_dir("path_network").items():
    n = {"id": name, "type": short(j["path_type"]), "structs": [short(s) for s in j["structure_sets"]],
         "feats": [short(s) for s in j["feature_decorator_sets"]], "bushes": [short(s) for s in j["bush_decorator_sets"]]}
    if "origin" in j:
        if name.startswith("village_road_"):
            village_networks[name[len("village_road_"):]] = n
        else:
            skipped.append(name)
        continue
    n.update(biomes=resolve_biomes(j["biomes"]), weight=j["weight"], region=j["region_size"])
    networks.append(n)

structures, structure_sets = {}, {}
for name, j in load_dir("structure_set").items():
    entries = []
    for e in j["structures"]:
        sid = short(e["nbt"])
        if sid not in structures:
            structures[sid] = convert_structure(os.path.join(DATA, "structure", sid + ".nbt"))
        entries.append({"s": sid, "w": e["weight"], "rot": e["rotation"] == "random", "dy": e["offset"][1]})
    structure_sets[name] = {"entries": entries, "mode": j["placement"], "spacing": j["spacing"],
                            "variance": j["spacing_variance"], "flat": j["flatness_tolerance"], "side": j["side_offset"]}

bush_sets = {n: {"blocks": weighted(j["blocks"]), "density": j["density"], "side": j["side"],
                 "off": [j["min_offset"], j["max_offset"]], "size": [j["min_size"], j["max_size"]],
                 "spacing": j["min_spacing"]} for n, j in load_dir("bush_decorator_set").items()}
feature_sets = {n: {"features": weighted(j["features"], "feature"), "density": j["density"], "side": j["side"],
                    "width": j["scatter_width"]} for n, j in load_dir("feature_decorator_set").items()}

no_paths = ["ocean", "deep_ocean", "warm_ocean", "deep_warm_ocean", "lukewarm_ocean", "deep_lukewarm_ocean",
            "cold_ocean", "deep_cold_ocean", "frozen_ocean", "deep_frozen_ocean", "legacy_frozen_ocean",
            "deep_dark", "lush_caves", "dripstone_caves"]
crossable = ["river", "frozen_river"]

os.makedirs(os.path.join(OUT, "scripts"), exist_ok=True)
js = lambda v: json.dumps(v, separators=(",", ":"))
with open(os.path.join(OUT, "scripts", "data.js"), "w") as f:
    f.write("// Generated by tools/build.py from Moog's Paths 1.2.0 (CC0). Do not edit by hand.\n")
    for k, v in [("PATH_TYPES", path_types), ("NETWORKS", networks), ("VILLAGE_NETWORKS", village_networks),
                 ("STRUCTURE_SETS", structure_sets), ("BUSH_SETS", bush_sets), ("FEATURE_SETS", feature_sets),
                 ("NO_PATH_BIOMES", no_paths), ("CROSSABLE_BIOMES", crossable), ("PALETTE", palette),
                 ("STRUCTURES", structures)]:
        f.write(f"export const {k} = {js(v)};\n")
shutil.copyfile(os.path.join(SRC, "assets/moogs_paths/icon.png"), os.path.join(OUT, "pack_icon.png"))
print(f"{len(path_types)} path types, {len(networks)} networks (+{len(village_networks)} village), "
      f"{len(structures)} structures, palette {len(palette)}; not portable: {skipped}")
