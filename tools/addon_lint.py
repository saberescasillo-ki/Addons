"""Checks a Bedrock add-on (a behaviour and a resource pack) for the errors
that make Minecraft reject it or log content errors.

    python3 tools/addon_lint.py BP_folder RP_folder

Checks: manifests (types and UUIDs), JSON syntax, entity events and
component groups, entity ids and loot tables named by entities, spawn rules,
items/blocks custom components against the scripts, client entities and
attachables (models, textures, animations, render controllers, particles,
sounds), item icons, block textures, sounds and texts.
References that are not in the pack are reported only when they use the
pack's own namespace (vanilla ones are provided by the game).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dungeons_mobs import _strip, mentions  # noqa: E402

# Vanilla resources these packs use (the game provides them).
VANILLA = {
    "controller.render.default", "controller.render.fireball", "controller.render.ghast", "controller.render.allay",
    "controller.render.husk", "controller.render.wither_skull", "geometry.wither_skull", "animation.wither_skull.move",
    "animation.actor.billboard", "controller.animation.drowned.attack.rotations", "loot_tables/empty.json",
    "textures/entity/wolf/wolf_angry", "textures/entity/wolf/wolf_tame", "textures/items/soul_lantern",
}
VANILLA_LOOT = re.compile(r"^loot_tables/entities/(wolf|ghast|magma_cube|wither_skeleton|zombie|skeleton|creeper|"
                          r"blaze|piglin|husk|stray|drowned|spider|witch|enderman|vex_gear|zombie_equipment|iron_golem|fish|dolphin|pillager|pillager_raid|warden|polar_bear)\.json$")
# More vanilla names (e.g. from Mojang's bedrock-samples): LINT_VANILLA=path/to/list.json
if os.environ.get("LINT_VANILLA"):
    with open(os.environ["LINT_VANILLA"], encoding="utf-8") as _f:
        VANILLA |= set(json.load(_f))
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
TEXTURE_EXTS = (".png", ".tga", ".jpg", ".jpeg")


class Lint:
    def __init__(self, bp, rp):
        self.bp, self.rp = bp, rp
        self.problems = []
        self.json = {}
        self.namespaces = set()

    def p(self, level, where, msg):
        if any(f"'{v}'" in msg for v in VANILLA) or any(VANILLA_LOOT.match(w.strip("'")) for w in msg.split()):
            return
        self.problems.append((level, where, msg))

    # --- loading
    def load_all(self):
        for root in (self.bp, self.rp):
            for path in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
                rel = os.path.relpath(path, os.path.dirname(root))
                with open(path, encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()
                try:
                    self.json[path] = json.loads(text)
                except ValueError:
                    try:
                        self.json[path] = json.loads(_strip(text))
                        if re.search(r",\s*[\]}]", _strip_comments_only(text)):
                            self.p("aviso", rel, "coma final en JSON (Minecraft suele aceptarla, otros editores no)")
                    except ValueError as e:
                        self.p("ERROR", rel, f"JSON inválido: {e}")

    def jfiles(self, root, folder):
        base = os.path.join(root, folder)
        return [(p, d) for p, d in self.json.items() if p.startswith(base + os.sep)]

    def rel(self, path):
        return os.path.relpath(path, os.path.dirname(self.bp))

    # --- manifests
    def manifests(self):
        uuids = {}
        heads = {}
        for root in (self.bp, self.rp):
            path = os.path.join(root, "manifest.json")
            m = self.json.get(path)
            if not m:
                self.p("ERROR", self.rel(path), "falta manifest.json")
                continue
            fv = m.get("format_version")

            def ver(v, where):
                if fv == 3:
                    ok = isinstance(v, str) and re.fullmatch(r"\d+\.\d+\.\d+([-+].*)?", v)
                else:
                    ok = isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) for x in v)
                if not ok:
                    self.p("ERROR", self.rel(path), f"{where}: versión {v!r} no válida para format_version {fv}")
            h = m.get("header", {})
            ver(h.get("version"), "header.version")
            if "min_engine_version" in h:
                ver(h["min_engine_version"], "min_engine_version")
            heads[root] = h.get("uuid")
            for u, where in [(h.get("uuid"), "header")] + [(mod.get("uuid"), "módulo " + mod.get("type", "?"))
                                                          for mod in m.get("modules", [])]:
                if not u or not UUID.match(u):
                    self.p("ERROR", self.rel(path), f"{where}: UUID no válido {u!r}")
                elif u in uuids:
                    self.p("ERROR", self.rel(path), f"{where}: UUID {u} repetido (también en {uuids[u]})")
                else:
                    uuids[u] = f"{os.path.basename(root)} {where}"
            for mod in m.get("modules", []):
                ver(mod.get("version"), "módulo " + mod.get("type", "?"))
            for d in m.get("dependencies", []):
                if "uuid" in d:
                    ver(d.get("version"), "dependencia " + d["uuid"][:8])
        bp_m = self.json.get(os.path.join(self.bp, "manifest.json"), {})
        if heads.get(self.rp) and not any(d.get("uuid") == heads[self.rp] for d in bp_m.get("dependencies", [])):
            self.p("aviso", "BP manifest", "el BP no depende del RP (hay que activar los dos a mano)")

    # --- behaviour pack
    def index_bp(self):
        self.entities, self.items, self.blocks = {}, {}, {}
        for p, d in self.jfiles(self.bp, "entities"):
            e = d.get("minecraft:entity", {}).get("description", {}).get("identifier")
            if e:
                self.entities[e] = p
        for p, d in self.jfiles(self.bp, "items"):
            i = d.get("minecraft:item", {}).get("description", {}).get("identifier")
            if i:
                self.items[i] = p
        for p, d in self.jfiles(self.bp, "blocks"):
            b = d.get("minecraft:block", {}).get("description", {}).get("identifier")
            if b:
                self.blocks[b] = p
        for i in list(self.entities) + list(self.items) + list(self.blocks):
            ns = i.split(":")[0]
            if ns != "minecraft":
                self.namespaces.add(ns)
        self.bp_anims = {}
        for folder, key in (("animations", "animations"), ("animation_controllers", "animation_controllers")):
            for p, d in self.jfiles(self.bp, folder):
                for k in d.get(key, {}) or {}:
                    self.bp_anims[k] = p
        self.registered = set()
        self.script_text = ""
        for p in glob.glob(os.path.join(self.bp, "scripts", "**", "*.js"), recursive=True):
            with open(p, encoding="utf-8", errors="replace") as f:
                t = f.read()
            self.script_text += t
            self.registered |= set(re.findall(r"registerCustomComponent\(\s*['\"]([^'\"]+)['\"]", t))

    def own(self, ident):
        return isinstance(ident, str) and ident.split(":")[0] in self.namespaces

    def entity_checks(self):
        for ident, p in self.entities.items():
            ent = self.json[p]["minecraft:entity"]
            groups = set(ent.get("component_groups", {}))
            events = set(ent.get("events", {}))
            desc = ent.get("description", {})
            props = set((desc.get("properties") or {}).keys())
            text = json.dumps(ent)
            where = self.rel(p)
            # component groups added/removed
            for g in _all_values(ent.get("events", {}), "component_groups"):
                for name in g if isinstance(g, list) else [g]:
                    if name not in groups:
                        self.p("ERROR", where, f"el evento usa el grupo '{name}', que no existe")
            # events triggered on self
            for ev, target in _event_refs(ent):
                if target in (None, "self") and ev not in events and not ev.startswith("minecraft:"):
                    self.p("ERROR", where, f"se dispara el evento '{ev}', que no existe")
            for m in re.findall(r"/?event entity @s ([A-Za-z0-9_:.#\-]+)", text):
                if m not in events:
                    self.p("aviso", where, f"comando 'event entity @s {m}': ese evento no existe")
            # properties
            for m in set(re.findall(r"(?:q|query)\.property\(\s*'([^']+)'", text)) | \
                    set(k for sp in _all_values(ent, "set_property") if isinstance(sp, dict) for k in sp):
                if m not in props:
                    self.p("ERROR", where, f"usa la propiedad '{m}', que no está declarada")
            # entities summoned / spawned / transformed into / shot
            refs = set(re.findall(r"summon ([a-z0-9_]+:[a-z0-9_.]+)", text))
            refs |= {x.split("<")[0] for x in _all_values(ent, "into") if isinstance(x, str)}
            refs |= {x for x in _all_values(ent, "spawn_entity") if isinstance(x, str)}
            refs |= {x for x in _all_values(ent, "def") if isinstance(x, str)}
            for r in refs:
                if self.own(r) and r not in self.entities:
                    self.p("ERROR", where, f"invoca/transforma en '{r}', que no existe")
            for t in _all_values(ent, "table"):
                if isinstance(t, str) and not os.path.isfile(os.path.join(self.bp, t)) and \
                        os.path.isdir(os.path.join(self.bp, os.path.dirname(t))):
                    self.p("ERROR", where, f"tabla '{t}' no existe")
            for k, v in (desc.get("animations") or {}).items():
                if v not in self.bp_anims and self.own_anim(v):
                    self.p("ERROR", where, f"animación '{v}' no existe en el BP")
            for item in re.findall(r"\"([a-z0-9_]+:[a-z0-9_]+)\"", text):
                pass
        for p, d in self.jfiles(self.bp, "spawn_rules"):
            i = d.get("minecraft:spawn_rules", {}).get("description", {}).get("identifier")
            if i and not i.startswith("minecraft:") and i not in self.entities:
                self.p("ERROR", self.rel(p), f"regla de aparición para '{i}', que no existe")

    def own_anim(self, name):
        return not name.startswith(("animation.humanoid", "animation.player", "controller.animation.humanoid"))

    def item_block_checks(self):
        for kind, table, key in (("objeto", self.items, "minecraft:item"), ("bloque", self.blocks, "minecraft:block")):
            for ident, p in table.items():
                d = self.json[p][key]
                comps = [d.get("components", {})] + [x.get("components", {}) for x in d.get("permutations", [])]
                for c in comps:
                    names = set(c.get("minecraft:custom_components", []))
                    names |= {k for k in c if not k.startswith(("minecraft:", "tag:"))}
                    for n in names:
                        if n not in self.registered:
                            self.p("ERROR", self.rel(p), f"{kind} {ident}: componente '{n}' sin registrar en los scripts")
                    for k in ("minecraft:projectile", "minecraft:shooter"):
                        pe = c.get(k, {}).get("projectile_entity") if isinstance(c.get(k), dict) else None
                        if pe and self.own(pe) and pe not in self.entities:
                            self.p("ERROR", self.rel(p), f"{ident}: proyectil '{pe}' no existe")

    # --- resource pack
    def index_rp(self):
        self.def_words = set()
        self.defs = {}
        for folder in ("models", "animations", "animation_controllers", "render_controllers", "particles"):
            for p, d in self.jfiles(self.rp, folder):
                if not isinstance(d, dict):
                    self.p("ERROR", self.rel(p), "el archivo no es un objeto JSON")
                    continue
                for k in ("animations", "animation_controllers", "render_controllers"):
                    for i in (d.get(k) or {}) if isinstance(d.get(k), dict) else {}:
                        self.defs[i] = p
                if "particle_effect" in d:
                    self.defs[d["particle_effect"]["description"]["identifier"]] = p
                for g in d.get("minecraft:geometry", []) or []:
                    self.defs[g.get("description", {}).get("identifier")] = p
                for k in d:
                    if k.startswith("geometry."):
                        self.defs[k.split(":")[0]] = p
        # words that only the pack's own definitions use (e.g. "netherboss")
        for name in list(self.defs):
            for w in re.split(r"[._:]", name or ""):
                if len(w) > 4 and w not in ("geometry", "animation", "controller", "render", "default"):
                    self.def_words.add(w)
        self.def_words -= {"humanoid", "player", "attack", "skeleton", "zombie", "armor", "rotations",
                           "look_at_target", "base", "move", "riding"}
        sd = self.json.get(os.path.join(self.rp, "sounds", "sound_definitions.json"), {})
        self.sounds = sd.get("sound_definitions", sd) if isinstance(sd, dict) else {}
        it = self.json.get(os.path.join(self.rp, "textures", "item_texture.json"), {})
        self.item_tex = it.get("texture_data", {})
        tt = self.json.get(os.path.join(self.rp, "textures", "terrain_texture.json"), {})
        self.terrain = tt.get("texture_data", {})
        self.client = {}
        for p, d in self.jfiles(self.rp, "entity"):
            i = d.get("minecraft:client_entity", {}).get("description", {}).get("identifier")
            if i:
                self.client.setdefault(i, []).append(p)

    def tex_exists(self, path):
        return any(os.path.isfile(os.path.join(self.rp, path + e)) for e in TEXTURE_EXTS) or \
            os.path.isfile(os.path.join(self.rp, path))

    def pack_texture(self, path):
        """True when the texture should be in this pack (its folder exists here)."""
        return os.path.isdir(os.path.join(self.rp, os.path.dirname(path)))

    def client_checks(self):
        groups = [("entity", "minecraft:client_entity"), ("attachables", "minecraft:attachable")]
        for folder, key in groups:
            for p, d in self.jfiles(self.rp, folder):
                desc = d.get(key, {}).get("description", {})
                where = self.rel(p)
                for t in (desc.get("textures") or {}).values():
                    if not self.tex_exists(t) and self.pack_texture(t):
                        self.p("ERROR", where, f"textura '{t}' no existe")
                for g in (desc.get("geometry") or {}).values():
                    if g not in self.defs and self.own_def(g):
                        self.p("ERROR", where, f"modelo '{g}' no existe")
                anims = desc.get("animations") or {}
                for a in anims.values():
                    if a not in self.defs and self.own_def(a):
                        self.p("ERROR", where, f"animación '{a}' no existe")
                for r in desc.get("render_controllers") or []:
                    r = r if isinstance(r, str) else list(r)[0]
                    if r not in self.defs and self.own_def(r):
                        self.p("ERROR", where, f"render controller '{r}' no existe")
                for v in (desc.get("particle_effects") or {}).values():
                    if v not in self.defs and self.own(v):
                        self.p("ERROR", where, f"partícula '{v}' no existe")
                for v in (desc.get("sound_effects") or {}).values():
                    if v not in self.sounds and self.own_sound(v):
                        self.p("ERROR", where, f"sonido '{v}' no está definido")
                # animate scripts name animations of the entity
                for a in (desc.get("scripts") or {}).get("animate", []) or []:
                    n = a if isinstance(a, str) else list(a)[0]
                    if n not in anims:
                        self.p("ERROR", where, f"scripts.animate usa '{n}', que no está en animations")
                # controllers' states name animations of the entity
                for a in anims.values():
                    ac = self.json.get(self.defs.get(a, ""), {}).get("animation_controllers", {}).get(a)
                    if not ac:
                        continue
                    states = ac.get("states", {})
                    for sname, st in states.items():
                        for an in st.get("animations", []) or []:
                            n = an if isinstance(an, str) else list(an)[0]
                            if n not in anims:
                                self.p("ERROR", where, f"el controlador {a} (estado {sname}) usa '{n}', "
                                                       "que esta entidad no define")
                        for tr in st.get("transitions", []) or []:
                            for target in tr:
                                if target not in states:
                                    self.p("ERROR", self.rel(self.defs[a]), f"{a}: transición a '{target}', estado inexistente")
                        for pe in st.get("particle_effects", []) or []:
                            e = pe.get("effect")
                            if e and e not in (desc.get("particle_effects") or {}):
                                self.p("ERROR", where, f"{a}: efecto de partícula '{e}' no está en particle_effects")
                        for se in st.get("sound_effects", []) or []:
                            e = se.get("effect")
                            if e and e not in (desc.get("sound_effects") or {}):
                                self.p("ERROR", where, f"{a}: efecto de sonido '{e}' no está en sound_effects")
                # animations' timeline effects
                for a in anims.values():
                    an = self.json.get(self.defs.get(a, ""), {}).get("animations", {}).get(a)
                    if not an:
                        continue
                    for kind, field in (("particle_effects", "particle_effects"), ("sound_effects", "sound_effects")):
                        for frame in (an.get(field) or {}).values():
                            for e in frame if isinstance(frame, list) else [frame]:
                                eff = e.get("effect") if isinstance(e, dict) else None
                                if eff and eff not in (desc.get(kind) or {}):
                                    self.p("ERROR", where, f"{a}: '{eff}' no está en {kind} de la entidad")
                if folder == "entity" and desc.get("identifier") and desc["identifier"] not in self.entities \
                        and self.own(desc["identifier"]):
                    self.p("aviso", where, f"entidad de cliente '{desc['identifier']}' sin entidad en el BP")
        for e, p in self.entities.items():
            if self.own(e) and e not in self.client:
                self.p("aviso", self.rel(p), f"'{e}' no tiene entidad de cliente (será invisible)")

    def own_def(self, name):
        """Missing models/animations/controllers are errors only when they look like the pack's
        own (they name one of its namespaces or something it defines); others are the game's."""
        low = name.lower()
        return any(ns.lower() in low for ns in self.namespaces | self.def_words)

    def own_sound(self, name):
        return not re.match(r"^(mob|random|armor|step|dig|fire|ambient|note|block|item|use|game|bucket|liquid|"
                            r"hit|beacon|break|jump|land|fall|ui|camera|damage|bubble|bottle|tile|cauldron)\.", name)

    def item_texture_checks(self):
        for ident, p in self.items.items():
            ic = self.json[p]["minecraft:item"].get("components", {}).get("minecraft:icon")
            key = ic if isinstance(ic, str) else (ic or {}).get("texture") or ((ic or {}).get("textures") or {}).get("default")
            if key and key not in self.item_tex and not key.startswith("textures/"):
                level = "ERROR" if self.own(key) or ":" in key else "aviso"
                self.p(level, self.rel(p), f"icono '{key}' no está en item_texture.json (¿vanilla?)")
        for k, v in self.item_tex.items():
            for t in _strings(v):
                if t.startswith("textures/") and not self.tex_exists(t):
                    self.p("ERROR", "RP item_texture.json", f"'{k}': '{t}' no existe")
        for k, v in self.terrain.items():
            for t in _strings(v):
                if t.startswith("textures/") and not self.tex_exists(t) and self.pack_texture(t):
                    self.p("ERROR", "RP terrain_texture.json", f"'{k}': '{t}' no existe")
        for b, p in self.blocks.items():
            d = self.json[p]["minecraft:block"]
            for mi in _all_values(d, "minecraft:material_instances"):
                for v in mi.values():
                    t = v.get("texture") if isinstance(v, dict) else None
                    if t and t not in self.terrain:
                        self.p("ERROR", self.rel(p), f"textura de bloque '{t}' no está en terrain_texture.json")
            for g in _all_values(d, "minecraft:geometry"):
                g = g if isinstance(g, str) else g.get("identifier")
                if g and not g.startswith("minecraft:") and g not in self.defs:
                    self.p("ERROR", self.rel(p), f"modelo de bloque '{g}' no existe")

    def sound_checks(self):
        for k, v in self.sounds.items():
            for s in v.get("sounds", []) if isinstance(v, dict) else []:
                n = s if isinstance(s, str) else s.get("name")
                if n and not any(os.path.isfile(os.path.join(self.rp, n + e)) for e in (".ogg", ".wav", ".fsb", ".mp3")) \
                        and os.path.isdir(os.path.join(self.rp, os.path.dirname(n))):
                    self.p("ERROR", "RP sound_definitions.json", f"'{k}': falta el archivo '{n}'")
        sj = self.json.get(os.path.join(self.rp, "sounds.json"), {})
        for ent, v in (sj.get("entity_sounds", {}).get("entities", {}) or {}).items():
            for ev, x in (v.get("events", {}) or {}).items():
                n = x if isinstance(x, str) else (x or {}).get("sound")
                if n and n not in self.sounds and self.own_sound(n):
                    self.p("ERROR", "RP sounds.json", f"{ent} {ev}: sonido '{n}' no está definido")
        for m in set(re.findall(r"playSound\(\s*['\"]([^'\"]+)", self.script_text)) | \
                set(re.findall(r"playsound ([A-Za-z0-9_.]+)", self.script_text + "".join(
                    json.dumps(d) for p, d in self.jfiles(self.bp, "entities")))):
            if m not in self.sounds and self.own_sound(m):
                self.p("aviso", "BP", f"se reproduce el sonido '{m}', que no está definido")
        for m in set(re.findall(r"spawnParticle\(\s*['\"]([^'\"]+)", self.script_text)):
            if m not in self.defs and not m.startswith("minecraft:"):
                self.p("ERROR", "BP scripts", f"partícula '{m}' no existe")

    def text_checks(self):
        langs = glob.glob(os.path.join(self.rp, "texts", "*.lang"))
        keys = set()
        for p in langs:
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                keys |= {line.split("=", 1)[0].strip() for line in f if "=" in line and not line.startswith("#")}
        for e, p in self.entities.items():
            spawnable = self.json[p]["minecraft:entity"]["description"].get("is_spawnable")
            if self.own(e) and spawnable and f"entity.{e}.name" not in keys:
                self.p("aviso", "RP texts", f"falta el nombre de '{e}' (sale el ID en pantalla)")

    def run(self):
        self.load_all()
        self.manifests()
        self.index_bp()
        self.entity_checks()
        self.item_block_checks()
        self.index_rp()
        self.client_checks()
        self.item_texture_checks()
        self.sound_checks()
        self.text_checks()
        return self.problems


def _strip_comments_only(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def _all_values(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from _all_values(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_values(v, key)


def _event_refs(ent):
    """(event, target) for every place an entity fires one of its events."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            ev = o.get("event")
            if isinstance(ev, str):
                out.append((ev, o.get("target")))
            if isinstance(o.get("trigger"), str):
                out.append((o["trigger"], "self"))
            elif isinstance(o.get("trigger"), dict) and isinstance(o["trigger"].get("event"), str):
                out.append((o["trigger"]["event"], o["trigger"].get("target", "self")))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(ent.get("components", {}))
    walk(ent.get("component_groups", {}))
    walk(ent.get("events", {}))
    return out


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    problems = Lint(sys.argv[1], sys.argv[2]).run()
    seen = set()
    for level, where, msg in sorted(problems, key=lambda x: (x[0] != "ERROR", x[1])):
        if (level, where, msg) in seen:
            continue
        seen.add((level, where, msg))
        print(f"[{level}] {where}: {msg}")
    print(f"-- {sum(1 for x in seen if x[0] == 'ERROR')} errores, {sum(1 for x in seen if x[0] != 'ERROR')} avisos")


if __name__ == "__main__":
    main()
