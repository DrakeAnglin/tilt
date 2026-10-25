# System architecture

```
 Wall outlet
     │  (certified 5 V / 3 A USB-C adapter: the only thing touching mains)
     ▼
┌──────────────────────── Controller PCB ────────────────────────┐
│ USB-C in ─► bulk caps ─┬─► 3.3 V buck/LDO ─► ESP32-S3 module    │
│                        │                    (Wi-Fi + BLE)      │
│                        └─► 2× DRV8833 dual H-bridge (4 ch)     │
│                                 │   │   │   │(spare/lift)      │
│ Button + status LED           M1  M2  M3  M4                   │
└────────────────────────────────┼───┼───┼───────────────────────┘
                                 │   │   │  6-wire cables (≤3 m)
                              N20 N20 N20  motor + Hall encoder, in each headrail
```

## Microcontroller: ESP32-S3 (module: ESP32-S3-WROOM-1-**N8**, 8 MB flash)
- **Hardware pulse counters (PCNT, 4 units):** one per encoder, counting quadrature in hardware with zero CPU load. 3 tilt motors + 1 spare. (The ESP32-**C3 has no PCNT**, so avoid it. The classic ESP32 has 8 units if we ever need 6 motors for tilt + lift.)
- **8 MB flash** because Matter firmware is large, and OTA needs two app slots. (4 MB forces the "Huge APP, no OTA" partition, which conflicts with requirement C-6.)
- Native USB for flashing and logs, so no USB-UART chip is needed.
- Dev phase: **ESP32-S3-DevKitC-1 (N8R2 or N8R8)**. Anything "ESP32 Arduino" works with this.

## Motor driver: 2× TI DRV8833
- 2.7–10.8 V, ~1.5 A RMS per channel: far above an N20's needs; runs straight from the 5 V rail.
- **Built-in current limiting** via a sense resistor on each bridge: a hardware torque limit that protects the N20 gearbox even if firmware hangs. Set it just below the measured stall current.
- PWM at 20–25 kHz (inaudible), slow-decay (brake) mode for smooth low-speed control and idle damping.
- JLCPCB stocks it, so it suits one-order assembly.
- Alternative: TB6612FNG (similar, no built-in current limit).

## Power: single 5 V USB-C
- **Why 5 V:** USB-C adapters are everywhere, certified, and cheap. The ESP32 and DRV8833 both run from it directly. A 6 V N20 at 5 V just runs ~17% slower and quieter.
- Budget: ESP32 peak ~0.5 A + 3 motors × stall ~0.5 A = ~2 A worst case → **5 V/3 A adapter**. USB-C CC pull-downs (5.1 kΩ) so any USB-C charger supplies 5 V.
- Brownout protection: ≥ 470 µF bulk on the motor rail, LC/ferrite split between motor and logic rails, firmware staggers motor starts by ~100 ms.
- **Future option:** a footprint for a USB-PD trigger chip (CH224K) to request 9 V if we ever move to 9 V/12 V motors for very heavy blinds or lift.
- Long cable runs to the outlet: USB-C cables up to 3 m are fine at 2 A. Beyond that, put a 5 V barrel-jack adapter footprint as an alternative input.

## Motor cabling
- 6 conductors per motor: M+, M−, encoder VCC (3.3 V), GND, A, B.
- Suggested connector: **RJ12 (6P6C)**: cheap, locking, pre-made cables in any length, 26 AWG is fine for < 0.5 A at 3 m. Alternative: JST-XH 6-pin + custom cable.
- Encoder lines over 3 m: 10 kΩ pull-ups at the controller, RC filter (~100 Ω/1 nF), ESD diodes (TVS array) on every connector pin. PCNT glitch filter enabled.
- A tiny breakout board at the motor end (or direct solder + heat shrink) turns the N20's 6-pin header into the RJ12 jack.

## Firmware (overview, details later in `firmware/`)
- **Framework:** Arduino-ESP32 core 3.x via PlatformIO/Arduino IDE. It now includes a `MatterWindowCovering` class with lift + tilt and covering types such as `BLIND_TILT_ONLY` and `BLIND_LIFT_AND_TILT`. If Arduino Matter hits limits, fall back to ESP-IDF + esp-matter (same chip, more control).
- **Motion control per motor:** target position in encoder counts → trapezoidal speed profile → PI speed loop on encoder rate → stop + brake at target.
- **Stall detection:** commanded PWM high but encoder rate ≈ 0 for > 150 ms → stop. Doubles as **homing**: drive gently into the fully closed end stop, zero the count there.
- **Position persistence:** write position to NVS (flash) on every stop. Re-home opportunistically whenever a move targets a hard end.
- **Matter endpoints:** one Window Covering endpoint per enabled motor (3 named blinds in Alexa/Home).
- **Local API:** HTTP + WebSocket JSON API for the setup app; mDNS name `blinds-<id>.local`.
- **OTA:** dual-partition, from the setup app (upload or GitHub release URL).

## Smart home: Matter over Wi-Fi
One protocol covers **Apple Home, Alexa, Google Home, SmartThings, and Home Assistant**, works locally, and needs no cloud
account or skill.

- Commissioning: scan the Matter QR code in Apple Home or the Alexa app. That also provisions Wi-Fi over BLE.
- Multi-admin: the same blind can be in Apple Home and Alexa simultaneously.
- **Risk to verify early:** ecosystems differ in how they show *tilt*. Apple Home has tilt controls. Alexa's handling of Matter
  tilt is unclear. **Mitigation:** a firmware setting to expose tilt-only blinds as a simple *lift* position (0% = closed,
  100% = slats open/horizontal). Every ecosystem handles that, and "Alexa, open/close/set to 50%" just works.
  Switch to true lift + tilt when the lift bonus lands.
- Fallback for Alexa if Matter disappoints: Sinric Pro (free tier, Alexa skill with blinds support) or a custom Alexa Smart Home skill (more work, needs a cloud endpoint).
- Matter requires an Echo/HomePod/Apple TV/Google Nest as a hub for remote access. Local control works without it.

## Setup app
1. **Phase 1: web app hosted by the controller** (served from flash). Works on any phone/PC, no App Store, no $99/yr Apple fee. Covers naming, calibration wizard, sliders, schedules, OTA, logs.
2. **Phase 2 (optional): native Flutter app** that discovers all controllers via mDNS and shows the whole house. Mostly a wrapper around the same local API.

Provisioning paths: Matter commissioning (preferred) → or BLE "Improv Wi-Fi" from the web flasher → or a SoftAP captive portal fallback.

## Calibration flow (per motor)
1. Jog buttons, confirm direction ("does this tilt slats **down**?"), and flip it if not.
2. Drive to slats-down-closed → firmware detects stall → sets **0**.
3. Drive to slats-up-closed → stall → sets **max**. Firmware backs off a few % from each stall point so normal moves never hit the hard stop.
4. Pick what "Close" means: down (privacy, default) or up (blocks more sun).
5. "Open" = slats horizontal = midpoint (adjustable).
