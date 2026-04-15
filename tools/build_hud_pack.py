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

import base64
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
TEXTURES_OUT = REPO_ROOT / "assets" / "foxmobmashers" / "textures" / "hud"
# Override minecraft:default font instead of adding a namespaced font. Some
# client versions silently drop custom-font style attributes on action bar
# components (presumably a Paper<->Adventure serialization quirk), so the
# glyphs fall back to unifont even when the pack is loaded. Overriding
# default means the PUA codepoints resolve to our bitmaps from any component
# without needing a Style.font() annotation on the server side.
FONT_OUT = REPO_ROOT / "assets" / "minecraft" / "font" / "default.json"

# 32 frames @ 2 ticks each = 3.2s loop. Matches the original BetterHud cadence
# closely enough that the eye reads it as the same animation.
FRAMETIME_TICKS = 2
BAR_STEPS = 25

# Codepoint allocation — KEEP IN SYNC with HudGlyphs.java in the plugin.
# Plates render above the action-bar baseline (ascent < 0); under-plates
# render below (ascent > 0). Numeric ascents are tuned so the plate art
# lands roughly where BetterHud's renderer would have placed it relative
# to the screen center.
# Single source of truth for the top-left plate group's vertical
# position. The skull, balance, and time ascents below are all expressed
# as offsets from it, so raising this shifts the entire group upward
# (plate + head + both text rows).
# Natural height of the plate's content (44) plus TOP_LEFT_DOWN_SHIFT
# of extra rows below the content. Raising TOP_LEFT_DOWN_SHIFT pushes
# the entire boss-bar-rendered group DOWNWARD on screen: every glyph's
# canvas grows by that amount and its content stays bottom-anchored,
# so with the ascent unchanged the visible pixels slide lower.
TOP_LEFT_NATURAL_H  = 44
TOP_LEFT_DOWN_SHIFT = 50
TOP_PLATE_PADDED_HEIGHT = TOP_LEFT_NATURAL_H + TOP_LEFT_DOWN_SHIFT

