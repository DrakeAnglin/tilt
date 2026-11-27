# Automations live in the home; Tilt keeps only the Light trigger

Clock, sunrise and sunset automations belong to the Matter home the blinds are in (Apple Home, Alexa, or any other Matter controller). Tilt no longer offers its own. The one Schedule Tilt keeps is the Light trigger ("When it gets light", "When it gets dark"), because only the controller can read its solar panel, and no home app can express it. Light Schedules are made in the Tilt app.

## Why

- **One place for automations.** With two schedulers, Apple Home can open the blinds at 7:00 and a Tilt Schedule can close them at 7:05, and nobody can tell why. Each home already does time, sunrise with offsets, scenes, presence and other devices' triggers better than Tilt will.
- **We expect every Tilt home to have a Matter controller that runs automations** (a HomePod, Apple TV, Echo or similar). The Tilt Hub is required anyway, and Tilt is built to sit in a Matter home.
- **Less to maintain.** Most of the cost of Schedules is in the app: one Schedule spread over several controllers, slot ids, the editor, and the tests.
- **What started it** (2026-11-27): the Dining sunrise and sunset Schedules never ran, because the controller had no location and nothing said so. Apple Home already knows the home's location.

## What we gave up

- **Running without a home hub.** A clock or sunrise automation now needs the home's own hub, and a working path from it through the Tilt Hub and Thread to the controller. A controller's own Schedule ran even with Wi-Fi or the Tilt Hub down. We accept that, because we expect every home to have a hub.
- **Gentle on a clock time.** A home sends "go to this position". Matter has no way to ask for a slow move, and a command does not say whether a person or an automation sent it (the controller can only tell which home it came from). So "move gently when an automation sends it" cannot be built today. A Light Schedule can still be gentle.

## Considered and rejected

- **Tilt keeps all its Schedules alongside the home's.** That leaves two schedulers that can fight. Rejected.
- **The Tilt app writes Apple Home automations for you** (HomeKit triggers). It would keep the Tilt screens, but it does nothing for Alexa, needs Apple's HomeKit approval, and adds a second way to make the same automation. Not needed now: people make automations in their home app.
- **Warn when a blind has both a Tilt Schedule and a home automation.** Not needed once Tilt has no clock or sun Schedules. A Light Schedule and a home automation on the same blind is the owner's choice.

## Consequences

- The app stops offering clock time, sunrise and sunset Schedules, and points to the home app for those. Light Schedules stay, gentle moves included.
- The controller still needs its location: the Light trigger's window is placed around sunrise and sunset, and it falls back to the sun time when there is no panel. A Light Schedule must not be saved, or run silently, without one.
- Clock and sun slots already on a controller can keep running until a firmware release removes them. The app shows them so they can be deleted.
- If this comes back up (for example, homes without a Matter hub turn out to be common), this ADR is the place to change it.
