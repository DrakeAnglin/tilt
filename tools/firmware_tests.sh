#!/bin/sh
# Run the firmware's logic tests on the Mac (no hardware, no ESP-IDF): firmware/blinds_matter/test/logic_test.cpp,
# ota_test.cpp (a firmware file through the hub) with files signed by tools/release_firmware.py with a throwaway key,
# the hub link both firmwares share (firmware/blinds_matter/test/link_test.cpp) and the hub's link to a controller
# (firmware/tilt_hub/test/ctrl_link_test.cpp). The link tests use test/host_mbedtls, a stand-in for mbedtls.
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
c++ -std=c++17 -Wall -Wextra -O1 -I host_mbedtls -o "$OUT/link_test" link_test.cpp
"$OUT/link_test"
c++ -std=c++17 -Wall -Wextra -O1 -pthread -I host_mbedtls -I ../main -o "$OUT/ctrl_link_test" ../../tilt_hub/test/ctrl_link_test.cpp
"$OUT/ctrl_link_test"
