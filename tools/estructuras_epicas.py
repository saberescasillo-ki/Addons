#!/usr/bin/env python3
"""Estructuras Épicas — versiones mejoradas de las estructuras vanilla, estilo "When Dungeons Arise".

Genera:
  EstructurasEpicas_BP/  (estructuras .mcstructure, worldgen jigsaw, loot tables, bloque trial spawner y script)
  EstructurasEpicas_RP/  (texturas/sonido del bloque, textos)
  dist/EstructurasEpicas.mcaddon

Todo se construye por código (no usa estructuras de otros mods). Uso:  python3 tools/estructuras_epicas.py
"""
import io, json, os, random, shutil, struct, uuid, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, 'EstructurasEpicas_BP')
RP = os.path.join(ROOT, 'EstructurasEpicas_RP')
DIST = os.path.join(ROOT, 'dist', 'EstructurasEpicas.mcaddon')
NS = 'epicas'
FMT_WG = '1.21.20'
VERSION = [1, 0, 0]
# UUIDs fijos para que las actualizaciones reemplacen al pack anterior
UUIDS = {
    'bp': 'a3c6d1e2-5b7f-4c38-9e21-7f0d4b6a8c11', 'bp_data': 'b8e2f4a1-3c5d-4e6f-8a7b-9c0d1e2f3a41',
    'bp_script': 'c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e51', 'rp': 'd4e5f6a7-b8c9-4dae-bf01-2c3d4e5f6a61',
    'rp_res': 'e7f8a9b0-c1d2-4e3f-a4b5-c6d7e8f9a071',
}

SPEC = json.load(open(os.path.join(ROOT, 'tools', 'data', 'bedrock_blocks.json')))
BLOCK_VERSION = SPEC['version']
BLOCKS = SPEC['blocks']

# ============================================================== NBT (little endian)
END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BARR, STR, LIST, COMP = range(11)

class Tag:
    __slots__ = ('t', 'v')
    def __init__(self, t, v): self.t, self.v = t, v

def tB(v): return Tag(BYTE, int(v))
def tS(v): return Tag(SHORT, int(v))
def tI(v): return Tag(INT, int(v))
def tL(v): return Tag(LONG, int(v))
def tF(v): return Tag(FLOAT, float(v))
def tStr(v): return Tag(STR, str(v))
def tC(d): return Tag(COMP, d)
def tList(et, items): return Tag(LIST, (et, items))

def _w(buf, t, v):
    p = lambda f, *a: buf.write(struct.pack('<' + f, *a))
    if t == BYTE: p('b', v)
    elif t == SHORT: p('h', v)
    elif t == INT: p('i', v)
    elif t == LONG: p('q', v)
    elif t == FLOAT: p('f', v)
    elif t == DOUBLE: p('d', v)
    elif t == STR:
        e = v.encode('utf-8'); p('H', len(e)); buf.write(e)
    elif t == LIST:
        et, items = v; p('b', et); p('i', len(items))
        if et == INT: buf.write(struct.pack(f'<{len(items)}i', *items))
        elif et == FLOAT: buf.write(struct.pack(f'<{len(items)}f', *items))
        else:
            for it in items: _w(buf, et, it)
    elif t == COMP:
        for k, x in v.items():
            p('b', x.t); _w(buf, STR, k); _w(buf, x.t, x.v)
        p('b', END)
    else: raise ValueError(t)

def nbt_bytes(root):
    buf = io.BytesIO(); buf.write(struct.pack('<b', COMP)); _w(buf, STR, ''); _w(buf, COMP, root.v)
    return buf.getvalue()

def py_to_tag(v):
    """dict/list/int/float/str -> Tag (ints become INT, bool -> BYTE)."""
    if isinstance(v, Tag): return v
    if isinstance(v, bool): return tB(v)
    if isinstance(v, int): return tI(v)
    if isinstance(v, float): return tF(v)
    if isinstance(v, str): return tStr(v)
    if isinstance(v, dict): return tC({k: py_to_tag(x) for k, x in v.items()})
    if isinstance(v, list):
        items = [py_to_tag(x) for x in v]
        et = items[0].t if items else COMP
        return tList(et, [i.v for i in items])
    raise TypeError(type(v))

# ============================================================== blocks
class Blk:
    __slots__ = ('name', 'states', 'key', 'be')
    def __init__(self, name, states, be=None):
        self.name, self.states, self.be = name, states, be
        self.key = (name, tuple(sorted((k, v[0], v[1]) for k, v in states.items())))

_bcache = {}
def B(name, **st):
    """Bedrock block with every state filled (validated against tools/data/bedrock_blocks.json)."""
    name = name if ':' in name else 'minecraft:' + name
    key = (name, tuple(sorted(st.items())))
    if key in _bcache: return _bcache[key]
    if name.startswith(NS + ':'):
        states = {k: ('i', v) for k, v in st.items()}
    else:
        spec = BLOCKS.get(name)
        if spec is None: raise KeyError(f'bloque desconocido: {name}')
        states = {}
        for k, info in spec.items():
            typ, dv = info['default']
            states[k] = (typ, dv)
        for k, v in st.items():
            k2 = 'minecraft:' + k if ('minecraft:' + k) in spec and k not in spec else k
            if k2 not in spec: raise KeyError(f'{name}: estado desconocido {k}')
            if v not in spec[k2]['values'] and (int(v) if isinstance(v, bool) else v) not in spec[k2]['values']:
                raise ValueError(f'{name}: {k}={v} no válido ({spec[k2]["values"]})')
            states[k2] = (spec[k2]['default'][0], int(v) if isinstance(v, bool) else v)
    b = Blk(name, states)
    _bcache[key] = b
    return b

# direcciones
STAIR_DIR = {'east': 0, 'west': 1, 'south': 2, 'north': 3}
FACE6 = {'down': 0, 'up': 1, 'north': 2, 'south': 3, 'west': 4, 'east': 5}
DOOR_DIR = {'north': 'east', 'south': 'west', 'east': 'south', 'west': 'north'}
BED_DIR = {'south': 0, 'west': 1, 'north': 2, 'east': 3}
TRAP_DIR = {'east': 0, 'west': 1, 'south': 2, 'north': 3}
OPP = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}
VEC = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}
VINE_BITS = {'south': 1, 'west': 2, 'north': 4, 'east': 8}
DYES = ['white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime', 'pink', 'gray', 'light_gray', 'cyan',
        'purple', 'blue', 'brown', 'green', 'red', 'black']

def stairs(mat, facing, top=False): return B(f'{mat}_stairs', weirdo_direction=STAIR_DIR[facing], upside_down_bit=top)
def slab(mat, top=False): return B(f'{mat}_slab', vertical_half='top' if top else 'bottom')
def log(mat, axis='y'): return B(mat, pillar_axis=axis)
def lantern(hanging=False, soul=False): return B('soul_lantern' if soul else 'lantern', hanging=hanging)
def leaves(kind): return B(f'{kind}_leaves', persistent_bit=True)
def wall(mat): return B(f'{mat}_wall', wall_post_bit=True)
def trapdoor(mat, facing, open_=False, top=False):
    return B(f'{mat}_trapdoor' if mat != 'oak' else 'trapdoor', direction=TRAP_DIR[facing], open_bit=open_, upside_down_bit=top)

AIR = B('air')
WATER = B('water', liquid_depth=0)

# ============================================================== structure builder
class Build:
    def __init__(self, sx, sy, sz):
        self.sx, self.sy, self.sz = sx, sy, sz
        self.blocks = {}
        self.ents = []

    def inb(self, x, y, z): return 0 <= x < self.sx and 0 <= y < self.sy and 0 <= z < self.sz

    def set(self, x, y, z, b, be=None):
        if not self.inb(x, y, z): return
        if b is None: self.blocks.pop((x, y, z), None); return
        self.blocks[(x, y, z)] = (b, be)

    def get(self, x, y, z):
        v = self.blocks.get((x, y, z)); return v[0] if v else None

    def fill(self, x0, y0, z0, x1, y1, z1, b):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.set(x, y, z, b)

    def walls(self, x0, y0, z0, x1, y1, z1, b):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, z0, b); self.set(x, y, z1, b)
            for z in range(z0, z1 + 1):
                self.set(x0, y, z, b); self.set(x1, y, z, b)

    def mix(self, x0, y0, z0, x1, y1, z1, rng, choices, only_existing=False):
        """Rellena eligiendo al azar entre [(bloque, peso)]."""
        tot = sum(w for _, w in choices)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if only_existing and (x, y, z) not in self.blocks: continue
                    r = rng.uniform(0, tot)
                    for b, w in choices:
                        r -= w
                        if r <= 0: self.set(x, y, z, b); break

    def replace(self, frm, to_choices, rng, prob=1.0):
        """Reemplaza bloques de nombre `frm` (con probabilidad) por uno de to_choices."""
        for p, (b, be) in list(self.blocks.items()):
            if b.name == frm and rng.random() < prob:
                self.blocks[p] = (rng.choice(to_choices), be)

    # ---- objetos con block entity
    def chest(self, x, y, z, facing, loot):
        self.set(x, y, z, B('chest', cardinal_direction=facing),
                 {'id': 'Chest', 'LootTable': f'loot_tables/{NS}/{loot}.json', 'Findable': tB(0), 'Items': []})

    def barrel(self, x, y, z, loot=None):
        be = {'id': 'Barrel', 'Findable': tB(0), 'Items': []}
        if loot: be['LootTable'] = f'loot_tables/{NS}/{loot}.json'
        self.set(x, y, z, B('barrel', facing_direction=1, open_bit=False), be)

    def banner(self, x, y, z, facing, color):
        self.set(x, y, z, B('wall_banner', facing_direction=FACE6[facing]),
                 {'id': 'Banner', 'Base': tI(15 - DYES.index(color)), 'Type': tI(0), 'Patterns': []})

    def bed(self, x, z, y, facing, color='red'):
        """Cama: (x,z) = pie, cabecera hacia `facing`."""
        dx, dz = VEC[facing]
        be = {'id': 'Bed', 'color': tB(DYES.index(color))}
        self.set(x, y, z, B('bed', direction=BED_DIR[facing], head_piece_bit=False), dict(be))
        self.set(x + dx, y, z + dz, B('bed', direction=BED_DIR[facing], head_piece_bit=True), dict(be))

    def door(self, x, y, z, facing, mat='oak', hinge=False):
        name = 'wooden_door' if mat == 'oak' else f'{mat}_door'
        d = DOOR_DIR[facing]
        self.set(x, y, z, B(name, cardinal_direction=d, upper_block_bit=False, door_hinge_bit=hinge))
        self.set(x, y + 1, z, B(name, cardinal_direction=d, upper_block_bit=True, door_hinge_bit=hinge))

    def skull(self, x, y, z, kind='skeleton_skull'):
        self.set(x, y, z, B(kind, facing_direction=1), {'id': 'Skull', 'SkullType': tB(0), 'Rotation': tF(0.0)})

    def spawner(self, x, y, z, config):
        """Trial spawner propio (ver scripts/main.js). config = índice en SPAWNERS."""
        self.set(x, y, z, B(f'{NS}:trial_spawner', **{f'{NS}:config': SPAWNER_INDEX[config], f'{NS}:fase': 0}))

    def simple_be(self, x, y, z, b, be_id, **extra):
        d = {'id': be_id}; d.update(extra)
        self.set(x, y, z, b, d)

    def mob(self, x, y, z, ident, **extra):
        self.ents.append((ident, (x + 0.5, y, z + 0.5), extra))

    # ---- salida
    def save(self, path):
        sx, sy, sz = self.sx, self.sy, self.sz
        total = sx * sy * sz
        l0 = [-1] * total; l1 = [-1] * total
        pal, idx = [], {}
        posdata = {}
        def pi(b):
            if b.key not in idx: idx[b.key] = len(pal); pal.append(b)
            return idx[b.key]
        WATERLOGGABLE = ('_stairs', '_slab', '_fence', '_wall', 'iron_bars', 'glass_pane', 'lantern', 'chest')
        for (x, y, z), (b, be) in self.blocks.items():
            i = (x * sy + y) * sz + z
            l0[i] = pi(b)
            if b.name.startswith(NS + ':water_'):  # no usado
                pass
            if be is not None:
                d = {k: py_to_tag(v) for k, v in be.items()}
                d['x'] = tI(x); d['y'] = tI(y); d['z'] = tI(z); d['isMovable'] = tB(1)
                posdata[str(i)] = tC({'block_entity_data': tC(d)})
        ents = []
        for n, (ident, pos, extra) in enumerate(self.ents):
            d = {'identifier': tStr(ident), 'definitions': tList(STR, ['+' + ident] + extra.pop('defs', [])),
                 'Pos': tList(FLOAT, list(pos)), 'Rotation': tList(FLOAT, [random.uniform(0, 360), 0.0]),
                 'Motion': tList(FLOAT, [0.0, 0.0, 0.0]), 'UniqueID': tL(-(10_000_000 + n + len(path))),
                 'Persistent': tB(1), 'OnGround': tB(1), 'Tags': tList(STR, [])}
            for k, v in extra.items(): d[k] = py_to_tag(v)
            ents.append(tC(d).v)
        bpal = [tC({'name': tStr(b.name), 'states': tC({k: Tag({'b': BYTE, 'i': INT, 's': STR}[t], v) for k, (t, v) in b.states.items()}),
                    'version': tI(BLOCK_VERSION)}).v for b in pal]
        root = tC({
            'format_version': tI(1),
            'size': tList(INT, [sx, sy, sz]),
            'structure': tC({
                'block_indices': tList(LIST, [(INT, l0), (INT, l1)]),
                'entities': tList(COMP, ents),
                'palette': tC({'default': tC({'block_palette': tList(COMP, bpal), 'block_position_data': tC(posdata)})}),
            }),
            'structure_world_origin': tList(INT, [0, 0, 0]),
        })
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f: f.write(nbt_bytes(root))
        return len(self.blocks)

# ============================================================== componentes de construcción
def foundation(b, x0, z0, x1, z1, top_y, depth, mat_top, mat_fill):
    """Cimientos: capa superior en top_y y relleno hacia abajo (para que no flote en terreno irregular)."""
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            b.set(x, top_y, z, mat_top)
            for y in range(top_y - depth, top_y):
                b.set(x, y, z, mat_fill)

def clear(b, x0, y0, z0, x1, y1, z1):
    b.fill(x0, y0, z0, x1, y1, z1, AIR)

def gable_roof(b, x0, z0, x1, z1, y, mat, axis, overhang=1, fill=None, trim=None):
    """Techo a dos aguas con escaleras. axis='x' = cumbrera a lo largo de X."""
    x0 -= overhang; x1 += overhang; z0 -= overhang; z1 += overhang
    if axis == 'x':
        lo, hi = z0, z1
        layer = 0
        while lo <= hi:
            yy = y + layer
            for x in range(x0, x1 + 1):
                if lo == hi:
                    b.set(x, yy, lo, slab(mat) if fill is None else fill)
                else:
                    b.set(x, yy, lo, stairs(mat, 'south'))
                    b.set(x, yy, hi, stairs(mat, 'north'))
            # hastiales (relleno de las paredes laterales)
            if fill is not None:
                for z in range(lo + 1, hi):
                    b.set(x0 + overhang, yy, z, fill); b.set(x1 - overhang, yy, z, fill)
            if trim is not None:
                b.set(x0, yy, lo, stairs(trim, 'south')); b.set(x0, yy, hi, stairs(trim, 'north'))
                b.set(x1, yy, lo, stairs(trim, 'south')); b.set(x1, yy, hi, stairs(trim, 'north'))
            lo += 1; hi -= 1; layer += 1
        return y + layer
    else:
        lo, hi = x0, x1
        layer = 0
        while lo <= hi:
            yy = y + layer
            for z in range(z0, z1 + 1):
                if lo == hi:
                    b.set(lo, yy, z, slab(mat) if fill is None else fill)
                else:
                    b.set(lo, yy, z, stairs(mat, 'east'))
                    b.set(hi, yy, z, stairs(mat, 'west'))
            if fill is not None:
                for x in range(lo + 1, hi):
                    b.set(x, yy, z0 + overhang, fill); b.set(x, yy, z1 - overhang, fill)
            if trim is not None:
                b.set(lo, yy, z0, stairs(trim, 'east')); b.set(hi, yy, z0, stairs(trim, 'west'))
                b.set(lo, yy, z1, stairs(trim, 'east')); b.set(hi, yy, z1, stairs(trim, 'west'))
            lo += 1; hi -= 1; layer += 1
        return y + layer

def hip_roof(b, x0, z0, x1, z1, y, mat, overhang=1, cap=None):
    """Techo a cuatro aguas (pirámide escalonada de escaleras)."""
    x0 -= overhang; x1 += overhang; z0 -= overhang; z1 += overhang
    layer = 0
    while x0 <= x1 and z0 <= z1:
        yy = y + layer
        if x0 == x1 or z0 == z1:
            b.fill(x0, yy, z0, x1, yy, z1, slab(mat) if cap is None else cap); break
        for x in range(x0, x1 + 1):
            b.set(x, yy, z0, stairs(mat, 'south')); b.set(x, yy, z1, stairs(mat, 'north'))
        for z in range(z0 + 1, z1):
            b.set(x0, yy, z, stairs(mat, 'east')); b.set(x1, yy, z, stairs(mat, 'west'))
        x0 += 1; x1 -= 1; z0 += 1; z1 -= 1; layer += 1
    return y + layer

def crenellate(b, x0, z0, x1, z1, y, blk, step=2):
    """Almenas en el perímetro."""
    i = 0
    for x in range(x0, x1 + 1):
        if i % step == 0: b.set(x, y, z0, blk); b.set(x, y, z1, blk)
        i += 1
    i = 0
    for z in range(z0, z1 + 1):
        if i % step == 0: b.set(x0, y, z, blk); b.set(x1, y, z, blk)
        i += 1

def windows(b, x0, z0, x1, z1, y, h, pane, every=3, skip=None):
    """Ventanas en las cuatro paredes (cada `every` bloques, sin esquinas)."""
    skip = skip or set()
    for x in range(x0 + 2, x1 - 1, every):
        for yy in range(y, y + h):
            if (x, z0) not in skip: b.set(x, yy, z0, pane)
            if (x, z1) not in skip: b.set(x, yy, z1, pane)
    for z in range(z0 + 2, z1 - 1, every):
        for yy in range(y, y + h):
            if (x0, z) not in skip: b.set(x0, yy, z, pane)
            if (x1, z) not in skip: b.set(x1, yy, z, pane)

