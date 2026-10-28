"""The "mutant" texture style (learned from the user's mutant skeleton,
stray, bogged and wither skeleton textures) + a geometry builder and a small
renderer to check the models. See docs/estilo_texturas.md.

Style rules:
- 128x128 sheet, 1 texel per model pixel, box UV; most of the sheet stays empty.
- No outlines. Every material is a ramp of 6-8 tones of one hue.
- Soft "cloudy" shading: blotches of 2-4 texels, low contrast, a little grain.
- Light from above: tops lighter, bottoms darker; long faces get darker
  towards the bottom with vertical streaks.
- Eyes are 2x1 slots (dark, or glowing for magic mobs); mouths are dark rows with teeth.
- Overlays (cloth, moss, sculk) are inflated cubes with ragged fringes that
  hang with transparent gaps; small flat cross-planes carry decorations.

Coordinates are Bedrock's: pixels, Y up, the mob faces -Z, its right side is -X.
"""
import math
import random

from PIL import Image, ImageDraw


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) + (a[3] if len(a) > 3 else 255,)


# ---------------------------------------------------------------- ramps
RAMPS = {
    # from the training textures
    "bone": ["#5e5e5e", "#7b7b7b", "#949494", "#a9a9a9", "#bdbdbd", "#cfcfcf", "#dedede", "#ececec"],
    "wither": ["#151515", "#1d1f1f", "#262928", "#2f3433", "#3a4140", "#4a5352", "#5d6867"],
    "stray": ["#56615f", "#6d7a78", "#84918f", "#9aa6a4", "#b0bab8", "#c6cecc", "#dce2e0"],
    "bogged": ["#4d5a37", "#5f6c43", "#717f4f", "#86945d", "#9aa86c", "#b2bd80", "#c8d196"],
    "wood": ["#3a2414", "#4b2f1a", "#5c3a21", "#6e4628", "#7f5331"],
    # for the abyss mutants
    "deepslate": ["#141417", "#1c1c20", "#25252a", "#2f2f35", "#3a3a41", "#47474f", "#56565e"],
    "deep_bone": ["#3c4247", "#4f565c", "#636b71", "#788086", "#8d959b", "#a3aab0", "#b9bfc4"],
    "rot_skin": ["#26332e", "#33433b", "#40544a", "#4e6658", "#5d7867", "#6f8b78", "#83a08b"],
    "rag": ["#141a24", "#1b2330", "#232d3d", "#2b374a", "#344257", "#3e4e66"],
    "leather": ["#211913", "#2c211a", "#382b21", "#45352a", "#524033"],
    "carapace": ["#0f0f12", "#16161a", "#1e1e23", "#27272d", "#313138", "#3d3d45"],
    "spider_hair": ["#1d1714", "#29201b", "#352a23", "#42352c", "#504036"],
    "creeper": ["#1f3b2b", "#2a4d38", "#356044", "#417352", "#4f8760", "#5f9b6f", "#73b080"],
    "sculk": ["#020d10", "#04161b", "#062027", "#082b33", "#0b3841", "#0f4852", "#155b66"],
    "sculk_glow": ["#0f8f9a", "#1fb3bd", "#3fd3db", "#7aeef2", "#c2fbfc"],
    "ember": ["#4a0c0c", "#6b1414", "#8f1f1a", "#b52e22", "#d9472c", "#f06a3a"],
    "iron": ["#3d3d40", "#55555a", "#6e6e74", "#88888e", "#a3a3a8", "#bfbfc3"],
}


def ramp(name):
    return [hx(c) for c in RAMPS[name]]


# ---------------------------------------------------------------- noise
class Cloud:
    """Value noise on a coarse lattice: blotches of 2-4 texels."""

    def __init__(self, rng, scale):
        self.rng, self.scale, self.cache = rng, scale, {}

    def at(self, gx, gy):
        if (gx, gy) not in self.cache:
            self.cache[(gx, gy)] = self.rng.random()
        return self.cache[(gx, gy)]

    def __call__(self, x, y):
        fx, fy = x / self.scale, y / self.scale
        x0, y0 = math.floor(fx), math.floor(fy)
        tx, ty = fx - x0, fy - y0
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a, b = self.at(x0, y0), self.at(x0 + 1, y0)
        c, d = self.at(x0, y0 + 1), self.at(x0 + 1, y0 + 1)
        return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


