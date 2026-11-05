"""Old (pre 1.19.50) command syntax -> current syntax.

  * execute <target> <x y z> [detect <x y z> <block> <data>] <command>
      -> execute as <target> at @s [positioned <x y z>] [if block <x y z> <block>] run <command>
  * block data values in fill / setblock (removed in 1.19.70+) are dropped.
"""
import re

COORD = re.compile(r"\s*([~^](?:-?\d*\.?\d+)?|-?\d*\.?\d+)")
SELECTOR = re.compile(r"\s*(@[aeprsvc](?:\[[^\]]*\])?|\"[^\"]+\"|[A-Za-z0-9_.\-]+)")


def _coords(text, pos):
    """Three coordinates from text[pos:] (they may be glued: ~~~, ^^^1). -> (list, pos) or None."""
    out = []
    for _ in range(3):
        m = COORD.match(text, pos)
        if not m or not m.group(1):
            return None
        out.append(m.group(1))
        pos = m.end()
    return out, pos


def _is_zero(c):
    return c in ("~", "^", "~0", "^0", "~0.0", "^0.0")


def convert(cmd):
    cmd = cmd.strip()
    lead = "/" if cmd.startswith("/") else ""
    body = cmd[1:] if lead else cmd
    return lead + _convert(body)


def _convert(cmd):
    if re.match(r"execute\s+(as|at|if|unless|positioned|align|anchored|in|facing|rotated|run)\b", cmd):
        return cmd  # already new syntax
    m = re.match(r"execute\b", cmd)
    if m:
        sel = SELECTOR.match(cmd, m.end())
        if sel:
            got = _coords(cmd, sel.end())
            if got:
                coords, pos = got
                parts = [f"execute as {sel.group(1)} at @s"]
                if not all(_is_zero(c) for c in coords):
                    parts.append("positioned " + " ".join(coords))
                rest = cmd[pos:].lstrip()
                d = re.match(r"detect\b", rest)
                if d:
                    got2 = _coords(rest, d.end())
                    if got2:
                        bcoords, p2 = got2
                        bm = re.match(r"\s*(\S+)\s+(-?\d+)\s*", rest[p2:])
                        if bm:
                            block, data = bm.group(1), int(bm.group(2))
                            parts.append(f"if block {' '.join(bcoords)} {block}")
                            rest = rest[p2 + bm.end():]
                return " ".join(parts) + " run " + _convert(rest.strip())
        return cmd
    return _data_values(cmd)


def _data_values(cmd):
    m = re.match(r"(fill|setblock)\b", cmd)
    if not m:
        return cmd
    n = 2 if m.group(1) == "fill" else 1
    pos = m.end()
    for _ in range(n):
        got = _coords(cmd, pos)
        if not got:
            return cmd
        pos = got[1]
    rest = cmd[pos:].split()
    if not rest:
        return cmd
    out = [rest[0]]                  # block
    i = 1
    if i < len(rest) and re.fullmatch(r"-?\d+", rest[i]):
        i += 1                       # its data value
    if i < len(rest):
        out.append(rest[i])          # mode
        if rest[i] == "replace" and i + 1 < len(rest):
            out.append(rest[i + 1])  # the block to replace
            if i + 2 < len(rest) and re.fullmatch(r"-?\d+", rest[i + 2]):
                i += 1               # its data value
            i += 1
        out += rest[i + 1:]
    return cmd[:pos].rstrip() + " " + " ".join(out)


if __name__ == "__main__":
    tests = {
        "execute @e[type=mo:x,r=3] ^^^1 fill ~ ~ ~ ~ ~2 ~ fire 0 replace air":
            "execute as @e[type=mo:x,r=3] at @s positioned ^ ^ ^1 run fill ~ ~ ~ ~ ~2 ~ fire replace air",
        "execute @s ~ ~ ~ execute @p ~1 ~ ~ say hi": "execute as @s at @s run execute as @p at @s positioned ~1 ~ ~ run say hi",
        "execute @a ~ ~ ~ detect ~ ~-1 ~ stone 0 say on stone": "execute as @a at @s if block ~ ~-1 ~ stone run say on stone",
        "fill ~0 ~ ~0 ~0 ~1 ~0 mo:bleached 0 replace grass": "fill ~0 ~ ~0 ~0 ~1 ~0 mo:bleached replace grass",
        "setblock ~ ~ ~ air": "setblock ~ ~ ~ air",
        "setblock ~ ~1 ~ stone 0 destroy": "setblock ~ ~1 ~ stone destroy",
        "fill ~ ~ ~ ~ ~ ~ air 0 replace stone 0": "fill ~ ~ ~ ~ ~ ~ air replace stone",
        "/execute @s ~~~ particle a ~~~": "/execute as @s at @s run particle a ~~~",
        "give @s mo:x 1 0": "give @s mo:x 1 0",
        "execute as @a at @s run say ok": "execute as @a at @s run say ok",
    }
    bad = 0
    for src, want in tests.items():
        got = convert(src)
        if got != want:
            bad += 1
            print("FAIL", src, "\n  got ", got, "\n  want", want)
    print("ok" if not bad else f"{bad} fallos")
