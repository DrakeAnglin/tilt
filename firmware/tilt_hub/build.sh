#!/bin/sh
# Build the Tilt Hub firmware. Extra arguments go to idf.py (for example: ./build.sh -p /dev/cu.usbmodemXXXX flash monitor).
# Wi-Fi comes from main/secrets.h (not in Git; copy main/secrets.h.example) until Apple Home gives the hub its network.
cd "$(dirname "$0")"
. ~/esp/esp-idf/export.sh > /dev/null 2>&1
. ~/esp/esp-matter/export.sh > /dev/null 2>&1
# sdkconfig (not in Git) is made from sdkconfig.defaults: made again whenever the defaults change, so every checkout
# builds with the same settings (the memory and TLS trims for push alerts live there).
if [ -f sdkconfig ] && [ sdkconfig.defaults -nt sdkconfig ]; then rm -f sdkconfig; rm -rf build; fi
[ -f sdkconfig ] || idf.py set-target esp32c6 > build-setup.log 2>&1
# A worktree has no local-only files. Take them from the main checkout, so a worktree build matches the bench hub;
# with none there, secrets.h comes from the example (it builds; the hub just cannot join that Wi-Fi).
MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")/firmware/tilt_hub/main
for F in secrets.h setup_pin.h; do
  [ -f "main/$F" ] || [ ! -f "$MAIN/$F" ] || [ "$MAIN" -ef main ] || cp "$MAIN/$F" "main/$F"
done
[ -f main/secrets.h ] || { cp main/secrets.h.example main/secrets.h; echo "main/secrets.h made from the example: no bench Wi-Fi in this build."; }
# The hub's setup code (8 digits): the first owner types it in the app. Made once, kept in main/setup_pin.h (not in
# Git). Put it on a label on the hub.
if [ ! -f main/setup_pin.h ]; then
  PIN=$(LC_ALL=C tr -dc 0-9 < /dev/urandom | head -c 8)
  printf '// The Tilt Hub setup code: on its label. Made by build.sh; never commit it.\n#pragma once\n#define HUB_SETUP_PIN "%s"\n' "$PIN" > main/setup_pin.h
  echo "New Tilt Hub setup code: ${PIN%????}-${PIN#????}  (put it on the hub's label; kept in main/setup_pin.h)"
fi
idf.py "${@:-build}"
