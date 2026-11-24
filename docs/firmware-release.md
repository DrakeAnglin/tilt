# Firmware release

A release is a version tag on `main`. The GitHub Action (`.github/workflows/release.yml`) builds it with no secrets in it, signs it, and publishes it on the public `DrakeAnglin/tilt-site` repo. The app reads `releases/latest/download/firmware.json` there and offers the update on the controller's page (or the hub page). ADR 0005 says why it is signed on GitHub.

## Cut a release

1. Raise the version in a pull request and merge it: `FW_VERSION` in `firmware/blinds_matter/main/web.h` (controller), or `PROJECT_VER` in `firmware/tilt_hub/CMakeLists.txt` (hub).
2. Tag that commit on `main`. The tag's message is the release notes the app shows.
   - Controller, stable: `git tag -a fw-v2.3.0 -m "What changed"`
   - Controller, beta (only developer builds of the app see it): `git tag -a fw-v2.3.0-beta1 -m "..."`
   - Tilt Hub: `git tag -a hub-v0.3.4 -m "..."`
3. `git push origin <tag>`. Watch it under Actions, "Firmware release" (about 35 minutes).

The Action stops, and publishes nothing, when the tag is not on `main`, the tag and the code's version differ, a logic test fails, the build fails, a `secrets.h` value is in the image, or a signature does not check out.

Each release on tilt-site carries the new `firmware.json` and every file it names (stable, beta, hub, and the patches from the last three controller images), because the app only reads the newest release.

## Roll back

Controllers never go back to an older version by themselves: the app only offers a newer one.

- **Stop a bad release from spreading:** delete it on tilt-site (`gh release delete <tag> --repo DrakeAnglin/tilt-site`). The one before becomes the newest, and its `firmware.json` lists the old version again. Controllers that already took the bad one keep it.
- **Fix controllers that took it:** release a higher version with the fix (for example the old code as `2.3.1`).

## Set up once (owner)

1. In `DrakeAnglin/tilt`, Settings, Environments: make `release`. Under deployment branches and tags choose "Selected", and add the tag rules `fw-v*` and `hub-v*`.
2. In that environment, add two secrets:
   - `FIRMWARE_SIGNING_KEY`: the whole text of `~/.tilt/firmware-signing-key.pem` (`pbcopy < ~/.tilt/firmware-signing-key.pem`).
   - `TILT_SITE_TOKEN`: a fine-grained personal access token for `DrakeAnglin/tilt-site` only, with Contents read and write.
3. Optional: Settings, Rules, a tag ruleset on `fw-v*` and `hub-v*` so only you can make them.

## By hand, on the Mac

`tools/release_firmware.py` still works on its own (the Action runs it): it writes `firmware/releases/`. Then `gh release create <tag> --repo DrakeAnglin/tilt-site` with `firmware.json` and every file it names. Prefer the tag.
