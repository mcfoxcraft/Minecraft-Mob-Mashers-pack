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
  url: "https://github.com/mcfoxcraft/Minecraft-Mob-Mashers-pack/releases/download/<tag>/foxmobmashers-resourcepack.zip"
  sha1: "<sha1 from release notes>"
  required: false
music:
  run_track: "foxmobmashers:music.run"
  run_track_length_seconds: 120
  volume: 0.6
```

Clients cache packs by hash — bump both `url` and `sha1` after each release.

## Releasing

Push a `v*` tag. GitHub Actions builds the zip, computes SHA-1, and uploads both to a release:

```
git tag v1.0.0
git push origin v1.0.0
```

Release notes include the SHA-1 and a copy-paste-ready `config.yml` snippet.

## Credits

See [CREDITS.md](CREDITS.md).
