#!/usr/bin/env python3
"""
Build the HUD textures + font definition from a BetterHud-format source pack.

The source pack ships per-frame PNGs (32 frames per animated element) and full
bar PNGs that BetterHud splits dynamically. Vanilla Minecraft can do neither at
runtime, so this script:

  * stitches the 32-frame sequences into vertical strips + .mcmeta animations
    so the client cycles them with no plugin chatter,
  * pre-slices each bar into 25 cumulative reveal frames so the plugin can pick
    a glyph by (value / max * 25) without per-tick image work,
  * copies static plates and avatar art straight through,
  * writes assets/foxmobmashers/font/hud.json wiring every output PNG to a
    Private-Use-Area codepoint that matches HudGlyphs.java in the plugin.

All outputs land under assets/foxmobmashers/textures/hud/ and the font dir;
both are gitignored because the source PNGs are licensed (3BSTUDIO graveyard
pack) and the generated artifacts are derivative.

Usage:
    python3 tools/build_hud_pack.py path/to/BetterHud_source/assets

The expected source layout is the BetterHud "Config Default/BetterHud/assets"
directory with these subpaths:
    hud_top_left/top_left{1..32}.png
    top_right/top_right.png
    top_right/{east,north,south,west}/{dir}{1..32}.png
    under/{left,right}/under_{left,right}{1..32}.png
    health_bar.png  armor_bar.png  exp_bar.png
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
TEXTURES_OUT = REPO_ROOT / "assets" / "foxmobmashers" / "textures" / "hud"
FONT_OUT = REPO_ROOT / "assets" / "foxmobmashers" / "font" / "hud.json"

# 32 frames @ 2 ticks each = 3.2s loop. Matches the original BetterHud cadence
# closely enough that the eye reads it as the same animation.
FRAMETIME_TICKS = 2
BAR_STEPS = 25

# Codepoint allocation — KEEP IN SYNC with HudGlyphs.java in the plugin.
# Plates render above the action-bar baseline (ascent < 0); under-plates
# render below (ascent > 0). Numeric ascents are tuned so the plate art
# lands roughly where BetterHud's renderer would have placed it relative
# to the screen center.
PLATES = [
    # (codepoint, output_png, ascent, height)
    (0xE000, "top_left.png",         -90, 44),
    (0xE001, "top_right_base.png",   -90, 44),
    (0xE002, "top_right_east.png",   -90, 44),
    (0xE003, "top_right_north.png",  -90, 44),
    (0xE004, "top_right_south.png",  -90, 44),
    (0xE005, "top_right_west.png",   -90, 44),
    (0xE006, "under_left.png",        60, 86),
    (0xE007, "under_right.png",       60, 86),
    (0xE008, "graveyard_head.png",   -90, 16),
]

# Bar codepoint ranges: each bar gets BAR_STEPS sequential codepoints starting
# at the base. Index 0 = empty, BAR_STEPS-1 = full.
BAR_BASES = {
    "health":  0xE020,
    "armor":   0xE040,
    "exp":     0xE060,
}
BAR_SOURCES = {
    "health":  ("health_bar.png", -78,  7),  # ascent below baseline so they sit at chest-bar level
    "armor":   ("armor_bar.png",  -85,  7),
    # Minecraft enforces ascent <= height on bitmap glyphs, so anything taller
    # than the exp bar's 3px height would fail font load. Keep it at the limit.
    "exp":     ("exp_bar.png",      3,  3),  # under the action-bar text — exp belt
}

# Horizontal positioning glyphs (space provider). Negative = backtrack,
# positive = forward. We expose a power-of-two ladder so the composer can
# stack glyphs to reach any pixel offset with at most ~10 chars.
SPACE_OFFSETS = [
    -512, -256, -128, -64, -32, -16, -8, -4, -2, -1,
       1,    2,    4,   8,  16,  32,  64, 128, 256, 512,
]
# Codepoints E100 .. E113 in the same order as SPACE_OFFSETS above.
SPACE_BASE = 0xE100


def die(msg: str) -> None:
    print(f"build_hud_pack: {msg}", file=sys.stderr)
    sys.exit(1)


def stitch_animated(src_dir: Path, frame_prefix: str, out_path: Path) -> None:
    """Concatenate 32 frames vertically into one strip + write .mcmeta."""
    frames = [src_dir / f"{frame_prefix}{i}.png" for i in range(1, 33)]
    missing = [f for f in frames if not f.is_file()]
    if missing:
        die(f"missing frames in {src_dir}: {[m.name for m in missing[:3]]}...")
    images = [Image.open(f).convert("RGBA") for f in frames]
    w = images[0].width
    h = images[0].height
    if any(img.size != (w, h) for img in images):
        die(f"frame size mismatch in {src_dir}")
    strip = Image.new("RGBA", (w, h * len(images)), (0, 0, 0, 0))
    for i, img in enumerate(images):
        strip.paste(img, (0, i * h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)
    mcmeta = {"animation": {"frametime": FRAMETIME_TICKS, "interpolate": False}}
    out_path.with_suffix(out_path.suffix + ".mcmeta").write_text(
        json.dumps(mcmeta, indent=2) + "\n"
    )


def slice_bar(src: Path, out_dir: Path, name: str) -> None:
    """Write BAR_STEPS PNGs each revealing (i+1)/BAR_STEPS of the source bar.

    Each output is the FULL source size with the right portion masked
    transparent — keeps the glyph advance constant so the bar doesn't shift
    around the screen as it fills.
    """
    if not src.is_file():
        die(f"missing bar source {src}")
    base = Image.open(src).convert("RGBA")
    w, h = base.size
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(BAR_STEPS):
        # Reveal pixels [0, fill_px). i=0 gives an empty bar, i=BAR_STEPS-1 full.
        fill_px = round((i + 1) * w / BAR_STEPS)
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if fill_px > 0:
            frame.paste(base.crop((0, 0, fill_px, h)), (0, 0))
        frame.save(out_dir / f"{name}_{i:02d}.png")


def emit_font(width_map: dict[int, int]) -> None:
    """Write hud.json wiring every codepoint to its texture/advance.

    width_map[codepoint] = source PNG width in pixels — needed so we can set
    the bitmap glyph's height without distorting it (Minecraft scales bitmap
    glyphs to `height` while preserving aspect ratio via the source image).
    """
    providers: list[dict] = []

    def chr_(cp: int) -> str:
        return chr(cp)

    # Plates (single PNG each)
    for cp, fname, ascent, height in PLATES:
        providers.append({
            "type": "bitmap",
            "file": f"foxmobmashers:hud/{fname}",
            "ascent": ascent,
            "height": height,
            "chars": [chr_(cp)],
        })

    # Bar slices
    for bar, base in BAR_BASES.items():
        _, ascent, height = BAR_SOURCES[bar]
        for i in range(BAR_STEPS):
            providers.append({
                "type": "bitmap",
                "file": f"foxmobmashers:hud/{bar}/{bar}_{i:02d}.png",
                "ascent": ascent,
                "height": height,
                "chars": [chr_(base + i)],
            })

    # Space provider — a single entry holds every horizontal-shift codepoint.
    advances: dict[str, int] = {}
    for i, offset in enumerate(SPACE_OFFSETS):
        advances[chr_(SPACE_BASE + i)] = offset
    providers.append({"type": "space", "advances": advances})

    FONT_OUT.parent.mkdir(parents=True, exist_ok=True)
    FONT_OUT.write_text(json.dumps({"providers": providers}, indent=2) + "\n")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: build_hud_pack.py <BetterHud assets dir>")
    src = Path(sys.argv[1]).resolve()
    if not src.is_dir():
        die(f"source not found: {src}")

    if TEXTURES_OUT.exists():
        shutil.rmtree(TEXTURES_OUT)
    TEXTURES_OUT.mkdir(parents=True)

    # Animated plates
    stitch_animated(src / "hud_top_left", "top_left",      TEXTURES_OUT / "top_left.png")
    stitch_animated(src / "top_right" / "east",  "east",   TEXTURES_OUT / "top_right_east.png")
    stitch_animated(src / "top_right" / "north", "north",  TEXTURES_OUT / "top_right_north.png")
    stitch_animated(src / "top_right" / "south", "south",  TEXTURES_OUT / "top_right_south.png")
    stitch_animated(src / "top_right" / "west",  "west",   TEXTURES_OUT / "top_right_west.png")
    stitch_animated(src / "under" / "left",  "under_left",  TEXTURES_OUT / "under_left.png")
    stitch_animated(src / "under" / "right", "under_right", TEXTURES_OUT / "under_right.png")

    # Static plates
    shutil.copy(src / "top_right" / "top_right.png", TEXTURES_OUT / "top_right_base.png")

    # Graveyard avatar — sourced from the heads dir if present, otherwise we
    # just skip silently and the avatar glyph renders blank.
    head_src = src.parent / "heads" / "graveyard_head.png"
    if head_src.is_file():
        shutil.copy(head_src, TEXTURES_OUT / "graveyard_head.png")
    else:
        # 16x16 transparent placeholder so the font reference doesn't 404.
        Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(TEXTURES_OUT / "graveyard_head.png")

    # Bar slices
    for bar, (fname, _, _) in BAR_SOURCES.items():
        slice_bar(src / fname, TEXTURES_OUT / bar, bar)

    # Font JSON — width_map currently unused but kept threaded so it's easy
    # to introduce per-glyph aspect tweaks later without rewriting the call.
    emit_font(width_map={})

    print(f"wrote {TEXTURES_OUT}")
    print(f"wrote {FONT_OUT}")


if __name__ == "__main__":
    main()
