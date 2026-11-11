"""Writes the Natura PvP map straight into a Bedrock world database (prebuilt).

Input: the columns exported by export.mjs (every area of gen/). Output: a `db`
folder (LevelDB) with the chunks of the lobby and all the arenas, so the world
opens already built. Everything else stays void (the world is a flat world
without layers).

Chunk format (Bedrock 1.18+), keys in LevelDB:
  [x:int32][z:int32][0x2C]            chunk version (one byte)
  [x:int32][z:int32][0x2B]            Data3D: height map + biomes (plains)
  [x:int32][z:int32][0x36]            FinalizedState = 2 (nothing left to generate)
  [x:int32][z:int32][0x2F][y:int8]    sub-chunk (16x16x16), version 9, block palette in NBT
The database is written as a LevelDB write-ahead log plus its manifest: when the
game opens the world it replays the log into its own tables.

Block names and their states come from block_states.json (taken from
minecraft-data for Bedrock 1.21.100); newer versions of the game upgrade them.
"""
import json
import math
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK_VERSION = 40
PLAINS = 1
MIN_Y = -64

try:
    from crc32c import crc32c
except ImportError:  # slow, but works everywhere
    _T = []
    for _i in range(256):
        _c = _i
        for _ in range(8):
            _c = (_c >> 1) ^ 0x82F63B78 if _c & 1 else _c >> 1
        _T.append(_c)

    def crc32c(data, crc=0):
        crc ^= 0xFFFFFFFF
        for b in data:
            crc = _T[(crc ^ b) & 0xFF] ^ (crc >> 8)
        return crc ^ 0xFFFFFFFF


# ------------------------------------------------------------ NBT (little endian)
def _nbt_str(s):
    raw = s.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw


def _nbt_value(kind, value):
    if kind == "byte":
        return 1, struct.pack("<b", int(value))
    if kind == "short":
        return 2, struct.pack("<h", int(value))
    if kind == "int":
        return 3, struct.pack("<i", int(value))
    if kind == "string":
        return 8, _nbt_str(str(value))
    raise ValueError(kind)


def block_nbt(name, states, version):
    body = b""
    body += b"\x08" + _nbt_str("name") + _nbt_str("minecraft:" + name)
    inner = b""
    for key in sorted(states):
        kind, value = states[key]
        tag, payload = _nbt_value(kind, value)
        inner += bytes([tag]) + _nbt_str(key) + payload
    body += b"\x0a" + _nbt_str("states") + inner + b"\x00"
    body += b"\x03" + _nbt_str("version") + struct.pack("<i", version)
    return b"\x0a" + _nbt_str("") + body + b"\x00"


# ------------------------------------------------------------ blocks
def load_blocks():
    with open(os.path.join(HERE, "block_states.json"), encoding="utf-8") as fh:
        return json.load(fh)["blocks"]


def resolve(spec, blocks):
    """The block of a PALETTE entry: the first id the data knows, with its states."""
    for ident in spec["id"].split("|"):
        name = ident.split(":", 1)[1]
        if name not in blocks:
            continue
        base = blocks[name]
        states = {k: list(v) for k, v in base["states"].items()}
        for k, v in (spec.get("s") or {}).items():
            if k not in states:
                raise ValueError(f"{name}: no state {k}")
            kind = states[k][0]
            states[k][1] = (1 if v else 0) if isinstance(v, bool) else v
        return name, states, base["version"]
    raise ValueError(f"unknown block {spec['id']}")


