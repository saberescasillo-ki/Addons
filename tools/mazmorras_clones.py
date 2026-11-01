"""Indestructible copies of every block the dungeons use (mazmorra:<vanilla name>).

They look like the vanilla blocks (same textures, from the vanilla resource pack) but cannot
be mined nor blown up. Plants and hanging things need no support, so they never break when
something next to them changes. They are listed in the creative inventory in four collapsible
groups (item_catalog/crafting_item_catalog.json).

Blocks that must keep working stay vanilla and are protected by the script inside the
dungeons instead: chests, vaults, trial spawners, vines (to climb), water and lava; the copper
grate barrier of the corridors stays breakable on purpose.

write(bp, rp, lang) writes everything; CLONE_MAP tells the script which clone replaces each
vanilla block and how to translate its states.
"""
import json
import os

NS = "mazmorra"
FORMAT = "1.26.0"          # several collision boxes per block (stairs) need 1.26.0
KEEP_VANILLA = {"air", "water", "lava", "chest", "vault", "trial_spawner", "vine", "waxed_copper_grate", "glow_frame",
                # the natural stone around the hall of a cave-entrance dungeon: it is part of the terrain
                "stone", "andesite", "cobblestone", "diorite", "granite"}

TB = "textures/blocks/"
DS = TB + "deepslate/"


def tex(*parts):
    return TB + "/".join(parts)


