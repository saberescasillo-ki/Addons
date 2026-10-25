"""Bedrock geometry builder + the medieval mob models.

Coordinates are in pixels (16 = one block), Y up, the mob faces -Z and its
right side is -X (same conventions as the vanilla models). UVs are packed
automatically and the texture is painted from the same cube list.
"""
import math
import random

from PIL import Image

from textures import (
    Mat, col, d_belt, d_border, d_clear, d_creeper_face, d_cross, d_ender_eyes,
    d_goggles, d_hline, d_px, d_rect, d_skull_face, d_slime_face, d_spots,
    d_tattered, d_tnt, d_visor, d_vline, d_zombie_face,
)


class Cube:
    def __init__(self, origin, size, mat, inflate=0.0, pivot=None, rotation=None):
        for s in size:
            assert float(s).is_integer() and s > 0, size
        self.origin, self.size, self.mat = origin, [int(s) for s in size], mat
        self.inflate, self.pivot, self.rotation = inflate, pivot, rotation
        w, h, d = self.size
        self.rw, self.rh = 2 * (w + d), d + h
        self.uv = None

    def to_json(self):
        c = {"origin": self.origin, "size": self.size, "uv": list(self.uv)}
        if self.inflate:
            c["inflate"] = self.inflate
        if self.rotation:
            c["pivot"] = self.pivot
            c["rotation"] = self.rotation
        return c


class Model:
    def __init__(self, name, tex_w=128, bounds=(2.5, 3.0), ns="medieval"):
        self.name, self.tex_w, self.bounds, self.ns = name, tex_w, bounds, ns
        self.geos = {"default": []}  # geometry key -> list of bones

    def bone(self, name, pivot, parent=None, geo="default", rotation=None):
        b = {"name": name, "pivot": pivot, "cubes": []}
        if parent:
            b["parent"] = parent
        if rotation:
            b["rotation"] = rotation
        self.geos.setdefault(geo, []).append(b)
        return b

    def cube(self, bone, origin, size, mat, **kw):
        c = Cube(origin, size, mat, **kw)
        bone["cubes"].append(c)
        return c

    def all_cubes(self):
        return [c for bones in self.geos.values() for b in bones for c in b["cubes"]]

    def build(self, seed, res=1):
        """Packs UVs and paints the texture. res > 1 paints an HD texture
        (res texels per model pixel); the geometry UVs stay in model units."""
        cubes = sorted(self.all_cubes(), key=lambda c: (-c.rh, -c.rw))
        tw = max([self.tex_w] + [c.rw for c in cubes])
        x = y = row_h = 0
        for c in cubes:
            if x + c.rw > tw:
                x, y, row_h = 0, y + row_h, 0
            c.uv = (x, y)
            x += c.rw
            row_h = max(row_h, c.rh)
        th = 16
        while th < y + row_h:
            th *= 2
        img = Image.new("RGBA", (tw * res, th * res), (0, 0, 0, 0))
        rng = random.Random(seed)
        for c in cubes:
            w, h, d = c.size
            c.mat.paint(img, c.uv[0] * res, c.uv[1] * res, w, h, d, rng, res=res)
        self.tex_size = (tw, th)
        return img

    def geometry_json(self):
        out = []
        for key, bones in self.geos.items():
            ident = f"geometry.{self.ns}.{self.name}" + ("" if key == "default" else f"_{key}")
            jb = []
            for b in bones:
                nb = {k: v for k, v in b.items() if k != "cubes"}
                if b["cubes"]:
                    nb["cubes"] = [c.to_json() for c in b["cubes"]]
                jb.append(nb)
            out.append({
                "description": {
                    "identifier": ident,
                    "texture_width": self.tex_size[0],
                    "texture_height": self.tex_size[1],
                    "visible_bounds_width": self.bounds[0],
                    "visible_bounds_height": self.bounds[1],
                    "visible_bounds_offset": [0, self.bounds[1] / 2, 0],
                },
                "bones": jb,
            })
        return {"format_version": "1.12.0", "minecraft:geometry": out}


