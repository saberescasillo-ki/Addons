"""Builds the "Reproductor de Música" add-on: an item that plays songs.

The songs are NOT 3D: they sound at the same volume wherever you are, like the
background music of Minecraft (they use the "music" volume slider).

Add your own songs:
  1. Put the audio files (.ogg, .mp3, .wav, .flac, .m4a) in sources/music_player/canciones/
  2. (Optional) give them a name and an order in sources/music_player/canciones.json
  3. Run:  python3 tools/music_player.py         (needs Pillow and ffmpeg)

Files that are not .ogg Vorbis are converted with ffmpeg. The length of every
song is measured so the player knows when it ends (repeat / next song).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_NAME = "Reproductor de Música"
BP = os.path.join(ROOT, "MusicPlayer_BP")
RP = os.path.join(ROOT, "MusicPlayer_RP")
DIST = os.path.join(ROOT, "dist")
SONGS_DIR = os.path.join(ROOT, "sources", "music_player", "canciones")
SONGS_JSON = os.path.join(ROOT, "sources", "music_player", "canciones.json")

VERSION = [1, 1, 0]
SCRIPT_API = "2.0.0"
SCRIPT_UI_API = "2.0.0"
MIN_ENGINE = [1, 21, 90]
UUIDS = dict(bp="6de1590f-b6b2-422c-8ffb-aaa714a1c165", bp_data="44d6e28f-688f-48fc-86e6-39b7ba839703",
             bp_script="519a813b-3f17-4748-bca3-e5def8cf0bfd", rp="37f79877-e758-4e1f-857f-a5a93e93dab1",
             rp_res="c68e741e-b614-48ec-a479-4956ebd08506")

NS = "musica"
ITEM = f"{NS}:reproductor"
AUDIO_EXT = (".ogg", ".mp3", ".wav", ".flac", ".m4a", ".aac", ".opus")

# Copied into scripts/canciones.js (you can also change them there by hand).
SETTINGS = dict(
    volumen=1.0,             # 0.0 - 1.0
    oyentes_por_defecto="yo",    # who hears the songs until a player changes it: "yo", "todos" or "sel"
    callar_musica_vanilla=True,  # stop the vanilla music when a song starts
    mostrar_titulo=True,     # show "Reproduciendo: ..." in the action bar
)
# Volume slider that controls the songs: "music" (Música), "record" (Tocadiscos), "ui" (Interfaz)...
CATEGORY = "music"


# ---------------------------------------------------------------- helpers
def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "cancion"


def nice_name(filename):
    return re.sub(r"[_\-]+", " ", os.path.splitext(filename)[0]).strip().title()


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=codec_name:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    codec = (info.get("streams") or [{}])[0].get("codec_name", "")
    return codec, float(info.get("format", {}).get("duration") or 0)


def load_songs():
    """The song list: canciones.json order first, then any other file in the folder."""
    files = sorted(f for f in os.listdir(SONGS_DIR) if f.lower().endswith(AUDIO_EXT)) \
        if os.path.isdir(SONGS_DIR) else []
    listed = []
    if os.path.exists(SONGS_JSON):
        with open(SONGS_JSON, encoding="utf-8") as f:
            listed = json.load(f)
    songs, seen = [], set()
    for entry in listed:
        if entry.get("archivo") not in files:
            print("  aviso: no existe", entry.get("archivo"), "(se ignora)")
            continue
        songs.append(entry)
        seen.add(entry["archivo"])
    songs += [{"archivo": f} for f in files if f not in seen]
    if not songs:
        sys.exit(f"No hay canciones en {os.path.relpath(SONGS_DIR, ROOT)}")

    ids = set()
    for s in songs:
        s.setdefault("nombre", nice_name(s["archivo"]))
        base = sid = slug(os.path.splitext(s["archivo"])[0])
        n = 2
        while sid in ids:
            sid, n = f"{base}_{n}", n + 1
        ids.add(sid)
        s["id"] = sid
    return songs


def copy_song(song):
    """Copies (or converts to .ogg Vorbis) one song into the resource pack; returns its length."""
    src = os.path.join(SONGS_DIR, song["archivo"])
    dst = os.path.join(RP, "sounds", NS, song["id"] + ".ogg")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    codec, _ = probe(src)
    if codec == "vorbis" and src.lower().endswith(".ogg"):
        shutil.copyfile(src, dst)
    else:
        print("  convirtiendo", song["archivo"], "a .ogg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "2", "-ar", "44100",
                        "-c:a", "libvorbis", "-q:a", "4", dst], check=True)
    return round(probe(dst)[1], 2)


# ---------------------------------------------------------------- textures
def icon():
    """A small purple music box with a golden double note."""
    pal = {"k": (36, 20, 52, 255), "p": (124, 72, 190, 255), "P": (168, 118, 230, 255),
           "d": (84, 44, 132, 255), "g": (255, 205, 72, 255), "G": (255, 240, 170, 255),
           "o": (196, 140, 40, 255), "w": (240, 230, 255, 255)}
    rows = [
        "......kkkkkkkk..",
        "......kGggggok..",
        "......kgkkkkgk..",
        "......kgk...gk..",
        "......kgk...gk..",
        "......kgk...gk..",
        "....kkkgk.kkgk..",
        "...kGgggk.kGggk.",
        "...kgggok.kgggk.",
        "kkkkkkkkkkkkkkkk",
        "kPPPPPPPPPPPPPPk",
        "kPwPpppppppppPpk",
        "kPpppkkkkkkppPdk",
        "kPpppkddddkpppdk",
        "kpddddddddddddkk",
        "kkkkkkkkkkkkkkk.",
    ]
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                im.putpixel((x, y), pal[ch])
    return im


# ---------------------------------------------------------------- packs
def item():
    return {"format_version": "1.21.90", "minecraft:item": {
        "description": {"identifier": ITEM, "menu_category": {"category": "items"}},
        "components": {
            "minecraft:icon": "musica_reproductor",
            "minecraft:display_name": {"value": f"item.{ITEM}.name"},
            "minecraft:max_stack_size": 1,
            "minecraft:glint": False,
            "minecraft:use_modifiers": {"use_duration": 0.1, "movement_modifier": 1.0},
        }}}


def sound_definitions(songs):
    return {"format_version": "1.20.20", "sound_definitions": {
        f"{NS}.{s['id']}": {"category": CATEGORY, "sounds": [{
            "name": f"sounds/{NS}/{s['id']}", "stream": True, "is3D": False,
            "volume": 1.0, "load_on_low_memory": True}]}
        for s in songs}}


def songs_js(songs):
    lines = [
        "// Lista de canciones del Reproductor de Música.",
        "// Generado por tools/music_player.py, pero también se puede editar a mano:",
        "//   sonido   -> el nombre del sonido en MusicPlayer_RP/sounds/sound_definitions.json",
        "//   nombre   -> lo que sale en el menú",
        "//   segundos -> lo que dura (para saber cuándo termina; 0 = no se sabe)",
        "",
        "export const AJUSTES = " + re.sub(r'"(\w+)":', r"\1:", json.dumps(SETTINGS, indent=2)) + ";",
        "",
        "export const CANCIONES = [",
    ]
    for s in songs:
        entry = dict(sonido=f"{NS}.{s['id']}", nombre=s["nombre"], segundos=s["segundos"])
        if s.get("autor"):
            entry["autor"] = s["autor"]
        lines.append("  " + json.dumps(entry, ensure_ascii=False) + ",")
    lines.append("];")
    return "\n".join(lines) + "\n"


SCRIPT = r"""// Reproductor de Música: menu to play songs that are not 3D (same volume everywhere).
// Generated by tools/music_player.py. The songs and settings are in canciones.js.
import { system, world } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import { AJUSTES, CANCIONES } from "./canciones.js";

