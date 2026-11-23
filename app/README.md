# Tilt: the iPhone app

SwiftUI app in [Tilt](Tilt) with a Home Screen widget and Control Center buttons. No server: the phone talks to each
controller through the Tilt Hub over a secured channel (the hub cannot read it), and sets up a new controller over
Bluetooth.

- `Tilt/Tilt/`: the app. `Tilt/Shared/`: code shared with the widget. `Tilt/TiltWidget/`: the widget and controls.
- Open `Tilt/Tilt.xcodeproj` in Xcode and run the `Tilt` scheme.
