#!/bin/bash
# Build the controller firmware and install it through the Tilt Hub (a patch when it can; FULL=1 for the whole file).
#   tools/flash.sh <controller id> [hub address]          hub: $TILT_HUB, else 192.168.50.122
# The build is signed with ~/.tilt/firmware-signing-key.pem (tools/release_firmware.py --sign). The hub keeps the file
# and feeds it to the controller over Thread; the new firmware runs on trial and goes back by itself if it cannot
# reach the hub. (A controller with no firmware yet, or a broken one: ./build.sh -p <USB port> flash in
# firmware/blinds_matter, or --usb below.)
set -eo pipefail
PY=${PY:-$HOME/.espressif/python_env/idf5.5_py3.9_env/bin/python}
case ${1:-} in
  -h|--help) cat <<'EOF'
Build the controller firmware and install it.
  tools/flash.sh <controller id> [hub address]     through the Tilt Hub, over Thread: an update
  tools/flash.sh --usb <port> [--label-size WxH]   the first flash, over USB: saves the controller's record in
                                                   ~/.tilt/devices on this Mac and writes an ID label
  --new-identity   developer flag for a Tilt Hub only (tools/flash_hub.sh --usb); refused for a controller, which
                   has no code from the Mac: reset it from the app
More: tools/device_identity.py --help
EOF
    exit 0;;
  --usb) P=${2:?usage: tools/flash.sh --usb <port>}; shift 2
    exec "$PY" "$(dirname "$0")/device_identity.py" flash controller --port "$P" "$@";;
esac
ID=${1:?usage: tools/flash.sh <controller id> [hub address]}
HUB=${2:-${TILT_HUB:-192.168.50.122}}
cd "$(dirname "$0")/../firmware/blinds_matter"
ask() { "$PY" ../../tools/blinds_client.py --ip "$HUB/c/$ID" --as "${TILT_AS:-dining-owner}" get "$1"; }
# Progress from the hub's own list (sealed: the public /hub page shows no controllers).
member() { "$PY" ../../tools/blinds_client.py --ip "$HUB/hub" --as hub-owner get /api/info 2>/dev/null | "$PY" ../../tools/bench_json.py ota-progress "$ID"; }

echo "building"
./build.sh > build.log 2>&1 || { grep -n "error:" build.log | head; exit 1; }
grep -o "blinds_matter.bin binary size.*" build.log
# Every image put on a controller is kept (~/.tilt/fw/<its SHA-256>.bin), so the next update can be a patch: only
# what changed, about a minute over Thread instead of seven.
mkdir -p ~/.tilt/fw
IMG=$("$PY" ../../tools/blinds_client.py --ip "$HUB/c/$ID" hello 2>/dev/null | sed -n 's/.*"img":"\([0-9a-f]*\)".*/\1/p')
NEWIMG=$(tail -c 32 build/blinds_matter.bin | xxd -p -c 64)
cp build/blinds_matter.bin ~/.tilt/fw/$NEWIMG.bin
FILE=build/blinds_matter.bin.signed
if [ -n "$IMG" ] && [ -f ~/.tilt/fw/$IMG.bin ] && [ "${FULL:-0}" != 1 ]; then
  "$PY" ../../tools/release_firmware.py --sign build/blinds_matter.bin --patch-from ~/.tilt/fw/$IMG.bin && FILE=build/blinds_matter.bin.patch
else
  "$PY" ../../tools/release_firmware.py --sign build/blinds_matter.bin
fi
PRE=$("$PY" ../../tools/blinds_client.py --ip "$HUB/c/$ID" hello 2>/dev/null) || { echo "the controller does not answer through the hub"; exit 1; }
PREBOOT=$(echo "$PRE" | sed -n 's/.*"boot":"\([0-9a-f]*\)".*/\1/p')
case $(ask /api/otaopen) in *'"ok":1'*) ;; *) echo "the controller did not allow the update"; exit 1;; esac
# The hub takes a file only when its owner allows it (sealed, owner key on the hub: pair this tool once with
# "blinds_client.py --ip <hub>/hub --as hub-owner ask" and let it in as an owner from the app). An older hub does not ask.
"$PY" ../../tools/blinds_client.py --ip "$HUB/hub" --as hub-owner get "/api/upload?id=$ID" >/dev/null 2>&1 || true
R=$(curl -sS -m 120 -X POST -H "Content-Type: application/octet-stream" --data-binary @$FILE "http://$HUB/c/$ID/api/update")
case $R in *'"ok":1'*) echo "the hub has it, sending over Thread";; *) echo "the hub refused: $R"; exit 1;; esac
while true; do
  sleep 10
  set -- $(member)
  case $1 in 3) echo "sent, it restarts"; break;; 4) shift 2; echo "failed: $*"; exit 1;; *) echo "  $2%";; esac
done
for i in $(seq 1 40); do
  sleep 4
  H=$("$PY" ../../tools/blinds_client.py --ip "$HUB/c/$ID" hello 2>/dev/null || true)
  case $H in *'"boot":"'"$PREBOOT"'"'*|"") ;; *)
    echo "running $(echo "$H" | sed -n 's/.*"fw":"\([^"]*\)".*/\1/p') (kept by itself after a minute on the hub)"
    # Tell it which key is the hub's (the app does this too when it is open), so it trusts the hub's messages.
    HC=$("$PY" ../../tools/blinds_client.py --ip "$HUB/hub" --as hub-owner get /api/info 2>/dev/null | "$PY" ../../tools/bench_json.py hub-cid "$ID" 2>/dev/null)
    [ -n "$HC" ] && ask "/api/hubkey?cid=$HC" >/dev/null && echo "hub key marked"
    exit 0;; esac
done
echo "it did not come back on the hub (a new firmware that cannot reach the hub goes back by itself)"; exit 1
