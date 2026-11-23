# No Lift: Tilt only tilts, it never raises or lowers a blind

We looked at adding Lift (a motor that raises and lowers the blind) in issue #10 and dropped it for good. On the owner's cordless blinds the lift is a sealed spring-balance module (two cord spools geared to constant-force spring drums), 21.75 mm tall, screwed to the headrail floor and pinched side to side, so it can't move. With its cover on there is no room to mesh a gear with a spool. Its only drive input is a soft plastic 1/8 in hex in the middle, which strips when turned the raising way, and the 4 mm square tilt rod runs straight over that hex with only a paper-thin gap. A motor would mean designing a whole new lift module, with a lot of testing and a real risk of ruining a set of blinds. Not worth it.

Don't reopen this unless the blinds change (for example a lift with a reachable shaft). Consequences: the controller has no lifter port, and the firmware keeps sending tilt on Matter's lift channel.
