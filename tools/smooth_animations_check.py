"""Checks the "Animaciones Suaves" pack without the game, and draws its poses.

    python3 tools/smooth_animations_check.py            # run every check
    python3 tools/smooth_animations_check.py --preview  # also draw docs/smooth_animations_preview.png

Checks:
1. Every Molang expression parses (small Molang parser following the official
   operator precedence), and every query.* / math.* name is in Mojang's list
   (sources/vanilla_player_1.26.60/molang_names.json).
2. Every animation name used by a controller exists in the vanilla player
   entity, every state named by a transition exists, every reused animation
   slot is defined by the pack.
3. The new controllers are simulated in thousands of random situations
   (items, armor, sneaking, riding...): they must always settle in the state
   that matches the situation, without bouncing between states.
4. --preview: evaluates the animations (same "this" / blend weight rules as the
   game) on the vanilla player model and draws front and side views.
"""
import itertools
import json
import math
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "SmoothAnimations_RP")
SRC = os.path.join(ROOT, "sources", "vanilla_player_1.26.60")


# ------------------------------------------------------------------ Molang
class MolangError(Exception):
    pass


TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)f?|('[^']*')|([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)"
                   r"|(\?\?|&&|\|\||==|!=|<=|>=|->|[-+*/!<>?:;,(){}=\[\]]))")
ALIASES = {"q": "query", "v": "variable", "t": "temp", "c": "context"}


def tokenize(s):
    pos, out = 0, []
    s = s.rstrip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise MolangError(f"bad character at {pos}: {s[pos:pos + 20]!r}")
        pos = m.end()
        num, string, ident, op = m.groups()
        if num is not None:
            out.append(("num", float(num)))
        elif string is not None:
            out.append(("str", string[1:-1]))
        elif ident is not None:
            head, _, rest = ident.partition(".")
            head = ALIASES.get(head.lower(), head.lower())
            out.append(("id", head + ("." + rest.lower() if rest else "")))
        else:
            out.append(("op", op))
    return out


class Parser:
    """Builds a tiny AST: ('num', v) ('str', s) ('name', n) ('call', n, args) ('un', op, a)
    ('bin', op, a, b) ('cond', a, b, c) ('set', n, a) ('seq', [stmts]) ('ret', a)."""

    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    def peek(self, v=None):
        if self.i >= len(self.t):
            return None
        tok = self.t[self.i]
        if v is None:
            return tok
        return tok if tok[0] == "op" and tok[1] == v else None

    def take(self, v=None):
        tok = self.peek(v)
        if tok is None:
            raise MolangError(f"expected {v!r} at token {self.i}")
        self.i += 1
        return tok

    def parse(self):
        stmts = self.statements(top=True)
        if self.i != len(self.t):
            raise MolangError(f"unexpected token {self.t[self.i]}")
        return stmts

    def statements(self, top=False):
        stmts, complex_ = [], False
        while self.i < len(self.t) and not self.peek("}"):
            if self.peek(";"):
                self.take(";")
                complex_ = True
                continue
            if self.peek() == ("id", "return"):
                self.take()
                stmts.append(("ret", self.expr()))
            else:
                stmts.append(self.expr())
            if self.peek(";"):
                self.take(";")
                complex_ = True
            elif self.i < len(self.t) and not self.peek("}"):
                raise MolangError(f"missing ';' before token {self.t[self.i]}")
        if not stmts:
            raise MolangError("empty expression")
        if len(stmts) == 1 and not complex_ and stmts[0][0] != "ret":
            return stmts[0]
        return ("seq", stmts)

    def expr(self):
        a = self.cond()
        if self.peek("="):
            if a[0] != "name" or not a[1].startswith(("variable.", "temp.")):
                raise MolangError(f"cannot assign to {a}")
            self.take("=")
            return ("set", a[1], self.expr())
        return a

    def cond(self):  # lowest: ??, then ternary
        a = self.ternary()
        while self.peek("??"):
            self.take()
            a = ("bin", "??", a, self.ternary())
        return a

    def ternary(self):
        a = self.binary(0)
        if self.peek("?"):
            self.take()
            b = self.ternary()
            if self.peek(":"):
                self.take()
                return ("cond", a, b, self.ternary())
            return ("cond", a, b, ("num", 0.0))
        return a

    LEVELS = [["||"], ["&&"], ["==", "!="], ["<", "<=", ">", ">="], ["+", "-"], ["*", "/"]]

    def binary(self, level):
        if level == len(self.LEVELS):
            return self.unary()
        a = self.binary(level + 1)
        while True:
            tok = self.peek()
            if tok and tok[0] == "op" and tok[1] in self.LEVELS[level]:
                self.take()
                a = ("bin", tok[1], a, self.binary(level + 1))
            else:
                return a

    def unary(self):
        if self.peek("!") or self.peek("-"):
            op = self.take()[1]
            return ("un", op, self.unary())
        return self.atom()

    def atom(self):
        tok = self.take()
        if tok[0] == "num":
            return ("num", tok[1])
        if tok[0] == "str":
            return ("str", tok[1])
        if tok == ("op", "("):
            a = self.expr()
            self.take(")")
            return a
        if tok == ("op", "{"):
            body = self.statements()
            self.take("}")
            return body
        if tok[0] == "id":
            name = tok[1]
            if self.peek("("):
                self.take("(")
                args = []
                while not self.peek(")"):
                    args.append(self.expr())
                    if not self.peek(")"):
                        self.take(",")
                self.take(")")
                return ("call", name, args)
            return ("name", name)
        raise MolangError(f"unexpected token {tok}")


