# Tilt Hub: showing blinds in Matter, and talking to controllers

Research for [#41](https://github.com/DrakeAnglin/tilt/issues/41), part of the
[Tilt Hub map (#37)](https://github.com/DrakeAnglin/tilt/issues/37).
Sources were checked on 2026-11-22. Each claim links to the spec, doc or source file it comes from.
Hub hardware is from [#39](https://github.com/DrakeAnglin/tilt/issues/39): ESP32-S3 host + ESP32-H2 radio.

## Short answer

- **The hub is a Matter bridge.** One Aggregator endpoint, then one Bridged Node endpoint per
  blind with Window Covering + Power Source on it. esp-matter has a ready bridge component that adds
  and removes these endpoints at runtime and remembers them across reboots.
- **Apple Home and Alexa both list bridges and window coverings as supported.** Neither publishes
  details on how they show a *bridged* blind's battery or "not responding". Those are must-tests.
- **Hub to controller: plain CoAP over Thread, not Matter.** A sleeping controller is woken by
  its own poll timer either way, so the wake-ups are the same. CoAP needs about 2 messages per
  command; Matter needs about 3 plus session setup, keep-alive reports and a full Matter
  controller in the hub.
- **Speed comes from the poll timer, not the protocol.** The hub holds each message until the
  controller next checks in. A short poll (or Thread CSL) is what makes a blind react fast.

**Recommendation:** hub = esp-matter bridge (Matter over Wi-Fi to Apple Home and Alexa) + its
own private Thread network for the controllers. Controllers in Tilt Hub mode run Thread as a
sleepy child and speak a small CoAP API to the hub. Start from esp-matter
`examples/bridge_apps/bridge_cli` (plus `examples/common/app_bridge`) for the Matter side, and
ESP-IDF `examples/openthread/ot_br` / `ot_rcp` (hub) and `ot_sleepy_device` (controller) for Thread.

## 1. How the bridge works in Matter

### What the spec asks for

- A bridge puts an **Aggregator** endpoint (device type 0x000E) on the node. Each bridged device
  is an endpoint in the Aggregator's PartsList.
- Each bridged device endpoint carries the **Bridged Node** device type (0x0013) and the
  **Bridged Device Basic Information** cluster. That cluster "shall be exposed by a Bridge on the
  Endpoint representing each Bridged Device", and must not be used outside an Aggregator's
  PartsList (spec section 9.13, quoted in
  [matter.js cluster types](https://cdn.jsdelivr.net/npm/@matter/types@0.17.0/src/clusters/bridged-device-basic-information.d.ts)).
- **Reachable** (boolean) tells controllers whether the bridge can reach the device, so they know
  a command "might fail" when it is false. A **ReachableChanged** event fires when it flips
  (same source, sections 9.13.5.2 and 9.13.7.2).
- **Power Source** and **Power Source Configuration** are allowed (optional) on a Bridged Node
  endpoint. That is where each blind's battery goes.
  ([connectedhomeip `matter-devices.xml`, MA-bridgednode](https://github.com/project-chip/connectedhomeip/blob/master/src/app/zap-templates/zcl/data-model/chip/matter-devices.xml))
- Matter 1.4 added an optional **BridgedICDSupport** feature: a `KeepActive` command
  (StayActiveDuration, TimeoutMs 30 s to 1 h) and an `ActiveChanged` event, so a controller can ask
  the bridge to keep a sleeping bridged device awake.
  ([data_model 1.4.2 BridgedDeviceBasicInformationCluster.xml](https://github.com/project-chip/connectedhomeip/blob/master/data_model/1.4.2/clusters/BridgedDeviceBasicInformationCluster.xml))
  We do not need it: our hub answers for the blind right away and passes the command on.

So one blind on the hub looks like this:

```
Endpoint 0   Root Node
Endpoint 1   Aggregator
Endpoint 2+  Bridged Node + Window Covering      (one per blind)
             clusters: Bridged Device Basic Information (Reachable, NodeLabel, UniqueID),
                       Window Covering, Power Source (battery percent, charge level)
```

Battery belongs to the *controller*, which serves up to 3 blinds. Each blind endpoint can carry its
own Power Source showing the shared battery (simplest), or the three blinds can sit under one
Bridged Node with a Power Source whose EndpointList names them (the spec allows a bridged device
to span endpoints, Bridged Device Basic Information then sits on the top one). Pick the simple
one first and see what Apple Home shows.

### How esp-matter builds it

- `esp_matter_bridge` component: `create_device(node, parent_endpoint_id, device_type_id, priv_data)`,
  `remove_device()`, `resume_device()` and `initialize(node, device_type_cb)`. It creates each
  device as a `bridged_node` endpoint with `ENDPOINT_FLAG_DESTROYABLE | ENDPOINT_FLAG_BRIDGE`.
  ([`esp_matter_bridge.h`](https://github.com/espressif/esp-matter/blob/main/components/esp_matter_bridge/esp_matter_bridge.h),
  [`esp_matter_bridge.cpp`](https://github.com/espressif/esp-matter/blob/main/components/esp_matter_bridge/esp_matter_bridge.cpp))
- **It remembers bridged endpoints across reboots.** `initialize()` reads the stored endpoint list
  from NVS (partition set by `CONFIG_ESP_MATTER_BRIDGE_INFO_PART_NAME`, default `nvs`), and each
  device's parent endpoint, endpoint ID and device type are stored with it (same .cpp).
- **Limit on blinds:** `MAX_BRIDGED_DEVICE_COUNT = CONFIG_ESP_MATTER_MAX_DYNAMIC_ENDPOINT_COUNT - 1
  - CONFIG_ESP_MATTER_AGGREGATOR_ENDPOINT_COUNT`. The default is 16 - 1 - 1 = **14 blinds**; the
  Kconfig allows up to 255 ([esp_matter Kconfig](https://github.com/espressif/esp-matter/blob/main/components/esp_matter/Kconfig),
  [esp_matter_bridge Kconfig](https://github.com/espressif/esp-matter/blob/main/components/esp_matter_bridge/Kconfig)).
  Raise it to cover a whole house (for example 32).
- `examples/common/app_bridge/app_bridged_device.h` adds a list of bridged devices keyed by the
  native address (for us: the controller's Thread address + port), saved to NVS:
  `app_bridge_create_new_device()`, `app_bridge_get_device(addr)`, `app_bridge_remove_device()`.
  ([`app_bridged_device.h`](https://github.com/espressif/esp-matter/blob/main/examples/common/app_bridge/app_bridged_device.h))
- Examples in `examples/bridge_apps`: `bridge_cli` (add or remove bridged devices from a console:
  `matter esp bridge add <parent_ep> <device_type>`), `esp-now_bridge_light`, `zigbee_bridge`,
  `blemesh_bridge`, `esp_rainmaker_bridge`, `dali_bridge`
  ([bridge_apps](https://github.com/espressif/esp-matter/tree/main/examples/bridge_apps),
  [bridge_cli README](https://github.com/espressif/esp-matter/blob/main/examples/bridge_apps/bridge_cli/README.md)).
  `bridge_cli` is the closest to ours: no radio-specific code, just add endpoints on demand.
- **Endpoint IDs are never reused.** Removing and re-adding a blind gives it a new endpoint, so
  Apple Home sees a new tile ([esp-now_bridge_light README](https://github.com/espressif/esp-matter/blob/main/examples/bridge_apps/esp-now_bridge_light/README.md)).
  Keep a blind's endpoint when its controller is swapped or its cord changes port.

## 2. Do Apple Home and Alexa handle bridged window coverings?

### Apple Home

- Apple lists "bridges" and "blinds and shades" as supported Matter categories
  ([Apple Support 102135](https://support.apple.com/en-us/102135)). The Matter SDK's Apple page
  lists Window Covering (0x0202) and Bridges (0x000E) as supported in Apple Home
  ([connectedhomeip `docs/guides/darwin.md`](https://github.com/project-chip/connectedhomeip/blob/master/docs/guides/darwin.md)).
- An Apple engineer explains that to Matter only the bridge is a real accessory; HomeKit "invents"
  one accessory per bridged endpoint. Behavior with a bridge that is not set up to spec is
  undefined ([Apple forums 786861](https://developer.apple.com/forums/thread/786861)). So the
  endpoint layout must follow the spec exactly.
- A report of a **tilt-only** Matter blind: Apple Home said "not responding" and sent tilt only as
  0% or 100% ([Apple forums 740415](https://developer.apple.com/forums/thread/740415)). Our
  firmware sends tilt on the lift channel today, which avoids this; keep that in the bridge.
- Apple's Matter best-practices guide (v1.5, 2025-10-07) covers SDK versions, diagnostics and OTA,
  but says nothing about bridges, battery or Reachable
  ([Matter Accessory Best Practices for Apple Home](https://developer.apple.com/apple-home/downloads/Matter-Accessory-Best-Practices-for-Apple-Home.pdf)).
  It asks for the Diagnostic Logs, General Diagnostics and Wi-Fi Network Diagnostics clusters
  and Matter OTA on the hub.
- **Not found in any Apple source:** whether Home shows a battery level for a bridged Power
  Source, and whether Reachable = false shows "No Response". Must-test.

### Alexa

- Alexa supports Matter bridges. "For each bridged device, the bridge must implement the Bridged
  Node (0x0013) device type and the Bridged Device Basic Information cluster", plus the clusters
  for the device's own category. Window covering (0x0202) is listed ("venetian blind
  controllers"), mapped to Alexa.RangeController. Echo uses Matter SDK 1.5.1
  ([Alexa supported Matter device categories](https://developer.amazon.com/en-US/docs/alexa/smarthome/supported-matter-device-categories.html),
  [Alexa Matter support](https://developer.amazon.com/en-US/docs/alexa/smarthome/matter-support.html),
  both last modified 2026-11-04).
- Power Source shows up only on the smoke alarm row (mapped to EndpointHealth and
  InventoryLevelSensor). Nothing on battery for blinds, nothing on Reachable. Must-test,
  together with [#18](https://github.com/DrakeAnglin/tilt/issues/18).

### What this means

Both ecosystems accept the layout. The three things to test on a real bridge are: position
moves and reports right, battery shows, and a blind whose controller is gone shows "not
responding". Apple and Amazon publish no details on the last two.

## 3. Hub to controller over Thread

### The network

The hub runs its own Thread network (leader/router on the ESP32-H2 radio). Controllers join it as
sleepy children of the hub. The hub talks to Apple Home and Alexa over Wi-Fi only, so this Thread
network does not need to be shared with an Apple or Amazon border router. (Whether a Tilt Hub and
an Apple hub *should* share one Thread network is open in #37.)

### What a sleeping controller costs

This part is the same for every protocol, because it is how Thread works:

- A **sleepy end device (SED)** keeps its radio off and "occasionally poll[s] the parent Router
  for any pending data". "A higher polling frequency results in lower latency ... but also higher
  power consumption." ([Nordic: SED types in Thread](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/protocols/thread/sed_ssed.html))
  The hub holds messages for the controller until its next poll.
- A **synchronized SED (SSED)** uses Thread 1.2 CSL: it wakes in short scheduled windows and the
  parent sends right then, no poll needed. Rule of thumb: worth it when the CSL period is under
  20 s and the parent has good CSL timing. The same page gives window coverings as an example
  that "may need responses within 500 ms" with rare data.
  ESP-IDF has `CONFIG_OPENTHREAD_CSL_ENABLE`
  ([ESP-IDF OpenThread Kconfig](https://github.com/espressif/esp-idf/blob/release/v5.5/components/openthread/Kconfig)).
- The hub can see each child's health for free: OpenThread's child table gives `mAge` (seconds
  since last heard), `mQueuedMessageCnt`, `mIsCslSynced`
  ([otChildInfo](https://openthread.io/reference/struct/ot-child-info)). That is enough to drive
  the Reachable flag with no extra messages.

So the **number of wake-ups is set by the poll (or CSL) period**, not by CoAP vs. Matter. The
protocol only changes how many messages and how much crypto happen per wake.

### Option A: plain UDP / CoAP between hub and controller

OpenThread has CoAP built in: confirmable and non-confirmable messages, `otCoapSendRequest()`,
default port 5683, min ACK timeout 1000 ms, up to 20 retries, Observe option, block-wise transfer
([OpenThread CoAP API](https://openthread.io/reference/group/api-coap)).

Per command (hub tells a blind to move), estimated from the protocol:

| Step | Messages |
|---|---|
| Hub queues a confirmable request; controller gets it at its next poll | 1 |
| Controller answers with the result in the ACK (piggybacked) | 1 |
| Controller sends position and battery when the move ends (non-confirmable, or confirmable if it must arrive) | 1 (2) |

Nothing else: no session setup, no keep-alive reports. Thread already encrypts every frame with
the network key, and only the hub and its controllers have that key. Signed Owner/Guest
commands can still ride inside the CoAP payload if we want the controller to check them.

### Option B: Matter between hub and controller

The hub would be a Matter *controller* too (commission each blind controller onto a hub fabric,
open CASE sessions, subscribe). esp-matter has `examples/controller` for this
([esp-matter examples](https://github.com/espressif/esp-matter/tree/main/examples)). Estimated cost:

- Per command: Invoke Request, Invoke Response, and an MRP ACK back to the controller. The last
  one is again held for the controller's next poll, so it stays awake a bit longer (Matter ICDs
  have an "active mode threshold" for this; see
  [Silicon Labs Matter ICD guide](https://docs.silabs.com/matter/2.8.0/matter-overview-guides/matter-icd)).
- **Session setup (CASE):** about 4 messages and public-key crypto on the controller after every
  hub reboot or session loss.
- **Subscriptions:** the controller must send a report at least once per max interval even when
  nothing changes, so the hub knows it is alive. That is extra wake-ups that Option A does not
  need, because Thread polls already tell the hub the child is alive.
- Big code on both ends: the hub runs a Matter server (to Apple) and a Matter controller +
  commissioner (to the blinds). Two fabrics to manage, more flash and RAM on the hub.

### Option C: plain UDP (no CoAP)

Smallest frames, but we would write our own retries, ACKs and duplicate checks. CoAP gives that
for free in OpenThread at almost no extra bytes. Not worth it.

## 4. Recommendation

1. **Matter side:** start from esp-matter `examples/bridge_apps/bridge_cli` with the
   `esp_matter_bridge` component and `examples/common/app_bridge`. Aggregator + one Bridged Node +
   Window Covering + Power Source per blind. Set `CONFIG_ESP_MATTER_MAX_DYNAMIC_ENDPOINT_COUNT` to
   fit a house (about 32). Keep tilt on the lift channel, like the controller firmware does now.
2. **Thread side, hub:** ESP32-S3 host + ESP32-H2 radio, based on ESP-IDF `examples/openthread/ot_br`
   (host) and `ot_rcp` (H2), or esp-matter `examples/thread_border_router` which already combines
   Matter + OpenThread on Espressif's S3 + H2 board. The hub forms its own Thread network.
3. **Thread side, controller:** sleepy child (SED first, SSED/CSL as a later power test), based on
   ESP-IDF `examples/openthread/ot_sleepy_device` (`light_sleep` and `deep_sleep`). Matter is
   off in Tilt Hub mode.
4. **Link:** a small CoAP API on the controller (for example `PUT /p/<port>/tilt`,
   `GET /state`) and on the hub (`POST /report`). Hub sets Reachable from the child table `mAge`.
5. **Must-tests before the hub spec is final:** (a) Apple Home and Alexa show a bridged blind's
   position and accept moves; (b) bridged battery shows in each app; (c) Reachable = false shows
   "not responding"; (d) poll period vs. reaction time vs. battery on the bench (feeds
   [#6](https://github.com/DrakeAnglin/tilt/issues/6)).

## Not found in primary sources

- How Apple Home and Alexa show battery for a bridged device, and how they show Reachable = false.
- Real current numbers for an ESP32-C6 sleepy child at a given poll period; this needs our own
  bench test.
- The message counts in section 3 are worked out from the protocols, not measured.
