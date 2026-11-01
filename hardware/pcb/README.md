# Controller PCB

KiCad project goes here. **Not started:** the soldered perfboard dev board ([controller-v4.md](../../docs/controller-v4.md))
comes first; the PCB replaces it once the bench and install tests pass, with the same box outline and port positions.

## Block list (from the dev board)
- ESP32-C6 module (C6-MINI or the SuperMini's chip on board), BOOT/RESET pads, USB D+/D− to the USB-C for flashing
- MCP73871 charger with power path; inputs USB-C (5.1 kΩ CC pull-downs) and solar (6.2 V clamp), each through a Schottky
- 18650 holder or JST-XH, 10 kΩ NTC on the cell to THERM
- Battery-voltage divider (1 MΩ / 1 MΩ + 100 nF) to an ADC pin, input-power (USB/solar) divider 1 MΩ / 1 MΩ to an ADC pin (or route the MCP73871 STAT1 pin on the PCB)
- 3 × RJ12 6P6C ports: VBAT (with a polyfuse per port), IN1, IN2, EN, ANGLE (1 kΩ + 100 nF to the ADC), GND; ESD array on each
- Bulk capacitor on VBAT, 10 µF at the ESP's supply
- No motor drivers: the DRV8833s are in the tilters

## Tilter board (later)
A small board for the sensor module could combine the AS5600, the DRV8833 and the RJ12 jack, replacing three
breakouts and their wiring.
