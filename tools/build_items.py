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
# A small feather bolt flying quill-last (the bird bursts, plugin #911): W vane,
# d vane shadow, s shaft / quill, o outline. Column 7 is the shaft, so
# split_recolor's column-8 cut gives Vandalier a white left and black right vane.
FEATHER_ROWS = [
    "................",
    "................",
    "................",
    ".......o........",
    "......oWo.......",
    ".....oWsWo......",
    ".....oWsWo......",
    "....oWWsWdo.....",
    "....oWWsWdo.....",
    "....oWdsddo.....",
    ".....odsdo......",
    "......oso.......",
    ".......s........",
    ".......s........",
    "................",
    "................",
]
BLACK_FEATHER = {"W": "k", "d": "D"}

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
    # Knife: a flat face-up item display flying tip-first (texture "up" = travel),
    # not a sword in a vex's hand any more — the 62-pixel diagonal blade of the
    # first version was a 2 px sliver from the run camera (eyes harness, #20).
    # Bold vertical blade with a black outline, 6 px wide.
    "knife": ("iron_sword", "item/generated", {
        "s": (0xC8, 0xCC, 0xD0), "S": (0xF4, 0xF6, 0xF8), "d": (0x7A, 0x80, 0x88),
        "h": (0x3A, 0x2A, 0x1A), "g": (0xB8, 0x90, 0x2A), "o": (0x1A, 0x1A, 0x1A),
    }, [
        ".......oo.......",
        "......oSSo......",
        "......oSso......",
        ".....oSssdo.....",
        ".....oSssdo.....",
        ".....oSssdo.....",
        ".....oSssdo.....",
        ".....oSssdo.....",
        ".....oSssdo.....",
        ".....oSssdo.....",
        "....ogggggo.....",
        "....ogggggo.....",
        ".....ohhho......",
        ".....ohhho......",
        ".....ohhho......",
        "......ooo.......",
    ]),
    # ── #26 batch 3 (plugin #894 A + B): bracelet bolts, gun bullets, bombs ──
    # All flat sprites flying point-first (texture up = travel). Drawn small
    # inside the 16 px so a 1.8-scale display (0.9 block) reads at the size of
    # the snowball / magma cube they replace.
    # Bracelet bolt: a gold energy teardrop with a white core and a short tail.
    "bracelet": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xF0), "y": (0xFF, 0xE0, 0x50), "g": (0xE8, 0xB8, 0x30),
        "d": (0xA8, 0x7A, 0x10), "o": (0x3A, 0x2A, 0x05),
    }, [
        "................",
        ".......oo.......",
        "......oWWo......",
        ".....oWWWyo.....",
        ".....oWWyyo.....",
        ".....oWyyyo.....",
        ".....oyyygo.....",
        ".....oyyggo.....",
        ".....oyggdo.....",
        "......oggo......",
        "......odgo......",
        ".......oo.......",
        ".......dd.......",
        "........d.......",
        "................",
        "................",
    ]),
    # Bi-Bracelet: the same bolt run hotter — orange edges, a forked tail.
    "bi_bracelet": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xF0), "y": (0xFF, 0xE0, 0x50), "r": (0xFF, 0x9A, 0x2A),
        "d": (0xB8, 0x50, 0x10), "o": (0x3A, 0x1A, 0x05),
    }, [
        "................",
        ".......oo.......",
        "......oWWo......",
        ".....oWWWyo.....",
        ".....oWWyyo.....",
        ".....oWyyro.....",
        ".....oyyrro.....",
        ".....oyrrro.....",
        ".....oyrrdo.....",
        "......orro......",
        "......odro......",
        ".....od.odo.....",
        ".....d....d.....",
        "................",
        "................",
        "................",
    ]),
    # Tri-Bracelet: bigger, white-hot, three tails.
    "tri_bracelet": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xF8), "c": (0xFF, 0xF4, 0xC0), "y": (0xFF, 0xE0, 0x50),
        "g": (0xE8, 0xB8, 0x30), "d": (0xA8, 0x7A, 0x10), "o": (0x3A, 0x2A, 0x05),
    }, [
        ".......oo.......",
        "......oWWo......",
        ".....oWWWWo.....",
        "....oWWWWcyo....",
        "....oWWWccyo....",
        "....oWWcccyo....",
        "....oWccyyyo....",
        "....occyyygo....",
        "....ocyyyggo....",
        ".....oyyggo.....",
        ".....oygggo.....",
        "....od.ogo.do...",
        "....d..odo..d...",
        ".......d........",
        "................",
        "................",
    ]),
    # Phiera Der Tuphello: a red bullet capsule with a bright nose.
    "phiera_der_tuphello": ("iron_nugget", "item/generated", {
        "W": (0xFF, 0xE8, 0xE8), "r": (0xE0, 0x30, 0x30), "R": (0x8A, 0x10, 0x10), "o": (0x2A, 0x08, 0x08),
    }, [
        "................",
        "................",
        "......oooo......",
        ".....oWWrro.....",
        ".....oWrrro.....",
        ".....orrrro.....",
        ".....orrrro.....",
        ".....orrrRo.....",
        ".....orrRRo.....",
        ".....oRRRRo.....",
        "......oooo......",
        "................",
        "................",
        "................",
        "................",
        "................",
    ]),
    # Eight The Sparrow: the same bullet in blue.
    "eight_the_sparrow": ("iron_nugget", "item/generated", {
        "W": (0xE0, 0xF0, 0xFF), "r": (0x40, 0x90, 0xFF), "R": (0x18, 0x40, 0xA8), "o": (0x08, 0x14, 0x30),
    }, [
        "................",
        "................",
        "......oooo......",
        ".....oWWrro.....",
        ".....oWrrro.....",
        ".....orrrro.....",
        ".....orrrro.....",
        ".....orrrRo.....",
        ".....orrRRo.....",
        ".....oRRRRo.....",
        "......oooo......",
        "................",
        "................",
        "................",
        "................",
        "................",
    ]),
    # Phieraggi: the fused gun — a red / blue bullet with a white seam.
    "phieraggi": ("iron_nugget", "item/generated", {
        "W": (0xFF, 0xFF, 0xFF), "r": (0xE0, 0x30, 0x30), "R": (0x8A, 0x10, 0x10),
        "b": (0x40, 0x90, 0xFF), "B": (0x18, 0x40, 0xA8), "o": (0x1A, 0x0A, 0x1A),
    }, [
        "................",
        "................",
        "......oooo......",
        ".....orWWbo.....",
        ".....orWWbo.....",
        ".....orrbbo.....",
        ".....orrbbo.....",
        ".....orrbbo.....",
        ".....oRrbBo.....",
        ".....oRRBBo.....",
        "......oooo......",
        "................",
        "................",
        "................",
        "................",
        "................",
    ]),
    # Cherry Bomb: a red cherry, lit fuse sparking at the top.
    "cherry_bomb": ("sweet_berries", "item/generated", {
        "r": (0xE0, 0x20, 0x30), "R": (0x90, 0x0C, 0x1C), "W": (0xFF, 0xC8, 0xC8),
        "g": (0x3C, 0xA0, 0x30), "G": (0x1E, 0x5C, 0x18), "y": (0xFF, 0xF0, 0x60),
        "Y": (0xFF, 0xA0, 0x20), "o": (0x2A, 0x06, 0x0A),
    }, [
        "........y.......",
        ".......yYy......",
        "........Y.......",
        ".......oGo......",
        "......oGgo......",
        "......ogo.......",
        ".....ooooo......",
        "....orWWrro.....",
        "...orWrrrrro....",
        "...orrrrrrro....",
        "...orrrrrRro....",
        "...orrrrRRro....",
        "....orrRRRo.....",
        ".....oRRRo......",
        "......ooo.......",
        "................",
    ]),
    # Yatta Daikarin: a white daikon radish, leaves up, tapering down.
    "yatta_daikarin": ("beetroot", "item/generated", {
        "c": (0xF4, 0xF0, 0xE0), "s": (0xC8, 0xC0, 0xA8), "W": (0xFF, 0xFF, 0xFF),
        "g": (0x3C, 0xA0, 0x30), "G": (0x1E, 0x5C, 0x18), "o": (0x30, 0x30, 0x28),
    }, [
        ".....oGo.oGo....",
        "....oGggogGo....",
        ".....oGgggGo....",
        "......ogggo.....",
        ".....oosssoo....",
        "....oWccccsso...",
        "....oWcccccso...",
        "....oWcccccso...",
        "....occccccso...",
        ".....occccso....",
        ".....occccso....",
        "......occso.....",
        "......occso.....",
        ".......oso......",
        ".......oo.......",
        "................",
    ]),
    # ── #26 batch 3 C (plugin #894 C): the pinion strikes ─────────────────────
    # Shadow Pinion: a dark violet spike flying point-first, a pale edge glow.
    "shadow_pinion": ("echo_shard", "item/generated", {
        "W": (0xD8, 0xC8, 0xFF), "v": (0x8A, 0x5A, 0xD0), "V": (0x4A, 0x28, 0x80),
        "k": (0x1E, 0x10, 0x38), "o": (0x0C, 0x06, 0x18),
    }, [
        ".......oo.......",
        "......oWWo......",
        "......oWvo......",
        ".....oWvvVo.....",
        ".....oWvvVo.....",
        ".....ovvVVo.....",
        ".....ovvVko.....",
        "....ovvVVkko....",
        "....ovVVkkko....",
        "....oVVkkkko....",
        ".....oVkkko.....",
        ".....oVkkko.....",
        "......okko......",
        "......okko......",
        ".......oo.......",
        "................",
    ]),
    # Valkyrie Turner: a golden spear with a white-hot tip and a short haft.
    "valkyrie_turner": ("blaze_rod", "item/generated", {
        "W": (0xFF, 0xFF, 0xF0), "y": (0xFF, 0xE8, 0x80), "g": (0xE8, 0xB8, 0x30),
        "d": (0xA8, 0x7A, 0x10), "h": (0x6A, 0x48, 0x18), "o": (0x3A, 0x2A, 0x05),
    }, [
        ".......oo.......",
        "......oWWo......",
        "......oWWo......",
        ".....oWWyyo.....",
        ".....oWyygo.....",
        ".....oyyggo.....",
        "....oyyggdo.....",
        "....oygggdo.....",
        ".....oggdo......",
        "....oogddoo.....",
        "....odhhhdo.....",
        ".....ohhho......",
        "......ohho......",
        "......ohho......",
        "......odo.......",
        ".......o........",
    ]),
    # ── plugin #911 follow-ups of #894: three flown visuals #894 missed ───────
    # Carozza!'s "Take Us Away" train, seen from above like every flown sprite
    # (texture up = travel): a black steam locomotive (headlamp, red buffer
    # beam, funnel blowing a white puff, brass band, red cab) pulling a blue
    # carriage. Top-down, so it reads the same whichever way a stage camera
    # sees it cross; nothing like Carréllo's grey side-view cart. The plugin
    # flies it at twice the usual sprite size, the width of its sweep.
    "carozza_train": ("minecart", "item/generated", {
        "y": (0xFF, 0xF0, 0x80), "R": (0xE0, 0x38, 0x30), "r": (0x98, 0x18, 0x1C),
        "k": (0x2C, 0x2A, 0x32), "K": (0x50, 0x4E, 0x5C), "L": (0x7C, 0x7A, 0x8A),
        "s": (0x0C, 0x0C, 0x10), "b": (0xE0, 0xB0, 0x40), "W": (0xFF, 0xFF, 0xFF),
        "w": (0xC8, 0xCC, 0xD6), "M": (0x38, 0x6C, 0xC8), "m": (0x24, 0x44, 0x88),
        "g": (0xFF, 0xE8, 0x90), "c": (0x18, 0x16, 0x1A), "o": (0x10, 0x0C, 0x10),
    }, [
        "......oyyo......",
        "....oRRRRRRo....",
        "....okKLKkko....",
        "....okossoko.oo.",
        "....okossokoWWWo",
        "....okKLKkoWWWwo",
        "....obbbbbbowwo.",
        "....okKLKkko.oo.",
        "...orrrrrrrro...",
        "...orRRRRRRro...",
        "....oooccooo....",
        "...oMMMMMMMMo...",
        "...oMgMMMMgMo...",
        "...oMMMMMMMMo...",
        "...omgmmmmgmo...",
        "...oooooooooo...",
    ]),
    # Peachone / Ebony Wings / Vandalier burst shots: a small feather bolt,
    # drawn tiny because a flock fires dozens (they replace a thrown snowball).
    # White and gold for Peachone, black with a red quill for Ebony Wings, and
    # Vandalier's split like its bird: white left vane, black right vane.
    "peachone_burst": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xF4), "d": (0xE8, 0xB8, 0xB0), "s": (0xF0, 0xC0, 0x40),
        "o": (0x3A, 0x2A, 0x10),
    }, FEATHER_ROWS),
    "ebony_wings_burst": ("snowball", "item/generated", {
        "k": (0x3A, 0x36, 0x44), "D": (0x1A, 0x18, 0x20), "s": (0xE0, 0x30, 0x30),
        "o": (0xB8, 0x90, 0xD8),
    }, recolor(FEATHER_ROWS, BLACK_FEATHER)),
    "vandalier_burst": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xF4), "d": (0xE8, 0xB8, 0xB0),
        "k": (0x3A, 0x36, 0x44), "D": (0x1A, 0x18, 0x20),
        "s": (0xF0, 0x70, 0x40), "o": (0x3A, 0x2A, 0x2A),
    }, split_recolor(FEATHER_ROWS, BLACK_FEATHER)),
    # Twilight Requiem's retaliation shot: a dusky violet orb, lavender core,
    # trailing a sunset-pink wisp — an arcana's shot, not the Fire Wand's
    # fireball it shares a carrier with (the small fireball renders a fire charge).
    "twilight_retaliation": ("fire_charge", "item/generated", {
        "W": (0xF4, 0xEC, 0xFF), "c": (0xC8, 0xA8, 0xF8), "v": (0x8A, 0x5C, 0xD8),
        "V": (0x52, 0x2E, 0x96), "p": (0xF0, 0x80, 0xA8), "P": (0xC0, 0x50, 0x88),
        "o": (0x1C, 0x0C, 0x30),
    }, [
        "................",
        "................",
        "......oooo......",
        ".....oWWcvo.....",
        "....oWWccvVo....",
        "....oWccvvVo....",
        "....ocvvvVVo....",
        "....opvvVVPo....",
        ".....opVVPo.....",
        ".....oppPPo.....",
        "......oppo......",
        "......oPPo......",
        ".......PP.......",
        ".......P........",
        "................",
        "................",
    ]),
    # ── #21: sprites for the vanilla-entity projectiles ──────────────────────
    # Magic Wand bolt: a blue-white teardrop flying point-first (up) with a
    # fading trail. Replaces the snowball (one white pixel from the camera).
    "magic_wand": ("snowball", "item/generated", {
        "W": (0xFF, 0xFF, 0xFF), "c": (0xB4, 0xE6, 0xFF), "b": (0x5A, 0xA8, 0xFF),
        "B": (0x2A, 0x62, 0xD6), "t": (0x8C, 0xC4, 0xFF), "o": (0x10, 0x24, 0x5A),
    }, [
        ".......oo.......",
        "......oWWo......",
        ".....oWccWo.....",
        ".....oWccbo.....",
        "....oWcccbBo....",
        "....oWccbbBo....",
        "....oWcbbbBo....",
        "....ocbbbBBo....",
        ".....obbBBo.....",
        ".....oBBBBo.....",
        "......oBBo......",
        "......otto......",
        ".......tt.......",
        ".......tt.......",
        "........t.......",
        "................",
    ]),
    # Fire Wand fireball: orange ball with a yellow-white core and flame tips
    # trailing behind (down). Replaces the small fireball (a 3 px dot).
    "fire_wand": ("fire_charge", "item/generated", {
        "W": (0xFF, 0xF8, 0xC8), "y": (0xFF, 0xE0, 0x50), "r": (0xFF, 0x8C, 0x1E),
        "R": (0xE0, 0x3C, 0x10), "d": (0x8A, 0x1E, 0x08), "o": (0x2A, 0x0A, 0x04),
    }, [
        "......oooo......",
        ".....orrrro.....",
        "....orryyrro....",
        "...orryWWyrro...",
        "...oryWWWWyro...",
        "...oryWWWWyro...",
        "...orryWWyrro...",
        "...oRrryyrrRo...",
        "....oRrrrrRo....",
        "....odRrrRdo....",
        ".....odRRdo.....",
        "....o.oRRo.o....",
        "...oRo.oo.oRo...",
        "...oRo....oRo...",
        "....o......o....",
        "................",
    ]),
    # Runetracer: a teal crystal bolt with a glowing rune, flying point-first.
    # Replaces the trident (a 2 px line seen edge-on from above).
    "runetracer": ("amethyst_shard", "item/generated", {
        "W": (0xF0, 0xFF, 0xFA), "c": (0x8C, 0xF0, 0xE0), "t": (0x2E, 0xC8, 0xB0),
        "T": (0x14, 0x8A, 0x7A), "g": (0xC8, 0xFF, 0x64), "o": (0x06, 0x30, 0x2C),
    }, [
        ".......oo.......",
        "......oWWo......",
        "......ocWo......",
        ".....occtTo.....",
        ".....octtTo.....",
        "....ocggttTo....",
        "....ocgWgtTo....",
        "....octggtTo....",
        "....octtttTo....",
        ".....ottTTo.....",
        ".....ottTTo.....",
        "......oTTo......",
        "......oTTo......",
        ".......oo.......",
        "................",
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
    # Every model referenced by one of OUR item definitions must exist, with its
    # texture(s). Other overrides (build_decals.py's paper.json) validate themselves.
    for item in {v[0] for v in SPRITES.values()}:
        item_def = ROOT / f"assets/minecraft/items/{item}.json"
        model = json.loads(item_def.read_text())["model"]
        for case in model["cases"]:
            ns, name = case["model"]["model"].split(":")
            model_path = ROOT / f"assets/{ns}/models/{name}.json"
            assert model_path.exists(), f"{item_def.name}: missing model {model_path}"
            for tex in json.loads(model_path.read_text())["textures"].values():
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
