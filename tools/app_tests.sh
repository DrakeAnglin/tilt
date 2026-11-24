#!/bin/sh
# Run the app's tests: builds the shared code (and the app's Apple Home code) with the tests and runs them on the Mac,
# then runs the iPhone-only checks in an iPhone simulator (HomeKit is not in the Mac's SDK).
set -e
cd "$(dirname "$0")/../app/Tilt"
OUT=$(mktemp -d)
# Design.swift is colors (UIKit, iPhone only): the tests do not need it.
swiftc -o "$OUT/tilt-tests" $(ls Shared/*.swift | grep -v Design.swift) Tilt/HomeSetup.swift Tests/main.swift 2>"$OUT/errors" || { cat "$OUT/errors"; exit 1; }
# The shared wire fixture: made from the firmware and checked by both sides.
"$OUT/tilt-tests" ../../firmware/blinds_matter/test/wire
# The iPhone side: Apple's add-to-Home request, built and checked in an iPhone simulator (a running one, or the first
# one there is, started for this). The iOS version is the app's (its IPHONEOS_DEPLOYMENT_TARGET).
SIM=$(xcrun simctl list devices booted | sed -n 's/.*iPhone.*(\([0-9A-F-]\{36\}\)) (Booted).*/\1/p' | head -1)
if [ -z "$SIM" ]; then
  SIM=$(xcrun simctl list devices available | sed -n 's/.*iPhone.*(\([0-9A-F-]\{36\}\)) (Shutdown).*/\1/p' | head -1)
  [ -n "$SIM" ] || { echo "no iPhone simulator: install one in Xcode (Settings, Components)"; exit 1; }
  echo "starting an iPhone simulator for the iPhone checks"; xcrun simctl boot "$SIM"
fi
IOS=$(sed -n 's/.*IPHONEOS_DEPLOYMENT_TARGET = \([0-9.]*\);.*/\1/p' Tilt.xcodeproj/project.pbxproj | head -1)
SDK=$(xcrun --sdk iphonesimulator --show-sdk-path)
SDKROOT="$SDK" swiftc -target "$(uname -m)-apple-ios$IOS-simulator" -sdk "$SDK" -o "$OUT/tilt-iphone-tests" Tilt/HomeSetup.swift Tests/iPhone/main.swift 2>"$OUT/errors" || { cat "$OUT/errors"; exit 1; }
xcrun simctl spawn "$SIM" "$OUT/tilt-iphone-tests"