def timber_house(b, rng, x0, y0, z0, w, d, floors, pal, door_side='south', roof_axis=None, inside='house'):
    """Casa de entramado estilo WDA: zócalo de piedra, postes de tronco, paredes, ventanas, techo a dos aguas
    y muebles. Devuelve la altura del techo."""
    x1, z1 = x0 + w - 1, z0 + d - 1
    fh = 4  # alto por piso
    # zócalo y suelo
    b.fill(x0, y0, z0, x1, y0, z1, pal['base'])
    top = y0 + floors * fh
    clear(b, x0 + 1, y0 + 1, z0 + 1, x1 - 1, top, z1 - 1)
    b.walls(x0, y0 + 1, z0, x1, y0 + 1, z1, pal['base'])
    b.walls(x0, y0 + 2, z0, x1, top, z1, pal['wall'])
    for f in range(floors):
        fy = y0 + f * fh
        if f > 0:
            b.fill(x0 + 1, fy, z0 + 1, x1 - 1, fy, z1 - 1, pal['floor'])
            b.walls(x0, fy, z0, x1, fy, z1, log(pal['log'], 'x'))
            for z in range(z0, z1 + 1):
                b.set(x0, fy, z, log(pal['log'], 'z')); b.set(x1, fy, z, log(pal['log'], 'z'))
        windows(b, x0, z0, x1, z1, fy + 2, 2 if f == 0 else 2, pal['pane'], every=3)
    b.fill(x0 + 1, y0, z0 + 1, x1 - 1, y0, z1 - 1, pal['floor'])
    # vigas superiores y postes
    for x in range(x0, x1 + 1):
        b.set(x, top, z0, log(pal['log'], 'x')); b.set(x, top, z1, log(pal['log'], 'x'))
    for z in range(z0, z1 + 1):
        b.set(x0, top, z, log(pal['log'], 'z')); b.set(x1, top, z, log(pal['log'], 'z'))
    for (x, z) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        b.fill(x, y0 + 1, z, x, top, z, log(pal['log']))
    # techo interior
    b.fill(x0 + 1, top, z0 + 1, x1 - 1, top, z1 - 1, pal['floor'])
    # puerta
    if door_side in ('south', 'north'):
        dx, dz = (x0 + x1) // 2, (z1 if door_side == 'south' else z0)
    else:
        dx, dz = (x1 if door_side == 'east' else x0), (z0 + z1) // 2
    b.door(dx, y0 + 1, dz, door_side, pal['door'])
    ox, oz = VEC[door_side]
    b.set(dx + ox, y0, dz + oz, pal['step'])
    b.set(dx + ox, y0 + 1, dz + oz, AIR); b.set(dx + ox, y0 + 2, dz + oz, AIR)
    # lámparas exteriores
    for side in (-1, 1):
        lx, lz = (dx + side, dz + oz) if door_side in ('south', 'north') else (dx + ox, dz + side)
        b.set(lx, y0 + 3, lz, lantern(hanging=False)) if b.get(lx, y0 + 2, lz) is None else None
    # techo
    axis = roof_axis or ('x' if w >= d else 'z')
    ry = gable_roof(b, x0, z0, x1, z1, top + 1, pal['roof'], axis, overhang=1, fill=pal['gable'])
    # escalera interior entre pisos
    if floors > 1:
        lx, lz = x1 - 1, z1 - 1 if door_side != 'south' else z0 + 1
        for f in range(floors - 1):
            for yy in range(y0 + f * fh + 1, y0 + (f + 1) * fh + 1):
                b.set(lx, yy, lz, B('ladder', facing_direction=FACE6['west']))
    furnish(b, rng, x0 + 1, y0 + 1, z0 + 1, x1 - 1, z1 - 1, inside, pal, door=(dx, dz))
    if floors > 1:
        furnish(b, rng, x0 + 1, y0 + fh + 1, z0 + 1, x1 - 1, z1 - 1, 'bedroom', pal, door=None)
    return ry

def furnish(b, rng, x0, y, z0, x1, z1, kind, pal, door=None):
    """Muebles a lo largo de las paredes interiores, evitando la puerta."""
    spots = []
    for x in range(x0, x1 + 1):
        spots += [(x, z0, 'south'), (x, z1, 'north')]
    for z in range(z0 + 1, z1):
        spots += [(x0, z, 'east'), (x1, z, 'west')]
    if door:
        spots = [s for s in spots if abs(s[0] - door[0]) + abs(s[1] - door[1]) > 1]
    rng.shuffle(spots)
    sets = {
        'house': [('bed',), ('crafting_table',), ('barrel', 'casa'), ('furnace',), ('chest', 'casa'), ('lantern',), ('pot',), ('bookshelf',), ('cauldron',)],
        'bedroom': [('bed',), ('bed',), ('chest', 'casa'), ('bookshelf',), ('lantern',), ('barrel', None), ('pot',)],
        'smith': [('anvil',), ('blast_furnace',), ('smithing_table',), ('chest', 'herreria'), ('barrel', 'herreria'), ('lava_cauldron',), ('grindstone',)],
        'library': [('bookshelf',), ('bookshelf',), ('bookshelf',), ('lectern',), ('chest', 'biblioteca'), ('lantern',), ('bookshelf',), ('enchanting',)],
        'storage': [('barrel', 'casa'), ('barrel', 'casa'), ('chest', 'casa'), ('hay',), ('hay',), ('composter',), ('barrel', None)],
        'tavern': [('barrel', 'taberna'), ('barrel', 'taberna'), ('smoker',), ('crafting_table',), ('chest', 'taberna'), ('lantern',), ('cauldron',)],
        'chapel': [('brewing',), ('lectern',), ('candle',), ('candle',), ('chest', 'capilla'), ('bookshelf',)],
    }
    items = list(sets.get(kind, sets['house']))
    used = set()
    for item in items:
        while spots:
            x, z, face = spots.pop()
            if (x, z) in used or b.get(x, y, z) not in (None, AIR): continue
            if item[0] == 'bed':
                hx, hz = x + VEC[OPP[face]][0], z + VEC[OPP[face]][1]
                # la cama sale de la pared hacia dentro: pie hacia dentro, cabecera contra la pared
                fx, fz = x + VEC[face][0], z + VEC[face][1]
                if not (x0 <= fx <= x1 and z0 <= fz <= z1) or (fx, fz) in used: continue
                b.bed(fx, fz, y, OPP[face], rng.choice(['red', 'blue', 'green', 'white', 'yellow', 'light_blue']))
                used |= {(x, z), (fx, fz)}
            else:
                place_item(b, rng, x, y, z, face, item, pal)
                used.add((x, z))
            break

def place_item(b, rng, x, y, z, face, item, pal):
    k = item[0]
    if k == 'crafting_table': b.set(x, y, z, B('crafting_table'))
    elif k == 'barrel': b.barrel(x, y, z, item[1])
    elif k == 'chest': b.chest(x, y, z, face, item[1])
    elif k == 'furnace': b.simple_be(x, y, z, B('furnace', cardinal_direction=face), 'Furnace', Items=[])
    elif k == 'blast_furnace': b.simple_be(x, y, z, B('blast_furnace', cardinal_direction=face), 'BlastFurnace', Items=[])
    elif k == 'smoker': b.simple_be(x, y, z, B('smoker', cardinal_direction=face), 'Smoker', Items=[])
    elif k == 'lantern':
        b.set(x, y, z, pal.get('table', B('oak_fence'))); b.set(x, y + 1, z, lantern())
    elif k == 'pot': b.simple_be(x, y, z, B('flower_pot'), 'FlowerPot')
    elif k == 'bookshelf':
        b.set(x, y, z, B('bookshelf')); b.set(x, y + 1, z, B('bookshelf'))
    elif k == 'cauldron': b.simple_be(x, y, z, B('cauldron', fill_level=6, cauldron_liquid='water'), 'Cauldron', PotionId=tS(-1))
    elif k == 'lava_cauldron': b.simple_be(x, y, z, B('cauldron', fill_level=6, cauldron_liquid='lava'), 'Cauldron', PotionId=tS(-1))
    elif k == 'anvil': b.set(x, y, z, B('anvil', cardinal_direction=face))
    elif k == 'smithing_table': b.set(x, y, z, B('smithing_table'))
    elif k == 'grindstone': b.set(x, y, z, B('grindstone', attachment='standing', direction=BED_DIR[face]))
    elif k == 'lectern': b.simple_be(x, y, z, B('lectern', cardinal_direction=face), 'Lectern')
    elif k == 'enchanting': b.simple_be(x, y, z, B('enchanting_table'), 'EnchantTable')
    elif k == 'hay': b.set(x, y, z, log('hay_block'))
    elif k == 'composter': b.set(x, y, z, B('composter'))
    elif k == 'brewing': b.simple_be(x, y, z, B('brewing_stand'), 'BrewingStand', Items=[])
    elif k == 'candle': b.set(x, y, z, B('candle', candles=rng.randint(1, 3), lit=True))

def round_tower(b, cx, cz, y0, r, h, mat, roof_mat=None, pane=None, rng=None, floor=None, cren=None):
    """Torre redonda hueca con pisos cada 5 bloques, ventanas y techo cónico (o almenas)."""
    def inside(x, z, rr): return (x - cx) ** 2 + (z - cz) ** 2 <= rr * rr + rr * 0.8
    for x in range(cx - r - 2, cx + r + 3):
        for z in range(cz - r - 2, cz + r + 3):
            if inside(x, z, r):
                edge = not inside(x, z, r - 1)
                for y in range(y0, y0 + h):
                    if edge: b.set(x, y, z, mat if not callable(mat) else mat())
                    else: b.set(x, y, z, AIR)
                b.set(x, y0, z, floor or (mat if not callable(mat) else mat()))
                for fy in range(y0 + 5, y0 + h, 5):
                    if not edge: b.set(x, fy, z, floor or (mat if not callable(mat) else mat()))
    # ventanas en cruz
    if pane:
        for fy in range(y0 + 2, y0 + h - 1, 5):
            for dx, dz in ((r, 0), (-r, 0), (0, r)):   # (0,-r) queda libre: ahí va la escalera
                b.set(cx + dx, fy, cz + dz, pane); b.set(cx + dx, fy + 1, cz + dz, pane)
    # escalera de mano por dentro
    for y in range(y0 + 1, y0 + h):
        b.set(cx, y, cz - r + 1, B('ladder', facing_direction=FACE6['south']))
    top = y0 + h
    if roof_mat:
        rr = r + 1; y = top
        while rr >= 0:
            for x in range(cx - rr - 1, cx + rr + 2):
                for z in range(cz - rr - 1, cz + rr + 2):
                    if inside(x, z, rr) and not inside(x, z, rr - 1):
                        b.set(x, y, z, roof_mat)
            rr -= 1; y += 1
        return y
    if cren:
        for x in range(cx - r - 2, cx + r + 3):
            for z in range(cz - r - 2, cz + r + 3):
                if inside(x, z, r) and not inside(x, z, r - 1):
                    b.set(x, top, z, cren if (x + z) % 2 == 0 else AIR)
                elif inside(x, z, r - 1):
                    b.set(x, top - 1, z, floor or cren)
        return top + 1
    return top

def path_line(b, rng, x0, z0, x1, z1, y, mats):
    """Camino de 3 de ancho entre dos puntos (en L)."""
    xs = range(min(x0, x1), max(x0, x1) + 1)
    zs = range(min(z0, z1), max(z0, z1) + 1)
    for x in xs:
        for dz in (-1, 0, 1):
            b.set(x, y, z0 + dz, rng.choice(mats))
    for z in zs:
        for dx in (-1, 0, 1):
            b.set(x1 + dx, y, z, rng.choice(mats))

def farm(b, rng, x0, z0, w, d, y, crop, border):
    b.walls(x0, y, z0, x0 + w - 1, y, z0 + d - 1, border)
    for x in range(x0 + 1, x0 + w - 1):
        for z in range(z0 + 1, z0 + d - 1):
            if x == x0 + w // 2:
                b.set(x, y, z, WATER)
                b.set(x, y + 1, z, AIR)
            else:
                b.set(x, y, z, B('farmland', moisturized_amount=7))
                b.set(x, y + 1, z, crop)

def lamp_post(b, x, y, z, post, h=3, soul=False):
    for yy in range(y, y + h): b.set(x, yy, z, post)
    b.set(x, y + h, z, lantern(soul=soul))

def tree(b, rng, x, y, z, logb, leaf, h=5, r=2):
    for yy in range(y, y + h): b.set(x, yy, z, logb)
    for yy in range(y + h - 2, y + h + 2):
        rr = r if yy < y + h + 1 else r - 1
        for dx in range(-rr, rr + 1):
            for dz in range(-rr, rr + 1):
                if abs(dx) + abs(dz) <= rr + 1 and b.get(x + dx, yy, z + dz) is None and rng.random() > 0.08:
                    b.set(x + dx, yy, z + dz, leaf)

# ============================================================== trial spawners propios
# mobs: (id, peso). loot: tabla de recompensa en loot_tables/epicas/trial/
SPAWNERS = {
    'desierto': {'mobs': [('minecraft:husk', 3), ('minecraft:skeleton', 2), ('minecraft:spider', 1)], 'loot': 'desierto'},
    'jungla': {'mobs': [('minecraft:spider', 2), ('minecraft:cave_spider', 2), ('minecraft:zombie', 1)], 'loot': 'jungla'},
    'pantano': {'mobs': [('minecraft:slime', 2), ('minecraft:bogged', 2), ('minecraft:witch', 1)], 'loot': 'pantano'},
    'nieve': {'mobs': [('minecraft:stray', 3), ('minecraft:zombie', 1)], 'loot': 'nieve'},
    'saqueadores': {'mobs': [('minecraft:pillager', 3), ('minecraft:vindicator', 2)], 'loot': 'saqueadores'},
    'nether': {'mobs': [('minecraft:zombie_pigman', 2), ('minecraft:magma_cube', 2), ('minecraft:blaze', 1)], 'loot': 'nether'},
    'cripta': {'mobs': [('minecraft:zombie', 3), ('minecraft:zombie_villager_v2', 1), ('minecraft:skeleton', 2)], 'loot': 'cripta'},
    'bosque': {'mobs': [('minecraft:skeleton', 2), ('minecraft:zombie', 2), ('minecraft:spider', 1)], 'loot': 'cripta'},
    # tanda 2 (se agregan al final para no cambiar los índices de los bloques ya colocados)
    'trial_melee': {'mobs': [('minecraft:zombie', 3), ('minecraft:husk', 2), ('minecraft:spider', 1)], 'loot': 'camaras'},
    'trial_ranged': {'mobs': [('minecraft:skeleton', 3), ('minecraft:stray', 2), ('minecraft:bogged', 1)], 'loot': 'camaras'},
    'trial_breeze': {'mobs': [('minecraft:breeze', 1)], 'loot': 'camaras_breeze'},
    'trial_small': {'mobs': [('minecraft:slime', 2), ('minecraft:cave_spider', 2), ('minecraft:silverfish', 1)], 'loot': 'camaras'},
    'fortaleza': {'mobs': [('minecraft:wither_skeleton', 3), ('minecraft:blaze', 2), ('minecraft:magma_cube', 1)], 'loot': 'fortaleza'},
    'bastion': {'mobs': [('minecraft:piglin', 2), ('minecraft:piglin_brute', 1), ('minecraft:hoglin', 1)], 'loot': 'bastion'},
    'end': {'mobs': [('minecraft:shulker', 2), ('minecraft:enderman', 2), ('minecraft:endermite', 1)], 'loot': 'end'},
    'mansion': {'mobs': [('minecraft:vindicator', 3), ('minecraft:pillager', 2), ('minecraft:evocation_illager', 1)], 'loot': 'mansion'},
}
SPAWNER_INDEX = {k: i for i, k in enumerate(SPAWNERS)}

# ============================================================== paletas
def P(**kw): return kw

PAL_PLAINS = P(base=B('cobblestone'), wall=B('oak_planks'), floor=B('spruce_planks'), log='oak_log', roof='dark_oak',
               gable=B('oak_planks'), pane=B('glass_pane'), door='spruce', step=B('cobblestone_slab', vertical_half='top'),
               table=B('oak_fence'))
PAL_DESERT = P(base=B('cut_sandstone'), wall=B('smooth_sandstone'), floor=B('cut_sandstone'), log='stripped_jungle_log',
               roof='smooth_sandstone', gable=B('smooth_sandstone'), pane=B('glass_pane'), door='jungle',
               step=B('sandstone_slab', vertical_half='top'), table=B('jungle_fence'))
PAL_SAVANNA = P(base=B('hardened_clay'), wall=B('acacia_planks'), floor=B('acacia_planks'), log='acacia_log', roof='acacia',
                gable=B('orange_terracotta'), pane=B('glass_pane'), door='acacia', step=B('acacia_slab', vertical_half='top'),
                table=B('acacia_fence'))
PAL_TAIGA = P(base=B('mossy_cobblestone'), wall=B('spruce_planks'), floor=B('spruce_planks'), log='spruce_log', roof='spruce',
              gable=B('spruce_planks'), pane=B('glass_pane'), door='spruce', step=B('spruce_slab', vertical_half='top'),
              table=B('spruce_fence'))
PAL_SNOW = P(base=B('stone_bricks'), wall=B('spruce_planks'), floor=B('dark_oak_planks'), log='stripped_spruce_log',
             roof='dark_oak', gable=B('white_wool'), pane=B('glass_pane'), door='dark_oak',
             step=B('stone_brick_slab', vertical_half='top'), table=B('dark_oak_fence'))