# ------------------------------------------------------------ the world in memory
class Chunks:
    def __init__(self, palette_specs, keys, blocks):
        self.blocks = []  # global ids -> (name, states, version); 0 = air
        self.index = {}
        self.add_block("air", {}, blocks.get("air", {"version": 18168865})["version"])
        self.key_ids = []
        for k in keys:
            if k == "air":
                self.key_ids.append(0)
                continue
            name, states, version = resolve(palette_specs[k], blocks)
            self.key_ids.append(self.add_block(name, states, version))
        self.sub = {}

    def add_block(self, name, states, version):
        sig = (name, json.dumps(states, sort_keys=True))
        if sig not in self.index:
            self.index[sig] = len(self.blocks)
            self.blocks.append((name, states, version))
        return self.index[sig]

    def fill(self, x, y0, y1, z, gid):
        cx, cz, lx, lz = x >> 4, z >> 4, x & 15, z & 15
        y0, y1 = max(y0, MIN_Y), min(y1, 319)
        for sy in range(y0 >> 4, (y1 >> 4) + 1):
            arr = self.sub.get((cx, cz, sy))
            if arr is None:
                if gid == 0:
                    continue
                arr = self.sub[(cx, cz, sy)] = np.zeros((16, 16, 16), dtype=np.uint16)
            a = max(y0, sy * 16) - sy * 16
            b = min(y1, sy * 16 + 15) - sy * 16
            arr[lx, lz, a:b + 1] = gid

    def load_area(self, path):
        data = open(path, "rb").read()
        pos, n = 0, len(data)
        key_ids = self.key_ids
        while pos < n:
            x, z, count = struct.unpack_from("<iiH", data, pos)
            pos += 10
            segs = np.frombuffer(data, dtype="<i2", count=count * 3, offset=pos).reshape(count, 3)
            pos += count * 6
            for y0, y1, k in segs.tolist():
                self.fill(x, y0, y1, z, key_ids[k & 0xFFFF])


# ------------------------------------------------------------ encoding
BITS = (1, 2, 3, 4, 5, 6, 8, 16)


def encode_subchunk(arr, sy, blocks, nbt_cache):
    flat = arr.reshape(-1)  # x * 256 + z * 16 + y
    ids, local = np.unique(flat, return_inverse=True)
    if len(ids) == 1 and ids[0] == 0:
        return None
    bits = next(b for b in BITS if (1 << b) >= len(ids))
    per_word = 32 // bits
    words = math.ceil(4096 / per_word)
    padded = np.zeros(words * per_word, dtype=np.uint32)
    padded[:4096] = local.astype(np.uint32)
    shifts = (np.arange(per_word, dtype=np.uint32) * bits)
    packed = np.bitwise_or.reduce(padded.reshape(words, per_word) << shifts, axis=1).astype("<u4")
    out = bytearray(struct.pack("<BBb", 9, 1, sy))
    out += bytes([bits << 1])
    out += packed.tobytes()
    out += struct.pack("<i", len(ids))
    for gid in ids.tolist():
        if gid not in nbt_cache:
            nbt_cache[gid] = block_nbt(*blocks[gid])
        out += nbt_cache[gid]
    return bytes(out)


def data3d(heights):
    out = bytearray(heights.astype("<i2").tobytes())
    for _ in range(24):  # one biome per sub-chunk section, all plains
        out += bytes([1]) + struct.pack("<i", PLAINS)
    return bytes(out)


def chunk_key(cx, cz, tag, sy=None):
    key = struct.pack("<iiB", cx, cz, tag)
    if sy is not None:
        key += struct.pack("<b", sy)
    return key


def chunk_records(chunks):
    """(key, value) pairs of every chunk, grouped per chunk."""
    by_chunk = {}
    for (cx, cz, sy), arr in chunks.sub.items():
        by_chunk.setdefault((cx, cz), []).append((sy, arr))
    nbt_cache = {}
    for (cx, cz), subs in sorted(by_chunk.items()):
        recs = []
        heights = np.zeros((16, 16), dtype=np.int16)  # [z][x]
        for sy, arr in sorted(subs):
            value = encode_subchunk(arr, sy, chunks.blocks, nbt_cache)
            if value is None:
                continue
            recs.append((chunk_key(cx, cz, 0x2F, sy), value))
            solid = arr != 0
            has = solid.any(axis=2)
            top = 15 - np.argmax(solid[:, :, ::-1], axis=2)
            h = np.where(has, sy * 16 + top + 1 - MIN_Y, 0).astype(np.int16)  # [x][z]
            heights = np.maximum(heights, h.T)
        if not recs:
            continue
        recs.insert(0, (chunk_key(cx, cz, 0x2C), bytes([CHUNK_VERSION])))
        recs.insert(1, (chunk_key(cx, cz, 0x2B), data3d(heights)))
        recs.append((chunk_key(cx, cz, 0x36), struct.pack("<i", 2)))
        yield recs


