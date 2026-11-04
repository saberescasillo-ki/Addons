"""Builds "Dungeons End" from Alylica's Dungeons (2.1.4), for personal use.

Only the End's boss and miniboss, and what their fight needs:
  * the Endersent (miniboss): spawns in the dark in the End, summons
    Watchlings, and here drops an Enchanted Eye of Ender every time it dies
    (in the original it dropped a blueprint, and the eyes came from the six
    Eye bosses, which are not part of this version);
  * the Vengeful Heart of Ender (boss), its Broken Citadel and its portal:
    put 6 Enchanted Eyes of Ender in the portal frames and it wakes up. Its
    chest opens with the Void Key it drops. The citadel never generates on
    its own: /structure load broken_citadel:structure ~ ~ ~

Reuses tools/dungeons_mobs.py with another configuration. Output in private/
(git-ignored), like that one.

    python3 tools/dungeons_end.py path/to/AlylicasDungeons.zip
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dungeons_mobs as dm  # noqa: E402

dm.BP = os.path.join(dm.OUT, "DungeonsEnd_BP")
dm.RP = os.path.join(dm.OUT, "DungeonsEnd_RP")
dm.MCADDON = os.path.join(dm.OUT, "DungeonsEnd.mcaddon")
dm.NAME = "Dungeons End"
dm.UUIDS = dict(bp="e2a7c41b-9d35-4f08-b6e1-3c5a8f0d27b9", bp_data="5d0b8e63-a1f4-4c92-8e37-b9c2d6a4f015",
                bp_script="9f3c6a28-e71d-4b05-a4c8-0d2e5b7f9163", rp="c6e19b74-3f2a-4d58-9b0c-a7e4d1f8326e",
                rp_res="0a8d5f32-b6c9-4e17-8d4a-f2b7c9e1a650")

ROOTS = {"dungeons:endersent", "dungeons:diamond_chest", "dungeons:vengeful_heart_of_ender_loot"}
ROOT_DIR = "entities/new/boss/vengeful_heart_of_ender/"
# What the boss and miniboss may pull in: their projectiles, effects, minions.
ALLOW = re.compile(r"^dungeons:(endersent|watchling|vengeful_.*|vhoe_.*|void_portal|diamond_chest)$")

dm.BOSS_STRUCTURES = ["dungeons:broken_citadel"]
dm.ITEM_ALWAYS = ["items/enchanted_eye_of_ender.json", "items/keys/void_key.json"]
dm.ITEM_IF_USED = []
dm.GEAR_DIR = "items/-none-/"
dm.BLOCK_REWARDS = set()
dm.MAIN_IMPORTS = {"./worldInitialise.js", "./components/blocks.js", "./misc/voidedEffect.js",
                   "./misc/bossManager.js", "./misc/entityBehaviour.js"}
dm.BEHAVIOUR_IMPORTS = {"endersent", "vengefulHeartofEnder", "watchling"}
dm.BLOCK_IMPORTS = {"voidFluid", "voidPortal"}
dm.RP_ALWAYS = ["pack_icon.png", "materials/entity.material", "ui/hud_screen.json",  # boss health bar
                "font/glyph_E2.png", "font/glyph_E3.png",  # icons in the boss bar names
                "textures/item_texture.json", "textures/terrain_texture.json", "textures/flipbook_textures.json",
                "blocks.json", "sounds.json", "sounds/sound_definitions.json"]

rejected = {}


def pick_entities(src):
    return {i for i, rel in src.entities.items() if i in ROOTS or rel.startswith(ROOT_DIR)}


def allowed_entity(self, ident):
    if ident.startswith("dungeons:") and ident in self.src.entities and ALLOW.match(ident):
        return True
    if ident.startswith("dungeons:") and ident in self.src.entities:
        rejected.setdefault(ident, set()).add("?")
    return False


_patch_scripts = dm.patch_scripts


def patch_scripts(scripts_dir):
    out = _patch_scripts(scripts_dir)
    # main.js only imports the armour for its set bonuses in specialDamage():
    # without armour nobody wears a set.
    out["main.js"] = re.sub(r'^import \{ isWearingSet, isWearingMysteryArmour \} from "\./components/armour\.js";?\r?$',
                            "const isWearingSet = () => false;\nconst isWearingMysteryArmour = () => false;",
                            out["main.js"], count=1, flags=re.M)
    if "isWearingSet = () => false" not in out["main.js"]:
        sys.exit("main.js: no se encontró el import de armour.js")
    return out


_manifests = dm.manifests


def manifests(src_bp, src_rp):
    bp, rp = _manifests(src_bp, src_rp)
    bp["header"]["description"] = "El Endersent y el Vengeful Heart of Ender de Alylica's Dungeons (uso personal)."
    rp["header"]["description"] = "Recursos de Dungeons End (uso personal)."
    return bp, rp


def prune_chest():
    """The diamond chest knows every boss's chest; keep only this one."""
    path = os.path.join(dm.BP, "entities/utility/chest/diamond/_diamond_chest.json")
    data = dm.load(path)
    ent = data["minecraft:entity"]

    def other_boss(name):
        return name.startswith("dungeons:") and any(k in name for k in ("_chest", "open_", "spawn_")) \
            and "vengeful_heart_of_ender" not in name
    ent["component_groups"] = {k: v for k, v in ent["component_groups"].items() if not other_boss(k)}
    ent["events"] = {k: v for k, v in ent["events"].items() if not other_boss(k)}
    text = dm.json.dumps(data)
    for group in re.findall(r'"(dungeons:[a-z_]+_chest)"', text):
        if group not in ent["component_groups"] and group != ent["description"]["identifier"]:
            sys.exit(f"_diamond_chest: queda una referencia a {group}")
    dm.dump(path, data)


