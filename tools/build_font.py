#!/usr/bin/env python3
"""Damage-number font for VFX step 3 (issue #7).

Writes
  assets/foxmobmashers/textures/font/damage.png   10 digits in one row, 12x16 cells:
                                                  a 5x7 pixel font at 2x with a 1px
                                                  dark outline baked in; white fill so
                                                  the text colour tints it
  assets/foxmobmashers/font/damage.json           two bitmap providers over that image:
                                                  U+E400..E409 normal (height 12),
                                                  U+E410..E419 big   (height 18, crits / one-shots)

The plugin's effects/DamageFont maps digits onto those codepoints and sets the
font key foxmobmashers:damage on the text display; players without the pack get
a plain-digit display instead (viewer partition), so there is no fallback path.

    python3 tools/build_font.py          # (re)generate
    python3 tools/build_font.py --check  # verify tree + dist zip
"""
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = "foxmobmashers"

DIGITS = [
    [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    [" ### ", "#   #", "    #", " ### ", "    #", "#   #", " ### "],
    ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
]
CELL_W, CELL_H, SCALE = 12, 16, 2
FILL = (255, 255, 255, 255)
OUTLINE = (34, 34, 40, 255)
NORMAL_BASE, BIG_BASE = 0xE400, 0xE410


def render():
    w, h = CELL_W * 10, CELL_H
    px = [[(0, 0, 0, 0)] * w for _ in range(h)]
    for d, rows in enumerate(DIGITS):
        assert len(rows) == 7 and all(len(r) == 5 for r in rows), d
        ox, oy = d * CELL_W + 1, 1
        on = set()
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    for dy in range(SCALE):
                        for dx in range(SCALE):
                            on.add((ox + x * SCALE + dx, oy + y * SCALE + dy))
        for (x, y) in on:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x + dx, y + dy) not in on and px[y + dy][x + dx][3] == 0:
                        px[y + dy][x + dx] = OUTLINE
        for (x, y) in on:
            px[y][x] = FILL
    raw = bytearray()
    for row in px:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def chars(base):
    return "".join(chr(base + i) for i in range(10))


def outputs():
    return {
        f"assets/{NS}/textures/font/damage.png": render(),
        f"assets/{NS}/font/damage.json": (json.dumps({
            "providers": [
                # ascent = pixels of the (scaled) glyph above the baseline: the outline
                # row + 14 px of digit → the digit's bottom sits on the baseline.
                {"type": "bitmap", "file": f"{NS}:font/damage.png", "height": 12, "ascent": 11,
                 "chars": [chars(NORMAL_BASE)]},
                {"type": "bitmap", "file": f"{NS}:font/damage.png", "height": 18, "ascent": 16,
                 "chars": [chars(BIG_BASE)]},
            ]
        }, indent=2, ensure_ascii=True) + "\n").encode(),
    }


def main(argv):
    check = "--check" in argv
    stale = []
    outs = outputs()
    for rel, data in outs.items():
        path = ROOT / rel
        if check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if check:
        dist = ROOT / "dist" / "foxmobmashers-resourcepack.zip"
        if dist.exists():
            import zipfile
            with zipfile.ZipFile(dist) as z:
                names = set(z.namelist())
                for rel, data in outs.items():
                    if rel not in names:
                        stale.append(f"{rel} (missing from dist zip — run tools/build_dist.py)")
                    elif z.read(rel) != data:
                        stale.append(f"{rel} (dist zip has stale bytes — run tools/build_dist.py)")
        if stale:
            print("STALE (run tools/build_font.py):\n  " + "\n  ".join(stale))
            return 1
        print("ok: damage font in sync")
    else:
        print("wrote damage font (10 digits, normal U+E400.. / big U+E410..)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