# ------------------------------------------------------------------ bodies
def humanoid(m, head, body, arm, leg, arm_w=4, leg_w=4, arm_mats=None, leg_mats=None):
    """Vanilla-proportioned biped. Returns the bones dict."""
    B = {}
    B["body"] = m.bone("body", [0, 24, 0])
    if body:
        m.cube(B["body"], [-4, 12, -2], [8, 12, 4], body)
    B["head"] = m.bone("head", [0, 24, 0], "body")
    if head:
        m.cube(B["head"], [-4, 24, -4], [8, 8, 8], head)
    a, l = arm_w, leg_w
    ra, la = (arm_mats or (arm, arm))
    rl, ll = (leg_mats or (leg, leg))
    B["rightArm"] = m.bone("rightArm", [-5, 22, 0], "body")
    m.cube(B["rightArm"], [-4 - a, 12, -a / 2], [a, 12, a], ra)
    B["leftArm"] = m.bone("leftArm", [5, 22, 0], "body")
    m.cube(B["leftArm"], [4, 12, -a / 2], [a, 12, a], la)
    lx = 1.9 if l == 4 else 2
    B["rightLeg"] = m.bone("rightLeg", [-lx, 12, 0], "body")
    m.cube(B["rightLeg"], [-lx - l / 2, 0, -l / 2], [l, 12, l], rl)
    B["leftLeg"] = m.bone("leftLeg", [lx, 12, 0], "body")
    m.cube(B["leftLeg"], [lx - l / 2, 0, -l / 2], [l, 12, l], ll)
    ix = -6 if a == 4 else -5
    B["rightItem"] = m.bone("rightItem", [ix, 15, 1], "rightArm")
    B["leftItem"] = m.bone("leftItem", [-ix, 15, 1], "leftArm")
    return B


def enderman(m, head, body, limb):
    B = {}
    B["body"] = m.bone("body", [0, 40, 0])
    m.cube(B["body"], [-4, 28, -2], [8, 12, 4], body)
    B["head"] = m.bone("head", [0, 40, 0], "body")
    m.cube(B["head"], [-4, 40, -4], [8, 8, 8], head)
    B["rightArm"] = m.bone("rightArm", [-5, 39, 0], "body")
    m.cube(B["rightArm"], [-6, 11, -1], [2, 28, 2], limb)
    B["leftArm"] = m.bone("leftArm", [5, 39, 0], "body")
    m.cube(B["leftArm"], [4, 11, -1], [2, 28, 2], limb)
    B["rightLeg"] = m.bone("rightLeg", [-2, 28, 0], "body")
    m.cube(B["rightLeg"], [-3, 0, -1], [2, 28, 2], limb)
    B["leftLeg"] = m.bone("leftLeg", [2, 28, 0], "body")
    m.cube(B["leftLeg"], [1, 0, -1], [2, 28, 2], limb)
    B["rightItem"] = m.bone("rightItem", [-5, 14, 1], "rightArm")
    return B


def creeper(m, head, body, leg):
    B = {}
    B["body"] = m.bone("body", [0, 6, 0])
    m.cube(B["body"], [-4, 6, -2], [8, 12, 4], body)
    B["head"] = m.bone("head", [0, 18, 0], "body")
    m.cube(B["head"], [-4, 18, -4], [8, 8, 8], head)
    for name, px, pz in (("leg0", -2, 4), ("leg1", 2, 4), ("leg2", -2, -4), ("leg3", 2, -4)):
        B[name] = m.bone(name, [px, 6, pz], "body")
        m.cube(B[name], [px - 2, 0, pz - 2 if pz > 0 else pz - 2], [4, 6, 4], leg)
    return B