def prune_loot():
    """Drops the loot tables left without anything this pack has (the armour
    rolled by the boss chest), the entries pointing to them, and the
    Watchling's natural spawning: here it only comes when the Endersent calls it."""
    root = os.path.join(dm.BP, "loot_tables")
    items = {"dungeons:enchanted_eye_of_ender", "dungeons:void_key"}

    def useful(data):
        return any(e.get("type") == "item" and (not e.get("name", "").startswith("dungeons:") or e["name"] in items)
                   for pool in data.get("pools", []) for e in pool.get("entries", []))
    while True:
        tables = {os.path.relpath(os.path.join(r, f), dm.BP) for r, _, fs in os.walk(root) for f in fs}
        empty = {t for t in tables if not useful(dm.load(os.path.join(dm.BP, t)))
                 and not any(e.get("type") == "loot_table" for pool in dm.load(os.path.join(dm.BP, t)).get("pools", [])
                             for e in pool.get("entries", []))}
        for t in empty:
            os.remove(os.path.join(dm.BP, t))
        kept = tables - empty
        changed = bool(empty)
        for t in kept:
            path = os.path.join(dm.BP, t)
            before = dm.load(path)
            after = dm.filter_loot(before, items, kept)
            if after != before:
                dm.dump(path, after)
                changed = True
        if not changed:
            break
    for r, dirs, fs in os.walk(root, topdown=False):
        if not os.listdir(r):
            os.rmdir(r)
    os.remove(os.path.join(dm.BP, "spawn_rules/watchling.json"))


def patch_watchling():
    """1 in 10 Watchlings turned into the enchanted Watchling, which is not in
    this pack: here they always stay normal."""
    path = os.path.join(dm.BP, "entities/new/watchling.json")
    data = dm.load(path)
    ent = data["minecraft:entity"]
    spawned = ent["events"]["minecraft:entity_spawned"]
    if not any(r.get("trigger") == "dungeons:become_enchanted" for r in spawned.get("randomize", [])):
        sys.exit("watchling.json: cambió su evento de aparición")
    ent["events"]["minecraft:entity_spawned"] = {"add": {"component_groups": ["dungeons:watchling_normal"]}}
    ent["events"].pop("dungeons:become_enchanted", None)
    ent["component_groups"].pop("dungeons:transform_to_enchanted", None)
    if "enchanted_watchling" in dm.json.dumps(data) or "become_enchanted" in dm.json.dumps(data):
        sys.exit("watchling.json: quedan referencias al Watchling encantado")
    dm.dump(path, data)


def endersent_loot():
    """One Enchanted Eye of Ender per Endersent (6 open the portal). The Endersent
    uses one of two tables: the usual one (a blueprint, which is not in this
    pack, and ender pearls) and an 'eye' one (an ender eye and pearls)."""
    eye = {"rolls": 1, "entries": [{"type": "item", "name": "dungeons:enchanted_eye_of_ender", "weight": 1}]}
    pearls = {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:ender_pearl", "weight": 1,
                                       "functions": [{"function": "set_count", "count": {"min": 1, "max": 2}}]}]}
    dm.dump(os.path.join(dm.BP, "loot_tables/entities/endersent.json"), {"pools": [eye, pearls]})
    path = os.path.join(dm.BP, "loot_tables/entities/eye_endersent.json")
    data = dm.load(path)
    data["pools"].insert(0, eye)
    dm.dump(path, data)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dm.pick_entities = pick_entities
    dm.BPClosure.allowed_entity = allowed_entity
    dm.patch_scripts = patch_scripts
    dm.manifests = manifests
    write_mcaddon, report = dm.write_mcaddon, dm.report
    dm.write_mcaddon = lambda: None
    dm.report = lambda *a: None
    dm.main()
    prune_chest()
    patch_watchling()
    endersent_loot()
    prune_loot()
    write_mcaddon()
    count = sum(len(f) for _, _, f in os.walk(dm.BP)), sum(len(f) for _, _, f in os.walk(dm.RP))
    ents = sorted(dm.load(os.path.join(r, f))["minecraft:entity"]["description"]["identifier"]
                  for r, _, fs in os.walk(os.path.join(dm.BP, "entities")) for f in fs)
    print(f"Entidades ({len(ents)}): {', '.join(e.split(':')[1] for e in ents)}")
    print(f"Archivos BP: {count[0]}  RP: {count[1]}  .mcaddon: {os.path.getsize(dm.MCADDON) / 1e6:.1f} MB")
    if rejected:
        print("Referencias que no se incluyen:", ", ".join(sorted(rejected)))


if __name__ == "__main__":
    main()
