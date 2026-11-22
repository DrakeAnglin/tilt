# No cloud: local control, Matter, and parts a maker can print or buy

The project must work with no cloud service, no account and no server we host. Anyone should be able to build it with a 3D printer and off-the-shelf parts. So the app talks to controllers directly on the home network (per-phone keys), and away-from-home control and voice go through Matter (Apple Home, Alexa), which use free services the user already has. We rejected a hosted relay and user accounts: they would add running cost, a single point of failure and a barrier for makers.

Consequence: Matter behavior can only be tested against Apple Home and Alexa, the two ecosystems the owner has.