PLATES = [
    # (codepoint, output_png, ascent, height)
    # Minecraft enforces 0 <= ascent <= height, where ascent = pixels the
    # glyph extends above the text baseline. Content sits at the top of a
    # padded canvas; ascent == padded_height pushes that content upward.
    (0xE000, "top_left.png",         TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    (0xE001, "top_right_base.png",   TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    (0xE002, "top_right_east.png",   TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    (0xE003, "top_right_north.png",  TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    (0xE004, "top_right_south.png",  TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    (0xE005, "top_right_west.png",   TOP_PLATE_PADDED_HEIGHT, TOP_PLATE_PADDED_HEIGHT),
    # Under plates sit at hotbar level framing the hotbar.
    (0xE006, "under_left.png",        22, 86),
    (0xE007, "under_right.png",       22, 86),
    (0xE008, "graveyard_head.png",    16, 16),
    # Synthesized middle connector — tiled plate body that bridges the gap
    # across the hotbar between the left and right under plates.
    (0xE009, "under_middle.png",      22, 86),
]

# Custom digit glyphs used to render coin balance + run timer on top of
# the top-left plate. 5 pixel cols * 7 rows per digit, padded to a tall
# canvas so a high ascent can land the content inside the plate art.
DIGIT_CELL_W = 5
DIGIT_CELL_H = 7
DIGIT_PATTERNS = {
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': [".##..", "###..", ".##..", ".##..", ".##..", ".##..", "####."],
    '2': [".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"],
    '3': [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': [".###.", "#...#", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "#...#", ".###."],
    ':': ["....", "..#.", "..#.", "....", "..#.", "..#.", "...."],
}

# Compact 3x5 digit patterns used for the level readout in the
# medallion — visibly smaller than the 5x7 balance/time digits.
SMALL_DIGIT_PATTERNS = {
    '0': ["###", "#.#", "#.#", "#.#", "###"],
    '1': [".#.", "##.", ".#.", ".#.", "###"],
    '2': ["##.", "..#", ".#.", "#..", "###"],
    '3': ["##.", "..#", ".#.", "..#", "##."],
    '4': ["#.#", "#.#", "###", "..#", "..#"],
    '5': ["###", "#..", "##.", "..#", "##."],
    '6': [".##", "#..", "###", "#.#", "###"],
    '7': ["###", "..#", "..#", ".#.", ".#."],
    '8': ["###", "#.#", "###", "#.#", "###"],
    '9': ["###", "#.#", "###", "..#", "##."],
    ':': ["..", ".#", "..", ".#", ".."],
}
SMALL_DIGIT_ADVANCE = 4  # texture width 3 + 1 default spacing

# Codepoint ranges for the digit providers. Balance uses one ascent,
# time uses a lower ascent so they stack vertically on the plate.
DIGIT_BASE_BALANCE = 0xE200  # 0..9 at 0xE200..0xE209, ':' at 0xE20A
DIGIT_BASE_TIME    = 0xE220  # 0..9 at 0xE220..0xE229, ':' at 0xE22A
DIGIT_BASE_LEVEL   = 0xE240  # 0..9 at 0xE240..0xE249, ':' at 0xE24A
SKULL_CODEPOINT    = 0xE3FF  # Fallback skull icon (no per-character head)

# Per-character head codepoints. KEEP IN SYNC with HudGlyphs.java
# CHARACTER_HEAD_CODEPOINTS in the plugin — the plugin looks the
# codepoint up by character id to pick which glyph to render.
CHARACTER_HEAD_CODEPOINTS = {
    "antonio":   0xE300,
    "imelda":    0xE301,
    "pasqualina":0xE302,
    "gennaro":   0xE303,
    "arca":      0xE304,
    "porta":     0xE305,
    "lama":      0xE306,
    "poe":       0xE307,
    "clerici":   0xE308,
    "dommario":  0xE309,
    "krochi":    0xE30A,
    "christine": 0xE30B,
    "pugnala":   0xE30C,
    "giovanna":  0xE30D,
    "mortaccio": 0xE30E,
}
# ── Top-left plate group ascent offsets (relative to TOP_PLATE_PADDED_HEIGHT) ──
# Each offset is how many pixels BELOW the plate's top edge the glyph's
# top renders. Raising TOP_PLATE_PADDED_HEIGHT lifts the whole group;
# these offsets keep the elements' relative positions locked.
BALANCE_ASCENT_OFFSET = 10   # balance digits 10 px below plate top
TIME_ASCENT_OFFSET    = 24   # time digits 24 px below plate top
HEAD_ASCENT_OFFSET    = 10   # head 10 px below plate top
DIGIT_BALANCE_ASCENT  = TOP_LEFT_NATURAL_H - BALANCE_ASCENT_OFFSET
DIGIT_TIME_ASCENT     = TOP_LEFT_NATURAL_H - TIME_ASCENT_OFFSET
# Level sits in the medallion diamond at the top-center of the bottom
# HUD. Ascent alone can't go below 0, so to push level DOWN below
# baseline we render its digit content at the bottom of a shorter
# canvas (SMALL_DIGIT_CANVAS_H), then use an ascent that offsets the
# whole glyph so the visible content lands where the diamond sits
# (roughly -10 below the action-bar baseline).
DIGIT_LEVEL_ASCENT   = 6
# Canvas for balance + time digits. Tracks TOP_PLATE_PADDED_HEIGHT so
# ascent <= height stays satisfied when the group is lifted.
DIGIT_CANVAS_H       = TOP_PLATE_PADDED_HEIGHT
SMALL_DIGIT_CANVAS_H = 30   # level canvas (smaller, content at bottom)

# Character head canvas. 16x16 head content pasted at the top of a tall
# canvas so ascent=HEAD_ASCENT lifts it up onto the top-left plate.
HEAD_CONTENT_PX = 16
HEAD_CANVAS_H   = TOP_PLATE_PADDED_HEIGHT  # keeps ascent<=height
HEAD_ASCENT     = TOP_LEFT_NATURAL_H - HEAD_ASCENT_OFFSET

# Bar codepoint ranges: each bar gets BAR_STEPS sequential codepoints starting
# at the base. Index 0 = empty, BAR_STEPS-1 = full.
BAR_BASES = {
    "health":  0xE020,
    "armor":   0xE040,
    "exp":     0xE060,
}
BAR_SOURCES = {
    # (file, ascent, height). ascent must be ≤ height or MC aborts font
    # load. Health bar content sits in the bottom rows of a padded canvas
    # so it lands on the plate's HEART label. Exp bar does the same but
    # with an even lower ascent, dropping it onto the vanilla XP bar
    # strip below the hotbar.
    "health":  ("health_bar.png",   9, 40),
    "armor":   ("armor_bar.png",   15, 20),
    "exp":     ("exp_bar.png",      2, 40),
}
BAR_PAD_HEIGHT = {
    "health": 40,
    "armor":  20,
    "exp":    40,
}
BAR_CONTENT_AT_BOTTOM = {"health", "exp"}

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


def stitch_animated(src_dir: Path, frame_prefix: str, out_path: Path,
                    pad_to_height: int = 0,
                    content_at_bottom: bool = False) -> None:
    """Copy frame 1 as the plate texture, optionally padded with
    transparent rows at the bottom.

    Font bitmap providers do not respect the .mcmeta animation spec that
    block/item textures use — Minecraft treats the whole PNG as a single
    glyph and scales it to match ``height``, turning a 32-frame vertical
    strip into a sliver ~3 pixels wide. Until we find a pack-side way to
    animate font glyphs (probably requires shader work), we ship one
    frame and accept a static plate.

    When ``pad_to_height`` is nonzero, the frame is placed at the TOP of
    a transparent canvas of that height. Combined with a large ``ascent``
    value, this pushes the visible content toward the top of the screen
    while keeping the rest of the glyph transparent. A sentinel alpha=1
    pixel at bottom-right pins the advance so MC's auto-crop doesn't
    collapse the padded columns.
    """
    frame1 = src_dir / f"{frame_prefix}1.png"
    if not frame1.is_file():
        die(f"missing frame 1 in {src_dir}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if pad_to_height <= 0:
        shutil.copy(frame1, out_path)
        return
    src_img = Image.open(frame1).convert("RGBA")
    w = src_img.width
    padded = Image.new("RGBA", (w, pad_to_height), (0, 0, 0, 0))
    paste_y = pad_to_height - src_img.height if content_at_bottom else 0
    padded.paste(src_img, (0, paste_y))
    # Sentinel next to the content's top-right edge so MC doesn't
    # auto-crop transparent columns and collapse the glyph's advance,
    # but also doesn't extend the glyph's vertical bounding box to the
    # full padded canvas height.
    padded.putpixel((w - 1, paste_y), (0, 0, 0, 1))
    padded.save(out_path)


def slice_bar(src: Path, out_dir: Path, name: str,
              pad_to_height: int = 0,
              content_at_bottom: bool = False) -> None:
    """Write BAR_STEPS PNGs each revealing (i+1)/BAR_STEPS of the source bar.

    Every output is the FULL source size with a right-side transparency
    mask for the unfilled portion. Crucially we place a single alpha=1
    sentinel pixel at each slice's top-right corner: Minecraft auto-crops
    trailing fully-transparent columns from a bitmap glyph's advance,
    which would otherwise make lower-fill slices narrower than higher-fill
    ones — shifting the whole action bar every time the value changed.
    The sentinel is practically invisible (alpha 1/255) but keeps the
    glyph's advance pinned to the source's full pixel width.

    ``pad_to_height``: if > source h, each slice is placed at the TOP of
    a canvas that tall and the rest left transparent. Used so we can set
    ascent > source_h (e.g. to lift the armor bar above the HEART row)
    while still satisfying MC's ascent ≤ height constraint.
    """
    if not src.is_file():
        die(f"missing bar source {src}")
    base = Image.open(src).convert("RGBA")
    w, src_h = base.size
    canvas_h = max(src_h, pad_to_height)
    out_dir.mkdir(parents=True, exist_ok=True)
    paste_y = canvas_h - src_h if content_at_bottom else 0
    for i in range(BAR_STEPS):
        fill_px = round((i + 1) * w / BAR_STEPS)
        frame = Image.new("RGBA", (w, canvas_h), (0, 0, 0, 0))
        if fill_px > 0:
            frame.paste(base.crop((0, 0, fill_px, src_h)), (0, paste_y))
        frame.putpixel((w - 1, 0), (0, 0, 0, 1))
        frame.save(out_dir / f"{name}_{i:02d}.png")


def extract_head_from_skin(skin_png: Image.Image) -> Image.Image:
    """Composite the 8x8 face + hat overlay, upscale to HEAD_CONTENT_PX
    with nearest-neighbor, and paste at the top of a HEAD_CONTENT_PX-wide
    × HEAD_CANVAS_H-tall canvas so a high ascent lifts it onto the plate."""
    face = skin_png.crop((8, 8, 16, 16)).convert("RGBA")
    hat = skin_png.crop((40, 8, 48, 16)).convert("RGBA")
    head8 = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    head8.paste(face, (0, 0))
    head8.alpha_composite(hat)
    head = head8.resize((HEAD_CONTENT_PX, HEAD_CONTENT_PX), Image.NEAREST)
    canvas = Image.new("RGBA", (HEAD_CONTENT_PX, HEAD_CANVAS_H), (0, 0, 0, 0))
    # Content bottom-anchored so the TOP_LEFT_DOWN_SHIFT padding pushes
    # the visible head downward with the rest of the group.
    paste_y = HEAD_CANVAS_H - HEAD_CONTENT_PX
    canvas.paste(head, (0, paste_y))
    canvas.putpixel((HEAD_CONTENT_PX - 1, paste_y), (255, 255, 255, 1))
    return canvas


def build_character_heads(out_dir: Path) -> set[str]:
    """Parse tools/character_skins.yaml, download each skin PNG, extract
    the 8x8 head, and save it as ``heads/<character_id>.png``. Cached in
    tools/skin_cache/<hash>.png so repeat builds don't re-download.

    Returns the set of character ids for which a head was produced."""
    try:
        import yaml  # type: ignore
    except ImportError:
        print("character_heads: PyYAML not installed, skipping character head generation", file=sys.stderr)
        return set()

    tools_dir = Path(__file__).resolve().parent
    skins_path = tools_dir / "character_skins.yaml"
    if not skins_path.is_file():
        return set()
    with open(skins_path) as f:
        skins = yaml.safe_load(f) or {}

    cache_dir = tools_dir / "skin_cache"
    cache_dir.mkdir(exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    produced: set[str] = set()
    for char_id, entry in skins.items():
        if not isinstance(entry, dict) or "value" not in entry:
            continue
        if char_id not in CHARACTER_HEAD_CODEPOINTS:
            print(f"character_heads: unknown character id '{char_id}' — add to CHARACTER_HEAD_CODEPOINTS")
            continue
        try:
            decoded = base64.b64decode(entry["value"]).decode()
            payload = json.loads(decoded)
            url = payload["textures"]["SKIN"]["url"]
        except Exception as e:
            print(f"character_heads: {char_id} — failed to decode skin value: {e}")
            continue

        cache_key = hashlib.sha1(url.encode()).hexdigest()
        cached = cache_dir / f"{cache_key}.png"
        if not cached.is_file():
            # textures.minecraft.net redirects http → https cleanly but some
            # CDNs reject plain http requests without a user-agent, so we
            # force-upgrade and set one.
            https_url = url.replace("http://", "https://", 1)
            req = urllib.request.Request(https_url, headers={"User-Agent": "foxmobmashers-pack-build"})
            with urllib.request.urlopen(req, timeout=10) as r:
                cached.write_bytes(r.read())

        skin_img = Image.open(cached).convert("RGBA")
        head = extract_head_from_skin(skin_img)
        head.save(out_dir / f"{char_id}.png")
        produced.add(char_id)
        print(f"character_heads: {char_id} -> {out_dir / (char_id + '.png')}")
    return produced


def render_placeholder_skull(out_path: Path) -> None:
    """Pixel-art skull pasted at the top of a HEAD_CONTENT_PX wide ×
    HEAD_CANVAS_H tall canvas — same geometry as character heads so both
    render at the same size + position via the same ascent."""
    pattern = [
        ".######.",
        "########",
        "#.##.##.",
        "########",
        "#.####.#",
        "########",
        "##.##.##",
        ".######.",
    ]
    head8 = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y, row in enumerate(pattern):
        for x, c in enumerate(row):
            if c == "#":
                head8.putpixel((x, y), (220, 220, 210, 255))
    head = head8.resize((HEAD_CONTENT_PX, HEAD_CONTENT_PX), Image.NEAREST)
    canvas = Image.new("RGBA", (HEAD_CONTENT_PX, HEAD_CANVAS_H), (0, 0, 0, 0))
    paste_y = HEAD_CANVAS_H - HEAD_CONTENT_PX
    canvas.paste(head, (0, paste_y))
    canvas.putpixel((HEAD_CONTENT_PX - 1, paste_y), (255, 255, 255, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def mask_regions(png_path: Path, regions, fill=(0, 0, 0, 0)) -> None:
    """Erase opaque pixels inside ``regions`` (set alpha=0 by default)
    to cut away label text and bar art from the plate. Pixels that were
    already transparent are untouched so the plate's overall silhouette
    stays identical — only the letters/bars become holes."""
    im = Image.open(png_path).convert("RGBA")
    for (x1, y1, x2, y2) in regions:
        for y in range(y1, y2):
            for x in range(x1, x2):
                if im.getpixel((x, y))[3] >= 128:
                    im.putpixel((x, y), fill)
    im.save(png_path)


def render_digits(out_dir: Path, patterns, canvas_h: int,
                  content_at_bottom: bool = False) -> None:
    """Draw each digit pattern into a canvas_h-tall canvas. content_at_bottom
    shifts the pixel art down to the last rows so a low ascent places the
    visible content below baseline.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for ch, rows in patterns.items():
        w = max(len(r) for r in rows)
        img = Image.new("RGBA", (w, canvas_h), (0, 0, 0, 0))
        pattern_h = len(rows)
        y_offset = canvas_h - pattern_h if content_at_bottom else 0
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c == "#":
                    img.putpixel((x, y + y_offset), (255, 255, 255, 255))
        img.putpixel((w - 1, 0), (255, 255, 255, 1))
        safe = "colon" if ch == ":" else ch
        img.save(out_dir / f"{safe}.png")


def emit_font(width_map: dict[int, int], character_head_ids: set[str]) -> None:
    """Write default.json wiring every codepoint to its texture/advance.

    width_map[codepoint] = source PNG width in pixels — needed so we can set
    the bitmap glyph's height without distorting it (Minecraft scales bitmap
    glyphs to `height` while preserving aspect ratio via the source image).

    We override minecraft:default, so must first chain in the vanilla default
    providers via reference so normal ASCII + unifont keep working.
    """
    providers: list[dict] = [
        {"type": "reference", "id": "minecraft:include/space"},
        {"type": "reference", "id": "minecraft:include/default"},
        {"type": "reference", "id": "minecraft:include/unifont"},
    ]

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

    # Placeholder skull glyph — fallback when no per-character head is
    # shipped for the player's selected character. 16x16 content at the
    # top of a tall padded canvas, same geometry as character heads.
    providers.append({
        "type": "bitmap",
        "file": "foxmobmashers:hud/skull.png",
        "ascent": HEAD_ASCENT,
        "height": HEAD_CANVAS_H,
        "chars": [chr_(SKULL_CODEPOINT)],
    })

    # Per-character head glyphs. Only emitted for characters whose skins
    # were decoded in build_character_heads — unknown ids fall back to
    # the placeholder skull via the plugin's character → codepoint map.
    for char_id in sorted(character_head_ids):
        providers.append({
            "type": "bitmap",
            "file": f"foxmobmashers:hud/heads/{char_id}.png",
            "ascent": HEAD_ASCENT,
            "height": HEAD_CANVAS_H,
            "chars": [chr_(CHARACTER_HEAD_CODEPOINTS[char_id])],
        })

    # Digit glyphs for on-plate readouts. Balance + time use 5x7 digits
    # from digits/, level uses the compact 3x5 digits from digits_small/.
    for base_cp, ascent, dir_, h in [
        (DIGIT_BASE_BALANCE, DIGIT_BALANCE_ASCENT, "digits",       DIGIT_CANVAS_H),
        (DIGIT_BASE_TIME,    DIGIT_TIME_ASCENT,    "digits",       DIGIT_CANVAS_H),
        (DIGIT_BASE_LEVEL,   DIGIT_LEVEL_ASCENT,   "digits_small", SMALL_DIGIT_CANVAS_H),
    ]:
        for i, ch in enumerate("0123456789"):
            providers.append({
                "type": "bitmap",
                "file": f"foxmobmashers:hud/{dir_}/{ch}.png",
                "ascent": ascent,
                "height": h,
                "chars": [chr_(base_cp + i)],
            })
        providers.append({
            "type": "bitmap",
            "file": f"foxmobmashers:hud/{dir_}/colon.png",
            "ascent": ascent,
            "height": h,
            "chars": [chr_(base_cp + 10)],
        })

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

    # Top plates: content bottom-anchored in a canvas padded by
    # TOP_LEFT_DOWN_SHIFT. With ascent unchanged the visible plate art
    # slides downward on screen by the same number of pixels.
    stitch_animated(src / "hud_top_left", "top_left",
                    TEXTURES_OUT / "top_left.png",
                    pad_to_height=TOP_PLATE_PADDED_HEIGHT,
                    content_at_bottom=True)
    stitch_animated(src / "top_right" / "east",  "east",
                    TEXTURES_OUT / "top_right_east.png",
                    pad_to_height=TOP_PLATE_PADDED_HEIGHT,
                    content_at_bottom=True)
    stitch_animated(src / "top_right" / "north", "north",
                    TEXTURES_OUT / "top_right_north.png",
                    pad_to_height=TOP_PLATE_PADDED_HEIGHT,
                    content_at_bottom=True)
    stitch_animated(src / "top_right" / "south", "south",
                    TEXTURES_OUT / "top_right_south.png",
                    pad_to_height=TOP_PLATE_PADDED_HEIGHT,
                    content_at_bottom=True)
    stitch_animated(src / "top_right" / "west",  "west",
                    TEXTURES_OUT / "top_right_west.png",
                    pad_to_height=TOP_PLATE_PADDED_HEIGHT,
                    content_at_bottom=True)
    stitch_animated(src / "under" / "left",  "under_left",
                    TEXTURES_OUT / "under_left.png")
    stitch_animated(src / "under" / "right", "under_right",
                    TEXTURES_OUT / "under_right.png")

    # Erase unwanted label text + bar art by setting those pixels to
    # alpha=0. The plate body around them stays opaque so the silhouette
    # of the plate is unchanged — only the labels/bars become holes.
    # Plate-texture masking disabled — the user is supplying hand-edited
    # under_left.png / under_right.png.

    # Static top-right base plate — bottom-anchored in the padded canvas
    # to match the animated plates.
    base_src = Image.open(src / "top_right" / "top_right.png").convert("RGBA")
    padded = Image.new("RGBA",
                       (base_src.width, TOP_PLATE_PADDED_HEIGHT),
                       (0, 0, 0, 0))
    paste_y = TOP_PLATE_PADDED_HEIGHT - base_src.height
    padded.paste(base_src, (0, paste_y))
    padded.putpixel((base_src.width - 1, paste_y), (0, 0, 0, 1))
    padded.save(TEXTURES_OUT / "top_right_base.png")

    # Graveyard avatar — sourced from the heads dir if present, otherwise we
    # just skip silently and the avatar glyph renders blank.
    head_src = src.parent / "heads" / "graveyard_head.png"
    if head_src.is_file():
        shutil.copy(head_src, TEXTURES_OUT / "graveyard_head.png")
    else:
        # 16x16 transparent placeholder + sentinel pixel at top-right so MC
        # doesn't auto-crop the glyph's advance down to zero. Without the
        # sentinel, placeElement's shift-back math under-compensates and
        # every HUD frame drifts by the missing 17 pixels.
        ph = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        ph.putpixel((15, 0), (0, 0, 0, 1))
        ph.save(TEXTURES_OUT / "graveyard_head.png")

    # Bar slices
    for bar, (fname, _, _) in BAR_SOURCES.items():
        slice_bar(src / fname, TEXTURES_OUT / bar, bar,
                  pad_to_height=BAR_PAD_HEIGHT.get(bar, 0),
                  content_at_bottom=(bar in BAR_CONTENT_AT_BOTTOM))
    # If a local override exists, swap it in for the final plate texture.
    # The user hand-edits under_left.png / under_right.png (e.g. to erase
    # label art) and drops them under tools/overrides/ — build script
    # copies them over the stitched output.
    overrides = Path(__file__).resolve().parent / "overrides"
    for name in ("under_left.png", "under_right.png"):
        candidate = overrides / name
        if candidate.is_file():
            shutil.copy(candidate, TEXTURES_OUT / name)
            print(f"override: {candidate} -> {TEXTURES_OUT / name}")

    # Custom digit glyphs. Balance + time: large 5x7 at canvas-top so
    # high ascent lifts them up. Level: compact 3x5 at canvas-BOTTOM so
    # low ascent drops them below baseline into the medallion.
    # Content bottom-anchored so the TOP_LEFT_DOWN_SHIFT padding in
    # DIGIT_CANVAS_H shifts the balance/time digits downward on screen.
    render_digits(TEXTURES_OUT / "digits", DIGIT_PATTERNS, DIGIT_CANVAS_H,
                  content_at_bottom=True)
    render_digits(TEXTURES_OUT / "digits_small", SMALL_DIGIT_PATTERNS,
                  SMALL_DIGIT_CANVAS_H, content_at_bottom=True)

    # Placeholder skull icon for the character slot on the top-left plate.
    # overrides/skull.png (if present) wins so a proper per-character head
    # can be dropped in later.
    render_placeholder_skull(TEXTURES_OUT / "skull.png")
    skull_override = Path(__file__).resolve().parent / "overrides" / "skull.png"
    if skull_override.is_file():
        shutil.copy(skull_override, TEXTURES_OUT / "skull.png")
        print(f"override: {skull_override} -> {TEXTURES_OUT / 'skull.png'}")

    # Per-character head glyphs from tools/character_skins.yaml. Skipped
    # silently if PyYAML isn't installed or the yaml file is empty.
    produced_heads = build_character_heads(TEXTURES_OUT / "heads")

    # Synthesize middle connector by tiling a 1-pixel-wide plate-body
    # column from under_left.png across the hotbar gap. Column 95 is pure
    # body (between labels and the right-edge V-notch), so tiling it gives
    # a smooth banner with no repeating decorative artifacts.
    ul_src = Image.open(src / "under" / "left" / "under_left1.png").convert("RGBA")
    strip = ul_src.crop((95, 0, 96, ul_src.height))  # 1px wide
    connector_w = 32
    connector = Image.new("RGBA", (connector_w, ul_src.height), (0, 0, 0, 0))
    for x in range(connector_w):
        connector.paste(strip, (x, 0), strip)
    connector.putpixel((connector_w - 1, 0), (0, 0, 0, 1))
    connector.save(TEXTURES_OUT / "under_middle.png")

    # Font JSON — width_map currently unused but kept threaded so it's easy
    # to introduce per-glyph aspect tweaks later without rewriting the call.
    emit_font(width_map={}, character_head_ids=produced_heads)

    print(f"wrote {TEXTURES_OUT}")
    print(f"wrote {FONT_OUT}")


if __name__ == "__main__":
    main()
