#!/bin/sh
# Take needs-human off a pull request when its reason is gone, and only then.
#   tools/agent/clear_stale_label.sh <pr>
# A label goes stale when the gate said human for an older commit, CI was red or never ran, an old copy of the
# merge script added it, or a repo move carried it over. The label stays (exit 1) when:
#   - a verdict gave a reason a new commit does not take away (a stuck finding, a large blast radius, ten rounds,
#     a test-script change, a fork): its marker says sticky=1;
#   - the owner wrote a comment starting with /hold;
#   - the merge rules on main, asked with the label ignored, still need a person;
#   - anything cannot be checked (GitHub, main's copy of the rules): it fails closed.
# Only comments from the account running this count: a stranger cannot hold or free a pull request.
set -u
PR=${1:?usage: clear_stale_label.sh <pr>}
keep() { echo "#$PR keeps needs-human: $1"; exit 1; }

# Judge by main's copy of this script and of merge_pr.sh, never a worktree's.
if [ -z "${CLEAR_FROM_MAIN:-}" ]; then
  git fetch -q origin main 2>/dev/null || true
  T=$(mktemp -d)
  git archive origin/main tools/agent 2>/dev/null | tar -x -C "$T" 2>/dev/null
  if [ -f "$T/tools/agent/clear_stale_label.sh" ]; then
    RC=0; CLEAR_FROM_MAIN=1 sh "$T/tools/agent/clear_stale_label.sh" "$PR" || RC=$?
    rm -rf "$T"; exit $RC
  fi
  rm -rf "$T"
  # Main does not have this script yet: the first run after it merges. Use this copy.
fi
HERE=$(dirname "$0")

J=$(gh pr view "$PR" --json headRefOid,labels,comments) || keep "could not read the pull request."
ME=$(gh api user --jq .login) || keep "could not tell which account this is."
get() { printf '%s' "$J" | jq -r "$1"; }
[ "$(get '[.labels[].name] | index("needs-human")')" != null ] || { echo "#$PR has no needs-human label."; exit 0; }
SHA=$(get .headRefOid)
MINE="[.comments[] | select(.author.login == \"$ME\") | .body]"
[ "$(get "$MINE | map(select(startswith(\"/hold\"))) | length")" = 0 ] || keep "the owner wrote /hold."
[ "$(get "$MINE | map(select(test(\"<!-- factory-(human|gate) [^>]*sticky=1\"))) | length")" = 0 ] ||
  keep "a verdict gave a reason a new commit does not take away (see the comment marked sticky=1)."

OUT=$(IGNORE_NEEDS_HUMAN=1 "$HERE/merge_pr.sh" "$PR" --check 2>&1); RC=$?
printf '%s\n' "$OUT" | grep -q "could not read main's copy" && keep "could not read main's copy of the rules."
printf '%s\n' "$OUT" | grep -q 'A human decides' && { printf '%s\n' "$OUT"; keep "the rules still need a person."; }
# Free it only on a clear answer: every rule passes, or the only things left are "not yet".
if [ "$RC" != 0 ] && ! printf '%s\n' "$OUT" | grep -q "^Not merging #$PR yet:"; then
  printf '%s\n' "$OUT"; keep "the check did not give a clear answer."
fi
gh pr edit "$PR" --remove-label needs-human >/dev/null || keep "GitHub would not take the label off."
gh pr comment "$PR" --body "Took off \`needs-human\`: its reason is gone, and no rule on main needs a person for $(printf '%.7s' "$SHA") (\`tools/agent/clear_stale_label.sh\`). The owner keeps a pull request with a comment that starts with /hold.

<!-- factory-unlabel sha=$SHA -->" >/dev/null || true
echo "#$PR: needs-human taken off (stale)."
printf '%s\n' "$OUT"
