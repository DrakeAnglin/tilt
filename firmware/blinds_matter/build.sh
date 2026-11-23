#!/bin/sh
# Build the controller firmware (Thread, for a Tilt Hub). Extra arguments go to idf.py
# (for example: ./build.sh -p /dev/cu.usbmodemXXXX flash monitor). BUILD_DIR / SDKCONFIG_FILE: another build folder
# and settings file (the release script uses its own).
cd "$(dirname "$0")"
. ~/esp/esp-idf/export.sh > /dev/null 2>&1
. ~/esp/esp-matter/export.sh > /dev/null 2>&1
D=${BUILD_DIR:-build}; C=${SDKCONFIG_FILE:-sdkconfig}
[ -f "$C" ] || idf.py -B "$D" -D SDKCONFIG="$C" set-target esp32c6 > build-setup.log 2>&1
idf.py -B "$D" -D SDKCONFIG="$C" "${@:-build}"
