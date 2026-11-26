#!/bin/sh
# Merge a pull request, but only when the rules in docs/agents/review-policy.md allow an agent to.
#   tools/agent/merge_pr.sh <pr>            check, then squash-merge
#   tools/agent/merge_pr.sh <pr> --check    check only
# "Not yet" (CI running, no review) just stops. "Not allowed" also gets the needs-human label,
# and the owner merges on GitHub.
set -eu
PR=${1:?usage: merge_pr.sh <pr> [--check]}
MODE=${2:-}
[ -z "$MODE" ] || [ "$MODE" = --check ] || { echo "usage: merge_pr.sh <pr> [--check]" >&2; exit 2; }

# Always judge by the rules on main, never by an older copy in this branch's worktree: an old copy once
# added needs-human by rules that had already changed. Unpack main's tools/agent/ and run that copy.
if [ -z "${MERGE_PR_FROM_MAIN:-}" ]; then
  git fetch -q origin main 2>/dev/null || true
  T=$(mktemp -d)
  if git archive origin/main tools/agent 2>/dev/null | tar -x -C "$T" 2>/dev/null && [ -f "$T/tools/agent/merge_pr.sh" ]; then
    RC=0; MERGE_PR_FROM_MAIN=1 sh "$T/tools/agent/merge_pr.sh" "$@" || RC=$?
    rm -rf "$T"; exit $RC
  fi
  rm -rf "$T"; echo "merge_pr: could not read main's copy; using this one." >&2
fi

# One merge at a time, across every worktree on this Mac: each merge moves main, and the next pull request
# is checked against the new main. A lock older than 15 minutes is stale.
if [ "$MODE" != --check ]; then
  QLOCK="$(git rev-parse --path-format=absolute --git-common-dir)/merge-queue.lock"; WAITED=0
  until mkdir "$QLOCK" 2>/dev/null; do
    if [ -n "$(find "$QLOCK" -maxdepth 0 -mmin +15 2>/dev/null)" ]; then rm -rf "$QLOCK"; continue; fi
    [ "$WAITED" -lt 900 ] || { echo "merge_pr: another merge has held the queue for 15 minutes; try again." >&2; exit 1; }
    sleep 15; WAITED=$((WAITED + 15))
  done
  trap 'rm -rf "$QLOCK"' EXIT INT TERM
fi

MAX_REVIEWS=10

J=$(gh pr view "$PR" --json number,state,isDraft,isCrossRepository,baseRefName,headRefName,headRefOid,mergeable,additions,deletions,labels,comments)
get() { printf '%s' "$J" | jq -r "$1"; }
SHA=$(get .headRefOid)
NO=""      # not allowed: a human decides
WAIT=""    # not yet: try again later
no() { NO="$NO
- $1"; }
wait_for() { WAIT="$WAIT
- $1"; }

[ "$(get .state)" = OPEN ] || { echo "#$PR is not open ($(get .state)). Nothing to do."; exit 1; }
[ "$(get .isDraft)" = false ] || wait_for "pull request is a draft"
[ "$(get .baseRefName)" = main ] || no "base is not main"
[ "$(get .isCrossRepository)" = false ] || no "comes from a fork"
case "$(get .mergeable)" in
  MERGEABLE) ;;
  UNKNOWN) wait_for "GitHub has not worked out yet whether it merges cleanly" ;;
  *) wait_for "does not merge cleanly into main: bring the branch up to date" ;;
esac

# A label set by hand, or by the gate, wins over everything else.
# IGNORE_NEEDS_HUMAN=1 (with --check only) asks: would the rules still send this to a human without the label?
# tools/agent/clear_stale_label.sh uses it to take off a label whose reason is gone.
if [ -z "${IGNORE_NEEDS_HUMAN:-}" ] || [ "$MODE" != --check ]; then
  [ "$(get '[.labels[].name] | index("needs-human")')" = null ] || no "has the needs-human label"
fi

# Every changed file (and the old name of a renamed one), not only the first page.
FILE_JSON=$(gh api "repos/{owner}/{repo}/pulls/$PR/files" --paginate --jq '.[] | {f: .filename, p: (.previous_filename // ""), n: (.additions + .deletions)}')
FILES=$(printf '%s\n' "$FILE_JSON" | jq -r '.f, (select(.p != "") | .p)')
[ -n "$FILES" ] || no "could not list the changed files"
# Who may merge is the review's call, not a list of files: a tested change that the author and an
# independent reviewer agree on, with a small or medium blast radius, merges, whatever it touches.
# That includes these rules themselves. Only a change to how the tests run goes to the owner,
# because it could hide a failure.
# The test scripts: adding a test to the run is fine; changing how the tests run is not.
# only_adds_tests.awk says which: removed lines are only comments, and no added line can hide a failure.
AWK="$(dirname "$0")/only_adds_tests.awk"
for F in $(printf '%s\n' "$FILES" | grep -E '^tools/(firmware_tests|app_tests)\.sh$' | sort -u || true); do
  PATCH=$(gh api "repos/{owner}/{repo}/pulls/$PR/files" --paginate --jq ".[] | select(.filename == \"$F\" and .status == \"modified\") | .patch // \"\"")
  printf '%s\n' "$PATCH" | awk -f "$AWK" ||
    no "How the tests run changed, not only which tests run. Confirm: no test was dropped or weakened. Files: $F"