FACE_BIAS = {"top": 0.16, "front": 0.0, "right": -0.05, "left": -0.05, "back": -0.08, "bottom": -0.22}


class Face:
    """One face of a cube on the texture, with its own pixel coordinates."""

    def __init__(self, img, x0, y0, w, h, name, rng, mat):
        self.img, self.x0, self.y0, self.w, self.h = img, x0, y0, w, h
        self.name, self.rng, self.mat = name, rng, mat

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((self.x0 + x, self.y0 + y), c)

    def get(self, x, y):
        return self.img.getpixel((self.x0 + x, self.y0 + y))

    def clear(self, x, y):
        self.put(x, y, (0, 0, 0, 0))

    def tone(self, i):
        r = self.mat.ramp
        return r[max(0, min(len(r) - 1, i))]

    def darken(self, x, y, steps=1):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        c = self.get(x, y)
        if c[3] == 0:
            return
        r = self.mat.ramp
        best = min(range(len(r)), key=lambda i: sum((r[i][k] - c[k]) ** 2 for k in range(3)))
        self.put(x, y, r[max(0, best - steps)][:3] + (c[3],))


class Mat:
    """A material: a ramp, the cloudy shading and optional decorations.

    fringe: ragged bottom rows on the side faces (cloth, moss), with drips.
    streaks: darker vertical streaks towards the bottom of the side faces.
    deco: {face name or "sides"/"all": [fn(face)]} painted on top.
    """

    def __init__(self, ramp_name, contrast=1.0, light=0.0, scale=2.6, grain=0.12, streaks=0.0,
                 fringe=0, fringe_top=False, deco=None, alpha=255, hollow=False):
        self.ramp = [c[:3] + (alpha,) for c in ramp(ramp_name)]
        self.contrast, self.light, self.scale, self.grain = contrast, light, scale, grain
        self.streaks, self.fringe, self.fringe_top = streaks, fringe, fringe_top
        self.deco, self.hollow = deco or {}, hollow

    def with_deco(self, **deco):
        m = Mat.__new__(Mat)
        m.__dict__.update(self.__dict__)
        merged = {k: list(v) for k, v in self.deco.items()}
        for k, v in deco.items():
            merged.setdefault(k, []).extend(v if isinstance(v, list) else [v])
        m.deco = merged
        return m

    def paint(self, img, u, v, w, h, d, rng):
        regions = {
            "top": (u + d, v, w, d), "bottom": (u + d + w, v, w, d),
            "right": (u, v + d, d, h), "front": (u + d, v + d, w, h),
            "left": (u + d + w, v + d, d, h), "back": (u + 2 * d + w, v + d, w, h),
        }
        n = len(self.ramp)
        for name, (x0, y0, fw, fh) in regions.items():
            if fw <= 0 or fh <= 0:
                continue
            face = Face(img, x0, y0, fw, fh, name, rng, self)
            big, small = Cloud(rng, self.scale), Cloud(rng, self.scale / 2)
            side = name in ("front", "back", "left", "right")
            streak = [rng.random() for _ in range(fw)]
            for y in range(fh):
                for x in range(fw):
                    val = 0.62 * big(x, y) + 0.24 * small(x, y) + self.grain * (rng.random() - 0.5)
                    val = 0.5 + (val - 0.5) * 1.5 * self.contrast + FACE_BIAS[name] + self.light
                    if side and fh > 3:
                        t = y / (fh - 1)
                        val -= 0.22 * max(0.0, t - 0.35)
                        if self.streaks and t > 1 - self.streaks * (0.4 + 0.6 * streak[x]):
                            val -= 0.18
                    i = max(0, min(n - 1, round(val * (n - 1))))
                    face.put(x, y, self.ramp[i])
            if self.fringe and side:
                rows = min(self.fringe, fh - 1)
                for x in range(fw):
                    length = rng.randint(0, rows)
                    if rng.random() < 0.3:
                        length = rows  # long drip
                    cut = fh - rows + length
                    for y in range(cut, fh):
                        face.clear(x, y)
                    if 0 < cut <= fh:
                        face.darken(x, cut - 1, 1)
            if self.fringe_top and side:
                for x in range(fw):
                    for y in range(rng.randint(0, 1)):
                        face.clear(x, y)
            if self.hollow and name in ("top", "bottom"):
                for y in range(fh):
                    for x in range(fw):
                        face.clear(x, y)
            keys = [name, "all"] + (["sides"] if side else [])
            for k in keys:
                for fn in self.deco.get(k, []):
                    fn(face)


