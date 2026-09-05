#!/usr/bin/env python3
"""Ground decals for VFX steps 2 and 5 (issues #6, #9): flat textured quads the
plugin shows as item displays under auras, zones, flashes and enemy telegraphs.

For every kind in DECALS this writes
  assets/foxmobmashers/textures/decal/<kind>.png   64x64 RGBA, drawn procedurally
  assets/foxmobmashers/models/decal/<kind>.json    one zero-thickness plane at model y=8
and one override
  assets/minecraft/items/paper.json                select on custom_model_data
                                                   "foxmobmashers:decal/<kind>", vanilla fallback

The plugin (effects/DecalKind + DecalManager) flies a `paper` tagged with that
string, scaled to 2 x radius, full-bright, at ground + 0.05. Players without
the pack never see these entities at all (viewer partition), so the fallback
only matters for a stale pack.

    python3 tools/build_decals.py          # (re)generate
    python3 tools/build_decals.py --check  # verify tree + dist zip
"""
import json
import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS = "foxmobmashers"
SIZE = 64


# ── drawing primitives (all coordinates normalised: centre 0,0, edge radius 1) ──

def ring(fill, rim, rim_w=0.07, rims=(1.0,), wobble=0.0, wobble_n=5, dashes=0, rays=0, lines=(), spots=0):
    """A disc `fill` (r,g,b,a) with one or more rim circles `rim` of width rim_w at
    the radii in `rims`, optionally: a wobbly edge (puddles), dashed outer rim,
    `rays` spokes, extra line segments, or `spots` dots on a mid ring."""
    def px(u, v):
        ang = math.atan2(v, u)
        r = math.hypot(u, v)
        edge = 1.0 - (wobble * (0.5 + 0.5 * math.sin(ang * wobble_n + 0.7)) if wobble else 0.0)
        rr = r / edge
        a = 0.0
        col = fill
        if rr <= 1.0:
            a = fill[3] / 255.0
            # soft outer falloff
            if rr > 0.92:
                a *= max(0.0, 1.0 - (rr - 0.92) / 0.08) if not rim else 1.0
        for k in rims:
            d = abs(rr - k * 1.0)
            if d < rim_w:
                if dashes and k == rims[-1]:
                    seg = (ang + math.pi) / (2 * math.pi) * dashes
                    if seg - math.floor(seg) > 0.6:
                        continue
                w = 1.0 - d / rim_w
                a2 = rim[3] / 255.0 * min(1.0, w * 2.5)
                if a2 > a:
                    a, col = a2, rim
        if rays:
            spoke = (ang + math.pi) / (2 * math.pi) * rays
            frac = spoke - math.floor(spoke)
            if min(frac, 1 - frac) < 0.035 and 0.15 < rr < 0.95:
                a, col = max(a, rim[3] / 255.0 * 0.8), rim
        for (x1, y1, x2, y2) in lines:
            dx, dy = x2 - x1, y2 - y1
            t = max(0.0, min(1.0, ((u - x1) * dx + (v - y1) * dy) / (dx * dx + dy * dy)))
            d = math.hypot(u - (x1 + t * dx), v - (y1 + t * dy))
            if d < 0.04:
                a, col = max(a, rim[3] / 255.0 * min(1.0, (0.04 - d) / 0.015)), rim
        if spots:
            for i in range(spots):
                sa = 2 * math.pi * i / spots
                if math.hypot(u - 0.62 * math.cos(sa), v - 0.62 * math.sin(sa)) < 0.09:
                    a, col = max(a, rim[3] / 255.0), rim
        if rr > 1.0 + rim_w:
            a = 0.0
        return col[0], col[1], col[2], int(max(0.0, min(1.0, a)) * 255)
    return px


def star_lines(points=5, r=0.9):
    pts = [(r * math.cos(-math.pi / 2 + 2 * math.pi * i / points),
            r * math.sin(-math.pi / 2 + 2 * math.pi * i / points)) for i in range(points)]
    return [(pts[i][0], pts[i][1], pts[(i + 2) % points][0], pts[(i + 2) % points][1]) for i in range(points)]


