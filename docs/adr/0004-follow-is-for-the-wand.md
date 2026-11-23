# Follow is for the wand only

"Blinds follow each other" means one thing: when you turn one blind's wand by hand, the controller sends its other blinds to the same tilt. A blind moved from the app, Apple Home, a Scene or a Schedule moves alone, with Follow on or off.

Before this, Follow also took the other blinds along when one blind was moved from the app or from its own Apple Home tile, and the app sent a "solo" flag to opt out in some places. That surprised the owner: picking one blind in the app moved all of them. The app and Apple Home can already move every blind at once (the room's buttons, one tile for all), so Follow only adds something for the wand, where there is no other way to say "all of them".

Consequences: the firmware's move rule (`firmware/blinds_matter/main/request.h movePicks`) follows only a hand move, the `solo` flag is gone from the app and the firmware, and the setting's footer in the app says the same thing. Don't widen Follow again without a way to tell a one-blind command from an all-blinds one.