# ---------------------------------------------------------------- decorations
def eyes(y, xs, color, core=None, width=2):
    """2x1 eye slots at the given x positions (front face)."""
    def fn(f):
        for x in xs:
            for i in range(width):
                f.put(x + i, y, hx(color))
            if core:
                f.put(x + (width - 1 if x < f.w / 2 else 0), y, hx(core))
    return fn


def mouth(y, x0, x1, dark="#16110f", teeth="#c9c2b0", gap=2):
    def fn(f):
        for x in range(x0, x1):
            f.put(x, y, hx(dark))
            if (x - x0) % gap == 0:
                f.put(x, y - 1, hx(teeth))
                f.put(x, y + 1, hx(teeth))
    return fn


def cracks(count=2, steps=3):
    def fn(f):
        for _ in range(count):
            x, y = f.rng.randrange(max(1, f.w)), f.rng.randrange(max(1, f.h))
            for _ in range(steps + f.rng.randint(0, 2)):
                f.darken(x, y, 2)
                x += f.rng.choice((-1, 0, 1))
                y += 1
    return fn


def veins(ramp_name="sculk_glow", count=2, length=5):
    """Glowing sculk veins crawling over a face."""
    r = ramp(ramp_name)

    def fn(f):
        for _ in range(count):
            x, y = f.rng.randrange(max(1, f.w)), f.rng.randrange(max(1, f.h))
            for i in range(length):
                f.put(x, y, r[min(len(r) - 1, 1 + (i % 3))])
                if f.rng.random() < 0.5:
                    x += f.rng.choice((-1, 1))
                else:
                    y += f.rng.choice((-1, 1))
    return fn


def spots(ramp_name, chance=0.08, size=1):
    r = ramp(ramp_name)

    def fn(f):
        for y in range(f.h):
            for x in range(f.w):
                if f.rng.random() < chance:
                    c = r[f.rng.randrange(len(r))]
                    for dy in range(size):
                        for dx in range(size):
                            f.put(x + dx, y + dy, c)
    return fn


def ribs(color_ramp="bone", every=2):
    """Horizontal ribs on a dark chest."""
    r = ramp(color_ramp)

    def fn(f):
        for y in range(1, f.h - 1, every):
            for x in range(1, f.w - 1):
                if x != f.w // 2:
                    f.put(x, y, r[3 + (x + y) % 3])
    return fn


def glow_core(color_ramp="sculk_glow", r=2):
    rr = ramp(color_ramp)

    def fn(f):
        cx, cy = f.w // 2, f.h // 2
        for y in range(f.h):
            for x in range(f.w):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if d <= r:
                    f.put(x, y, rr[min(len(rr) - 1, int((1 - d / (r + 0.01)) * len(rr)))])
    return fn