# ---------------------------------------------------------------- definitions
# name: (kind, textures, Spanish name, options)
# textures: a path, or {"up", "down", "side"} or named materials for special models.
DEFS = {
    # tuff
    "tuff": ("cube", TB + "tuff", "Toba"),
    "polished_tuff": ("cube", TB + "polished_tuff", "Toba pulida"),
    "tuff_bricks": ("cube", TB + "tuff_bricks", "Ladrillos de toba"),
    "chiseled_tuff": ("cube", {"up": TB + "chiseled_tuff_top", "down": TB + "chiseled_tuff_top", "side": TB + "chiseled_tuff"}, "Toba cincelada"),
    "chiseled_tuff_bricks": ("cube", {"up": TB + "chiseled_tuff_bricks_top", "down": TB + "chiseled_tuff_bricks_top",
                                      "side": TB + "chiseled_tuff_bricks"}, "Ladrillos de toba cincelados"),
    "tuff_brick_slab": ("slab", TB + "tuff_bricks", "Losa de ladrillos de toba"),
    "polished_tuff_slab": ("slab", TB + "polished_tuff", "Losa de toba pulida"),
    "tuff_brick_stairs": ("stairs", TB + "tuff_bricks", "Escaleras de ladrillos de toba"),
    "polished_tuff_stairs": ("stairs", TB + "polished_tuff", "Escaleras de toba pulida"),
    "tuff_brick_wall": ("wall", TB + "tuff_bricks", "Muro de ladrillos de toba"),
    "polished_tuff_wall": ("wall", TB + "polished_tuff", "Muro de toba pulida"),
    # deepslate
    "deepslate": ("axis", {"up": DS + "deepslate_top", "down": DS + "deepslate_top", "side": DS + "deepslate"}, "Pizarra profunda"),
    "cobbled_deepslate": ("cube", DS + "cobbled_deepslate", "Pizarra profunda labrada"),
    "polished_deepslate": ("cube", DS + "polished_deepslate", "Pizarra profunda pulida"),
    "deepslate_bricks": ("cube", DS + "deepslate_bricks", "Ladrillos de pizarra profunda"),
    "cracked_deepslate_bricks": ("cube", DS + "cracked_deepslate_bricks", "Ladrillos de pizarra profunda agrietados"),
    "deepslate_tiles": ("cube", DS + "deepslate_tiles", "Baldosas de pizarra profunda"),
    "cracked_deepslate_tiles": ("cube", DS + "cracked_deepslate_tiles", "Baldosas de pizarra profunda agrietadas"),
    "chiseled_deepslate": ("cube", DS + "chiseled_deepslate", "Pizarra profunda cincelada"),
    "cobbled_deepslate_slab": ("slab", DS + "cobbled_deepslate", "Losa de pizarra profunda labrada"),
    "polished_deepslate_slab": ("slab", DS + "polished_deepslate", "Losa de pizarra profunda pulida"),
    "deepslate_brick_slab": ("slab", DS + "deepslate_bricks", "Losa de ladrillos de pizarra profunda"),
    "deepslate_tile_slab": ("slab", DS + "deepslate_tiles", "Losa de baldosas de pizarra profunda"),
    "cobbled_deepslate_stairs": ("stairs", DS + "cobbled_deepslate", "Escaleras de pizarra profunda labrada"),
    "polished_deepslate_stairs": ("stairs", DS + "polished_deepslate", "Escaleras de pizarra profunda pulida"),
    "deepslate_brick_stairs": ("stairs", DS + "deepslate_bricks", "Escaleras de ladrillos de pizarra profunda"),
    "deepslate_tile_stairs": ("stairs", DS + "deepslate_tiles", "Escaleras de baldosas de pizarra profunda"),
    "deepslate_brick_wall": ("wall", DS + "deepslate_bricks", "Muro de ladrillos de pizarra profunda"),
    "deepslate_tile_wall": ("wall", DS + "deepslate_tiles", "Muro de baldosas de pizarra profunda"),
    "cobbled_deepslate_wall": ("wall", DS + "cobbled_deepslate", "Muro de pizarra profunda labrada"),
    "smooth_basalt": ("cube", TB + "smooth_basalt", "Basalto liso"),
    "crying_obsidian": ("cube", TB + "crying_obsidian", "Obsidiana llorosa", {"light": 10}),
    "obsidian": ("cube", TB + "obsidian", "Obsidiana"),
    "waxed_weathered_copper_grate": ("glass", TB + "weathered_copper_grate", "Rejilla de cobre desgastada"),
    # lush caves
    "moss_block": ("cube", TB + "moss_block", "Bloque de musgo"),
    "pale_moss_block": ("cube", TB + "pale_moss_block", "Bloque de musgo pálido"),
    "moss_carpet": ("carpet", TB + "moss_block", "Alfombra de musgo"),
    "pale_moss_carpet": ("carpet", TB + "pale_moss_block", "Alfombra de musgo pálido"),
    "dirt_with_roots": ("cube", TB + "dirt_with_roots", "Tierra enraizada"),
    "clay": ("cube", TB + "clay", "Arcilla"),
    "azalea_leaves": ("leaves", TB + "azalea_leaves", "Hojas de azalea"),
    "azalea_leaves_flowered": ("leaves", TB + "azalea_leaves_flowers", "Hojas de azalea florida"),
    "mangrove_roots": ("glass", {"up": TB + "mangrove_roots_top", "down": TB + "mangrove_roots_top", "side": TB + "mangrove_roots_side"},
                       "Raíces de mangle"),
    "oak_log": ("axis", {"up": TB + "log_oak_top", "down": TB + "log_oak_top", "side": TB + "log_oak"}, "Tronco de roble"),
    "azalea": ("azalea", {"top": TB + "azalea_top", "side": TB + "azalea_side", "plant": TB + "azalea_plant"}, "Azalea"),
    "flowering_azalea": ("azalea", {"top": TB + "flowering_azalea_top", "side": TB + "flowering_azalea_side",
                                    "plant": TB + "azalea_plant"}, "Azalea florida"),
    "fern": ("cross", TB + "fern", "Helecho", {"tint": "grass"}),
    "short_grass": ("cross", TB + "tallgrass", "Hierba", {"tint": "grass"}),
    "hanging_roots": ("cross", TB + "hanging_roots", "Raíces colgantes"),
    "cave_vines": ("cross", TB + "cave_vines_body", "Enredadera de cueva"),
    "cave_vines_body_with_berries": ("cross", TB + "cave_vines_body_berries", "Enredadera de cueva con bayas", {"light": 14}),
    "cave_vines_head_with_berries": ("cross", TB + "cave_vines_head_berries", "Punta de enredadera con bayas luminosas", {"light": 14}),
    "pale_hanging_moss": ("cross", {"body": TB + "pale_hanging_moss_middle", "tip": TB + "pale_hanging_moss_tip"},
                          "Musgo pálido colgante", {"tip": True}),
    "spore_blossom": ("spore", {"flower": TB + "spore_blossom", "base": TB + "spore_blossom_base"}, "Flor de esporas"),
    "big_dripleaf": ("dripleaf", {"leaf": TB + "big_dripleaf_top", "stem": TB + "big_dripleaf_stem"}, "Plantaforma grande"),
    "glow_lichen": ("lichen", TB + "glow_lichen", "Liquen luminoso", {"light": 7}),
    # light and decoration
    "lantern": ("lantern", {"*": "flip:lantern", "link": TB + "chain1"}, "Farol", {"light": 15}),
    "soul_lantern": ("lantern", {"*": "flip:soul_lantern", "link": TB + "chain1"}, "Farol de almas", {"light": 10}),
    "chain": ("chain", {"c1": TB + "chain1", "c2": TB + "chain2"}, "Cadena"),
    "green_candle": ("candle", TB + "candles/green_candle_lit", "Vela verde"),
    "lime_candle": ("candle", TB + "candles/lime_candle_lit", "Vela verde lima"),
    "white_candle": ("candle", TB + "candles/white_candle_lit", "Vela blanca"),
    "ochre_froglight": ("cube", {"up": TB + "ochre_froglight_top", "down": TB + "ochre_froglight_top", "side": TB + "ochre_froglight_side"},
                        "Ranaluz ocre", {"light": 15}),
    "verdant_froglight": ("cube", {"up": TB + "verdant_froglight_top", "down": TB + "verdant_froglight_top",
                                   "side": TB + "verdant_froglight_side"}, "Ranaluz verde", {"light": 15}),
    "pearlescent_froglight": ("cube", {"up": TB + "pearlescent_froglight_top", "down": TB + "pearlescent_froglight_top",
                                       "side": TB + "pearlescent_froglight_side"}, "Ranaluz perlada", {"light": 15}),
}
WOODS = {"oak": ("planks_oak", "roble"), "spruce": ("planks_spruce", "abeto"), "mangrove": ("mangrove_planks", "mangle"),
         "dark_oak": ("planks_big_oak", "roble oscuro"), "pale_oak": ("pale_oak_planks", "roble pálido"),
         "jungle": ("planks_jungle", "jungla"), "cherry": ("cherry_planks", "cerezo")}
