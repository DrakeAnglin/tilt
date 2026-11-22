#!/bin/sh
# Run the app's tests on the Mac (no simulator needed): builds the shared code with the tests and runs them.
set -e
cd "$(dirname "$0")/../app/Tilt"
OUT=$(mktemp -d)
# Design.swift is colors (UIKit, iPhone only): the tests do not need it.
swiftc -o "$OUT/tilt-tests" $(ls Shared/*.swift | grep -v Design.swift) Tests/main.swift 2>"$OUT/errors" || { cat "$OUT/errors"; exit 1; }
"$OUT/tilt-tests"
