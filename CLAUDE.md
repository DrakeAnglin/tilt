## Agent skills

### Issue tracker

Issues and specs are GitHub Issues on `DrakeAnglin/tilt` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## How work gets into main

Every change goes: issue, own branch in its own worktree, pull request, CI, independent review, merge gate. Nothing is pushed to `main`. To do a task start to finish, use the `/work-issue` skill. See `docs/agents/workflow.md` and `docs/agents/review-policy.md`.

- Tests: `tools/agent/check.sh` (the same tests run in GitHub on every pull request).
- Review: the `pr-reviewer` agent, started fresh with only the pull request number. It names the door: one-way or two-way.
- Merge: `tools/agent/merge_pr.sh <pr>`, after the `merge-gate` agent says merge. Otherwise the `needs-human` label, and the owner merges.
- Something unrelated found on the way: a new issue with `needs-triage`, not a fix in this branch.
