#!/usr/bin/env python3
"""Refresh dist/foxmobmashers-resourcepack.zip without the HUD source pack.

The HUD textures/font are generated from a non-redistributable source and are
not in git — they exist only inside the previously released zip. This script
copies those entries forward from the current zip and (re)adds every tracked
pack file (pack.mcmeta + assets/ as committed), then rewrites the .sha1 sidecar.
"""
import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "foxmobmashers-resourcepack.zip"

tracked = subprocess.run(["git", "ls-files", "pack.mcmeta", "assets"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
tracked_set = set(tracked)

buf = io.BytesIO()
with zipfile.ZipFile(DIST) as old, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as new:
    kept = 0
    for info in old.infolist():
        if info.filename in tracked_set or info.filename.endswith("/"):
            continue
        new.writestr(info, old.read(info))
        kept += 1
    for rel in sorted(tracked):
        new.write(ROOT / rel, rel)
DIST.write_bytes(buf.getvalue())
sha1 = hashlib.sha1(buf.getvalue()).hexdigest()
(DIST.with_suffix(".zip.sha1")).write_text(sha1 + "\n")
print(f"kept {kept} generated entries, added {len(tracked)} tracked files, sha1 {sha1}")
