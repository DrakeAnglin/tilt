# Build guide

Most smart blinds need one device per blind. Tilt uses **one controller for up to three blinds**, and each blind
still has its own name in Apple Home and Alexa, its own Schedule and its own tilt.

- **One blind:** 1 tilter + 1 controller + 1 Tilt Hub.
- **Up to three blinds:** more tilters on the same controller.
- **More blinds:** another controller for each three. Still one Tilt Hub for the whole home.

[Part 1](#part-1-one-blind-start-to-finish) builds one blind from parts to Apple Home. [Part 2](#part-2-add-a-second-and-third-blind)
adds a second and third blind to the same controller. [Part 3](#part-3-add-more-blinds) adds more blinds with another
controller. Each step links to the detailed page.

## Part 1: one blind, start to finish

| Step | What | Detail |
|---|---|---|
| 1 | Measure your blind (if it is not like the reference blinds) | [measure-your-blinds.md](measure-your-blinds.md) |
| 2 | Order the parts | [BOM](../hardware/BOM.md) |
| 3 | Print the tilter, the box and the hub box | [tilter](../hardware/mechanical/stl/tilter/README.md#printed-parts), [box](controller-box.md), [hub box](hub-box.md) |
| 4 | Build the tilter: sensor module, then mechanical build | [sensor module](tilter-wiring.md), [mechanical build](tilter-assembly.md) |
| 5 | Flash the ESP32-C6 | [firmware](../firmware/README.md#first-flash-over-usb-on-the-bench) |
| 6 | Build the controller: PCB, then box | [PCB build](pcb-build.md), [box assembly](controller-box.md#assembly) |
| 7 | Build the Tilt Hub | below |
| 8 | Set up in the Tilt app | below |
| 9 | Add to Apple Home | below |
| 10 | Add to Alexa (if you have an Echo) | below |

### 1. Measure your blind
The tilter is drawn for the reference blinds: cordless blinds with a headrail about 55.5 × 36.5 mm inside, a 4 mm
square steel tilt rod 24 mm above the floor, and 110 mm free between the end cap and the first tilt drum
([headrail notes](../hardware/mechanical/README.md#the-headrail)). If yours differ, measure first; the CAD is
parametric.

### 2. Order the parts
Everything is in the [BOM](../hardware/BOM.md): per tilter, per controller and per hub, with
[how many you need](../hardware/BOM.md#how-many-do-i-need) for your number of blinds. Order the PCBs early
([how](../hardware/pcb/README.md#ordering)): they take the longest.

When parts arrive, do the [checks on arrival](../hardware/BOM.md#check-on-arrival), and switch every AS5600 to PWM
output with the bench tool ([as5600_setup](../firmware/README.md#as5600_setup-sensor-bench-tool)).

### 3. Print
- **Tilter:** one set of parts per blind, white PLA and white PETG. The Bambu Studio project puts PLA and PETG on
  their own plates. Only the tray lid needs support (under its gear shelf).
  [Parts and how they sit](../hardware/mechanical/stl/tilter/README.md#printed-parts).
- **Box:** tray and lid in white PLA, no supports ([controller box](controller-box.md)).
- **Hub box:** printed round the hub's ESP and its plug, so flash the hub first ([hub box](hub-box.md)).

### 4. Build the tilter
The tilter is two subassemblies, built in this order:
1. **Sensor module** (electronics): RJ12 breakout, DRV8833 motor driver and AS5600 angle sensor, wired together on
   the bench, then the meter checks ([sensor module](tilter-wiring.md)).

   ![tilter wiring](renders/tilter-wiring.png)

2. **Mechanical build** (printed parts): inserts, gearbox, motor, then the sensor module goes into the tray and the
   lid goes on ([mechanical build](tilter-assembly.md)). Leave it out of the blind until it is set up in the app.

### 5. Flash the ESP32-C6
Over its own USB-C, on the bench, before it goes on the PCB
([first flash](../firmware/README.md#first-flash-over-usb-on-the-bench)). In the box there is no room for a cable.
Later updates come from the app.

### 6. Build the controller
1. **PCB:** solder it part by part, lowest first, with the meter checks ([PCB build](pcb-build.md)). Step 11 makes
   the charger harness and the battery splice; step 13 plugs in the ESP.

   ![PCB done](renders/pcb-build-done.png)

2. **Charge the cell** before the ESP goes on: it needs the cell above about 3.8 V
   ([bench charging](pcb-build.md#charging-the-battery-on-the-bench)).
3. **Box:** inserts, PCB, cell, charger, lid, 3 screws, then **4 stick-on feet** in the corners of the floor
   ([box assembly](controller-box.md#assembly)).
4. Plug the tilter into port 1 with an RJ12 cord. Check the cord first: pin 1 to pin 1.
   Cord through a wall? Drill a 5/8 in hole and cover it with a printed plug on each side ([wall plug](wall-plug.md)).

### 7. Build the Tilt Hub
Every home needs one Tilt Hub. One hub serves every controller, and it stays plugged in: the controllers talk to it
over Thread and sleep, and Apple Home, Alexa and the app reach the blinds through it
([ADR 0003](adr/0003-thread-only-tilt-hub.md)). A mode with no hub may come later; it is not a build option today.

| Part | Notes |
|---|---|
| ESP32-C6 SuperMini, no pins soldered | Wi-Fi, Thread and Bluetooth on one chip |
| USB-C male-to-male adapter | the hub's plug ([BOM](../hardware/BOM.md#one-tilt-hub)) |
| Printed box | printed round the ESP and the adapter ([hub box](hub-box.md)) |
| A 5 V USB-C wall plug (1 A is plenty) | always on |
| A label | its setup label, printed in step 2 ([Print a setup label](#print-a-setup-label)) |

1. Copy `firmware/tilt_hub/main/secrets.h.example` to `secrets.h` and fill in the Wi-Fi network.
2. `tools/flash_hub.sh --usb <USB port>`. It gives the hub its own codes and writes its setup label: print it and
   stick it on the hub. (Plain `firmware/tilt_hub/build.sh -p <USB port> flash` still works: it prints a setup code
   to write on a label, and the app shows the Apple Home code.)
3. Print the box round the ESP and the adapter ([hub box](hub-box.md)). Flash first: the box has no way in afterward.
4. Plug the hub into the wall plug.

Later updates come over Wi-Fi ("Update Tilt Hub" on the hub page in the app). More:
[firmware/tilt_hub](../firmware/tilt_hub/README.md).

#### Print a setup label
`tools/flash_hub.sh --usb <USB port>` makes the hub's **Apple Home code** and its 8-digit **setup code** on the Mac,
writes them into the hub before its first start, and keeps them in `~/.tilt/devices/` on that Mac only. It writes the
label there as a PNG and a PDF (it prints the path): a QR and the 11 digits for Apple Home, the setup code for the
Tilt app, and the hub's short ID.

- **Once per Mac:** the label needs Pillow in the ESP-IDF Python the tool runs with:
  `~/.espressif/python_env/idf5.5_py3.9_env/bin/python -m pip install pillow qrcode`. Without it the flash and the
  record still work, and the tool prints the command for the label.
- The default label is a 1 x 1 in (25 x 25 mm) square at 300 dpi. Another size: `--label-size 40x20` (mm). A size
  too small for a QR a phone can read is refused before anything is flashed, with the smallest that works.
- Print it again any time, with the same Python:
  `~/.espressif/python_env/idf5.5_py3.9_env/bin/python tools/device_identity.py labels <short ID>` (or `--all`).
- If a flash stops partway (a cable, the port), run the same command again: the codes are saved on the Mac before
  anything is written to the hub, and the rerun finishes with the same codes. If the hub has meanwhile been given
  another code, the rerun asks for its short ID before it wipes anything. Unplug and replug the hub after a stop.
- A reflash or an update keeps the codes, so the label keeps working. A hub erased over USB gets the same codes back
  from this Mac. Only the developer flag `--new-identity` makes new ones, after you type the hub's short ID.
- A new hub can be scanned into Apple Home from its label in its first 15 minutes after power-on. Later, use **Add**
  in the app (step 9).
- A controller flashed with `tools/flash.sh --usb <USB port>` gets an ID label only: it has no code of its own.

### 8. Set up in the Tilt app
Install **Tilt** from the App Store on an iPhone or iPad on your home Wi-Fi.

1. **The hub first.** With the hub plugged in, the Blinds page shows **New Tilt Hub found**: tap **Connect** and type
   the code from its label. The first phone to connect is the hub's **Owner**.
2. Power the controller (plug in its cell). A new controller shows up in the app for 15 minutes after power-on.
3. The app says **New controller found**: tap **Set Up**, pick it under **New, over Bluetooth**, then **Connect to the
   Tilt Hub**. The first phone to set it up is its **Owner**.
4. Open the room, use the gear, pick the blind and tap **Set Up**. The app asks for three **Marks**: turn the wand
   until the slats are **closed up**, then **level (open)**, then **closed down**, and save each one. The blind then
   moves to Open by itself. That first move checks the motor's wiring: if the wires are the other way round, the
   controller turns it round and remembers it, so nothing needs rewiring. Then try each position.
5. In the room's settings, name the blind, and pick which way **"Close"** tilts the slats (up or down).
6. Put the tilter and the box in the headrail, push the rod through, and check the blind once more.

To share the blinds, the Owner invites the people they live with from the room's settings.

#### Schedules that follow the light
With a solar panel plugged in, a Schedule can start **When it gets dark** or **When it gets light** instead of at a
time. The controller reads the panel: when its input stays dark (or light) for a few minutes within 90 minutes of
sunset (or sunrise), the Schedule runs, once a day. Under the Schedule the app shows when it last ran and why.

- It is not a brightness meter. It only sees how much light reaches the panel, so put the panel where it sees the sky,
  not behind the slats.
- It needs a panel and a place (**Set Location for Sunrise and Sunset**). The two choices show up in the app about a
  day after the panel is first plugged in: the controller has to see one night and one day first.
- With no steady reading by the end of the 90 minutes (a USB cable plugged in at dusk, say), it runs then. The same
  goes when the panel already reads dark (or light) as the 90 minutes start, for example when it was unplugged at
  midday: it waits for a real change and otherwise runs at the end.
- Every controller the Schedule covers needs firmware that knows these choices. The app offers them only then.
- With no solar panel seen, it runs at sunset or sunrise, like a plain sun Schedule.

### 9. Add to Apple Home
Apple Home adds the Tilt Hub once, and every blind on every controller shows up through it. There is no code per
controller.

1. In Tilt, open **Settings > Tilt Hub**. Under **Integrations**, tap **Add** next to **Apple Home** (owners only).
2. Apple's add screen opens with the code filled in. When Home says **"Uncertified Accessory"**, choose
   **Add Anyway**. The hub accepts this for 15 minutes.
3. Or add it by hand: tap **Show the Apple Home code instead**, copy the code, open Home, tap **+**, **Add
   Accessory**, **More Options**, **My Accessory Isn't Shown Here**, and paste the code. From another iPhone or iPad,
   point its camera at the QR code in the sheet.

**Show each blind separately**, in each room's settings under **Apple Home**, chooses one tile per blind or one for
the room. It can take a minute to show in Home.

### 10. Add to Alexa
With a Tilt Hub, the blinds can also be in Alexa, so an Echo opens and closes them by voice. Apple Home keeps working:
Matter lets the hub be in both. It needs an Echo with Matter on the same Wi-Fi as the hub: Amazon lists which ones
([Matter on Alexa](https://developer.amazon.com/docs/alexaplus/smarthome/matter-support)). Alexa opens, closes and sets
a percent; check the battery in Tilt or Apple Home (Amazon lists no battery for blinds).
1. In Tilt, open **Settings > Tilt Hub**. Under **Integrations**, tap **Add** next to **Alexa** (owners only).
2. Tilt shows a one-time code, good for 15 minutes. Tap **Open Alexa**: it copies the code and opens the Alexa app.
3. In Alexa: **Devices**, **+**, **Add Device**, **Other**, **Matter**, say **Yes** to the Matter logo, then
   **Try numeric code** and paste the code. If Alexa says the device is not Matter certified, continue.
4. Alexa finds one blind per tile (as in Apple Home). Put each in a room.
5. Say, for example, **"Alexa, open the living room blinds"** or **"Alexa, close the living room blinds"**.

Names come from Tilt: rename a blind in Tilt, not in Alexa. To take the hub out of Alexa, remove it in the Alexa app.
A code adds one Alexa home. After it is used or 15 minutes pass, tap again for a new one.

## Part 2: add a second and third blind
The controller has three ports, so up to three blinds within a cord's reach (3 m) need no new controller and no new
hub.

1. Build another tilter: print its parts, wire it and assemble it ([step 3](#3-print), [step 4](#4-build-the-tilter)).
2. Plug its cord into a free port on the controller. Check the cord first: pin 1 to pin 1.
3. In the app, open the room, use the gear, pick the new blind and tap **Set Up**: the same Marks as
   [step 8](#8-set-up-in-the-tilt-app). Name it in the room's settings.
4. Put it in its headrail and check it once more. It shows up in Apple Home and Alexa by itself, through the hub.

## Part 3: add more blinds
Add another controller when the controller's three ports are full, or when a blind is farther away than a cord
reaches. Controllers are grouped by cord reach, not by room. The home keeps its one Tilt Hub.

1. Build the tilters ([step 4](#4-build-the-tilter)) and another controller ([step 5](#5-flash-the-esp32-c6),
   [step 6](#6-build-the-controller)).
2. Power it and set it up in the app the same way ([step 8](#8-set-up-in-the-tilt-app), from item 2): **Set Up**, **Connect
   to the Tilt Hub**, then Setup for each blind.
3. Its blinds show up in Apple Home and Alexa by themselves, through the hub. No new code.

## If something is wrong
- PCB readings: [PCB build, "If something reads wrong"](pcb-build.md#if-something-reads-wrong).
- A blind moves the wrong way: nothing to rewire. The motor leads can go either way round; on its first moves the
  controller sees which way the angle changes, turns the motor the other way if needed, and remembers it.
- A blind is slow, stalls, or overshoots: check its motor's speed and pick another to suit the blind
  ([motor speed](../hardware/BOM.md#motor-speed), [check on arrival](../hardware/BOM.md#check-on-arrival)).
- Open problems and planned work: [GitHub issues](https://github.com/DrakeAnglin/tilt/issues).