for _w, (_t, _es) in WOODS.items():
    DEFS[f"{_w}_slab"] = ("slab", TB + _t, f"Losa de {_es}")

ENGLISH = {k: k.replace("_", " ").capitalize() for k in DEFS}

GROUPS = [
    ("construction", "grupo_toba", "tuff_bricks",
     [k for k in DEFS if "tuff" in k]),
    ("construction", "grupo_abismo", "deepslate_tiles",
     [k for k in DEFS if "deepslate" in k or k in ("smooth_basalt", "crying_obsidian", "obsidian", "waxed_weathered_copper_grate")]),
    ("construction", "grupo_adornos", "lantern",
     [k for k in DEFS if k in ("lantern", "soul_lantern", "chain", "oak_log") or k.endswith("candle") or "froglight" in k
      or (k.endswith("_slab") and k.split("_slab")[0] in WOODS)]),
    ("nature", "grupo_plantas", "flowering_azalea",
     [k for k in DEFS if k in ("moss_block", "pale_moss_block", "moss_carpet", "pale_moss_carpet", "dirt_with_roots", "clay",
                                "azalea_leaves", "azalea_leaves_flowered", "mangrove_roots", "azalea", "flowering_azalea", "fern",
                                "short_grass", "hanging_roots", "cave_vines", "cave_vines_body_with_berries",
                                "cave_vines_head_with_berries", "pale_hanging_moss", "spore_blossom", "big_dripleaf", "glow_lichen")]),
]
GROUP_NAMES = {
    "es": {"grupo_toba": "Toba indestructible", "grupo_abismo": "Abismo indestructible",
           "grupo_adornos": "Luces y adornos indestructibles", "grupo_plantas": "Plantas indestructibles"},
    "en": {"grupo_toba": "Indestructible tuff", "grupo_abismo": "Indestructible abyss",
           "grupo_adornos": "Indestructible lights and decorations", "grupo_plantas": "Indestructible plants"},
}