def slime(m, inner, outer, face_mat):
    B = {}
    B["root"] = m.bone("root", [0, 0, 0])
    m.cube(B["root"], [-3, 1, -3], [6, 6, 6], inner)
    m.cube(B["root"], [-3.25, 4, -3.5], [2, 2, 2], face_mat)
    m.cube(B["root"], [1.25, 4, -3.5], [2, 2, 2], face_mat)
    m.cube(B["root"], [0, 2, -3.5], [1, 1, 1], face_mat)
    B["outer_root"] = m.bone("root", [0, 0, 0], geo="outer")
    m.cube(B["outer_root"], [-4, 0, -4], [8, 8, 8], outer)
    return B


# ---------------------------------------------------------------- palettes
ZSKIN = "#5f7d4b"
ZROT = "#3d5a30"
BONE = "#d9d3be"
STEEL = "#9ba4ae"
DSTEEL = "#555b63"
GOLD = "#d6a92e"


def zombie_knight():
    m = Model("zombie_knight")
    chain = Mat(STEEL, "chain")
    plate = Mat(STEEL, "plate", accent="#e8edf2")
    B = humanoid(m, None, chain, chain, Mat(DSTEEL, "metal"),
                 arm_mats=(chain, chain))
    # Great helm (replaces the head) with visor and a red crest
    m.cube(B["head"], [-4.5, 23.5, -4.5], [9, 9, 9], Mat(STEEL, "metal").with_deco(front=d_visor()))
    m.cube(B["head"], [-0.5, 32.5, -3.5], [1, 3, 8], Mat("#9b1c1c", "cloth", noise=0.12))
    # Breastplate, tabard with a gold cross, back tabard
    m.cube(B["body"], [-4.5, 17, -2.5], [9, 7, 5], plate)
    tabard = Mat("#8e1b1b", "cloth", accent=GOLD)
    m.cube(B["body"], [-3, 6, -3.5], [6, 11, 1], tabard.with_deco(front=d_cross(GOLD, 3)))
    m.cube(B["body"], [-3, 6, 2.5], [6, 11, 1], tabard.with_deco(back=d_cross(GOLD, 3)))
    m.cube(B["body"], [-4.5, 12, -2.5], [9, 2, 5], Mat("#4a2c16", "leather").with_deco(front=d_px([(4, 0), (4, 1)], GOLD)))
    # Pauldrons and gauntlets
    m.cube(B["rightArm"], [-9, 19, -3], [5, 4, 6], plate)
    m.cube(B["leftArm"], [4, 19, -3], [5, 4, 6], plate)
    m.cube(B["rightArm"], [-8.5, 11.5, -2.5], [5, 4, 5], Mat(DSTEEL, "plate", accent=STEEL))
    m.cube(B["leftArm"], [3.5, 11.5, -2.5], [5, 4, 5], Mat(DSTEEL, "plate", accent=STEEL))
    # Sabatons
    for leg, x in (("rightLeg", -4.4), ("leftLeg", -0.6)):
        m.cube(B[leg], [x, 0, -3], [5, 3, 5], Mat(STEEL, "metal"))
    return m


def zombie_archer():
    m = Model("zombie_archer")
    skin = Mat(ZSKIN, "skin", accent=ZROT, prob=0.12)
    tunic = Mat("#3e5c2b", "cloth", accent="#2b3f1d").with_deco(sides=d_belt(-3, "#4a2c16", GOLD))
    trousers = Mat("#5a4027", "cloth").with_deco(sides=d_hline(-2, "#2e1f12"), all=[])
    B = humanoid(m, skin.with_deco(front=d_zombie_face(pupil="#a3ff6b")), tunic, skin, trousers)
    # Leather cap with a long red/white feather
    m.cube(B["head"], [-4.5, 28.5, -4.5], [9, 4, 9], Mat("#6b4423", "leather", accent="#3e2a17").with_deco(sides=d_hline(-1, "#3e2a17")))
    m.cube(B["head"], [3.5, 30, -1], [1, 7, 3], Mat("#f2f2f2", "feather", accent="#b52020"),
           pivot=[4, 30, 0], rotation=[0, 0, -25])
    # Huge iron-studded gauntlets: the "fists" that hurl arrows
    fist = Mat("#6b4423", "leather", accent="#cfd6dc").with_deco(front=d_px([(1, 1), (4, 1), (1, 4), (4, 4)], "#cfd6dc"))
    m.cube(B["rightArm"], [-9, 10, -3], [6, 6, 6], fist)
    m.cube(B["leftArm"], [3, 10, -3], [6, 6, 6], fist)
    # Quiver full of arrows on the back (tilted)
    m.cube(B["body"], [-1, 12, 2], [4, 11, 3], Mat("#7a4e2a", "leather", accent="#3e2a17").with_deco(sides=d_belt(1, GOLD)),
           pivot=[1, 18, 3.5], rotation=[0, 0, 22])
    m.cube(B["body"], [-0.5, 23, 2.5], [3, 4, 2], Mat("#efefef", "feather", accent="#c43a3a"),
           pivot=[1, 18, 3.5], rotation=[0, 0, 22])
    # Strap across the chest
    m.cube(B["body"], [-4.25, 12, -2.25], [1, 12, 1], Mat("#3e2a17", "leather"), pivot=[0, 18, -2], rotation=[0, 0, -35])
    return m