def creeper_face(eye="#0b0b0b", glow=None):
    """The creeper face scaled to the face size."""
    def fn(f):
        s = max(1, f.w // 8)
        ox, oy = (f.w - 8 * s) // 2, (f.h - 8 * s) // 2
        pix = [(1, 2), (2, 2), (1, 3), (2, 3), (5, 2), (6, 2), (5, 3), (6, 3),
               (3, 4), (4, 4), (2, 5), (3, 5), (4, 5), (5, 5), (2, 6), (5, 6)]
        for px, py in pix:
            c = hx(glow) if glow and py in (2, 3) and px in (2, 5) else hx(eye)
            for dy in range(s):
                for dx in range(s):
                    f.put(ox + px * s + dx, oy + py * s + dy, c)
    return fn


# ---------------------------------------------------------------- model
class Cube:
    def __init__(self, origin, size, mat, inflate=0.0, pivot=None, rotation=None, mirror=False):
        self.origin, self.size, self.mat = list(origin), [int(s) for s in size], mat
        self.inflate, self.pivot, self.rotation, self.mirror = inflate, pivot, rotation, mirror
        w, h, d = self.size
        self.rw, self.rh = 2 * (w + d), d + h
        self.uv = None
        self.share = None  # another cube whose texture this one reuses

    def to_json(self):
        c = {"origin": self.origin, "size": self.size, "uv": list(self.uv)}
        if self.inflate:
            c["inflate"] = self.inflate
        if self.rotation:
            c["pivot"], c["rotation"] = self.pivot, self.rotation
        if self.mirror:
            c["mirror"] = True
        return c


class Model:
    def __init__(self, ident, bounds=(3.0, 3.5), tex=128):
        self.ident, self.bounds, self.tex = ident, bounds, tex
        self.bones = []

    def bone(self, name, pivot, parent=None, rotation=None, locators=None):
        b = {"name": name, "pivot": list(pivot), "cubes": []}
        if parent:
            b["parent"] = parent
        if rotation:
            b["rotation"] = list(rotation)
        if locators:
            b["locators"] = locators
        self.bones.append(b)
        return b

    def cube(self, bone, origin, size, mat, share=None, **kw):
        c = Cube(origin, size, mat, **kw)
        c.share = share
        bone["cubes"].append(c)
        return c

    def build(self, seed):
        cubes = [c for b in self.bones for c in b["cubes"]]
        own = sorted([c for c in cubes if c.share is None], key=lambda c: (-c.rh, -c.rw))
        x = y = row_h = 0
        for c in own:
            if x + c.rw > self.tex:
                x, y, row_h = 0, y + row_h, 0
            c.uv = (x, y)
            x += c.rw
            row_h = max(row_h, c.rh)
        th = self.tex
        while th < y + row_h:
            th *= 2
        img = Image.new("RGBA", (self.tex, th), (0, 0, 0, 0))
        rng = random.Random(seed)
        for c in own:
            w, h, d = c.size
            c.mat.paint(img, c.uv[0], c.uv[1], w, h, d, rng)
        for c in cubes:
            if c.share is not None:
                c.uv = c.share.uv
        self.tex_h = th
        self.image = img
        return img

    def geometry(self):
        bones = []
        for b in self.bones:
            nb = {k: v for k, v in b.items() if k != "cubes"}
            if b["cubes"]:
                nb["cubes"] = [c.to_json() for c in b["cubes"]]
            bones.append(nb)
        return {"format_version": "1.12.0", "minecraft:geometry": [{
            "description": {
                "identifier": self.ident, "texture_width": self.tex, "texture_height": self.tex_h,
                "visible_bounds_width": self.bounds[0], "visible_bounds_height": self.bounds[1],
                "visible_bounds_offset": [0, self.bounds[1] / 2, 0]},
            "bones": bones}]}


# ---------------------------------------------------------------- renderer
def _rot(rx, ry, rz):
    """Blockbench's reading of a Bedrock rotation (x mirrored space)."""
    ax, ay, az = math.radians(-rx), math.radians(-ry), math.radians(rz)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

    def mm(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(Rz, Ry), Rx)


def _apply(m, p, pivot):
    v = [p[i] - pivot[i] for i in range(3)]
    return [sum(m[i][k] * v[k] for k in range(3)) + pivot[i] for i in range(3)]


def render(geo_json, tex, yaw=-35, pitch=18, scale=6, pose=None, bg=(0, 0, 0, 0)):
    """Renders a Bedrock geometry with its texture (painter's algorithm over
    texel quads). pose: {bone: [rx, ry, rz]} extra rotations."""
    g = geo_json["minecraft:geometry"][0]
    bones = {b["name"]: b for b in g["bones"]}
    pose = pose or {}
    px = tex.load()
    quads = []

    def mirror_pt(p):
        return [-p[0], p[1], p[2]]

    def chain(name):
        out = []
        while name:
            out.append(bones[name])
            name = bones[name].get("parent")
        return out

    for b in g["bones"]:
        for c in b.get("cubes", []):
            w, h, d = c["size"]
            inf = c.get("inflate", 0)
            ox, oy, oz = c["origin"]
            # Blockbench space: x mirrored
            x0, x1 = -(ox + w) - inf, -ox + inf
            y0, y1 = oy - inf, oy + h + inf
            z0, z1 = oz - inf, oz + d + inf
            u, v = c["uv"] if isinstance(c["uv"], list) else (None, None)
            if u is None:
                continue
            mir = c.get("mirror", False)

            def tf(p, c=c, b=b):
                if c.get("rotation"):
                    p = _apply(_rot(*c["rotation"]), p, mirror_pt(c["pivot"]))
                for bb in chain(b["name"]):
                    r = [a + e for a, e in zip(bb.get("rotation", [0, 0, 0]), pose.get(bb["name"], [0, 0, 0]))]
                    if any(r):
                        p = _apply(_rot(*r), p, mirror_pt(bb["pivot"]))
                return p
            faces = []
            # (texture rect), function texel (i, j) -> 4 corners
            fw = lambda i, n, a, b_: (a + (b_ - a) * i / n)  # noqa: E731
            faces.append(((u + d, v + d, w, h), lambda i, j, s: (fw(w - i - s[0], w, x0, x1), fw(h - j - s[1], h, y0, y1), z0), "z"))
            faces.append(((u + 2 * d + w, v + d, w, h), lambda i, j, s: (fw(i + s[0], w, x0, x1), fw(h - j - s[1], h, y0, y1), z1), "z"))
            faces.append(((u, v + d, d, h), lambda i, j, s: (x1, fw(h - j - s[1], h, y0, y1), fw(d - i - s[0], d, z0, z1)), "x"))
            faces.append(((u + d + w, v + d, d, h), lambda i, j, s: (x0, fw(h - j - s[1], h, y0, y1), fw(i + s[0], d, z0, z1)), "x"))
            faces.append(((u + d, v, w, d), lambda i, j, s: (fw(w - i - s[0], w, x0, x1), y1, fw(d - j - s[1], d, z0, z1)), "y"))
            faces.append(((u + d + w, v, w, d), lambda i, j, s: (fw(w - i - s[0], w, x0, x1), y0, fw(j + s[1], d, z0, z1)), "y"))
            for (tu, tv, tw, th), corner, axis in faces:
                if tw <= 0 or th <= 0:
                    continue
                for j in range(th):
                    for i in range(tw):
                        ii = tw - 1 - i if mir else i
                        sx, sy = tu + ii, tv + j
                        if not (0 <= sx < tex.width and 0 <= sy < tex.height):
                            continue
                        col = px[sx, sy]
                        if col[3] < 128:
                            continue
                        pts = [tf(list(corner(i, j, s))) for s in ((0, 0), (1, 0), (1, 1), (0, 1))]
                        quads.append((pts, col, axis))
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def cam(p):
        x, y, z = p
        x, z = x * cy - z * sy, x * sy + z * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        return x, y, z
    proj = []
    for pts, colr, axis in quads:
        cp_ = [cam(p) for p in pts]
        depth = sum(p[2] for p in cp_) / 4
        # face light: normal from the quad
        a, b_, c_ = pts[0], pts[1], pts[3]
        n = [(b_[1] - a[1]) * (c_[2] - a[2]) - (b_[2] - a[2]) * (c_[1] - a[1]),
             (b_[2] - a[2]) * (c_[0] - a[0]) - (b_[0] - a[0]) * (c_[2] - a[2]),
             (b_[0] - a[0]) * (c_[1] - a[1]) - (b_[1] - a[1]) * (c_[0] - a[0])]
        ln = math.sqrt(sum(k * k for k in n)) or 1
        light = 0.72 + 0.28 * abs(n[1] / ln) - 0.1 * abs(n[0] / ln)
        proj.append((depth, [(-p[0], p[1]) for p in cp_], tuple(int(min(255, k * light)) for k in colr[:3]) + (255,)))
    if not proj:
        return Image.new("RGBA", (16, 16), bg)
    proj.sort(key=lambda q: -q[0])
    xs = [p[0] for q in proj for p in q[1]]
    ys = [p[1] for q in proj for p in q[1]]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    W, H = int((maxx - minx) * scale) + 8, int((maxy - miny) * scale) + 8
    img = Image.new("RGBA", (W, H), bg)
    dr = ImageDraw.Draw(img)
    for _, pts, colr in proj:
        dr.polygon([((x - minx) * scale + 4, (maxy - y) * scale + 4) for x, y in pts], fill=colr)
    return img
