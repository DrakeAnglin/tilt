# Controller PCB

KiCad project goes here (`blinds-controller.kicad_pro`). Not started. Breadboard prototype first.

## v1 block list
- USB-C receptacle (power only), 5.1 kΩ CC pull-downs, TVS on VBUS, polyfuse
- ≥ 470 µF bulk on motor rail, ferrite split to logic rail
- 3.3 V regulator (≥ 600 mA, e.g. AP2112K-3.3 or a small buck)
- ESP32-S3-WROOM-1-N8 + BOOT/RESET buttons + native USB data option (for flashing via the same USB-C)
- 2× DRV8833 with current-sense resistors (value set from measured stall current)
- 3–4× RJ12 6P6C motor jacks with ESD arrays, encoder pull-ups + RC filters
- User button, status RGB LED (WS2812-mini or 3 discrete)
- Optional footprints: CH224K USB-PD trigger (9 V), barrel jack, 4th/5th/6th motor port

## Bench prototype BOM
| Qty | Part |
|---|---|
| 1 | ESP32-S3-DevKitC-1 (N8R2/N8R8) |
| 2 | DRV8833 breakout |
| 2 | N20 6 V 40 RPM with encoder (MECCANIXITY B0F8NGRYGS) |
| 1 | USB-C 5 V 3 A adapter + USB-C breakout |
| 1 | 470 µF 10 V electrolytic |
| — | Dupont wires, luggage scale, phone SPL meter app |