def zombie_plague():
    m = Model("zombie_plague")
    skin = Mat("#6f7f4d", "skin", accent="#8a5a6a", prob=0.16)
    robe = Mat("#2a2420", "cloth", accent="#4b3b2a", noise=0.1)
    B = humanoid(m, skin.with_deco(front=[d_zombie_face(), d_goggles()]), robe, robe,
                 Mat("#1d1915", "cloth"))
    # Leather hood with an opening for the face
    m.cube(B["head"], [-4.5, 23.5, -4.5], [9, 9, 9], Mat("#3b2c1f", "leather", accent="#22180f").with_deco(front=d_clear(1, 2, -1, -1)))
    # Plague-doctor beak
    m.cube(B["head"], [-1, 24.5, -10], [2, 2, 6], Mat("#cbb68a", "leather", accent="#8c7652"),
           pivot=[0, 26, -4.5], rotation=[12, 0, 0])
    # Wide-brimmed hat
    m.cube(B["head"], [-6.5, 32, -6.5], [13, 1, 13], Mat("#1b1714", "cloth"))
    m.cube(B["head"], [-4, 33, -4], [8, 3, 8], Mat("#1b1714", "cloth").with_deco(sides=d_hline(-1, "#6d1f1f")))
    # Long robe skirt that hides the legs, tattered hem
    m.cube(B["body"], [-4.5, 1, -2.5], [9, 12, 5], robe.with_deco(sides=[d_belt(0, "#5a3a1e", "#a08a52"), d_tattered(2, 0.5)]))
    # Censer hanging from the left hand
    m.cube(B["leftArm"], [5.5, 4, -1], [2, 3, 2], Mat("#7a6a3a", "gold").with_deco(front=d_px([(0, 1)], "#9cff4a")))
    m.cube(B["leftArm"], [6, 7, -0.5], [1, 5, 1], Mat("#444444", "chain"))
    return m


def skeleton_swordsman():
    m = Model("skeleton_swordsman")
    bone = Mat(BONE, "bone")
    B = humanoid(m, bone.with_deco(front=d_skull_face(glow="#7fd4ff")), Mat(BONE, "ribs", accent="#3a342b"),
                 bone, bone, arm_w=2, leg_w=2)
    # Kettle hat
    m.cube(B["head"], [-6, 30, -6], [12, 1, 12], Mat(STEEL, "metal"))
    m.cube(B["head"], [-4.5, 31, -4.5], [9, 3, 9], Mat(STEEL, "metal").with_deco(sides=d_hline(-1, DSTEEL)))
    # Blue gambeson with a white cross
    m.cube(B["body"], [-4.5, 11, -2.5], [9, 12, 5], Mat("#2b3f8c", "cloth", accent="#1a2757").with_deco(front=d_cross("#e8e8e8", 3), back=d_cross("#e8e8e8", 3)))
    m.cube(B["body"], [-4.5, 11, -2.5], [9, 2, 5], Mat("#4a2c16", "leather"), inflate=0.1)
    # Round-top heater shield on the left forearm
    m.cube(B["leftArm"], [6, 10, -4], [1, 10, 8], Mat("#6e4a2a", "wood").with_deco(
        lat=[d_border(DSTEEL), d_rect(3, 3, 2, 3, "#2b3f8c"), d_px([(3, 4), (4, 4)], "#e8e8e8")]))
    # Chainmail sleeves
    m.cube(B["rightArm"], [-6.5, 17, -1.5], [3, 5, 3], Mat(STEEL, "chain"))
    m.cube(B["leftArm"], [3.5, 17, -1.5], [3, 5, 3], Mat(STEEL, "chain"))
    return m


