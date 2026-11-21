#!/bin/sh
# Build the blinds firmware (web app included) and send it to the controller over Wi-Fi.
#   tools/flash_blinds.sh [address]      default address: blinds-pcb.local
# The update password is read from firmware/blinds/secrets.h. A firmware that cannot join Wi-Fi rolls back by itself.
set -e
cd "$(dirname "$0")/.."
ADDR=${1:-blinds-pcb.local}
OUT=${TMPDIR:-/tmp}/blinds-build
python3 tools/build_ui.py
cd firmware
bin/arduino-cli compile --fqbn esp32:esp32:esp32c6:CDCOnBoot=cdc --build-path "$OUT" blinds | grep "Sketch uses"
PW=$(sed -n 's/^#define OTA_PASSWORD *"\(.*\)".*/\1/p' blinds/secrets.h)
bin/arduino-cli upload --fqbn esp32:esp32:esp32c6:CDCOnBoot=cdc -p "$ADDR" --protocol network --upload-field password="$PW" --input-dir "$OUT" blinds > "$OUT/upload.log" 2>&1 && echo "sent to $ADDR" || { echo "upload failed:"; tr '\r' '\n' < "$OUT/upload.log" | grep -v -i password | tail -4; exit 1; }
