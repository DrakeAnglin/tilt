---
name: architecture-scan
description: The daily architecture scan. A Fable agent looks for deepening opportunities the way the improve-codebase-architecture skill does, a second Fable agent tries to argue each one down, and only the ones that hold up go into the backlog as issues (two a day at most). Hands-off. Use when the scheduled task fires, or when asked to run the scan once.
---

You are the **scan runner**. Two Fable agents do the thinking, each in its own context: the **scout** finds candidates, the **skeptic** tries to kill them. You file what is left. Each Fable agent reads the code on its own: the skeptic never sees why the scout liked a candidate. Most days that is nothing, and that is a good result: the backlog is for work that is really needed, not for ideas.

`gh` is at `~/.local/bin/gh` when it is not on `PATH`. Never edit files in the main checkout, and never open a pull request: this scan only files issues.

## The bar

An issue goes in only when all of these are true:

1. **Real friction, shown.** Evidence from this repo, not taste: a bug that came back, a fix that needed edits in many files, a test that could not be written through the current interface, the same rule written twice and drifting. With commits, issues or file and line.
2. **Where work is happening.** The files changed in the last 60 days (`git log --since=60.days --name-only origin/main`), or work that is open now and will land there. A messy corner nobody touches is not worth a change.
3. **Passes the deletion test** (`codebase-design` skill): deepening it concentrates complexity, it does not just move it.
4. **Not already decided or filed.** No ADR in `docs/adr/` settles it the other way, and no issue, open or closed, covers it (search titles and bodies with `gh issue list --state all --search`). A closed `wontfix` is a no. Already open: add the new evidence there as a comment, do not file again.
5. **Worth the change now.** Say what gets easier or safer after, in one sentence a person would agree with.

Two new issues a day at most. When more than two pass, file the two strongest, and the rest wait for another day.

## 1. Scout (Fable)

`git fetch origin`. Start a `general-purpose` agent with model `fable`:

> You scan DrakeAnglin/tilt for architecture friction, read-only. Work in /Users/drakeanglin/Documents/automated-blinds/blinds but read the code at `origin/main` (`git show`, `git log`, `git grep origin/main`); change no files. Read `~/.claude/plugins/marketplaces/mattpocock/skills/engineering/improve-codebase-architecture/SKILL.md` and follow its step 1 (Explore) only: scope by the hot spots in `git log`, load the `codebase-design` skill and use its words exactly. This repo's glossary is `CONTEXT.md`, not `GLOSSARY.md`; the ADRs are in `docs/adr/`. You cannot start sub-agents: walk the code yourself. Skip the HTML report and the grilling: nobody is there to answer.
>
> Then hold every candidate to this bar: <paste "The bar" above>.
>
> Reply with at most five candidates that you think pass, strongest first. For each: a title (plain, says what changes), the files, the friction with its evidence, the change in plain words, what gets easier after, the deletion test result, the ADRs and issues you checked. Zero candidates is a fine answer: say what you looked at.

Zero candidates: go to step 4.

## 2. Skeptic (Fable)

Start a second, fresh `general-purpose` agent with model `fable`. Give it the candidates, not the scout's reasoning about why they are good:

> You decide whether each of these candidates belongs in the backlog of DrakeAnglin/tilt. Read the code yourself at `origin/main`, read-only. Your job is to argue each one down. Reject it when: the evidence does not hold when you look; the area is not changing; the change would only move complexity; an ADR or an issue (open or closed) already covers it; or the work costs more than it saves. Keep it only when you cannot argue it down. <paste "The bar" above>. <the candidates>. Reply for each one: keep or reject, and one line why.

## 3. File

For each kept candidate, two at most, file an issue the hourly loop can take on its own:

```
gh issue create --label backlog --label "P3 low" --label <area> --title "<title>" --body-file <file>
```

`P2 medium` instead when the friction already caused a bug. The body: **Goal**, **Why now** (the evidence), **What changes**, **Done when** (tests that prove it, behavior unchanged), and a last line `Found by the daily architecture scan.` No `needs-triage`, no `needs-human`. Nothing private: the repo is public.

## 4. Log

One comment on issue #133, "Architecture scan log" (closed on purpose, so no loop picks it; it holds the scan's history), always, even on a day with nothing filed:

```
## Scan <date>
Looked at: <areas>
Filed: #<n>, #<n> | none
Not filed: <candidate>: <why, one line> (scout or skeptic)
```

Read the last ten log comments by `DrakeAnglin` (`gh issue view 133 --comments`) at the start of step 1 and pass them to the scout: a candidate rejected before comes back only with new evidence.

No push notification. Say in one line what was filed, or "Nothing filed".
