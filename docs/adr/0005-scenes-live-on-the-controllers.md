# Scenes live on the controllers

A Scene made on one phone must show up on the other phones in the home, including a Guest on a different Apple account (issue #12). So Scenes are kept on the controllers, the same way Schedules are: each controller keeps its own blinds' part of a Scene (up to 16), under an id the app picks, with the Scene's name, icon and the time of its last edit. The app puts a Scene back together from every controller it has a key for, and keeps a copy on the phone for Siri, Shortcuts and controllers it cannot reach right now.

We rejected iCloud sharing (CloudKit). The app already uses CloudKit for join notices, but sharing data between different Apple accounts needs a share to be sent and accepted, and it would make Scenes depend on iCloud, which ADR 0001 keeps out of the basics. Anyone with a key can already reach the controllers, so that is who sees the Scenes, with no extra step.

When two phones edit the same Scene, the last save wins (the newest edit's name and icon; each controller keeps what it was last sent). A Scene with blinds on a controller that does not answer cannot be saved until it does, like a Schedule. A controller on firmware older than 2.3.0-dev29 keeps no Scenes: its part stays on the phone that made it.

Consequences: `/api/scenes` and `/api/scene` (firmware `scenes.h`, wire contract `wire.h`, fixture `test/wire/scenes.json`); a Guest may read and write Scenes (`logic.h permitRule`); the app's `Shared/ScenePlan.swift` does the splitting and joining. Scenes are not in the settings backup yet: a replaced controller starts with none.
