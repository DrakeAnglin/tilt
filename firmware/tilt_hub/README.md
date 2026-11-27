# Tilt Hub

An ESP32-C6 on a USB wall plug that lets the controllers sleep. Every home needs one, one hub serves every
controller, and it stays plugged in. Current version: one C6 runs both radios (Wi-Fi and Thread share its
antenna).

The first part of this page is what a builder needs. [For developers](#for-developers) has the rest.

## What the hub does

- **Apple Home** adds the hub once (Matter over Wi-Fi). It shows **one tile per controller**, or one per blind
  when the controller's "separate tiles" setting (`hksep`) is on. Battery and "not responding" come with each tile.
- **Controllers** run the Thread build of `blinds_matter` and join the hub's own Thread network as sleepy children
  (one check-in a second). They push their status to the hub only when something changes, and every 10 minutes.
- **The Tilt app** finds each controller as before: the hub announces it as `_tilt._tcp` with
  `ip=<hub address>/c/<controller id>` and passes the app's sealed commands along. It cannot read them.
- **The hub's own key:** it asks to join each controller as "Tilt Hub"; the app lets it in by itself (as a Guest) and
  tells the controller which key is the hub's.

- **New controllers are found by themselves.** A controller nobody owns says "Tilt new" over Bluetooth for its first
  15 minutes; the hub scans for it (a few seconds every half minute, 10 % duty) and the app shows "New controller
  found". The hub's Owner picks it and chooses Start fresh or Restore a backup; the app gets the hub's Thread network
  from the hub, gives it to the controller over Bluetooth, lets the hub in, and the blinds appear in Apple Home by
  themselves. Someone who is not the hub's Owner is told to connect to the hub first, or to ask its Owner.
- **Firmware updates through the hub.** The app uploads the signed file to `/c/<id>/api/update`; the hub keeps it in
  its `fwstage` partition and feeds it over Thread (the controller keeps its radio on meanwhile). Thread carries about
  4 KB a second, so a whole file (1.6 MB) takes about 7 minutes. Usually it is a **patch** instead: only what changed
  since the firmware the controller runs (`esp_delta_ota`; releases list them under `patches`, `tools/flash.sh` makes
  one from the image it last installed), typically a tenth of the size. Progress is in
  `/hub` (`ota`, `otaPct`, `otaErr`). Releases carry a Thread build (`thread` in firmware.json).
- **Push alerts** (issue #70): stalls, a controller not responding, battery levels and failed updates come to every
  owner's iPhone as a push, at home or away. See [Push alerts](#push-alerts).
- **Settings backups.** Each controller's settings, schedules and blind positions are kept on the hub (fetched when
  the checksum in its status push changes). Setting up a replacement offers "Restore", and the hub moves the old
  Apple Home tile over (`/hub/replace`).
- **Factory reset:** hold BOOT (not RST) for 10 s; the light blinks white, then fast. Keeps only the two codes on
  its label: the Apple Home code and the setup code.
- **Status light** (the board's color LED, GPIO8, at full brightness; the one-color LED on GPIO15 stays dark). Off
  when all is well. Otherwise the most urgent of: blinking white (factory reset), blinking blue (being added to Apple
  Home or Alexa), flashing red (no Wi-Fi once in a home, no Thread network, Matter not running, or a controller set up with
  the hub silent for 30 minutes; not in the first 90 s after a start), blinking purple (installing an update), solid
  blue (ready to be added, or an Alexa code is open), solid green (a new controller waiting for setup), slow yellow blink (a controller's
  battery too low to move its blinds). The app's hub page
  lists them too. `/api/light` (owner) sets the lights by hand for a minute, to tell which is which on a new board.
- **Alexa and other home apps** (issue #18). `/api/sharecode` (owner) gives a one-time code for a second Matter home:
  a fresh random passcode in an enhanced pairing window (15 minutes, one home, Wi-Fi only), the same kind Apple
  Home's "Turn On Pairing Mode" makes. A second ask while it is good gives the same code. A hub in no home yet gives
  its own code instead (`first: 1`). The app shows it under Alexa on the hub page and opens the Alexa app.
- **Hub page** in the app (Settings > Tilt Hub): every controller's battery, signal and last check-in.

The protocol between hub and controller is described at the top of `../blinds_matter/main/hub_link.h`.

## Build and flash

```bash
./build.sh -p <USB port> flash
```

Wi-Fi comes from `main/secrets.h` (copy `main/secrets.h.example`) until Apple Home gives the hub its network. The USB log prints
`HUB DATASET <hex>` (the Thread network) and `HUB SETUP CODE` (for Apple Home). Both stay on the USB log only. A
plain `flash` keeps what the hub has learned (Thread network, people, tiles, backups); only `erase-flash` clears it.

## Setup code

The first flash from the Mac, `tools/flash_hub.sh --usb <USB port>`, makes the hub's two codes: its Apple Home code
and its 8-digit setup code. It writes them into the hub's saved data before its first start, keeps them in
`~/.tilt/devices/` on that Mac (never in Git) and writes a setup label with both
([Print a setup label](../../docs/build-guide.md#print-a-setup-label)). A reflash or an update keeps them.

A plain `./build.sh -p <port> flash` works too: then `build.sh` makes an 8-digit code once (`main/setup_pin.h`, not
in Git) and prints it, and the hub makes its own Apple Home code on its first start (the app shows it). The first
owner (a new hub, or after its people are reset) types the setup code in the app; it goes into the key, never over
the network. Five wrong codes close connecting for 5 minutes.

## Add a controller

Use the app: plug the controller in (it can be set up in its first 15 minutes after power-on), then Add a New Device.
Setup pairs over Bluetooth, hands over the hub's Thread network, lets the hub in and tells the controller which key
is the hub's. Its blinds then show up in Apple Home through the hub by themselves.

## For developers

Not needed to build a hub: the code, the API, push alerts, updates from the Mac and the known limits.

### Code

One compiled file: `main/hub.cpp` includes the parts below once, in this order (each uses what the ones before it
hold). The pure rules beside them are tested on the Mac (`test/`).

- `hub.cpp`: the includes, Thread start, the status light, factory reset, `app_main`.
- `hub_store.h`: what the hub keeps about each controller, in memory and in flash.
- `hub_matter.h`: Matter: one Window covering per blind, the Apple Home setup code, the homes the hub is in.
- `hub_ctrl.h`: the link to the controllers over Thread (on `ctrl_link.h` and `tilt_link.h`).
- `hub_alerts.h`: when the hub tells owners (on `alert_rules.h`; `cloud.h` sends them).
- `hub_care.h`: settings backups, the care task, new controllers nearby on Bluetooth.
- `hub_update.h`: firmware for a controller through the hub, and the hub's own (on `hub_file.h`).
- `hub_pair.h`: the hub's people: keys, setup code, the hub's id, pairing (on `hub_people.h`; the key exchange is the controller's `tilt_pair.h`).
- `hub_api.h`: what the app asks the hub: the relay to a controller, the hub's commands, the HTTP handlers, and
  the one-time code for another home app (last, after its one caller, so the binary stays the same).
- `cloud.h`, `lights.h`: push alerts through iCloud, and the color light.

### The hub's HTTP API

| Path | What |
|---|---|
| `GET /hub` | the hub's id and whether it has an owner (nothing else) |
| `/hub/x/hello`, `/hub/x/pair`, `/hub/x/ask`, `POST /hub/x` | a phone's key on the hub, and its sealed commands: `/api/info`, `/api/keys`, `/api/net`, `/api/homecode`, `/api/backups`, `/api/upload?id=`, `/api/testalert` (owner) and the people commands |
| `GET /c/<id>/x/hello`, `POST /c/<id>/x/ask`, `POST /c/<id>/x/recover`, `GET /c/<id>/x/recstate`, `POST /c/<id>/x` | passed to the controller over Thread: its hello, asking to join, getting back in when no owner is left, and the app's sealed commands. A new controller takes its first owner over Bluetooth only, so there is no `/x/pair` here |
| `POST /c/<id>/api/update` | a signed firmware file for that controller, only in the 5 minutes after an owner's `/api/upload?id=<id>` |

### Push alerts

The hub is always on and knows each controller's check-ins, battery and stalls, so it is the one that tells the owners.
It writes an **Alert** record to the app's iCloud container (`iCloud.app.tilt.blinds`, CloudKit public database) with
CloudKit's server-to-server key; each owner's Tilt app has a subscription on that controller's topic (and the hub's
own, for the hub's alerts), so iCloud sends the push. No Tilt server, no other push service.

| Alert | When | Sent |
|---|---|---|
| `stall` | a blind stalled during an ordinary move (the controller's status counts them: `b[].st`) | once per stall |
| `silent` | a controller set up with the hub not heard for 25 minutes (it checks in every 10) | once, cleared when heard |
| `batt-low`, `batt-crit`, `batt-dead` | under 20 %, under 10 %, too low to move | each level once; reset at 25 % |
| `update` | a firmware update through the hub failed | once |
| `hub-update` | the hub's own new firmware did not work and it went back | once per version |
| `test` | `/api/testalert` (owner): try the whole path | each time |

"Tilt Hub is offline" is the one alert the hub can't send: an owner's iPhone on the home Wi-Fi (the same Wi-Fi router
as when the hub last answered) that can't reach the hub for 3 minutes shows it, once per outage.

- **Code:** the rules in `main/alert_rules.h` (tested in `blinds_matter/test/logic_test.cpp`), sending in
  `main/cloud.h`, every alert through `alertRaise()`. The app's words: `app/Tilt/Shared/Words.swift` (`AlertWords`);
  the push is worded by the app's notification extension (`app/Tilt/TiltAlerts`).
- **A record** holds the topic (a random name only phones that talked to the controller know), the kind, the blind
  (port), the room's name, a short detail (the battery percent, the blind's name, why an update failed), a number and
  a time. No keys, no addresses. There is one record per topic, kind and blind, replaced each time, so the database
  does not grow.
- **No internet?** Alerts wait in the hub's flash (10 at most, a week at most) and go once it is back. A try whose
  answer was lost looks first whether iCloud already has that alert, so it never comes twice.
- **Memory:** a TLS session takes about 22 KB of the hub's memory for a few seconds. The hub sends only with 50 KB
  free (about 63 KB is free when it is idle) and not while a firmware file is coming in or going out; otherwise the alert waits a minute. Only the two roots
  iCloud's certificate comes from are on the hub (`main/cloud_roots.pem`): if Apple moves to another root, the hub
  page shows an error and that file needs the new one. `/api/mem` (owners) lists free memory and each task's stack low
  point; `"mem"` in `/api/info`'s `cloud` gives the last send's memory before and at its lowest, and the lowest of any.
  Wi-Fi and Bluetooth buffers and some task stacks were cut to what a hub needs (`sdkconfig.defaults`, measured the
  same way): measure again before raising anything.
- **Both iCloud environments:** the app built from Xcode listens in "development", the App Store app in
  "production"; the hub writes to both. `/api/info` has `cloud` (key there, alerts waiting, last status and error).

#### The iCloud key (once, by the developer)

The key stays out of Git, like `secrets.h`: it lives in `~/.tilt/` and in `main/cloud_key.h` (ignored), and is copied
into the hub's flash at its next start. A public release build carries no key; each hub keeps its own in flash.

1. Make the key: `~/.espressif/python_env/idf5.5_py3.9_env/bin/python tools/cloudkit_key.py new`. It prints a public
   key.
2. In [CloudKit Console](https://icloud.developer.apple.com/dashboard/), container `iCloud.app.tilt.blinds`:
   **Tokens & Keys** > **Server-to-Server Keys** > **+**, paste the public key, save, and copy the **Key ID**. Keys
   are per environment: do it once in **Development** and once in **Production** (the same public key both times).
3. `tools/cloudkit_key.py header <Development Key ID> <Production Key ID>`, then update the hub:
   `tools/flash_hub.sh`.
4. Try it: `tools/cloudkit_key.py test <topic>` from the Mac, or `/api/testalert` on the hub.
5. Once, by hand, in Development: record type **Alert** with fields `topic`, `kind`, `name`,
   `detail` (String), `port`, `n` (Int(64)), `at` (Date/Time), and a **Queryable** index on `topic` (the phones'
   subscriptions need it). A server key can't make these itself. **Deploy Schema Changes** copies them to Production,
   so App Store phones get alerts too.

### Security

- **Controllers' port (UDP 49100) is on Thread only.** Nothing on the Wi-Fi can reach it.
- **Proofs.** Once a controller has let the hub in and the app has marked the hub's key there (`/api/hubkey`), every
  status push, goodbye, time and firmware start between them carries an HMAC made from that key. Nothing else on the
  Thread network can pose as either side.
- **Firmware** is checked on the hub too (Tilt signature, not older than what the controller runs) before it is sent.
- Hardening still to do (flash encryption, secure boot, ...): [docs/developer/security-hardening.md](../../docs/developer/security-hardening.md).

### Update the hub from the Mac (no cable)

```bash
tools/flash_hub.sh
```

Raise `PROJECT_VER` in `CMakeLists.txt` first. The hub has two firmware slots: the signed file goes into the spare
one over Wi-Fi (owner-allowed, signature and version checked), the hub restarts on it on trial and keeps it once Wi-Fi
and Apple Home have worked for a minute, otherwise it goes back by itself. About a minute in all. With no firmware to
go back to, it stays on the new one, still on trial. The spare slot is also where a controller's update waits while the hub sends it. The codes live in the hub's saved data (written by
`tools/flash_hub.sh --usb`, or copied from `main/setup_pin.h` at its first start), so update files carry no code.

### Update a controller from the Mac

```bash
tools/flash.sh <controller id>
```

Builds, signs and sends it through the hub: a patch when `~/.tilt/fw/` has the image the controller runs (about a
minute), else the whole file (`FULL=1` forces that; about 7 minutes). The tool needs owner keys, once:
`blinds_client.py --ip <hub>/hub --as hub-owner ask` and `blinds_client.py --ip <hub>/c/<id> --as <name> ask`, each
let in as an owner from the app; then `TILT_AS=<name> tools/flash.sh <id>`.

### Known limits

- One C6 for both radios: Espressif rates Wi-Fi plus a Thread network on one chip as "supported but unstable".
  The plan is to stay with one chip. A second chip (ESP32-S3 + ESP32-H2, `docs/research/thread-border-router-chips.md`
  on its research branch) is only the fallback if response times through the hub fall short.
- Firmware slot space: about 68 KB is free in the 0x1F0000 app slot at 0.3.18. The 4 MB flash is fully used by the
  two slots (0x20000 + 2 x 0x1F0000), so the slots cannot grow. CI's hub build fails when under 32 KB is free
  (`tools/firmware_size.py`); the way to make room is a trim, which is settings in `sdkconfig.defaults` (see #144).
