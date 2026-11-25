#!/bin/sh
# Run the firmware's logic tests on the Mac (no hardware, no ESP-IDF): firmware/blinds_matter/test/logic_test.cpp, and
# ota_test.cpp (a firmware file through the hub) with files signed by tools/release_firmware.py with a throwaway key.
# Needs python3 and openssl.
set -e
cd "$(dirname "$0")/../firmware/blinds_matter/test"
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
c++ -std=c++17 -Wall -Wextra -O1 -o "$OUT/logic_test" logic_test.cpp
"$OUT/logic_test"
python3 make_ota_files.py "$OUT"
c++ -std=c++17 -Wall -Wextra -O1 -o "$OUT/ota_test" ota_test.cpp
"$OUT/ota_test" "$OUT"
