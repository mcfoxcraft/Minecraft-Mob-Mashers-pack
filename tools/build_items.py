#!/usr/bin/env python3
"""Generate the per-weapon item sprites, models and vanilla-item definition
overrides for VFX step 1 (issue #5).

Source of truth is SPRITES below: one 16x16 ASCII-art sprite per weapon, plus
the vanilla item the plugin flies for it. From that this script writes

  assets/foxmobmashers/textures/item/<weapon>.png      the sprite
  assets/foxmobmashers/models/item/<weapon>.json       item/generated (or handheld)
  assets/minecraft/items/<vanilla_item>.json           `select` on custom_model_data:
                                                       case "foxmobmashers:<weapon>" ->
                                                       our model, fallback -> vanilla

The plugin sets custom_model_data strings ["foxmobmashers:<weapon>"] on the
visual ItemStack (WeaponVisuals.java there). A client without this pack — or a
pack that predates a weapon — matches no case and renders the vanilla item,
which is why this uses custom_model_data and not the item_model component.

    python3 tools/build_items.py          # (re)generate
    python3 tools/build_items.py --check  # verify the tree matches the table

No third-party modules: PNGs are written with zlib + struct.
"""
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "foxmobmashers"

# weapon id -> (vanilla item the plugin flies, model parent, palette, rows)
# Palette letters map to RGB; '.' is transparent. Rows are exactly 16 chars.
SPRITES = {
    "axe": ("iron_axe", "item/generated", {
        "h": (0x6B, 0x4A, 0x2B), "H": (0x8B, 0x6A, 0x3B),
        "s": (0xC8, 0xCC, 0xD0), "S": (0xEE, 0xF0, 0xF2), "d": (0x7A, 0x80, 0x88),
        "o": (0x2B, 0x2B, 0x2B),
    }, [
        "................",
        "..........oooo..",
        ".........osSSSo.",
        "........osSSSSo.",
        ".......osSSSSso.",
        "......odsSSSsdo.",
        ".....ohodsssdo..",
        "....ohHo.oddo...",
        "...ohHo...oo....",
        "..ohHo..........",
        ".ohHo...........",
        ".ohho...........",
        ".oho............",
        ".oo.............",
        "................",
        "................",
    ]),
    "cross": ("iron_hoe", "item/generated", {
        "g": (0xE8, 0xB8, 0x30), "G": (0xFF, 0xE0, 0x7A), "d": (0xA8, 0x7A, 0x10),
        "o": (0x3A, 0x2A, 0x05),
    }, [
        "......oooo......",
        "......oGgdo.....",
        "......oGgdo.....",
        "......oGgdo.....",
        "..oooooGgdooooo.",
        ".oGGGGGGGgddddo.",
        ".oggggggggddddo.",
        "..oooooggdoooo..",
        "......oggdo.....",
        "......oggdo.....",
        "......oggdo.....",
        "......oggdo.....",
        "......oggdo.....",
        "......oggdo.....",
        "......odddo.....",
        ".......ooo......",
    ]),
    "king_bible": ("book", "item/generated", {
        "b": (0x1E, 0x3A, 0x8A), "B": (0x3B, 0x5F, 0xCC), "p": (0xF1, 0xE9, 0xD2),
        "g": (0xE8, 0xB8, 0x30), "o": (0x10, 0x18, 0x28),
    }, [
        "................",
        "..oooooooooooo..",
        ".oBBBBBBBBBBBbo.",
        ".oBbbbbbggbbbbo.",
        ".oBbbbbbggbbbbo.",
        ".oBbbbggggggbbo.",
        ".oBbbbggggggbbo.",
        ".oBbbbbbggbbbbo.",
        ".oBbbbbbggbbbbo.",
        ".oBbbbbbggbbbbo.",
        ".oBbbbbbbbbbbbo.",
        ".oBbbbbbbbbbbbo.",
        ".oBbbbbbbbbbbbo.",
        ".opppppppppppbo.",
        "..oooooooooooo..",
        "................",
    ]),
    # handheld: the Knife is rendered in an invisible vex's hand, not as a
    # free-floating display, so keep the vanilla in-hand transforms.
    "knife": ("iron_sword", "item/handheld", {
        "s": (0xC8, 0xCC, 0xD0), "S": (0xF4, 0xF6, 0xF8), "d": (0x7A, 0x80, 0x88),
        "h": (0x3A, 0x2A, 0x1A), "g": (0xB8, 0x90, 0x2A), "o": (0x1A, 0x1A, 0x1A),
    }, [
        ".............oo.",
        "............oSo.",
        "...........oSso.",
        "..........oSsdo.",
        ".........oSsdo..",
        "........oSsdo...",
        ".......oSsdo....",
        "......oSsdo.....",
        ".....oSsdo......",
        "....ogggo.......",
        "...ohhoo........",
        "..ohho..........",
        ".ohho...........",
        ".oho............",
        ".oo.............",
        "................",
    ]),
    "bone": ("bone", "item/generated", {
        "w": (0xF5, 0xF2, 0xEA), "W": (0xFF, 0xFF, 0xFF), "d": (0xC9, 0xC2, 0xB0),
        "o": (0x5A, 0x50, 0x40),
    }, [
        "............oooo",
        "...........oWWwo",
        "..........oWwwdo",
        ".........oWwddo.",
        "........oWwdo...",
        ".......oWwdo....",
        "......oWwdo.....",
        ".....oWwdo......",
        "....oWwdo.......",
        "...oWwdo........",
        "..oWwdo.........",
        ".oWwwdo.........",
        "oWWwwdo.........",
        "oWwddo..........",
        "owddo...........",
        "oooo............",
    ]),
    "peachone": ("feather", "item/generated", {
        "w": (0xF7, 0xF3, 0xF0), "W": (0xFF, 0xFF, 0xFF), "d": (0xC8, 0xBD, 0xB8),
        "p": (0xE8, 0x9A, 0xA0), "e": (0x20, 0x20, 0x20), "o": (0x4A, 0x40, 0x40),
    }, [
        ".......oo.......",
        "......oWwo......",
        ".....oWwweo.....",
        "......owwpo.....",
        "..oo..owwo..oo..",
        ".oWwo.owwo.oWwo.",
        "oWwwwooWwooWwwwo",
        "oWwwwwwwwwwwwwwo",
        ".odwwwwwwwwwwdo.",
        "..oddwwwwwwddo..",
        "....oodwwwdoo...",
        "......owwwo.....",
        "......owwwo.....",
        ".....owwwwwo....",
        ".....oddoddo....",
        "......oo.oo.....",
    ]),
}