def skeleton_longbowman():
    m = Model("skeleton_longbowman")
    bone = Mat("#cfc6a8", "bone")
    green = Mat("#2f5a26", "cloth", accent="#1d3a18", noise=0.1)
    B = humanoid(m, bone.with_deco(front=d_skull_face(glow="#b6ff7a")), Mat("#cfc6a8", "ribs", accent="#3a342b"),
                 bone, bone, arm_w=2, leg_w=2)
    # Green hood + capelet, Robin-Hood style
    m.cube(B["head"], [-4.5, 23.5, -4.5], [9, 9, 9], green.with_deco(front=d_clear(1, 2, -1, -1)))
    m.cube(B["head"], [-1, 27, 4.5], [2, 3, 3], green, pivot=[0, 28, 4.5], rotation=[-30, 0, 0])
    m.cube(B["body"], [-5, 19, -3], [10, 5, 6], green.with_deco(sides=d_tattered(1, 0.4)))
    # Leather jerkin
    m.cube(B["body"], [-4.25, 12, -2.25], [8, 7, 4], Mat("#6b4423", "leather", accent="#3e2a17").with_deco(sides=d_belt(0, "#2e1f12", GOLD)), inflate=0.25)
    # Quiver on the back
    m.cube(B["body"], [-2, 13, 2.5], [4, 11, 3], Mat("#7a4e2a", "leather", accent="#3e2a17"),
           pivot=[0, 18, 4], rotation=[0, 0, -20])
    m.cube(B["body"], [-1.5, 24, 3], [3, 4, 2], Mat("#efefef", "feather", accent="#2f5a26"),
           pivot=[0, 18, 4], rotation=[0, 0, -20])
    # Bracer on the bow arm
    m.cube(B["leftArm"], [3.5, 12.5, -1.5], [3, 5, 3], Mat("#4a2c16", "leather"))
    return m


def skeleton_warlord():
    m = Model("skeleton_warlord")
    bone = Mat("#c8c0a8", "bone", accent="#2b2b2b")
    dark = Mat("#3a3d44", "plate", accent="#9aa0aa")
    B = humanoid(m, bone.with_deco(front=d_skull_face(glow="#ff4a2a")), Mat("#c8c0a8", "ribs", accent="#2a251f"),
                 bone, bone, arm_w=2, leg_w=2)
    # Iron crown with spikes
    m.cube(B["head"], [-4.5, 31, -4.5], [9, 2, 9], Mat(GOLD, "gold").with_deco(front=d_px([(4, 1)], "#c0213a")))
    for x, z in ((-4.5, -4.5), (3.5, -4.5), (-4.5, 3.5), (3.5, 3.5), (-0.5, -4.5)):
        m.cube(B["head"], [x, 33, z], [1, 2, 1], Mat(GOLD, "gold"))
    # Black plate cuirass
    m.cube(B["body"], [-4.5, 13, -2.5], [9, 11, 5], dark.with_deco(front=d_px([(4, 3), (4, 4), (3, 4), (5, 4)], "#9b1c1c")))
    # Spiked pauldrons
    m.cube(B["rightArm"], [-8, 19, -3], [5, 4, 6], dark)
    m.cube(B["leftArm"], [3, 19, -3], [5, 4, 6], dark)
    m.cube(B["rightArm"], [-6, 23, -0.5], [1, 3, 1], Mat("#bfc4cc", "metal"))
    m.cube(B["leftArm"], [5, 23, -0.5], [1, 3, 1], Mat("#bfc4cc", "metal"))
    # Royal cape (animated)
    cape = m.bone("cape", [0, 24, 2.5], "body")
    m.cube(cape, [-5, 3, 2.5], [10, 21, 1], Mat("#5b1a6e", "cloth", accent=GOLD, noise=0.06).with_deco(
        back=[d_vline(0, GOLD), d_vline(-1, GOLD), d_cross("#d6a92e", 5)]))
    # Longbow strapped on the back (over the cape)
    m.cube(B["body"], [-0.5, 6, 3.5], [1, 18, 1], Mat("#5a3a1e", "wood"), pivot=[0, 15, 4], rotation=[0, 0, 30])
    m.cube(B["body"], [1.5, 6, 3.6], [1, 18, 1], Mat("#dddddd", "noise"), inflate=-0.4, pivot=[0, 15, 4], rotation=[0, 0, 30])
    # Greaves
    m.cube(B["rightLeg"], [-3.5, 0, -1.5], [3, 6, 3], dark)
    m.cube(B["leftLeg"], [0.5, 0, -1.5], [3, 6, 3], dark)
    return m


