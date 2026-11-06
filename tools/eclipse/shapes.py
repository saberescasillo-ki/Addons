"""The Eclipse's 3D shapes: real models instead of particles that turn to face the camera.

  * fx_gem    a bullet: a spinning diamond (octahedron-like) with a glowing shell;
  * fx_beam   a laser: a cylinder of light along its facing, centred, `len` long;
  * fx_column a vertical cylinder of light (celestial rays, safe zones, portals);
  * fx_tube   a circular wall of light that fades upwards (the edge of circles on the
              floor), growing or shrinking by itself: radius r0 + rate * t, at most rmax;
  * fx_wall   a straight wall of light that fades upwards (lines on the floor).

Each takes its colour and sizes from entity properties the script sets; the client
animates growth and fading from q.life_time, so the script only spawns and removes them.
"""
import math
import os

from PIL import Image

COLORS = [  # the order of COLOR_INDEX in scripts/fx.js
    ("white", (255, 255, 255)), ("gold", (255, 204, 72)), ("cyan", (102, 235, 255)), ("violet", (173, 107, 255)),
    ("magenta", (255, 90, 209)), ("azure", (90, 140, 255)), ("crimson", (255, 56, 77)), ("danger", (255, 64, 100)),
    ("safe", (255, 230, 115)), ("jade", (90, 255, 166)),
]
def P(name, kind, rng, default=0):
    """A synced entity property; float ones need float defaults and ranges (0.0, not 0)."""
    if kind == "float":
        rng, default = [float(rng[0]), float(rng[1])], float(default)
    return (name, {"type": kind, "range": rng, "default": default, "client_sync": True})
PROPS = {
    "gem": [P("eclipse:size", "float", [0.0, 3.0])],
    "beam": [P("eclipse:w", "float", [0.0, 4.0]), P("eclipse:len", "float", [0.0, 96.0]),
             P("eclipse:spin", "float", [-360.0, 360.0]), ("eclipse:shrink", {"type": "bool", "default": False, "client_sync": True})],
    "column": [P("eclipse:w", "float", [0.0, 8.0]), P("eclipse:len", "float", [0.0, 64.0]),
               ("eclipse:shrink", {"type": "bool", "default": False, "client_sync": True})],
    "tube": [P("eclipse:r0", "float", [0.0, 64.0]), P("eclipse:rate", "float", [-64.0, 64.0]),
             P("eclipse:rmax", "float", [0.0, 64.0]), P("eclipse:h", "float", [0.0, 8.0])],
    "wall": [P("eclipse:len", "float", [0.0, 96.0]), P("eclipse:h", "float", [0.0, 8.0])],
}
FADE = ("math.clamp(q.life_time * 10, 0, 1) * math.clamp((q.property('eclipse:life') - q.life_time) * 6, 0, 1)")
SHRINK = "(q.property('eclipse:shrink') ? math.max(0, 1 - q.life_time / math.max(0.05, q.property('eclipse:life'))) : 1)"


def _faces(uv, faces):
    return {f: {"uv": [0, 0], "uv_size": [uv, uv]} for f in faces}


ALL = ("north", "south", "east", "west", "up", "down")


