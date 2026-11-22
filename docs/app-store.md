# App Store release checklist

What is still needed before Tilt can go to TestFlight and the App Store, and the answers to give.

## Steps only the owner can do (Apple account)
1. **App Store Connect:** create the app record for bundle ID `app.tilt.blinds` (name Tilt, primary language English).
2. **CloudKit:** in the CloudKit Console, open container `iCloud.app.tilt.blinds`, Development, and use
   "Deploy Schema Changes" to copy the record types `Join` and `Gone` to Production. Add a query index on `Join.topic`
   (queryable) if the console asks.
3. **Privacy policy URL:** once the repo is public on GitHub, use the link to `docs/privacy-policy.md`.
4. **Firmware hosting:** the app reads `https://github.com/DrakeAnglin/tilt/releases/latest/download/firmware.json`.
   For each firmware release: `python3 tools/release_firmware.py stable --notes "..."` (builds without secrets, signs),
   then upload `firmware/releases/firmware.json` and the new `tilt-<version>.bin` to a GitHub release. The repo must be
   public for phones to download them.
5. **Release-day clean-up on the controller:** remove the "Duo Test" user, and the "Mac owner" key once the app can do
   every update (the Mac tools need that key today).

## App Privacy answers (App Store Connect)
- Data used to track you: **None.**
- Data linked to you, for App Functionality only: **Name** (your display name, in a request to join),
  **Other User Content** (the room's name, in the same request). Both pass through Tilt's iCloud container.
- Location: **not collected** (it is sent only to the user's own controller, never to the developer).
- Everything else: not collected.

## Export compliance (encryption)
Tilt uses standard encryption from Apple's CryptoKit (P-256 key agreement, AES-256-GCM) to secure the connection to
the user's own controller, and HTTPS. To confirm before the first upload: this is expected to be "uses encryption,
exempt (standard algorithms, mass market)". `ITSAppUsesNonExemptEncryption` is not set yet, so App Store Connect will
ask at upload.

## Notes for App Review
> Tilt controls a small battery-powered controller for window blinds. You do not need one to review the app: on the
> first screen tap "No controller yet? Try the Demo" (or Add, Try the Demo). The demo room behaves like a real one:
> open, close, gentle moves, schedules, scenes and settings all work. Bluetooth setup, Apple Home and sharing need the
> hardware. Sign in with Apple is used only for the display name shown to people you share blinds with.

## Metadata draft
- **Subtitle:** Smart tilt for your blinds
- **Description:** Tilt opens and closes your window blinds from your iPhone, Apple Home, Siri and schedules that run on
  the controller itself, so they work even when your phone is away. Move blinds gently over minutes, set scenes, follow
  sunrise and sunset, and share access with the people you live with. No account, no cloud server, no tracking.
- **Keywords:** blinds, smart home, tilt, window, shades, Apple Home, schedule, sunrise, automation
- **Category:** Lifestyle (secondary: Utilities)

## Screenshots
Made with the demo room in a developer build: `xcrun simctl launch <device> app.tilt.blinds -demo -skyminute 600`
(add `-tab 1` for Automations, `-tab 2` for Settings). Needed sizes: iPhone 6.9" and iPad 13".
