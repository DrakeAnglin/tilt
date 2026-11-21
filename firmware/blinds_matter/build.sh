#!/bin/sh
# Build the Matter firmware. Extra arguments go to idf.py (for example: ./build.sh -p /dev/cu.usbmodemXXXX flash monitor).
cd "$(dirname "$0")"
. ~/esp/esp-idf/export.sh > /dev/null 2>&1
. ~/esp/esp-matter/export.sh > /dev/null 2>&1
# shared with the Wi-Fi firmware: the web app (packed page) and the Wi-Fi / update passwords
python3 ../../tools/build_ui.py > /dev/null && sed 's/#include <Arduino.h>/#include "ardu.h"/' ../blinds/ui.h > main/ui.h && cp ../blinds/secrets.h main/secrets.h
[ -f sdkconfig ] || idf.py set-target esp32c6 > build-setup.log 2>&1
idf.py "${@:-build}"
