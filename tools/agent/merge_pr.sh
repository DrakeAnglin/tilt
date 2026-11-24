#!/bin/sh
# Merge a pull request, but only when the rules in docs/agents/review-policy.md allow an agent to.
#   tools/agent/merge_pr.sh <pr>            check, then squash-merge
#   tools/agent/merge_pr.sh <pr> --check    check only
# Anything not allowed gets the needs-human label and is left for the owner to merge on GitHub.
set -eu
PR=${1:?usage: merge_pr.sh <pr> [--check]}
MODE=${2:-}

# Human-only paths. Keep the same as the list in docs/agents/review-policy.md.
HUMAN_ONLY='^(hardware/|tools/(fusion_.*|bambu.*|orient|release_firmware)\.py$|tools/flash.*\.sh$|tools/agent/|docs/adr/|docs/agents/|docs/requirements\.md$|\.github/|\.claude/|\.githooks/|CLAUDE\.md$)|(^|/)(partitions\.csv|sdkconfig[^/]*|fwkey\.h|sec\.h|tilt_crypto\.h|lock\.h|update\.h|Secure\.swift|FirmwareUpdate\.swift|Info\.plist|[^/]*-Info\.plist|PrivacyInfo\.xcprivacy|[^/]*\.entitlements)$'
MAX_LINES=400

J=$(gh pr view "$PR" --json number,state,isDraft,baseRefName,headRefName,headRefOid,mergeable,additions,deletions,files,comments)
get() { printf '%s' "$J" | jq -r "$1"; }
SHA=$(get .headRefOid)
WHY=""
no() { WHY="$WHY
- $1"; }

[ "$(get .state)" = OPEN ] || no "pull request is not open"
[ "$(get .isDraft)" = false ] || no "pull request is a draft"
[ "$(get .baseRefName)" = main ] || no "base is not main"
[ "$(get .mergeable)" = MERGEABLE ] || no "does not merge cleanly into main ($(get .mergeable))"

LINES=$(( $(get .additions) + $(get .deletions) ))
[ "$LINES" -le "$MAX_LINES" ] || no "$LINES changed lines (limit $MAX_LINES)"

TOUCHED=$(get '.files[].path' | grep -E "$HUMAN_ONLY" || true)
[ -z "$TOUCHED" ] || no "touches human-only paths: $(echo $TOUCHED)"

# CI: the 'ci' check must have passed, and nothing may be failing or still running.
CHECKS=$(gh pr checks "$PR" --json name,bucket 2>/dev/null || echo '[]')
[ "$(printf '%s' "$CHECKS" | jq -r '[.[] | select(.name == "ci" and .bucket == "pass")] | length')" -ge 1 ] || no "the ci check has not passed"
BAD=$(printf '%s' "$CHECKS" | jq -r '[.[] | select(.bucket != "pass" and .bucket != "skipping") | .name] | join(", ")')
[ -z "$BAD" ] || no "checks not green: $BAD"

# The review and the gate must both be for this exact commit.
marker() { get "[.comments[].body | capture(\"<!-- $1 (?<m>[^>]*) -->\"; \"g\") | .m] | last // \"\""; }
field() { printf '%s' "$1" | tr ' ' '\n' | sed -n "s/^$2=//p"; }
REVIEW=$(marker factory-review)
GATE=$(marker factory-gate)
if [ -z "$REVIEW" ]; then no "no review yet (run the pr-reviewer agent)"
else
  [ "$(field "$REVIEW" sha)" = "$SHA" ] || no "the review is for an older commit (run pr-reviewer again)"
  [ "$(field "$REVIEW" door)" = two-way ] || no "the review says one-way door"
  [ "$(field "$REVIEW" must-fix)" = 0 ] || no "the review has must-fix findings"
fi
if [ -z "$GATE" ]; then no "no gate verdict yet (run the merge-gate agent)"
else
  [ "$(field "$GATE" sha)" = "$SHA" ] || no "the gate verdict is for an older commit (run merge-gate again)"
  [ "$(field "$GATE" verdict)" = merge ] || no "the gate says a human decides"
fi

if [ -n "$WHY" ]; then
  echo "Not merging #$PR:$WHY"
  [ "$MODE" = --check ] || gh pr edit "$PR" --add-label needs-human --remove-label auto-merge-ok >/dev/null 2>&1 || gh pr edit "$PR" --add-label needs-human >/dev/null
  exit 1
fi

echo "#$PR passes every rule."
[ "$MODE" = --check ] && exit 0
gh pr merge "$PR" --squash --match-head-commit "$SHA"
git push origin --delete "$(get .headRefName)" >/dev/null 2>&1 || true
echo "Merged #$PR."
