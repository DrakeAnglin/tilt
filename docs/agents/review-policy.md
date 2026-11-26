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
3. The author and the reviewer agree: no must-fix finding is left, and none is in dispute (below).
4. Changed behavior has a test, or the change is docs or comments only. Firmware that only runs on the ESP counts as tested when the author built it (`firmware/blinds_matter/build.sh`, `firmware/tilt_hub/build.sh`) on the reviewed commit, said so in Evidence, and the pull request has `bench-check`.
5. The change does what the issue asked and nothing else.
6. No human-only path is touched (below).

Doubt about a rule is not a reason to hand over. Say what you are unsure about and decide.

**These are never a reason to hand over, and never a Human Review item**, however they are worded:

- **A choice the issue left open.** The author makes it, by `docs/requirements.md`, the ADRs and `CONTEXT.md`, and writes it in the pull request under **Choices made**. The reviewer checks each choice against those docs; a wrong or unwritten choice is must-fix. If no doc settles it and it changes what a person can do (who may do what, what a guest sees), the author asks on the issue before building, not on the pull request after.
- **"Confirm the rule is what you want" or "accept this trade-off".** A rule in the code (a role, a limit, a timeout) is pinned by a test, and the test is the check. Reading the code is the reviewer's job.
- **A hardware run.** That is staging.

### Two agents, until they agree

Every pull request is reviewed by a second agent with none of the author's context: started fresh with only the pull request number, or that same reviewer continued. Never the author, and never a fork of the author's session. It cannot pick up the author's assumptions.

**A finding is the author's to answer, never a reason to hand over.** The reviewer posts its findings on the pull request, numbered (`M1`, `M2` for must-fix; a finding keeps its number in later rounds). The author answers each one on the pull request, in one comment per round:

- **Fixed**, with the commit; or
- **Disagree**, with the reason: what the reviewer missed, with file and line, a test or a log.

The reviewer then looks again. For each answer it either drops the finding (and says so) or holds it and says why the reason does not hold. Back and forth, up to ten rounds.

- **They agree** (nothing to fix, nothing in dispute): the gate, then merge.
- **They cannot agree**: the reviewer still holds a finding after the author has argued it twice. The reviewer counts these as `stuck` and the pull request goes to the owner, with both sides written down in the review.
- **Ten rounds** without agreement: the owner.

The owner gets a pull request only for what a person must judge: a large blast radius, a test-script change beyond adding tests, two agents that cannot agree, or ten rounds.

`needs-human` sticks while its reason holds: a pull request with it is never merged by an agent. When the reason is gone (the gate said human for an older commit, CI was red or never ran, an old copy of the merge script added it, a repo move carried it over), `tools/agent/clear_stale_label.sh` takes it off. It asks the rules on main, with the label ignored, whether a person is still needed, and leaves a comment when it removes the label. That script is the only way an agent takes the label off. The owner keeps a pull request for themselves with a comment that starts with `/hold`. Red, unfinished or missing CI is always "not yet", never a reason for a person. The door labels do not stick: the reviewer moves them when the door changes.

**A human merges** in every other case, and the pull request always says why. See below.

## What goes on the pull request

Three things, each with the same parts, so the owner can read any one of them alone:

| Who | Where | What |
| --- | --- | --- |
| Author | The pull request body (the template; Matt Pocock's `pr` skill has the same shape) | Summary, Evidence, Merge Danger: door, blast radius (size and area), what could go wrong |
| `pr-reviewer` | A comment | Its own TL;DR, Summary, Evidence and Merge Danger, written from the diff, then the findings |
| `merge-gate` | A comment | TL;DR of the verdict, door, blast radius, what could go wrong, then the six rules as notes |

**`needs-human` never stands alone.** It always comes with two things: **why** a person is needed (which reason in "Who merges"), and **what to confirm** (three checks at most). A check is something only a person can do, such as agree to a change in the merge rules. Never "every role is what you want", "you accept that ...", "run this on hardware" or "read this function". The gate writes them in its comment and in the pull request body under `## Human Review`. `merge_pr.sh` writes them in a comment when it is the one that refuses.

## Human-only paths

There is no size limit and no list of risky files. Keys, pairing, the update path, release tools, hardware, Apple settings, ADRs and these rules themselves all merge like any other change once they are tested and the two agents agree. The review is what has to be good: the reviewer reads every line of those, and a bug there is must-fix, for the author. Only one path goes to the owner:

- `tools/firmware_tests.sh`, `tools/app_tests.sh`: how the tests run. Adding a test to the run is fine and an agent may merge it: every removed line is a comment, and every added line is a comment, a compile (`c++`, `cc`), a test run (`"$OUT/<name>"`), a `python3 <file>.py` generator or the `$OUT` cleanup trap, with no `; & | $( ) { } < > ! \`, and no open quote. `tools/agent/only_adds_tests.awk` decides. Anything else is a human's. The reviewer still reads the diff: the check narrows what can change, it does not prove a test is good.
**What decides a merge** (`docs/agents/review-policy.md`, `.claude/agents/`, `.claude/settings.json`, `tools/agent/`, `.githooks/`, `.github/workflows/`) merges by agreement like anything else. The reviewer holds one more line there: a change that lets more through (a check dropped or loosened, a path taken off a list, fewer rounds, a weaker reviewer) must be something the owner asked for, quoted in the issue. If it is not, that is must-fix.

The script's check is in `tools/agent/merge_pr.sh`, with the why and the what-to-confirm. Keep the two the same.