const ITEM = "__ITEM__";
const MODE_PROP = "musica:modo";
const AUDIENCE_PROP = "musica:oyentes";
const MODES = [
  { id: "una", label: "Una vez" },
  { id: "repetir", label: "Repetir canción" },
  { id: "todas", label: "Todas en orden" },
  { id: "aleatorio", label: "Aleatorio" },
];
const AUDIENCES = { yo: "Solo yo", todos: "Todos", sel: "Jugadores seleccionados" };

// Who started the music (player id) -> { index, endsAt, ears: [ids of the players that hear it] }
const playing = new Map();
const lastOpen = new Map();

function online(id) {
  return world.getAllPlayers().find((p) => p.id === id);
}

function run(p, cmd) {
  try {
    p.runCommand(cmd);
  } catch {}
}

// ------------------------------------------------------------ settings saved on the player
function getMode(owner) {
  const v = owner.getDynamicProperty(MODE_PROP);
  return MODES.find((m) => m.id === v) ?? MODES[0];
}

function getAudience(owner) {
  try {
    const a = JSON.parse(String(owner.getDynamicProperty(AUDIENCE_PROP) ?? ""));
    if (AUDIENCES[a.tipo]) return { tipo: a.tipo, ids: Array.isArray(a.ids) ? a.ids : [] };
  } catch {}
  const tipo = AUDIENCES[AJUSTES.oyentes_por_defecto] ? AJUSTES.oyentes_por_defecto : "yo";
  return { tipo, ids: [] };
}

