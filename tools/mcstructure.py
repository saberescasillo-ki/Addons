"""Reads and writes Bedrock .mcstructure files (little-endian NBT), and builds
structures block by block.

    s = Structure((64, 40, 64))
    s.set(x, y, z, "minecraft:polished_blackstone_bricks")
    s.set(x, y, z, "minecraft:polished_blackstone_brick_stairs", {"weirdo_direction": 2, "upside_down_bit": 0})
    s.save("arena.mcstructure")
"""
import struct

# NBT tag ids
END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


class Tag:
    """A value with an explicit NBT type (for ints that must be bytes, etc.)."""
    __slots__ = ("type", "value")

    def __init__(self, type_, value):
        self.type, self.value = type_, value

    def __repr__(self):
        return f"Tag({self.type}, {self.value!r})"

    def __eq__(self, other):
        return isinstance(other, Tag) and (self.type, self.value) == (other.type, other.value)

    def __hash__(self):
        return hash((self.type, _freeze(self.value)))


def _freeze(v):
    if isinstance(v, dict):
        return tuple(sorted((k, _freeze(x)) for k, x in v.items()))
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)
    return v


def byte(v):
    return Tag(BYTE, int(v))


def short(v):
    return Tag(SHORT, int(v))


def int_(v):
    return Tag(INT, int(v))


# --- reading -----------------------------------------------------------------
class _Reader:
    def __init__(self, data):
        self.d, self.i = data, 0

    def take(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.i)
        self.i += struct.calcsize("<" + fmt)
        return v[0]

    def string(self):
        n = self.take("H")
        s = self.d[self.i:self.i + n].decode("utf-8", "replace")
        self.i += n
        return s

    def payload(self, t):
        if t == BYTE:
            return Tag(BYTE, self.take("b"))
        if t == SHORT:
            return Tag(SHORT, self.take("h"))
        if t == INT:
            return Tag(INT, self.take("i"))
        if t == LONG:
            return Tag(LONG, self.take("q"))
        if t == FLOAT:
            return Tag(FLOAT, self.take("f"))
        if t == DOUBLE:
            return Tag(DOUBLE, self.take("d"))
        if t == STRING:
            return self.string()
        if t == BYTE_ARRAY:
            n = self.take("i")
            v = self.d[self.i:self.i + n]
            self.i += n
            return Tag(BYTE_ARRAY, v)
        if t == INT_ARRAY:
            n = self.take("i")
            v = list(struct.unpack_from("<%di" % n, self.d, self.i))
            self.i += 4 * n
            return Tag(INT_ARRAY, v)
        if t == LONG_ARRAY:
            n = self.take("i")
            v = list(struct.unpack_from("<%dq" % n, self.d, self.i))
            self.i += 8 * n
            return Tag(LONG_ARRAY, v)
        if t == LIST:
            et = self.take("b")
            n = self.take("i")
            if et == INT and n:
                v = list(struct.unpack_from("<%di" % n, self.d, self.i))
                self.i += 4 * n
                return Tag(LIST, (INT, [Tag(INT, x) for x in v]))
            return Tag(LIST, (et, [self.payload(et) for _ in range(n)]))
        if t == COMPOUND:
            out = {}
            while True:
                ct = self.take("b")
                if ct == END:
                    return out
                name = self.string()
                out[name] = self.payload(ct)
        raise ValueError(f"tipo NBT desconocido {t}")


def read_nbt(data):
    r = _Reader(data)
    t = r.take("b")
    r.string()
    return r.payload(t)


def plain(v):
    """NBT value -> plain Python (Tag -> value, lists -> lists)."""
    if isinstance(v, Tag):
        if v.type == LIST:
            return [plain(x) for x in v.value[1]]
        return v.value
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    return v


# --- writing -----------------------------------------------------------------
def _type_of(v):
    if isinstance(v, Tag):
        return v.type
    if isinstance(v, bool):
        return BYTE
    if isinstance(v, int):
        return INT
    if isinstance(v, float):
        return FLOAT
    if isinstance(v, str):
        return STRING
    if isinstance(v, dict):
        return COMPOUND
    if isinstance(v, list):
        return LIST
    raise TypeError(type(v))