_cache = {}


def parse(src):
    if isinstance(src, (int, float)):
        return ("num", float(src))
    if src not in _cache:
        _cache[src] = Parser(src).parse()
    return _cache[src]


def names_in(ast, out):
    if isinstance(ast, tuple):
        if ast[0] in ("name", "call"):
            out.add((ast[0], ast[1], len(ast[2]) if ast[0] == "call" else 0))
        if ast[0] == "set":
            out.add(("set", ast[1], 0))
        for x in ast[1:]:
            if isinstance(x, (tuple, list)):
                names_in(x, out)
    elif isinstance(ast, list):
        for x in ast:
            names_in(x, out)
    return out


class Ret(Exception):
    def __init__(self, v):
        self.v = v


class Env:
    """Values for one evaluation: queries (dict of name -> value or callable), variables, this."""

    def __init__(self, queries, variables, this=0.0, context=None):
        self.q, self.v, self.this, self.ctx = queries, variables, this, context or {}
        self.temp = {}

    def ev(self, ast):
        k = ast[0]
        if k == "num":
            return ast[1]
        if k == "str":
            return ast[1]
        if k == "name":
            n = ast[1]
            if n == "this":
                return self.this
            if n == "math.pi":
                return math.pi
            if n.startswith("query."):
                return self.query(n, [])
            if n.startswith("variable."):
                if n[9:] not in self.v:
                    raise KeyError(n)
                return self.v[n[9:]]
            if n.startswith("temp."):
                return self.temp.get(n[5:], 0.0)
            if n.startswith("context."):
                return self.ctx[n[8:]]
            raise MolangError(f"unknown name {n}")
        if k == "call":
            n, args = ast[1], [self.ev(a) for a in ast[2]]
            if n.startswith("query."):
                return self.query(n, args)
            return MATH[n](*args)
        if k == "un":
            a = self.ev(ast[2])
            return float(not a) if ast[1] == "!" else -a
        if k == "bin":
            op = ast[1]
            if op == "??":
                try:
                    return self.ev(ast[2])
                except KeyError:
                    return self.ev(ast[3])
            if op == "&&":
                return float(bool(self.ev(ast[2])) and bool(self.ev(ast[3])))
            if op == "||":
                return float(bool(self.ev(ast[2])) or bool(self.ev(ast[3])))
            a, b = self.ev(ast[2]), self.ev(ast[3])
            return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b,
                    "/": lambda: a / b if b else 0.0, "<": lambda: float(a < b), "<=": lambda: float(a <= b),
                    ">": lambda: float(a > b), ">=": lambda: float(a >= b), "==": lambda: float(a == b),
                    "!=": lambda: float(a != b)}[op]()
        if k == "cond":
            return self.ev(ast[2]) if self.ev(ast[1]) else self.ev(ast[3])
        if k == "set":
            val = self.ev(ast[2])
            if ast[1].startswith("temp."):
                self.temp[ast[1][5:]] = val
            else:
                self.v[ast[1][9:]] = val
            return val
        if k == "ret":
            raise Ret(self.ev(ast[1]))
        if k == "seq":
            try:
                for s in ast[1]:
                    self.ev(s)
            except Ret as r:
                return r.v
            return 0.0
        raise MolangError(f"bad node {ast}")

    def query(self, n, args):
        val = self.q.get(n[6:], 0.0)
        return val(*args) if callable(val) else val