def geometries():
    geos = {}
    # a diamond: a cube turned on its corner, plus a glowing shell
    gem = {"origin": [-2, -2, -2], "size": [4, 4, 4], "pivot": [0, 0, 0], "rotation": [45, 0, 35.26], "uv": _faces(16, ALL)}
    geos["gem"] = [{"name": "gem", "pivot": [0, 0, 0], "cubes": [gem]},
                   {"name": "glow", "parent": "gem", "pivot": [0, 0, 0], "cubes": [{**gem, "inflate": 1.1}]}]
    # cylinders: four square prisms turned around their axis (16 sides), one block across
    geos["beam"] = [{"name": "beam", "pivot": [0, 0, 0], "cubes": [
        {"origin": [-8, -8, -8], "size": [16, 16, 16], "pivot": [0, 0, 0], "rotation": [0, 0, a], "uv": _faces(16, ALL)}
        for a in (0, 22.5, 45, 67.5)]}]
    geos["column"] = [{"name": "column", "pivot": [0, 0, 0], "cubes": [
        {"origin": [-8, 0, -8], "size": [16, 16, 16], "pivot": [0, 0, 0], "rotation": [0, a, 0],
         "uv": _faces(16, ("north", "south", "east", "west"))} for a in (0, 22.5, 45, 67.5)]}]
    # a ring wall of 24 thin panels, radius and height one block
    geos["tube"] = [{"name": "tube", "pivot": [0, 0, 0], "cubes": [
        {"origin": [-2.1, 0, 16], "size": [4.2, 16, 0], "pivot": [0, 0, 0], "rotation": [0, k * 15, 0],
         "uv": _faces(16, ("north", "south"))} for k in range(24)]}]
    geos["wall"] = [{"name": "wall", "pivot": [0, 0, 0], "cubes": [
        {"origin": [0, 0, -8], "size": [0, 16, 16], "uv": _faces(16, ("east", "west"))}]}]
    return geos


def textures(folder):
    """Per colour: a gem (bright facets), a beam (bright centre, dim edges) and a wall
    (bright at the floor, fading to nothing upwards). Additive materials: black = clear."""
    os.makedirs(folder, exist_ok=True)
    for name, (r, g, b) in COLORS:
        gem = Image.new("RGBA", (16, 16))
        beam = Image.new("RGBA", (16, 16))
        wall = Image.new("RGBA", (16, 16))
        for y in range(16):
            for x in range(16):
                u, v = (x + 0.5) / 8 - 1, (y + 0.5) / 8 - 1
                edge = max(abs(u), abs(v))
                k = 1.0 if edge < 0.55 else (0.55 if edge > 0.85 else 0.8)
                lift = 0.35 * max(0.0, 1 - math.hypot(u + 0.4, v + 0.4) / 0.9)   # a highlight
                gem.putpixel((x, y), tuple(min(255, int(c * k + 255 * lift)) for c in (r, g, b)) + (255,))
                core = max(0.0, 1 - abs(u)) ** 1.5 * (0.6 + 0.4 * max(0.0, 1 - abs(v)) ** 0.5)
                white = max(0.0, 1 - abs(u) / 0.35) ** 2
                beam.putpixel((x, y), tuple(min(255, int(c * core + 255 * white * 0.8)) for c in (r, g, b)) + (255,))
                t = (y + 0.5) / 16                                               # 0 at the top, 1 at the floor
                fade = 1.0 if y == 15 else t ** 2.2
                wall.putpixel((x, y), tuple(int(c * fade) for c in (r, g, b)) + (255,))
        gem.save(os.path.join(folder, f"gem_{name}.png"))
        beam.save(os.path.join(folder, f"beam_{name}.png"))
        wall.save(os.path.join(folder, f"wall_{name}.png"))


def animations():
    p = lambda k: f"q.property('eclipse:{k}')"  # noqa: E731
    return {
        "animation.eclipse.fx_gem": {"loop": True, "bones": {"gem": {
            "rotation": [0, "q.life_time * 220", 0],
            "scale": [f"{p('size')} * 6 * math.clamp(q.life_time * 10, 0, 1)",
                      f"{p('size')} * 9 * math.clamp(q.life_time * 10, 0, 1)",
                      f"{p('size')} * 6 * math.clamp(q.life_time * 10, 0, 1)"]}}},
        "animation.eclipse.fx_beam": {"loop": True, "bones": {"beam": {
            "rotation": [0, f"{p('spin')} * q.life_time", 0],
            "scale": [f"{p('w')} * 2 * {FADE} * {SHRINK}", f"{p('w')} * 2 * {FADE} * {SHRINK}", p("len")]}}},
        "animation.eclipse.fx_column": {"loop": True, "bones": {"column": {
            "scale": [f"{p('w')} * 2 * {FADE} * {SHRINK}", f"{p('len')} * math.clamp(q.life_time * 8, 0, 1)",
                      f"{p('w')} * 2 * {FADE} * {SHRINK}"]}}},
        "animation.eclipse.fx_tube": {"loop": True, "bones": {"tube": {
            "scale": [f"math.clamp({p('r0')} + {p('rate')} * q.life_time, 0.01, {p('rmax')})", f"{p('h')} * {FADE}",
                      f"math.clamp({p('r0')} + {p('rate')} * q.life_time, 0.01, {p('rmax')})"]}}},
        "animation.eclipse.fx_wall": {"loop": True, "bones": {"wall": {
            "scale": [1, f"{p('h')} * {FADE}", p("len")]}}},
    }


