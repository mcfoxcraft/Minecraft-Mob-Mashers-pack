# FoxMobMashers Resource Pack

Client-side assets for the [FoxMobMashers](https://github.com/mcfoxcraft/Minecraft-Mob-Mashers) Paper plugin — music and (eventually) custom item textures.

## Layout

```
pack.mcmeta
assets/foxmobmashers/
  sounds.json          # sound events exposed to the plugin
  sounds/music/*.ogg   # track variants for music.run
```

The `music.run` sound event declares all tracks as variants. Minecraft picks one at random every time the plugin triggers the event, so rotation happens client-side with no plugin changes.

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