def ender_wraith():
    m = Model("ender_wraith", bounds=(3.0, 3.5))
    shroud = Mat("#2a1838", "cloth", accent="#4b2766", noise=0.12)
    B = enderman(m, Mat("#0c0a10", "speckle", accent="#2a1a3a", prob=0.1).with_deco(front=d_ender_eyes("#7cf6ff", "#ffffff")),
                 Mat("#141018", "speckle", accent="#2a1a3a"), Mat("#141018", "speckle", accent="#2a1a3a"))
    # Deep hood
    m.cube(B["head"], [-4.5, 39.5, -4.5], [9, 9, 9], shroud.with_deco(front=d_clear(1, 2, -1, -1)))
    m.cube(B["head"], [-2, 46, 3.5], [4, 3, 3], shroud, pivot=[0, 47, 4], rotation=[-25, 0, 0])
    # Tattered robe down to the knees
    m.cube(B["body"], [-4.5, 27.5, -2.5], [9, 13, 5], shroud.with_deco(front=d_vline(4, "#7cf6ff", 1, 9)))
    m.cube(B["body"], [-5, 10, -3], [10, 18, 6], shroud.with_deco(sides=d_tattered(4, 0.6)))
    # Ragged sleeves
    m.cube(B["rightArm"], [-6.5, 24, -1.5], [3, 15, 3], shroud.with_deco(sides=d_tattered(3, 0.5)))
    m.cube(B["leftArm"], [3.5, 24, -1.5], [3, 15, 3], shroud.with_deco(sides=d_tattered(3, 0.5)))
    # Soul lantern chain belt
    m.cube(B["body"], [-4.75, 26.5, -2.75], [9, 1, 5], Mat("#5b6169", "chain"), inflate=0.25)
    return m


