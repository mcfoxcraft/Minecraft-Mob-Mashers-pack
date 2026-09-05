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


def recolor(rows, mapping):
    """Copy of `rows` with palette letters swapped per `mapping` (shape reuse)."""
    return ["".join(mapping.get(ch, ch) for ch in row) for row in rows]


def split_recolor(rows, mapping, from_x=8):
    """Copy of `rows` with `mapping` applied only to columns >= from_x — a two-tone
    variant of one shape (Vandalier = white left wing, black right wing)."""
    return ["".join((mapping.get(ch, ch) if x >= from_x else ch) for x, ch in enumerate(row)) for row in rows]


# Vanilla item definitions we override, copied from the 1.21.11 client jar so the
# fallback is byte-for-byte what a player without the pack renders today. Items
# not listed here are the plain single-model shape. `--client-jar <path>` checks
# this table against the real jar.
VANILLA_FALLBACKS = {
    "elytra": {
        "type": "minecraft:condition",
        "property": "minecraft:broken",
        "on_false": {"type": "minecraft:model", "model": "minecraft:item/elytra"},
        "on_true": {"type": "minecraft:model", "model": "minecraft:item/elytra_broken"},
    },
}

# ── shared shapes (16 rows × 16 cols) ─────────────────────────────────────────
AXE_ROWS = [
    "................",
    "..........oooo..",
    ".........oSSSSo.",
    "........oSSSSsdo",
    ".......oSSSssddo",
    "......obosssdddo",
    ".....oHbo.odddo.",
    "....oHHo...ooo..",
    "...oHHo.........",
    "..oHHo..........",
    ".oHHo...........",
    ".ohho...........",
    ".ohho...........",
    ".oho............",
    ".oo.............",
    "................",
]
BOOK_ROWS = [
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
]
BIRD_ROWS = [
    ".......oo.......",
    "......oWwo......",
    ".....oWwweo.....",
    "......owpo......",
    "......oWwo......",
    "oo...oWwwwo...oo",
    "oWwo.oWwwwwo.owo",
    "oWwwooWwwwwoowwo",
    ".oWwwwWwwwwwwwdo",
    "..odwwwwwwwwwdo.",
    "...oddwwwwwddo..",
    ".....oowwwoo....",
    "......owwwo.....",
    ".....owwwwwo....",
    ".....odd.ddo....",
    "......oo.oo.....",
]
# A full-size sword (bigger blade than the knife): S edge highlight, s blade,
# d blade shadow, g guard, h grip, o outline.
SWORD_ROWS = [
    "..............oo",
    ".............oSo",
    "............oSso",
    "...........oSsdo",
    "..........oSsdo.",
    ".........oSsdo..",
    "........oSsdo...",
    ".......oSsdo....",
    "......oSsdo.....",
    "..oo.oSsdo......",
    ".ogggggdo.......",
    "..oogghoo.......",
    "...ohho.........",
    "..ohho..........",
    ".ohho...........",
    ".oo.............",
]
CART_ROWS = [
    "................",
    "................",
    "................",
    ".oooooooooooooo.",
    "oGggggggggggggGo",
    "oGhhhhhhhhhhhhGo",
    "oGhHHhhHHhhHHhGo",
    "oGhhhhhhhhhhhhGo",
    "oGggggggggggggGo",
    ".oooooooooooooo.",
    "..oddo....oddo..",
    ".odssdo..odssdo.",
    ".odssdo..odssdo.",
    "..oddo....oddo..",
    "................",
    "................",
]
BLACK_BIRD = {"w": "k", "W": "K", "d": "D"}