# How the script turns a vanilla block (with its states) into its clone.
MAP_KIND = {"slab": "slab", "stairs": "stairs", "axis": "axis", "lantern": "lantern", "candle": "candle"}
CLONE_MAP = {f"minecraft:{k}": [f"{NS}:{k}", "tip" if len(v) > 3 and v[3].get("tip") else MAP_KIND.get(v[0], "")]
             for k, v in DEFS.items()}
CLONE_MAP["minecraft:iron_chain"] = [f"{NS}:chain", ""]


# ---------------------------------------------------------------- geometry
def faces(x0, y0, z0, sx, sy, sz, mat=None, only=None):
    """Per-face UVs that follow the block grid; zero-sized faces are left out."""
    bx, bz = x0 + 8, z0 + 8
    f = {}
    if sx and sy:
        for k in ("north", "south"):
            f[k] = {"uv": [bx, 16 - y0 - sy], "uv_size": [sx, sy]}
    if sz and sy:
        for k in ("east", "west"):
            f[k] = {"uv": [bz, 16 - y0 - sy], "uv_size": [sz, sy]}
    if sx and sz:
        for k in ("up", "down"):
            f[k] = {"uv": [bx, bz], "uv_size": [sx, sz]}
    if only:
        f = {k: v for k, v in f.items() if k in only}
    if mat:
        for v in f.values():
            v["material_instance"] = mat
    return f


def cube(x0, y0, z0, sx, sy, sz, mat=None, uv=None, rot=None, only=None):
    c = {"origin": [x0, y0, z0], "size": [sx, sy, sz], "uv": uv or faces(x0, y0, z0, sx, sy, sz, mat, only)}
    if uv and mat:
        for v in c["uv"].values():
            v["material_instance"] = mat
    if rot is not None:
        c["rotation"] = [0, rot, 0]
        c["pivot"] = [0, 8, 0]
    return c


def bone(name, cubes):
    return {"name": name, "pivot": [0, 0, 0], "cubes": cubes}


def geo(name, bones):
    return {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": f"geometry.{NS}.{name}", "texture_width": 16, "texture_height": 16},
        "bones": bones}]}


def uvs(**kw):
    return {k: {"uv": v[:2], "uv_size": v[2:]} for k, v in kw.items()}


DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def stair_boxes(direction, half):
    """The two boxes of a stair (block coordinates -8..8): the slab and the step on the high side."""
    dx, dz = DIRS[direction]
    base_y, step_y = (0, 8) if half == "bottom" else (8, 0)
    x0, sx = (0, 8) if dx > 0 else (-8, 8) if dx < 0 else (-8, 16)
    z0, sz = (0, 8) if dz > 0 else (-8, 8) if dz < 0 else (-8, 16)
    return [(-8, base_y, -8, 16, 8, 16), (x0, step_y, z0, sx, 8, sz)]


def candle_spots():
    return [(0, 0), (-3, 2), (3, 1), (1, -3)]


