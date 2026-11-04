"""Bundles several built packs into one .mcaddon (they stay separate packs).

    python3 tools/bundle.py private/Jefes.mcaddon private/Ignis private/Netherens private/DungeonsEnd

Each name X stands for the folders X_BP and X_RP.
"""
import json
import os
import sys
import zipfile


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out, names = sys.argv[1], sys.argv[2:]
    folders = [f"{n}_{kind}" for n in names for kind in ("BP", "RP")]
    seen = {}
    for folder in folders:
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        for uuid in [m["header"]["uuid"]] + [mod["uuid"] for mod in m.get("modules", [])]:
            if uuid in seen:
                sys.exit(f"UUID repetido {uuid}: {seen[uuid]} y {folder}")
            seen[uuid] = folder
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for folder in folders:
            base = os.path.dirname(os.path.abspath(folder))
            for dirpath, dirs, files in os.walk(folder):
                dirs.sort()
                for name in sorted(files):
                    full = os.path.join(dirpath, name)
                    info = zipfile.ZipInfo(os.path.relpath(os.path.abspath(full), base),
                                           date_time=(2025, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        z.writestr(info, f.read(), compresslevel=9)
    print(f"OK -> {out} ({os.path.getsize(out) / 1e6:.1f} MB, {len(folders)} packs)")


if __name__ == "__main__":
    main()
