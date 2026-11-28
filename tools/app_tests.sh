#!/bin/sh
# Run the app's tests: builds the shared code (and the app's Apple Home code) with the tests and runs them on the Mac,
# then runs the iPhone-only checks in an iPhone simulator (HomeKit is not in the Mac's SDK), then the Xcode tests
# (Tests/Unit and Tests/UI: the TiltTests and TiltUITests targets) on a simulator of their own, "Tilt tests".
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

# The Xcode tests, on their own simulator: a test run replaces the app there and clears its saved settings, so never
# on one the owner uses. Signed to run locally (no account: CI has none; an unsigned build gets no Keychain), one
# binary per target (no debug dylib) for coverage, and one test at a time, so each test prints one
# "Test Case '…' passed|failed" line for the coverage gate.
TSIM=$(xcrun simctl list devices available | sed -n 's/^ *Tilt tests (\([0-9A-F-]\{36\}\)).*/\1/p' | head -1)
if [ -z "$TSIM" ]; then
  TYPE=$(xcrun simctl list devicetypes | sed -n 's/^iPhone.*(\(com\.apple\.CoreSimulator\.SimDeviceType\.[^)]*\))$/\1/p' | head -1)
  echo "making the iPhone simulator \"Tilt tests\" for the Xcode tests"; TSIM=$(xcrun simctl create "Tilt tests" "$TYPE")
fi
set +e
xcodebuild test -project Tilt.xcodeproj -scheme Tilt -destination "id=$TSIM" -derivedDataPath "$OUT/xcode" \
  -parallel-testing-enabled NO CODE_SIGN_IDENTITY=- CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM= ENABLE_DEBUG_DYLIB=NO >"$OUT/xcodebuild.log" 2>&1
RC=$?
set -e
grep -E "^Test Case '.*' (passed|failed)|error:" "$OUT/xcodebuild.log" || true
if [ "$RC" != 0 ]; then
  echo "xcodebuild failed ($RC); the end of its log:"; tail -40 "$OUT/xcodebuild.log"
  # A compile error can be in the result bundle only, not in the log.
  for R in "$OUT"/xcode/Logs/Test/*.xcresult; do
    [ -d "$R" ] && xcrun xcresulttool get build-results --path "$R" 2>/dev/null | grep -E '"(message|sourceURL)"' | head -40 || true
  done
fi
tail -1 "$OUT/xcodebuild.log"
rm -rf "$OUT/xcode"
exit "$RC"
