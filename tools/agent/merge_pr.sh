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

MAX_LINES=600
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
[ "$(get '[.labels[].name] | index("needs-human")')" = null ] || no "has the needs-human label"

# Every changed file (and the old name of a renamed one), not only the first page.
FILE_JSON=$(gh api "repos/{owner}/{repo}/pulls/$PR/files" --paginate --jq '.[] | {f: .filename, p: (.previous_filename // ""), n: (.additions + .deletions)}')
FILES=$(printf '%s\n' "$FILE_JSON" | jq -r '.f, (select(.p != "") | .p)')
[ -n "$FILES" ] || no "could not list the changed files"
# Tests do not count toward the size: more tests should never push a change to a human.
TEST_FILES='(^|/)(test|tests|Tests)/|(^|/)test_[^/]*\.py$'
LINES=$(printf '%s\n' "$FILE_JSON" | jq -rs --arg t "$TEST_FILES" '[.[] | select(.f | test($t) | not) | .n] | add // 0')
[ "$LINES" -lt "$MAX_LINES" ] || no "$LINES changed lines, not counting tests (must be under $MAX_LINES): too big for an agent to vouch for. Confirm: the change is one thing, and read the summary against the diff."
# Human-only paths: pattern, why a person is needed, what the person confirms.
# Keep the same as the list in docs/agents/review-policy.md.
human_only() {
  HIT=$(printf '%s\n' "$FILES" | grep -E "$1" | tr '\n' ' ' || true)
  [ -z "$HIT" ] || no "$2 Confirm: $3 Files: $HIT"
}
human_only '^(hardware/|tools/(fusion_.*|bambu.*|orient)\.py$)' \
  "Printed parts or the PCB changed, and no test can look at a part." \
  "the build is ok, nothing pokes out, every moving part can turn."
human_only '^tools/(release_firmware\.py|flash.*\.sh)$|(^|/)(partitions\.csv|sdkconfig[^/]*)$' \
  "Release or flashing changed; a mistake here can reach controllers that are in use." \
  "a controller still takes an update and still starts."
# update.h is here for its signature check (fwSignatureOk). The rest of the update path is two-way
# at merge and gets a bench check before the next release.
human_only '(^|/)(fwkey\.h|sec\.h|tilt_crypto\.h|lock\.h|update\.h|Secure\.swift)$' \
  "Keys, pairing, the firmware signature check or who may do what changed, and a bench check does not show a hole." \
  "nothing is let in that should not be, and paired devices still trust each other."
human_only '(^|/)(Info\.plist|[^/]*-Info\.plist|PrivacyInfo\.xcprivacy|[^/]*\.entitlements)$' \
  "What the app asks Apple for changed." \
  "the permissions and privacy answers are what you want Apple to review."
human_only '^(docs/adr/|docs/requirements\.md$)' \
  "A decision or requirement changed, and those are the owner's." \
  "you agree with the decision as written."
# The test scripts: adding a test to the run is fine; changing how the tests run is not.
# only_adds_tests.awk says which: removed lines are only comments, and no added line can hide a failure.
AWK="$(dirname "$0")/only_adds_tests.awk"
for F in $(printf '%s\n' "$FILES" | grep -E '^tools/(firmware_tests|app_tests)\.sh$' | sort -u || true); do
  PATCH=$(gh api "repos/{owner}/{repo}/pulls/$PR/files" --paginate --jq ".[] | select(.filename == \"$F\" and .status == \"modified\") | .patch // \"\"")
  printf '%s\n' "$PATCH" | awk -f "$AWK" ||
    no "How the tests run changed, not only which tests run. Confirm: no test was dropped or weakened. Files: $F"
done
# Only what decides a merge. Workflow docs, skills, CLAUDE.md and the pull request template are open to agents.
human_only '^(tools/agent/|docs/agents/review-policy\.md$|\.github/workflows/|\.claude/agents/|\.claude/settings[^/]*\.json$|\.githooks/)' \
  "What decides a merge changed (policy, reviewer, gate, merge script, guard or CI), and an agent does not approve that for itself." \
  "the rules still say what you want: who may merge, the doors, the blast radius, the human-only list."

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
[ "$(markers factory-review | jq -r length)" -le "$MAX_REVIEWS" ] || no "More than $MAX_REVIEWS rounds of review without a clean result. Confirm: read the last review and decide whether to go on."
if [ -z "$REVIEW" ]; then wait_for "no review yet (run the pr-reviewer agent)"
elif [ "$(field "$REVIEW" sha)" != "$SHA" ]; then wait_for "the review is for an older commit (run pr-reviewer again)"
else
  # The door is not a rule: the blast radius and the review decide (docs/agents/review-policy.md).
  case "$(field "$REVIEW" blast)" in
    small|medium) ;;
    large) no "The review says the blast radius is large: a mistake reaches devices, people's data or accounts on merge. Confirm: you want this now, and the reason in the review holds." ;;
    *) wait_for "the review has no blast radius (run pr-reviewer again)" ;;
  esac
  [ "$(field "$REVIEW" must-fix)" = 0 ] || wait_for "the review has must-fix findings"
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
