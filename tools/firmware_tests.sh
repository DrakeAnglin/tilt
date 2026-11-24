#!/bin/sh
# Run the firmware's logic tests on the Mac (no hardware, no ESP-IDF):
#   firmware/blinds_matter/test/logic_test.cpp   the controller
#   firmware/tilt_hub/test/hub_test.cpp          the Tilt Hub (needs mbedtls: see below)
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(mktemp -d)
cd "$ROOT/firmware/blinds_matter/test"
c++ -std=c++17 -Wall -Wextra -O1 -o "$OUT/logic_test" logic_test.cpp
"$OUT/logic_test"

# The hub test checks real signatures, with mbedtls (the library the firmware uses): the system's if it has one
# (CI: apt-get install libmbedtls-dev; a Mac: brew install mbedtls), else built here from ESP-IDF's copy.
cd "$ROOT/firmware/tilt_hub/test"
HUB_INC="-I../main -I../../blinds_matter/main"
BREW=$(brew --prefix mbedtls 2>/dev/null || true)
IDF_MBED="${IDF_PATH:-$HOME/esp/esp-idf}/components/mbedtls/mbedtls"
if [ -n "$BREW" ] && [ -f "$BREW/include/mbedtls/ecdsa.h" ]; then
  MBED="-I$BREW/include -L$BREW/lib -lmbedcrypto"
elif printf '#include <mbedtls/ecdsa.h>\n' | c++ -x c++ -fsyntax-only - 2>/dev/null; then
  MBED="-lmbedcrypto"
elif [ -f "$IDF_MBED/library/ecdsa.c" ]; then
  for f in sha256 ecdsa ecp ecp_curves bignum bignum_core constant_time platform_util platform asn1parse asn1write md hmac_drbg sha1 sha512 sha3 md5 ripemd160; do
    cc -O1 -I"$IDF_MBED/include" -DMBEDTLS_USER_CONFIG_FILE='"mbedtls_host.h"' -I. -c "$IDF_MBED/library/$f.c" -o "$OUT/mbed_$f.o"
  done
  MBED="-I$IDF_MBED/include -DMBEDTLS_USER_CONFIG_FILE=\"mbedtls_host.h\" -I. $OUT/mbed_*.o"
else
  echo "hub test: no mbedtls. Install it (Mac: brew install mbedtls; Linux: apt-get install libmbedtls-dev) or ESP-IDF." >&2
  exit 1
fi
# shellcheck disable=SC2086
c++ -std=c++17 -Wall -Wextra -O1 $HUB_INC -o "$OUT/hub_test" hub_test.cpp $MBED
"$OUT/hub_test"
