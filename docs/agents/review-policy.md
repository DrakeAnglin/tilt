# Review policy

How a pull request is judged before it goes into `main`. The `pr-reviewer` and `merge-gate` agents follow this. `tools/agent/merge_pr.sh` enforces the hard rules, whatever the agents say.

## Doors

Every pull request gets one door. The door is about **what merging does**, not about which files are touched.

Merging puts code on `main`. It does not put it on a controller, a hub or a phone: firmware gets there only through a release, and the app only through an App Store or TestFlight build. The owner does both. So until the next release, reverting the commit puts everything back.

**Two-way door**: reverting the commit puts everything back. Almost every change: app screens, firmware logic, the update path, stored data, the wire format, tools, docs.

**One-way door**: merging itself does something a revert does not undo. In this repo:

- Anything published by the merge: a workflow that publishes on merge, a change in `tilt-site` (a merge there goes live), a firmware release, an App Store build, a deleted GitHub release, branch or issue.
- Deleting a person's data or settings.

A one-way door needs a named reason: what happens on merge that a revert cannot take back. "It touches `update.h`" is not one. If you cannot name it, it is two-way.

### Bench check before the next release

Some two-way changes are only safe to release once they have run on real hardware. Merging them is fine; releasing them untested is not. The reviewer adds the `bench-check` label and writes what to check in its review. These are:

- The update path: `ota.h`, `FirmwareUpdate.swift`, the hub's update code (`update.h` is human-only, above). A bad update can leave a controller that cannot be updated again.
- Stored data changes shape: what a controller or hub keeps in flash (`store.h`), what the app keeps (`Store.swift`).
- The wire format: `wire.h`, `api.h`, `Api.swift`, the hub link, the `test/wire` fixture, when devices or apps already in use would stop understanding each other.
- Firmware that only runs on the ESP (adapters, tasks, timers) and has no Mac test.

Before a firmware release, the owner works through the merged pull requests with `bench-check` since the last release (`gh pr list --state merged --label bench-check`), then takes the label off.

## Who merges

**The agent merges** when all of these are true:

1. Two-way door.
2. CI is green on the commit that was reviewed.
3. The review found nothing that must be fixed, or the fixes are in and reviewed again.
4. Changed behavior has a test, or the change is docs or comments only. Firmware that only runs on the ESP counts as tested when the author built it (`firmware/blinds_matter/build.sh`, `firmware/tilt_hub/build.sh`) on the reviewed commit, said so in Evidence, and the pull request has `bench-check`.
5. The change does what the issue asked and nothing else.
6. Under 600 changed lines, not counting tests (`test/`, `Tests/`, `test_*.py`).
7. No human-only path is touched (below).

Doubt about a rule is not a reason to hand over. Say what you are unsure about. Hand over only when a rule is clearly not met, or a person can judge something here that the tests and the review cannot.

**A finding is the author's to fix, never a reason to hand over.** A bug, a missing test, a missing build or something the issue asked for and did not get goes back to the author as must-fix, and the author fixes it and asks for review again, up to ten rounds. The owner gets a pull request only for what a person must judge: a one-way door, a human-only path, a change too big to vouch for, or ten rounds without a clean result.

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
- `fwkey.h`, `sec.h`, `tilt_crypto.h`, `lock.h`, `update.h` (it holds the firmware signature check), `Secure.swift`: keys, pairing, signatures and who may do what. A hole here lets someone in, and a bench check does not show a hole.
- `*.entitlements`, `Info.plist`, `PrivacyInfo.xcprivacy`: what Apple reviews.
- `docs/adr/`, `docs/requirements.md`: decisions are the owner's.
- `docs/agents/review-policy.md`, `.claude/agents/`, `.claude/settings.json`, `tools/agent/`, `.githooks/`, `.github/workflows/`: what decides a merge. That is this policy, the reviewer and the gate, the merge script, the guard and CI. An agent does not approve that for itself.

Everything else about how agents work is open to them: `docs/agents/workflow.md` and the other agent docs, `.claude/skills/`, `CLAUDE.md`, the pull request template.

The script's list is in `tools/agent/merge_pr.sh`, with the why and the what-to-confirm for each line. Keep the two the same.