GEOMETRIES = {
    "slab": geo("slab", [bone("bottom", [cube(-8, 0, -8, 16, 8, 16)]), bone("top", [cube(-8, 8, -8, 16, 8, 16)])]),
    # one stair facing north; the other directions are the same model turned by minecraft:transformation,
    # which turns the collision boxes too (so what you see and what you walk on always match)
    "stairs": geo("stairs", [bone(h, [cube(*b) for b in stair_boxes("north", h)]) for h in ("bottom", "top")]),
    "wall": geo("wall", [bone("post", [cube(-4, 0, -4, 8, 16, 8)])]),
    "carpet": geo("carpet", [bone("carpet", [cube(-8, 0, -8, 16, 1, 16)])]),
    "lichen": geo("lichen", [bone("lichen", [cube(-8, 15.9, -8, 16, 0, 16, only=("down", "up"))])]),
    "spore": geo("spore", [bone("blossom", [
        cube(-8, 15.95, -8, 16, 0, 16, "base", only=("down",)),
        cube(-7, 14.5, -7, 14, 0, 14, "flower", uv=uvs(down=[0, 0, 16, 16], up=[0, 0, 16, 16]))])]),
    "dripleaf": geo("dripleaf", [bone("leaf", [
        cube(-8, 15, -8, 16, 0, 16, "leaf", uv=uvs(up=[0, 0, 16, 16], down=[0, 0, 16, 16])),
        cube(-8, 0, 0, 16, 15, 0, "stem", uv=uvs(north=[0, 1, 16, 15], south=[0, 1, 16, 15]), rot=45),
        cube(-8, 0, 0, 16, 15, 0, "stem", uv=uvs(north=[0, 1, 16, 15], south=[0, 1, 16, 15]), rot=-45)])]),
    "azalea": geo("azalea", [bone("bush", [
        cube(-8, 8, -8, 16, 8, 16, None, uv={**{k: {"uv": [0, 0], "uv_size": [16, 8], "material_instance": "side"}
                                                for k in ("north", "south", "east", "west")},
                                             "up": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "top"},
                                             "down": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "top"}}),
        cube(-8, 0, 0, 16, 8, 0, "plant", uv=uvs(north=[0, 8, 16, 8], south=[0, 8, 16, 8]), rot=45),
        cube(-8, 0, 0, 16, 8, 0, "plant", uv=uvs(north=[0, 8, 16, 8], south=[0, 8, 16, 8]), rot=-45)])]),
    "chain": geo("chain", [bone("chain", [
        cube(-1.5, 0, 0, 3, 16, 0, "c1", uv=uvs(north=[0, 0, 3, 16], south=[0, 0, 3, 16]), rot=45),
        cube(-1.5, 0, 0, 3, 16, 0, "c2", uv=uvs(north=[0, 0, 3, 16], south=[0, 0, 3, 16]), rot=-45)])]),
    "lantern": geo("lantern", [
        bone("stand", [
            cube(-3, 0, -3, 6, 7, 6, None, uv=uvs(north=[0, 2, 6, 7], south=[0, 2, 6, 7], east=[0, 2, 6, 7], west=[0, 2, 6, 7],
                                                  up=[0, 9, 6, 6], down=[0, 9, 6, 6])),
            cube(-2, 7, -2, 4, 2, 4, None, uv=uvs(north=[1, 0, 4, 2], south=[1, 0, 4, 2], east=[1, 0, 4, 2], west=[1, 0, 4, 2],
                                                  up=[1, 10, 4, 4]))]),
        bone("hang", [
            cube(-3, 1, -3, 6, 7, 6, None, uv=uvs(north=[0, 2, 6, 7], south=[0, 2, 6, 7], east=[0, 2, 6, 7], west=[0, 2, 6, 7],
                                                  up=[0, 9, 6, 6], down=[0, 9, 6, 6])),
            cube(-2, 8, -2, 4, 2, 4, None, uv=uvs(north=[1, 0, 4, 2], south=[1, 0, 4, 2], east=[1, 0, 4, 2], west=[1, 0, 4, 2],
                                                  up=[1, 10, 4, 4])),
            cube(-1.5, 10, 0, 3, 6, 0, "link", uv=uvs(north=[0, 0, 3, 6], south=[0, 0, 3, 6]), rot=45),
            cube(-1.5, 10, 0, 3, 6, 0, "link", uv=uvs(north=[0, 0, 3, 6], south=[0, 0, 3, 6]), rot=-45)])]),
    "candle": geo("candle", [bone(f"c{k}", [
        cube(x - 1, 0, z - 1, 2, 6, 2, None, uv=uvs(north=[0, 8, 2, 6], south=[0, 8, 2, 6], east=[0, 8, 2, 6], west=[0, 8, 2, 6],
                                                    up=[0, 6, 2, 2])),
        cube(x - 0.5, 6, z, 1, 3, 0, None, uv=uvs(north=[0, 5, 1, 3], south=[0, 5, 1, 3])),
        cube(x, 6, z - 0.5, 0, 3, 1, None, uv=uvs(east=[0, 5, 1, 3], west=[0, 5, 1, 3]))])
        for k, (x, z) in enumerate(candle_spots())]),
}


