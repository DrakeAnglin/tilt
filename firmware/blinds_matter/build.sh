#!/bin/sh
# Build the Matter firmware. Extra arguments go to idf.py (for example: ./build.sh -p /dev/cu.usbmodemXXXX flash monitor).
cd "$(dirname "$0")"
. ~/esp/esp-idf/export.sh > /dev/null 2>&1
. ~/esp/esp-matter/export.sh > /dev/null 2>&1
# the update password lives in main/secrets.h (not in Git)
[ -f main/secrets.h ] || { echo "main/secrets.h is missing: copy main/secrets.h.example and fill it in"; exit 1; }
[ -f sdkconfig ] || idf.py set-target esp32c6 > build-setup.log 2>&1
idf.py "${@:-build}"
