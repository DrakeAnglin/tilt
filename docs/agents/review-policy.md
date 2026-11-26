# Review policy

How a pull request is judged before it goes into `main`. The `pr-reviewer` and `merge-gate` agents follow this. `tools/agent/merge_pr.sh` enforces the hard rules, whatever the agents say.

## Doors

Every pull request gets one door, and only one: the `two-way-door` label or the `one-way-door` label, never both. When a new review changes the door, the reviewer takes the old label off. The door is about **what merging does**, not about which files are touched.

The door says how easy it is to go back. It does not decide the merge on its own: the **blast radius** and the **review** do (below). A one-way door with a small blast radius and a clean review is merged like any other change.

Merging puts code on `main`. It does not put it on a controller, a hub or a phone: firmware gets there only through a release, and the app only through an App Store or TestFlight build. The owner does both. So until the next release, reverting the commit puts everything back.

**Two-way door**: reverting the commit puts everything back. Almost every change: app screens, firmware logic, the update path, stored data, the wire format, tools, docs.

**One-way door**: merging itself does something a revert does not undo. In this repo:

- Anything published by the merge: a workflow that publishes on merge, a change in `site/` (a merge goes live on the website), a firmware release, an App Store build, a deleted GitHub release, branch or issue.
- Deleting a person's data or settings.

A one-way door needs a named reason: what happens on merge that a revert cannot take back. "It touches `update.h`" is not one. If you cannot name it, it is two-way.

## Blast radius

Who is hurt, and how badly, if the change is wrong after merge. The reviewer gives one of three sizes and the area (`docs`, `tools`, `app`, `firmware`, `hardware`, `site`, `release`), for example `small (app)`.

- **small**: nobody outside this repo sees it on merge. A revert or a follow-up pull request fixes it. Almost every change, because merging does not reach any device or phone.
- **medium**: people can see it on merge, but a follow-up fixes it soon and nothing lasting is lost. A help page on the site, a deleted stale branch or issue.
- **large**: on merge it reaches controllers, hubs or phones in use, a person's data or settings, keys or accounts, or the harm stays after a fix. A firmware or app release, a workflow that publishes to devices, deleting someone's data.

Judge by what really happens on merge, not by the worst file name in the diff. If you cannot name who is hurt, it is small.

### Bench check: part of staging a release

A bench check is not part of review. The code is made good first: a clean review, tests, and the firmware builds. A pull request is never flashed to hardware to check it before merge, and a bench check is never a reason to hand a pull request to the owner or to list it under Human Review.

Some changes are only safe to release once they have run on real hardware. The reviewer adds the `bench-check` label and writes in its review what to check. The label only puts the pull request on the staging list. These are:

- The update path: `ota.h`, `update.h`, `FirmwareUpdate.swift`, the hub's update code. A bad update can leave a controller that cannot be updated again.
- Stored data changes shape: what a controller or hub keeps in flash (`store.h`), what the app keeps (`Store.swift`).
- The wire format: `wire.h`, `api.h`, `Api.swift`, the hub link, the `test/wire` fixture, when devices or apps already in use would stop understanding each other.
- Firmware that only runs on the ESP (adapters, tasks, timers) and has no Mac test.

**Staging**, before a firmware or app release: build one release candidate from `main`, put it on the bench controllers, hub and phone, and run the checks from every merged pull request with `bench-check` since the last release (`gh pr list --state merged --label bench-check`). A failed check is a new issue and a fix through the normal flow. When all pass, take the labels off and release.

## Who merges

**The agent merges** when all of these are true:

1. Blast radius is small or medium. The door, one-way or two-way, is not a rule here.
2. CI is green on the commit that was reviewed.
3. The review found nothing that must be fixed, or the fixes are in and reviewed again.
4. Changed behavior has a test, or the change is docs or comments only. Firmware that only runs on the ESP counts as tested when the author built it (`firmware/blinds_matter/build.sh`, `firmware/tilt_hub/build.sh`) on the reviewed commit, said so in Evidence, and the pull request has `bench-check`.
5. The change does what the issue asked and nothing else.
6. No human-only path is touched (below).

Doubt about a rule is not a reason to hand over. Say what you are unsure about. Hand over only when a rule is clearly not met, or a person can judge something here that the tests and the review cannot.

**A finding is the author's to fix, never a reason to hand over.** A bug, a missing test, a missing build or something the issue asked for and did not get goes back to the author as must-fix, and the author fixes it and asks for review again, up to ten rounds. The owner gets a pull request only for what a person must judge: a large blast radius, a human-only path, or ten rounds without a clean result.

`needs-human` sticks: a pull request with it is never merged by an agent, and only the owner takes it off. The door labels do not stick: the reviewer moves them when the door changes.

**A human merges** in every other case, and the pull request always says why. See below.

## What goes on the pull request

Three things, each with the same parts, so the owner can read any one of them alone:

| Who | Where | What |
| --- | --- | --- |
| Author | The pull request body (the template; Matt Pocock's `pr` skill has the same shape) | Summary, Evidence, Merge Danger: door, blast radius (size and area), what could go wrong |
| `pr-reviewer` | A comment | Its own TL;DR, Summary, Evidence and Merge Danger, written from the diff, then the findings |
| `merge-gate` | A comment | TL;DR of the verdict, door, blast radius, what could go wrong, then the six rules as notes |

**`needs-human` never stands alone.** It always comes with two things: **why** a person is needed (what a person can judge here that tests and agents cannot), and **what to confirm** (three checks at most, each naming a file). The gate writes them in its comment and in the pull request body under `## Human Review`. `merge_pr.sh` writes them in a comment when it is the one that refuses.

## Human-only paths

There is no size limit and no list of risky files. Keys, pairing, the update path, release tools, hardware, Apple settings and ADRs all merge like any other change once they are tested and the review is clean. The review is what has to be good: the reviewer reads every line of those, and a bug there is must-fix, for the author. Only two things go to the owner:

- `tools/firmware_tests.sh`, `tools/app_tests.sh`: how the tests run. Adding a test to the run is fine and an agent may merge it: every removed line is a comment, and no added line can hide a failure (any `||`, `set +` anything, `exit 0` or a bare `exit`, `return`, `exec`, a test run in the background with `&`, a `trap` that exits). `tools/agent/only_adds_tests.awk` decides. Anything else is a human's.
- `docs/agents/review-policy.md`, `.claude/agents/`, `.claude/settings.json`, `tools/agent/`, `.githooks/`, `.github/workflows/`: what decides a merge. That is this policy, the reviewer and the gate, the merge script, the guard and CI. An agent does not approve that for itself.

Everything else about how agents work is open to them: `docs/agents/workflow.md` and the other agent docs, `.claude/skills/`, `CLAUDE.md`, the pull request template.

The script's list is in `tools/agent/merge_pr.sh`, with the why and the what-to-confirm for each line. Keep the two the same.