DECALS = {
    # ── auras (step 2) ─────────────────────────────────────────────────────
    "garlic":            ring((170, 240, 150, 45),  (190, 255, 170, 205)),
    "soul_eater":        ring((120, 40, 160, 55),   (170, 70, 220, 215)),
    "vicious_hunger":    ring((255, 200, 60, 40),   (255, 215, 0, 225), dashes=12),
    "laurel":            ring((180, 255, 180, 55),  (120, 230, 120, 220), rims=(0.82, 1.0), rim_w=0.05),
    "crimson_shroud":    ring((220, 20, 60, 55),    (255, 60, 90, 225)),
    "infinite_corridor": ring((100, 180, 255, 35),  (170, 220, 255, 220), rims=(0.45, 0.72, 1.0), rim_w=0.05),
    # ── zones (step 2) ─────────────────────────────────────────────────────
    "water":             ring((64, 164, 223, 120),  (140, 210, 245, 200), wobble=0.12, wobble_n=5),
    "fire":              ring((255, 120, 20, 115),  (255, 225, 90, 210), wobble=0.18, wobble_n=7),
    "petal":             ring((255, 150, 190, 85),  (255, 205, 225, 210), spots=6),
    "shadow":            ring((30, 20, 50, 150),    (90, 60, 140, 205), wobble=0.10, wobble_n=6),
    "holy":              ring((255, 240, 180, 95),  (255, 215, 90, 225), rays=8),
    "arcane":            ring((60, 220, 255, 65),   (150, 240, 255, 225), lines=[(-0.7, 0, 0.7, 0), (0, -0.7, 0, 0.7)]),
    # ── flashes (step 2) ───────────────────────────────────────────────────
    "pentagram":         ring((120, 0, 20, 30),     (230, 40, 50, 235), lines=star_lines(5, 0.88)),
    "moon":              ring((230, 230, 255, 85),  (255, 255, 255, 225), rims=(0.55, 1.0), rim_w=0.06),
    # ── enemies (step 5) ───────────────────────────────────────────────────
    "boss_telegraph":    ring((255, 40, 40, 70),    (255, 90, 90, 235), rims=(0.35, 1.0), rim_w=0.06,
                              lines=[(-0.95, 0, 0.95, 0), (0, -0.95, 0, 0.95)]),
    "mob_aura":          ring((60, 60, 90, 60),     (120, 120, 210, 205), dashes=8),
}


def png_bytes(fn):
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        for x in range(SIZE):
            u = (x + 0.5) / SIZE * 2 - 1
            v = (y + 0.5) / SIZE * 2 - 1
            r, g, b, a = fn(u, v)
            raw += bytes((r, g, b, a))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def dumps(obj):
    return json.dumps(obj, indent=2) + "\n"


def outputs():
    out = {}
    for kind, fn in DECALS.items():
        out[f"assets/{NS}/textures/decal/{kind}.png"] = png_bytes(fn)
        out[f"assets/{NS}/models/decal/{kind}.json"] = dumps({
            "textures": {"d": f"{NS}:decal/{kind}"},
            # One plane through the model's centre (y = 8) so the quad sits at the
            # entity's own y; FIXED item displays centre the 0..16 model cube on the
            # entity. shade:false keeps the decal at its own colour under any light.
            "elements": [{
                "from": [0, 8, 0], "to": [16, 8, 16], "shade": False,
                "faces": {
                    "up":   {"uv": [0, 0, 16, 16], "texture": "#d"},
                    "down": {"uv": [0, 0, 16, 16], "texture": "#d"},
                },
            }],
        }).encode()
    out[f"assets/minecraft/items/paper.json"] = dumps({
        "model": {
            "type": "minecraft:select",
            "property": "minecraft:custom_model_data",
            "index": 0,
            "cases": [
                {"when": f"{NS}:decal/{k}", "model": {"type": "minecraft:model", "model": f"{NS}:decal/{k}"}}
                for k in DECALS
            ],
            "fallback": {"type": "minecraft:model", "model": "minecraft:item/paper"},
        }
    }).encode()
    return out


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
            print("STALE (run tools/build_decals.py):\n  " + "\n  ".join(stale))
            return 1
        print(f"ok: {len(DECALS)} decals in sync")
    else:
        print(f"wrote {len(DECALS)} decals: {', '.join(DECALS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
