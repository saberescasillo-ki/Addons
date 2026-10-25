"""Pixel-art helpers: materials, patterns and face decorations.

Every cube of a model gets a Mat. The Mat paints the six faces of the cube
in its box-UV layout, so the texture always matches the geometry.
"""
import math

FACE_SHADE = {"top": 1.12, "bottom": 0.72, "right": 0.88, "front": 1.0, "left": 0.88, "back": 0.8}
SIDES = ("right", "front", "left", "back")


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def col(c, a=None):
    if isinstance(c, str):
        return hx(c, 255 if a is None else a)
    if a is not None:
        return c[:3] + (a,)
    return c


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (c[3],)


def jitter(c, rng, n):
    return shade(c, 1 + (rng.random() - 0.5) * 2 * n)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) + (a[3],)


# ---------------------------------------------------------------- patterns
def p_noise(x, y, w, h, r, m):
    return jitter(m.base, r, m.noise)


def p_skin(x, y, w, h, r, m):
    if m.accent and r.random() < m.prob:
        return jitter(m.accent, r, 0.08)
    return jitter(m.base, r, m.noise)


def p_metal(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.04)
    if y == 0:
        c = shade(c, 1.25)
    elif y == h - 1:
        c = shade(c, 0.72)
    if x == 0 and h > 2:
        c = shade(c, 1.12)
    elif x == w - 1:
        c = shade(c, 0.86)
    if m.accent and w > 3 and h > 3 and r.random() < 0.04:
        c = m.accent
    return c


def p_plate(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.05)
    if y == 0 or x == 0:
        c = shade(c, 1.3)
    elif y == h - 1 or x == w - 1:
        c = shade(c, 0.68)
    if w >= 4 and h >= 4 and x in (1, w - 2) and y in (1, h - 2):
        c = m.accent or shade(m.base, 1.6)
    return c


def p_chain(x, y, w, h, r, m):
    c = shade(m.base, 1.18 if (x + y) % 2 == 0 else 0.72)
    if y % 2 == 1:
        c = shade(c, 0.85)
    return jitter(c, r, 0.03)


def p_cloth(x, y, w, h, r, m):
    c = jitter(m.base, r, m.noise)
    if y % 3 == 2:
        c = shade(c, 0.88)
    if m.accent and y == h - 1 and h > 2:
        c = jitter(m.accent, r, 0.05)
    return c


def p_leather(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.1)
    if m.accent and w > 3 and h > 3 and x in (0, w - 1) and y % 2 == 0:
        c = m.accent
    return c


def p_wood(x, y, w, h, r, m):
    c = shade(m.base, 1 + 0.12 * math.sin(x * 1.9 + (x * x) % 3))
    c = jitter(c, r, 0.05)
    if r.random() < 0.06:
        c = shade(c, 0.75)
    return c


def p_bone(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.06)
    if r.random() < 0.06:
        c = shade(c, 0.74)
    return c


def p_ribs(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.05)
    if y % 3 == 2 and 0 < x < w - 1:
        c = jitter(m.accent, r, 0.05)
    return c


def p_gold(x, y, w, h, r, m):
    c = jitter(m.base, r, 0.06)
    if y == 0:
        c = shade(c, 1.3)
    elif y == h - 1:
        c = shade(c, 0.7)
    if r.random() < 0.08:
        c = shade(m.base, 1.45)
    return c


def p_speckle(x, y, w, h, r, m):
    c = jitter(m.base, r, m.noise)
    if m.accent and r.random() < m.prob:
        c = jitter(m.accent, r, 0.1)
    if m.accent2 and r.random() < m.prob * 0.4:
        c = jitter(m.accent2, r, 0.1)
    return c


def p_slime(x, y, w, h, r, m):
    c = jitter(m.base, r, m.noise)
    edge = x in (0, w - 1) or y in (0, h - 1)
    if edge:
        c = shade(c, 0.85)[:3] + (min(255, m.base[3] + 50),)
    if m.accent and r.random() < m.prob:
        c = m.accent
    return c


