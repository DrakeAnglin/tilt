#!/bin/bash
# Build the Tilt Hub firmware and install it over Wi-Fi (no cable).
#   tools/flash_hub.sh [hub address]          hub: $TILT_HUB, else 192.168.50.122
# The build is signed with ~/.tilt/firmware-signing-key.pem. The hub takes it only in the 5 minutes after its owner
# allows it (this tool's "hub-owner" key: see firmware/tilt_hub/README.md), checks the signature and that it is not
# older, and starts it on trial: kept once Wi-Fi and Apple Home have worked for a minute, otherwise it goes back.
# Raise PROJECT_VER in firmware/tilt_hub/CMakeLists.txt for each update. A hub with the old one-slot layout needs one
# USB flash first (./build.sh -p <port> flash in firmware/tilt_hub, or --usb below).
set -eo pipefail
PY=${PY:-$HOME/.espressif/python_env/idf5.5_py3.9_env/bin/python}
case ${1:-} in
  -h|--help) cat <<'EOF'
Build the Tilt Hub firmware and install it.
  tools/flash_hub.sh [hub address]     over Wi-Fi: an update (the hub keeps its codes)
  tools/flash_hub.sh --usb <port> [--label-size WxH] [--new-identity]
                                       the first flash, over USB: a new hub gets its Apple Home code and setup code,
                                       saved in ~/.tilt/devices on this Mac, and a setup label (PNG and PDF, 25x25 mm)
  --new-identity   developer flag: wipe the hub's saved data and make new codes; asks for its short ID first
More: tools/device_identity.py --help
EOF
    exit 0;;
  --usb) P=${2:?usage: tools/flash_hub.sh --usb <port>}; shift 2
    exec "$PY" "$(dirname "$0")/device_identity.py" flash hub --port "$P" "$@";;
esac
HUB=${1:-${TILT_HUB:-192.168.50.122}}
cd "$(dirname "$0")/../firmware/tilt_hub"
fw() { "$PY" ../../tools/blinds_client.py --ip "$HUB/hub" hello 2>/dev/null | sed -n 's/.*"fw":"\([^"]*\)".*/\1/p'; }

echo "building"
./build.sh > build.log 2>&1 || { grep -n "error:" build.log | head; exit 1; }
grep -o "tilt_hub.bin binary size.*" build.log
"$PY" ../../tools/release_firmware.py --sign build/tilt_hub.bin
BEFORE=$(fw)
"$PY" ../../tools/blinds_client.py --ip "$HUB/hub" --as hub-owner get /api/hubupdate | grep -q '"ok":1' || { echo "the hub did not allow the update (is this tool an owner on it?)"; exit 1; }
R=$(curl -sS -m 180 -X POST -H "Content-Type: application/octet-stream" --data-binary @build/tilt_hub.bin.signed "http://$HUB/hub/api/update")
case $R in *'"ok":1'*) echo "the hub took it ($R), restarting";; *) echo "the hub refused: $R"; exit 1;; esac
for i in $(seq 1 30); do
  sleep 5
  NOW=$(fw)
  [ -n "$NOW" ] && [ "$NOW" != "$BEFORE" ] && { echo "running $NOW (kept by itself once Wi-Fi and Apple Home work for a minute)"; exit 0; }
done
echo "the hub did not come back with new firmware (it goes back to $BEFORE by itself if the new one fails)"; exit 1