function setAudience(owner, audience) {
  owner.setDynamicProperty(AUDIENCE_PROP, JSON.stringify(audience));
}

function listenersOf(owner, audience) {
  const all = world.getAllPlayers();
  if (audience.tipo === "todos") return all;
  if (audience.tipo === "sel") return all.filter((p) => audience.ids.includes(p.id));
  return [owner];
}

function audienceText(owner, audience) {
  if (audience.tipo !== "sel") return AUDIENCES[audience.tipo];
  const names = listenersOf(owner, audience).map((p) => p.name);
  return names.length ? names.join(", ") : "nadie (elige jugadores)";
}

// ------------------------------------------------------------ playing
function stopFor(ownerId) {
  const cur = playing.get(ownerId);
  playing.delete(ownerId);
  if (!cur) return;
  const song = CANCIONES[cur.index];
  for (const id of cur.ears) {
    const p = online(id);
    if (p && song) run(p, `stopsound @s ${song.sonido}`);
  }
}

function play(owner, index) {
  const song = CANCIONES[index];
  if (!song) return;
  stopFor(owner.id);
  const ears = listenersOf(owner, getAudience(owner));
  if (ears.length === 0) {
    owner.onScreenDisplay.setActionBar("§cNo has elegido a nadie para escuchar");
    return;
  }
  for (const p of ears) {
    if (AJUSTES.callar_musica_vanilla) run(p, "music stop 0");
    try {
      p.playSound(song.sonido, { volume: AJUSTES.volumen });
    } catch {}
    if (AJUSTES.mostrar_titulo) {
      const who = p.id === owner.id ? "§dReproduciendo: " : `§d${owner.name} te pone: `;
      p.onScreenDisplay.setActionBar(`${who}§f${song.nombre}`);
    }
  }
  const ticks = Math.ceil((song.segundos || 0) * 20);
  playing.set(owner.id, {
    index,
    ears: ears.map((p) => p.id),
    endsAt: ticks > 0 ? system.currentTick + ticks + 10 : Infinity,
  });
}

function nextIndex(mode, index) {
  if (mode === "repetir") return index;
  if (mode === "todas") return (index + 1) % CANCIONES.length;
  if (mode === "aleatorio") {
    if (CANCIONES.length < 2) return index;
    let i = index;
    while (i === index) i = Math.floor(Math.random() * CANCIONES.length);
    return i;
  }
  return -1;
}

