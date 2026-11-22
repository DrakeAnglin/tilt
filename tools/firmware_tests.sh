#!/bin/sh
# Run the firmware's logic tests on the Mac (no hardware, no ESP-IDF): firmware/blinds_matter/test/logic_test.cpp.
set -e
cd "$(dirname "$0")/../firmware/blinds_matter/test"
OUT=$(mktemp -d)
c++ -std=c++17 -Wall -Wextra -O1 -o "$OUT/logic_test" logic_test.cpp
"$OUT/logic_test"
