#!/usr/bin/env python3
"""Refresh dist/foxmobmashers-resourcepack.zip without the HUD source pack.

The HUD textures/font are generated from a non-redistributable source and are
not in git — they exist only inside the previously released zip. This script
copies those entries forward from the current zip and (re)adds every tracked
pack file (pack.mcmeta + assets/ as committed), then rewrites the .sha1 sidecar.

The character head glyphs are the exception (#23): they are baked from
tools/character_skins.yaml, not from the licensed source, so they are re-baked
here instead of carried forward, and the head providers inside the carried
default.json are swapped for the current CHARACTER_HEAD_CODEPOINTS set. A skin
or codepoint added in git therefore reaches the zip without the source pack.
"""
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "foxmobmashers-resourcepack.zip"
sys.path.insert(0, str(ROOT / "tools"))
import build_hud_pack as hud  # noqa: E402

FONT = "assets/minecraft/font/default.json"
HEADS_DIR = "assets/foxmobmashers/textures/hud/heads/"

# Cached AND untracked-but-not-ignored, so a freshly generated file that has not
# been `git add`ed yet still ships (the first build of #11 missed every new item
# override for exactly that reason). Ignored files (the HUD art) are excluded
# here and carried forward from the previous zip below.
tracked = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard",
                          "pack.mcmeta", "assets"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
tracked_set = set(tracked)


def swap_head_providers(font_bytes, head_ids):
    """The carried default.json with its head providers replaced by the current
    set, in the slot the old ones occupied (right after the skull glyph when the
    old font had none). Serialised exactly as build_hud_pack.emit_font does."""
    providers = json.loads(font_bytes)["providers"]
    is_head = lambda p: p.get("file", "").startswith(hud.HEAD_FILE_PREFIX)
    slot = next((i for i, p in enumerate(providers) if is_head(p)), None)
    if slot is None:
        slot = 1 + next(i for i, p in enumerate(providers) if p.get("file") == "foxmobmashers:hud/skull.png")
    kept = [p for p in providers[:slot] if not is_head(p)]
    rest = [p for p in providers[slot:] if not is_head(p)]
    providers = kept + hud.head_providers(head_ids) + rest
    return (json.dumps({"providers": providers}, indent=2) + "\n").encode()


with tempfile.TemporaryDirectory() as tmp:
    heads = hud.build_character_heads(Path(tmp))
    hud.require_all_heads(heads)
    head_png = {f"{HEADS_DIR}{cid}.png": (Path(tmp) / f"{cid}.png").read_bytes() for cid in sorted(heads)}

buf = io.BytesIO()
with zipfile.ZipFile(DIST) as old, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as new:
    kept = 0
    head_template = None
    for info in old.infolist():
        if info.filename in tracked_set or info.filename.endswith("/"):
            continue
        if info.filename.startswith(HEADS_DIR):
            head_template = head_template or info
            continue  # re-baked below
        data = old.read(info)
        if info.filename == FONT:
            data = swap_head_providers(data, heads)
        new.writestr(info, data)
        kept += 1
    # Same entry metadata as the carried heads (stored, same timestamp), so an
    # unchanged head is an unchanged entry.
    for name, data in head_png.items():
        info = zipfile.ZipInfo(name, head_template.date_time if head_template else (1980, 1, 1, 0, 0, 0))
        info.compress_type = head_template.compress_type if head_template else zipfile.ZIP_STORED
        new.writestr(info, data)
    for rel in sorted(tracked):
        new.write(ROOT / rel, rel)
DIST.write_bytes(buf.getvalue())
# Every non-ignored pack file on disk must be in the zip — fail loudly otherwise.
with zipfile.ZipFile(DIST) as check:
    names = set(check.namelist())
    missing = [rel for rel in tracked if rel not in names]
    assert not missing, f"dist zip is missing {missing}"
    assert "pack.mcmeta" in names
    # …and every head codepoint the plugin names must have its glyph (#23).
    font = {p["chars"][0]: p["file"] for p in json.loads(check.read(FONT))["providers"] if p.get("chars")}
    for cid, cp in hud.CHARACTER_HEAD_CODEPOINTS.items():
        assert font.get(chr(cp)) == f"{hud.HEAD_FILE_PREFIX}{cid}.png", f"font has no head glyph U+{cp:04X} for {cid}"
        assert f"{HEADS_DIR}{cid}.png" in names, f"dist zip is missing {HEADS_DIR}{cid}.png"
sha1 = hashlib.sha1(buf.getvalue()).hexdigest()
(DIST.with_suffix(".zip.sha1")).write_text(sha1 + "\n")
print(f"kept {kept} generated entries, baked {len(head_png)} character heads, "
      f"added {len(tracked)} tracked files, sha1 {sha1}")
