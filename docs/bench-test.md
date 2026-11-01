# Bench test: one tilter on a breadboard

One port of the controller, wired on a breadboard exactly as the dev board will be (same pins as
[controller-v4.md](controller-v4.md#dev-board)), so the firmware carries straight over. The tilter is wired directly
(no RJ12 cord) for the first runs. Sketch: [firmware/bench_test](../firmware/bench_test/bench_test.ino).

## Parts
ESP32-C6 SuperMini, 1 DRV8833 (J2 pad cut), 1 AS5600 board, the tilter with its N20, an 18650 cell (motor supply),
USB-C cable to the computer (ESP power + serial), 1 kΩ + 100 nF (angle filter), 10 µF (driver supply), a breadboard
and jumper wires, the USB power meter or a multimeter.

The SuperMini's two pin rows are 0.6" apart: it straddles the breadboard's centre gap like a wide DIP chip.

## Wiring
| From | To | Note |
|---|---|---|
| ESP **USB-C** | computer | powers the ESP, serial monitor at 115200 |
| ESP **GND** | breadboard GND rail | |
| 18650 **+** (red, XH lead) | DRV8833 **VCC** | motor supply: the real 3.0–4.2 V |
| 18650 **−** (black) | GND rail | grounds must be shared |
| 10 µF | DRV8833 VCC ↔ GND, at the driver | |
| DRV8833 **GND** | GND rail | |
| ESP **GPIO 18** | DRV8833 **IN1** | PWM |
| ESP **GPIO 19** | DRV8833 **IN2** | PWM |
| ESP **GPIO 4** | DRV8833 **ULT** and AS5600 **VCC** | EN: wakes the driver and powers the sensor |
| DRV8833 **OUT1 / OUT2** | N20 tabs | swap them if "forward" turns the wrong way |
| AS5600 **GND** | GND rail | |
| AS5600 **GPO** | AS5600 **VCC** | analog output mode |
| AS5600 **OUT** | 1 kΩ → ESP **GPIO 0** | |
| 100 nF | ESP GPIO 0 ↔ GND | angle filter |

Same nets as RJ12 port 1: VBAT = DRV VCC, IN1 = 18, IN2 = 19, EN = 4, ANGLE = 0, GND.

**Never** power the ESP from the 18650 through its 5V pin while USB is plugged in (no diode on the board's 5V pin).

## Tests
1. **Angle:** EN on (`e`), turn the wand by hand: the angle should change smoothly over the whole travel, without
   jumping or wrapping past 0/360°. Note the readings at both ends.
2. **Unloaded:** rod out. `f` / `r` at full duty: smooth running in both directions. Note the current (meter in the
   battery lead).
3. **Loaded:** rod in, blind hanging. `f` / `r`. Watch what fails, if it does:
   - **motor hums but doesn't turn** (current high, near stall): real torque shortage, or something binds under load;
   - **motor spins, blind doesn't move:** the pinion slips on the D-shaft, or the helical mesh skips (pinion pushed
     out of mesh: motor or lid flexing);
   - **turns in one direction, not the other:** the worm's thrust steps binding (one direction loads one step);
   - **works mid-travel, stalls near closed:** the slats' squeeze at the ends; measure the wand torque there.
4. **Hand check under load:** with the motor removed, turn the pinion's D-bore with a 3 mm shaft or hex key. If the
   blind turns easily from there, the drivetrain is fine and the motor side (supply, slip, mounting) is the problem.
5. **Sleep current:** EN off (`x`), motor stopped: driver + sensor draw should be ≈ 0 (multimeter µA range).

Record: supply voltage under load, current running and at stall, where in the travel it struggles, direction.
