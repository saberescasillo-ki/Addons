"""Refreshes block_states.json: the default states of every block the generator
can use, from minecraft-data (Bedrock 1.21.100).

    npm pack minecraft-data && tar xzf minecraft-data-*.tgz
    python3 tools/natura_pvp/update_block_states.py package/minecraft-data/data/bedrock/1.21.100
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(data_dir):
    states = json.load(open(os.path.join(data_dir, "blockStates.json")))
    blocks = {b["name"]: b for b in json.load(open(os.path.join(data_dir, "blocks.json")))}
    palette = json.loads(subprocess.run(["node", os.path.join(HERE, "dump_palette.mjs")], check=True,
                                        capture_output=True, text=True, cwd=HERE).stdout)
    out = {}
    for spec in palette.values():
        for ident in spec["id"].split("|"):
            name = ident.split(":")[1]
            if name in blocks and name not in out:
                d = states[blocks[name]["defaultState"]]
                out[name] = {"states": {k: [v["type"], v["value"]] for k, v in d["states"].items()}, "version": d["version"]}
    missing = [k for k, v in palette.items() if not any(i.split(":")[1] in out for i in v["id"].split("|"))]
    if missing:
        sys.exit(f"sin datos para: {missing}")
    with open(os.path.join(HERE, "block_states.json"), "w") as fh:
        json.dump({"game": os.path.basename(os.path.normpath(data_dir)), "blocks": out}, fh, indent=0, sort_keys=True)
    print(len(out), "bloques")


if __name__ == "__main__":
    main(sys.argv[1])
