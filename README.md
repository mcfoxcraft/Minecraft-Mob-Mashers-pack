# FoxMobMashers Resource Pack

Client-side assets for the [FoxMobMashers](https://github.com/mcfoxcraft/Minecraft-Mob-Mashers) Paper plugin — music and (eventually) custom item textures.

## Layout

```
pack.mcmeta
assets/foxmobmashers/
  sounds.json                # sound events exposed to the plugin
  sounds/music/*.ogg         # track variants for music.run
  font/hud.json              # generated; gitignored
  textures/hud/...           # generated; gitignored
```

The `music.run` sound event declares all tracks as variants. Minecraft picks one at random every time the plugin triggers the event, so rotation happens client-side with no plugin changes.

## Animated HUD assets (generated)

The HUD plates, compass, and bars are derived from a 3rd-party BetterHud-format source pack whose textures are not redistributable in source form. The build pipeline:

1. Drop the source pack's `assets/` dir somewhere local (e.g. `tools/source/`).
2. Run `python3 tools/build_hud_pack.py tools/source/`. This stitches per-frame sequences into vertical strips with `.mcmeta` animations, slices the bars into 25 reveal frames each, and writes `assets/foxmobmashers/font/hud.json` mapping every glyph to a Private-Use-Area codepoint.
3. The generated `textures/hud/` and `font/hud.json` are gitignored — they live only in your local working tree and inside the release `dist/` zip.

Codepoint allocations are the contract between this pack and the plugin's `HudGlyphs.java`. Edit both sides if you remap them.

> ⚠ The current release flow uploads `dist/foxmobmashers-resourcepack.zip` to a public CDN. If your HUD source pack's license forbids public redistribution, switch the dist target to a private host before tagging.

## Using the pack

In your server's `plugins/FoxMobMashers/config.yml`:

```yaml
resource_pack:
  url: "https://cdn.jsdelivr.net/gh/mcfoxcraft/Minecraft-Mob-Mashers-pack@<tag>/dist/foxmobmashers-resourcepack.zip"
  sha1: "<sha1 from release notes>"
  required: false
music:
  run_track: "foxmobmashers:music.run"
  run_track_length_seconds: 120
  volume: 0.6
```

The recommended URL points at jsDelivr (free global CDN fronted by Cloudflare + Fastly) for fast downloads everywhere. Each tag is a pinned, immutable snapshot. Release notes also list a fallback GitHub Releases URL if jsDelivr ever misbehaves.

Clients cache packs by hash — bump both `url` and `sha1` after each release.

## Releasing

Rebuild the zip locally, commit it to `dist/`, then tag:

```
zip -r dist/foxmobmashers-resourcepack.zip pack.mcmeta assets
sha1sum dist/foxmobmashers-resourcepack.zip | cut -d' ' -f1 > dist/foxmobmashers-resourcepack.zip.sha1
git add dist/ && git commit -m "Rebuild pack zip"
git tag vX.Y.Z -m "…" && git push origin main vX.Y.Z
```

The committed `dist/` zip is what jsDelivr serves, so it must match the current `assets/` contents — CI fails the release otherwise. On tag push, GitHub Actions uploads the same zip to a release and writes copy-paste config to the release notes.

## Credits

See [CREDITS.md](CREDITS.md).