// When a song ends: repeat it, play the next one, or stop (depending on the mode).
system.runInterval(() => {
  const now = system.currentTick;
  for (const [ownerId, cur] of [...playing]) {
    const owner = online(ownerId);
    if (!owner) {
      stopFor(ownerId);
      continue;
    }
    if (now < cur.endsAt) continue;
    const next = nextIndex(getMode(owner).id, cur.index);
    if (next < 0) playing.delete(ownerId);
    else play(owner, next);
  }
}, 10);

// If whoever put the music leaves, it stops for everyone.
world.afterEvents.playerLeave.subscribe(({ playerId }) => {
  stopFor(playerId);
  lastOpen.delete(playerId);
});

// ------------------------------------------------------------ menus
function afterAudienceChange(owner) {
  // A song already playing starts again for the new listeners.
  const cur = playing.get(owner.id);
  if (cur) play(owner, cur.index);
  system.run(() => openMenu(owner));
}

function openPlayerPicker(owner) {
  const players = world.getAllPlayers();
  const audience = getAudience(owner);
  const chosen = audience.tipo === "sel" ? audience.ids : [owner.id];
  const form = new ModalFormData().title("§5Elegir jugadores");
  for (const p of players) {
    form.toggle(p.id === owner.id ? `${p.name} §7(tú)` : p.name, { defaultValue: chosen.includes(p.id) });
  }
  form.submitButton("Guardar");
  form.show(owner).then((res) => {
    if (res.canceled || !res.formValues) return system.run(() => openAudienceMenu(owner));
    const ids = players.filter((p, i) => res.formValues[i] === true).map((p) => p.id);
    setAudience(owner, { tipo: "sel", ids });
    afterAudienceChange(owner);
  });
}

function openAudienceMenu(owner) {
  const audience = getAudience(owner);
  const form = new ActionFormData()
    .title("§5¿Quién escucha?")
    .body(`§7Ahora: §f${audienceText(owner, audience)}\n§7Si ya suena una canción, empieza de nuevo para ellos.`);
  const mark = (tipo) => (audience.tipo === tipo ? "§a> " : "");
  form.button(`${mark("yo")}Solo yo`);
  form.button(`${mark("todos")}Todos`);
  form.button(`${mark("sel")}Jugadores seleccionados...`);
  form.button("§8< Volver");
  form.show(owner).then((res) => {
    if (res.canceled || res.selection === undefined) return;
    if (res.selection === 0 || res.selection === 1) {
      setAudience(owner, { tipo: res.selection === 0 ? "yo" : "todos", ids: audience.ids });
      afterAudienceChange(owner);
    } else if (res.selection === 2) {
      system.run(() => openPlayerPicker(owner));
    } else {
      system.run(() => openMenu(owner));
    }
  });
}

function openMenu(owner) {
  const cur = playing.get(owner.id);
  const mode = getMode(owner);
  const audience = getAudience(owner);
  const song = cur && CANCIONES[cur.index];
  const form = new ActionFormData().title("§5Reproductor de Música");
  form.body(
    (song ? `§aSonando: §f${song.nombre}` : "§7No suena nada") +
      `\n§7Escuchan: §f${audienceText(owner, audience)}` +
      `\n§7Modo: §f${mode.label}`
  );
  const actions = [];
  if (song) {
    form.button("§c■ Detener");
    actions.push(() => stopFor(owner.id));
  }
  form.button(`§9¿Quién escucha?\n§8${audienceText(owner, audience)}`);
  actions.push(() => system.run(() => openAudienceMenu(owner)));
  form.button(`§9Modo: ${mode.label}`);
  actions.push(() => {
    const i = MODES.indexOf(mode);
    owner.setDynamicProperty(MODE_PROP, MODES[(i + 1) % MODES.length].id);
    system.run(() => openMenu(owner));
  });
  CANCIONES.forEach((c, i) => {
    const on = cur && cur.index === i;
    form.button((on ? "§a> " : "") + c.nombre + (c.autor ? `\n§8${c.autor}` : ""));
    actions.push(() => play(owner, i));
  });
  form.show(owner).then((res) => {
    if (res.canceled || res.selection === undefined) return;
    actions[res.selection]?.();
  });
}

