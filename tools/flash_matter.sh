#!/bin/sh
# Build the Apple Home (Matter) firmware and send it to the controller over Wi-Fi.
#   tools/flash_matter.sh [address]      default address: 192.168.50.135
# The build is signed with ~/.tilt/firmware-signing-key.pem (tools/release_firmware.py --sign), so it installs on a
# controller running a public release too. A firmware that cannot join Wi-Fi goes back by itself.
set -e
cd "$(dirname "$0")/../firmware/blinds_matter"
ADDR=${1:-192.168.50.135}
./build.sh build > build.log 2>&1 || { grep -n "error:" build.log | head; exit 1; }
grep -o "blinds_matter.bin binary size.*" build.log
python3 ../../tools/release_firmware.py --sign build/blinds_matter.bin
# The controller's plain web page is locked, so talk to it the way the app does (as an owner).
PY=${PY:-$HOME/.espressif/python_env/idf5.5_py3.9_env/bin/python}
ask() { "$PY" ../../tools/blinds_client.py --ip "$ADDR" --as owner get "$1" 2>/dev/null | tail -1; }
ask /api/otaopen > /dev/null                      # allow a firmware upload for 5 minutes
curl -s -m 180 -X POST -H "Content-Type: application/octet-stream" --data-binary @build/blinds_matter.bin.signed "http://$ADDR/api/update"
echo
# The new firmware is on trial until told to keep it: check it answers, then keep it. (NOKEEP=1: leave it on trial;
# a restart of the controller then goes back to the old firmware.)
sleep 25
for i in 1 2 3 4 5 6; do
  V=$(ask /api/s | sed -n 's/.*"v":"\([^"]*\)".*/\1/p')
  [ -n "$V" ] && break
  sleep 5
done
[ -n "$V" ] || { echo "no answer after the update: restart the controller to go back to the old firmware"; exit 1; }
echo "running $V"
[ -n "$NOKEEP" ] || ask /api/keep > /dev/null