def _clamp(x, a, b):
    return max(a, min(b, x))


MATH = {
    "math.sin": lambda x: math.sin(math.radians(x)), "math.cos": lambda x: math.cos(math.radians(x)),
    "math.clamp": _clamp, "math.min": min, "math.max": max, "math.abs": abs, "math.sqrt": math.sqrt,
    "math.pow": math.pow, "math.lerp": lambda a, b, t: a + (b - a) * t, "math.mod": math.fmod,
    "math.hermite_blend": lambda t: 3 * t * t - 2 * t ** 3,
}


def evaluate(src, env):
    return env.ev(parse(src)) if isinstance(src, str) else float(src)


# ------------------------------------------------------------------ loading
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.loads(re.sub(r"^\s*//.*$", "", f.read(), flags=re.M))


def load_pack():
    anims = {}
    for f in ("humanoid.animation.json", "player.animation.json", "player_firstperson.animation.json"):
        anims.update(load_json(os.path.join(SRC, f))["animations"])
    for f in sorted(os.listdir(os.path.join(RP, "animations"))):
        anims.update(load_json(os.path.join(RP, "animations", f))["animations"])
    ctrls = load_json(os.path.join(RP, "animation_controllers", "player.animation_controllers.json"))
    entity = load_json(os.path.join(SRC, "player.entity.json"))["minecraft:client_entity"]["description"]
    return anims, ctrls["animation_controllers"], entity


def channel_exprs(anim):
    for bone, chans in anim.get("bones", {}).items():
        for ch, val in chans.items():
            if ch == "relative_to":
                continue
            frames = val.items() if isinstance(val, dict) else [("0", val)]
            for t, fv in frames:
                if isinstance(fv, dict):
                    fv = [x for k in ("pre", "post") if k in fv for x in (fv[k] if isinstance(fv[k], list) else [fv[k]])]
                for x in (fv if isinstance(fv, list) else [fv]):
                    if isinstance(x, str):
                        yield f"{bone}.{ch}@{t}", x


# ------------------------------------------------------------------ static checks
def static_checks():
    import smooth_animations as sa
    names = load_json(os.path.join(SRC, "molang_names.json"))
    queries, maths = set(names["queries"]), set(names["math"])
    anims, ctrls, entity = load_pack()
    errors, exprs = [], []

    for aid, a in anims.items():
        for where, e in channel_exprs(a):
            exprs.append((f"{aid} {where}", e))
    for cid, c in ctrls.items():
        for sname, st in c["states"].items():
            for a in st.get("animations", []):
                if isinstance(a, dict):
                    exprs.append((f"{cid}/{sname} weight", next(iter(a.values()))))
            for tr in st.get("transitions", []):
                (dest, cond), = tr.items()
                exprs.append((f"{cid}/{sname} -> {dest}", cond))
                if dest not in c["states"]:
                    errors.append(f"{cid}/{sname}: transition to missing state {dest}")
            for e in st.get("on_entry", []) + st.get("on_exit", []):
                exprs.append((f"{cid}/{sname} on_entry", e))
            for a in st.get("animations", []):
                key = a if isinstance(a, str) else next(iter(a))
                if key not in entity["animations"]:
                    errors.append(f"{cid}/{sname}: animation {key} is not in the player entity")
        if c["initial_state"] not in c["states"]:
            errors.append(f"{cid}: initial state missing")

    assigned = set()
    for where, e in exprs:
        try:
            ast = parse(e)
        except MolangError as ex:
            errors.append(f"PARSE {where}: {ex}\n    {e}")
            continue
        for kind, n, nargs in names_in(ast, set()):
            if kind == "set":
                assigned.add(n)
            elif n.startswith("query.") and n not in queries:
                errors.append(f"UNKNOWN QUERY {n} in {where}")
            elif n.startswith("math.") and n not in maths:
                errors.append(f"UNKNOWN MATH {n} in {where}")
            elif not n.startswith(("query.", "math.", "variable.", "temp.", "context.", "this")):
                errors.append(f"UNKNOWN NAME {n} in {where}")

    # Variables read by the pack's new expressions must be set by the vanilla entity, by the
    # engine (seen in vanilla files) or by the pack itself.
    vanilla_text = "".join(open(os.path.join(SRC, f)).read() for f in os.listdir(SRC))
    pack_text = json.dumps(ctrls) + json.dumps({k: anims[k] for k in anims})
    for v in sorted(set(re.findall(r"variable\.([a-z_0-9]+)", pack_text, flags=re.I))):
        if v.lower() not in vanilla_text.lower() and f"variable.{v}" not in assigned:
            errors.append(f"variable.{v} is read but never set")

    for slot, short in sa.SLOTS.items():
        target = entity["animations"].get(short)
        if target is None:
            errors.append(f"slot {slot}: {short} not in the player entity")
        elif target.startswith("animation.") and target not in anims:
            errors.append(f"slot {slot}: {target} not defined")
        elif target.startswith("controller.") and target not in ctrls:
            errors.append(f"slot {slot}: {target} not defined")

    # The vanilla-unused slots really are unused by vanilla controllers.
    vanilla_ctrls = open(os.path.join(SRC, "player.animation_controllers.json")).read()
    for short in ("look_at_target_inverted", "first_person_attack_rotation_item", "first_person_crossbow_hold",
                  "base_controller", "hudplayer"):
        if f'"{short}"' in vanilla_ctrls:
            errors.append(f"{short} is used by a vanilla controller")
    print(f"static: {len(exprs)} expressions, {len(ctrls)} controllers, {len(errors)} problems")
    return errors