world.afterEvents.itemUse.subscribe(({ source: player, itemStack }) => {
  if (itemStack?.typeId !== ITEM) return;
  const now = system.currentTick;
  if (now - (lastOpen.get(player.id) ?? -100) < 10) return;
  lastOpen.set(player.id, now);
  // Sneak + use: stop the music without opening the menu.
  if (player.isSneaking) {
    stopFor(player.id);
    player.onScreenDisplay.setActionBar("§7Música detenida");
    return;
  }
  openMenu(player);
});
"""


def manifests():
    bp = {
        "format_version": 2,
        "header": {"name": ADDON_NAME, "description": "Un objeto para escuchar canciones en cualquier sitio.",
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
        "header": {"name": ADDON_NAME, "description": "Canciones y textura del reproductor de música.",
                   "uuid": UUIDS["rp"], "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUIDS["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUIDS["bp"], "version": VERSION}],
    }
    return bp, rp


LANG = {
    "es": {f"item.{ITEM}.name": "Reproductor de Música", "pack.name": ADDON_NAME,
           "pack.description": "Un objeto para escuchar canciones en cualquier sitio."},
    "en": {f"item.{ITEM}.name": "Music Player", "pack.name": "Music Player",
           "pack.description": "An item to listen to songs anywhere."},
}


def main():
    for pack in (BP, RP):
        shutil.rmtree(pack, ignore_errors=True)

    songs = load_songs()
    for s in songs:
        s["segundos"] = copy_song(s)
        print(f"  {s['nombre']}  ({s['segundos']:.0f} s)")

    tex = icon()
    tex_path = "textures/items/musica/reproductor"
    os.makedirs(os.path.join(RP, os.path.dirname(tex_path)), exist_ok=True)
    tex.save(os.path.join(RP, tex_path + ".png"))
    write(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": NS, "texture_name": "atlas.items",
        "texture_data": {"musica_reproductor": {"textures": tex_path}}})
    write(os.path.join(RP, "sounds/sound_definitions.json"), sound_definitions(songs))

    for code, key in (("es_ES", "es"), ("es_MX", "es"), ("en_US", "en"), ("en_GB", "en")):
        lang = "\n".join(f"{k}={v}" for k, v in LANG[key].items()) + "\n"
        write(os.path.join(RP, f"texts/{code}.lang"), lang)
        write(os.path.join(BP, f"texts/{code}.lang"),
              "\n".join(f"{k}={v}" for k, v in LANG[key].items() if k.startswith("pack.")) + "\n")
    for pack in (BP, RP):
        write(os.path.join(pack, "texts/languages.json"), ["es_ES", "es_MX", "en_US", "en_GB"])

    write(os.path.join(BP, "items/reproductor.json"), item())
    write(os.path.join(BP, "scripts/main.js"), SCRIPT.replace("__ITEM__", ITEM))
    write(os.path.join(BP, "scripts/canciones.js"), songs_js(songs))
    bp, rp = manifests()
    write(os.path.join(BP, "manifest.json"), bp)
    write(os.path.join(RP, "manifest.json"), rp)

    pack_icon = Image.new("RGBA", (128, 128), (30, 20, 44, 255))
    pack_icon.alpha_composite(tex.resize((112, 112), Image.NEAREST), (8, 8))
    for pack in (BP, RP):
        pack_icon.save(os.path.join(pack, "pack_icon.png"))
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    tex.resize((128, 128), Image.NEAREST).save(os.path.join(ROOT, "docs", "music_player_preview.png"))

    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DIST, "MusicPlayer.mcaddon"), "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            for folder, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    z.write(full, os.path.relpath(full, ROOT))
    print("Built", ADDON_NAME, ".".join(map(str, VERSION)), f"({len(songs)} canciones) ->",
          os.path.relpath(DIST, ROOT))


if __name__ == "__main__":
    main()
