| From | To | Note |
|---|---|---|
| Port 1 (room side) pin 1 VBAT | charger LOAD | motor supply |
| Port 1 (room side) pin 2 IN1 | ESP GPIO 18 | PWM |
| Port 1 (room side) pin 3 GND | GND | |
| Port 1 (room side) pin 4 ANGLE | R ADC 1 k -> ESP GPIO 0; C ADC 100 n to GND | AS5600 OUT |
| Port 1 (room side) pin 5 EN | ESP GPIO 4 | AS5600 power + DRV8833 sleep |
| Port 1 (room side) pin 6 IN2 | ESP GPIO 19 | PWM |
| Port 2 (middle) pin 1 VBAT | charger LOAD | motor supply |
| Port 2 (middle) pin 2 IN1 | ESP GPIO 20 | PWM |
| Port 2 (middle) pin 3 GND | GND | |
| Port 2 (middle) pin 4 ANGLE | R ADC 1 k -> ESP GPIO 1; C ADC 100 n to GND | AS5600 OUT |
| Port 2 (middle) pin 5 EN | ESP GPIO 5 | AS5600 power + DRV8833 sleep |
| Port 2 (middle) pin 6 IN2 | ESP GPIO 14 | PWM |
| Port 3 (back side) pin 1 VBAT | charger LOAD | motor supply |
| Port 3 (back side) pin 2 IN1 | ESP GPIO TX16 | PWM |
| Port 3 (back side) pin 3 GND | GND | |
| Port 3 (back side) pin 4 ANGLE | R ADC 1 k -> ESP GPIO 2; C ADC 100 n to GND | AS5600 OUT |
| Port 3 (back side) pin 5 EN | ESP GPIO 6 | AS5600 power + DRV8833 sleep |
| Port 3 (back side) pin 6 IN2 | ESP GPIO RX17 | PWM |
| USB-C VBUS / GND (2 leads) | USB pads V+ / V- -> D1 (band to charger) -> charger PWR | charge only |
| Solar + / - (ZH pigtail through end wall B) | Solar pads S+ / S- -> D2 (band to charger) -> charger PWR | |
| 6.2 V zener | across charger PWR / GND, band to PWR | solar over-voltage clamp |
| Battery pins B+ / B- | charger BATT + / - | the cell's XH plug pushes on |
| 10 k NTC taped to the cell | charger THERM (replaces its fixed resistor) | stops charging when hot |
| Charger LOAD | D3 (band to ESP) -> ESP 5V; C bulk + on LOAD | |
| Charger LOAD | R div top 1 M -> GPIO 3 -> R div bot 1 M -> GND; C div 100 n on GPIO 3 | battery voltage |
| Charger STAT | GPIO 7, R stat 10 k to 3V3 | charging / charged |
| C 10 u | ESP 5V to GND | |