def p_feather(x, y, w, h, r, m):
    c = m.base if (y // 2) % 2 == 0 else (m.accent or shade(m.base, 0.8))
    return jitter(c, r, 0.05)


def p_stripes(x, y, w, h, r, m):
    c = m.base if (x // 2) % 2 == 0 else m.accent
    return jitter(c, r, 0.05)


PATTERNS = {
    "noise": p_noise, "skin": p_skin, "metal": p_metal, "plate": p_plate,
    "chain": p_chain, "cloth": p_cloth, "leather": p_leather, "wood": p_wood,
    "bone": p_bone, "ribs": p_ribs, "gold": p_gold, "speckle": p_speckle,
    "slime": p_slime, "feather": p_feather, "stripes": p_stripes,
}


class FaceCtx:
    def __init__(self, img, x0, y0, w, h, rng, mat, name):
        self.img, self.x0, self.y0, self.w, self.h = img, x0, y0, w, h
        self.rng, self.mat, self.name = rng, mat, name

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((self.x0 + x, self.y0 + y), col(c))

    def get(self, x, y):
        return self.img.getpixel((self.x0 + x, self.y0 + y))

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c)


class Mat:
    def __init__(self, base, pattern="noise", accent=None, accent2=None, noise=0.08,
                 alpha=255, prob=0.1, deco=None, shade=True):
        self.base = col(base, alpha)
        self.accent = col(accent, alpha) if accent else None
        self.accent2 = col(accent2, alpha) if accent2 else None
        self.pattern, self.noise, self.prob, self.shade = pattern, noise, prob, shade
        self.deco = deco or {}

    def with_deco(self, **deco):
        m = Mat.__new__(Mat)
        m.__dict__.update(self.__dict__)
        merged = {k: list(v) for k, v in self.deco.items()}
        for k, v in deco.items():
            merged.setdefault(k, []).extend(v if isinstance(v, list) else [v])
        m.deco = merged
        return m

    def paint(self, img, u, v, w, h, d, rng, res=1):
        assert res == 1, "Mat paints 1:1 textures only"
        regions = {
            "top": (u + d, v, w, d),
            "bottom": (u + d + w, v, w, d),
            "right": (u, v + d, d, h),
            "front": (u + d, v + d, w, h),
            "left": (u + d + w, v + d, d, h),
            "back": (u + 2 * d + w, v + d, w, h),
        }
        pat = PATTERNS[self.pattern]
        for name, (x0, y0, rw, rh) in regions.items():
            if rw <= 0 or rh <= 0:
                continue
            f = FACE_SHADE[name] if self.shade else 1.0
            ctx = FaceCtx(img, x0, y0, rw, rh, rng, self, name)
            for y in range(rh):
                for x in range(rw):
                    ctx.put(x, y, shade(pat(x, y, rw, rh, rng, self), f))
            keys = [name, "all"]
            if name in SIDES:
                keys.append("sides")
            if name in ("left", "right"):
                keys.append("lat")
            for k in keys:
                for fn in self.deco.get(k, []):
                    fn(ctx)


# ------------------------------------------------------------- decorations
def d_rect(x, y, w, h, c):
    return lambda f: f.rect(x, y, w, h, c)


def d_px(points, c):
    def fn(f):
        for x, y in points:
            f.put(x, y, c)
    return fn


def d_clear(x, y, w, h):
    """Cut a hole (fully transparent) - used for hood openings."""
    return lambda f: f.rect(x, y, w if w > 0 else f.w + w - x, h if h > 0 else f.h + h - y, (0, 0, 0, 0))


def d_hline(y, c, x0=0, x1=None):
    def fn(f):
        yy = y if y >= 0 else f.h + y
        for x in range(x0, f.w if x1 is None else x1):
            f.put(x, yy, c)
    return fn


def d_vline(x, c, y0=0, y1=None):
    def fn(f):
        xx = x if x >= 0 else f.w + x
        for y in range(y0, f.h if y1 is None else y1):
            f.put(xx, y, c)
    return fn


def d_border(c):
    def fn(f):
        for x in range(f.w):
            f.put(x, 0, c)
            f.put(x, f.h - 1, c)
        for y in range(f.h):
            f.put(0, y, c)
            f.put(f.w - 1, y, c)
    return fn


def d_cross(c, arm_y=None):
    """Heraldic cross centred on the face."""
    def fn(f):
        cx = f.w // 2
        cy = arm_y if arm_y is not None else max(1, f.h // 3)
        for y in range(1, f.h - 1):
            f.put(cx, y, c)
            if f.w % 2 == 0:
                f.put(cx - 1, y, c)
        for x in range(1, f.w - 1):
            f.put(x, cy, c)
    return fn


def d_belt(y, c, buckle=None):
    def fn(f):
        yy = y if y >= 0 else f.h + y
        for x in range(f.w):
            f.put(x, yy, c)
        if buckle and f.name == "front":
            f.put(f.w // 2, yy, buckle)
            f.put(f.w // 2 - 1, yy, buckle)
    return fn


def d_tattered(rows=2, chance=0.5):
    def fn(f):
        for y in range(f.h - rows, f.h):
            for x in range(f.w):
                if f.rng.random() < chance * (1 + (y - (f.h - rows)) / rows) / 2 + 0.15:
                    f.put(x, y, (0, 0, 0, 0))
    return fn


def d_zombie_face(eye="#141a10", pupil=None, mouth="#2c3b22"):
    def fn(f):
        f.rect(1, 3, 2, 1, eye)
        f.rect(5, 3, 2, 1, eye)
        if pupil:
            f.put(2, 3, pupil)
            f.put(5, 3, pupil)
        f.rect(3, 4, 2, 2, shade(f.get(3, 4), 0.75))
        f.rect(2, 6, 4, 1, mouth)
        f.put(1, 5, shade(f.get(1, 5), 0.8))
    return fn


def d_skull_face(socket="#26211b", glow=None):
    def fn(f):
        f.rect(1, 3, 2, 2, socket)
        f.rect(5, 3, 2, 2, socket)
        if glow:
            f.put(2, 4, glow)
            f.put(5, 4, glow)
        f.rect(3, 5, 2, 1, socket)
        for x in range(1, 7):
            f.put(x, 6, socket if x % 2 else "#cfc8b0")
        f.rect(2, 7, 4, 1, shade(col("#d8d2bd"), 0.8))
    return fn


def d_ender_eyes(c="#e070ff", core="#ffd9ff", y=4):
    def fn(f):
        for x0 in (0, 5):
            f.rect(x0, y, 3, 1, c)
        f.put(1, y, core)
        f.put(6, y, core)
    return fn


def d_creeper_face(c="#1a1a1a"):
    def fn(f):
        f.rect(1, 2, 2, 2, c)
        f.rect(5, 2, 2, 2, c)
        f.rect(3, 4, 2, 2, c)
        f.rect(2, 5, 1, 3, c)
        f.rect(5, 5, 1, 3, c)
        f.rect(3, 6, 2, 1, c)
    return fn


def d_visor(slit="#0d0d0d", eye="#ff3b1f"):
    """Great-helm visor: eye slit, glowing eyes, breathing holes, centre ridge."""
    def fn(f):
        f.rect(1, 3, f.w - 2, 1, slit)
        f.put(2, 3, eye)
        f.put(f.w - 3, 3, eye)
        cx = f.w // 2
        for y in range(f.h):
            if y != 3:
                f.put(cx, y, shade(f.get(cx, y), 1.25))
        for y in (5, 7):
            for x in range(cx + 2, f.w - 1, 2):
                f.put(x, y, slit)
    return fn


def d_goggles(glass="#c9b458", rim="#2a2a2a"):
    def fn(f):
        for x0 in (1, 5):
            f.rect(x0, 2, 2, 2, glass)
            f.put(x0, 2, shade(col(glass), 1.3))
        f.rect(0, 1, 8, 1, rim)
    return fn


def d_slime_face(c="#1d3b14"):
    def fn(f):
        f.rect(1, 2, 2, 2, c)
        f.rect(5, 2, 2, 2, c)
        f.rect(3, 5, 2, 1, c)
    return fn


def d_spots(c, chance=0.15):
    def fn(f):
        for y in range(f.h):
            for x in range(f.w):
                if f.rng.random() < chance:
                    f.put(x, y, jitter(col(c), f.rng, 0.1))
    return fn


def d_tnt():
    def fn(f):
        f.rect(0, f.h // 2 - 1, f.w, 2, "#e8e2d0")
        for x in range(0, f.w, 2):
            f.put(x, f.h // 2 - 1, "#1a1a1a")
    return fn