def _write(out, t, v):
    if isinstance(v, Tag):
        v = v.value
    if t == BYTE:
        out += struct.pack("<b", int(v))
    elif t == SHORT:
        out += struct.pack("<h", v)
    elif t == INT:
        out += struct.pack("<i", v)
    elif t == LONG:
        out += struct.pack("<q", v)
    elif t == FLOAT:
        out += struct.pack("<f", v)
    elif t == DOUBLE:
        out += struct.pack("<d", v)
    elif t == STRING:
        b = v.encode("utf-8")
        out += struct.pack("<H", len(b)) + b
    elif t == BYTE_ARRAY:
        out += struct.pack("<i", len(v)) + bytes(v)
    elif t == INT_ARRAY:
        out += struct.pack("<i%di" % len(v), len(v), *v)
    elif t == LONG_ARRAY:
        out += struct.pack("<i%dq" % len(v), len(v), *v)
    elif t == LIST:
        if isinstance(v, tuple):  # (element type, items) as read
            et, items = v
        else:
            items = v
            et = _type_of(items[0]) if items else END
        out += struct.pack("<bi", et, len(items))
        if et == INT and items and not any(isinstance(x, Tag) and x.type != INT for x in items):
            out += struct.pack("<%di" % len(items), *[x.value if isinstance(x, Tag) else x for x in items])
        else:
            for x in items:
                _write(out, et, x)
    elif t == COMPOUND:
        for k, x in v.items():
            xt = _type_of(x)
            out += struct.pack("<b", xt)
            _write(out, STRING, k)
            _write(out, xt, x)
        out += struct.pack("<b", END)
    else:
        raise ValueError(t)


def write_nbt(root):
    out = bytearray(struct.pack("<b", COMPOUND))
    _write(out, STRING, "")
    _write(out, COMPOUND, root)
    return bytes(out)


# --- structures --------------------------------------------------------------
# Block palette version of Minecraft 1.21 (the game upgrades older versions on load).
BLOCK_VERSION = 18168865
AIR = "minecraft:air"
STRUCTURE_VOID = "minecraft:structure_void"


def _state_tag(v):
    if isinstance(v, Tag):
        return v
    if isinstance(v, bool):
        return byte(v)
    if isinstance(v, int):
        return int_(v)
    return v


class Structure:
    """A box of blocks. Unset positions are structure_void (they keep the world's block)."""

    def __init__(self, size, fill=STRUCTURE_VOID):
        self.size = tuple(size)
        self.palette = []
        self._index = {}
        self.blocks = [self._pal(fill, {})] * (size[0] * size[1] * size[2])
        self.water = {}           # second layer: waterlogging
        self.block_entities = {}  # flat index -> block entity compound
        self.entities = []

    def _pal(self, name, states):
        key = (name, _freeze({k: _state_tag(v) for k, v in states.items()}))
        if key not in self._index:
            self._index[key] = len(self.palette)
            self.palette.append({"name": name, "states": {k: _state_tag(v) for k, v in states.items()},
                                 "version": int_(BLOCK_VERSION)})
        return self._index[key]

    def _flat(self, x, y, z):
        sx, sy, sz = self.size
        return (x * sy + y) * sz + z  # Bedrock order: x outermost, z innermost

    def inside(self, x, y, z):
        return 0 <= x < self.size[0] and 0 <= y < self.size[1] and 0 <= z < self.size[2]

    def set(self, x, y, z, name, states=None, block_entity=None):
        if not self.inside(x, y, z):
            return
        i = self._flat(x, y, z)
        self.blocks[i] = self._pal(name, states or {})
        if block_entity is not None:
            self.block_entities[i] = block_entity
        else:
            self.block_entities.pop(i, None)

    def get(self, x, y, z):
        if not self.inside(x, y, z):
            return None
        return self.palette[self.blocks[self._flat(x, y, z)]]["name"]

    def fill(self, x0, y0, z0, x1, y1, z1, name, states=None):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.set(x, y, z, name, states)

    def add_entity(self, identifier, pos, extra=None):
        """Saves an entity (pos relative to the structure's corner, in blocks)."""
        e = {"identifier": identifier,
             "Pos": Tag(LIST, (FLOAT, [Tag(FLOAT, float(c)) for c in pos])),
             "Rotation": Tag(LIST, (FLOAT, [Tag(FLOAT, 0.0), Tag(FLOAT, 0.0)])),
             "Persistent": byte(1)}
        e.update(extra or {})
        self.entities.append(e)

    def to_nbt(self):
        sx, sy, sz = self.size
        n = sx * sy * sz
        layer2 = [-1] * n
        for i, idx in self.water.items():
            layer2[i] = idx
        pos_data = {str(i): {"block_entity_data": be} for i, be in self.block_entities.items()}
        return {
            "format_version": int_(1),
            "size": Tag(LIST, (INT, [int_(sx), int_(sy), int_(sz)])),
            "structure": {
                "block_indices": Tag(LIST, (LIST, [Tag(LIST, (INT, [int_(v) for v in self.blocks])),
                                                    Tag(LIST, (INT, [int_(v) for v in layer2]))])),
                "entities": Tag(LIST, (COMPOUND, self.entities)),
                "palette": {"default": {"block_palette": Tag(LIST, (COMPOUND, self.palette)),
                                        "block_position_data": pos_data}},
            },
            "structure_world_origin": Tag(LIST, (INT, [int_(0), int_(0), int_(0)])),
        }

    def save(self, path):
        with open(path, "wb") as f:
            f.write(write_nbt(self.to_nbt()))


def load_structure(path):
    with open(path, "rb") as f:
        root = read_nbt(f.read())
    return root
