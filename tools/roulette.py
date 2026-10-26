"""Builds the "Ruleta de Colores" add-on: admin commands that show and spin a
6-colour wheel drawn in the bottom corner of each player's HUD.

How the HUD wheel works: the script sends titles that start with PREFIX
("_roul:f07", "_roul:hide"...). ui/hud_screen.json hides those titles,
remembers the last one and uses it as the texture path of the wheel, so each
title shows one pre-rendered frame of the spinning wheel.

    python3 tools/roulette.py            # regenerate the packs and the .mcaddon
    python3 tools/roulette.py --preview  # also refresh docs/roulette_preview.png
"""
import json
import math
import os
import shutil
import sys
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_NAME = "Ruleta de Colores"
BP = os.path.join(ROOT, "Roulette_BP")
RP = os.path.join(ROOT, "Roulette_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
SCRIPT_API = "2.0.0"  # stable: custom commands without the "Beta APIs" experiment
MIN_ENGINE = [1, 21, 90]
UUIDS = dict(bp="cebd64fa-ccb8-4f9f-a744-dc03c3d56ea8", bp_data="de1aa5e9-fa5f-47a0-8041-dcc2b0df6867",
             bp_script="ce237dc6-fa54-47fc-b7ae-907460106128", rp="3dcf6310-841c-4f10-9844-c8b91af2d428",
             rp_res="b1f1a7f5-211f-465e-a0b0-59f6244f9b99")

# Segments clockwise from the pointer (top) when the wheel is at frame 0.
COLORS = [
    dict(id="rojo", es="Rojo", fmt="§c", hex="#e53935", aliases=["red"]),
    dict(id="verde", es="Verde", fmt="§a", hex="#43a047", aliases=["green"]),
    dict(id="azul", es="Azul", fmt="§9", hex="#1e56d6", aliases=["blue"]),
    dict(id="blanco", es="Blanco", fmt="§f", hex="#f4f4f4", aliases=["white"]),
    dict(id="celeste", es="Celeste", fmt="§b", hex="#4fc3f7", aliases=["light_blue", "cyan"]),
    dict(id="amarillo", es="Amarillo", fmt="§e", hex="#fdd835", aliases=["yellow"]),
]
RANDOM = ["aleatorio", "random"]

PREFIX = "_roul:"
FRAMES = 72          # one frame every 5 degrees
TEX_SIZE = 128
SS = 4               # supersampling when drawing
UI_SIZE = 64         # wheel size on screen, in UI units
ANCHOR = "bottom_right"
OFFSET = [-4, -4]
SPIN_TICKS = 120     # 6 s
MIN_TURNS = 4        # full turns before it slows down on the colour
JITTER = 4           # frames (x5 degrees) the landing point moves inside the segment


def hx(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- textures
def disk():
    """The rotating part, at SS x TEX_SIZE: six segments and the hub."""
    n = TEX_SIZE * SS
    c = n / 2
    r = c * 0.86
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    seg = 360 / len(COLORS)
    for i, color in enumerate(COLORS):
        # PIL angles: 0 = east, clockwise. Segment i is centred at i*seg from the top.
        start = -90 + i * seg - seg / 2
        d.pieslice([c - r, c - r, c + r, c + r], start, start + seg, fill=hx(color["hex"]))
        # soft shading toward the rim
        shade = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(shade).pieslice([c - r, c - r, c + r, c + r], start, start + seg, fill=(0, 0, 0, 40))
        ImageDraw.Draw(shade).ellipse([c - r * 0.7, c - r * 0.7, c + r * 0.7, c + r * 0.7], fill=(0, 0, 0, 0))
        im.alpha_composite(shade)
    for i in range(len(COLORS)):
        a = math.radians(-90 + i * seg - seg / 2)
        d.line([c, c, c + r * math.cos(a), c + r * math.sin(a)], fill=(40, 30, 25, 255), width=SS * 2)
    h = r * 0.2
    d.ellipse([c - h, c - h, c + h, c + h], fill=(70, 50, 35, 255), outline=(220, 180, 70, 255), width=SS * 3)
    d.ellipse([c - h * 0.35, c - h * 0.35, c + h * 0.35, c + h * 0.35], fill=(240, 205, 90, 255))
    return im


def ring():
    """Static golden rim with light bulbs, drawn over the disk."""
    n = TEX_SIZE * SS
    c = n / 2
    ro, ri = c * 0.98, c * 0.85
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([c - ro, c - ro, c + ro, c + ro], fill=(120, 75, 30, 255))
    d.ellipse([c - ro + SS * 2, c - ro + SS * 2, c + ro - SS * 2, c + ro - SS * 2], fill=(214, 160, 52, 255))
    d.ellipse([c - ri, c - ri, c + ri, c + ri], fill=(0, 0, 0, 0))
    d.ellipse([c - ri, c - ri, c + ri, c + ri], outline=(90, 55, 20, 255), width=SS * 2)
    rm, b = (ro + ri) / 2, SS * 3.2
    for k in range(18):
        a = math.radians(k * 20)
        x, y = c + rm * math.cos(a), c + rm * math.sin(a)
        d.ellipse([x - b, y - b, x + b, y + b], fill=(255, 245, 200, 255), outline=(150, 100, 30, 255), width=SS)
    return im


def pointer():
    n = 32 * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tri = [(n * 0.12, n * 0.08), (n * 0.88, n * 0.08), (n * 0.5, n * 0.95)]
    d.polygon(tri, fill=(60, 35, 20, 255))
    inner = [(n * 0.24, n * 0.16), (n * 0.76, n * 0.16), (n * 0.5, n * 0.78)]
    d.polygon(inner, fill=(250, 250, 250, 255))
    return im.resize((32, 32), Image.LANCZOS)


def small(im):
    return im.resize((TEX_SIZE, TEX_SIZE), Image.LANCZOS)


def composite(frame_img, ring_img, pointer_img, size):
    """Wheel + rim + pointer as the HUD draws it (for the icon and preview)."""
    out = Image.new("RGBA", (size, size + size // 8), (0, 0, 0, 0))
    w = frame_img.resize((size, size), Image.LANCZOS)
    out.alpha_composite(w, (0, size // 8))
    out.alpha_composite(ring_img.resize((size, size), Image.LANCZOS), (0, size // 8))
    p = pointer_img.resize((size // 4, size // 4), Image.LANCZOS)
    out.alpha_composite(p, ((size - p.width) // 2, 0))
    return out


# ---------------------------------------------------------------- UI
def hud():
    tex = "textures/ui/roulette"
    src = "roul_data_control"
    shown = f"(not ((#preserved_text - '{PREFIX}') = #preserved_text) and not (#preserved_text = '{PREFIX}hide'))"
    corner = dict(anchor_from=ANCHOR, anchor_to=ANCHOR, offset=OFFSET)
    tip = UI_SIZE // 4
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
                    {"binding_name": "#hud_title_text_string", "binding_name_override": "#preserved_text",
                     "binding_condition": "visibility_changed"},
                    {"binding_type": "view",
                     "source_property_name": f"(not (#hud_title_text_string = #preserved_text) and "
                                             f"not ((#hud_title_text_string - '{PREFIX}') = #hud_title_text_string))",
                     "target_property_name": "#visible"}]}},
                # Every frame stays loaded, so the first spin doesn't flicker.
                {"roulette_preload": dict(type="panel", size=[1, 1], **corner, controls=[
                    {f"pre_{k:02d}": {"type": "image", "texture": f"{tex}/f{k:02d}", "size": [1, 1], "alpha": 0.01}}
                    for k in range(FRAMES)])},
                {"roulette_wheel": dict(
                    type="panel", size=[UI_SIZE, UI_SIZE + tip // 2], **corner,
                    bindings=[{"binding_type": "view", "source_control_name": src,
                               "source_property_name": shown, "target_property_name": "#visible"}],
                    controls=[
                        {"disk": {"type": "image", "texture": "#texture", "size": [UI_SIZE, UI_SIZE],
                                  "anchor_from": "bottom_middle", "anchor_to": "bottom_middle", "layer": 1,
                                  "bindings": [{"binding_type": "view", "source_control_name": src,
                                                "source_property_name": f"('{tex}/' + (#preserved_text - '{PREFIX}'))",
                                                "target_property_name": "#texture"}]}},
                        {"rim": {"type": "image", "texture": f"{tex}/ring", "size": [UI_SIZE, UI_SIZE],
                                 "anchor_from": "bottom_middle", "anchor_to": "bottom_middle", "layer": 2}},
                        {"pointer": {"type": "image", "texture": f"{tex}/pointer", "size": [tip, tip],
                                     "anchor_from": "top_middle", "anchor_to": "top_middle", "layer": 3}},
                    ])},
            ]},
    }


# ---------------------------------------------------------------- script
SCRIPT = r"""// Ruleta de Colores: admin commands that show and spin a 6-colour wheel in the
// bottom corner of the HUD. Generated by tools/roulette.py.
//
// The wheel is drawn by ui/hud_screen.json (resource pack): every title that
// starts with PREFIX is hidden and used as the frame to draw.
import { CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, system, world } from "@minecraft/server";

const PREFIX = __PREFIX__;
const FRAMES = __FRAMES__;
const SPIN_TICKS = __SPIN_TICKS__;
const MIN_TURNS = __MIN_TURNS__;
const JITTER = __JITTER__;
// Clockwise from the pointer at frame 0.
const COLORS = __COLORS__;
const RANDOM = __RANDOM__;
const SEG = FRAMES / COLORS.length;
const OBJECTIVE = "ruleta"; // score "resultado": 1..6, the colour it landed on

const spins = new Map(); // player id -> running spin

const mod = (a, n) => ((a % n) + n) % n;

function colorIndex(name) {
  const key = String(name).toLowerCase().trim();
  if (RANDOM.includes(key)) return Math.floor(Math.random() * COLORS.length);
  return COLORS.findIndex((c) => c.id === key || c.aliases.includes(key));
}

function send(player, text) {
  player.onScreenDisplay.setTitle(PREFIX + text, { fadeInDuration: 0, stayDuration: 2, fadeOutDuration: 0 });
}

function frameName(frame) {
  return "f" + String(frame).padStart(2, "0");
}

function currentFrame(player) {
  const spin = spins.get(player.id);
  if (spin) return mod(spin.last, FRAMES);
  return mod(Number(player.getDynamicProperty("roulette:frame") ?? 0), FRAMES);
}

function show(players) {
  for (const p of players) {
    p.setDynamicProperty("roulette:visible", true);
    send(p, frameName(currentFrame(p)));
  }
}

function hide(players) {
  for (const p of players) {
    p.setDynamicProperty("roulette:frame", currentFrame(p));
    spins.delete(p.id);
    p.setDynamicProperty("roulette:visible", false);
    send(p, "hide");
  }
}

function spin(players, index) {
  // Same landing point for everybody watching this spin.
  const target = mod(-index * SEG + Math.round((Math.random() * 2 - 1) * JITTER), FRAMES);
  for (const p of players) {
    const start = currentFrame(p);
    p.setDynamicProperty("roulette:visible", true);
    spins.set(p.id, { player: p, start, last: start, tick: 0, index,
                      delta: MIN_TURNS * FRAMES + mod(target - start, FRAMES) });
    send(p, frameName(start));
  }
}

function landed(player, frame, index) {
  const c = COLORS[index];
  player.setDynamicProperty("roulette:frame", frame);
  player.onScreenDisplay.setActionBar(`${c.fmt}§l${c.es.toUpperCase()}`);
  player.sendMessage(`§6[Ruleta]§r Ha caído en ${c.fmt}§l${c.es}`);
  player.playSound("random.levelup", { volume: 0.8 });
  const obj = world.scoreboard.getObjective(OBJECTIVE) ?? world.scoreboard.addObjective(OBJECTIVE, "Ruleta");
  obj.setScore("resultado", index + 1);
}

system.runInterval(() => {
  for (const [id, s] of spins) {
    if (!s.player.isValid) {
      spins.delete(id);
      continue;
    }
    s.tick++;
    const t = Math.min(1, s.tick / SPIN_TICKS);
    const pos = s.start + Math.round(s.delta * (1 - (1 - t) ** 3)); // ease-out cubic
    if (pos !== s.last) {
      send(s.player, frameName(mod(pos, FRAMES)));
      // a click each time a segment border passes under the pointer
      if (Math.floor((pos + SEG / 2) / SEG) !== Math.floor((s.last + SEG / 2) / SEG)) {
        s.player.playSound("random.click", { volume: 0.4, pitch: 1.6 - 0.6 * t });
      }
      s.last = pos;
    }
    if (t >= 1) {
      spins.delete(id);
      landed(s.player, mod(pos, FRAMES), s.index);
    }
  }
});

// Players who join (or come back) with the wheel open see it again.
world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
  if (!initialSpawn || !player.getDynamicProperty("roulette:visible")) return;
  system.runTimeout(() => {
    if (player.isValid) send(player, frameName(currentFrame(player)));
  }, 40);
});

// ------------------------------------------------------------ commands
const targets = (players) => (players && players.length ? players : world.getAllPlayers());

function result(players, message) {
  if (!players.length) return { status: CustomCommandStatus.Failure, message: "No hay jugadores." };
  return { status: CustomCommandStatus.Success, message: `${message} (${players.length} jugador(es))` };
}

system.beforeEvents.startup.subscribe(({ customCommandRegistry: reg }) => {
  const who = [{ type: CustomCommandParamType.PlayerSelector, name: "jugadores" }];
  const admin = { permissionLevel: CommandPermissionLevel.GameDirectors, cheatsRequired: false, optionalParameters: who };

  // /spin_roulette:rojo, /spin_roulette:verde ... /spin_roulette:aleatorio
  for (const name of [...COLORS.map((c) => c.id), RANDOM[0]]) {
    reg.registerCommand(
      { ...admin, name: `spin_roulette:${name}`, description: `Gira la ruleta y cae en ${name}` },
      (origin, players) => {
        const list = targets(players);
        const index = colorIndex(name);
        system.run(() => spin(list, index));
        return result(list, `Girando la ruleta: ${COLORS[index].es}`);
      });
  }
  reg.registerCommand(
    { ...admin, name: "roulette:show", description: "Muestra la ruleta en la esquina de la pantalla" },
    (origin, players) => {
      const list = targets(players);
      system.run(() => show(list));
      return result(list, "Ruleta mostrada");
    });
  reg.registerCommand(
    { ...admin, name: "roulette:hide", description: "Oculta la ruleta" },
    (origin, players) => {
      const list = targets(players);
      system.run(() => hide(list));
      return result(list, "Ruleta ocultada");
    });
});

// The same actions with /scriptevent: spin_roulette:rojo, roulette:show, roulette:hide
system.afterEvents.scriptEventReceive.subscribe(({ id, sourceEntity }) => {
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
    spin(list, index);
  } else if (id === "roulette:show") show(list);
  else if (id === "roulette:hide") hide(list);
}, { namespaces: ["spin_roulette", "roulette"] });
"""


def script():
    js_colors = [{k: c[k] for k in ("id", "es", "fmt", "aliases")} for c in COLORS]
    out = SCRIPT
    for key, value in dict(PREFIX=PREFIX, FRAMES=FRAMES, SPIN_TICKS=SPIN_TICKS, MIN_TURNS=MIN_TURNS,
                           JITTER=JITTER, COLORS=js_colors, RANDOM=RANDOM).items():
        out = out.replace(f"__{key}__", json.dumps(value, ensure_ascii=False))
    return out


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
                         {"module_name": "@minecraft/server", "version": SCRIPT_API}],
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
    tex = os.path.join(RP, "textures", "ui", "roulette")
    os.makedirs(tex)

    base = disk()
    frames = []
    for k in range(FRAMES):
        # frame k = wheel turned k*5 degrees clockwise (PIL rotates counter-clockwise)
        f = small(base.rotate(-k * 360 / FRAMES, resample=Image.BICUBIC))
        f.save(os.path.join(tex, f"f{k:02d}.png"))
        frames.append(f)
    rim = small(ring())
    rim.save(os.path.join(tex, "ring.png"))
    tip = pointer()
    tip.save(os.path.join(tex, "pointer.png"))

    icon = composite(frames[0], rim, tip, 112)
    pack_icon = Image.new("RGBA", (128, 128), (36, 40, 52, 255))
    pack_icon.alpha_composite(icon, (8, 0))
    for pack in (BP, RP):
        os.makedirs(pack, exist_ok=True)
        pack_icon.save(os.path.join(pack, "pack_icon.png"))

    write(os.path.join(RP, "ui", "hud_screen.json"), hud())
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
        # The wheel resting on each colour, as the pointer shows it.
        cell = 150
        strip = Image.new("RGBA", (cell * len(COLORS), cell + 20), (36, 40, 52, 255))
        d = ImageDraw.Draw(strip)
        for i, c in enumerate(COLORS):
            k = (-i * FRAMES // len(COLORS)) % FRAMES
            strip.alpha_composite(composite(frames[k], rim, tip, 128), (i * cell + 11, 2))
            d.text((i * cell + cell // 2, cell + 6), c["es"], fill=hx(c["hex"]), anchor="mm")
        strip.save(os.path.join(ROOT, "docs", "roulette_preview.png"))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), "->", os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
