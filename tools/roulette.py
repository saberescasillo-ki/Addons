"""Builds the "Ruleta de Colores" add-on: admin commands and a control item
that show and spin a 6-colour wheel (wood, vines and leaves) in each player's
HUD.

How the HUD wheel works: the script sends titles that start with PREFIX,
"_roul:~<scale>~~p<position>~<texture>" ("_roul:~10~~photbar~f07", "_roul:hide").
ui/hud_screen.json hides those titles, remembers the last one and uses it to
pick where the wheel goes (POSITIONS), its size (1..MAX_SCALE, for the
grow/shrink/pop animations) and the texture to draw, so each title shows one
pre-rendered frame.

    python3 tools/roulette.py            # regenerate the packs and the .mcaddon
    python3 tools/roulette.py --preview  # also refresh docs/roulette_preview.png
"""
import json
import math
import os
import random
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_NAME = "Ruleta de Colores"
BP = os.path.join(ROOT, "Roulette_BP")
RP = os.path.join(ROOT, "Roulette_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 2, 1]
SCRIPT_API = "2.1.0"  # first stable version with custom commands (2.0.0 has none)
SCRIPT_UI_API = "2.0.0"
MIN_ENGINE = [1, 21, 100]
UUIDS = dict(bp="cebd64fa-ccb8-4f9f-a744-dc03c3d56ea8", bp_data="de1aa5e9-fa5f-47a0-8041-dcc2b0df6867",
             bp_script="ce237dc6-fa54-47fc-b7ae-907460106128", rp="3dcf6310-841c-4f10-9844-c8b91af2d428",
             rp_res="b1f1a7f5-211f-465e-a0b0-59f6244f9b99")
NS = "roulette"
ITEM = f"{NS}:controller"

# Segments clockwise from the pointer (top) when the wheel is at frame 0.
COLORS = [
    dict(id="rojo", es="Rojo", fmt="§c", hex="#d8342c", aliases=["red"]),
    dict(id="verde", es="Verde", fmt="§a", hex="#4c9a2a", aliases=["green"]),
    dict(id="azul", es="Azul", fmt="§9", hex="#2456c4", aliases=["blue"]),
    dict(id="blanco", es="Blanco", fmt="§f", hex="#f2efe4", aliases=["white"]),
    dict(id="celeste", es="Celeste", fmt="§b", hex="#5cc4ec", aliases=["light_blue", "cyan"]),
    dict(id="amarillo", es="Amarillo", fmt="§e", hex="#f4cf2c", aliases=["yellow"]),
]
BLANK = "#f2efe4"    # "ocultar resultado": every segment this colour
RANDOM = ["aleatorio", "random"]

PREFIX = "_roul:"
FRAMES = 72          # one frame every 5 degrees
SCALES = 10          # sizes of the grow/shrink animation (one per tick), 10 = normal size
MAX_SCALE = 15       # 1.5x for a second when it lands
TEX_SIZE = 128
SS = 4               # supersampling when drawing
UI_SIZE = 64         # normal wheel size on screen, in UI units
# Where the admin can put the wheel. grow_from: the point that stays still while it grows.
POSITIONS = {
    "hotbar": dict(es="Encima de la barra de objetos", anchor="bottom_middle", offset=[0, -28],
                   grow_from="bottom_middle"),
    "hambre": dict(es="Debajo de la barra de hambre", anchor="top_right", offset=[-4, 30], grow_from="top_right"),
    "centro": dict(es="En el centro", anchor="center", offset=[0, 0], grow_from="center"),
}
DEFAULT_POSITION = "hotbar"
SPIN_TICKS = 300     # 15 s
MIN_TURNS = 8        # full turns before it slows down on the colour
JITTER = 4           # frames (x5 degrees) the landing point moves inside the segment
WARN_TICKS = 20      # warning bells before it starts
POP_TICKS = 25       # 5 ticks growing to 1.5x + 1 s at that size
WILD_TICKS = 200     # "girar sin control": 10 s speeding up...
VANISH_TICKS = 10    # ...then gone for half a second, and back broken

BARK, BARK_DARK, BARK_LIGHT = (104, 70, 40, 255), (62, 40, 22, 255), (140, 98, 58, 255)
LEAF, LEAF_DARK, LEAF_LIGHT = (70, 140, 50, 255), (34, 84, 30, 255), (128, 186, 74, 255)


def hx(s, a=255):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def shade(c, f):
    return tuple(max(0, min(255, int(ch * f))) for ch in c[:3]) + (c[3],)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- drawing
def leaf(d, x, y, angle, length, width, fill, vein=True):
    """A leaf from its stem (x, y) pointing at `angle` (radians)."""
    ca, sa = math.cos(angle), math.sin(angle)
    left, right = [], []
    for k in range(13):
        t = k / 12
        w = width / 2 * math.sin(math.pi * t) ** 0.8
        px, py = t * length, w
        left.append((x + px * ca - py * sa, y + px * sa + py * ca))
        right.append((x + px * ca + py * sa, y + px * sa - py * ca))
    d.polygon(left + right[::-1], fill=fill, outline=shade(fill, 0.6))
    if vein:
        d.line([(x, y), (x + length * 0.85 * ca, y + length * 0.85 * sa)], fill=shade(fill, 0.7),
               width=max(1, int(width / 9)))


def flower(d, x, y, r, petal, centre=(250, 210, 70, 255)):
    for k in range(5):
        a = k * 2 * math.pi / 5
        px, py = x + r * 0.6 * math.cos(a), y + r * 0.6 * math.sin(a)
        d.ellipse([px - r * 0.5, py - r * 0.5, px + r * 0.5, py + r * 0.5], fill=petal, outline=shade(petal, 0.8))
    d.ellipse([x - r * 0.35, y - r * 0.35, x + r * 0.35, y + r * 0.35], fill=centre)


def disk(colors):
    """The rotating part, at SS x TEX_SIZE: segments, twig borders and a log hub."""
    n = TEX_SIZE * SS
    c = n / 2
    r = c * 0.82
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    seg = 360 / len(colors)
    box = [c - r, c - r, c + r, c + r]
    for i, col in enumerate(colors):
        # PIL angles: 0 = east, clockwise. Segment i is centred at i*seg from the top.
        start = -90 + i * seg - seg / 2
        d.pieslice(box, start, start + seg, fill=hx(col))
        # a faint leaf drawn in each segment, and darker toward the rim
        mid = math.radians(start + seg / 2)
        leaf(d, c + r * 0.3 * math.cos(mid), c + r * 0.3 * math.sin(mid), mid, r * 0.6, r * 0.32,
             shade(hx(col), 0.9), vein=True)
    rim_shade = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    sd = ImageDraw.Draw(rim_shade)
    for k in range(12):
        rr = r * (1 - k * 0.025)
        sd.ellipse([c - rr, c - rr, c + rr, c + rr], fill=(30, 20, 0, 10))
    sd.ellipse([c - r * 0.72, c - r * 0.72, c + r * 0.72, c + r * 0.72], fill=(0, 0, 0, 0))
    im.alpha_composite(rim_shade)
    rng = random.Random(7)
    for i in range(len(colors)):
        a = math.radians(-90 + i * seg - seg / 2)
        ca, sa = math.cos(a), math.sin(a)
        d.line([c, c, c + r * ca, c + r * sa], fill=BARK_DARK, width=SS * 4)
        d.line([c, c, c + r * ca, c + r * sa], fill=BARK, width=SS * 2)
        for t in (0.45, 0.72):  # buds along the twig
            side = 1 if rng.random() < 0.5 else -1
            leaf(d, c + r * t * ca, c + r * t * sa, a + side * 0.7, r * 0.12, r * 0.06, LEAF, vein=False)
    h = r * 0.22  # log cross-section
    d.ellipse([c - h, c - h, c + h, c + h], fill=BARK_DARK)
    d.ellipse([c - h * 0.86, c - h * 0.86, c + h * 0.86, c + h * 0.86], fill=(214, 172, 116, 255))
    for k in (0.68, 0.48, 0.28):
        d.ellipse([c - h * k, c - h * k, c + h * k, c + h * k], outline=(160, 116, 70, 255), width=SS)
    d.ellipse([c - h * 0.1, c - h * 0.1, c + h * 0.1, c + h * 0.1], fill=(150, 104, 60, 255))
    return im


def ring():
    """Static bark rim wrapped by a vine with leaves and flowers."""
    n = TEX_SIZE * SS
    c = n / 2
    ro, ri = c * 0.96, c * 0.81
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([c - ro, c - ro, c + ro, c + ro], fill=BARK_DARK)
    d.ellipse([c - ro + SS * 2, c - ro + SS * 2, c + ro - SS * 2, c + ro - SS * 2], fill=BARK)
    rng = random.Random(3)
    for _ in range(70):  # bark grain
        rr = rng.uniform(ri + SS * 3, ro - SS * 4)
        a0 = rng.uniform(0, 360)
        d.arc([c - rr, c - rr, c + rr, c + rr], a0, a0 + rng.uniform(8, 30),
              fill=rng.choice([BARK_DARK, BARK_LIGHT]), width=SS)
    d.ellipse([c - ri, c - ri, c + ri, c + ri], fill=(0, 0, 0, 0))
    d.ellipse([c - ri, c - ri, c + ri, c + ri], outline=BARK_DARK, width=SS * 2)
    # the vine winds in and out around the rim
    rm, amp = (ro + ri) / 2, (ro - ri) * 0.42
    pts = []
    for k in range(361):
        a = math.radians(k)
        rr = rm + amp * math.sin(a * 9)
        pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
    d.line(pts, fill=LEAF_DARK, width=SS * 3, joint="curve")
    d.line(pts, fill=(96, 150, 56, 255), width=SS, joint="curve")
    for k in range(0, 360, 17):
        a = math.radians(k + 6)
        rr = rm + amp * math.sin(a * 9)
        x, y = c + rr * math.cos(a), c + rr * math.sin(a)
        out = a + (0.9 if k % 34 else -0.9)
        leaf(d, x, y, out, c * 0.13, c * 0.07, LEAF if k % 3 else LEAF_LIGHT)
    for k in (40, 130, 215, 300):
        a = math.radians(k)
        flower(d, c + ro * 0.97 * math.cos(a), c + ro * 0.97 * math.sin(a), c * 0.055,
               (240, 150, 190, 255) if k % 2 else (250, 250, 245, 255))
    return im


def pointer():
    """A leaf hanging from a twig, tip down."""
    n = 32 * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(n * 0.15, n * 0.12), (n * 0.85, n * 0.12)], fill=BARK_DARK, width=SS * 4)
    d.line([(n * 0.15, n * 0.12), (n * 0.85, n * 0.12)], fill=BARK, width=SS * 2)
    leaf(d, n * 0.5, n * 0.1, math.pi / 2, n * 0.86, n * 0.52, LEAF)
    leaf(d, n * 0.3, n * 0.12, math.pi * 0.8, n * 0.22, n * 0.12, LEAF_LIGHT, vein=False)
    return im.resize((32, 32), Image.LANCZOS)


