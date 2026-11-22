# Thread border router: one ESP32-C6 or two chips?

Research for [#39](https://github.com/DrakeAnglin/tilt/issues/39), part of the
[Tilt Hub map (#37)](https://github.com/DrakeAnglin/tilt/issues/37).
Sources were checked on 2026-11-22. Each claim links to the Espressif doc or file it comes from.

## Short answer

- **One C6 works, but Espressif does not recommend it for a border router.** The C6 has one radio
  path, so Wi-Fi and Thread take turns. Espressif rates "Wi-Fi connected + Thread router" as
  *supported but unstable*.
- **Two chips is the supported design.** A Wi-Fi chip (the "host") talks to an 802.15.4 chip
  (the "RCP", usually an ESP32-H2) over UART. Espressif's own border router board is
  ESP32-S3 + ESP32-H2.
- **Flash and RAM:** Espressif's Matter + Thread border router example uses **8 MB flash and PSRAM**.
  The C6 has 512 KB SRAM and no PSRAM. A border router + Matter bridge on 4 MB is very tight and
  leaves no room for safe two-slot updates. Plan on 8 MB.

**Recommendation:** build the Hub as **ESP32-S3 (8 MB flash, 2 MB PSRAM) + ESP32-H2 as RCP over
UART**, the same layout as Espressif's reference board. For the first prototype, buy the
ESP Thread Border Router board instead of wiring two dev boards.

## 1. One C6 doing Wi-Fi and Thread

The ESP-IDF border router example says it can run on one chip, but warns against it:

> "could also run on a single SoC which supports both Wi-Fi and Thread (e.g., ESP32-C6)" ...
> Wi-Fi and Thread cannot receive at the same time, which "has a significant impact on
> performance" ... "Hence the two SoCs solution is recommended."
> — [ESP-IDF `examples/openthread/ot_br/README.md`](https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_br/README.md)

To use one chip you set `CONFIG_OPENTHREAD_RADIO_NATIVE` and `CONFIG_ESP_COEX_SW_COEXIST_ENABLE`.
Both are on by default for the C6 (same README).

The ESP-IDF coexistence guide gives the support table for the C6
([RF coexistence, ESP32-C6](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/coexist.html)):

| Wi-Fi state | Thread scan | Thread **router** | Thread end device |
|---|---|---|---|
| STA connected | C1 (unstable) | **C1 (unstable)** | Y (stable) |
| SoftAP connected | C1 | **X (not supported)** | C1 |

A border router is always a Thread router, so the Hub would sit in the "unstable" cell. The same
page explains why:

- The radios share one RF path and use time slots. 802.15.4 normal receive has the **lowest
  priority**, so Thread only listens when Wi-Fi and BLE leave the radio free.
- Routers need to listen all the time, and "increased Wi-Fi or BLE traffic may lead to higher
  packet loss rates for Thread."
- For a Wi-Fi Thread border router it recommends "a dual-SoC solution (e.g., ESP32-S3 + ESP32-H2)
  with separate antennas."

The esp-thread-br standalone RCP guide says the same in plain words: "Using a single chip to handle
both Wi-Fi and Thread interfaces is not recommended."
([`README_standalone_RCP.md`](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/README_standalone_RCP.md))

**What this means for Tilt:** our controllers sleep and wake to poll their parent. Thread
messages for them are held by the parent (the Hub). If the Hub's radio is busy with Wi-Fi when a
controller polls, the poll or reply can be lost and the blind reacts late or needs a retry. Also,
SoftAP is "not supported" with a router, so a one-chip Hub could not use a SoftAP setup page while
Thread runs (BLE setup is still possible, but BLE also takes radio time).

Limits that were **not** found in primary sources: Espressif gives no numbers for added delay or
packet loss. Wi-Fi channel choice is not listed as a rule; Thread and Wi-Fi are both 2.4 GHz, and
the coexistence guide only talks about time sharing.

## 2. Two chips: how they connect

**Roles:** the host runs Wi-Fi, lwIP, the OpenThread stack and the border router (and Matter). The
RCP runs only the 802.15.4 radio (`ot_rcp` example) and talks to the host with the Spinel protocol.

**Which RCP chip:** ESP32-H2 is the default. An ESP32-C6 can also be the RCP
(`CONFIG_ESP_BR_C6_TARGET=y`). ([`README_standalone_RCP.md`](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/README_standalone_RCP.md),
[hardware platforms](https://docs.espressif.com/projects/esp-thread-br/en/latest/hardware_platforms.html))

**Which host chip:** `ot_br` lists ESP32, C2, C3, C5, C6, P4, S2, S3 as targets
([`ot_br/README.md`](https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_br/README.md)).
So a C6 host + H2 RCP is allowed. Espressif's board and Matter examples use the S3.

**Link:** UART is the documented and default link. SPI also exists in ESP-IDF
(`CONFIG_OPENTHREAD_RADIO_SPINEL_SPI` on the host, `CONFIG_OPENTHREAD_RCP_SPI` on the RCP)
([ESP-IDF `components/openthread/Kconfig`](https://github.com/espressif/esp-idf/blob/master/components/openthread/Kconfig),
[`ot_rcp/main/esp_ot_config.h`](https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_rcp/main/esp_ot_config.h)),
but no Espressif board or guide uses it. Use UART.

**Wiring on Espressif's board** (ESP32-S3 host, ESP32-H2-MINI-1 RCP, UART at 460800 baud)
([hardware platforms](https://docs.espressif.com/projects/esp-thread-br/en/latest/hardware_platforms.html)):

| Signal | S3 host | H2 RCP |
|---|---|---|
| UART TX | GPIO18 | GPIO23 (U0RXD) |
| UART RX | GPIO17 | GPIO24 (U0TXD) |
| RCP reset | GPIO7 | EN |
| RCP boot | GPIO8 | GPIO9 |
| PTA coexistence (optional, off by default) | GPIO12/10/13/11 | GPIO0/2/1/3 |

The reset and boot lines let the host **flash new RCP firmware by itself** at boot
(`esp_rcp_update`, `CONFIG_AUTO_UPDATE_RCP`). The RCP image is stored in an `rcp_fw` flash
partition on the host. Keep these two lines on the PCB so the H2 never needs its own USB port.

**Wiring with two dev boards** (any host, H2 or C6 RCP)
([`README_standalone_RCP.md`](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/README_standalone_RCP.md)):
GND–G, 5V–5V, host GPIO4 (RX)–RCP TX, host GPIO5 (TX)–RCP RX, host GPIO7–RCP RST,
host GPIO8–RCP GPIO9 (BOOT). Pins are set in `esp_ot_config.h` on both sides.

**Antennas:** two chips means two antennas, which is what Espressif recommends.

## 3. Flash and RAM for border router + Matter bridge (~30 endpoints)

What Espressif ships:

| Build | Flash | App slot | PSRAM | Source |
|---|---|---|---|---|
| esp-matter `thread_border_router` (Matter + BR) | **8 MB** | 3.4 MB x2 (OTA) + 640 KB RCP image | **Yes, required config** | [partitions.csv](https://github.com/espressif/esp-matter/blob/main/examples/thread_border_router/partitions.csv), [sdkconfig.defaults](https://github.com/espressif/esp-matter/blob/main/examples/thread_border_router/sdkconfig.defaults) |
| esp-thread-br basic BR (no Matter), 8 MB | 8 MB | 2 MB x2 (OTA) + 640 KB RCP | no | [partitions.csv](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/partitions.csv) |
| esp-thread-br basic BR (no Matter), 4 MB | 4 MB | one 3 MB factory app, **OTA turned off** | no | [partitions_4mb.csv](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/partitions_4mb.csv), [sdkconfig.defaults.4mb](https://github.com/espressif/esp-thread-br/blob/main/examples/basic_thread_border_router/sdkconfig.defaults.4mb) |
| esp-matter `zigbee_bridge` (Matter bridge, no Thread BR) | 4 MB | 1.8 MB x2 (OTA) | no | [partitions.csv](https://github.com/espressif/esp-matter/blob/main/examples/bridge_apps/zigbee_bridge/partitions.csv) |

The esp-matter border router README says: "The default setting flash size is 8MB", and it requires
the S3 + H2 board
([README](https://github.com/espressif/esp-matter/blob/main/examples/thread_border_router/README.md)).
Its config turns on PSRAM and moves Matter, BLE, Wi-Fi, lwIP and mbedTLS memory to PSRAM.

Size of a plain Matter app: the esp-matter `light` example uses about **1.48 MB flash and
195 KB D/IRAM** on a C3, with about 36 KB free heap at boot
([esp-matter `docs/en/optimizations.rst`](https://github.com/espressif/esp-matter/blob/main/docs/en/optimizations.rst)).
A border router adds the OpenThread BR, NAT64, mDNS/SRP server and route hooks on top of that.

Endpoints: each dynamic endpoint costs about **550 bytes of DRAM**; the default limit is 16 and can
go up to 255 (`CONFIG_ESP_MATTER_MAX_DYNAMIC_ENDPOINT_COUNT`)
([optimizations.rst](https://github.com/espressif/esp-matter/blob/main/docs/en/optimizations.rst),
[esp_matter Kconfig](https://github.com/espressif/esp-matter/blob/main/components/esp_matter/Kconfig)).
So 30 blinds (plus about 10 controller/aggregator endpoints) is only about 20–25 KB of endpoint
tables. Endpoints are not the problem; the stacks are.

C6 memory: 512 KB SRAM ([Espressif ESP32-C6 page](https://www.espressif.com/en/products/socs/esp32-c6)),
and the C6 has no PSRAM support (no `SPIRAM` entry in
[`soc/esp32c6/include/soc/soc_caps.h`](https://github.com/espressif/esp-idf/blob/master/components/soc/esp32c6/include/soc/soc_caps.h)).

**Our estimate (not an Espressif number):**

- Flash: Matter + BR + bridge app is likely 2–2.5 MB. Two OTA slots of that size plus the 640 KB
  RCP image does not fit in 4 MB. On 4 MB we would have to drop OTA (like the 4 MB BR config does)
  or drop on-board RCP updates. Neither is OK for a product. **Use 8 MB.**
- RAM: Espressif only ships Matter + BR with PSRAM. On a C6 (no PSRAM) it might boot, but heap
  would be thin with Wi-Fi + Thread + BLE commissioning + 30+ endpoints + many Matter sessions
  (Apple Home and Alexa both connected). Not proven by any Espressif example.

## 4. Options compared

| Option | Thread reliability | Flash/RAM | Effort | Verdict |
|---|---|---|---|---|
| One C6, 4 MB | "Unstable" per Espressif | Too tight, no OTA | Lowest parts cost | No |
| C6 host (8 MB) + H2 RCP | Good (own radio) | 8 MB OK; RAM tight, no PSRAM | Not an Espressif reference | Maybe, if we want to stay on C6 |
| **S3 host (8 MB + 2 MB PSRAM) + H2 RCP** | Good | Matches the esp-matter example | Espressif reference design and dev board exist | **Yes** |

## 5. Next steps

1. Buy one ESP Thread Border Router board (S3 + H2) and run the esp-matter `thread_border_router`
   example, then add bridged endpoints and check free heap with 30+ endpoints.
2. On the Hub PCB, copy the reference UART + reset + boot wiring so the S3 can update the H2.
3. Leave the PTA coexistence pins as unpopulated pads; Espressif ships them off by default.

## Sources

- ESP-IDF `ot_br` README — https://github.com/espressif/esp-idf/blob/master/examples/openthread/ot_br/README.md
- ESP-IDF `ot_rcp` example — https://github.com/espressif/esp-idf/tree/master/examples/openthread/ot_rcp
- ESP-IDF OpenThread Kconfig — https://github.com/espressif/esp-idf/blob/master/components/openthread/Kconfig
- ESP-IDF RF coexistence (ESP32-C6) — https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/coexist.html
- ESP Thread BR docs and hardware platforms — https://docs.espressif.com/projects/esp-thread-br/en/latest/hardware_platforms.html
- esp-thread-br basic border router example — https://github.com/espressif/esp-thread-br/tree/main/examples/basic_thread_border_router
- esp-matter `thread_border_router` example — https://github.com/espressif/esp-matter/tree/main/examples/thread_border_router
- esp-matter `zigbee_bridge` example — https://github.com/espressif/esp-matter/tree/main/examples/bridge_apps/zigbee_bridge
- esp-matter RAM and flash optimizations — https://github.com/espressif/esp-matter/blob/main/docs/en/optimizations.rst
- ESP32-C6 product page — https://www.espressif.com/en/products/socs/esp32-c6
