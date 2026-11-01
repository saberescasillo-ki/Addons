"""A tiny writer of Bedrock .mcstructure files (little-endian NBT).

Used for the item frame with the totem on the altar of the Torre del Tótem: scripts cannot put
an item into a frame, but a structure can carry the frame together with its item.
"""
import struct

END, BYTE, SHORT, INT, FLOAT, STRING, LIST, COMPOUND = 0, 1, 2, 3, 5, 8, 9, 10


class Byte(int):
    pass


class Short(int):
    pass


class Float(float):
    pass


def _type(v):
    if isinstance(v, Byte) or isinstance(v, bool):
        return BYTE
    if isinstance(v, Short):
        return SHORT
    if isinstance(v, Float):
        return FLOAT
    if isinstance(v, int):
        return INT
    if isinstance(v, str):
        return STRING
    if isinstance(v, list):
        return LIST
    if isinstance(v, dict):
        return COMPOUND
    raise TypeError(v)


def _str(s):
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def _payload(v):
    t = _type(v)
    if t == BYTE:
        return struct.pack("<b", int(v))
    if t == SHORT:
        return struct.pack("<h", v)
    if t == INT:
        return struct.pack("<i", v)
    if t == FLOAT:
        return struct.pack("<f", v)
    if t == STRING:
        return _str(v)
    if t == LIST:
        et = _type(v[0]) if v else COMPOUND
        return struct.pack("<bi", et, len(v)) + b"".join(_payload(x) for x in v)
    out = b"".join(struct.pack("<b", _type(x)) + _str(k) + _payload(x) for k, x in v.items())
    return out + struct.pack("<b", END)


def nbt(root):
    return struct.pack("<b", COMPOUND) + _str("") + _payload(root)


# facing_direction of a frame: the side it looks at
FACING = {"north": 2, "south": 3, "west": 4, "east": 5}
BLOCK_VERSION = 18168865  # 1.21.60: the game upgrades older block states by itself


def item_frame(facing, item, glow=True):
    """A 1x1x1 structure: a (glow) item frame looking `facing`, holding `item`."""
    name = "minecraft:glow_frame" if glow else "minecraft:frame"
    return nbt({
        "format_version": 1,
        "size": [1, 1, 1],
        "structure_world_origin": [0, 0, 0],
        "structure": {
            "block_indices": [[0], [-1]],
            "entities": [],
            "palette": {"default": {
                "block_palette": [{"name": name, "states": {
                    "facing_direction": FACING[facing], "item_frame_map_bit": Byte(0), "item_frame_photo_bit": Byte(0)},
                    "version": BLOCK_VERSION}],
                "block_position_data": {"0": {"block_entity_data": {
                    "id": "GlowItemFrame" if glow else "ItemFrame", "isMovable": Byte(1), "x": 0, "y": 0, "z": 0,
                    "Item": {"Name": item, "Count": Byte(1), "Damage": Short(0), "WasPickedUp": Byte(0)},
                    "ItemRotation": Float(0.0), "ItemDropChance": Float(1.0)}}},
            }},
        },
    })