def smiley(im):
    """Black and white smiley in the middle of the blank wheel."""
    n = im.width
    c, r = n / 2, n * 0.2
    d = ImageDraw.Draw(im)
    d.ellipse([c - r, c - r, c + r, c + r], fill=(250, 250, 250, 255), outline=(20, 20, 20, 255), width=SS * 4)
    e = r * 0.14
    for side in (-1, 1):
        ex, ey = c + side * r * 0.38, c - r * 0.25
        d.ellipse([ex - e, ey - e * 1.4, ex + e, ey + e * 1.4], fill=(20, 20, 20, 255))
    d.arc([c - r * 0.6, c - r * 0.55, c + r * 0.6, c + r * 0.62], 20, 160, fill=(20, 20, 20, 255), width=SS * 4)
    return im


def broken(disk_img, ring_img):
    """The wheel (with its rim) split in two along a jagged crack."""
    n = TEX_SIZE * SS
    whole = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    whole.alpha_composite(disk_img)
    whole.alpha_composite(ring_img)
    whole = whole.resize((int(n * 0.8), int(n * 0.8)), Image.LANCZOS)
    m = whole.width
    rng = random.Random(11)
    crack = [(m / 2 + rng.uniform(-m * 0.06, m * 0.06), m * k / 10) for k in range(11)]
    crack[0], crack[-1] = (m / 2, -1), (m / 2, m + 1)
    out = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    # each half pivots on the bottom of the crack, so they open like a V
    for side, poly in ((-1, [(-1, -1)] + crack + [(-1, m + 1)]), (1, [(m + 1, -1)] + crack + [(m + 1, m + 1)])):
        mask = Image.new("L", (m, m), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        half = Image.new("RGBA", (m, m), (0, 0, 0, 0))
        half.paste(whole, (0, 0), mask)
        half = half.rotate(-side * 11, resample=Image.BICUBIC, center=(m / 2, m * 0.95))
        out.alpha_composite(half, (int((n - m) / 2 + side * n * 0.04), int((n - m) / 2 + n * 0.06)))
    d = ImageDraw.Draw(out)
    for _ in range(6):  # splinters falling from the crack
        x, y = n / 2 + rng.uniform(-n * 0.04, n * 0.04), n * rng.uniform(0.15, 0.6)
        sz = SS * rng.uniform(2, 3.5)
        d.polygon([(x, y - sz), (x + sz * 0.6, y + sz), (x - sz * 0.6, y + sz * 0.6)], fill=BARK_LIGHT,
                  outline=BARK_DARK)
    return out


def small(im):
    return im.resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)