# ------------------------------------------------------------------ simulation
ITEMS = {  # item -> tags
    "": [], "diamond_sword": ["is_sword"], "iron_spear": ["is_spear"], "mace": [], "trident": [],
    "iron_axe": ["is_axe"], "iron_pickaxe": ["is_pickaxe"], "stone_shovel": ["is_shovel"], "bow": [],
    "crossbow": [], "shield": [], "heavy_core": [], "bread": ["is_food"], "stone": [], "torch": [],
}


def random_world(rng):
    main = rng.choice(list(ITEMS))
    off = rng.choice(["", "", "shield", "torch", "totem_of_undying"])
    armor = [rng.random() < 0.5 for _ in range(4)]
    elytra = rng.random() < 0.3
    b = lambda p=0.5: float(rng.random() < p)
    q = {
        "is_sneaking": b(), "blocking": b(0.3), "is_sleeping": b(0.1), "is_swimming": b(0.1),
        "is_crawling": b(0.1), "is_riding": b(0.3), "is_on_ground": b(0.6), "is_gliding": b(0.1),
        "is_in_water": b(0.1), "is_levitating": b(0.05), "is_spectator": b(0.05),
        "vertical_speed": rng.choice([0.0, -5.0, -12.0, -30.0, 3.0]),
        "item_remaining_use_duration": rng.choice([0.0, 0.0, 0.5]), "item_is_charged": b(0.3),
        "is_item_equipped": lambda slot="main_hand": float(bool(main if slot in ("main_hand", 0) else off)),
        "is_item_name_any": lambda slot, *names: float(
            ("minecraft:" + (main if "mainhand" in slot else off)) in names),
        "equipped_item_any_tag": lambda slot, *tags: float(
            any(t.replace("minecraft:", "") in ITEMS.get(main, []) for t in tags)),
        "has_armor_slot": lambda i: float(armor[int(i)]),
        "armor_texture_slot": lambda i: 5.0 if (int(i) == 1 and elytra) else 1.0,
        "all_animations_finished": 1.0,
        "is_moving": b(), "is_emoting": b(0.05),
        "is_pack_setting_enabled": (lambda name, _s={n: float(rng.random() < 0.2) for n in (
            "sa:no_item_switch", "sa:no_fp_ease", "sa:no_armor", "sa:no_shield_guard",
            "sa:no_glide", "sa:no_idle", "sa:no_death")}: _s[name]),
        "get_pack_setting": lambda name: rng.choice([0.0, 10.0, 30.0]),
    }
    v = {"is_holding_right": float(bool(main)), "is_holding_left": float(bool(off)),
         "item_use_normalized": rng.choice([0.0, 0.0, 0.5, 1.0]), "attack_time": rng.choice([0.0, 0.0, 0.4])}
    return q, v


