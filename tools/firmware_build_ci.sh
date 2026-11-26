#!/bin/sh
# CI's firmware builds, run by .github/workflows/ci.yml inside the esp-matter image (the same image as release.yml).
#   tools/firmware_build_ci.sh hub          the Tilt Hub, release kind: the command tools/release_firmware.py --hub uses
#   tools/firmware_build_ci.sh controller   the controller, release kind: the command tools/release_firmware.py uses
# No signing, no key, no upload: it only proves the firmware builds and fits. Run it by hand in the image the same way.
set -e
cd "$(dirname "$0")/.."
case "$1" in
  hub) DIR=firmware/tilt_hub NAME="Tilt Hub" ;;
  controller) DIR=firmware/blinds_matter NAME="controller" ;;
  *) echo "usage: tools/firmware_build_ci.sh hub|controller" >&2; exit 2 ;;
esac
git config --global --add safe.directory "$PWD"
mkdir -p ~/esp
ln -sfn "$IDF_PATH" ~/esp/esp-idf                  # build.sh looks in ~/esp, as on the Mac
ln -sfn "$ESP_MATTER_PATH" ~/esp/esp-matter
LOG="$DIR/build-release.log"
build() {
  case "$1" in
    hub) BUILD_DIR=build-release "$DIR/build.sh" -B build-release -DTILT_RELEASE=1 build ;;
    controller) BUILD_DIR=build-release SDKCONFIG_FILE=sdkconfig.release "$DIR/build.sh" -DTILT_RELEASE=1 build ;;
  esac
}
if ! build "$1" > "$LOG" 2>&1; then
  echo "::error::the $NAME build failed. Compiler errors:"
  grep -E 'error:|Error:|FAILED:|overflow|does not fit' "$LOG" | head -40 || true
  echo "--- last lines of $LOG ---"
  tail -40 "$LOG"
  exit 1
fi
tail -5 "$LOG"
echo "$NAME build: ok"