def png_bytes(palette, rows):
    assert len(rows) == 16, "sprite must be 16 rows"
    raw = bytearray()
    for row in rows:
        assert len(row) == 16, f"row {row!r} is not 16 wide"
        raw.append(0)  # filter: none
        for ch in row:
            if ch == ".":
                raw += b"\0\0\0\0"
            else:
                r, g, b = palette[ch]
                raw += bytes((r, g, b, 255))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def dumps(obj):
    return json.dumps(obj, indent=2) + "\n"


def outputs():
    """{relative path: bytes} for everything this script owns."""
    out = {}
    by_item = {}
    for weapon, (item, parent, palette, rows) in SPRITES.items():
        out[f"assets/{NAMESPACE}/textures/item/{weapon}.png"] = png_bytes(palette, rows)
        out[f"assets/{NAMESPACE}/models/item/{weapon}.json"] = dumps({
            "parent": f"minecraft:{parent}",
            "textures": {"layer0": f"{NAMESPACE}:item/{weapon}"},
        }).encode()
        by_item.setdefault(item, []).append(weapon)
    for item, weapons in by_item.items():
        out[f"assets/minecraft/items/{item}.json"] = dumps({
            "model": {
                "type": "minecraft:select",
                "property": "minecraft:custom_model_data",
                "index": 0,
                "cases": [
                    {"when": f"{NAMESPACE}:{w}",
                     "model": {"type": "minecraft:model", "model": f"{NAMESPACE}:item/{w}"}}
                    for w in weapons
                ],
                "fallback": {"type": "minecraft:model", "model": f"minecraft:item/{item}"},
            }
        }).encode()
    return out


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
    # Every model referenced by an item definition must exist, with its texture.
    for item_def in (ROOT / "assets/minecraft/items").glob("*.json"):
        model = json.loads(item_def.read_text())["model"]
        for case in model["cases"]:
            ns, name = case["model"]["model"].split(":")
            model_path = ROOT / f"assets/{ns}/models/{name}.json"
            assert model_path.exists(), f"{item_def.name}: missing model {model_path}"
            tex = json.loads(model_path.read_text())["textures"]["layer0"]
            tns, tname = tex.split(":")
            assert (ROOT / f"assets/{tns}/textures/{tname}.png").exists(), f"{model_path.name}: missing texture {tex}"
    if check:
        if stale:
            print("STALE (run tools/build_items.py):\n  " + "\n  ".join(stale))
            return 1
        print(f"ok: {len(SPRITES)} sprites, {len(list((ROOT / 'assets/minecraft/items').glob('*.json')))} item definitions in sync")
    else:
        print(f"wrote {len(SPRITES)} sprites: {', '.join(SPRITES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