# ---------------------------------------------------------------- blocks
def key(name, part=""):
    return f"mz_{name}" + (f"_{part}" if part else "")


def box(x0, y0, z0, sx, sy, sz):
    return {"origin": [x0, y0, z0], "size": [sx, sy, sz]}


def block(name):
    kind, textures, _es, *rest = DEFS[name]
    opts = rest[0] if rest else {}
    cid = f"{NS}:{name}"
    desc = {"identifier": cid}
    comps = {"minecraft:destructible_by_mining": False, "minecraft:destructible_by_explosion": False}
    perms = []

    def mats(render, **extra):
        if isinstance(textures, dict):
            out = {}
            for part in textures:
                face = {"side": "*"}.get(part, part)
                out[face] = {"texture": key(name, part), "render_method": render, **extra}
            out.setdefault("*", dict(next(iter(out.values()))))
            return out
        return {"*": {"texture": key(name), "render_method": render, **extra}}

    if kind in ("cube", "axis"):
        comps["minecraft:light_dampening"] = 15
    if kind in ("cube", "axis", "glass", "leaves"):
        render = {"cube": "opaque", "axis": "opaque", "glass": "alpha_test_single_sided", "leaves": "alpha_test_to_opaque"}[kind]
        comps["minecraft:geometry"] = "minecraft:geometry.full_block"
        comps["minecraft:material_instances"] = mats(render)
        if kind == "glass":
            comps["minecraft:light_dampening"] = 0
        if kind == "leaves":
            comps["minecraft:light_dampening"] = 1
        if kind == "axis":
            desc["traits"] = {"minecraft:placement_position": {"enabled_states": ["minecraft:block_face"]}}
            perms = [
                {"condition": "q.block_state('minecraft:block_face') == 'east' || q.block_state('minecraft:block_face') == 'west'",
                 "components": {"minecraft:transformation": {"rotation": [0, 0, 90]}}},
                {"condition": "q.block_state('minecraft:block_face') == 'north' || q.block_state('minecraft:block_face') == 'south'",
                 "components": {"minecraft:transformation": {"rotation": [90, 0, 0]}}},
            ]
    elif kind == "slab":
        desc["traits"] = {"minecraft:placement_position": {"enabled_states": ["minecraft:vertical_half"]}}
        comps["minecraft:geometry"] = {"identifier": f"geometry.{NS}.slab", "bone_visibility": {
            "bottom": "q.block_state('minecraft:vertical_half') == 'bottom'",
            "top": "q.block_state('minecraft:vertical_half') == 'top'"}}
        comps["minecraft:material_instances"] = mats("opaque")
        comps["minecraft:light_dampening"] = 15  # no light through floors, ceilings and ledges of slabs
        for half, y in (("bottom", 0), ("top", 8)):
            perms.append({"condition": f"q.block_state('minecraft:vertical_half') == '{half}'", "components": {
                "minecraft:collision_box": box(-8, y, -8, 16, 8, 16), "minecraft:selection_box": box(-8, y, -8, 16, 8, 16)}})
    elif kind == "stairs":
        desc["traits"] = {"minecraft:placement_direction": {"enabled_states": ["minecraft:cardinal_direction"]},
                          "minecraft:placement_position": {"enabled_states": ["minecraft:vertical_half"]}}
        comps["minecraft:geometry"] = {"identifier": f"geometry.{NS}.stairs", "bone_visibility": {
            h: f"q.block_state('minecraft:vertical_half') == '{h}'" for h in ("bottom", "top")}}
        comps["minecraft:material_instances"] = mats("opaque")
        comps["minecraft:light_dampening"] = 15
        # the official rotations for minecraft:cardinal_direction
        yaw = {"north": 0, "west": 90, "south": 180, "east": -90}
        for d in DIRS:
            for h in ("bottom", "top"):
                perms.append({
                    "condition": f"q.block_state('minecraft:cardinal_direction') == '{d}' && q.block_state('minecraft:vertical_half') == '{h}'",
                    "components": {"minecraft:transformation": {"rotation": [0, yaw[d], 0]},
                                   "minecraft:collision_box": [box(*b) for b in stair_boxes("north", h)]}})
    elif kind in ("wall", "carpet"):
        comps["minecraft:geometry"] = f"geometry.{NS}.{kind}"
        comps["minecraft:material_instances"] = mats("opaque")
        comps["minecraft:light_dampening"] = 15 if kind == "wall" else 0
        shape = box(-4, 0, -4, 8, 16, 8) if kind == "wall" else box(-8, 0, -8, 16, 1, 16)
        comps["minecraft:collision_box"] = shape
        comps["minecraft:selection_box"] = shape
    elif kind == "cross":
        extra = {"ambient_occlusion": 0, "face_dimming": False}
        if opts.get("tint"):
            extra["tint_method"] = opts["tint"]
        comps["minecraft:geometry"] = "minecraft:geometry.cross"
        if opts.get("tip"):
            desc["states"] = {f"{NS}:tip": [False, True]}
            comps["minecraft:material_instances"] = {"*": {"texture": key(name, "body"), "render_method": "alpha_test", **extra}}
            perms.append({"condition": f"q.block_state('{NS}:tip')", "components": {
                "minecraft:geometry": "minecraft:geometry.cross",
                "minecraft:material_instances": {"*": {"texture": key(name, "tip"), "render_method": "alpha_test", **extra}}}})
        else:
            comps["minecraft:material_instances"] = {"*": {"texture": key(name), "render_method": "alpha_test", **extra}}
        comps["minecraft:collision_box"] = False
        comps["minecraft:selection_box"] = box(-6, 0, -6, 12, 16, 12)
        comps["minecraft:light_dampening"] = 0
    else:  # special models
        model = {"spore": "spore", "dripleaf": "dripleaf", "azalea": "azalea", "chain": "chain", "lantern": "lantern",
                 "candle": "candle", "lichen": "lichen"}[kind]
        render = "alpha_test"
        m = {}
        for part, path in (textures.items() if isinstance(textures, dict) else [("*", textures)]):
            m[part] = {"texture": key(name, "" if part == "*" else part), "render_method": render, "ambient_occlusion": 0}
        m.setdefault("*", dict(next(iter(m.values()))))
        comps["minecraft:material_instances"] = m
        comps["minecraft:light_dampening"] = 0
        geom = {"identifier": f"geometry.{NS}.{model}"}
        if kind == "lantern":
            desc["traits"] = {"minecraft:placement_position": {"enabled_states": ["minecraft:block_face"]}}
            geom["bone_visibility"] = {"stand": "q.block_state('minecraft:block_face') != 'down'",
                                       "hang": "q.block_state('minecraft:block_face') == 'down'"}
            comps["minecraft:collision_box"] = box(-3, 0, -3, 6, 9, 6)
            comps["minecraft:selection_box"] = box(-3, 0, -3, 6, 9, 6)
            perms.append({"condition": "q.block_state('minecraft:block_face') == 'down'", "components": {
                "minecraft:collision_box": box(-3, 1, -3, 6, 9, 6), "minecraft:selection_box": box(-3, 1, -3, 6, 15, 6)}})
        elif kind == "candle":
            desc["states"] = {f"{NS}:candles": [0, 1, 2, 3]}
            geom["bone_visibility"] = {f"c{k}": f"q.block_state('{NS}:candles') >= {k}" for k in range(4)}
            comps["minecraft:collision_box"] = box(-5, 0, -5, 10, 6, 10)
            comps["minecraft:selection_box"] = box(-5, 0, -5, 10, 7, 10)
            for k in range(4):
                perms.append({"condition": f"q.block_state('{NS}:candles') == {k}",
                              "components": {"minecraft:light_emission": 3 * (k + 1)}})
        elif kind == "chain":
            comps["minecraft:collision_box"] = box(-1.5, 0, -1.5, 3, 16, 3)
            comps["minecraft:selection_box"] = box(-1.5, 0, -1.5, 3, 16, 3)
        elif kind == "dripleaf":
            comps["minecraft:collision_box"] = box(-8, 15, -8, 16, 1, 16)
        elif kind == "azalea":
            comps["minecraft:light_dampening"] = 1
        else:  # spore blossom, lichen: no collision
            comps["minecraft:collision_box"] = False
            comps["minecraft:selection_box"] = box(-6, 12, -6, 12, 4, 12)
        comps["minecraft:geometry"] = geom
    if "light" in opts:
        comps["minecraft:light_emission"] = opts["light"]
    out = {"format_version": FORMAT, "minecraft:block": {"description": desc, "components": comps}}
    if perms:
        out["minecraft:block"]["permutations"] = perms
    return out