# weapon id -> (vanilla item the plugin flies, model parent, palette, rows)
# Palette letters map to RGB; '.' is transparent. Rows are exactly 16 chars.
SPRITES = {
    "axe": ("iron_axe", "item/generated", {
        "h": (0x5E, 0x40, 0x24), "H": (0x8B, 0x62, 0x36), "b": (0x3A, 0x3A, 0x40),
        "s": (0xB8, 0xBE, 0xC6), "S": (0xEE, 0xF0, 0xF2), "d": (0x6C, 0x74, 0x7E),
        "o": (0x24, 0x22, 0x22),
    }, AXE_ROWS),
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
    }, BOOK_ROWS),
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
        "w": (0xEC, 0xE6, 0xD6), "W": (0xFF, 0xFF, 0xFA), "d": (0xBC, 0xB2, 0x9A),
        "o": (0x4A, 0x40, 0x34),
    }, [
        "..........oo.oo.",
        ".........oWWoWWo",
        ".........oWWWWWo",
        "..........oWWWdo",
        ".........oWwwdo.",
        "........oWwwdo..",
        ".......oWwwdo...",
        "......oWwwdo....",
        ".....oWwwdo.....",
        "....oWwwdo......",
        "...oWwwdo.......",
        "..oWwwdo........",
        ".odwwwo.........",
        "oWWWWWo.........",
        "oWWoWdo.........",
        ".oo.oo..........",
    ]),
    "peachone": ("feather", "item/generated", {
        "w": (0xF4, 0xEF, 0xEA), "W": (0xFF, 0xFF, 0xFF), "d": (0xC4, 0xB8, 0xB2),
        "p": (0xE8, 0x8A, 0x90), "e": (0x1A, 0x1A, 0x1A), "o": (0x30, 0x28, 0x28),
    }, BIRD_ROWS),
    # ── batch 2 (#5) ─────────────────────────────────────────────────────────
    "death_spiral": ("netherite_axe", "item/generated", {
        "h": (0x2E, 0x26, 0x3A), "H": (0x4A, 0x3E, 0x5C), "b": (0x6A, 0x1C, 0x8C),
        "s": (0x4C, 0x4A, 0x58), "S": (0x7E, 0x78, 0x92), "d": (0xB4, 0x3C, 0xE6),
        "o": (0x14, 0x10, 0x1A),
    }, AXE_ROWS),
    "heaven_sword": ("netherite_hoe", "item/generated", {
        "S": (0xFF, 0xFF, 0xF0), "s": (0xFF, 0xE6, 0x96), "d": (0xDC, 0xAA, 0x3C),
        "g": (0xE6, 0xB4, 0x32), "h": (0x78, 0x50, 0x28), "o": (0x3C, 0x28, 0x0A),
    }, SWORD_ROWS),
    "unholy_vespers": ("enchanted_book", "item/generated", {
        "b": (0x3C, 0x14, 0x5A), "B": (0x6E, 0x32, 0xA0), "p": (0xDC, 0xC8, 0xE6),
        "g": (0xE6, 0xBE, 0x3C), "o": (0x14, 0x05, 0x1E),
    }, BOOK_ROWS),
    "ebony_wings": ("phantom_membrane", "item/generated", {
        "k": (0x28, 0x26, 0x2E), "K": (0x48, 0x44, 0x52), "D": (0x14, 0x12, 0x18),
        "p": (0xC8, 0x28, 0x28), "e": (0xFF, 0x3C, 0x3C), "o": (0x0A, 0x08, 0x0C),
    }, recolor(BIRD_ROWS, BLACK_BIRD)),
    "vandalier": ("elytra", "item/generated", {
        "w": (0xF4, 0xEF, 0xEA), "W": (0xFF, 0xFF, 0xFF), "d": (0xC4, 0xB8, 0xB2),
        "k": (0x28, 0x26, 0x2E), "K": (0x48, 0x44, 0x52), "D": (0x14, 0x12, 0x18),
        "p": (0xE8, 0x8A, 0x90), "e": (0x1A, 0x1A, 0x1A), "o": (0x30, 0x28, 0x28),
    }, split_recolor(BIRD_ROWS, BLACK_BIRD)),
    "carrello": ("minecart", "item/generated", {
        "G": (0x96, 0x96, 0xA0), "g": (0x6E, 0x6E, 0x78), "h": (0x78, 0x50, 0x28),
        "H": (0x96, 0x69, 0x37), "d": (0x3C, 0x3C, 0x46), "s": (0x5A, 0x5A, 0x64),
        "o": (0x1E, 0x1E, 0x23),
    }, CART_ROWS),
    "fuwalafuwaloo": ("netherite_sword", "item/generated", {
        "S": (0xFF, 0x78, 0x78), "s": (0xC8, 0x1E, 0x28), "d": (0x78, 0x0A, 0x14),
        "g": (0x3C, 0x14, 0x14), "h": (0x1E, 0x0A, 0x0A), "o": (0x14, 0x05, 0x05),
    }, SWORD_ROWS),
    # "sacred wind": a pale green-white blade so it doesn't read as a second
    # Heaven Sword; gold guard keeps the holy family resemblance.
    "vento_sacro": ("golden_sword", "item/generated", {
        "S": (0xF0, 0xFF, 0xF0), "s": (0x96, 0xE6, 0xAA), "d": (0x3C, 0xA0, 0x64),
        "g": (0xC8, 0x96, 0x28), "h": (0x5A, 0x3C, 0x1E), "o": (0x1E, 0x3C, 0x28),
    }, SWORD_ROWS),
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
                "fallback": VANILLA_FALLBACKS.get(item, {"type": "minecraft:model", "model": f"minecraft:item/{item}"}),
            }
        }).encode()
    return out


def verify_against_client(jar_path):
    """Every fallback must equal the vanilla definition inside the client jar."""
    import zipfile
    with zipfile.ZipFile(jar_path) as jar:
        for item in {v[0] for v in SPRITES.values()}:
            vanilla = json.loads(jar.read(f"assets/minecraft/items/{item}.json"))["model"]
            ours = json.loads((ROOT / f"assets/minecraft/items/{item}.json").read_text())["model"]["fallback"]
            assert vanilla == ours, f"{item}: fallback differs from vanilla:\n  vanilla {vanilla}\n  ours    {ours}"
    print(f"fallbacks match the client jar for {len({v[0] for v in SPRITES.values()})} items")


def main(argv):
    check = "--check" in argv
    if "--client-jar" in argv:
        verify_against_client(argv[argv.index("--client-jar") + 1])
        return 0
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
        # The release zip must carry every generated file byte-for-byte; the
        # first build of #11 shipped a zip without any of them.
        dist = ROOT / "dist" / "foxmobmashers-resourcepack.zip"
        if dist.exists():
            import zipfile
            with zipfile.ZipFile(dist) as z:
                names = set(z.namelist())
                for rel, data in outputs().items():
                    if rel not in names:
                        stale.append(f"{rel} (missing from dist zip — run tools/build_dist.py)")
                    elif z.read(rel) != data:
                        stale.append(f"{rel} (dist zip has stale bytes — run tools/build_dist.py)")
                if z.read("pack.mcmeta") != (ROOT / "pack.mcmeta").read_bytes():
                    stale.append("pack.mcmeta (dist zip has stale bytes — run tools/build_dist.py)")
        if stale:
            print("STALE (run tools/build_items.py):\n  " + "\n  ".join(stale))
            return 1
        print(f"ok: {len(SPRITES)} sprites, {len(list((ROOT / 'assets/minecraft/items').glob('*.json')))} item definitions in sync")
    else:
        print(f"wrote {len(SPRITES)} sprites: {', '.join(SPRITES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
