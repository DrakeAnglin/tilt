# Tilt Hub

An ESP32-C6 on a USB wall plug that lets the controllers sleep. Bench version: one C6 runs both radios (Wi-Fi and
Thread share its antenna), and the firmware is updated over USB.

- **Apple Home** adds the hub once (Matter over Wi-Fi). It shows **one tile per controller**, or one per blind
  when the controller's "separate tiles" setting (`hksep`) is on. Battery and "not responding" come with each tile.
- **Controllers** run the Thread build of `blinds_matter` and join the hub's own Thread network as sleepy children
  (one check-in a second). They push their status to the hub only when something changes, and every 10 minutes.
- **The Tilt app** finds each controller as before: the hub announces it as `_tilt._tcp` with
  `ip=<hub address>/c/<controller id>` and passes the app's sealed commands along. It cannot read them.
- **The hub's own key:** it asks to join each controller as "Tilt Hub"; the app lets it in by itself (as a user) and
  tells the controller which key is the hub's.

- **New controllers are found by themselves.** A controller nobody owns says "Tilt new" over Bluetooth for its first
  15 minutes; the hub scans for it (a few seconds every half minute, 10 % duty) and the app shows "New controller
  found". Setup offers Tilt Hub or Wi-Fi; with the hub the app hands over the hub's Thread network (from one of your
  controllers on it, or from the hub while a new controller is nearby), lets the hub in, and the blinds appear in
  Apple Home by themselves.
- **Firmware updates through the hub.** The app uploads the signed file to `/c/<id>/api/update`; the hub keeps it in
  its `fwstage` partition and feeds it over Thread (the controller keeps its radio on meanwhile). Thread carries about
  4 KB a second, so a whole file (1.6 MB) takes about 7 minutes. Usually it is a **patch** instead: only what changed
  since the firmware the controller runs (`esp_delta_ota`; releases list them under `patches`, `tools/flash.sh` makes
  one from the image it last installed), typically a tenth of the size. Progress is in
  `/hub` (`ota`, `otaPct`, `otaErr`). Releases carry a Thread build (`thread` in firmware.json).
- **Alerts without waking anyone.** The app's background check reads battery and last check-in from `/hub`.
- **Settings backups.** Each controller's settings, schedules and blind positions are kept on the hub (fetched when
  the checksum in its status push changes). Setting up a replacement offers "Restore", and the hub moves the old
  Apple Home tile over (`/hub/replace`).
- **Factory reset:** hold BOOT (not RST) for 10 s; the LED blinks slowly, then fast. Keeps the setup code only.
- **Hub page** in the app (Settings > Tilt Hub): every controller's battery, signal and last check-in.

The protocol between hub and controller is described at the top of `../blinds_matter/main/hub_link.h`.

## The hub's HTTP API

| Path | What |
|---|---|
| `GET /hub` | the hub's id and whether it has an owner (nothing else) |
| `/hub/x/hello`, `/hub/x/pair`, `/hub/x/ask`, `POST /hub/x` | a phone's key on the hub, and its sealed commands: `/api/info`, `/api/keys`, `/api/net`, `/api/homecode`, `/api/backups`, `/api/upload?id=` (owner) and the people commands |
| `/c/<id>/x...` | the app's sealed commands, passed to the controller over Thread |
| `POST /c/<id>/api/update` | a signed firmware file for that controller, only in the 5 minutes after the owner's `/api/upload?id=<id>` |

## Security

- **Setup code.** `build.sh` makes an 8-digit code once (`main/setup_pin.h`, not in Git) and prints it: put it on a
  label on the hub. The first owner (a new hub, or after its people are reset) types it in the app; it goes into the
  key, never over the network. Five wrong codes close connecting for 5 minutes.
- **Controllers' port (UDP 49100) is on Thread only.** Nothing on the Wi-Fi can reach it.
- **Proofs.** Once a controller has let the hub in and the app has marked the hub's key there (`/api/hubkey`), every
  status push, goodbye, time and firmware start between them carries an HMAC made from that key. Nothing else on the
  Thread network can pose as either side.
- **Firmware** is checked on the hub too (Tilt signature, not older than what the controller runs) before it is sent.
- Hardening still to do (flash encryption, secure boot, ...): `docs/security-hardening.md`.

## Build and flash

```bash
./build.sh -p /dev/cu.usbmodem21101 flash
```

Wi-Fi comes from `main/secrets.h` (copy `main/secrets.h.example`) until Apple Home gives the hub its network. The USB log prints
`HUB DATASET <hex>` (the Thread network, for `/api/hubjoin`) and `HUB SETUP CODE` (for Apple Home). Both stay on
the USB log only. Use `app-flash` to update without forgetting the Thread network, the setup code or the tiles.

## Move a controller onto the hub

1. While it is on Wi-Fi, give it the network: `blinds_client.py --ip <controller> --as owner get "/api/hubjoin?ds=<HUB DATASET>"`.
2. `tools/flash_thread.sh <controller id>`: builds the Thread firmware and installs it. If the controller cannot
   reach the hub within 5 minutes it goes back to Wi-Fi by itself. Run it again for later updates: on Thread it
   sends the file through the hub (`VIA_WIFI=1`: switch to its Wi-Fi firmware first and send over Wi-Fi).
   Or use the app: setup does all of this for a new controller.
3. Let "Tilt Hub" in from the app (People), as a user.
4. Remove the controller's old tile from Apple Home: Home now sees it through the hub.

`http://<hub>/hub` lists the controllers the hub knows (no keys).

## Known limits (bench)

- One C6 for both radios: Espressif rates Wi-Fi plus a Thread network on one chip as "supported but unstable".
  The plan is to stay with one chip. A second chip (ESP32-S3 + ESP32-H2, `docs/research/thread-border-router-chips.md`
  on its research branch) is only the fallback if response times through the hub fall short.
- One firmware slot (plus the staging area): no update over the air for the hub itself yet.
- A controller whose firmware predates the always-on radio takes small pieces: about 90 minutes for one update.
- The app is only 3 % short of the 2 MB firmware slot: keep an eye on the size.