def textures():
    """terrain_texture entries and flipbooks (the lanterns are animated)."""
    data, flip = {}, []
    for name, (kind, tx, *_rest) in DEFS.items():
        for part, path in (tx.items() if isinstance(tx, dict) else [("", tx)]):
            k = key(name, "" if part in ("", "*") else part)
            if path.startswith("flip:"):
                src = TB + path[5:]
                flip.append({"flipbook_texture": src, "atlas_tile": k, "ticks_per_frame": 8})
                path = src
            data[k] = {"textures": path}
    return data, flip


def write(bp, rp, lang_es, lang_en, write_json):
    for name in DEFS:
        write_json(os.path.join(bp, "blocks", "clones", f"{name}.json"), block(name))
    for model, g in GEOMETRIES.items():
        write_json(os.path.join(rp, "models", "blocks", f"{NS}_{model}.geo.json"), g)
    data, flip = textures()
    write_json(os.path.join(rp, "textures", "terrain_texture.json"),
               {"resource_pack_name": NS, "texture_name": "atlas.terrain", "padding": 8, "num_mip_levels": 4,
                "texture_data": data})
    write_json(os.path.join(rp, "textures", "flipbook_textures.json"), flip)
    catalog = {"format_version": "1.21.60", "minecraft:crafting_items_catalog": {"categories": []}}
    cats = {}
    for cat, group, icon, items in GROUPS:
        cats.setdefault(cat, []).append({"group_identifier": {"icon": f"{NS}:{icon}", "name": f"{NS}:{group}"},
                                         "items": [f"{NS}:{i}" for i in items]})
    catalog["minecraft:crafting_items_catalog"]["categories"] = [{"category_name": c, "groups": g} for c, g in cats.items()]
    write_json(os.path.join(bp, "item_catalog", "crafting_item_catalog.json"), catalog)
    for name, (_k, _t, es, *_r) in DEFS.items():
        lang_es[f"tile.{NS}:{name}.name"] = f"{es} (indestructible)"
        lang_en[f"tile.{NS}:{name}.name"] = f"{ENGLISH[name]} (indestructible)"
    for g in GROUP_NAMES["es"]:
        lang_es[f"{NS}:{g}"] = GROUP_NAMES["es"][g]
        lang_en[f"{NS}:{g}"] = GROUP_NAMES["en"][g]


def check(ids):
    """Every block the generator uses has a clone or is meant to stay vanilla."""
    missing = sorted(i for i in ids if i.replace("minecraft:", "") not in DEFS
                     and i.replace("minecraft:", "") not in KEEP_VANILLA and i not in CLONE_MAP)
    grouped = {i for *_x, items in GROUPS for i in items}
    return missing, sorted(set(DEFS) - grouped)
