# Firmware is built and signed by a GitHub Action

A version tag on `main` (`fw-v…` or `hub-v…`) starts `.github/workflows/release.yml`, which builds the release with no secrets in it, signs it and publishes it as a release of this repo, where the app finds it. The firmware signing key is a GitHub Actions secret (`FIRMWARE_SIGNING_KEY`) in a `release` environment that only release tags may use. (Until 2026-11-25 releases went to a separate public `tilt-site` repo with its own token, because this repo was private. Once this repo went public they moved here and the token went away.)

We rejected keeping signing on the Mac and having the Action only build and check. It keeps the key off GitHub, but every release would again need the Mac, a hand step and a hand upload, which is what this change removes.

Consequences: anyone who can push a release tag to this repo (a tag ruleset limits that to the owner), or change the workflow on `main`, can sign firmware that every controller accepts. The key also stays on the Mac (`~/.tilt/firmware-signing-key.pem`) for `tools/release_firmware.py --sign` on the bench. If the key leaks, new controllers need a new `fwkey.h`, and controllers in homes need one last update signed with the old key that carries the new one.