def ender_knight():
    m = Model("ender_knight", bounds=(3.0, 3.5))
    obsid = Mat("#1e1530", "plate", accent="#b06cff")
    B = enderman(m, Mat("#100c14", "speckle", accent="#2c1d3b").with_deco(front=d_ender_eyes()),
                 Mat("#100c14", "speckle", accent="#2c1d3b"), Mat("#100c14", "speckle", accent="#2c1d3b"))
    # Horned obsidian helm with purple visor
    m.cube(B["head"], [-4.5, 39.5, -4.5], [9, 9, 9], Mat("#241a35", "metal", accent="#3d2b57").with_deco(front=d_visor("#05030a", "#e070ff")))
    for s in (-1, 1):
        x = -7.5 if s < 0 else 4.5
        m.cube(B["head"], [x, 45, -1], [3, 2, 2], Mat("#d9cfb5", "bone"))
        m.cube(B["head"], [x + (-1 if s < 0 else 2), 47, -0.5], [2, 3, 1], Mat("#e8e0c8", "bone"))
    # Cuirass, faulds, pauldrons, greaves
    m.cube(B["body"], [-4.5, 32, -2.5], [9, 8, 5], obsid.with_deco(front=d_px([(4, 2), (4, 3), (4, 4), (3, 3), (5, 3)], "#e070ff")))
    m.cube(B["body"], [-4.5, 26, -2.5], [9, 6, 5], Mat("#2d2240", "chain"))
    m.cube(B["rightArm"], [-7.5, 35, -2], [4, 4, 4], obsid)
    m.cube(B["leftArm"], [3.5, 35, -2], [4, 4, 4], obsid)
    m.cube(B["rightArm"], [-6.5, 11, -1.5], [3, 7, 3], obsid)
    m.cube(B["leftArm"], [3.5, 11, -1.5], [3, 7, 3], obsid)
    m.cube(B["rightLeg"], [-3.5, 0, -1.5], [3, 9, 3], obsid)
    m.cube(B["leftLeg"], [0.5, 0, -1.5], [3, 9, 3], obsid)
    # Purple banner-cape
    cape = m.bone("cape", [0, 40, 2.5], "body")
    m.cube(cape, [-4, 18, 2.5], [8, 22, 1], Mat("#4a1d6e", "cloth", accent="#e070ff").with_deco(back=d_cross("#e070ff", 6), sides=d_tattered(2, 0.4)))
    return m


def bog_slime():
    m = Model("bog_slime", tex_w=64, bounds=(2.5, 2.5))
    B = slime(m, Mat("#3f6b2a", "speckle", accent="#5a3d1f", prob=0.15),
              Mat("#5f8f3a", "slime", alpha=150, accent="#3b5422", prob=0.1, noise=0.1),
              Mat("#1a2b10", "noise"))
    r = B["root"]
    # Moss cap on top and swamp mushrooms
    m.cube(r, [-4, 8, -4], [8, 1, 8], Mat("#3d6b22", "speckle", accent="#6b8f2a", accent2="#2a4a16", prob=0.3).with_deco(sides=d_tattered(1, 0.6)))
    m.cube(r, [1, 9, -1], [1, 2, 1], Mat("#e3d9c0", "noise"))
    m.cube(r, [0, 11, -2], [3, 1, 3], Mat("#b02a2a", "speckle", accent="#f2f2f2", prob=0.25))
    m.cube(r, [-3, 9, 1], [1, 1, 1], Mat("#e3d9c0", "noise"))
    m.cube(r, [-4, 10, 0], [3, 1, 3], Mat("#8a5a2a", "speckle", accent="#c79a5a", prob=0.2))
    # Dripping vines
    for x, z in ((-4.2, -2), (3.2, 1), (-1, 3.2)):
        m.cube(r, [x, 4, z], [1, 4, 1], Mat("#2f5a1a", "noise", noise=0.15))
    return m


def royal_slime():
    m = Model("royal_slime", tex_w=64, bounds=(2.5, 2.5))
    B = slime(m, Mat("#c98a1a", "speckle", accent="#f2c14a", prob=0.12),
              Mat("#e8b23a", "slime", alpha=150, accent="#fff0a0", prob=0.08, noise=0.08),
              Mat("#5a2a0a", "noise"))
    r = B["root"]
    # Golden crown with gems
    m.cube(r, [-3, 8, -3], [6, 1, 6], Mat(GOLD, "gold").with_deco(front=d_px([(2, 0), (3, 0)], "#c0213a"), back=d_px([(2, 0)], "#2a7ad6")))
    for x, z in ((-3, -3), (2, -3), (-3, 2), (2, 2), (-0.5, -3), (-0.5, 2)):
        m.cube(r, [x, 9, z], [1, 2 if x != -0.5 else 1, 1], Mat(GOLD, "gold"))
    m.cube(r, [-0.5, 10, -3.25], [1, 1, 1], Mat("#c0213a", "noise"))
    # Ermine cape at the back
    m.cube(r, [-3.5, 0.5, 4], [7, 7, 1], Mat("#8e1b1b", "cloth", accent="#f2f2f2").with_deco(back=d_spots("#f2f2f2", 0.1)))
    return m


