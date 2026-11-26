---
name: work-issue
description: Take one GitHub issue, or one plain request, all the way to main on its own: worktree branch, build, tests, pull request, CI, independent review, merge gate, merge or hand to a human. Use when asked to fix, build or change something in this repo, or to work an issue by number.
---

Follow `docs/agents/workflow.md` step by step, start to finish, without stopping to ask. Read it now.

What each step leans on:

- **Build**: the `tdd` skill where a test has a place; `diagnosing-bugs` for a bug that is not obvious.
- **Local check**: `tools/agent/check.sh`.
- **Review**: start the `pr-reviewer` agent with a prompt that is only `Review pull request <n>`. Do not tell it what you did or what you think: it must come to it fresh.
- **Findings**: answer each must-fix on the pull request, fixed or disagree with a reason ("Answer every must-fix" in the workflow doc). Then the reviewer looks again, the same one continued or a fresh one. Merge only when you both agree.
- **Gate**: start the `merge-gate` agent with only `Gate pull request <n>`.
- **No `pr-reviewer` or `merge-gate` agent type?** That happens when the session started outside this repo (for example in the folder above it). Start a `general-purpose` agent on Sonnet instead, with only: `Read <worktree>/.claude/agents/pr-reviewer.md (or merge-gate.md) and do what it says for pull request <n> in DrakeAnglin/tilt. Work in <worktree>.` Never skip the review because the agent type is missing.
- **Conflicts**: yours to fix, by "Merge conflicts" in the workflow doc. Check before review, before merging, and after merging.
- **Merge**: `tools/agent/merge_pr.sh <n>`. If it refuses, it says why. Fix that, or hand over. Never go around it.

Never end a turn while waiting for CI, a build or a lock: run it in the background so it wakes you ("Waiting" in the workflow doc).

Done means one of two things, and you say which:

1. Merged: the pull request link, what changed, and any issues you filed on the way.
2. Waiting for the owner: the pull request link, the `needs-human` reason, and what to look at. Send the push notification first ("Notifying the owner" in the workflow doc).

Anything else ("CI is running, I'll merge once it passes") is not done. Keep going.
