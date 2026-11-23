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
`HUB DATASET <hex>` (the Thread network) and `HUB SETUP CODE` (for Apple Home). Both stay on the USB log only. A
plain `flash` keeps what the hub has learned (Thread network, people, tiles, backups); only `erase-flash` clears it.

## Update the hub (no cable)

```bash
tools/flash_hub.sh
```

Raise `PROJECT_VER` in `CMakeLists.txt` first. The hub has two firmware slots: the signed file goes into the spare
one over Wi-Fi (owner-allowed, signature and version checked), the hub restarts on it on trial and keeps it once Wi-Fi
and Apple Home have worked for a minute, otherwise it goes back by itself. About a minute in all. The spare slot is
also where a controller's update waits while the hub sends it. The setup code lives in the hub's flash (copied there
from `main/setup_pin.h` at its first USB flash), so update files carry no code.

## Add a controller

Use the app: plug the controller in (it can be set up in its first 15 minutes after power-on), then Add a New Device.
Setup pairs over Bluetooth, hands over the hub's Thread network, lets the hub in and tells the controller which key
is the hub's. Its blinds then show up in Apple Home through the hub by themselves.

## Update a controller from the bench

```bash
tools/flash.sh <controller id>
```

Builds, signs and sends it through the hub: a patch when `~/.tilt/fw/` has the image the controller runs (about a
minute), else the whole file (`FULL=1` forces that; about 7 minutes). The tool needs owner keys, once:
`blinds_client.py --ip <hub>/hub --as hub-owner ask` and `blinds_client.py --ip <hub>/c/<id> --as <name> ask`, each
let in as an owner from the app; then `TILT_AS=<name> tools/flash.sh <id>`.

## Known limits (bench)

- One C6 for both radios: Espressif rates Wi-Fi plus a Thread network on one chip as "supported but unstable".
  The plan is to stay with one chip. A second chip (ESP32-S3 + ESP32-H2, `docs/research/thread-border-router-chips.md`
  on its research branch) is only the fallback if response times through the hub fall short.
- The app is only 3 % short of the 2 MB firmware slot: keep an eye on the size.