def siege_creeper():
    m = Model("siege_creeper", bounds=(2.0, 2.2))
    green = Mat("#4f9a3a", "speckle", accent="#2f6b22", accent2="#9ad06a", prob=0.25)
    B = creeper(m, green.with_deco(front=d_creeper_face()), green, green)
    # Spiked iron helmet with nose guard
    m.cube(B["head"], [-4.5, 22.5, -4.5], [9, 4, 9], Mat(STEEL, "metal").with_deco(sides=d_hline(-1, DSTEEL)))
    m.cube(B["head"], [-0.5, 26.5, -0.5], [1, 3, 1], Mat("#c8ced6", "metal"))
    m.cube(B["head"], [-0.5, 19.5, -5], [1, 4, 1], Mat(STEEL, "metal"))
    # Riveted chest plate and a TNT barrel strapped to the back
    m.cube(B["body"], [-4.5, 10, -2.5], [9, 7, 1], Mat(STEEL, "plate", accent="#e8edf2"))
    m.cube(B["body"], [-3, 8, 2], [6, 8, 4], Mat("#b4241a", "noise", noise=0.06).with_deco(sides=d_tnt(), top=d_rect(2, 1, 2, 2, "#3a3a3a")))
    m.cube(B["body"], [-4.5, 11, -2.5], [9, 1, 5], Mat("#4a2c16", "leather"), inflate=0.3)
    # Iron leg guards on the front legs
    m.cube(B["leg2"], [-4.5, 0, -6.5], [5, 3, 5], Mat(DSTEEL, "metal"))
    m.cube(B["leg3"], [-0.5, 0, -6.5], [5, 3, 5], Mat(DSTEEL, "metal"))
    return m


def plague_creeper():
    m = Model("plague_creeper", bounds=(2.0, 2.2))
    sick = Mat("#6a7a3a", "speckle", accent="#4b3a5a", accent2="#a6b84a", prob=0.3)
    B = creeper(m, sick.with_deco(front=d_creeper_face("#2a0f2a")), sick, sick)
    # Torn hood
    m.cube(B["head"], [-4.5, 21, -4.5], [9, 6, 9], Mat("#3b2c3f", "cloth").with_deco(front=d_clear(1, 0, -1, -1), sides=d_tattered(1, 0.5)))
    # Fungal growths and pustules
    m.cube(B["head"], [1.5, 27, -2], [1, 2, 1], Mat("#e3d9c0", "noise"))
    m.cube(B["head"], [0.5, 29, -3], [3, 1, 3], Mat("#7b2f8a", "speckle", accent="#c06ad0", prob=0.3))
    m.cube(B["head"], [-3, 27, 1], [2, 1, 2], Mat("#9cbf3a", "speckle", accent="#d0f070", prob=0.3))
    for o in ([-4.6, 13, -1], [3.6, 9, 0], [-1, 15, -2.6], [1, 8, 1.6]):
        m.cube(B["body"], o, [1, 2, 1], Mat("#9b4ab0", "speckle", accent="#e0a0f0", prob=0.3))
    # Bandages
    m.cube(B["body"], [-4.25, 12, -2.25], [8, 2, 4], Mat("#d8cfb0", "cloth", accent="#8a3a2a"), inflate=0.25)
    # Hanging gas sack
    m.cube(B["body"], [-2, 8, 2], [4, 5, 3], Mat("#5a8a2a", "slime", alpha=230, accent="#b0f060", prob=0.2))
    return m


MODELS = [zombie_knight, zombie_archer, zombie_plague, skeleton_swordsman, skeleton_longbowman,
          skeleton_warlord, ender_wraith, ender_knight, bog_slime, royal_slime, siege_creeper, plague_creeper]
