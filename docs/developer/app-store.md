# App Store release

Tilt 1.0 (build 3) was submitted to the App Store on 2026-11-21. Apple answered on 2026-11-22 with Guideline 2.1
"Information Needed": no bug, but they want a screen recording from a real device and written answers in the review
notes (issue #126). Build 4 goes back with both. This page keeps the account steps, the answers given in App Store
Connect, and how firmware is published, for the next release.

**Status (2026-11-25):** build 4 resubmitted with the notes below, the recording attached (in App Review Information and
in the Resolution Center reply), and a reply to Apple. Waiting for review. The version is set to release automatically
once approved.

## Account steps (owner only)
1. ~~App Store Connect record~~ done 2026-11-21: "Tilt: Smart Blinds" (the name Tilt was taken), bundle ID `app.tilt.blinds`, SKU TILT001. The home-screen name stays Tilt.
2. ~~CloudKit~~ done 2026-11-21 (`Gone` added; schema deployed to Production). Was: in the CloudKit Console, open container `iCloud.app.tilt.blinds`, Development, and use
   "Deploy Schema Changes" to copy the record types `Join` and `Gone` to Production. Add a query index on `Join.topic`
   (queryable) if the console asks.
3. **Website:** https://drakeanglin.github.io/tilt/ from `site/` in this repo (`.github/workflows/site.yml` publishes it on a
   merge to `main`). The privacy policy is `site/privacy.md`.
   - Privacy policy URL: https://drakeanglin.github.io/tilt/privacy/
   - Support URL: https://drakeanglin.github.io/tilt/support/
   - Questions and problems: issues on `DrakeAnglin/tilt`
4. **Firmware hosting:** the app reads `https://github.com/DrakeAnglin/tilt/releases/latest/download/firmware.json`.
   A release is a version tag on `main` (`fw-v2.3.0`, `hub-v0.3.4`): a GitHub Action builds, signs and publishes it.
   See `docs/developer/firmware-release.md`. Use releases on this repo for firmware only, so "latest" is always the newest firmware.
5. **Release-day clean-up on the controller:** remove the "Duo Test" user, and the "Mac owner" key once the app can do
   every update (the Mac tools need that key today).

## Listing status (filled in App Store Connect, 2026-11-21)
- Version page: promotional text, description, keywords, support and marketing URLs, copyright, App Review notes,
  sign-in not required, automatic release, App Review contact, screenshots, build 3 (build 4 for the resubmission).
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
Apple's 2.1 "Information Needed" asks for six things. The Notes field (App Review Information, at most 4000 characters)
holds the text below, and the screen recording goes in the Attachment field next to it.

**Screen recording (owner, on the iPhone):** turn on Screen Recording in Control Center, record, then open Tilt from the
home screen. Show: the first screen, Try the Demo, open and close a room and one blind, a scene, Automations (a
schedule), Settings, then Add a New Device and set up a real controller over Bluetooth, and open and close the real
blinds with the phone. Film the real blinds with a second phone if possible; otherwise the app alone is fine. Under
about 3 minutes; trim in Photos.

> 1. RECORDING: attached, filmed with a second camera so the real blinds show. It starts on the home screen of a real device,
> opens Tilt, and opens and closes real blinds with a Tilt controller: all three at once, then one blind with its
> slider. The demo (point 3) shows the rest without hardware. Tilt has no accounts, no user-generated content and
> nothing paid.
>
> 2. PURPOSE AND AUDIENCE: Tilt is the companion app for Tilt, a small open-source battery motor that clips onto the
> tilt rod of ordinary horizontal blinds. It is for people who want their existing blinds to open and close on a
> schedule, at sunrise and sunset, from Apple Home and Siri, without replacing them. The app sets up the controller,
> moves the blinds, and keeps schedules and scenes on the controller itself, so they run when the phone is away.
>
> 3. HOW TO REVIEW (no login, no hardware needed): on the first screen tap "No controller yet? Try the Demo" (also under
> + then Try the Demo). The demo room, "Living Room (Demo)", acts like a real one: tap Open or Close, press and hold
> them for a gentle move or Set Tilt…, tap the room to move one blind, run the Morning or Movie scene, add a
> schedule in Automations, and change room and blind settings in Settings. Bluetooth setup, Apple Home, the Tilt Hub and sharing with family need the hardware; they are shown in the
> recording. Sign in with Apple is optional and only fills in the display name that people you share with see. There is
> no account and nothing to log in to.
>
> 4. EXTERNAL SERVICES: only Apple's own and GitHub. iCloud (CloudKit and key-value storage) passes "ask to join"
> requests between family members and keeps the display name. Sign in with Apple (optional) for that name. Apple Push
> Notifications for join requests and low-battery alerts. Apple Home (HomeKit and Matter) to add blinds to the Home app.
> Firmware update files are downloaded from the project's public GitHub Releases page. Everything else talks only to
> the user's own controller and hub, over Bluetooth or the home Wi-Fi network. No server of ours, no analytics, no ads,
> no AI services, no payments. Location is read once on the phone to work out sunrise and sunset and is sent only to the
> user's own controller.
>
> 5. REGIONS: the app works the same in every region where it is offered. It is not offered in China mainland.
>
> 6. REGULATION AND THIRD-PARTY MATERIAL: not applicable. Tilt is a home convenience product; it uses no protected
> third-party content and is not in a regulated industry. The hardware designs and code are our own, published under
> open licenses at https://github.com/DrakeAnglin/tilt.

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