def settle(ctrl, state, q, v, steps=12):
    path = [state]
    for _ in range(steps):
        st = ctrl["states"][state]
        nxt = None
        for tr in st.get("transitions", []):
            (dest, cond), = tr.items()
            if evaluate(cond, Env(q, v)):
                nxt = dest
                break
        if nxt is None:
            return state, path
        for e in ctrl["states"][nxt].get("on_entry", []):
            evaluate(e, Env(q, v))
        state = nxt
        path.append(state)
    raise AssertionError(f"does not settle: {' -> '.join(path)}")


def simulate(n=20000, seed=1):
    import smooth_animations as sa
    _, ctrls, _ = load_pack()
    rng = random.Random(seed)
    errors = []
    names = {"controller.animation.player.base": "base", "controller.animation.player.hudplayer": "gear",
             "controller.animation.player.crossbow": "armor", "controller.animation.player.melee_spear": "item"}
    state = {cid: ctrls[cid]["initial_state"] for cid in names}
    seen = {cid: set() for cid in names}
    for i in range(n):
        q, v = random_world(rng)
        for cid, short in names.items():
            ctrl = ctrls[cid]
            expect = expected_state(short, q, v, sa)
            for start in (state[cid], ctrl["initial_state"]):
                try:
                    final, path = settle(ctrl, start, q, v)
                except AssertionError as ex:
                    errors.append(f"{short}: {ex}")
                    continue
                if expect is not None and final != expect:
                    errors.append(f"{short}: expected {expect}, got {final} via {path}")
                if short == "armor" and start == state[cid] and start.startswith("w_") and final.startswith("w_"):
                    for i in range(4):
                        if start[2 + i] == "0" and final[2 + i] == "1" and \
                                not any(p.startswith(f"equip_{sa.ARMOR_PARTS[i]}_") for p in path):
                            errors.append(f"armor: {sa.ARMOR_PARTS[i]} put on without animation: {path}")
                        if start[2 + i] == "1" and final[2 + i] == "0" and \
                                not any(p.startswith(f"remove_{sa.ARMOR_PARTS[i]}_") for p in path):
                            errors.append(f"armor: {sa.ARMOR_PARTS[i]} taken off without animation: {path}")
                if short == "item" and start == state[cid] and start.startswith("k_") and \
                        final.startswith("k_") and start.split("_")[1] != final.split("_")[1] and "swap" not in path:
                    errors.append(f"item: changed kind without the switch animation: {path}")
            state[cid] = final
            seen[cid].add(final)
        if len(errors) > 20:
            break
    for cid, short in names.items():
        never = {x for x in set(ctrls[cid]["states"]) - seen[cid]
                 if not x.startswith(("equip_", "remove_", "init", "swap"))}
        print(f"simulate {short}: reached {len(seen[cid])}/{len(ctrls[cid]['states'])} states"
              + (f" (never settled in: {sorted(never)[:8]}...)" if never else ""))
    return errors


def expected_state(short, q, v, sa):
    e = lambda s: evaluate(s, Env(q, v))
    if short == "base":
        on = [n for n, c in (("hold_r", "variable.is_holding_right"), ("sneak", sa.SNEAK_POSE),
                             ("glide", sa.GLIDE), ("idle", sa.IDLE)) if e(c)]
        return "_".join(on) or "default"
    if short == "gear":
        on = []
        if e("query.is_riding"):
            on.append("ride")
        for n, c in [("bow", f"{sa.name_in(sa.MAIN, 'bow')} && variable.item_use_normalized > 0.0 && "
                             "variable.item_use_normalized < 1.0"),
                     ("xbow_charge", f"{sa.CROSSBOW} && query.item_remaining_use_duration > 0.0"),
                     ("xbow_hold", f"{sa.CROSSBOW} && query.item_is_charged")]:
            if e(c):
                on.append(n)
                break
        for n, c in [("guard_off", f"{sa.GUARD} && {sa.SHIELD_OFF}"), ("guard_main", f"{sa.GUARD} && {sa.SHIELD_MAIN}")]:
            if e(c):
                on.append(n)
                break
        return "_".join(on) or "default"
    if short == "armor":
        return "w_" + "".join(str(int(e(f"query.has_armor_slot({i})"))) for i in range(4))
    if short == "item":
        for k, c in sa.ITEM_KINDS:
            if e(c):
                if k == "spear":
                    if v["item_use_normalized"] > 0:
                        return "k_spear_use"
                    return "k_spear_attack" if v["attack_time"] > 0 else "k_spear"
                return f"k_{k}"
    return None