def composite(disk_img, ring_img, pointer_img, size):
    """Wheel + rim + pointer as the HUD draws it (for icons and the preview)."""
    top = size // 8
    out = Image.new("RGBA", (size, size + top), (0, 0, 0, 0))
    out.alpha_composite(disk_img.resize((size, size), Image.LANCZOS), (0, top))
    if ring_img is not None:
        out.alpha_composite(ring_img.resize((size, size), Image.LANCZOS), (0, top))
        p = pointer_img.resize((size // 4, size // 4), Image.LANCZOS)
        out.alpha_composite(p, ((size - p.width) // 2, 0))
    return out


# ---------------------------------------------------------------- UI
def hud():
    tex = "textures/ui/roulette"
    src = "roul_data_control"
    p = "#preserved_text"
    has = lambda s: f"(not (({p} - '{s}') = {p}))"  # noqa: E731
    name = f"({p} - '{PREFIX}')"
    for tag in [f"~{k}~" for k in range(1, MAX_SCALE + 1)] + [f"~p{k}~" for k in POSITIONS]:
        name = f"({name} - '{tag}')"
    shown = f"({has(PREFIX)} and not ({p} = '{PREFIX}hide'))"
    tip = UI_SIZE // 4

    def view(prop, target):
        return {"binding_type": "view", "source_control_name": src, "source_property_name": prop,
                "target_property_name": target}

    def scales(anchor):
        out = []
        for k in range(1, MAX_SCALE + 1):
            s = max(2, round(UI_SIZE * k / SCALES))
            t = max(1, s // 4)
            out.append({f"scale_{k}": {
                "type": "panel", "size": [s, s + t // 2], "anchor_from": anchor, "anchor_to": anchor,
                "bindings": [view(has(f"~{k}~"), "#visible")],
                "controls": [
                    {"disk": {"type": "image", "texture": "#texture", "size": [s, s], "layer": 1,
                              "anchor_from": "bottom_middle", "anchor_to": "bottom_middle",
                              "bindings": [view(f"('{tex}/' + {name})", "#texture")]}},
                    {"rim_and_pointer": {
                        "type": "panel", "size": ["100%", "100%"],
                        # the broken wheel already has its own rim
                        "bindings": [view(f"(({p} - 'broken') = {p})", "#visible")],
                        "controls": [
                            {"rim": {"type": "image", "texture": f"{tex}/ring", "size": [s, s], "layer": 2,
                                     "anchor_from": "bottom_middle", "anchor_to": "bottom_middle"}},
                            {"pointer": {"type": "image", "texture": f"{tex}/pointer", "size": [t, t],
                                         "layer": 3, "anchor_from": "top_middle", "anchor_to": "top_middle"}}]}},
                ]}})
        return out

    # One box per position, as big as the 1.5x wheel. Only the box of the current
    # position is visible, and hidden controls don't update their bindings.
    boxes = []
    box = [round(UI_SIZE * MAX_SCALE / SCALES), round((UI_SIZE + tip // 2) * MAX_SCALE / SCALES)]
    for key, pos in POSITIONS.items():
        boxes.append({f"roulette_at_{key}": {
            "type": "panel", "size": box, "anchor_from": pos["anchor"], "anchor_to": pos["anchor"],
            "offset": pos["offset"],
            "bindings": [view(f"({shown} and {has(f'~p{key}~')})", "#visible")],
            "controls": scales(pos["grow_from"])}})
    preload = [f"f{k:02d}" for k in range(FRAMES)] + ["blank", "broken", "ring", "pointer"]
    return {
        "namespace": "hud",
        "root_panel": {"modifications": [{
            "array_name": "controls", "operation": "insert_back",
            "value": {"roulette_root@hud.roulette_root": {}}}]},
        # Titles sent by the add-on are data for the wheel, never shown as text.
        "hud_title_text": {"bindings": [
            {"binding_name": "#hud_title_text_string"},
            {"binding_type": "view",
             "source_property_name": f"((#hud_title_text_string - '{PREFIX}') = #hud_title_text_string)",
             "target_property_name": "#visible"}]},
        "roulette_root": {
            "type": "panel", "size": ["100%", "100%"], "layer": 30,
            "controls": [
                # Keeps the last add-on title in #preserved_text (visibility_changed trick).
                {src: {"type": "panel", "size": [0, 0], "bindings": [
                    {"binding_name": "#hud_title_text_string"},
                    {"binding_name": "#hud_title_text_string", "binding_name_override": p,
                     "binding_condition": "visibility_changed"},
                    {"binding_type": "view",
                     "source_property_name": f"(not (#hud_title_text_string = {p}) and "
                                             f"not ((#hud_title_text_string - '{PREFIX}') = #hud_title_text_string))",
                     "target_property_name": "#visible"}]}},
                # Every texture stays loaded, so the first spin doesn't flicker.
                {"roulette_preload": {"type": "panel", "size": [1, 1], "anchor_from": "top_left",
                                      "anchor_to": "top_left", "controls": [
                    {f"pre_{t}": {"type": "image", "texture": f"{tex}/{t}", "size": [1, 1], "alpha": 0.01}}
                    for t in preload]}},
            ] + boxes},
    }


# ---------------------------------------------------------------- script
SCRIPT = r"""// Ruleta de Colores: admin commands and a control item that show and spin a
// 6-colour wheel in the HUD. Generated by tools/roulette.py.
//
// The wheel is drawn by ui/hud_screen.json (resource pack): every title that
// starts with PREFIX is hidden and used as "~<size>~~p<position>~<texture>" to draw.
import { CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, ItemStack, system, world } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

const PREFIX = __PREFIX__;
const ITEM = __ITEM__;
const FRAMES = __FRAMES__;
const SCALES = __SCALES__;       // normal size
const MAX_SCALE = __MAX_SCALE__; // size of the 1.5x pop when it lands
const SPIN_TICKS = __SPIN_TICKS__;
const MIN_TURNS = __MIN_TURNS__;
const JITTER = __JITTER__;
const WARN_TICKS = __WARN_TICKS__; // warning bells before the wheel starts
const POP_TICKS = __POP_TICKS__;
const WILD_TICKS = __WILD_TICKS__; // the spin that ends up breaking the wheel
const VANISH_TICKS = __VANISH_TICKS__;
const POSITIONS = __POSITIONS__;
// Clockwise from the pointer at frame 0.
const COLORS = __COLORS__;
const RANDOM = __RANDOM__;
const SEG = FRAMES / COLORS.length;
const OBJECTIVE = "ruleta"; // score "resultado": 1..6, the colour it landed on
// The wild spin speeds up from slow to 10 times the average speed of a normal spin.
const WILD_MAX = (10 * (MIN_TURNS * FRAMES + FRAMES / 2)) / SPIN_TICKS;
const WILD_MIN = 0.2;

const mod = (a, n) => ((a % n) + n) % n;
const frameName = (frame) => "f" + String(mod(Math.floor(frame), FRAMES)).padStart(2, "0");
const segment = (pos) => Math.floor((pos + SEG / 2) / SEG);

// Read on first use: the world can't be read while the script loads (early execution).
let position;
const currentPosition = () =>
  (position ??= String(world.getDynamicProperty("roulette:position") ?? "") || __DEFAULT_POSITION__);

// ------------------------------------------------------------ per-player wheel
const views = new Map(); // player id -> what that player's wheel is doing

function view(player) {
  let v = views.get(player.id);
  if (!v) {
    let st = {};
    try {
      st = JSON.parse(String(player.getDynamicProperty("roulette:state") ?? "{}"));
    } catch {}
    v = {
      visible: !!st.visible,   // where the grow/shrink animation is heading
      scale: st.visible ? SCALES : 0,
      frame: mod(Number(st.frame ?? 0), FRAMES),
      blank: !!st.blank,
      broken: !!st.broken,
      spin: null,
      wild: null,
      vanish: 0,
      pop: 0,
      sent: "",
    };
    views.set(player.id, v);
  }
  return v;
}

function save(player, v) {
  const { visible, frame, blank, broken } = v;
  player.setDynamicProperty("roulette:state", JSON.stringify({ visible, frame, blank, broken }));
}

function texture(v) {
  if (v.wild) return frameName(v.wild.pos);
  if (v.spin) return frameName(v.spin.last);
  if (v.broken) return "broken";
  return v.blank ? "blank" : frameName(v.frame);
}

function render(player, v) {
  const title = v.scale > 0 && v.vanish <= 0 ? `${PREFIX}~${v.scale}~~p${currentPosition()}~${texture(v)}` : PREFIX + "hide";
  if (title === v.sent) return;
  v.sent = title;
  player.onScreenDisplay.setTitle(title, { fadeInDuration: 0, stayDuration: 2, fadeOutDuration: 0 });
}

// stops whatever the wheel is doing, keeping the frame it is on
function stop(v) {
  if (v.spin) v.frame = mod(v.spin.last, FRAMES);
  if (v.wild) v.frame = mod(Math.floor(v.wild.pos), FRAMES);
  v.spin = v.wild = null;
  v.vanish = v.pop = 0;
}

function show(players) {
  for (const p of players) {
    const v = view(p);
    v.visible = true;
    save(p, v);
  }
}

function hide(players) {
  for (const p of players) {
    const v = view(p);
    stop(v);
    v.visible = false;
    save(p, v);
  }
}

function blank(players) {
  for (const p of players) {
    const v = view(p);
    stop(v);
    v.blank = true;
    v.broken = false;
    v.visible = true;
    save(p, v);
  }
}

function spin(players, index, message) {
  // Same landing point for everybody watching this spin.
  const target = mod(-index * SEG + Math.round((Math.random() * 2 - 1) * JITTER), FRAMES);
  for (const p of players) {
    const v = view(p);
    stop(v);
    v.blank = v.broken = false;
    v.visible = true;
    v.spin = { start: v.frame, last: v.frame, tick: -WARN_TICKS, index, message,
               delta: MIN_TURNS * FRAMES + mod(target - v.frame, FRAMES) };
    save(p, v);
  }
}

function wild(players) {
  for (const p of players) {
    const v = view(p);
    stop(v);
    v.blank = v.broken = false;
    v.visible = true;
    v.wild = { pos: v.frame, tick: -WARN_TICKS };
    save(p, v);
  }
}

function setPosition(key) {
  position = key;
  world.setDynamicProperty("roulette:position", key);
  // the next tick sends every wheel again, with the new position
}

function warn(player, tick) {
  // three rising bells, then the wheel starts
  const k = tick + WARN_TICKS;
  if (k === 1 || k === 7 || k === 13) player.playSound("note.bell", { volume: 0.8, pitch: 1 + k / 24 });
}

function landed(player, v, s) {
  save(player, v);
  v.pop = POP_TICKS;
  if (s.message) player.onScreenDisplay.setActionBar(s.message);
  player.playSound("random.levelup", { volume: 0.8 });
  player.playSound("note.chime", { volume: 0.8 });
  const obj = world.scoreboard.getObjective(OBJECTIVE) ?? world.scoreboard.addObjective(OBJECTIVE, "Ruleta");
  obj.setScore("resultado", s.index + 1);
}

function step(player, v) {
  // grow / shrink one size per tick: hidden 0, normal SCALES, landing pop MAX_SCALE
  if (v.pop > 0) v.pop--;
  const goal = !v.visible ? 0 : v.pop > 0 ? MAX_SCALE : SCALES;
  if (v.scale < goal) v.scale++;
  else if (v.scale > goal) v.scale--;

  if (v.vanish > 0 && --v.vanish === 0) {
    // back again, broken in half
    v.broken = true;
    v.scale = SCALES;
    player.playSound("random.break", { volume: 1 });
    player.playSound("dig.wood", { volume: 1, pitch: 0.7 });
    save(player, v);
  }

  const s = v.spin;
  if (s) {
    s.tick++;
    if (s.tick <= 0) return warn(player, s.tick);
    const t = Math.min(1, s.tick / SPIN_TICKS);
    const pos = s.start + Math.round(s.delta * (1 - (1 - t) ** 3)); // ease-out cubic
    // a click each time a segment border passes under the pointer
    if (segment(pos) !== segment(s.last)) player.playSound("random.click", { volume: 0.4, pitch: 1.6 - 0.6 * t });
    s.last = pos;
    if (t >= 1) {
      v.frame = mod(pos, FRAMES);
      v.spin = null;
      landed(player, v, s);
    }
  }

  const w = v.wild;
  if (w) {
    w.tick++;
    if (w.tick <= 0) return warn(player, w.tick);
    const t = Math.min(1, w.tick / WILD_TICKS);
    const last = w.pos;
    w.pos += WILD_MIN * (WILD_MAX / WILD_MIN) ** t; // slow, then faster and faster
    if (segment(w.pos) !== segment(last)) player.playSound("random.click", { volume: 0.4, pitch: 0.8 + t });
    if (t >= 1) {
      // gone for half a second
      v.frame = mod(Math.floor(w.pos), FRAMES);
      v.wild = null;
      v.vanish = VANISH_TICKS;
      player.playSound("random.pop", { volume: 1, pitch: 0.6 });
    }
  }
}

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    const v = view(player);
    step(player, v);
    render(player, v); // only sends a title when the picture changed
  }
});

world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
  if (!initialSpawn) return;
  // titles sent while the player is still loading are lost: send the wheel again
  system.runTimeout(() => {
    if (player.isValid) view(player).sent = "";
  }, 40);
});

world.afterEvents.playerLeave.subscribe(({ playerId }) => views.delete(playerId));

// ------------------------------------------------------------ control item
function colorIndex(name) {
  const key = String(name).toLowerCase().trim();
  if (RANDOM.includes(key)) return Math.floor(Math.random() * COLORS.length);
  return COLORS.findIndex((c) => c.id === key || c.aliases.includes(key));
}

function isAdmin(player) {
  // PlayerPermissionLevel: 0 visitor, 1 member, 2 operator, 3 custom
  const level = player.playerPermissionLevel;
  return level === undefined || level >= 2;
}

async function menu(player) {
  const visible = view(player).visible;
  const res = await new ActionFormData()
    .title("§2§lRuleta")
    .body("Lo que elijas se aplica a todos los jugadores.")
    .button("Giro aleatorio", "textures/ui/roulette/f00")
    .button("Girar a un color", "textures/ui/roulette/f12")
    .button(visible ? "Ocultar ruleta" : "Mostrar ruleta", "textures/ui/roulette/ring")
    .button("Ocultar resultado", "textures/ui/roulette/blank")
    .button("Girar sin control", "textures/ui/roulette/broken")
    .button("Cambiar posición", "textures/ui/roulette/pointer")
    .show(player);
  if (res.canceled) return;
  const all = world.getAllPlayers();
  switch (res.selection) {
    case 0: return spin(all, colorIndex(RANDOM[0]));
    case 1: return colorMenu(player);
    case 2: return visible ? hide(all) : show(all);
    case 3: return blank(all);
    case 4: return wild(all);
    case 5: return positionMenu(player);
  }
}

async function colorMenu(player) {
  const res = await new ModalFormData()
    .title("§2§lGirar a un color")
    .dropdown("Color en el que caerá", COLORS.map((c) => `${c.fmt}${c.es}`))
    .textField("Mensaje al caer (opcional)", "Ej: ¡Los creepers de azalea vienen!")
    .show(player);
  if (res.canceled || !res.formValues) return;
  const [index, message] = res.formValues;
  spin(world.getAllPlayers(), Number(index), String(message ?? "").trim());
}

async function positionMenu(player) {
  const keys = Object.keys(POSITIONS);
  const form = new ActionFormData().title("§2§lPosición de la ruleta").body("Para todos los jugadores.");
  for (const k of keys) form.button((k === currentPosition() ? "§2» " : "") + POSITIONS[k]);
  const res = await form.show(player);
  if (!res.canceled) setPosition(keys[res.selection]);
}

const lastUse = new Map();
world.afterEvents.itemUse.subscribe(({ source, itemStack }) => {
  if (itemStack.typeId !== ITEM) return;
  if (system.currentTick - (lastUse.get(source.id) ?? -100) < 10) return; // one menu per click
  lastUse.set(source.id, system.currentTick);
  if (!isAdmin(source)) {
    source.sendMessage("§c[Ruleta] Solo los administradores pueden usar el control de la ruleta.");
    return;
  }
  menu(source).catch((e) => console.warn("[Ruleta] " + e));
});

// ------------------------------------------------------------ commands
const targets = (players) => (players && players.length ? players : world.getAllPlayers());

function result(players, message) {
  if (!players.length) return { status: CustomCommandStatus.Failure, message: "No hay jugadores." };
  return { status: CustomCommandStatus.Success, message: `${message} (${players.length} jugador(es))` };
}

system.beforeEvents.startup.subscribe(({ customCommandRegistry: reg }) => {
  const who = { type: CustomCommandParamType.PlayerSelector, name: "jugadores" };
  const admin = { permissionLevel: CommandPermissionLevel.GameDirectors, cheatsRequired: false };
  const simple = (name, description, action, done) =>
    reg.registerCommand({ ...admin, name, description, optionalParameters: [who] }, (origin, players) => {
      const list = targets(players);
      system.run(() => action(list));
      return result(list, done);
    });

  // /spin_roulette:rojo ["mensaje"] [jugadores] ... /spin_roulette:aleatorio
  for (const name of [...COLORS.map((c) => c.id), RANDOM[0]]) {
    reg.registerCommand(
      { ...admin, name: `spin_roulette:${name}`, description: `Gira la ruleta y cae en ${name}`,
        optionalParameters: [{ type: CustomCommandParamType.String, name: "mensaje" }, who] },
      (origin, message, players) => {
        const list = targets(players);
        const index = colorIndex(name);
        system.run(() => spin(list, index, message));
        return result(list, `Girando la ruleta: ${COLORS[index].es}`);
      });
  }
  simple("roulette:show", "Muestra la ruleta", show, "Ruleta mostrada");
  simple("roulette:hide", "Oculta la ruleta", hide, "Ruleta ocultada");
  simple("roulette:blank", "Oculta el resultado: todo en blanco con una carita", blank, "Resultado oculto");
  simple("roulette:wild", "Gira cada vez más rápido, sin resultado, hasta romperse", wild, "Girando sin control");
  for (const [key, label] of Object.entries(POSITIONS)) {
    reg.registerCommand(
      { ...admin, name: `roulette:pos_${key}`, description: `Pone la ruleta ${label.toLowerCase()}` },
      () => {
        system.run(() => setPosition(key));
        return { status: CustomCommandStatus.Success, message: `Ruleta: ${label}` };
      });
  }
  reg.registerCommand(
    { ...admin, name: "roulette:item", description: "Te da el control de la ruleta" },
    (origin) => {
      const player = origin.sourceEntity;
      if (player?.typeId !== "minecraft:player") return { status: CustomCommandStatus.Failure, message: "Solo jugadores." };
      system.run(() => player.getComponent("minecraft:inventory").container.addItem(new ItemStack(ITEM)));
      return { status: CustomCommandStatus.Success, message: "Control de la ruleta entregado" };
    });
});

// The same actions with /scriptevent: spin_roulette:rojo [mensaje], roulette:show, roulette:hide,
// roulette:blank, roulette:wild, roulette:pos_<position>
system.afterEvents.scriptEventReceive.subscribe(({ id, message, sourceEntity }) => {
  const [ns, key] = id.split(":");
  const list = world.getAllPlayers();
  if (ns === "spin_roulette") {
    const index = colorIndex(key);
    if (index < 0) {
      const msg = `§c[Ruleta] Color desconocido: ${key}. Usa: ${COLORS.map((c) => c.id).join(", ")}, ${RANDOM[0]}`;
      if (sourceEntity?.typeId === "minecraft:player") sourceEntity.sendMessage(msg);
      else console.warn(msg);
      return;
    }
    return spin(list, index, message.trim());
  }
  if (key.startsWith("pos_") && POSITIONS[key.slice(4)]) return setPosition(key.slice(4));
  const actions = { show, hide, blank, wild };
  actions[key]?.(list);
}, { namespaces: ["spin_roulette", "roulette"] });
"""


def script():
    js_colors = [{k: c[k] for k in ("id", "es", "fmt", "aliases")} for c in COLORS]
    out = SCRIPT
    positions = {k: p["es"] for k, p in POSITIONS.items()}
    for key, value in dict(PREFIX=PREFIX, ITEM=ITEM, FRAMES=FRAMES, SCALES=SCALES, MAX_SCALE=MAX_SCALE,
                           SPIN_TICKS=SPIN_TICKS, MIN_TURNS=MIN_TURNS, JITTER=JITTER, WARN_TICKS=WARN_TICKS,
                           POP_TICKS=POP_TICKS, WILD_TICKS=WILD_TICKS, VANISH_TICKS=VANISH_TICKS,
                           POSITIONS=positions, DEFAULT_POSITION=DEFAULT_POSITION, COLORS=js_colors,
                           RANDOM=RANDOM).items():
        out = out.replace(f"__{key}__", json.dumps(value, ensure_ascii=False))
    return out


def item():
    return {
        "format_version": "1.21.90",
        "minecraft:item": {
            "description": {"identifier": ITEM, "menu_category": {"category": "items"}},
            "components": {
                "minecraft:icon": {"textures": {"default": "roulette_controller"}},
                "minecraft:display_name": {"value": "§6Control de la Ruleta"},
                "minecraft:max_stack_size": 1,
                "minecraft:glint": True,
            },
        },
    }


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Comandos de administrador para girar una ruleta de 6 colores.",
                   "uuid": UUIDS["bp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUIDS["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUIDS["bp_script"], "version": VERSION,
             "entry": "scripts/main.js"}],
        "dependencies": [{"uuid": UUIDS["rp"], "version": VERSION},
                         {"module_name": "@minecraft/server", "version": SCRIPT_API},
                         {"module_name": "@minecraft/server-ui", "version": SCRIPT_UI_API}],
    }
    rp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "La ruleta en la esquina de la pantalla.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


def main():
    prev = "--preview" in sys.argv
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)
        os.makedirs(pack)
    tex = os.path.join(RP, "textures", "ui", "roulette")
    os.makedirs(tex)

    base = disk([c["hex"] for c in COLORS])
    frames = []
    for k in range(FRAMES):
        # frame k = wheel turned k*5 degrees clockwise (PIL rotates counter-clockwise)
        f = small(base.rotate(-k * 360 / FRAMES, resample=Image.BICUBIC))
        f.save(os.path.join(tex, f"f{k:02d}.png"))
        frames.append(f)
    big_ring = ring()
    extra = {
        "blank": small(smiley(disk([BLANK] * len(COLORS)))),
        "ring": small(big_ring),
        "broken": small(broken(base, big_ring)),
    }
    for name, im in extra.items():
        im.save(os.path.join(tex, f"{name}.png"))
    tip = pointer()
    tip.save(os.path.join(tex, "pointer.png"))

    wheel = composite(frames[0], extra["ring"], tip, 112)
    pack_icon = Image.new("RGBA", (128, 128), (40, 52, 36, 255))
    pack_icon.alpha_composite(wheel, (8, 0))
    for pack in (BP, RP):
        pack_icon.save(os.path.join(pack, "pack_icon.png"))
    os.makedirs(os.path.join(RP, "textures", "items"))
    composite(frames[0], extra["ring"], tip, 30).resize((32, 32), Image.LANCZOS).save(
        os.path.join(RP, "textures", "items", "roulette_controller.png"))
    write(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": "roulette", "texture_name": "atlas.items",
        "texture_data": {"roulette_controller": {"textures": "textures/items/roulette_controller"}}})

    write(os.path.join(RP, "ui", "hud_screen.json"), hud())
    write(os.path.join(BP, "items", "controller.json"), item())
    write(os.path.join(BP, "scripts", "main.js"), script())
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "Roulette.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    if prev:
        preview(frames, extra, tip)
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


def preview(frames, extra, tip):
    """The wheel resting on each colour, then the hidden result and the broken wheel."""
    cell, size = 150, 128
    cells = [(composite(frames[(-i * FRAMES // len(COLORS)) % FRAMES], extra["ring"], tip, size), c["es"])
             for i, c in enumerate(COLORS)]
    cells += [(composite(extra["blank"], extra["ring"], tip, size), "Resultado oculto"),
              (composite(extra["broken"], None, None, size), "Girar sin control")]
    font = ImageFont.load_default(size=15)
    cols = 4
    rows = (len(cells) + cols - 1) // cols
    out = Image.new("RGBA", (cell * cols, (cell + 30) * rows), (36, 44, 34, 255))
    d = ImageDraw.Draw(out)
    for k, (im, label) in enumerate(cells):
        x, y = (k % cols) * cell, (k // cols) * (cell + 30)
        out.alpha_composite(im, (x + (cell - size) // 2, y + 4))
        d.text((x + cell // 2, y + cell + 14), label, fill=(235, 235, 220, 255), anchor="mm", font=font)
    out.save(os.path.join(ROOT, "docs", "roulette_preview.png"))


if __name__ == "__main__":
    main()
