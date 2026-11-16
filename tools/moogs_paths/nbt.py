"""Minimal NBT reader (Java, big-endian, gzip) and writer (Bedrock, little-endian, uncompressed)."""
import gzip, struct

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTES, STRING, LIST, COMPOUND, INTS, LONGS = range(13)

class Tag:
    __slots__ = ("t", "v", "lt")
    def __init__(self, t, v, lt=None):
        self.t, self.v, self.lt = t, v, lt

def read_java(path):
    data = open(path, "rb").read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    pos = [0]
    def rd(fmt):
        s = struct.calcsize(fmt); v = struct.unpack_from(fmt, data, pos[0]); pos[0] += s; return v[0]
    def rstr():
        n = rd(">H"); s = data[pos[0]:pos[0]+n].decode("utf-8"); pos[0] += n; return s
    def payload(t):
        if t == BYTE: return rd(">b")
        if t == SHORT: return rd(">h")
        if t == INT: return rd(">i")
        if t == LONG: return rd(">q")
        if t == FLOAT: return rd(">f")
        if t == DOUBLE: return rd(">d")
        if t == BYTES:
            n = rd(">i"); b = data[pos[0]:pos[0]+n]; pos[0] += n; return list(b)
        if t == STRING: return rstr()
        if t == LIST:
            lt = rd(">b"); n = rd(">i"); return [payload(lt) for _ in range(n)]
        if t == COMPOUND:
            d = {}
            while True:
                tt = rd(">b")
                if tt == END: return d
                k = rstr(); d[k] = payload(tt)
        if t == INTS:
            n = rd(">i"); return [rd(">i") for _ in range(n)]
        if t == LONGS:
            n = rd(">i"); return [rd(">q") for _ in range(n)]
        raise ValueError(t)
    t = rd(">b"); rstr()
    return payload(t)

def write_bedrock(tag):
    out = bytearray()
    def wstr(s):
        b = s.encode("utf-8"); out.extend(struct.pack("<H", len(b))); out.extend(b)
    def payload(tag):
        t, v = tag.t, tag.v
        if t == BYTE: out.extend(struct.pack("<b", v))
        elif t == SHORT: out.extend(struct.pack("<h", v))
        elif t == INT: out.extend(struct.pack("<i", v))
        elif t == LONG: out.extend(struct.pack("<q", v))
        elif t == FLOAT: out.extend(struct.pack("<f", v))
        elif t == STRING: wstr(v)
        elif t == LIST:
            out.extend(struct.pack("<bi", tag.lt if v else END, len(v)))
            for x in v: payload(x)
        elif t == COMPOUND:
            for k, x in v.items():
                out.extend(struct.pack("<b", x.t)); wstr(k); payload(x)
            out.append(END)
        else: raise ValueError(t)
    out.append(COMPOUND); wstr(""); payload(tag)
    return bytes(out)
