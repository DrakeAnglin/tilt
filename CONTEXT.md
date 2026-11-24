# Tilt

**Tilt** is the product: a battery-powered motor kit and app that adds smart control to existing cordless window blinds. The controllers talk Thread to a Tilt Hub, which shows the blinds in Apple Home. It only tilts the slats; it never raises or lowers a blind ([ADR 0002](docs/adr/0002-no-lift.md)).

## Language

### Hardware

**Blind**:
One physical window covering with one tilt rod. It shows up as one tile in Apple Home. Two coverings in one window are two blinds.
_Avoid_: shade, window, slat set

**Tilter**:
The motor unit on one blind's tilt rod: gearbox, N20 motor, and sensor module with its RJ12 jack. A blind has exactly one.
_Avoid_: tilt motor, drive, TiltPod (the sensor module is a part of the tilter, not a separate thing)

**Controller**:
One box with one battery that serves up to 3 blinds by cord. Grouped by cord reach, not by room. It talks Thread to the Tilt Hub; the hub shows its blinds in Matter.
_Avoid_: hub, base

**Tilt Hub**:
The always-on, wall-powered box that controllers talk to over Thread, so they can sleep. Apple Home, Alexa and the app talk to the Tilt Hub, which passes commands on and answers from what the controllers last told it.
_Avoid_: hub (alone, when someone else's Thread border router could be meant), bridge, base station

**Port**:
A numbered slot (1-3) on a controller. A blind is bound to a port; the blind's name in the app stays the same if its cord moves to another port.

**Facing**:
The compass direction (north, south, east, west) a blind's window faces. It matters for sun, so it is the likely basis for grouping blinds. How blinds are grouped is not decided yet.

### Motion

**Tilt** (product):
The name of the whole system and its app. Capital T. The slat angle is written lowercase, below.

**tilt** (slat angle):
Where the slats are, as one number from -100 (closed, slats down) through 0 (open, slats level) to +100 (closed, slats up): the percent of the way from open to closed, worked out from the Marks. It is not a slat angle in degrees (the controller never knows that). Same number in the app and the firmware; Matter gets it as "percent closed".
_Avoid_: position, slat angle, degrees

**Angle**:
Only the raw sensor reading (0-360 degrees of the AS5600), never what the user sees.

**Marks**:
The calibration points the user sets that map a raw sensor reading onto a position. tilt has three (closed one way, open, closed the other way).
An internal word (code, docs, the developer page): the app never shows it. To the user, setting them is **Setup** ("Setup required", "Start Setup").

**Manual move**:
The user moving a blind by hand: turning the wand. It always keeps working with the tilter fitted, and the app shows the new tilt at the next wake, with no re-homing.
_Avoid_: override, hand mode

**Follow**:
A setting on a controller: when one of its blinds gets a Manual move, the others go to the same tilt. Only a Manual move is followed; a blind moved from the app, Apple Home, a Scene or a Schedule moves alone ([ADR 0004](docs/adr/0004-follow-is-for-the-wand.md)).
_Avoid_: sync, solo

**Window covering**:
How Matter sees a blind: one endpoint. The firmware sends tilt over Matter's lift channel as "percent closed" (Matter's word; Tilt never raises a blind).

**Target**:
The tilt last commanded.

**Current tilt**:
The tilt the sensor reads now. It differs from the Target after a stall stop or a wand turn, and it always wins: the app and Matter report Current tilt.
_Avoid_: state, position, stuck

### People and access

**Owner**:
The first phone to pair with a controller. Can invite, revoke and reset.

**Guest**:
A phone invited by the Owner. Can move blinds but cannot manage access.

**Matter user**:
Someone using the blinds through Apple Home or Alexa. Never holds an app key, so is neither Owner nor Guest.

### Joining the system

**Commissioning**:
Adding a controller to a Matter fabric (Apple Home, Alexa).

**Pairing**:
A phone gaining its own secret key for one controller, over the app's secured channel.

**Calibration**:
Setting a blind's Marks. In the app this is **Setup**, always one word ("Setup required", "Start Setup", "Redo Setup"); never "set up" or "Marks".

### Automation

**Scene**:
A named set of target tilts across any blinds. Kept on the controllers (each holds its own blinds' part), so every phone with a key, Owner or Guest, sees and edits the same Scenes ([ADR 0006](docs/adr/0006-scenes-live-on-the-controllers.md)). A phone runs it by moving each blind.

**Schedule**:
A trigger (clock time, or sunrise/sunset plus an offset) that applies a Scene. Stored on each controller for its own blinds so it runs with the phone away. Gentle wake is a kind of Schedule (a slow ramp), not its own concept.

### Power

**Battery level**:
The controller's battery as an estimated percent (worked out from the resting cell voltage, not a fuel gauge). It belongs to the controller and is shown on each of its blinds because Matter needs it per blind.
_Avoid_: charge, power (for this)

**Low battery**:
Battery level under 20%. Warns in the app and in Apple Home; changes nothing else.

**Critical battery**:
Battery level under 10%. Schedules pause and it is reported; blinds still move when told, until the Motor cut-off.

**Motor cut-off**:
Resting cell voltage under 3.35 V (about 3% Battery level), plugged in or not (a solar panel in weak light shows a voltage but charges nothing). No motor runs at all, whoever asks, so the cell is never drained that low; moves come back once it charges.
_Avoid_: dead battery, empty

**Charge source**:
Where the cell is topped up from: USB-C (charge only) or the optional solar panel. The user sees only the Battery level, not a charge state. A cell that stays too hot to charge (about 45 C) surfaces only as a warning.

### Reachability

**Asleep**:
The controller sleeps between check-ins with the Tilt Hub (about once a second) to save the battery, so a command waits up to a second. Normal; the user never sees it, and a command still works.

**Unreachable**:
The controller has not answered after a timeout. The app shows it with **Last seen**; Matter and the app use the same word.
_Avoid_: offline, asleep (to the user)