def build(bp, rp, dump):
    tex = os.path.join(rp, "textures", "eclipse", "fx")
    textures(tex)
    geos = geometries()
    dump(os.path.join(rp, "models", "entity", "eclipse_fx.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": f"geometry.eclipse.fx_{k}", "texture_width": 16, "texture_height": 16,
                            "visible_bounds_width": 64, "visible_bounds_height": 64, "visible_bounds_offset": [0, 0, 0]},
            "bones": bones} for k, bones in geos.items()]})
    dump(os.path.join(rp, "animations", "eclipse_fx.animation.json"), {"format_version": "1.8.0", "animations": animations()})
    rcs = {}
    for kind in geos:
        image = {"gem": "gem", "beam": "beam", "column": "beam", "tube": "wall", "wall": "wall"}[kind]
        props = dict([P("eclipse:color", "int", [0, len(COLORS) - 1]), P("eclipse:life", "float", [0.0, 60.0], 1.0)]
                     + PROPS[kind])
        dump(os.path.join(bp, "entities", f"fx_{kind}.json"), {
            "format_version": "1.21.50",
            "minecraft:entity": {
                "description": {"identifier": f"eclipse:fx_{kind}", "is_spawnable": False, "is_summonable": True,
                                "properties": props},
                "components": {
                    "minecraft:type_family": {"family": ["eclipse", "eclipse_fx", "inanimate"]},
                    "minecraft:health": {"value": 1, "max": 1},
                    "minecraft:collision_box": {"width": 0.1, "height": 0.1},
                    "minecraft:custom_hit_test": {"hitboxes": [{"width": 0, "height": 0, "pivot": [0, 200, 0]}]},
                    "minecraft:physics": {"has_gravity": False, "has_collision": False},
                    "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                    "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                    "minecraft:fire_immune": {},
                    "minecraft:loot": {"table": "loot_tables/empty.json"}}}})
        textures_ = {f"c{i}": f"textures/eclipse/fx/{image}_{name}" for i, (name, _) in enumerate(COLORS)}
        materials = {"default": "entity_beam_additive"}
        rc_mats = [{"*": "Material.default"}]
        if kind == "gem":
            materials = {"default": "entity_emissive_alpha", "glow": "entity_beam_additive"}
            rc_mats = [{"*": "Material.default"}, {"glow": "Material.glow"}]
        dump(os.path.join(rp, "entity", f"fx_{kind}.entity.json"), {
            "format_version": "1.10.0",
            "minecraft:client_entity": {"description": {
                "identifier": f"eclipse:fx_{kind}", "materials": materials, "textures": textures_,
                "geometry": {"default": f"geometry.eclipse.fx_{kind}"},
                "animations": {"shape": f"animation.eclipse.fx_{kind}"},
                "scripts": {"animate": ["shape"]},
                "render_controllers": [f"controller.render.eclipse.fx_{kind}"]}}})
        rcs[f"controller.render.eclipse.fx_{kind}"] = {
            "arrays": {"textures": {"Array.colors": [f"Texture.c{i}" for i in range(len(COLORS))]}},
            "geometry": "Geometry.default", "materials": rc_mats,
            "textures": ["Array.colors[q.property('eclipse:color')]"]}
    dump(os.path.join(rp, "render_controllers", "eclipse_fx.render_controllers.json"),
         {"format_version": "1.8.0", "render_controllers": rcs})
