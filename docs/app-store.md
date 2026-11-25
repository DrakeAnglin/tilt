# App Store release

Tilt 1.0 (build 3) was submitted to the App Store on 2026-11-21. This page keeps the account steps, the answers
given in App Store Connect, and how firmware is published, for the next release.

## Account steps (owner only)
1. ~~App Store Connect record~~ done 2026-11-21: "Tilt: Smart Blinds" (the name Tilt was taken), bundle ID `app.tilt.blinds`, SKU TILT001. The home-screen name stays Tilt.
2. ~~CloudKit~~ done 2026-11-21 (`Gone` added; schema deployed to Production). Was: in the CloudKit Console, open container `iCloud.app.tilt.blinds`, Development, and use
   "Deploy Schema Changes" to copy the record types `Join` and `Gone` to Production. Add a query index on `Join.topic`
   (queryable) if the console asks.
3. **Website (public, separate from this private repo):** https://drakeanglin.github.io/tilt-site/ from the
   `DrakeAnglin/tilt-site` repo. The privacy policy lives only there (`privacy.md`); edit it in that repo.
   - Privacy policy URL: https://drakeanglin.github.io/tilt-site/privacy/
   - Support URL: https://drakeanglin.github.io/tilt-site/support/
   - Questions and problems: issues on `DrakeAnglin/tilt-site`
4. **Firmware hosting:** the app reads `https://github.com/DrakeAnglin/tilt-site/releases/latest/download/firmware.json`
   (the public site repo, so this code repo can stay private). A release is a version tag on `main` (`fw-v2.3.0`,
   `hub-v0.3.4`): a GitHub Action builds, signs and publishes it. See `docs/firmware-release.md`.
   Use releases on tilt-site for firmware only, so "latest" is always the newest firmware.
5. **Release-day clean-up on the controller:** remove the "Duo Test" user, and the "Mac owner" key once the app can do
   every update (the Mac tools need that key today).

## Listing status (filled in App Store Connect, 2026-11-21)
- Version page: promotional text, description, keywords, support and marketing URLs, copyright, App Review notes,
  sign-in not required, manual release, App Review contact, screenshots, build 3.
- App Information: subtitle "Smart tilt for your blinds", Lifestyle / Utilities, no third-party content, rated 4+.
- Pricing: free. Availability: 174 countries or regions, all except China mainland (it needs a security assessment
  and an AI-content filing).
- App Privacy: answers saved (below); the owner publishes them (the publish step is an attestation).
- Screenshots: app/Tilt/AppStore/release-1.0/ (iPhone 6.9" 1320x2868, iPad 13" 2064x2752).

## App Privacy answers (App Store Connect)
- Data used to track you: **None.**
- Data linked to you, for App Functionality only: **Name** (your display name, in a request to join),
  **Other User Content** (the room's name, in the same request). Both pass through Tilt's iCloud container.
- Location: **not collected** (it is sent only to the user's own controller, never to the developer).
- Everything else: not collected.

## Export compliance (encryption)
Tilt's only encryption is Apple's CryptoKit (P-256 key agreement, AES-256-GCM, to secure the link to the user's own
controller) and HTTPS. It implements no encryption of its own and uses no third-party crypto library, so it only
"uses or accesses the encryption within Apple's operating system", which Apple treats as exempt.
`ITSAppUsesNonExemptEncryption` is set to false in Info.plist, so App Store Connect does not ask on each upload.
(The controller's firmware uses its own crypto library, but it is not part of the app.)

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
