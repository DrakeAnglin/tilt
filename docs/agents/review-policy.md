# Review policy

How a pull request is judged before it goes into `main`. The `pr-reviewer` and `merge-gate` agents follow this. `tools/agent/merge_pr.sh` enforces the hard rules, whatever the agents say.

## Doors

Every pull request gets one door.

**Two-way door**: reverting the commit puts everything back. Most changes: app screens, logic with tests, tools, docs.

**One-way door**: once it ships, a revert does not undo it. In this repo:

- Stored data changes shape: what a controller or hub keeps in flash (`store.h`), what the app keeps (`Store.swift`), with no way to read the old shape.
- The wire format changes (`wire.h`, `api.h`, `Api.swift`, the `test/wire` fixture) so that devices or apps already in use stop understanding each other.
- The update path: `update.h`, `fwkey.h`, `FirmwareUpdate.swift`, `partitions.csv`, `tools/release_firmware.py`. A bad update can leave a controller that cannot be updated again.
- Keys, pairing and signing: `sec.h`, `tilt_crypto.h`, `lock.h`, `Secure.swift`. Anything that makes a paired device forget who it trusts, or lets in someone it should not.
- Anything published: a firmware release, an App Store build, a deleted GitHub release, branch or issue.
- Deleting a person's data or settings.

When unsure, call it one-way.

## Who merges

**The agent merges** when all of these are true:

1. Two-way door.
2. CI is green on the commit that was reviewed.
3. The review found nothing that must be fixed, or the fixes are in and reviewed again.
4. Changed behavior has a test, or the change is docs or comments only.
5. The change does what the issue asked and nothing else.
6. Under 400 changed lines.
7. No human-only path is touched (below).

`needs-human` and `one-way-door` stick: a pull request with either is never merged by an agent, and only the owner takes them off.

**A human merges** in every other case, and the pull request always says why. See below.

## What goes on the pull request

Three things, each with the same parts, so the owner can read any one of them alone:

| Who | Where | What |
| --- | --- | --- |
| Author | The pull request body (the template; Matt Pocock's `pr` skill has the same shape) | Summary, Evidence, Merge Danger: door, blast radius, what could go wrong |
| `pr-reviewer` | A comment | Its own TL;DR, Summary, Evidence and Merge Danger, written from the diff, then the findings |
| `merge-gate` | A comment | TL;DR of the verdict, door, blast radius, what could go wrong, then the seven rules as notes |

**`needs-human` never stands alone.** It always comes with two things: **why** a person is needed (what a person can judge here that tests and agents cannot), and **what to confirm** (three checks at most, each naming a file). The gate writes them in its comment and in the pull request body under `## Human Review`. `merge_pr.sh` writes them in a comment when it is the one that refuses.

## Human-only paths

Tests cannot vouch for these, or they are the rules themselves:

- `hardware/`, `tools/fusion_*.py`, `tools/bambu*.py`, `tools/orient.py`: printed parts and the PCB. Someone has to look at the part.
- `tools/release_firmware.py`, `tools/flash*.sh`, `partitions.csv`, `sdkconfig*`: release and flashing.
- `tools/firmware_tests.sh`, `tools/app_tests.sh`: what the tests run. Adding tests is fine; changing how they run is not.
- `fwkey.h`, `sec.h`, `tilt_crypto.h`, `lock.h`, `update.h`, `Secure.swift`, `FirmwareUpdate.swift`, `*.entitlements`, `Info.plist`, `PrivacyInfo.xcprivacy`: security, updates and what Apple reviews.
- `docs/adr/`, `docs/requirements.md`: decisions are the owner's.
- `.github/`, `.claude/`, `.githooks/`, `tools/agent/`, `docs/agents/`, `CLAUDE.md`: the factory itself. An agent does not change its own rules.

The script's list is in `tools/agent/merge_pr.sh`, with the why and the what-to-confirm for each line. Keep the two the same.
