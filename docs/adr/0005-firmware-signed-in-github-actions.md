# Firmware is built and signed by a GitHub Action

A version tag on `main` (`fw-v…` or `hub-v…`) starts `.github/workflows/release.yml`, which builds the release with no secrets in it, signs it and publishes it on the public `DrakeAnglin/tilt-site` repo, where the app finds it. The firmware signing key is a GitHub Actions secret (`FIRMWARE_SIGNING_KEY`) in a `release` environment that only release tags may use; the token that publishes (`TILT_SITE_TOKEN`) can write to tilt-site and nothing else.

We rejected keeping signing on the Mac and having the Action only build and check. It keeps the key off GitHub, but every release would again need the Mac, a hand step and a hand upload, which is what this change removes.

Consequences: anyone who can push a release tag to this private repo, or change the workflow on `main`, can sign firmware that every controller accepts. The key also stays on the Mac (`~/.tilt/firmware-signing-key.pem`) for `tools/release_firmware.py --sign` on the bench. If the key leaks, new controllers need a new `fwkey.h`, and controllers in homes need one last update signed with the old key that carries the new one.
