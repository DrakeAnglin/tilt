# Tilt: the iPhone app

SwiftUI app in [Tilt](Tilt) with a Home Screen widget and Control Center buttons. No server: the phone talks to each
controller through the Tilt Hub over a secured channel (the hub cannot read it), and sets up a new controller over
Bluetooth.

- `Tilt/Tilt/`: the app. `Tilt/Shared/`: code shared with the widget. `Tilt/TiltWidget/`: the widget and controls.
- Open `Tilt/Tilt.xcodeproj` in Xcode and run the `Tilt` scheme.

## Tests

- `tools/app_tests.sh` runs them all: two test programs (`Tilt/Tests/main.swift` on the Mac, `Tilt/Tests/iPhone` in a
  simulator), then the Xcode tests on an iPhone simulator of their own, `Tilt tests` (made the first time).
- The Xcode tests: unit tests in `Tilt/Tests/Unit` (the `TiltTests` target) and UI tests in `Tilt/Tests/UI`
  (`TiltUITests`). A new file in either folder is picked up with no project or script edit. In Xcode: pick a
  simulator and choose Product, Test.
- A test run starts the app with `-testrun` (`Tilt/Tilt/Launch.swift`): it clears the app's saved settings on that
  simulator and keeps keys only in memory, and asks nothing of iCloud, the network, Bonjour or Bluetooth. Only in a
  developer build, only in a simulator.