# ------------------------------------------------------------------ pose evaluation and drawing
BONES = {  # name: (parent, pivot, cube origin, cube size)
    "root": (None, (0, 0, 0), None, None),
    "waist": ("root", (0, 12, 0), None, None),
    "body": ("waist", (0, 24, 0), (-4, 12, -2), (8, 12, 4)),
    "head": ("body", (0, 24, 0), (-4, 24, -4), (8, 8, 8)),
    "rightarm": ("body", (-5, 22, 0), (-8, 12, -2), (4, 12, 4)),
    "leftarm": ("body", (5, 22, 0), (4, 12, -2), (4, 12, 4)),
    "rightitem": ("rightarm", (-6, 15, 1), None, None),
    "leftitem": ("leftarm", (6, 15, 1), None, None),
    "rightleg": ("root", (-1.9, 12, 0), (-3.9, 0, -2), (4, 12, 4)),
    "leftleg": ("root", (1.9, 12, 0), (-0.1, 0, -2), (4, 12, 4)),
}


def sample(chan, t, env):
    """Value of a channel at time t (linear between keyframes)."""
    if not isinstance(chan, dict):
        vals = chan if isinstance(chan, list) else [chan] * 3
        return [evaluate(x, env) for x in vals]
    frames = sorted((float(k), v) for k, v in chan.items())

    def val(v):
        if isinstance(v, dict):
            v = v.get("post", v.get("pre"))
        v = v if isinstance(v, list) else [v] * 3
        return [evaluate(x, env) for x in v]
    if t <= frames[0][0]:
        return val(frames[0][1])
    for (t0, v0), (t1, v1) in zip(frames, frames[1:]):
        if t0 <= t <= t1:
            a, b = val(v0), val(v1)
            f = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
            return [x + (y - x) * f for x, y in zip(a, b)]
    return val(frames[-1][1])