# ============================================================== DISEÑOS
def build_piramide(rng):
    """Gran Pirámide del Desierto: pirámide escalonada con 4 torres, patio, cámara del tesoro bajo tierra."""
    S = 47; G = 12  # tamaño y nivel del suelo dentro de la plantilla
    b = Build(S, G + 34, S)
    c = S // 2
    sand = [(B('sandstone'), 6), (B('cut_sandstone'), 2), (B('smooth_sandstone'), 2), (B('chiseled_sandstone'), 0.3)]
    foundation(b, 1, 1, S - 2, S - 2, G, 4, B('sandstone'), B('sandstone'))
    # pirámide escalonada (base 37)
    r0 = 18
    for i in range(0, 14):
        rr = r0 - i
        y = G + 1 + i * 2
        b.mix(c - rr, y, c - rr, c + rr, y + 1, c + rr, rng, sand)
        # banda decorativa de terracota cada 3 niveles
        if i % 3 == 1:
            for x in range(c - rr, c + rr + 1):
                b.set(x, y + 1, c - rr, B('orange_terracotta')); b.set(x, y + 1, c + rr, B('orange_terracotta'))
            for z in range(c - rr, c + rr + 1):
                b.set(c - rr, y + 1, z, B('orange_terracotta')); b.set(c + rr, y + 1, z, B('orange_terracotta'))
        # escalones del borde
        for x in range(c - rr, c + rr + 1):
            b.set(x, y + 2, c - rr, stairs('sandstone', 'south')); b.set(x, y + 2, c + rr, stairs('sandstone', 'north'))
        for z in range(c - rr + 1, c + rr):
            b.set(c - rr, y + 2, z, stairs('sandstone', 'east')); b.set(c + rr, y + 2, z, stairs('sandstone', 'west'))
        if rr <= 4: break
    # vaciar interior: gran salón
    clear(b, c - 13, G + 1, c - 13, c + 13, G + 9, c + 13)
    b.fill(c - 13, G, c - 13, c + 13, G, c + 13, B('cut_sandstone'))
    # suelo en damero con terracota
    for x in range(c - 12, c + 13):
        for z in range(c - 12, c + 13):
            if (x + z) % 4 == 0: b.set(x, G, z, B('orange_terracotta'))
            if abs(x - c) <= 2 and abs(z - c) <= 2: b.set(x, G, z, B('blue_terracotta'))
    b.set(c, G, c, B('blue_glazed_terracotta', facing_direction=2))
    # columnas del salón
    for px in (c - 9, c - 3, c + 3, c + 9):
        for pz in (c - 9, c + 9):
            b.fill(px, G + 1, pz, px, G + 9, pz, B('chiseled_sandstone'))
            b.set(px, G + 1, pz, B('cut_sandstone')); b.set(px, G + 9, pz, B('cut_sandstone'))
            b.set(px, G + 5, pz, B('orange_terracotta'))
        for pz in (c - 3, c + 3):
            if px in (c - 9, c + 9):
                b.fill(px, G + 1, pz, px, G + 9, pz, B('chiseled_sandstone'))
    # antorchas/linternas colgantes
    for (x, z) in ((c - 6, c - 6), (c + 6, c - 6), (c - 6, c + 6), (c + 6, c + 6), (c, c - 10), (c, c + 10)):
        b.set(x, G + 9, z, B('iron_chain', pillar_axis='y')); b.set(x, G + 8, z, lantern(hanging=True))
    # entrada monumental (sur)
    clear(b, c - 2, G + 1, c + 13, c + 2, G + 6, c + 19)
    for x in range(c - 3, c + 4):
        b.set(x, G + 7, c + 19, B('chiseled_sandstone'))
    for side in (-3, 3):
        b.fill(c + side, G + 1, c + 19, c + side, G + 7, c + 19, B('cut_sandstone'))
        b.banner(c + side, G + 5, c + 20, 'south', 'orange')
    b.fill(c - 2, G, c + 14, c + 2, G, c + 21, B('smooth_sandstone'))
    for z in range(c + 19, c + 23):
        b.fill(c - 2, G, z, c + 2, G, z, stairs('sandstone', 'north') if z > c + 19 else B('smooth_sandstone'))
    # escaleras hacia la cima por fuera (norte) — se omiten; cima con altar
    top_y = max(y for (_, y, _) in b.blocks) + 1
    b.set(c, top_y, c, B('chiseled_sandstone')); b.set(c, top_y + 1, c, B('gold_block'))
    # 4 torres-obelisco en las esquinas
    for (tx, tz) in ((3, 3), (S - 4, 3), (3, S - 4), (S - 4, S - 4)):
        b.fill(tx - 1, G + 1, tz - 1, tx + 1, G + 14, tz + 1, B('cut_sandstone'))
        b.fill(tx - 1, G + 15, tz - 1, tx + 1, G + 15, tz + 1, B('chiseled_sandstone'))
        b.set(tx, G + 16, tz, B('orange_terracotta')); b.set(tx, G + 17, tz, B('cut_sandstone'))
        b.set(tx, G + 18, tz, lantern())
        for yy in (G + 4, G + 9):
            for dx, dz in ((0, -2), (0, 2), (-2, 0), (2, 0)):
                b.set(tx + dx // 2 * 1, yy, tz + dz // 2, B('orange_terracotta'))
    # cámara del tesoro subterránea (bajo el centro): escalera desde el salón
    ty = G - 9
    clear(b, c - 6, ty, c - 6, c + 6, ty + 5, c + 6)
    b.fill(c - 7, ty - 1, c - 7, c + 7, ty - 1, c + 7, B('cut_sandstone'))
    b.walls(c - 7, ty, c - 7, c + 7, ty + 6, c + 7, B('cut_sandstone'))
    b.fill(c - 7, ty + 6, c - 7, c + 7, ty + 6, c + 7, B('cut_sandstone'))
    for x in range(c - 6, c + 7):
        for z in range(c - 6, c + 7):
            b.set(x, ty - 1, z, B('blue_terracotta') if (x + z) % 2 else B('orange_terracotta'))
    # pozo/escalera de bajada desde el salón (esquina noreste del salón)
    sx0, sz0 = c + 9, c - 4
    b.fill(sx0 - 2, ty - 1, sz0 - 2, sx0 + 2, G - 1, sz0 + 2, B('cut_sandstone'))
    clear(b, sx0 - 1, ty, sz0 - 1, sx0 + 1, G, sz0 + 1)
    clear(b, c + 6, ty, sz0, sx0 - 1, ty + 2, sz0)          # pasillo hacia la cámara
    for yy in range(ty, G + 1): b.set(sx0, yy, sz0 - 1, B('ladder', facing_direction=FACE6['south']))
    for (x, z) in ((sx0 - 1, sz0 - 2), (sx0 + 1, sz0 - 2)):
        b.set(x, G + 1, z, B('cut_sandstone_slab', vertical_half='bottom') if 'minecraft:cut_sandstone_slab' in BLOCKS else B('sandstone_slab'))
    # trial spawner central + cofres del tesoro
    b.set(c, ty - 1, c, B('gold_block'))
    b.spawner(c, ty, c, 'desierto')
    for (x, z, f) in ((c - 5, c, 'east'), (c + 5, c, 'west'), (c, c - 5, 'south'), (c, c + 5, 'north')):
        b.chest(x, ty, z, f, 'piramide_tesoro')
    for (x, z) in ((c - 6, c - 6), (c + 6, c - 6), (c - 6, c + 6), (c + 6, c + 6)):
        b.fill(x, ty, z, x, ty + 5, z, B('chiseled_sandstone'))
        b.set(x + (1 if x < c else -1), ty + 4, z, lantern())
    # sala lateral oeste del salón (cripta con spawner)
    b.chest(c - 12, G + 1, c, 'east', 'piramide')
    b.chest(c + 12, G + 1, c + 4, 'west', 'piramide')
    b.spawner(c - 6, G + 1, c, 'desierto')
    # urnas decorativas
    for (x, z) in ((c - 11, c - 11), (c + 11, c - 11), (c - 11, c + 11), (c + 11, c + 11)):
        b.simple_be(x, G + 1, z, B('decorated_pot', direction=0), 'DecoratedPot')
    b.mob(c, G + 1, c + 8, 'minecraft:husk')
    return b, G

def build_templo_jungla(rng):
    """Templo de la Jungla mayor: zigurat de 3 niveles con escalinata, santuario superior y cripta."""
    S = 39; G = 8
    b = Build(S, G + 30, S)
    c = S // 2
    stone = [(B('mossy_cobblestone'), 5), (B('cobblestone'), 3), (B('mossy_stone_bricks'), 3), (B('stone_bricks'), 2),
             (B('cracked_stone_bricks'), 1)]
    foundation(b, 1, 1, S - 2, S - 2, G, 4, B('mossy_cobblestone'), B('cobblestone'))
    levels = [(17, 6), (13, 6), (9, 6)]
    y = G + 1
    for rr, h in levels:
        b.mix(c - rr, y, c - rr, c + rr, y + h - 1, c + rr, rng, stone)
        clear(b, c - rr + 1, y, c - rr + 1, c + rr - 1, y + h - 2, c + rr - 1)
        # cornisa
        for x in range(c - rr - 1, c + rr + 2):
            b.set(x, y + h - 1, c - rr - 1, stairs('mossy_cobblestone', 'south', True)); b.set(x, y + h - 1, c + rr + 1, stairs('mossy_cobblestone', 'north', True))
        for z in range(c - rr, c + rr + 1):
            b.set(c - rr - 1, y + h - 1, z, stairs('mossy_cobblestone', 'east', True)); b.set(c + rr + 1, y + h - 1, z, stairs('mossy_cobblestone', 'west', True))
        # ventanas con barrotes
        for k in range(c - rr + 3, c + rr - 2, 4):
            for (x, z) in ((k, c - rr), (k, c + rr), (c - rr, k), (c + rr, k)):
                b.set(x, y + 2, z, B('iron_bars')); b.set(x, y + 3, z, B('iron_bars'))
        # piso interior
        b.fill(c - rr + 1, y + h - 1, c - rr + 1, c + rr - 1, y + h - 1, c + rr - 1, B('mossy_stone_bricks'))
        y += h
    # santuario superior con techo
    b.mix(c - 5, y, c - 5, c + 5, y + 4, c + 5, rng, stone)
    clear(b, c - 4, y, c - 4, c + 4, y + 3, c + 4)
    hip_roof(b, c - 5, c - 5, c + 5, c + 5, y + 5, 'mossy_cobblestone', overhang=1, cap=B('chiseled_stone_bricks'))
    clear(b, c - 1, y, c + 5, c + 1, y + 2, c + 5)
    b.set(c, y, c, B('emerald_block')); b.chest(c, y + 1, c, 'south', 'templo_jungla_tesoro')
    for (x, z) in ((c - 3, c - 3), (c + 3, c - 3), (c - 3, c + 3), (c + 3, c + 3)):
        b.set(x, y, z, B('chiseled_stone_bricks')); b.set(x, y + 1, z, lantern())
    # escalinata frontal (sur) hasta la cima
    top = y
    for i in range(top - G):
        zz = c + 18 - i
        if zz < c + 6: break
        for x in range(c - 2, c + 3):
            b.set(x, G + 1 + i, zz, stairs('mossy_stone_brick', 'north'))
            for yy in range(G + 2 + i, G + 5 + i): b.set(x, yy, zz, AIR) if b.get(x, yy, zz) and yy > G + 1 + i else None
        b.set(c - 3, G + 1 + i, zz, B('mossy_stone_bricks')); b.set(c + 3, G + 1 + i, zz, B('mossy_stone_bricks'))
    # puertas de cada nivel (sur)
    y = G + 1
    for rr, h in levels:
        clear(b, c - 1, y, c + rr, c + 1, y + 2, c + rr)
        y += h
    # interior del nivel 1: sala con trial spawner y cofres
    b.spawner(c, G + 1, c, 'jungla')
    b.chest(c - 15, G + 1, c, 'east', 'templo_jungla'); b.chest(c + 15, G + 1, c, 'west', 'templo_jungla')
    for (x, z) in ((c - 8, c - 8), (c + 8, c - 8), (c - 8, c + 8), (c + 8, c + 8)):
        b.fill(x, G + 1, z, x, G + 5, z, B('chiseled_stone_bricks'))
        b.set(x, G + 5, z + 1, lantern(hanging=True))
    # nivel 2: biblioteca en ruinas
    y2 = G + 7
    for x in range(c - 11, c + 12, 2):
        b.set(x, y2, c - 12, B('bookshelf')); b.set(x, y2 + 1, c - 12, B('bookshelf'))
    b.spawner(c, y2, c - 4, 'jungla')
    b.chest(c + 10, y2, c + 10, 'west', 'templo_jungla')
    # escaleras de mano entre niveles (interior)
    for yy in range(G + 1, G + 13):
        b.set(c + 6, yy, c - 7, B('chiseled_stone_bricks') if yy % 6 == 3 else B('mossy_stone_bricks'))
        b.set(c + 6, yy, c - 6, B('ladder', facing_direction=FACE6['south']))
    # enredaderas por fuera
    for (x, yy, z), (blk, be) in list(b.blocks.items()):
        if blk.name in ('minecraft:mossy_cobblestone', 'minecraft:mossy_stone_bricks') and rng.random() < 0.18:
            for face in ('north', 'south', 'east', 'west'):
                vx, vz = x + VEC[face][0], z + VEC[face][1]
                if b.get(vx, yy, vz) is None and rng.random() < 0.6:
                    b.set(vx, yy, vz, B('vine', vine_direction_bits=VINE_BITS[OPP[face]]))
    # árboles alrededor
    for (x, z) in ((2, 2), (S - 3, 3), (3, S - 4), (S - 4, S - 3)):
        tree(b, rng, x, G + 1, z, log('jungle_log'), leaves('jungle'), h=7, r=2)
    return b, G

def build_cabana_bruja(rng):
    """Mansión de la Bruja: casa de dos pisos sobre pilotes en el pantano, con invernadero y torre."""
    S = 27; G = 6
    b = Build(S, G + 26, S)
    c = S // 2
    # pilotes
    for x in range(4, S - 4, 4):
        for z in range(4, S - 4, 4):
            b.fill(x, 0, z, x, G + 3, z, log('dark_oak_log'))
    # plataforma
    b.fill(3, G + 4, 3, S - 4, G + 4, S - 4, B('mangrove_planks'))
    for x in range(3, S - 3):
        b.set(x, G + 5, 3, B('mangrove_fence')); b.set(x, G + 5, S - 4, B('mangrove_fence'))
    for z in range(3, S - 3):
        b.set(3, G + 5, z, B('mangrove_fence')); b.set(S - 4, G + 5, z, B('mangrove_fence'))
    pal = P(base=B('mud_bricks'), wall=B('mangrove_planks'), floor=B('dark_oak_planks'), log='dark_oak_log', roof='dark_oak',
            gable=B('mangrove_planks'), pane=B('purple_stained_glass_pane'), door='mangrove', step=B('mangrove_planks'),
            table=B('mangrove_fence'))
    timber_house(b, rng, 6, G + 4, 6, 13, 11, 2, pal, door_side='south', inside='chapel')
    # escalera de acceso
    for yy in range(1, G + 4): b.set(c, yy, S - 4, log('dark_oak_log'))
    for yy in range(1, G + 5): b.set(c, yy, S - 3, B('ladder', facing_direction=FACE6['south']))
    b.set(c, G + 5, S - 4, AIR)
    # torre del caldero
    round_tower(b, S - 6, 6, G + 4, 3, 10, B('mud_bricks'), roof_mat=B('dark_oak_planks'), pane=B('purple_stained_glass_pane'))
    b.simple_be(S - 6, G + 5, 6, B('cauldron', fill_level=6, cauldron_liquid='water'), 'Cauldron', PotionId=tS(-1))
    b.simple_be(S - 7, G + 5, 6, B('brewing_stand'), 'BrewingStand', Items=[])
    # jardín de hongos y calabazas en la plataforma
    for (x, z) in ((5, S - 6), (7, S - 6), (S - 7, S - 6), (S - 9, S - 6)):
        b.set(x, G + 5, z, rng.choice([B('red_mushroom'), B('brown_mushroom'), B('carved_pumpkin', cardinal_direction='south')]))
    # cofres y spawner (sótano de pociones en el piso de abajo)
    b.spawner(c, G + 5, c, 'pantano')
    b.chest(7, G + 5, 7, 'south', 'bruja')
    b.chest(17, G + 9, 15, 'north', 'bruja')
    # agua del pantano debajo
    for x in range(0, S):
        for z in range(0, S):
            if b.get(x, 0, z) is None: b.set(x, 0, z, WATER if rng.random() < 0.7 else B('mud'))
            if b.get(x, 1, z) is None and rng.random() < 0.08: b.set(x, 1, z, B('waterlily'))
    b.mob(c - 2, G + 5, c, 'minecraft:witch')
    b.mob(c + 2, G + 5, c + 2, 'minecraft:cat')
    return b, 1

def build_iglu(rng):
    """Iglú mayor: domo grande, anexo y un laboratorio subterráneo con celdas."""
    S = 29; G = 16
    b = Build(S, G + 12, S)
    c = S // 2
    # domo principal
    R = 8
    for x in range(S):
        for z in range(S):
            for y in range(0, R + 1):
                d = ((x - c) ** 2 + (z - c) ** 2 + (y * 1.3) ** 2) ** 0.5
                if d <= R and d > R - 1.2: b.set(x, G + y, z, B('snow'))
                elif d <= R - 1.2 and y > 0: b.set(x, G + y, z, AIR)
            if (x - c) ** 2 + (z - c) ** 2 <= R * R: b.set(x, G, z, B('snow'))
    # ventanas de hielo
    for dx, dz in ((R - 1, 0), (-R + 1, 0), (0, -R + 1)):
        b.set(c + dx, G + 3, c + dz, B('ice'))
    # túnel de entrada (sur)
    for z in range(c + R - 2, c + R + 4):
        b.fill(c - 2, G, z, c + 2, G + 3, z, B('snow'))
        clear(b, c - 1, G + 1, z, c + 1, G + 2, z)
    b.fill(c - 1, G, c + R - 1, c + 1, G, c + R + 3, B('packed_ice'))
    # interior
    b.fill(c - 6, G, c - 6, c + 6, G, c + 6, B('white_carpet') if False else B('spruce_planks'))
    for x in range(c - 3, c + 4):
        for z in range(c - 3, c + 4):
            b.set(x, G + 1, z, B('light_blue_carpet') if (x + z) % 2 else B('white_carpet'))
    b.bed(c - 5, c - 3, G + 1, 'north', 'red')
    b.bed(c + 5, c - 3, G + 1, 'north', 'blue')
    b.simple_be(c, G + 1, c - 6, B('furnace', cardinal_direction='south'), 'Furnace', Items=[])
    b.set(c - 1, G + 1, c - 6, B('crafting_table'))
    b.chest(c + 1, G + 1, c - 6, 'south', 'iglu')
    b.set(c, G + 6, c, B('iron_chain', pillar_axis='y')); b.set(c, G + 5, c, lantern(hanging=True))
    # trampilla al sótano
    b.set(c + 4, G, c + 3, trapdoor('spruce', 'north'))
    # laboratorio subterráneo
    ly = G - 12
    b.fill(c - 9, ly - 1, c - 7, c + 9, ly + 5, c + 7, B('stone_bricks'))
    clear(b, c - 8, ly, c - 6, c + 8, ly + 4, c + 6)
    b.mix(c - 9, ly - 1, c - 7, c + 9, ly + 5, c + 7, rng, [(B('stone_bricks'), 5), (B('cracked_stone_bricks'), 1), (B('mossy_stone_bricks'), 1)], only_existing=True)
    clear(b, c - 8, ly, c - 6, c + 8, ly + 4, c + 6)
    for x in range(c - 8, c + 9):
        for z in range(c - 6, c + 7):
            b.set(x, ly - 1, z, B('polished_andesite') if (x + z) % 2 else B('polished_diorite'))
    for yy in range(ly, G):
        b.set(c + 4, yy, c + 3, B('ladder', facing_direction=FACE6['north']) if yy < G else AIR)
    b.fill(c + 3, ly, c + 4, c + 5, G - 1, c + 4, B('stone_bricks'))
    # celdas con barrotes al norte
    for i, cx in enumerate((c - 6, c - 2, c + 2, c + 6)):
        b.fill(cx - 1, ly, c - 6, cx + 1, ly + 3, c - 3, B('stone_bricks'))
        clear(b, cx - 1 + 0, ly, c - 6, cx + 1 - 0, ly + 2, c - 4)
        b.fill(cx - 1, ly, c - 3, cx + 1, ly + 2, c - 3, B('iron_bars'))
        b.walls(cx - 2, ly, c - 6, cx + 2, ly + 3, c - 3, B('stone_bricks'))
        b.fill(cx - 1, ly, c - 3, cx + 1, ly + 2, c - 3, B('iron_bars'))
        if i in (1, 2): b.mob(cx, ly, c - 5, 'minecraft:zombie_villager_v2')
    # mesa de alquimia y spawner
    b.simple_be(c - 6, ly, c + 5, B('brewing_stand'), 'BrewingStand', Items=[])
    b.simple_be(c - 5, ly, c + 5, B('cauldron', fill_level=6, cauldron_liquid='water'), 'Cauldron', PotionId=tS(-1))
    b.chest(c - 7, ly, c + 5, 'east', 'iglu_tesoro')
    b.spawner(c, ly, c + 2, 'nieve')
    for (x, z) in ((c - 7, c), (c + 7, c)):
        b.set(x, ly + 3, z, lantern(hanging=True))
    b.set(c, ly, c - 1, B('gold_block'))
    return b, G

def build_puesto(rng):
    """Fortaleza de Saqueadores: torre principal de 5 pisos, muralla con 4 torres, jaulas y campamento."""
    S = 45; G = 4
    b = Build(S, G + 40, S)
    c = S // 2
    foundation(b, 2, 2, S - 3, S - 3, G, 4, B('coarse_dirt'), B('dirt'))
    # muralla de empalizada
    for x in range(4, S - 4):
        for z in (4, S - 5):
            b.fill(x, G + 1, z, x, G + 5, z, log('dark_oak_log'))
            b.set(x, G + 6, z, B('dark_oak_fence') if x % 2 else AIR)
    for z in range(4, S - 4):
        for x in (4, S - 5):
            b.fill(x, G + 1, z, x, G + 5, z, log('dark_oak_log'))
            b.set(x, G + 6, z, B('dark_oak_fence') if z % 2 else AIR)
    # pasarela interior de la muralla
    for x in range(5, S - 5):
        b.set(x, G + 4, 5, B('dark_oak_slab', vertical_half='top')); b.set(x, G + 4, S - 6, B('dark_oak_slab', vertical_half='top'))
    for z in range(5, S - 5):
        b.set(5, G + 4, z, B('dark_oak_slab', vertical_half='top')); b.set(S - 6, G + 4, z, B('dark_oak_slab', vertical_half='top'))
    # puerta (sur)
    clear(b, c - 2, G + 1, S - 5, c + 2, G + 4, S - 5)
    for x in (c - 3, c + 3):
        b.fill(x, G + 1, S - 5, x, G + 9, S - 5, B('cobblestone'))
        b.banner(x, G + 7, S - 4, 'south', 'white')
    b.fill(c - 3, G + 8, S - 5, c + 3, G + 9, S - 5, log('dark_oak_log', 'x'))
    # torres de esquina
    for (tx, tz) in ((5, 5), (S - 6, 5), (5, S - 6), (S - 6, S - 6)):
        b.fill(tx - 2, G + 1, tz - 2, tx + 2, G + 10, tz + 2, B('cobblestone'))
        clear(b, tx - 1, G + 1, tz - 1, tx + 1, G + 9, tz + 1)
        b.fill(tx - 3, G + 10, tz - 3, tx + 3, G + 10, tz + 3, B('dark_oak_planks'))
        crenellate(b, tx - 3, tz - 3, tx + 3, tz + 3, G + 11, B('dark_oak_fence'), step=1)
        for yy in range(G + 1, G + 10): b.set(tx, yy, tz - 1, B('ladder', facing_direction=FACE6['south']))
        b.set(tx, G + 10, tz - 1, AIR)
        b.mob(tx + 1, G + 11, tz + 1, 'minecraft:pillager')
    # torre principal (centro)
    t0 = c - 5; t1 = c + 5
    b.fill(t0, G + 1, t0, t1, G + 2, t1, B('cobblestone'))
    fh = 6
    for f in range(5):
        fy = G + 1 + f * fh
        b.walls(t0, fy, t0, t1, fy + fh - 1, t1, B('dark_oak_planks'))
        for (x, z) in ((t0, t0), (t1, t0), (t0, t1), (t1, t1)):
            b.fill(x, fy, z, x, fy + fh - 1, z, log('dark_oak_log'))
        b.fill(t0 + 1, fy + fh - 1, t0 + 1, t1 - 1, fy + fh - 1, t1 - 1, B('birch_planks'))
        clear(b, t0 + 1, fy, t0 + 1, t1 - 1, fy + fh - 2, t1 - 1)
        for k in (c - 2, c + 2):
            for (x, z) in ((k, t0), (k, t1), (t0, k), (t1, k)):
                b.set(x, fy + 2, z, B('dark_oak_fence')); b.set(x, fy + 3, z, B('dark_oak_fence'))
        b.walls(t0, fy + fh - 1, t0, t1, fy + fh - 1, t1, log('dark_oak_log', 'x'))
        # balcones
        for x in range(t0 - 1, t1 + 2):
            b.set(x, fy + fh - 1, t0 - 1, B('dark_oak_slab', vertical_half='top')); b.set(x, fy + fh - 1, t1 + 1, B('dark_oak_slab', vertical_half='top'))
        for x in range(t0 - 1, t1 + 2, 2):
            b.set(x, fy + fh, t0 - 1, B('dark_oak_fence')); b.set(x, fy + fh, t1 + 1, B('dark_oak_fence'))
        b.banner(c, fy + 3, t1 + 1, 'south', 'black') if f % 2 == 0 else None
        b.set(c, fy + fh - 2, c, lantern(hanging=True))
    for yy in range(G + 1, G + 1 + 5 * fh):
        b.set(t1 - 1, yy, t1 - 1, B('ladder', facing_direction=FACE6['west']))
    clear(b, c - 1, G + 1, t1, c + 1, G + 3, t1)
    b.door(c, G + 1, t1, 'south', 'dark_oak')
    roof_y = G + 1 + 5 * fh
    b.fill(t0 - 1, roof_y, t0 - 1, t1 + 1, roof_y, t1 + 1, B('dark_oak_planks'))
    crenellate(b, t0 - 1, t0 - 1, t1 + 1, t1 + 1, roof_y + 1, B('cobblestone_wall', wall_post_bit=True), step=2)
    for yy in range(roof_y + 1, roof_y + 5): b.set(c, yy, c, B('dark_oak_fence'))
    b.banner(c, roof_y + 3, c + 1, 'south', 'white')
    b.set(t1 - 1, roof_y, t1 - 1, B('ladder', facing_direction=FACE6['west']))
    # contenido de la torre
    b.spawner(c, G + 1 + 2 * fh, c, 'saqueadores')
    b.spawner(c, G + 1 + 4 * fh, c, 'saqueadores')
    b.chest(t0 + 1, G + 1 + 4 * fh, t0 + 1, 'south', 'puesto_tesoro')
    b.chest(t0 + 1, G + 1 + fh, t0 + 1, 'south', 'puesto')
    b.chest(t0 + 1, G + 1 + 3 * fh, t0 + 1, 'east', 'puesto')
    b.set(t0 + 2, G + 1 + fh, t0 + 1, B('fletching_table'))
    for yy in (G + 1 + fh, G + 1 + 3 * fh):
        for x in range(t0 + 3, t1 - 1):
            b.set(x, yy, t0 + 1, B('dark_oak_fence'))
    # jaulas (golem y allay)
    for (jx, jz, mob) in ((10, c + 8, 'minecraft:iron_golem'), (S - 11, c + 8, 'minecraft:allay')):
        b.fill(jx - 2, G + 1, jz - 2, jx + 2, G + 4, jz + 2, B('dark_oak_fence'))
        clear(b, jx - 1, G + 1, jz - 1, jx + 1, G + 4, jz + 1)
        b.fill(jx - 2, G + 5, jz - 2, jx + 2, G + 5, jz + 2, B('dark_oak_slab'))
        b.mob(jx, G + 1, jz, mob)
    # tiendas del campamento
    for (tx, tz, col) in ((10, 12, 'white_wool'), (S - 11, 12, 'gray_wool'), (c - 9, c + 13, 'white_wool')):
        for i in range(3):
            b.fill(tx - 2 + i, G + 1 + i, tz - 2, tx - 2 + i, G + 1 + i, tz + 2, B(col))
            b.fill(tx + 2 - i, G + 1 + i, tz - 2, tx + 2 - i, G + 1 + i, tz + 2, B(col))
        b.simple_be(tx, G + 1, tz + 3, B('campfire', cardinal_direction='north', extinguished=False), 'Campfire')
        b.barrel(tx, G + 1, tz, 'puesto')
    # muñecos de prácticas (blancos) y troncos
    for (x, z) in ((c + 9, 10), (c + 11, 10), (c + 13, 10)):
        b.set(x, G + 1, z, B('oak_fence')); b.set(x, G + 2, z, B('hay_block', pillar_axis='y')); b.set(x, G + 3, z, B('carved_pumpkin', cardinal_direction='south'))
    for (x, z) in ((c - 4, c + 9), (c + 4, c + 9)):
        b.mob(x, G + 1, z, 'minecraft:pillager')
    b.mob(c, G + 1, c + 9, 'minecraft:vindicator')
    return b, G

def build_pozo(rng):
    """Oasis del Desierto: pozo monumental con cúpula, palmeras, estanque y una cripta bajo el pozo."""
    S = 23; G = 12
    b = Build(S, G + 16, S)
    c = S // 2
    foundation(b, 0, 0, S - 1, S - 1, G, 3, B('sand'), B('sandstone'))
    # estanque del oasis
    for x in range(S):
        for z in range(S):
            d = ((x - c) ** 2 + (z - c) ** 2) ** 0.5
            if 6.5 < d < 10.5 and rng.random() < 0.9:
                b.set(x, G, z, WATER if d < 9 else B('sand'))
                if d < 9: b.set(x, G - 1, z, B('sand'))
    # plataforma y pozo
    b.fill(c - 5, G, c - 5, c + 5, G, c + 5, B('smooth_sandstone'))
    for x in range(c - 5, c + 6):
        for z in range(c - 5, c + 6):
            if (x + z) % 2 == 0 and max(abs(x - c), abs(z - c)) in (3, 4): b.set(x, G, z, B('cut_sandstone'))
    b.walls(c - 2, G + 1, c - 2, c + 2, G + 1, c + 2, B('cut_sandstone'))
    clear(b, c - 1, G - 6, c - 1, c + 1, G + 1, c + 1)
    b.fill(c - 1, G - 7, c - 1, c + 1, G - 7, c + 1, B('sandstone'))
    b.fill(c - 1, G - 6, c - 1, c + 1, G - 2, c + 1, WATER)
    # columnas y cúpula
    for (x, z) in ((c - 4, c - 4), (c + 4, c - 4), (c - 4, c + 4), (c + 4, c + 4)):
        b.fill(x, G + 1, z, x, G + 6, z, B('cut_sandstone'))
        b.set(x, G + 1, z, B('chiseled_sandstone')); b.set(x, G + 6, z, B('chiseled_sandstone'))
    b.fill(c - 5, G + 7, c - 5, c + 5, G + 7, c + 5, B('smooth_sandstone'))
    for x in range(c - 5, c + 6):
        b.set(x, G + 7, c - 5, B('orange_terracotta')); b.set(x, G + 7, c + 5, B('orange_terracotta'))
    for z in range(c - 5, c + 6):
        b.set(c - 5, G + 7, z, B('orange_terracotta')); b.set(c + 5, G + 7, z, B('orange_terracotta'))
    for x in range(S):
        for z in range(S):
            for y in range(0, 5):
                d = ((x - c) ** 2 + (z - c) ** 2 + (y * 1.6) ** 2) ** 0.5
                if 3.2 < d <= 4.4: b.set(x, G + 8 + y, z, B('cut_sandstone') if y < 3 else B('blue_terracotta'))
    b.set(c, G + 13, c, B('gold_block'))
    b.set(c, G + 7, c, B('iron_chain', pillar_axis='y')); b.set(c, G + 6, c, lantern(hanging=True))
    # palmeras
    for (x, z) in ((2, 2), (S - 3, 3), (3, S - 3), (S - 3, S - 4)):
        h = rng.randint(5, 7)
        for yy in range(G + 1, G + 1 + h): b.set(x, yy, z, log('jungle_log'))
        top = G + 1 + h
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for k in range(1, 4):
                b.set(x + dx * k, top - (1 if k == 3 else 0), z + dz * k, leaves('jungle'))
        b.set(x, top, z, leaves('jungle'))
    # cripta bajo el pozo: escalera por el lado este
    cy = G - 10
    clear(b, c - 4, cy, c - 4, c + 4, cy + 3, c + 4)
    b.walls(c - 5, cy - 1, c - 5, c + 5, cy + 4, c + 5, B('cut_sandstone'))
    b.fill(c - 5, cy - 1, c - 5, c + 5, cy - 1, c + 5, B('cut_sandstone'))
    b.fill(c - 5, cy + 4, c - 5, c + 5, cy + 4, c + 5, B('cut_sandstone'))
    clear(b, c - 4, cy, c - 4, c + 4, cy + 3, c + 4)
    b.fill(c - 1, cy + 4, c - 1, c + 1, G - 8, c + 1, B('sandstone'))
    for yy in range(cy, G + 1):
        b.set(c + 6, yy, c, B('ladder', facing_direction=FACE6['west']))
        b.set(c + 7, yy, c, B('cut_sandstone'))
    clear(b, c + 5, cy, c, c + 5, cy + 1, c)
    b.set(c + 6, G + 1, c, AIR)
    b.spawner(c, cy, c, 'desierto')
    b.chest(c - 4, cy, c, 'east', 'pozo'); b.chest(c, cy, c - 4, 'south', 'pozo')
    for (x, z) in ((c - 3, c - 3), (c + 3, c + 3), (c - 3, c + 3), (c + 3, c - 3)):
        b.simple_be(x, cy, z, B('suspicious_sand', hanging=False) if 'hanging' in BLOCKS.get('minecraft:suspicious_sand', {}) else B('suspicious_sand'),
                    'BrushableBlock', LootTable='loot_tables/entities/desert_well_brushable_block.json', type='minecraft:suspicious_sand')
    b.set(c, cy + 3, c - 3, lantern(hanging=True)); b.set(c, cy + 3, c + 3, lantern(hanging=True))
    return b, G

def build_portal(rng):
    """Portal en Ruinas mayor: portal gigante roto, templo de piedra negra, lava y nether invadiendo."""
    S = 31; G = 6
    b = Build(S, G + 26, S)
    c = S // 2
    # mancha de netherrack/magma
    for x in range(S):
        for z in range(S):
            d = ((x - c) ** 2 + (z - c) ** 2) ** 0.5 + rng.uniform(-2, 2)
            if d < 14:
                b.set(x, G, z, rng.choice([B('netherrack')] * 5 + [B('magma'), B('blackstone'), B('gilded_blackstone')]))
                for y in range(G - 3, G): b.set(x, y, z, B('netherrack') if rng.random() < 0.7 else B('blackstone'))
    # base del templo
    b.fill(c - 9, G + 1, c - 6, c + 9, G + 1, c + 6, B('polished_blackstone_bricks'))
    b.mix(c - 9, G + 1, c - 6, c + 9, G + 1, c + 6, rng, [(B('polished_blackstone_bricks'), 4), (B('cracked_polished_blackstone_bricks'), 2), (B('blackstone'), 1)], only_existing=True)
    # columnas rotas
    for (x, z) in ((c - 8, c - 5), (c + 8, c - 5), (c - 8, c + 5), (c + 8, c + 5), (c - 8, c), (c + 8, c)):
        h = rng.randint(3, 9)
        b.fill(x, G + 2, z, x, G + 1 + h, z, B('polished_blackstone'))
        b.set(x, G + 2 + h, z, B('polished_blackstone_wall', wall_post_bit=True))
    # portal gigante (7x11), con huecos
    px0, px1 = c - 4, c + 4
    py0, py1 = G + 2, G + 14
    for x in range(px0, px1 + 1):
        for y in (py0, py1):
            if rng.random() < 0.85: b.set(x, y, c, rng.choice([B('obsidian')] * 3 + [B('crying_obsidian')]))
    for y in range(py0, py1 + 1):
        for x in (px0, px1):
            if rng.random() < 0.8 or y < py0 + 3: b.set(x, y, c, rng.choice([B('obsidian')] * 3 + [B('crying_obsidian')]))
    # marco decorativo de oro y piedra negra
    for y in range(py0, py1 + 2, 3):
        b.set(px0 - 1, y, c, B('gold_block')); b.set(px1 + 1, y, c, B('gold_block'))
    for x in range(px0 - 1, px1 + 2):
        b.set(x, py1 + 1, c, stairs('polished_blackstone_brick', 'north', True) if x % 2 else B('chiseled_polished_blackstone'))
    # lava y cascadas
    for (x, z) in ((c - 6, c + 3), (c + 6, c - 3), (c - 2, c + 8), (c + 3, c + 9)):
        b.set(x, G, z, B('lava', liquid_depth=0))
    # escalones de oro y cofres
    b.chest(c - 2, G + 2, c + 3, 'south', 'portal'); b.chest(c + 2, G + 2, c - 3, 'north', 'portal')
    b.spawner(c, G + 2, c + 4, 'nether')
    # vegetación del nether
    for _ in range(40):
        x, z = rng.randrange(S), rng.randrange(S)
        if b.get(x, G, z) and b.get(x, G, z).name == 'minecraft:netherrack' and b.get(x, G + 1, z) is None:
            b.set(x, G + 1, z, rng.choice([B('crimson_roots'), B('crimson_fungus'), B('nether_sprouts'), B('fire')]))
    # ruinas de muro
    for x in range(c - 9, c + 10):
        if rng.random() < 0.55:
            h = rng.randint(1, 4)
            b.fill(x, G + 2, c - 6, x, G + 1 + h, c - 6, rng.choice([B('stone_bricks'), B('cracked_stone_bricks'), B('blackstone')]))
    return b, G

def build_aldea(rng, kind):
    """Aldea fortificada: muralla con torres, plaza con pozo y campana, 6 casas, herrería, taberna,
    capilla con cripta (trial spawner), granjas y aldeanos."""
    S = 61; G = 10
    b = Build(S, G + 30, S)
    c = S // 2
    cfg = {
        'llanura': dict(pal=PAL_PLAINS, ground=[B('grass_path'), B('gravel'), B('coarse_dirt')], wall=B('cobblestone'),
                        wtop=B('cobblestone_wall', wall_post_bit=True), tower=B('stone_bricks'), roof='dark_oak',
                        crop=[B('wheat', growth=7), B('carrots', growth=7), B('potatoes', growth=7)], logb=log('oak_log'),
                        leaf=leaves('oak'), surf=B('grass_block'), fill=B('dirt'), cript='cripta', banner='red'),
        'desierto': dict(pal=PAL_DESERT, ground=[B('smooth_sandstone'), B('sandstone'), B('cut_sandstone')], wall=B('cut_sandstone'),
                         wtop=B('sandstone_wall', wall_post_bit=True), tower=B('smooth_sandstone'), roof='smooth_sandstone',
                         crop=[B('wheat', growth=7), B('beetroot', growth=7)], logb=log('jungle_log'), leaf=leaves('jungle'),
                         surf=B('sand'), fill=B('sandstone'), cript='desierto', banner='orange'),
        'sabana': dict(pal=PAL_SAVANNA, ground=[B('grass_path'), B('coarse_dirt'), B('red_sand')], wall=B('hardened_clay'),
                       wtop=B('acacia_fence'), tower=B('orange_terracotta'), roof='acacia',
                       crop=[B('wheat', growth=7), B('melon_stem', growth=7)], logb=log('acacia_log'), leaf=leaves('acacia'),
                       surf=B('grass_block'), fill=B('dirt'), cript='cripta', banner='yellow'),
        'taiga': dict(pal=PAL_TAIGA, ground=[B('grass_path'), B('podzol'), B('coarse_dirt')], wall=B('mossy_cobblestone'),
                      wtop=B('spruce_fence'), tower=B('mossy_stone_bricks'), roof='spruce',
                      crop=[B('sweet_berry_bush', growth=3), B('potatoes', growth=7)], logb=log('spruce_log'), leaf=leaves('spruce'),
                      surf=B('podzol'), fill=B('dirt'), cript='bosque', banner='brown'),
        'nevada': dict(pal=PAL_SNOW, ground=[B('packed_ice'), B('snow'), B('gravel')], wall=B('stone_bricks'),
                       wtop=B('stone_brick_wall', wall_post_bit=True), tower=B('stone_bricks'), roof='dark_oak',
                       crop=[B('wheat', growth=7), B('beetroot', growth=7)], logb=log('spruce_log'), leaf=leaves('spruce'),
                       surf=B('snow'), fill=B('dirt'), cript='nieve', banner='light_blue'),
    }[kind]
    pal = cfg['pal']
    foundation(b, 1, 1, S - 2, S - 2, G, 4, cfg['surf'], cfg['fill'])
    # muralla
    W0, W1 = 2, S - 3
    for x in range(W0, W1 + 1):
        for z in (W0, W1):
            b.fill(x, G + 1, z, x, G + 4, z, cfg['wall'])
            b.set(x, G + 5, z, cfg['wtop'] if x % 2 == 0 else AIR)
    for z in range(W0, W1 + 1):
        for x in (W0, W1):
            b.fill(x, G + 1, z, x, G + 4, z, cfg['wall'])
            b.set(x, G + 5, z, cfg['wtop'] if z % 2 == 0 else AIR)
    # puertas (norte y sur)
    for z in (W0, W1):
        clear(b, c - 2, G + 1, z, c + 2, G + 4, z)
        for x in (c - 3, c + 3):
            b.fill(x, G + 1, z, x, G + 7, z, cfg['tower'])
            b.set(x, G + 8, z, lantern())
            b.banner(x, G + 5, z + (1 if z == W1 else -1), 'south' if z == W1 else 'north', cfg['banner'])
        b.fill(c - 2, G + 6, z, c + 2, G + 7, z, cfg['tower'])
        b.fill(c - 2, G + 5, z, c + 2, G + 5, z, slab(cfg['roof'] if cfg['roof'] != 'smooth_sandstone' else 'smooth_sandstone', top=True))
    # torres de esquina
    for (tx, tz) in ((W0 + 1, W0 + 1), (W1 - 1, W0 + 1), (W0 + 1, W1 - 1), (W1 - 1, W1 - 1)):
        round_tower(b, tx, tz, G + 1, 2, 9, cfg['tower'], roof_mat=None, cren=cfg['wtop'], floor=pal['floor'])
        b.mob(tx, G + 10, tz, 'minecraft:villager_v2')
    # calles principales (cruz) y plaza
    for x in range(W0 + 1, W1):
        for dz in (-1, 0, 1): b.set(x, G, c + dz, rng.choice(cfg['ground']))
    for z in range(W0 + 1, W1):
        for dx in (-1, 0, 1): b.set(c + dx, G, z, rng.choice(cfg['ground']))
    for x in range(c - 6, c + 7):
        for z in range(c - 6, c + 7):
            if (x - c) ** 2 + (z - c) ** 2 <= 40: b.set(x, G, z, rng.choice(cfg['ground']))
    # pozo con techo
    b.walls(c - 2, G + 1, c - 2, c + 2, G + 1, c + 2, pal['base'])
    clear(b, c - 1, G - 4, c - 1, c + 1, G + 1, c + 1)
    b.fill(c - 1, G - 4, c - 1, c + 1, G - 1, c + 1, WATER)
    b.fill(c - 1, G - 5, c - 1, c + 1, G - 5, c + 1, pal['base'])
    for (x, z) in ((c - 2, c - 2), (c + 2, c - 2), (c - 2, c + 2), (c + 2, c + 2)):
        b.fill(x, G + 2, z, x, G + 4, z, pal['table'])
    hip_roof(b, c - 2, c - 2, c + 2, c + 2, G + 5, cfg['roof'] if cfg['roof'] != 'smooth_sandstone' else 'smooth_sandstone', overhang=1)
    b.set(c, G + 5, c, B('bell', attachment='hanging', direction=0) if False else B('iron_chain', pillar_axis='y'))
    b.set(c, G + 4, c, lantern(hanging=True))
    # campana en poste
    b.fill(c + 5, G + 1, c + 5, c + 5, G + 3, c + 5, pal['table'])
    b.simple_be(c + 5, G + 4, c + 5, B('bell', attachment='standing', direction=0), 'Bell')
    for (x, z) in ((c - 6, c), (c + 6, c), (c, c - 6), (c, c + 6)):
        lamp_post(b, x + (1 if x > c else -1 if x < c else 2), G + 1, z + (1 if z > c else -1 if z < c else 2), pal['table'])
    # parcelas: 4 cuadrantes
    quads = [(W0 + 3, W0 + 3), (c + 4, W0 + 3), (W0 + 3, c + 4), (c + 4, c + 4)]
    houses = []
    # cuadrante NO: casa grande + capilla
    qx, qz = quads[0]
    timber_house(b, rng, qx, G, qz, 11, 9, 2, pal, door_side='south', inside='house')
    chapel_x, chapel_z = qx + 13, qz
    timber_house(b, rng, chapel_x, G, chapel_z, 9, 11, 1, pal, door_side='east', inside='chapel', roof_axis='z')
    # torre campanario de la capilla
    b.fill(chapel_x + 3, G + 5, chapel_z + 4, chapel_x + 5, G + 12, chapel_z + 6, cfg['tower'])
    clear(b, chapel_x + 4, G + 9, chapel_z + 4, chapel_x + 4, G + 11, chapel_z + 6)
    clear(b, chapel_x + 3, G + 9, chapel_z + 5, chapel_x + 5, G + 11, chapel_z + 5)
    hip_roof(b, chapel_x + 3, chapel_z + 4, chapel_x + 5, chapel_z + 6, G + 13, cfg['roof'] if cfg['roof'] != 'smooth_sandstone' else 'smooth_sandstone', overhang=1)
    b.simple_be(chapel_x + 4, G + 11, chapel_z + 5, B('bell', attachment='hanging', direction=0), 'Bell')
    # cripta bajo la capilla
    cy = G - 7
    cx0, cz0 = chapel_x, chapel_z
    b.fill(cx0, cy - 1, cz0, cx0 + 8, cy + 4, cz0 + 10, B('stone_bricks'))
    b.mix(cx0, cy - 1, cz0, cx0 + 8, cy + 4, cz0 + 10, rng, [(B('stone_bricks'), 4), (B('mossy_stone_bricks'), 2), (B('cracked_stone_bricks'), 1)], only_existing=True)
    clear(b, cx0 + 1, cy, cz0 + 1, cx0 + 7, cy + 3, cz0 + 9)
    for yy in range(cy, G + 1):
        b.set(cx0 + 1, yy, cz0 + 1, B('ladder', facing_direction=FACE6['south']))
    b.set(cx0 + 1, G, cz0 + 1, trapdoor('spruce', 'south'))
    b.spawner(cx0 + 4, cy, cz0 + 6, cfg['cript'])
    b.chest(cx0 + 7, cy, cz0 + 9, 'west', 'aldea_cripta')
    for (x, z) in ((cx0 + 2, cz0 + 8), (cx0 + 6, cz0 + 3)):
        b.skull(x, cy, z)
    b.set(cx0 + 4, cy + 3, cz0 + 3, lantern(hanging=True, soul=True)); b.set(cx0 + 4, cy + 3, cz0 + 8, lantern(hanging=True, soul=True))
    # cuadrante NE: herrería + casa
    qx, qz = quads[1]
    timber_house(b, rng, qx, G, qz, 9, 9, 1, pal, door_side='west', inside='smith')
    timber_house(b, rng, qx + 11, G, qz, 9, 11, 2, pal, door_side='south', inside='house', roof_axis='z')
    # cuadrante SO: taberna + granja
    qx, qz = quads[2]
    timber_house(b, rng, qx, G, qz, 13, 9, 2, pal, door_side='east', inside='tavern')
    for i, crop in enumerate(cfg['crop'][:2]):
        farm(b, rng, qx + i * 10, qz + 11, 9, 9, G, crop, log(pal['log'], 'x'))
    # cuadrante SE: biblioteca + almacén + casa pequeña
    qx, qz = quads[3]
    timber_house(b, rng, qx, G, qz, 9, 9, 2, pal, door_side='north', inside='library')
    timber_house(b, rng, qx + 11, G, qz, 9, 9, 1, pal, door_side='north', inside='storage')
    timber_house(b, rng, qx + 5, G, qz + 12, 9, 9, 1, pal, door_side='north', inside='house')
    # árboles y faroles en espacios libres
    for _ in range(14):
        x, z = rng.randrange(W0 + 3, W1 - 2), rng.randrange(W0 + 3, W1 - 2)
        if all(b.get(x + dx, G + 1, z + dz) is None for dx in range(-2, 3) for dz in range(-2, 3)) and b.get(x, G, z) is cfg['surf']:
            tree(b, rng, x, G + 1, z, cfg['logb'], cfg['leaf'], h=rng.randint(4, 6), r=2)
    # aldeanos y golem
    for (x, z) in ((c - 4, c + 3), (c + 3, c - 4), (c + 4, c + 4), (c - 3, c - 4), (c, c + 10), (c - 10, c)):
        b.mob(x, G + 1, z, 'minecraft:villager_v2')
    b.mob(c + 8, G + 1, c - 8, 'minecraft:iron_golem')
    b.mob(c - 8, G + 1, c + 8, 'minecraft:cat')
    return b, G

# ------------------------------------------------------------------ TANDA 2
def shell(b, x0, y0, z0, x1, y1, z1, wallb, floorb=None, ceilb=None):
    """Caja hueca: paredes, suelo y techo; interior vaciado (aire explícito)."""
    b.fill(x0, y0, z0, x1, y1, z1, wallb)
    if floorb: b.fill(x0, y0, z0, x1, y0, z1, floorb)
    if ceilb: b.fill(x0, y1, z0, x1, y1, z1, ceilb)
    clear(b, x0 + 1, y0 + 1, z0 + 1, x1 - 1, y1 - 1, z1 - 1)

def build_trial_chambers(rng):
    """Cámaras del Desafío: atrio central de 2 niveles con 4 generadores, 4 pasillos con dispensadores
    y 4 cámaras laterales temáticas (cuerpo a cuerpo, distancia, breeze y pequeños)."""
    S = 69; c = S // 2
    b = Build(S, 26, S)
    TB, PT, CT = B('tuff_bricks'), B('polished_tuff'), B('chiseled_tuff')
    CU, GR = B('waxed_cut_copper'), B('waxed_copper_grate')
    bulb = B('waxed_copper_bulb', lit=True, powered_bit=False)
    walls_mix = [(TB, 6), (B('chiseled_tuff_bricks'), 1), (PT, 1)]
    def deco_room(x0, y0, z0, x1, y1, z1):
        shell(b, x0, y0, z0, x1, y1, z1, TB, PT, GR)
        b.mix(x0, y0 + 1, z0, x1, y1 - 1, z1, rng, walls_mix, only_existing=False)
        clear(b, x0 + 1, y0 + 1, z0 + 1, x1 - 1, y1 - 1, z1 - 1)
        for x in range(x0 + 1, x1):
            for z in range(z0 + 1, z1):
                if (x + z) % 2 == 0: b.set(x, y0, z, CT if (x // 2 + z // 2) % 2 else PT)
        # franja de cobre en las paredes
        for x in range(x0, x1 + 1):
            b.set(x, y0 + 3, z0, CU); b.set(x, y0 + 3, z1, CU)
        for z in range(z0, z1 + 1):
            b.set(x0, y0 + 3, z, CU); b.set(x1, y0 + 3, z, CU)
        for (x, z) in ((x0 + 2, z0 + 2), (x1 - 2, z0 + 2), (x0 + 2, z1 - 2), (x1 - 2, z1 - 2)):
            b.set(x, y1, z, bulb)
    # atrio central (21x21, 13 de alto, con balcón)
    A0, A1 = c - 10, c + 10
    deco_room(A0, 2, A0, A1, 16, A1)
    b.fill(A0 + 1, 8, A0 + 1, A1 - 1, 8, A1 - 1, B('polished_tuff_slab', vertical_half='top'))
    clear(b, A0 + 5, 8, A0 + 5, A1 - 5, 8, A1 - 5)           # hueco central del balcón
    for x in range(A0 + 4, A1 - 3):
        for z in (A0 + 4, A1 - 4): b.set(x, 9, z, B('waxed_copper_grate'))
    for z in range(A0 + 4, A1 - 3):
        for x in (A0 + 4, A1 - 4): b.set(x, 9, z, B('waxed_copper_grate'))
    for (x, z) in ((A0 + 4, A0 + 4), (A1 - 4, A0 + 4), (A0 + 4, A1 - 4), (A1 - 4, A1 - 4)):
        b.fill(x, 3, z, x, 15, z, B('chiseled_tuff_bricks'))
    for yy in range(3, 9): b.set(A0 + 1, yy, c + 6, B('ladder', facing_direction=FACE6['east']))
    # 4 generadores en el atrio (abajo) + 2 en el balcón
    b.spawner(c - 4, 3, c, 'trial_melee'); b.spawner(c + 4, 3, c, 'trial_ranged')
    b.spawner(c, 3, c - 4, 'trial_small'); b.spawner(c, 9, A0 + 2, 'trial_breeze')
    b.set(c, 2, c, B('waxed_chiseled_copper')); b.set(c, 3, c, B('heavy_core'))
    for (x, z) in ((A0 + 2, A0 + 2), (A1 - 2, A1 - 2)):
        b.chest(x, 3, z, 'south', 'camaras')
    for (x, z) in ((A1 - 2, A0 + 2), (A0 + 2, A1 - 2), (c + 3, A1 - 2)):
        b.simple_be(x, 3, z, B('decorated_pot', direction=0), 'DecoratedPot', LootTable=f'loot_tables/{NS}/camaras_vasija.json')
    # pasillos (5 ancho, 5 alto) hacia 4 cámaras
    rooms = {'north': (c, 6), 'south': (c, S - 7), 'west': (6, c), 'east': (S - 7, c)}
    themes = {'north': 'trial_melee', 'south': 'trial_ranged', 'west': 'trial_breeze', 'east': 'trial_small'}
    for side, (rx, rz) in rooms.items():
        dx, dz = VEC[side]
        # pasillo
        if dz:
            za, zb = sorted((rz - 6 * dz, (A1 if dz > 0 else A0)))
            shell(b, c - 3, 2, za, c + 3, 8, zb, TB, PT, GR)
            clear(b, c - 2, 3, za, c + 2, 7, zb)
            for z in range(za + 2, zb - 1, 4):
                b.set(c - 3, 5, z, B('dispenser', facing_direction=FACE6['east']))
                b.simple_be(c - 3, 5, z, B('dispenser', facing_direction=FACE6['east']), 'Dispenser', Items=[], LootTable=f'loot_tables/{NS}/camaras_dispensador.json')
                b.set(c + 3, 6, z, bulb)
        else:
            xa, xb = sorted((rx - 6 * dx, (A1 if dx > 0 else A0)))
            shell(b, xa, 2, c - 3, xb, 8, c + 3, TB, PT, GR)
            clear(b, xa, 3, c - 2, xb, 7, c + 2)
            for x in range(xa + 2, xb - 1, 4):
                b.simple_be(x, 5, c - 3, B('dispenser', facing_direction=FACE6['south']), 'Dispenser', Items=[], LootTable=f'loot_tables/{NS}/camaras_dispensador.json')
                b.set(x, 6, c + 3, bulb)
        # cámara 13x13
        deco_room(rx - 6, 2, rz - 6, rx + 6, 10, rz + 6)
        # abrir uniones
        if dz:
            clear(b, c - 2, 3, min(rz - 6 * dz, rz) if dz < 0 else rz - 6, c + 2, 7, rz + 6 if dz < 0 else rz - 6)
            clear(b, c - 2, 3, rz - 6 * dz, c + 2, 7, rz - 6 * dz)
            clear(b, c - 2, 3, (A0 if dz < 0 else A1), c + 2, 7, (A0 if dz < 0 else A1))
        else:
            clear(b, rx - 6 * dx, 3, c - 2, rx - 6 * dx, 7, c + 2)
            clear(b, (A0 if dx < 0 else A1), 3, c - 2, (A0 if dx < 0 else A1), 7, c + 2)
        b.spawner(rx, 3, rz, themes[side])
        b.spawner(rx + 3 * (1 if dz else 0), 3, rz + 3 * (1 if dx else 0), themes[side])
        b.chest(rx + 4 * dx + (4 if dz else 0), 3, rz + 4 * dz + (4 if dx else 0), OPP[side], 'camaras_tesoro')
        b.chest(rx + 4 * dx - (4 if dz else 0), 3, rz + 4 * dz - (4 if dx else 0), OPP[side], 'camaras')
        b.set(rx, 2, rz, B('waxed_oxidized_cut_copper'))
    return b, 0

def build_fortaleza_nether(rng):
    """Fortaleza del Nether mayor: torre central con sala de blazes, 4 puentes con corredores techados,
    4 torres con generadores de esqueletos wither, jardín de verrugas y pilares hasta abajo."""
    S = 71; c = S // 2; D = 22  # D = altura del piso de los puentes dentro de la plantilla
    b = Build(S, D + 24, S)
    NB, RB = B('nether_brick'), B('red_nether_brick')
    fence = B('nether_brick_fence')
    mixnb = [(NB, 8), (B('cracked_nether_bricks'), 2), (B('chiseled_nether_bricks'), 0.5)]
    def pillar(x, z, w=2):
        for xx in range(x, x + w):
            for zz in range(z, z + w):
                b.fill(xx, 0, zz, xx, D - 1, zz, NB)
    # puentes en cruz (ancho 5) con corredor techado en la mitad
    for side in ('north', 'south', 'east', 'west'):
        dx, dz = VEC[side]
        for k in range(10, c - 5):
            x, z = c + dx * k, c + dz * k
            for w in range(-2, 3):
                bx, bz = (x + w, z) if dz else (x, z + w)
                b.set(bx, D, bz, NB); b.set(bx, D - 1, bz, NB if abs(w) < 2 else stairs('nether_brick', side if False else ('east' if w < 0 else 'west') if dz else ('south' if w < 0 else 'north'), True))
                if abs(w) == 2: b.set(bx, D + 1, bz, fence)
                for yy in range(D + 1, D + 5):
                    if abs(w) < 2: b.set(bx, yy, bz, AIR)
            if k % 8 == 2: pillar(x - 1, z - 1)
            # corredor techado
            if 14 <= k <= 24:
                for w in (-2, 2):
                    bx, bz = (x + w, z) if dz else (x, z + w)
                    b.fill(bx, D + 1, bz, bx, D + 4, bz, NB)
                    if k % 3 == 0: b.set(bx, D + 2, bz, fence); b.set(bx, D + 3, bz, fence)
                for w in range(-2, 3):
                    bx, bz = (x + w, z) if dz else (x, z + w)
                    b.set(bx, D + 5, bz, NB)
                if k % 4 == 0:
                    b.set(x, D + 4, z, lantern(hanging=True, soul=True)) if False else b.set(x, D + 4, z, B('soul_lantern', hanging=True))
        # torre del extremo (9x9) con generador de esqueletos wither
        tx, tz = c + dx * (c - 6), c + dz * (c - 6)
        shell(b, tx - 4, D, tz - 4, tx + 4, D + 10, tz + 4, NB, NB, NB)
        b.mix(tx - 4, D + 1, tz - 4, tx + 4, D + 9, tz + 4, rng, mixnb, only_existing=False)
        clear(b, tx - 3, D + 1, tz - 3, tx + 3, D + 9, tz + 3)
        for x in range(tx - 4, tx + 5):
            for z in range(tz - 4, tz + 5):
                if x in (tx - 4, tx + 4) or z in (tz - 4, tz + 4):
                    b.set(x, D + 11, z, fence if (x + z) % 2 else NB)
                if b.get(x, D + 10, z) is None: b.set(x, D + 10, z, NB)
        for x in range(tx - 3, tx + 4):
            for z in range(tz - 3, tz + 4):
                b.fill(x, 0, z, x, D - 1, z, NB) if (x in (tx - 3, tx + 3) and z in (tz - 3, tz + 3)) else None
        clear(b, tx - 1 if dz else tx - 4 * dx, D + 1, tz - 4 * dz if dz else tz - 1, tx + 1 if dz else tx - 4 * dx, D + 3, tz - 4 * dz if dz else tz + 1)
        for k2 in (-2, 2):
            for yy in (D + 3, D + 4):
                if dz: b.set(tx + k2, yy, tz + 4 * dz, fence)
                else: b.set(tx + 4 * dx, yy, tz + k2, fence)
        b.spawner(tx, D + 1, tz, 'fortaleza')
        b.chest(tx + 2 * (1 if dz else 0) + 2 * dx, D + 1, tz + 2 * (1 if dx else 0) + 2 * dz, OPP[side], 'fortaleza_nether')
        b.set(tx, D + 9, tz, B('soul_lantern', hanging=True))
    # torre central (19x19, 3 pisos)
    K0, K1 = c - 9, c + 9
    for x in range(K0, K1 + 1):
        for z in range(K0, K1 + 1):
            b.fill(x, D - 6, z, x, D - 1, z, NB)
    for f in range(3):
        fy = D + f * 7
        shell(b, K0, fy, K0, K1, fy + 7, K1, NB, RB if f else NB, NB)
        b.mix(K0, fy + 1, K0, K1, fy + 6, K1, rng, mixnb)
        clear(b, K0 + 1, fy + 1, K0 + 1, K1 - 1, fy + 6, K1 - 1)
        for k in range(K0 + 3, K1 - 2, 3):
            for (x, z) in ((k, K0), (k, K1), (K0, k), (K1, k)):
                b.set(x, fy + 3, z, fence); b.set(x, fy + 4, z, fence)
        for (x, z) in ((K0 + 2, K0 + 2), (K1 - 2, K0 + 2), (K0 + 2, K1 - 2), (K1 - 2, K1 - 2)):
            b.set(x, fy + 6, z, B('soul_lantern', hanging=True))
    for yy in range(D + 1, D + 21): b.set(K1 - 1, yy, c + 4, B('ladder', facing_direction=FACE6['west']))
    for side in ('north', 'south', 'east', 'west'):
        dx, dz = VEC[side]
        ex, ez = c + dx * 9, c + dz * 9
        if dz: clear(b, ex - 1, D + 1, ez, ex + 1, D + 3, ez)
        else: clear(b, ex, D + 1, ez - 1, ex, D + 3, ez + 1)
    # almenas arriba
    top = D + 21
    for x in range(K0, K1 + 1):
        for z in range(K0, K1 + 1):
            if x in (K0, K1) or z in (K0, K1):
                b.set(x, top + 1, z, NB if (x + z) % 2 else fence)
    # piso 1: jardín de verrugas; piso 2: sala de blazes; piso 3: tesoro
    for x in range(c - 5, c + 6):
        for z in range(c - 5, c + 6):
            if abs(x - c) > 1 and abs(z - c) > 1:
                b.set(x, D, z, B('soul_sand')); b.set(x, D + 1, z, B('nether_wart', age=3))
    b.spawner(c, D + 8, c, 'nether')
    b.spawner(c - 5, D + 8, c - 5, 'fortaleza'); b.spawner(c + 5, D + 8, c + 5, 'fortaleza')
    b.chest(c, D + 15, c - 6, 'south', 'fortaleza_nether_tesoro'); b.chest(c, D + 15, c + 6, 'north', 'fortaleza_nether_tesoro')
    b.set(c, D + 14, c, B('gold_block')); b.skull(c, D + 15, c, 'wither_skeleton_skull')
    return b, D

def build_bastion(rng):
    """Bastión mayor: fortaleza de piedra negra con muralla, 4 torres, establos de hoglins,
    puentes y una cámara del tesoro central con oro y un foso de lava."""
    S = 61; c = S // 2; G = 8
    b = Build(S, G + 30, S)
    BS, PB = B('blackstone'), B('polished_blackstone_bricks')
    mix = [(PB, 6), (B('cracked_polished_blackstone_bricks'), 3), (BS, 2), (B('gilded_blackstone'), 0.4)]
    # base maciza
    for x in range(2, S - 2):
        for z in range(2, S - 2):
            d = max(abs(x - c), abs(z - c))
            if d <= 27: b.fill(x, 0, z, x, G, z, BS if rng.random() < 0.7 else B('basalt', pillar_axis='y'))
    # muralla exterior
    b.walls(4, G + 1, 4, S - 5, G + 9, S - 5, PB)
    b.mix(4, G + 1, 4, S - 5, G + 9, S - 5, rng, mix, only_existing=True)
    clear(b, 5, G + 1, 5, S - 6, G + 9, S - 6)
    crenellate(b, 4, 4, S - 5, S - 5, G + 10, B('polished_blackstone_brick_wall', wall_post_bit=True))
    for x in range(5, S - 5):
        b.set(x, G + 7, 5, slab('polished_blackstone_brick', True)); b.set(x, G + 7, S - 6, slab('polished_blackstone_brick', True))
    for z in range(5, S - 5):
        b.set(5, G + 7, z, slab('polished_blackstone_brick', True)); b.set(S - 6, G + 7, z, slab('polished_blackstone_brick', True))
    clear(b, c - 2, G + 1, S - 5, c + 2, G + 5, S - 5)
    # torres de esquina
    for (tx, tz) in ((7, 7), (S - 8, 7), (7, S - 8), (S - 8, S - 8)):
        shell(b, tx - 3, G, tz - 3, tx + 3, G + 16, tz + 3, PB, BS, PB)
        b.mix(tx - 3, G + 1, tz - 3, tx + 3, G + 15, tz + 3, rng, mix)
        clear(b, tx - 2, G + 1, tz - 2, tx + 2, G + 15, tz + 2)
        crenellate(b, tx - 3, tz - 3, tx + 3, tz + 3, G + 17, B('blackstone_wall', wall_post_bit=True), step=2)
        for yy in range(G + 1, G + 16): b.set(tx, yy, tz - 2, B('ladder', facing_direction=FACE6['south']))
        b.set(tx, G + 16, tz - 2, AIR)
        b.chest(tx + 2, G + 1, tz + 2, 'north', 'bastion')
        clear(b, tx + (3 if tx < c else -3), G + 1, tz, tx + (3 if tx < c else -3), G + 2, tz)
    # establos de hoglins (oeste y este)
    for sx in (12, S - 18):
        shell(b, sx, G, c - 8, sx + 6, G + 6, c - 2, PB, B('soul_soil'), PB)
        b.fill(sx + 1, G + 1, c - 7, sx + 5, G + 1, c - 3, B('crimson_roots'))
        clear(b, sx + 3, G + 1, c - 2, sx + 3, G + 3, c - 2)
        b.fill(sx + 2, G + 1, c - 2, sx + 4, G + 3, c - 2, B('iron_bars'))
        b.mob(sx + 3, G + 1, c - 5, 'minecraft:hoglin')
        b.mob(sx + 3, G + 1, c - 4, 'minecraft:hoglin')
    # cámara del tesoro central con foso de lava
    for x in range(c - 11, c + 12):
        for z in range(c - 11, c + 12):
            d = max(abs(x - c), abs(z - c))
            if 9 <= d <= 11: b.set(x, G, z, B('lava', liquid_depth=0)); b.set(x, G - 1, z, BS)
    for side in ('north', 'south', 'east', 'west'):
        dx, dz = VEC[side]
        for k in range(9, 12):
            for w in (-1, 0, 1):
                x, z = (c + w, c + dz * k) if dz else (c + dx * k, c + w)
                b.set(x, G, z, PB)
    T0, T1 = c - 8, c + 8
    shell(b, T0, G, T0, T1, G + 14, T1, PB, BS, PB)
    b.mix(T0, G + 1, T0, T1, G + 13, T1, rng, mix)
    clear(b, T0 + 1, G + 1, T0 + 1, T1 - 1, G + 13, T1 - 1)
    for side in ('north', 'south', 'east', 'west'):
        dx, dz = VEC[side]
        ex, ez = c + dx * 8, c + dz * 8
        if dz: clear(b, ex - 1, G + 1, ez, ex + 1, G + 4, ez)
        else: clear(b, ex, G + 1, ez - 1, ex, G + 4, ez + 1)
    # pirámide de oro y piedra dorada
    for i in range(4):
        for x in range(c - 3 + i, c + 4 - i):
            for z in range(c - 3 + i, c + 4 - i):
                b.set(x, G + 1 + i, z, B('gold_block') if i == 3 or rng.random() < 0.35 else B('gilded_blackstone'))
    b.spawner(c - 5, G + 1, c - 5, 'bastion'); b.spawner(c + 5, G + 1, c + 5, 'bastion')
    b.spawner(c + 5, G + 1, c - 5, 'bastion')
    for (x, z, f) in ((c - 6, c, 'east'), (c + 6, c, 'west'), (c, c - 6, 'south')):
        b.chest(x, G + 1, z, f, 'bastion_tesoro')
    b.set(c, G + 13, c, B('chain', pillar_axis='y')); b.set(c, G + 12, c, B('soul_lantern', hanging=True))
    for (x, z) in ((T0 + 1, T0 + 1), (T1 - 1, T0 + 1), (T0 + 1, T1 - 1), (T1 - 1, T1 - 1)):
        b.fill(x, G + 1, z, x, G + 13, z, B('basalt', pillar_axis='y'))
        b.set(x, G + 5, z, B('gilded_blackstone'))
    # puentes del patio y lava decorativa
    for (x, z) in ((c - 15, c + 12), (c + 15, c + 12)):
        b.set(x, G, z, B('magma')); b.set(x, G + 1, z, B('soul_fire'))
    for (x, z) in ((c - 4, c + 14), (c + 4, c + 14), (c, c + 18)):
        b.mob(x, G + 1, z, 'minecraft:piglin')
    b.mob(c, G + 1, c + 10, 'minecraft:piglin_brute')
    return b, G

def build_ciudad_end(rng):
    """Ciudad del End flotante: isla propia de piedra del End con 3 torres de purpur unidas por puentes,
    salas con generadores de shulkers y una plataforma con el marco de los élitros."""
    S = 57; c = S // 2; I = 16  # nivel de la superficie de la isla
    b = Build(S, I + 44, S)
    PU, PP = B('purpur_block', pillar_axis='y'), B('purpur_pillar', pillar_axis='y')
    EB = B('end_bricks')
    # isla flotante (cono invertido)
    for x in range(S):
        for z in range(S):
            d = ((x - c) ** 2 + (z - c) ** 2) ** 0.5 + rng.uniform(-1.5, 1.5)
            if d < 26:
                depth = int((26 - d) * 0.6) + 1
                for y in range(max(0, I - depth), I + 1): b.set(x, y, z, B('end_stone'))
    for _ in range(10):
        x, z = rng.randrange(6, S - 6), rng.randrange(6, S - 6)
        if b.get(x, I, z) and ((x - c) ** 2 + (z - c) ** 2) > 200:
            for yy in range(I + 1, I + rng.randint(2, 5)): b.set(x, yy, z, B('chorus_plant'))
    def tower(cx, cz, floors, r=4):
        for f in range(floors):
            fy = I + 1 + f * 6
            shell(b, cx - r, fy - 1, cz - r, cx + r, fy + 5, cz + r, PU, EB, PU)
            for (x, z) in ((cx - r, cz - r), (cx + r, cz - r), (cx - r, cz + r), (cx + r, cz + r)):
                b.fill(x, fy - 1, z, x, fy + 5, z, PP)
            for k in (cx - 1, cx + 1):
                for (x, z) in ((k, cz - r), (k, cz + r)):
                    b.set(x, fy + 2, z, B('magenta_stained_glass')); b.set(x, fy + 3, z, B('magenta_stained_glass'))
            for k in (cz - 1, cz + 1):
                for (x, z) in ((cx - r, k), (cx + r, k)):
                    b.set(x, fy + 2, z, B('magenta_stained_glass')); b.set(x, fy + 3, z, B('magenta_stained_glass'))
            b.set(cx, fy + 4, cz, B('end_rod', facing_direction=0))
            for x in range(cx - r - 1, cx + r + 2):
                b.set(x, fy + 5, cz - r - 1, stairs('purpur', 'south', True)); b.set(x, fy + 5, cz + r + 1, stairs('purpur', 'north', True))
            for z in range(cz - r, cz + r + 1):
                b.set(cx - r - 1, fy + 5, z, stairs('purpur', 'east', True)); b.set(cx + r + 1, fy + 5, z, stairs('purpur', 'west', True))
            for yy in range(fy, fy + 6): b.set(cx + r - 1, yy, cz, B('ladder', facing_direction=FACE6['west']))
        top = I + floors * 6
        hip_roof(b, cx - r, cz - r, cx + r, cz + r, top + 1, 'purpur', overhang=1, cap=EB)
        b.set(cx, top + 1 + r + 2, cz, B('end_rod', facing_direction=1))
        clear(b, cx - 1, I + 1, cz + r, cx + 1, I + 3, cz + r)
        return top
    t1 = tower(c, c, 6, 5)
    t2 = tower(c - 15, c + 8, 4)
    t3 = tower(c + 15, c + 8, 3)
    # puentes de purpur entre torres (en el piso 2)
    by = I + 7
    for x in range(c - 11, c - 4):
        for w in (-1, 0, 1): b.set(x, by - 1, c + 8 + w if x > c - 9 else c + 8 + w, PU)
        b.set(x, by, c + 6, B('purpur_slab')); b.set(x, by, c + 10, B('purpur_slab'))
    for x in range(c + 6, c + 12):
        for w in (-1, 0, 1): b.set(x, by - 1, c + 8 + w, PU)
        b.set(x, by, c + 6, B('purpur_slab')); b.set(x, by, c + 10, B('purpur_slab'))
    # plataforma de los élitros (sur), con marco y cofres
    for x in range(c - 6, c + 7):
        for z in range(c + 18, c + 25):
            b.set(x, I + 1, z, PU)
    for x in range(c - 6, c + 7):
        b.set(x, I + 2, c + 24, stairs('purpur', 'north', True)) if x % 2 else b.set(x, I + 2, c + 24, PU)
    b.fill(c - 1, I + 2, c + 23, c + 1, I + 6, c + 23, PU)
    b.simple_be(c, I + 4, c + 22, B('frame', facing_direction=FACE6['north'], item_frame_map_bit=False, item_frame_photo_bit=False), 'ItemFrame',
                Item={'Name': 'minecraft:elytra', 'Count': tB(1), 'Damage': tS(0), 'WasPickedUp': tB(0)}, ItemRotation=tF(0.0), ItemDropChance=tF(1.0))
    b.skull(c, I + 7, c + 23, 'dragon_head')
    b.chest(c - 3, I + 2, c + 22, 'north', 'ciudad_end_tesoro'); b.chest(c + 3, I + 2, c + 22, 'north', 'ciudad_end_tesoro')
    # generadores y cofres en las torres
    b.spawner(c, I + 1 + 2 * 6, c, 'end'); b.spawner(c, I + 1 + 4 * 6, c, 'end')
    b.spawner(c - 15, I + 1 + 6, c + 8, 'end'); b.spawner(c + 15, I + 1 + 6, c + 8, 'end')
    b.chest(c - 3, I + 1 + 5 * 6, c - 3, 'south', 'ciudad_end_tesoro'); b.chest(c - 3, I + 1 + 6, c - 3, 'south', 'ciudad_end')
    b.chest(c - 17, I + 1 + 3 * 6, c + 6, 'south', 'ciudad_end'); b.chest(c + 13, I + 1, c + 6, 'south', 'ciudad_end')
    for (x, z) in ((c - 4, c - 4), (c + 4, c + 4)):
        b.mob(x, I + 1 + 3 * 6, z, 'minecraft:shulker')
    return b, I

def build_mansion(rng):
    """Mansión del Bosque mayor: 3 pisos de roble oscuro con alas, patio, salón de banquetes, biblioteca,
    capilla, dormitorios, arena de entrenamiento y sala del tesoro en el ático."""
    W, Dp = 59, 47; G = 5
    b = Build(W, G + 32, Dp)
    pal = P(base=B('cobblestone'), wall=B('dark_oak_planks'), floor=B('birch_planks'), log='dark_oak_log', roof='dark_oak',
            gable=B('dark_oak_planks'), pane=B('glass_pane'), door='dark_oak', step=B('cobblestone_slab', vertical_half='top'),
            table=B('dark_oak_fence'))
    foundation(b, 1, 1, W - 2, Dp - 2, G, 4, B('cobblestone'), B('cobblestone'))
    x0, z0, x1, z1 = 3, 3, W - 4, Dp - 4
    fh = 6
    for f in range(3):
        fy = G + f * fh
        b.fill(x0, fy, z0, x1, fy, z1, pal['floor'] if f else B('cobblestone'))
        b.walls(x0, fy + 1, z0, x1, fy + fh, z1, pal['wall'])
        clear(b, x0 + 1, fy + 1, z0 + 1, x1 - 1, fy + fh - 1, z1 - 1)
        # vigas y postes
        for x in range(x0, x1 + 1, 6):
            b.fill(x, fy + 1, z0, x, fy + fh, z0, log('dark_oak_log')); b.fill(x, fy + 1, z1, x, fy + fh, z1, log('dark_oak_log'))
        for z in range(z0, z1 + 1, 6):
            b.fill(x0, fy + 1, z, x0, fy + fh, z, log('dark_oak_log')); b.fill(x1, fy + 1, z, x1, fy + fh, z, log('dark_oak_log'))
        b.walls(x0, fy + fh, z0, x1, fy + fh, z1, log('dark_oak_log', 'x'))
        for z in range(z0, z1 + 1):
            b.set(x0, fy + fh, z, log('dark_oak_log', 'z')); b.set(x1, fy + fh, z, log('dark_oak_log', 'z'))
        # ventanas dobles entre postes
        for x in range(x0 + 2, x1 - 1, 6):
            for xx in (x, x + 2):
                for yy in (fy + 2, fy + 3, fy + 4):
                    b.set(xx, yy, z0, pal['pane']); b.set(xx, yy, z1, pal['pane'])
        for z in range(z0 + 2, z1 - 1, 6):
            for zz in (z, z + 2):
                for yy in (fy + 2, fy + 3, fy + 4):
                    b.set(x0, yy, zz, pal['pane']); b.set(x1, yy, zz, pal['pane'])
        # tabiques interiores: cuadrícula de habitaciones 12x10 con puertas
        for x in range(x0 + 12, x1, 12):
            b.fill(x, fy + 1, z0 + 1, x, fy + fh - 1, z1 - 1, B('dark_oak_planks') if f != 1 else B('white_wool') if False else B('dark_oak_planks'))
            for z in range(z0 + 5, z1, 10):
                clear(b, x, fy + 1, z, x, fy + 2, z + 1)
        for z in (z0 + 13, z1 - 13):
            b.fill(x0 + 1, fy + 1, z, x1 - 1, fy + fh - 1, z, B('dark_oak_planks'))
            for x in range(x0 + 6, x1, 12):
                clear(b, x, fy + 1, z, x + 1, fy + 2, z)
        # pasillo central alfombrado
        for x in range(x0 + 1, x1):
            for z in range(z0 + 14, z1 - 13):
                if f: b.set(x, fy, z, B('red_carpet') if False else pal['floor'])
                b.set(x, fy + 1, z, B('red_carpet')) if z in (z0 + 19, z0 + 20) and b.get(x, fy + 1, z) in (None, AIR) else None
        for x in range(x0 + 4, x1 - 2, 8):
            b.set(x, fy + fh - 1, (z0 + z1) // 2, lantern(hanging=True))
        # escaleras de mano entre pisos
        if f < 2:
            for yy in range(fy + 1, fy + fh + 1):
                b.set(x0 + 1, yy, (z0 + z1) // 2 + 1, B('ladder', facing_direction=FACE6['east']))  # entre ventanas
    # entrada (sur) con porche
    cx = (x0 + x1) // 2
    clear(b, cx - 1, G + 1, z1, cx + 1, G + 3, z1)
    b.door(cx, G + 1, z1, 'south', 'dark_oak')
    b.fill(cx - 4, G, z1 + 1, cx + 4, G, z1 + 3, B('cobblestone'))
    for x in (cx - 4, cx + 4):
        b.fill(x, G + 1, z1 + 3, x, G + 4, z1 + 3, log('dark_oak_log'))
    b.fill(cx - 4, G + 5, z1 + 1, cx + 4, G + 5, z1 + 3, slab('dark_oak'))
    b.banner(cx - 2, G + 4, z1 + 1, 'south', 'gray'); b.banner(cx + 2, G + 4, z1 + 1, 'south', 'gray')
    # techo a cuatro aguas con ático
    top = G + 3 * fh
    hip_roof(b, x0, z0, x1, z1, top + 1, 'dark_oak', overhang=1, cap=B('dark_oak_planks'))
    b.fill(x0 + 1, top, z0 + 1, x1 - 1, top, z1 - 1, B('dark_oak_planks'))
    clear(b, x0 + 4, top + 1, z0 + 4, x1 - 4, top + 3, z1 - 4)
    for yy in range(G + 2 * fh + 1, top + 2): b.set(x0 + 5, yy, (z0 + z1) // 2, B('ladder', facing_direction=FACE6['east']))
    b.set(x0 + 4, G + 2 * fh + 1, (z0 + z1) // 2, B('dark_oak_planks'))
    for yy in range(G + 2 * fh + 1, top + 2): b.set(x0 + 4, yy, (z0 + z1) // 2, B('dark_oak_planks'))
    # contenido por habitación
    rooms = []
    for f in range(3):
        fy = G + f * fh + 1
        for i, rx in enumerate(range(x0 + 1, x1, 12)):
            for (rz0, rz1) in ((z0 + 1, z0 + 12), (z1 - 12, z1 - 1)):
                rooms.append((f, rx, min(rx + 10, x1 - 1), rz0, rz1, fy))
    kinds = ['tavern', 'library', 'house', 'storage', 'smith', 'chapel', 'bedroom', 'library', 'bedroom', 'house']
    for n, (f, rx0, rx1, rz0, rz1, fy) in enumerate(rooms):
        k = kinds[n % len(kinds)]
        furnish(b, rng, rx0, fy, rz0, rx1, rz1, k, pal, door=None)
        if n % 4 == 1: b.spawner((rx0 + rx1) // 2, fy, (rz0 + rz1) // 2, 'mansion')
    # sala del tesoro en el ático
    b.spawner(cx, top + 1, (z0 + z1) // 2, 'mansion')
    for dx in (-4, 4): b.chest(cx + dx, top + 1, (z0 + z1) // 2, 'south', 'mansion_tesoro')
    b.set(cx, top + 1, (z0 + z1) // 2 + 3, B('diamond_block'))
    # jardín alrededor
    for _ in range(10):
        x, z = rng.choice([(rng.randrange(1, W - 1), rng.choice([1, Dp - 2])), (rng.choice([1, W - 2]), rng.randrange(1, Dp - 1))])
        tree(b, rng, x, G + 1, z, log('dark_oak_log'), leaves('dark_oak'), h=4, r=2)
    for (x, z) in ((cx - 3, z1 - 3), (cx + 3, z1 - 3), (cx, (z0 + z1) // 2)):
        b.mob(x, G + 1, z, 'minecraft:vindicator')
    b.mob(cx, G + 2 * fh + 1, z0 + 6, 'minecraft:evocation_illager')
    return b, G

DESIGNS = {
    'piramide_del_desierto': (build_piramide, 'Gran Pirámide del Desierto'),
    'templo_de_la_jungla': (build_templo_jungla, 'Templo Mayor de la Jungla'),
    'mansion_de_la_bruja': (build_cabana_bruja, 'Mansión de la Bruja'),
    'iglu': (build_iglu, 'Gran Iglú'),
    'fortaleza_saqueadora': (build_puesto, 'Fortaleza Saqueadora'),
    'oasis_del_desierto': (build_pozo, 'Oasis del Desierto'),
    'portal_en_ruinas': (build_portal, 'Gran Portal en Ruinas'),
    'aldea_llanura': (lambda r: build_aldea(r, 'llanura'), 'Aldea Fortificada (llanura)'),
    'aldea_desierto': (lambda r: build_aldea(r, 'desierto'), 'Aldea Fortificada (desierto)'),
    'aldea_sabana': (lambda r: build_aldea(r, 'sabana'), 'Aldea Fortificada (sabana)'),
    'aldea_taiga': (lambda r: build_aldea(r, 'taiga'), 'Aldea Fortificada (taiga)'),
    'aldea_nevada': (lambda r: build_aldea(r, 'nevada'), 'Aldea Fortificada (nevada)'),
    'camaras_del_desafio': (build_trial_chambers, 'Cámaras del Desafío'),
    'fortaleza_del_nether': (build_fortaleza_nether, 'Gran Fortaleza del Nether'),
    'bastion': (build_bastion, 'Gran Bastión'),
    'ciudad_del_end': (build_ciudad_end, 'Ciudad Flotante del End'),
    'mansion_del_bosque': (build_mansion, 'Gran Mansión del Bosque'),
}

# ============================================================== worldgen
def bt(tag, inc=True): return {'test': 'has_biome_tag', 'operator': '==' if inc else '!=', 'value': tag}
WORLDGEN = {
    # id: (filtro de biomas, terrain_adaptation, spacing, separation, salt, heightmap)
    'piramide_del_desierto': ([bt('desert')], 'beard_thin', 40, 16, 7710011, 'world_surface'),
    'templo_de_la_jungla': ([bt('jungle')], 'beard_thin', 36, 14, 7710012, 'world_surface'),
    'mansion_de_la_bruja': ([{'any_of': [bt('swamp'), bt('mangrove_swamp')]}], 'none', 32, 12, 7710013, 'world_surface'),
    'iglu': ([{'any_of': [bt('ice_plains'), {'all_of': [bt('taiga'), bt('cold')]}, bt('snowy_slopes'), bt('grove')]}], 'beard_thin', 32, 12, 7710014, 'world_surface'),
    'fortaleza_saqueadora': ([{'any_of': [{'all_of': [bt('plains'), bt('mutated', False)]}, bt('desert'), bt('savanna'), bt('taiga'), bt('meadow'), bt('cherry_grove'), bt('grove')]}], 'beard_thin', 44, 18, 7710015, 'world_surface'),
    'oasis_del_desierto': ([bt('desert')], 'beard_thin', 28, 10, 7710016, 'world_surface'),
    'portal_en_ruinas': ([{'all_of': [bt('overworld'), bt('ocean', False), bt('river', False), bt('beach', False)]}], 'beard_thin', 40, 15, 7710017, 'world_surface'),
    'aldea_llanura': ([{'any_of': [{'all_of': [bt('plains'), bt('mutated', False)]}, bt('meadow')]}], 'beard_thin', 40, 16, 7710018, 'world_surface'),
    'aldea_desierto': ([bt('desert')], 'beard_thin', 40, 16, 7710019, 'world_surface'),
    'aldea_sabana': ([{'all_of': [bt('savanna'), bt('plateau', False)]}], 'beard_thin', 40, 16, 7710020, 'world_surface'),
    'aldea_taiga': ([{'all_of': [bt('taiga'), bt('cold', False)]}], 'beard_thin', 40, 16, 7710021, 'world_surface'),
    'aldea_nevada': ([{'any_of': [bt('ice_plains'), {'all_of': [bt('taiga'), bt('cold')]}]}], 'beard_thin', 40, 16, 7710022, 'world_surface'),
    # (filtro, adaptación, spacing, separation, salt, heightmap, extras)
    'camaras_del_desafio': ([bt('ocean', False), bt('deep_dark', False)], 'encapsulate', 34, 12, 7710023, 'none',
                            {'dim': 'overworld', 'height': {'type': 'uniform', 'min': {'absolute': -40}, 'max': {'absolute': -20}}, 'step': 'underground_structures'}),
    'fortaleza_del_nether': ([], 'none', 27, 4, 7710024, 'none',
                             {'dim': 'nether', 'height': {'type': 'uniform', 'min': {'absolute': 26}, 'max': {'absolute': 46}}, 'step': 'underground_decoration'}),
    'bastion': ([bt('basalt_deltas', False)], 'none', 27, 4, 7710025, 'none',
                {'dim': 'nether', 'height': {'type': 'uniform', 'min': {'absolute': 22}, 'max': {'absolute': 30}}, 'step': 'surface_structures'}),
    'ciudad_del_end': ([], 'none', 20, 9, 7710026, 'none',
                       {'dim': 'the_end', 'height': {'type': 'uniform', 'min': {'absolute': 44}, 'max': {'absolute': 60}}, 'step': 'surface_structures'}),
    'mansion_del_bosque': ([bt('roofed')], 'beard_thin', 60, 20, 7710027, 'world_surface'),
}

# ============================================================== loot
def item(name, w=1, cmin=1, cmax=1, ench=None, data=None, potion=None, extra=None):
    e = {'type': 'item', 'name': 'minecraft:' + name, 'weight': w}
    f = []
    if cmax > 1 or cmin > 1: f.append({'function': 'set_count', 'count': {'min': cmin, 'max': cmax}})
    if ench == 'random': f.append({'function': 'enchant_randomly'})
    elif ench: f.append({'function': 'enchant_with_levels', 'levels': {'min': ench[0], 'max': ench[1]}, 'treasure': True})
    if potion: f.append({'function': 'set_potion', 'id': potion})
    if extra: f += extra
    if f: e['functions'] = f
    return e

def pool(rmin, rmax, entries): return {'rolls': {'min': rmin, 'max': rmax}, 'entries': entries}

COMMON = [item('bread', 4, 2, 5), item('iron_ingot', 4, 2, 6), item('gold_ingot', 3, 1, 4), item('emerald', 3, 1, 4),
          item('arrow', 3, 4, 12), item('torch', 3, 4, 12), item('coal', 3, 3, 8), item('golden_carrot', 2, 1, 4),
          item('book', 2, 1, 3, ench='random'), item('name_tag', 1), item('saddle', 1)]
RARE = [item('diamond', 3, 1, 3), item('golden_apple', 3, 1, 2), item('enchanted_golden_apple', 1),
        item('diamond_sword', 2, ench=(20, 35)), item('diamond_chestplate', 1, ench=(20, 35)), item('book', 3, ench=(25, 40)),
        item('emerald_block', 1), item('experience_bottle', 3, 3, 8), item('netherite_scrap', 1)]
LOOT = {
    'casa': {'pools': [pool(2, 5, [item('bread', 4, 1, 4), item('apple', 3, 1, 3), item('wheat', 3, 2, 8), item('emerald', 1, 1, 2),
                                   item('torch', 2, 2, 6), item('iron_ingot', 1, 1, 2), item('book', 1), item('paper', 2, 1, 5)])]},
    'herreria': {'pools': [pool(3, 6, [item('iron_ingot', 5, 2, 7), item('gold_ingot', 2, 1, 3), item('diamond', 1, 1, 2),
                                       item('iron_sword', 2, ench=(5, 15)), item('iron_pickaxe', 2, ench=(5, 15)), item('iron_chestplate', 1, ench=(5, 15)),
                                       item('iron_helmet', 2), item('coal', 3, 3, 10), item('obsidian', 1, 1, 4)])]},
    'biblioteca': {'pools': [pool(3, 6, [item('book', 4, 1, 3), item('book', 3, ench='random'), item('paper', 3, 3, 9),
                                         item('lapis_lazuli', 3, 3, 10), item('experience_bottle', 2, 1, 4), item('compass', 1), item('empty_map', 1)])]},
    'taberna': {'pools': [pool(3, 6, [item('cooked_beef', 3, 2, 5), item('baked_potato', 3, 2, 6), item('pumpkin_pie', 2, 1, 3),
                                      item('honey_bottle', 2, 1, 3), item('potion', 2, potion='strength'), item('potion', 2, potion='regeneration'),
                                      item('emerald', 2, 1, 4), item('cake', 1)])]},
    'capilla': {'pools': [pool(2, 5, [item('glowstone_dust', 3, 2, 6), item('redstone', 3, 3, 8), item('ender_pearl', 2, 1, 2),
                                      item('potion', 2, potion='healing'), item('experience_bottle', 2, 2, 5), item('golden_apple', 1), item('candle', 2, 1, 4)])]},
    'aldea_cripta': {'pools': [pool(3, 6, COMMON), pool(1, 2, RARE)]},
    'piramide': {'pools': [pool(3, 6, COMMON + [item('bone', 4, 2, 7), item('rotten_flesh', 4, 2, 8), item('sand', 2, 4, 10)])]},
    'piramide_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE), pool(1, 1, [item('gold_block', 2, 1, 3), item('diamond_horse_armor', 1), item('golden_horse_armor', 2)])]},
    'templo_jungla': {'pools': [pool(3, 6, COMMON + [item('bamboo', 3, 2, 8), item('cocoa_beans', 3, 2, 6)])]},
    'templo_jungla_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE), pool(1, 1, [item('emerald_block', 2, 1, 3), item('trident', 1)])]},
    'bruja': {'pools': [pool(3, 6, [item('potion', 3, potion='healing'), item('potion', 3, potion='swiftness'), item('potion', 2, potion='fire_resistance'),
                                    item('splash_potion', 2, potion='harming'), item('glowstone_dust', 3, 2, 6), item('redstone', 3, 3, 8),
                                    item('spider_eye', 3, 1, 4), item('sugar', 2, 2, 6), item('nether_wart', 2, 2, 5), item('slime_ball', 2, 2, 6)]),
                        pool(0, 1, RARE)]},
    'iglu': {'pools': [pool(2, 4, [item('golden_apple', 1), item('coal', 3, 2, 6), item('apple', 3, 1, 3), item('wheat', 2, 2, 5),
                                   item('emerald', 2, 1, 2), item('stone_axe', 2), item('rotten_flesh', 2, 1, 3)])]},
    'iglu_tesoro': {'pools': [pool(3, 6, COMMON + [item('blue_ice', 2, 2, 6), item('splash_potion', 2, potion='weakness')]), pool(1, 2, RARE)]},
    'puesto': {'pools': [pool(3, 6, [item('arrow', 4, 6, 16), item('crossbow', 2, ench=(5, 20)), item('iron_ingot', 3, 2, 5),
                                     item('dark_oak_log', 3, 2, 6), item('emerald', 2, 1, 4), item('book', 1, ench='random'), item('bread', 3, 2, 5)])]},
    'puesto_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE + [item('totem_of_undying', 1)])]},
    'pozo': {'pools': [pool(3, 6, COMMON + [item('sand', 2, 4, 10), item('cactus', 2, 1, 4)]), pool(0, 1, RARE)]},
    'camaras': {'pools': [pool(2, 5, COMMON + [item('wind_charge', 3, 2, 6), item('copper_ingot', 3, 2, 8), item('tuff', 2, 4, 10)])]},
    'camaras_tesoro': {'pools': [pool(3, 5, COMMON), pool(1, 3, RARE + [item('mace', 1), item('heavy_core', 1), item('breeze_rod', 2, 1, 3)])]},
    'camaras_vasija': {'pools': [pool(1, 1, [item('emerald', 3, 1, 3), item('wind_charge', 3, 1, 3), item('diamond', 1), item('golden_carrot', 2, 1, 2)])]},
    'camaras_dispensador': {'pools': [pool(1, 1, [item('arrow', 3, 4, 8), item('snowball', 2, 4, 8), item('fire_charge', 1, 1, 3), item('splash_potion', 1, potion='poison')])]},
    'fortaleza_nether': {'pools': [pool(3, 6, [item('nether_wart', 4, 3, 7), item('gold_ingot', 4, 1, 4), item('iron_ingot', 3, 1, 5),
                                               item('diamond', 2, 1, 3), item('golden_sword', 2, ench='random'), item('golden_chestplate', 2, ench='random'),
                                               item('saddle', 2), item('obsidian', 2, 2, 4), item('blaze_rod', 2, 1, 3)])]},
    'fortaleza_nether_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE + [item('wither_skeleton_skull', 2), item('netherite_scrap', 2, 1, 2)])]},
    'bastion': {'pools': [pool(3, 6, [item('gold_ingot', 5, 2, 8), item('gold_nugget', 4, 6, 18), item('crying_obsidian', 3, 1, 4),
                                      item('golden_carrot', 3, 2, 5), item('arrow', 3, 6, 15), item('crossbow', 2, ench='random'),
                                      item('golden_axe', 2, ench='random'), item('magma_cream', 2, 2, 5), item('netherite_scrap', 1)])]},
    'bastion_tesoro': {'pools': [pool(4, 7, [item('gold_block', 4, 2, 5), item('netherite_ingot', 1), item('ancient_debris', 2, 1, 2),
                                             item('diamond', 3, 2, 5), item('enchanted_golden_apple', 1), item('diamond_sword', 2, ench=(25, 39)),
                                             item('diamond_chestplate', 2, ench=(25, 39)), item('netherite_upgrade_smithing_template', 2)]), pool(1, 2, RARE)]},
    'ciudad_end': {'pools': [pool(3, 6, [item('ender_pearl', 3, 1, 3), item('gold_ingot', 3, 2, 6), item('iron_ingot', 3, 3, 8),
                                         item('diamond', 2, 1, 3), item('emerald', 2, 2, 5), item('beetroot_seeds', 2, 1, 6),
                                         item('diamond_sword', 1, ench=(20, 39)), item('iron_chestplate', 2, ench=(20, 39))])]},
    'ciudad_end_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE + [item('shulker_shell', 3, 2, 4), item('spire_armor_trim_smithing_template', 1)])]},
    'mansion_tesoro': {'pools': [pool(4, 7, COMMON), pool(2, 3, RARE + [item('totem_of_undying', 2), item('vex_armor_trim_smithing_template', 1)])]},
    'portal': {'pools': [pool(4, 8, [item('obsidian', 4, 1, 3), item('flint_and_steel', 2), item('fire_charge', 3, 1, 3),
                                     item('gold_nugget', 5, 4, 18), item('gold_ingot', 3, 2, 6), item('golden_apple', 2),
                                     item('golden_sword', 2, ench='random'), item('golden_chestplate', 2, ench='random'), item('clock', 1),
                                     item('glistering_melon_slice', 2, 2, 5), item('light_weighted_pressure_plate', 1), item('gold_block', 1)]),
                         pool(1, 1, [item('enchanted_golden_apple', 1), item('diamond', 3, 1, 3), item('netherite_scrap', 2), item('ancient_debris', 1)])]},
}
TRIAL_LOOT_BASE = [item('emerald', 4, 2, 5), item('diamond', 2, 1, 2), item('golden_apple', 2), item('arrow', 3, 4, 10),
                   item('experience_bottle', 3, 2, 5), item('iron_ingot', 3, 2, 4), item('book', 2, ench='random'),
                   item('potion', 2, potion='regeneration'), item('potion', 2, potion='strength'), item('cooked_beef', 3, 2, 4)]
TRIAL_LOOT_EXTRA = {
    'desierto': [item('gold_ingot', 3, 2, 5), item('sandstone', 1, 4, 10)],
    'jungla': [item('emerald', 2, 2, 4), item('cocoa_beans', 2, 2, 5)],
    'pantano': [item('slime_ball', 3, 2, 6), item('potion', 2, potion='swiftness')],
    'nieve': [item('blue_ice', 2, 2, 5), item('arrow', 2, 6, 12)],
    'saqueadores': [item('crossbow', 2, ench=(10, 25)), item('totem_of_undying', 1)],
    'nether': [item('gold_block', 1), item('blaze_rod', 2, 1, 3), item('netherite_scrap', 1)],
    'cripta': [item('bone', 3, 3, 8), item('iron_sword', 2, ench=(10, 25))],
    'camaras': [item('wind_charge', 3, 2, 5), item('ominous_bottle', 1), item('honey_bottle', 2, 1, 2)],
    'camaras_breeze': [item('breeze_rod', 4, 1, 3), item('wind_charge', 3, 3, 6)],
    'fortaleza': [item('nether_wart', 2, 2, 6), item('blaze_rod', 3, 1, 3), item('wither_skeleton_skull', 1)],
    'bastion': [item('gold_block', 2, 1, 2), item('netherite_scrap', 1), item('ancient_debris', 1)],
    'end': [item('shulker_shell', 3, 1, 2), item('ender_pearl', 3, 1, 3), item('end_crystal', 1)],
    'mansion': [item('totem_of_undying', 2), item('emerald', 3, 3, 8)],
}

# ============================================================== bloque trial spawner, script, RP
def write(path, data):
    path = os.path.join(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(data, (dict, list)):
        with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
    elif isinstance(data, bytes):
        with open(path, 'wb') as f: f.write(data)
    else:
        with open(path, 'w', encoding='utf-8') as f: f.write(data)

def spawner_block():
    def mats(top, side):
        return {'*': {'texture': side, 'render_method': 'alpha_test'}, 'up': {'texture': top, 'render_method': 'alpha_test'},
                'down': {'texture': f'{NS}_trial_bottom', 'render_method': 'alpha_test'}}
    return {
        'format_version': '1.21.90',
        'minecraft:block': {
            'description': {
                'identifier': f'{NS}:trial_spawner',
                'menu_category': {'category': 'items'},
                'states': {f'{NS}:config': list(range(len(SPAWNERS))), f'{NS}:fase': [0, 1, 2]},
            },
            'components': {
                'minecraft:geometry': 'minecraft:geometry.full_block',
                'minecraft:material_instances': mats(f'{NS}_trial_top_inactive', f'{NS}_trial_side_inactive'),
                'minecraft:destructible_by_mining': {'seconds_to_destroy': 25},
                'minecraft:destructible_by_explosion': {'explosion_resistance': 1200},
                'minecraft:light_dampening': 0,
                'minecraft:map_color': '#3c4a55',
                'minecraft:loot': 'loot_tables/empty.json',
                'minecraft:tick': {'interval_range': [20, 20], 'looping': True},
                f'{NS}:trial_spawner': {},
            },
            'permutations': [
                {'condition': f"q.block_state('{NS}:fase') == 1",
                 'components': {'minecraft:material_instances': mats(f'{NS}_trial_top_active', f'{NS}_trial_side_active'),
                                'minecraft:light_emission': 6}},
                {'condition': f"q.block_state('{NS}:fase') == 2",
                 'components': {'minecraft:material_instances': mats(f'{NS}_trial_top_ejecting', f'{NS}_trial_side_inactive'),
                                'minecraft:light_emission': 3}},
            ],
        },
    }

SCRIPT = r'''// Estructuras Épicas — trial spawners propios.
// Funcionan como los de las Trial Chambers: detectan jugadores (14 bloques), sacan una oleada de
// 6 mobs (+2 por jugador extra, máx. 2 vivos +1 por jugador extra), sueltan recompensa al terminar
// (una por jugador) y se enfrían 30 minutos.
import { system, world, GameMode } from "@minecraft/server";

const NS = "__NS__";
const SPAWNERS = __SPAWNERS__;
const RANGE = 14;
const COOLDOWN = 36000;        // ticks (30 min)
const SPAWN_EVERY = 40;        // ticks entre apariciones
const RESET_IDLE = 2400;       // si nadie está cerca 2 min durante la oleada, se reinicia
const FASE = NS + ":fase", CONFIG = NS + ":config";

const keyOf = (b) => `ts:${b.dimension.id}:${b.location.x},${b.location.y},${b.location.z}`;
const tagOf = (b) => `ts_${b.location.x}_${b.location.y}_${b.location.z}`;
const load = (k) => { try { const v = world.getDynamicProperty(k); return v ? JSON.parse(v) : null; } catch { return null; } };
const save = (k, d) => world.setDynamicProperty(k, d === null ? undefined : JSON.stringify(d));

function setFase(block, f) {
  try { block.setPermutation(block.permutation.withState(FASE, f)); } catch {}
}
function sound(block, id) {
  try { block.dimension.playSound(id, block.center()); } catch {}
}
function particle(dim, id, loc) {
  try { dim.spawnParticle(id, loc); } catch {}
}
function playersNear(block) {
  return block.dimension.getPlayers({ location: block.center(), maxDistance: RANGE })
    .filter((p) => p.getGameMode() !== GameMode.Spectator);
}
function pick(list) {
  let tot = 0; for (const [, w] of list) tot += w;
  let r = Math.random() * tot;
  for (const [id, w] of list) { r -= w; if (r <= 0) return id; }
  return list[0][0];
}
function freeSpot(block) {
  const dim = block.dimension, o = block.location;
  for (let i = 0; i < 16; i++) {
    const x = o.x + Math.floor(Math.random() * 9) - 4, z = o.z + Math.floor(Math.random() * 9) - 4;
    for (const dy of [0, 1, -1, 2]) {
      const y = o.y + dy;
      try {
        const feet = dim.getBlock({ x, y, z }), head = dim.getBlock({ x, y: y + 1, z }), below = dim.getBlock({ x, y: y - 1, z });
        if (feet && head && below && feet.isAir && head.isAir && !below.isAir && !below.isLiquid) return { x: x + 0.5, y, z: z + 0.5 };
      } catch {}
    }
  }
  return null;
}

function tickSpawner(block) {
  const cfg = SPAWNERS[block.permutation.getState(CONFIG)] ?? SPAWNERS[0];
  const k = keyOf(block), now = world.getAbsoluteTime();
  let s = load(k) ?? { fase: 0 };
  const near = playersNear(block);

  if (s.fase === 2) {                                    // enfriamiento
    if (now >= s.until) { s = { fase: 0 }; setFase(block, 0); save(k, s); }
    return;
  }
  if (s.fase === 0) {                                    // esperando jugadores
    if (near.length === 0) return;
    const n = near.length;
    s = { fase: 1, total: 6 + 2 * (n - 1), maxAlive: 2 + (n - 1), spawned: 0, players: n, last: 0, seen: now };
    setFase(block, 1); sound(block, "trial_spawner.detect_player");
    save(k, s);
    return;
  }
  // fase 1: oleada activa
  if (near.length > s.players) {                         // llegó otro jugador: más mobs
    const extra = near.length - s.players;
    s.total += 2 * extra; s.maxAlive += extra; s.players = near.length;
  }
  if (near.length > 0) s.seen = now;
  const tag = tagOf(block);
  const alive = block.dimension.getEntities({ tags: [tag], location: block.center(), maxDistance: 48 }).length;
  if (now - s.seen > RESET_IDLE) {                        // abandonado: reinicia
    for (const e of block.dimension.getEntities({ tags: [tag] })) { try { e.remove(); } catch {} }
    s = { fase: 0 }; setFase(block, 0); save(k, s); return;
  }
  if (s.spawned < s.total && alive < s.maxAlive && now - s.last >= SPAWN_EVERY && near.length > 0) {
    const spot = freeSpot(block);
    if (spot) {
      try {
        const e = block.dimension.spawnEntity(pick(cfg.mobs), spot);
        e.addTag(tag);
        particle(block.dimension, "minecraft:mobflame_single", spot);
        particle(block.dimension, "minecraft:trial_spawner_detection", block.center());
        sound(block, "trial_spawner.spawn_mob");
        s.spawned++; s.last = now;
      } catch {}
    }
  }
  if (s.spawned >= s.total && alive === 0) {             // oleada superada: recompensa
    setFase(block, 2); sound(block, "trial_spawner.open_shutter");
    const n = Math.max(1, s.players), loc = block.location;
    for (let i = 0; i < n; i++) {
      system.runTimeout(() => {
        try {
          block.dimension.runCommand(`loot spawn ${loc.x + 0.5} ${loc.y + 1.2} ${loc.z + 0.5} loot "${NS}/trial/${cfg.loot}"`);
          sound(block, "trial_spawner.eject_item");
        } catch {}
      }, 20 + i * 20);
    }
    s = { fase: 2, until: now + COOLDOWN };
  }
  save(k, s);
}

system.beforeEvents.startup.subscribe(({ blockComponentRegistry }) => {
  blockComponentRegistry.registerCustomComponent(`${NS}:trial_spawner`, {
    onTick({ block }) { try { tickSpawner(block); } catch (e) { console.warn(`[${NS}] ${e}`); } },
  });
});

world.afterEvents.playerBreakBlock.subscribe(({ block, brokenBlockPermutation }) => {
  if (brokenBlockPermutation.type.id !== `${NS}:trial_spawner`) return;
  save(keyOf(block), null);
});
'''

def make_packs(stats):
    for d in (BP, RP):
        if os.path.isdir(d): shutil.rmtree(d)
    # ---- manifests
    write(os.path.join(BP, 'manifest.json'), {
        'format_version': 2,
        'header': {'name': 'Estructuras Épicas', 'description': 'Versiones mejoradas de las estructuras vanilla, estilo When Dungeons Arise.\nRequiere el experimento "Data-Driven Jigsaw Structures".',
                   'uuid': UUIDS['bp'], 'version': VERSION, 'min_engine_version': [1, 21, 90]},
        'modules': [{'type': 'data', 'uuid': UUIDS['bp_data'], 'version': VERSION},
                    {'type': 'script', 'language': 'javascript', 'uuid': UUIDS['bp_script'], 'version': VERSION, 'entry': 'scripts/main.js'}],
        'dependencies': [{'uuid': UUIDS['rp'], 'version': VERSION}, {'module_name': '@minecraft/server', 'version': '2.0.0'}],
    })
    write(os.path.join(RP, 'manifest.json'), {
        'format_version': 2,
        'header': {'name': 'Estructuras Épicas (recursos)', 'description': 'Recursos de Estructuras Épicas.',
                   'uuid': UUIDS['rp'], 'version': VERSION, 'min_engine_version': [1, 21, 90]},
        'modules': [{'type': 'resources', 'uuid': UUIDS['rp_res'], 'version': VERSION}],
    })
    # ---- bloque y script
    write(os.path.join(BP, 'blocks', 'trial_spawner.json'), spawner_block())
    write(os.path.join(BP, 'loot_tables', 'empty.json'), {'pools': []})
    spawners_js = json.dumps([{'mobs': [[m, w] for m, w in v['mobs']], 'loot': v['loot']} for v in SPAWNERS.values()])
    write(os.path.join(BP, 'scripts', 'main.js'), SCRIPT.replace('__NS__', NS).replace('__SPAWNERS__', spawners_js))
    tex = {
        f'{NS}_trial_top_inactive': 'textures/blocks/trial_spawner_top_inactive',
        f'{NS}_trial_top_active': 'textures/blocks/trial_spawner_top_active',
        f'{NS}_trial_top_ejecting': 'textures/blocks/trial_spawner_top_ejecting_reward',
        f'{NS}_trial_side_inactive': 'textures/blocks/trial_spawner_side_inactive',
        f'{NS}_trial_side_active': 'textures/blocks/trial_spawner_side_active',
        f'{NS}_trial_bottom': 'textures/blocks/trial_spawner_bottom',
    }
    write(os.path.join(RP, 'textures', 'terrain_texture.json'), {
        'resource_pack_name': NS, 'texture_name': 'atlas.terrain', 'padding': 8, 'num_mip_levels': 4,
        'texture_data': {k: {'textures': v} for k, v in tex.items()}})
    write(os.path.join(RP, 'blocks.json'), {'format_version': '1.1.0', f'{NS}:trial_spawner': {'sound': 'trial_spawner'}})
    lang = [f'tile.{NS}:trial_spawner.name=Generador de Desafío', 'pack.name=Estructuras Épicas',
            'pack.description=Versiones mejoradas de las estructuras vanilla.']
    for d in (BP, RP):
        write(os.path.join(d, 'texts', 'es_MX.lang'), '\n'.join(lang) + '\n')
        write(os.path.join(d, 'texts', 'es_ES.lang'), '\n'.join(lang) + '\n')
        write(os.path.join(d, 'texts', 'en_US.lang'), '\n'.join(lang) + '\n')
        write(os.path.join(d, 'texts', 'languages.json'), ['en_US', 'es_MX', 'es_ES'])
    # ---- loot
    for k, v in LOOT.items(): write(os.path.join(BP, 'loot_tables', NS, f'{k}.json'), v)
    for k, v in SPAWNERS.items():
        write(os.path.join(BP, 'loot_tables', NS, 'trial', f"{v['loot']}.json"),
              {'pools': [pool(2, 3, TRIAL_LOOT_BASE + TRIAL_LOOT_EXTRA.get(v['loot'], [])),
                         pool(0, 1, [item('enchanted_golden_apple', 1), item('diamond', 3, 2, 4), item('book', 3, ench=(25, 40)), {'type': 'empty', 'weight': 6}])]})

def main():
    stats = {}
    make_packs(stats)
    for sid, (fn, title) in DESIGNS.items():
        variants = []
        for v in range(2):
            rng = random.Random(f'{sid}-{v}')
            random.seed(f'{sid}-{v}')
            b, ground = fn(rng)
            name = f'{sid}_{v}'
            n = b.save(os.path.join(BP, 'structures', NS, name + '.mcstructure'))
            variants.append(name)
            stats[name] = (b.sx, b.sy, b.sz, n, ground)
        filt, adapt, spacing, sep, salt, hm = WORLDGEN[sid][:6]
        extra = WORLDGEN[sid][6] if len(WORLDGEN[sid]) > 6 else {}
        dim = extra.get('dim', 'overworld')
        write(os.path.join(BP, 'worldgen', 'template_pools', f'{sid}.json'), {'format_version': FMT_WG, 'minecraft:template_pool': {
            'description': {'identifier': f'{NS}:{sid}'},
            'elements': [{'element': {'element_type': 'minecraft:single_pool_element', 'location': f'{NS}/{v}', 'projection': 'rigid'}, 'weight': 1} for v in variants]}})
        ground = stats[variants[0]][4]
        write(os.path.join(BP, 'worldgen', 'structures', f'{sid}.json'), {'format_version': FMT_WG, 'minecraft:jigsaw': {
            'description': {'identifier': f'{NS}:{sid}'},
            'biome_filters': [{'all_of': [bt(dim)] + filt}],
            'step': extra.get('step', 'surface_structures'), 'terrain_adaptation': adapt, 'start_pool': f'{NS}:{sid}', 'max_depth': 1,
            'start_height': extra.get('height', {'type': 'constant', 'value': {'absolute': -ground}}), 'heightmap_projection': hm,
            'max_distance_from_center': {'horizontal': 64}, 'liquid_settings': 'ignore_waterlogging'}})
        write(os.path.join(BP, 'worldgen', 'structure_sets', f'{sid}.json'), {'format_version': FMT_WG, 'minecraft:structure_set': {
            'description': {'identifier': f'{NS}:{sid}'},
            'placement': {'type': 'minecraft:random_spread', 'salt': salt, 'separation': sep, 'spacing': spacing, 'spread_type': 'linear'},
            'structures': [{'structure': f'{NS}:{sid}', 'weight': 1}]}})
    # ---- empaquetar
    os.makedirs(os.path.dirname(DIST), exist_ok=True)
    with zipfile.ZipFile(DIST, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d in (BP, RP):
            for r, _, fs in os.walk(d):
                for f in sorted(fs):
                    p = os.path.join(r, f)
                    z.write(p, os.path.relpath(p, ROOT))
    for k, v in stats.items(): print(f'{k:28s} {v[0]}x{v[1]}x{v[2]}  bloques={v[3]}  suelo=y{v[4]}')
    print('->', os.path.relpath(DIST, ROOT), f'{os.path.getsize(DIST) // 1024} KB')

if __name__ == '__main__':
    main()
