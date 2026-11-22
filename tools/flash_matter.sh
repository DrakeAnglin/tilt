#!/bin/bash
# Build the Apple Home (Matter) firmware and send it to the controller over Wi-Fi.
#   tools/flash_matter.sh [address]      default address: $BLINDS_IP, else 192.168.50.135
# The build is signed with ~/.tilt/firmware-signing-key.pem (tools/release_firmware.py --sign), so it installs on a
# controller running a public release too. A firmware that cannot join Wi-Fi goes back by itself.
# PY: a python with 'cryptography' (default: the ESP-IDF one). NOKEEP=1: leave the new firmware on trial.
set -eo pipefail
cd "$(dirname "$0")/../firmware/blinds_matter"
ADDR=${1:-${BLINDS_IP:-192.168.50.135}}
PY=${PY:-$HOME/.espressif/python_env/idf5.5_py3.9_env/bin/python}

# the version being built: refuse to guess if the sources disagree
VERS=$(grep -ho '^#define FW_VERSION "[^"]*"' main/*.h | sort -u | sed 's/.*"\(.*\)"/\1/')
[ -n "$VERS" ] || { echo "no #define FW_VERSION in main/*.h"; exit 1; }
if [ "$(echo "$VERS" | wc -l)" -ne 1 ]; then
  echo "FW_VERSION differs between files, fix that first:"; grep -H '^#define FW_VERSION' main/*.h; exit 1
fi
echo "building $VERS"

./build.sh build > build.log 2>&1 || { grep -n "error:" build.log | head; exit 1; }
grep -o "blinds_matter.bin binary size.*" build.log
python3 ../../tools/release_firmware.py --sign build/blinds_matter.bin
# The controller's plain web page is locked, so talk to it the way the app does (as an owner).
ask() { "$PY" ../../tools/blinds_client.py --ip "$ADDR" --as owner get "$1"; }
case $(ask /api/otaopen) in *'"ok":1'*) ;; *) echo "the controller did not allow the update"; exit 1;; esac   # 5 minutes
R=$(curl -fsS -m 180 -X POST -H "Content-Type: application/octet-stream" --data-binary @build/blinds_matter.bin.signed "http://$ADDR/api/update")
echo "$R"
case $R in *'"ok":1'*) ;; *) echo "update refused"; exit 1;; esac
# The new firmware is on trial until told to keep it: check it answers with the new version, then keep it.
# (A restart of the controller while on trial goes back to the old firmware.)
sleep 25
V=
for i in 1 2 3 4 5 6; do
  V=$(ask /api/s 2>/dev/null | sed -n 's/.*"v":"\([^"]*\)".*/\1/p') || true
  [ -n "$V" ] && break
  sleep 5
done
[ -n "$V" ] || { echo "no answer after the update: restart the controller to go back to the old firmware"; exit 1; }
echo "running $V"
[ "$V" = "$VERS" ] || { echo "expected $VERS: not keeping it (restart the controller to go back)"; exit 1; }
[ -n "$NOKEEP" ] || case $(ask /api/keep) in *'"ok":1'*) echo "kept";; *) echo "keep failed"; exit 1;; esac
