#!/usr/bin/env python3
"""Bedrock half of VFX step 1 (issue #10): a Geyser custom-item mappings file
(format v2) plus a Bedrock resource pack so Geyser players see the weapon
sprites on the dropped-item visual the plugin shows them.

Generated from the same SPRITES table as build_items.py, so the two can't drift:

  bedrock/geyser_mappings.json                 v2 mappings: per vanilla item, one
                                               "definition" entry per weapon with a
                                               custom_model_data STRING match predicate
  bedrock/foxmobmashers-bedrock.mcpack         Bedrock resource pack (zip): manifest,
                                               textures/item_texture.json, textures/items/*.png

Install (Geyser instance, i.e. the proxy — a proxy-wide change):
  geyser_mappings.json  -> plugins/Geyser-<platform>/custom_mappings/
  *.mcpack              -> plugins/Geyser-<platform>/packs/
  enable-custom-content: true in Geyser's config, then `geyser reload`.

    python3 tools/build_bedrock.py          # (re)generate
    python3 tools/build_bedrock.py --check  # verify
"""
import io
import json
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_items  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NS = "foxmobmashers"
PACK_NAME = "FoxMobMashers Weapons"
PACK_VERSION = [1, 0, 0]

DISPLAY_NAMES = {
    "axe": "Axe", "cross": "Cross", "king_bible": "King Bible", "knife": "Knife", "bone": "Bone",
    "peachone": "Peachone", "death_spiral": "Death Spiral", "heaven_sword": "Heaven Sword",
    "unholy_vespers": "Unholy Vespers", "ebony_wings": "Ebony Wings", "vandalier": "Vandalier",
    "carrello": "Carrello", "fuwalafuwaloo": "Fuwalafuwaloo", "vento_sacro": "Vento Sacro",
}


def stable_uuid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/mcfoxcraft/Minecraft-Mob-Mashers-pack/bedrock/{tag}"))


def mappings():
    items = {}
    for weapon, (item, parent, _pal, _rows) in build_items.SPRITES.items():
        items.setdefault(f"minecraft:{item}", []).append({
            "type": "definition",
            # The Java item model definition the stack renders with: vanilla items
            # default their item_model to their own id, and our pack overrides that
            # definition's `select`, so the definition id stays the vanilla one.
            "model": f"minecraft:{item}",
            "bedrock_identifier": f"{NS}:{weapon}",
            "display_name": DISPLAY_NAMES.get(weapon, weapon),
            "predicate": {
                "type": "match",
                "property": "custom_model_data",
                "value": f"{NS}:{weapon}",
                "index": 0,
            },
            "bedrock_options": {
                "icon": f"{NS}:{weapon}",
                "display_handheld": parent == "item/handheld",
                "allow_offhand": True,
            },
        })
    return {"format_version": 2, "items": items}


def item_texture_json():
    return {
        "resource_pack_name": PACK_NAME,
        "texture_name": "atlas.items",
        "texture_data": {
            f"{NS}:{w}": {"textures": [f"textures/items/{w}"]} for w in build_items.SPRITES
        },
    }


def manifest():
    return {
        "format_version": 2,
        "header": {
            "name": PACK_NAME,
            "description": "Weapon sprites for the FoxMobMashers gamemode (Geyser custom items)",
            "uuid": stable_uuid("header"),
            "version": PACK_VERSION,
            "min_engine_version": [1, 20, 0],
        },
        "modules": [{"type": "resources", "uuid": stable_uuid("module"), "version": PACK_VERSION}],
    }


def mcpack_bytes():
    buf = io.BytesIO()
    # Fixed timestamps so the zip is reproducible byte-for-byte.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name, data):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        add("manifest.json", json.dumps(manifest(), indent=2) + "\n")
        add("textures/item_texture.json", json.dumps(item_texture_json(), indent=2) + "\n")
        for weapon, (item, parent, pal, rows) in build_items.SPRITES.items():
            add(f"textures/items/{weapon}.png", build_items.png_bytes(pal, rows))
    return buf.getvalue()


def outputs():
    return {
        "bedrock/geyser_mappings.json": (json.dumps(mappings(), indent=2) + "\n").encode(),
        "bedrock/foxmobmashers-bedrock.mcpack": mcpack_bytes(),
    }


def main(argv):
    check = "--check" in argv
    stale = []
    for rel, data in outputs().items():
        path = ROOT / rel
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if check:
        if stale:
            print("STALE (run tools/build_bedrock.py):\n  " + "\n  ".join(stale))
            return 1
        print(f"ok: bedrock mappings + pack in sync ({len(build_items.SPRITES)} items)")
    else:
        print(f"wrote bedrock/geyser_mappings.json + .mcpack for {len(build_items.SPRITES)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