# ------------------------------------------------------------ LevelDB
BLOCK = 32768


def _mask(crc):
    return (((crc >> 15) | (crc << 17)) + 0xA282EAD8) & 0xFFFFFFFF


class LogWriter:
    def __init__(self, path):
        self.f = open(path, "wb")
        self.offset = 0

    def add(self, data):
        first = True
        while True:
            left = BLOCK - self.offset
            if left < 7:
                self.f.write(b"\x00" * left)
                self.offset = 0
                left = BLOCK
            room = left - 7
            frag, data = data[:room], data[room:]
            last = not data
            kind = 1 if first and last else 2 if first else 4 if last else 3
            crc = _mask(crc32c(bytes([kind]) + frag))
            self.f.write(struct.pack("<IHB", crc, len(frag), kind) + frag)
            self.offset += 7 + len(frag)
            first = False
            if last:
                return

    def close(self):
        self.f.close()


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def write_leveldb(folder, batches):
    """batches: lists of (key, value). Returns the number of entries."""
    os.makedirs(folder, exist_ok=True)
    log = LogWriter(os.path.join(folder, "000003.log"))
    seq = 1
    for batch in batches:
        body = bytearray(struct.pack("<QI", seq, len(batch)))
        for key, value in batch:
            body += b"\x01" + _varint(len(key)) + key + _varint(len(value)) + value
        log.add(bytes(body))
        seq += len(batch)
    log.close()
    edit = (_varint(1) + _varint(len(b"leveldb.BytewiseComparator")) + b"leveldb.BytewiseComparator"
            + _varint(2) + _varint(3) + _varint(9) + _varint(0) + _varint(3) + _varint(4) + _varint(4) + _varint(0))
    man = LogWriter(os.path.join(folder, "MANIFEST-000002"))
    man.add(edit)
    man.close()
    with open(os.path.join(folder, "CURRENT"), "w", newline="\n") as fh:
        fh.write("MANIFEST-000002\n")
    return seq - 1


def read_leveldb_log(path):
    """Reads the log back (a check): yields (key, value)."""
    data = open(path, "rb").read()
    pos, buf = 0, b""
    while pos + 7 <= len(data):
        if BLOCK - pos % BLOCK < 7:
            pos += BLOCK - pos % BLOCK
            continue
        crc, length, kind = struct.unpack_from("<IHB", data, pos)
        if kind == 0 and length == 0:
            pos += BLOCK - pos % BLOCK
            continue
        frag = data[pos + 7:pos + 7 + length]
        assert _mask(crc32c(bytes([kind]) + frag)) == crc, "crc"
        pos += 7 + length
        buf += frag
        if kind in (1, 4):
            seq, count = struct.unpack_from("<QI", buf, 0)
            p = 12
            for _ in range(count):
                assert buf[p] == 1
                p += 1
                vals = []
                for _ in range(2):
                    n, shift = 0, 0
                    while True:
                        b = buf[p]
                        p += 1
                        n |= (b & 0x7F) << shift
                        shift += 7
                        if not b & 0x80:
                            break
                    vals.append(buf[p:p + n])
                    p += n
                yield vals[0], vals[1]
            buf = b""


def build(export_dir, out_db):
    with open(os.path.join(export_dir, "areas.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    chunks = Chunks(meta["palette"], meta["keys"], load_blocks())
    for area in meta["areas"]:
        chunks.load_area(os.path.join(export_dir, area["file"]))
    count = write_leveldb(out_db, chunk_records(chunks))
    return {"entries": count, "subchunks": len(chunks.sub), "blocks": len(chunks.blocks)}


if __name__ == "__main__":
    import sys
    print(build(sys.argv[1], sys.argv[2]))