def pose(anims, layers, q, v):
    """layers: [(animation id, weight, anim_time)] in play order. Returns bone -> rot/pos/scale."""
    out = {b: {"rotation": [0.0] * 3, "position": [0.0] * 3, "scale": [1.0] * 3} for b in BONES}
    for aid, w, t in layers:
        a = anims[aid]
        for bone, chans in a.get("bones", {}).items():
            bone = bone.lower()
            if bone not in out:
                continue
            if a.get("override_previous_animation") and w > 0:
                for ch in ("rotation", "position"):
                    if ch in chans:
                        out[bone][ch] = [c * (1.0 - w) for c in out[bone][ch]]
            for ch in ("rotation", "position", "scale"):
                if ch not in chans:
                    continue
                cur = out[bone][ch]
                vals = []
                for axis in range(3):
                    env = Env(dict(q, anim_time=t), v, this=cur[axis], context={"player_offhand_arm_height": 1.0})
                    vals.append(sample(chans[ch], t, env)[axis])
                if ch == "scale":
                    out[bone][ch] = [c + (x - 1.0) * w for c, x in zip(cur, vals)]
                else:
                    out[bone][ch] = [c + x * w for c, x in zip(cur, vals)]
    return out


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform(t=(0, 0, 0), rot=(0, 0, 0), s=(1, 1, 1)):
    # Calibrated on vanilla poses: x -90 points an arm forward (-Z), y +28 turns the left arm
    # inward, z -20 moves the left arm outward; applied X, then Y, then Z.
    x, y, z = [math.radians(a) for a in (-rot[0], rot[1], -rot[2])]
    rx = [[1, 0, 0, 0], [0, math.cos(x), -math.sin(x), 0], [0, math.sin(x), math.cos(x), 0], [0, 0, 0, 1]]
    ry = [[math.cos(y), 0, math.sin(y), 0], [0, 1, 0, 0], [-math.sin(y), 0, math.cos(y), 0], [0, 0, 0, 1]]
    rz = [[math.cos(z), -math.sin(z), 0, 0], [math.sin(z), math.cos(z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    m = mat_mul(mat_mul(rz, ry), rx)
    m = mat_mul(m, [[s[0], 0, 0, 0], [0, s[1], 0, 0], [0, 0, s[2], 0], [0, 0, 0, 1]])
    m[0][3], m[1][3], m[2][3] = t
    return m


def world(p):
    mats = {}
    for name, (parent, piv, _, _) in BONES.items():
        b = p[name]
        local = mat_mul(transform(t=[-b["position"][0] + piv[0], b["position"][1] + piv[1], b["position"][2] + piv[2]],
                                  rot=b["rotation"], s=b["scale"]),
                        transform(t=[-piv[0], -piv[1], -piv[2]]))
        mats[name] = mat_mul(mats[parent], local) if parent else local
    return mats


def apply(m, pt):
    x, y, z = pt
    return [m[i][0] * x + m[i][1] * y + m[i][2] * z + m[i][3] for i in range(3)]


def draw_pose(draw, p, ox, oy, view, scale=3.2, item=None, engine_tilt=0.0):
    mats = world(p)
    if engine_tilt:  # the engine tips dying mobs onto their left side (+X), around the feet
        tilt = transform(rot=(0, 0, engine_tilt))
        mats = {k: mat_mul(tilt, m) for k, m in mats.items()}
    faces = []
    colors = {"head": (230, 190, 150), "body": (60, 150, 210), "rightarm": (230, 190, 150),
              "leftarm": (205, 165, 125), "rightleg": (70, 70, 160), "leftleg": (50, 50, 130)}
    for name, (_, _, org, size) in BONES.items():
        if not org:
            continue
        corners = [[org[0] + dx * size[0], org[1] + dy * size[1], org[2] + dz * size[2]]
                   for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]
        pts = [apply(mats[name], c) for c in corners]
        for quad in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
            poly = [pts[i] for i in quad]
            faces.append((name, poly))

    def proj(pt):
        x, y, z = pt
        if view == "front":   # looking at the player's face (from -Z)
            return ox - x * scale, oy - y * scale, z
        return ox + z * scale, oy - y * scale, -x   # side: front of the player to the left... flipped below

    shaded = []
    for name, poly in faces:
        pp = [proj(pt) for pt in poly]
        depth = sum(c[2] for c in pp) / 4
        shaded.append((depth, name, [(c[0], c[1]) for c in pp]))
    for depth, name, pts in sorted(shaded, key=lambda f: -f[0]):
        draw.polygon(pts, fill=colors[name], outline=(30, 30, 30))
    if item:
        m = mats["rightitem"]
        sc = p["rightitem"]["scale"][0]
        base = apply(m, BONES["rightitem"][1])
        tip = apply(m, [BONES["rightitem"][1][0], BONES["rightitem"][1][1] + 0.0, BONES["rightitem"][1][2] - 11 * sc])
        a, b = proj(base), proj(tip)
        draw.line([a[:2], b[:2]], fill=(90, 90, 90), width=4)


def preview(path):
    import smooth_animations as sa
    from PIL import Image, ImageDraw
    anims, _, _ = load_pack()
    base_q = {"target_x_rotation": 0.0, "target_y_rotation": 0.0, "life_time": 1.3, "is_riding": 0.0,
              "is_sneaking": 0.0, "is_item_equipped": 1.0, "item_is_charged": 0.0, "is_swimming": 0.0,
              "cape_flap_amount": 0.0, "is_sleeping": 0.0, "blocking": 0.0, "is_alive": 1.0,
              "modified_move_speed": 0.0, "ground_speed": 0.0, "frame_alpha": 0.0}

    def scene(title, extra, main="", off="", sneaking=False, blocking=False, riding=False, armor=None,
              t=0.0, vars_=None, q_=None, tilt=0.0):
        q = dict(base_q)
        q.update(q_ or {})
        q.update(is_sneaking=float(sneaking), blocking=float(blocking), is_riding=float(riding),
                 is_item_name_any=lambda slot, *n: float(("minecraft:" + (main if "mainhand" in slot else off)) in n),
                 get_root_locator_offset=lambda *a: 0.0, get_default_bone_pivot=lambda *a: 0.0,
                 is_pack_setting_enabled=lambda n: 0.0, get_pack_setting=lambda n: 10.0)
        v = {"tcos0": 0.0, "is_holding_right": float(bool(main)), "is_holding_left": float(bool(off)),
             "attack_time": 0.0, "attack_body_rot_y": 0.0, "sa_equip_part": armor or 0.0, "item_use_normalized": 0.0,
             "is_first_person": 0.0}
        v.update(vars_ or {})
        layers = [("animation.humanoid.base_pose", 1, 0), ("animation.player.move.arms", 1, 0),
                  ("animation.player.move.legs", 1, 0)]
        if riding:
            layers += [("animation.player.riding.arms", 1, 0), ("animation.player.riding.legs", 1, 0)]
        layers += [("animation.player.holding", 1, 0)]
        if main:
            layers += [("animation.player.look_at_target.inverted", 1, 0)]
        layers += [(a, 1, t) for a in extra]
        layers += [("animation.player.bob", 1, 0)]
        return title, pose(anims, layers, q, v), main, tilt

    scenes = [
        scene("Vanilla: de pie", []),
        scene("Vanilla: agachado", ["animation.player.sneaking"], sneaking=True),
        scene("Escudo (2a mano)\n+ agacharse", ["animation.player.shield_block_off_hand"], main="diamond_sword",
              off="shield", sneaking=True, blocking=True),
        scene("Escudo (1a mano)\n+ agacharse", ["animation.player.shield_block_main_hand"], main="shield",
              sneaking=True, blocking=True),
        scene("Cambio de objeto\n(0,1 s)", ["animation.player.attack.positions"], main="diamond_sword", t=0.1),
        scene("Ponerse casco", ["animation.player.first_person.attack_rotation_item"], armor=0, t=0.35),
        scene("Ponerse peto", ["animation.player.first_person.attack_rotation_item"], armor=1, t=0.35),
        scene("Ponerse botas\n(toca el pie)", ["animation.player.first_person.attack_rotation_item"], armor=3, t=0.27),
        scene("Quitarse casco", ["animation.player.first_person.attack_rotation_item"], armor=4, t=0.4),
        scene("Quitarse peto", ["animation.player.first_person.attack_rotation_item"], armor=5, t=0.45),
        scene("Quitarse botas", ["animation.player.first_person.attack_rotation_item"], armor=7, t=0.57),
        scene("Ponerse élitros", ["animation.player.first_person.attack_rotation_item"], armor=8, t=0.4),
        scene("Élitros", ["animation.player.first_person.crossbow_hold"]),
        scene("Espera (quieto\n14 s)", ["animation.player.holding_heavy_core"], t=14.0),
        scene("Tridente\n(cargado)", ["animation.humanoid.brandish_spear"], main="trident",
              vars_={"is_brandishing_spear": 1.0, "charge_amount": 1.0}),
        scene("Muerte (0,4 s)\n(el juego inclina\nal jugador; se\ncompensa)", ["animation.player.sleeping"],
              q_={"is_alive": 0.0, "death_ticks": 8.0, "frame_alpha": 0.0},
              tilt=90.0 * min(1.0, math.sqrt(max(0.0, (8.0 - 1.0) / 20.0 * 1.6)))),
    ]
    cols = 6
    cw, ch = 230, 250
    rows = (len(scenes) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw, rows * ch), (235, 238, 242))
    d = ImageDraw.Draw(img)
    for i, (title, p, item, tilt) in enumerate(scenes):
        x0, y0 = (i % cols) * cw, (i // cols) * ch
        d.rectangle([x0 + 3, y0 + 3, x0 + cw - 3, y0 + ch - 3], outline=(180, 185, 195))
        d.multiline_text((x0 + 10, y0 + 8), title, fill=(20, 20, 20))
        it = item if item in ("diamond_sword", "trident") else None
        draw_pose(d, p, x0 + 62, y0 + 225, "front", item=it, engine_tilt=tilt)
        draw_pose(d, p, x0 + 165, y0 + 225, "side", item=it, engine_tilt=tilt)
    d.text((8, rows * ch - 14), "Izquierda: de frente. Derecha: de lado (mirando a la izquierda).", fill=(60, 60, 60))
    img.save(path)
    print("wrote", path)


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    errors = static_checks() + simulate()
    for e in errors[:60]:
        print("ERROR", e)
    if "--preview" in sys.argv:
        preview(os.path.join(ROOT, "docs", "smooth_animations_preview.png"))
    print("OK" if not errors else f"{len(errors)} problems")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
