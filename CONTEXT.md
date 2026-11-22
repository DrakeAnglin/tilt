# Tilt

**Tilt** is the product: a battery-powered motor kit and app that adds smart control to existing cordless window blinds. Today it is Matter over Wi-Fi (Apple Home); Thread through a hub is a later goal. Today it tilts the slats; lifting is a planned part of the same product.

## Language

### Hardware

**Blind**:
One physical window covering with one tilt rod. It shows up as one tile in Apple Home. Two coverings in one window are two blinds.
_Avoid_: shade, window, slat set

**Tilter**:
The motor unit on one blind's tilt rod: gearbox, N20 motor, and sensor module with its RJ12 jack. A blind has exactly one.
_Avoid_: tilt motor, drive, TiltPod (the sensor module is a part of the tilter, not a separate thing)

**Lifter**:
The future motor unit on a blind's lift shaft. A blind may have one later.

**Controller**:
One box with one battery that is one Matter device and serves up to 3 blinds by cord. Grouped by cord reach, not by room.
_Avoid_: hub, base

**Port**:
A numbered slot (1-3) on a controller. A blind is bound to a port; the blind's name in the app stays the same if its cord moves to another port.

**Facing**:
The compass direction (north, south, east, west) a blind's window faces. It matters for sun, so it is the likely basis for grouping blinds. How blinds are grouped is not decided yet.

### Motion

**Tilt** (product):
The name of the whole system and its app, lifting included. Capital T. The slat angle is written lowercase, below.

**tilt** (slat angle):
Where the slats are, as one number from -100 (closed, slats down) through 0 (open, slats level) to +100 (closed, slats up): the percent of the way from open to closed, worked out from the Marks. It is not a slat angle in degrees (the controller never knows that). Same number in the app and the firmware; Matter gets it as "percent closed".
_Avoid_: position, slat angle, degrees

**Angle**:
Only the raw sensor reading (0-360 degrees of the AS5600), never what the user sees.

**Marks**:
The calibration points the user sets that map a raw sensor reading onto a position. tilt has three (closed one way, open, closed the other way). Lift will have two (raised and lowered), set by the user, with everything between worked out as 0-100% from the turn count.

**Lift**:
Raising and lowering a blind. In the domain but not built yet; high on the priority list. Today the product only tilts. Its position is a 0-100% **Lift position**.
_Avoid_: raise/lower (as a noun), "bonus"

**Window covering**:
How Matter sees a blind: one endpoint with two independent axes, tilt and Lift. A blind without a lifter reports tilt only. Today the firmware sends tilt over Matter's lift channel as "percent closed"; when real Lift arrives, tilt moves to Matter's tilt channel and Lift gets the lift channel, after testing how Apple Home and Alexa treat tilt.

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
Setting a blind's Marks.
_Avoid_: setup (a UI flow name only, not a domain term)

### Automation

**Scene**:
A named set of target tilts (and later Lifts) across any blinds.

**Schedule**:
A trigger (clock time, or sunrise/sunset plus an offset) that applies a Scene. Stored on each controller for its own blinds so it runs with the phone away. Gentle wake is a kind of Schedule (a slow ramp), not its own concept.

### Power

**Battery level**:
The controller's battery as an estimated percent (worked out from the resting cell voltage, not a fuel gauge). It belongs to the controller and is shown on each of its blinds because Matter needs it per blind.
_Avoid_: charge, power (for this)

**Low battery**:
Battery level under 20%. Warns in the app and in Apple Home; changes nothing else.

**Critical battery**:
Battery level under 10% while not charging. Schedules pause and it is reported; blinds still move when told, until the Motor cut-off.

**Motor cut-off**:
Resting cell voltage under 3.35 V (about 3% Battery level) while not charging. No motor runs at all, whoever asks, so the cell is never drained that low; moves come back once it charges.
_Avoid_: dead battery, empty

**Charge source**:
Where the cell is topped up from: USB-C (charge only) or the optional solar panel. The user sees only the Battery level, not a charge state. A cell that stays too hot to charge (about 45 C) surfaces only as a warning.

### Reachability

**Asleep**:
The controller dozes between moves to save the battery (Wi-Fi power save), so it often answers slowly. Normal; the user never sees it, and a command still works.

**Unreachable**:
The controller has not answered after a timeout. The app shows it with **Last seen**; Matter and the app use the same word.
_Avoid_: offline, asleep (to the user)
