#!/bin/sh
# Merge a pull request, but only when the rules in docs/agents/review-policy.md allow an agent to.
#   tools/agent/merge_pr.sh <pr>            check, then squash-merge
#   tools/agent/merge_pr.sh <pr> --check    check only
# "Not yet" (CI running, no review) just stops. "Not allowed" also gets the needs-human label,
# and the owner merges on GitHub.
set -eu
PR=${1:?usage: merge_pr.sh <pr> [--check]}
MODE=${2:-}

# Human-only paths. Keep the same as the list in docs/agents/review-policy.md.
HUMAN_ONLY='^(hardware/|tools/(fusion_.*|bambu.*|orient|release_firmware)\.py$|tools/(flash.*|firmware_tests|app_tests)\.sh$|tools/agent/|docs/adr/|docs/agents/|docs/requirements\.md$|\.github/|\.claude/|\.githooks/|CLAUDE\.md$)|(^|/)(partitions\.csv|sdkconfig[^/]*|fwkey\.h|sec\.h|tilt_crypto\.h|lock\.h|update\.h|Secure\.swift|FirmwareUpdate\.swift|Info\.plist|[^/]*-Info\.plist|PrivacyInfo\.xcprivacy|[^/]*\.entitlements)$'
MAX_LINES=400
MAX_REVIEWS=3

J=$(gh pr view "$PR" --json number,state,isDraft,isCrossRepository,baseRefName,headRefName,headRefOid,mergeable,additions,deletions,labels,comments)
get() { printf '%s' "$J" | jq -r "$1"; }
SHA=$(get .headRefOid)
NO=""      # not allowed: a human decides
WAIT=""    # not yet: try again later
no() { NO="$NO
- $1"; }
wait_for() { WAIT="$WAIT
- $1"; }

[ "$(get .state)" = OPEN ] || no "pull request is not open"
[ "$(get .isDraft)" = false ] || wait_for "pull request is a draft"
[ "$(get .baseRefName)" = main ] || no "base is not main"
[ "$(get .isCrossRepository)" = false ] || no "comes from a fork"
case "$(get .mergeable)" in
  MERGEABLE) ;;
  UNKNOWN) wait_for "GitHub has not worked out yet whether it merges cleanly" ;;
  *) wait_for "does not merge cleanly into main: bring the branch up to date" ;;
esac

# A label set by hand, or by the gate, wins over everything else.
for L in needs-human one-way-door; do
  [ "$(get "[.labels[].name] | index(\"$L\")")" = null ] || no "has the $L label"
done

LINES=$(( $(get .additions) + $(get .deletions) ))
[ "$LINES" -lt "$MAX_LINES" ] || no "$LINES changed lines (must be under $MAX_LINES)"

# Every changed file (and the old name of a renamed one), not only the first page.
FILES=$(gh api "repos/{owner}/{repo}/pulls/$PR/files" --paginate --jq '.[] | .filename, (.previous_filename // empty)')
[ -n "$FILES" ] || no "could not list the changed files"
TOUCHED=$(printf '%s\n' "$FILES" | grep -E "$HUMAN_ONLY" || true)
[ -z "$TOUCHED" ] || no "touches human-only paths: $(echo $TOUCHED)"

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
markers() { get "[.comments[].body | capture(\"<!-- $1 (?<m>[^>]*) -->\"; \"g\") | .m]"; }
field() { printf '%s' "$1" | tr ' ' '\n' | sed -n "s/^$2=//p"; }
REVIEW=$(markers factory-review | jq -r 'last // ""')
GATE=$(markers factory-gate | jq -r 'last // ""')
[ "$(markers factory-review | jq -r length)" -le "$MAX_REVIEWS" ] || no "more than $MAX_REVIEWS rounds of review"
if [ -z "$REVIEW" ]; then wait_for "no review yet (run the pr-reviewer agent)"
elif [ "$(field "$REVIEW" sha)" != "$SHA" ]; then wait_for "the review is for an older commit (run pr-reviewer again)"
else
  [ "$(field "$REVIEW" door)" = two-way ] || no "the review says one-way door"
  [ "$(field "$REVIEW" must-fix)" = 0 ] || wait_for "the review has must-fix findings"
fi
if [ -z "$GATE" ]; then wait_for "no gate verdict yet (run the merge-gate agent)"
elif [ "$(field "$GATE" sha)" != "$SHA" ]; then wait_for "the gate verdict is for an older commit (run merge-gate again)"
else
  [ "$(field "$GATE" verdict)" = merge ] || no "the gate says a human decides"
fi

if [ -n "$NO" ]; then
  echo "Not merging #$PR. A human decides:$NO"
  [ -z "$WAIT" ] || echo "Also not ready:$WAIT"
  if [ "$MODE" != --check ]; then
    gh pr edit "$PR" --add-label needs-human >/dev/null
    gh pr edit "$PR" --remove-label auto-merge-ok >/dev/null 2>&1 || true
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
