# Controllers are Thread-only, through a Tilt Hub

Controllers talk only Thread, to a Tilt Hub; they have no Wi-Fi. The hub is the home's Matter device for every blind (a bridge on Wi-Fi), passes the app's sealed commands along, feeds firmware updates over Thread, keeps settings backups and finds new controllers over Bluetooth. Wi-Fi on a controller cost about ten times the battery of a sleeping Thread device (`docs/research/thread-sleepy-battery.md`, research branch) and needed its own setup screens and update path.

We rejected two alternatives. Keeping Wi-Fi as a fallback meant two firmwares to build, test and update, for homes the hub serves anyway. Using someone else's Thread border router instead of a hub failed in practice: Apple Home would not use the SmartThings Thread network ("Thread Border Router Required"), and a controller that is its own Matter device would need an Apple Thread border router (HomePod mini, Apple TV 4K with Ethernet) to test.

Consequences: every home needs a Tilt Hub; if the hub is unplugged the blinds do not answer (their wands still work by hand, and Schedules keep running on the controllers). A mode where a controller is its own Matter device on an Apple, Amazon or Google Thread border router, with no Tilt Hub, is possible later and has to be built and tested once such a router is at hand.
