#!/bin/sh
# The release build, run by .github/workflows/release.yml inside the esp-matter image (esp-matter 1.5, ESP-IDF 5.5.5).
#   KIND=controller|hub|both  CHANNEL=stable|beta  notes.txt: the release notes
#   FIRMWARE_SIGNING_KEY: the key's PEM text; empty: a throwaway key (dry run, nothing is published)
# Leaves upload/: firmware.json and every file it names.
set -e
cd "$(dirname "$0")/.."
git config --global --add safe.directory "$PWD"
pip3 install --break-system-packages --quiet detools
mkdir -p ~/esp ~/.tilt
ln -sfn "$IDF_PATH" ~/esp/esp-idf                  # build.sh looks in ~/esp, as on the Mac
ln -sfn "$ESP_MATTER_PATH" ~/esp/esp-matter
tools/firmware_tests.sh
umask 077
if [ -n "$FIRMWARE_SIGNING_KEY" ]; then
  printf '%s\n' "$FIRMWARE_SIGNING_KEY" > ~/.tilt/firmware-signing-key.pem
else
  echo "dry run: throwaway signing key"
  openssl ecparam -name prime256v1 -genkey -noout -out ~/.tilt/firmware-signing-key.pem
fi
umask 022
python3 tools/release_ci.py fetch
if [ "$KIND" != hub ]; then
  python3 tools/release_firmware.py "${CHANNEL:-beta}" --notes "$(cat notes.txt)" || { tail -50 firmware/blinds_matter/build-release.log; exit 1; }
fi
if [ "$KIND" != controller ]; then
  python3 tools/release_firmware.py --hub --notes "$(cat notes.txt)" || { tail -50 firmware/tilt_hub/build-release.log; exit 1; }
fi
# Every new file ends in its signature: check it with the public half of the key, as the controller does.
openssl ec -in ~/.tilt/firmware-signing-key.pem -pubout -out pub.pem 2>/dev/null
rm -f ~/.tilt/firmware-signing-key.pem
python3 tools/release_ci.py verify pub.pem
mkdir -p upload
python3 tools/release_ci.py files | xargs -I{} cp {} upload/
cp notes.txt upload/notes.txt
cat firmware/releases/firmware.json
ls -l upload
