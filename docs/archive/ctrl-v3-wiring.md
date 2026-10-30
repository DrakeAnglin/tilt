| From | To | Note |
|---|---|---|
| Port 1 (room side) pin 1 VBAT | charger LOAD | motor supply, ~250 mA per move |
| Port 1 (room side) pin 2 IN1 | ESP GPIO 18 | PWM |
| Port 1 (room side) pin 3 GND | GND | |
| Port 1 (room side) pin 4 ANGLE | R ADC (1 k) -> ESP GPIO 0, C ADC 100 n to GND | AS5600 OUT |
| Port 1 (room side) pin 5 EN | ESP GPIO 4 | powers the AS5600 and wakes the DRV8833 |
| Port 1 (room side) pin 6 IN2 | ESP GPIO 19 | PWM |
| Port 2 (middle) pin 1 VBAT | charger LOAD | motor supply, ~250 mA per move |
| Port 2 (middle) pin 2 IN1 | ESP GPIO 20 | PWM |
| Port 2 (middle) pin 3 GND | GND | |
| Port 2 (middle) pin 4 ANGLE | R ADC (1 k) -> ESP GPIO 1, C ADC 100 n to GND | AS5600 OUT |
| Port 2 (middle) pin 5 EN | ESP GPIO 5 | powers the AS5600 and wakes the DRV8833 |
| Port 2 (middle) pin 6 IN2 | ESP GPIO 14 | PWM |
| Port 3 (back side) pin 1 VBAT | charger LOAD | motor supply, ~250 mA per move |
| Port 3 (back side) pin 2 IN1 | ESP GPIO TX16 | PWM |
| Port 3 (back side) pin 3 GND | GND | |
| Port 3 (back side) pin 4 ANGLE | R ADC (1 k) -> ESP GPIO 2, C ADC 100 n to GND | AS5600 OUT |
| Port 3 (back side) pin 5 EN | ESP GPIO 6 | powers the AS5600 and wakes the DRV8833 |
| Port 3 (back side) pin 6 IN2 | ESP GPIO RX17 | PWM |
| USB-C VBUS | D1 (band to charger) -> charger PWR | charge-only port |
| Solar + (ZH pigtail) | D2 (band to charger) -> charger PWR | |
| 6.2 V zener | across charger PWR / GND (band to PWR) | solar over-voltage clamp |
| USB-C GND, solar -, charger GND | GND | |
| Battery pins B+ / B- | charger BATT + / - | cell's XH plug pushes on |
| 10 k NTC (taped to the cell) | charger THERM (replaces its fixed resistor) | stops charging when hot |
| Charger LOAD | D3 (band to ESP) -> ESP 5V; C bulk + to LOAD | |
| Charger LOAD | R div top 1 M -> ESP GPIO 3 -> R div bot 1 M -> GND; C div 100 n GPIO 3 to GND | battery voltage |
| Charger STAT | ESP GPIO 7, R stat 10 k to 3V3 | charging / charged |
| C 10 u | ESP 5V to GND | |
