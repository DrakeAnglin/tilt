# Agent workflow

How one agent takes one issue from request to `main`, without a person in the loop unless the review asks for one. The `/work-issue` skill runs these steps.

## Rules

- **One issue, one branch, one worktree, one pull request.** Never work in the main checkout: other agents and the owner are using it.
- **Nothing goes to `main` except through a pull request.** No direct pushes. Merging is done by `tools/agent/merge_pr.sh` or by the owner on GitHub, never by `gh pr merge`.
- **Stay on the issue.** Something else found on the way becomes a new issue, not part of this change.
- **Do not stop to ask** unless the issue cannot be understood, or the review policy says a human decides.

## Steps

1. **Pick up the issue.** `gh issue view <n> --comments`. No issue yet? Make one first from the request. Claim it: `gh issue edit <n> --add-assignee @me`.
2. **Branch in a worktree.** If the session is not already in its own worktree:
   `git fetch origin && git worktree add .claude/worktrees/issue-<n> -b issue-<n>-<short-name> origin/main`, then work there.
3. **Build it.** Read `CONTEXT.md` and the ADRs for the area. Write the test first where there is a place for one (`/tdd`). Small commits.
4. **Check locally.** `tools/agent/check.sh` must pass.
5. **Open the pull request.** `git push -u origin <branch>`, then `gh pr create`. Write the body in the template's shape (Matt Pocock's `pr` skill, when installed, is the guide): `Closes #<n>`, summary, evidence, door, blast radius, what could go wrong. Last, turn on the app's watch for the pull request (Auto-fix: `set_monitor` with `auto_fix`), so this session is woken on a conflict, a red CI or a comment. If that tool is not there or is not approved, go on without it.
6. **Wait for CI.** `gh pr checks <pr> --watch`. Red? Fix it, push, wait again.
7. **Review, by someone else.** Start the `pr-reviewer` agent with only the pull request number. It has no part of this session's context. It posts its own summary, evidence, merge danger and findings as a comment on the pull request.
8. **Fix what must be fixed**, push, and have `pr-reviewer` look again. Three rounds at most; the merge script counts them, and after that it goes to a human.
9. **Gate.** Start the `merge-gate` agent with the pull request number. It reads the review and the policy and decides: merge, or human.
10. **Merge or hand over.**
    - Merge: `tools/agent/merge_pr.sh <pr>`. It checks the rules again and squash-merges.
    - Human: the `needs-human` label, always with a comment that says why: a TL;DR first, notes after. Then notify the owner (below), tell them the TL;DR and stop. Do not merge.
11. **Clean up.** The issue closes itself through `Closes #<n>`. Worktrees clean themselves: `tools/agent/clean_worktrees.sh` removes every worktree under `.claude/worktrees/` whose pull request is merged or closed, with its local branch and build folders. It runs after every merge (`merge_pr.sh`) and at the start of every session, and keeps anything that could be lost (uncommitted changes, commits not in the pull request, no pull request, detached HEAD). When the owner merges or closes your pull request on GitHub, the next session clears your worktree. Run it with `--dry-run` to see what it would do.

## Merge conflicts

Other pull requests merge while yours is open, and yours can stop merging cleanly. That is yours to notice and fix; it is not a reason to stop.

**When to look** (`gh pr view <pr> --json mergeable --jq .mergeable`; on `UNKNOWN`, wait a few seconds and ask again):

- before asking for review, and before merging (`merge_pr.sh` refuses a pull request that does not merge cleanly)
- when the app wakes you about your pull request
- right after you merge anything: `gh pr list --json number,mergeable,headRefName`. Your merge may have put other open pull requests into conflict.

**How to resolve**, in the pull request's worktree:

1. `git fetch origin && git merge origin/main`. Merge, never rebase or force push: the review is tied to commits.
2. Fix each conflict so that what both sides meant is kept. Two new sections in the same place: keep both. Read the other pull request to see what it meant (`git log origin/main -- <file>`).
3. `tools/agent/check.sh`, commit the merge, push.
4. Have `pr-reviewer` look again: the review is for the commit before. Then the gate. Each review counts toward the three-round limit, so a pull request that keeps conflicting ends up with the owner.

**Someone else's pull request** that your merge put into conflict: if its worktree is on this Mac under `.claude/worktrees/` and has nothing uncommitted, resolve it there the same way and leave a comment on the pull request saying what you did and that it needs review again. Otherwise leave a comment and do not touch the branch.

**Do not guess.** When the two sides really disagree (the same line, two meanings; a file one side deleted and the other changed), stop: `needs-human` with a comment that says why, shows both sides, and names what the owner should confirm. Then notify the owner.

## Notifying the owner

The owner is often away from the Mac. Send one push notification with the `PushNotification` tool (load it with ToolSearch if it is not loaded) when:

- a pull request is handed over: `<repo>#<pr> needs you: <the why, in one sentence>`
- you are stuck and cannot go on without the owner: say what you need.

One line, under 200 characters, the thing to act on first. One per hand-over. None for a clean merge or for progress: a push that was not needed costs the owner's attention.

## Things found on the way

A bug, a smell, a missing test that is not this issue: file it and move on.

`gh issue create --label needs-triage --label <area> --title "..." --body "Found while working on #<n>. ..."`

Say what was seen, where (file and line), and how to see it again. Do not fix it in this branch.

## Labels

| Label | Meaning |
| --- | --- |
| `ready-for-agent` | The owner says an agent may pick this issue up on its own |
| `needs-triage` | Filed by an agent; the owner has not looked yet |
| `two-way-door` / `one-way-door` | The reviewer's door for a pull request |
| `auto-merge-ok` | The gate says the agent may merge |
| `needs-human` | The owner reviews and merges this one |

The review rules are in [review-policy.md](review-policy.md).

## The site

The public website is its own repo, `DrakeAnglin/tilt-site`, checked out next to this one: `../tilt-site` from the main checkout, `../../../../tilt-site` from a worktree here. It has the same workflow with its own rules: it is public, and a merge there goes live.

A change to the site, such as a new help page or a link to a release that is already out, is its own issue and its own pull request in that repo. Publishing a release is not a site change: it is one-way and the owner's, by the policy here.

1. File the issue there: `gh issue create -R DrakeAnglin/tilt-site ...`. That repo is public, so nothing private goes in it. Naming the issue here as `DrakeAnglin/tilt#<n>` is fine; quoting from it is not.
2. Work it in a worktree of that repo, by that repo's `docs/agents/workflow.md` and `docs/agents/review-policy.md`. If that repo's `main` does not have those files yet, do not merge or push to `main` there: push the branch, open the pull request, add `needs-human` with a comment saying why, and tell the owner.
3. Link the two pull requests to each other in their summaries.

If the site change only makes sense once the change here is in `main`, merge here first.