done

# CI: the 'ci' check must have passed, and nothing may be failing or still running.
CHECKS=$(gh pr checks "$PR" --json name,bucket 2>/dev/null) || true
printf '%s' "$CHECKS" | jq -e 'type == "array"' >/dev/null 2>&1 || CHECKS='[]'
if [ "$(printf '%s' "$CHECKS" | jq -r '[.[] | select(.bucket == "fail" or .bucket == "cancel")] | length')" != 0 ]; then
  wait_for "CI is red: fix it"
elif [ "$(printf '%s' "$CHECKS" | jq -r '[.[] | select(.name == "ci" and .bucket == "pass")] | length')" = 0 ] ||
     [ "$(printf '%s' "$CHECKS" | jq -r '[.[] | select(.bucket != "pass" and .bucket != "skipping")] | length')" != 0 ]; then
  wait_for "CI has not finished"
fi

# The review and the gate must both be for this exact commit.
# Count only what the account running this posted: a comment from anyone else is not a review or a verdict.
ME=$(gh api user --jq .login)
markers() { get "[.comments[] | select(.author.login == \"$ME\") | .body | capture(\"<!-- $1 (?<m>[^>]*) -->\"; \"g\") | .m]"; }
field() { printf '%s' "$1" | tr ' ' '\n' | sed -n "s/^$2=//p"; }
REVIEW=$(markers factory-review | jq -r 'last // ""')
GATE=$(markers factory-gate | jq -r 'last // ""')
# A look again after a clean merge from main (round=merge) is not a round of disagreement: it does not count.
[ "$(markers factory-review | jq -r '[.[] | select(test("round=merge") | not)] | length')" -le "$MAX_REVIEWS" ] || no "More than $MAX_REVIEWS rounds of review without a clean result. Confirm: read the last review and decide whether to go on."
if [ -z "$REVIEW" ]; then wait_for "no review yet (run the pr-reviewer agent)"
elif [ "$(field "$REVIEW" sha)" != "$SHA" ]; then wait_for "the review is for an older commit (run pr-reviewer again)"
else
  # The door is not a rule: the blast radius and the review decide (docs/agents/review-policy.md).
  case "$(field "$REVIEW" blast)" in
    small|medium) ;;
    large) no "The review says the blast radius is large: a mistake reaches devices, people's data or accounts on merge. Confirm: you want this now, and the reason in the review holds." ;;
    *) wait_for "the review has no blast radius (run pr-reviewer again)" ;;
  esac
  # stuck: findings the reviewer still holds after the author argued against them twice.
  # The two agents cannot agree, so a person settles it.
  case "$(field "$REVIEW" stuck)" in
    0|"") ;;
    *) no "The author and the reviewer cannot agree on $(field "$REVIEW" stuck) finding(s). Confirm: read both sides in the last review and the author's answer, and say which way to go." ;;
  esac
  [ "$(field "$REVIEW" must-fix)" = 0 ] || wait_for "the review has must-fix findings: fix them, or answer them on the pull request"
fi
if [ -z "$GATE" ]; then wait_for "no gate verdict yet (run the merge-gate agent)"
elif [ "$(field "$GATE" sha)" != "$SHA" ]; then wait_for "the gate verdict is for an older commit (run merge-gate again)"
else
  [ "$(field "$GATE" verdict)" = merge ] || no "The gate says a human decides: see its comment for why and what to confirm."
fi

if [ -n "$NO" ]; then
  echo "Not merging #$PR. A human decides:$NO"
  [ -z "$WAIT" ] || echo "Also not ready:$WAIT"
  if [ "$MODE" != --check ]; then
    gh pr edit "$PR" --add-label needs-human >/dev/null
    gh pr edit "$PR" --remove-label auto-merge-ok >/dev/null 2>&1 || true
    # The label never stands alone: say why, once per commit.
    # Leave out "has the label": whoever set it has said why already.
    WHY=$(printf '%s\n' "$NO" | grep '^- ' | grep -v 'has the needs-human label' || true)
    if [ -n "$WHY" ] && [ "$(get "[.comments[] | select(.author.login == \"$ME\") | .body | select(contains(\"factory-human sha=$SHA\"))] | length")" = 0 ]; then
      FIRST=$(printf '%s\n' "$WHY" | sed -n '1s/^- //p' | sed "s/ Confirm:.*//")
      COUNT=$(printf '%s\n' "$WHY" | grep -c '^- ')
      [ "$COUNT" -le 1 ] || FIRST="$FIRST ($((COUNT - 1)) more below.)"
      gh pr comment "$PR" --body "## Needs human review

**TL;DR:** An agent may not merge this. $FIRST

### Why, and what to confirm
$WHY

When you are happy, merge on GitHub.

<!-- factory-human sha=$SHA -->" >/dev/null
    fi
  fi
  exit 1
fi
if [ -n "$WAIT" ]; then
  echo "Not merging #$PR yet:$WAIT"
  exit 1
fi

echo "#$PR passes every rule."
[ "$MODE" = --check ] && exit 0
gh pr merge "$PR" --squash --match-head-commit "$SHA"
git push origin --delete "$(get .headRefName)" >/dev/null 2>&1 || true
echo "Merged #$PR."
# Clear out worktrees whose pull requests are done (this one goes on the next run, from another folder).
"$(dirname "$0")/clean_worktrees.sh" || true
