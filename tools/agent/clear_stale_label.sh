#!/bin/sh
# Take needs-human off a pull request when no rule still gives a reason for it.
#   tools/agent/clear_stale_label.sh <pr>
# A label goes stale when its reason is gone: the gate said human for an older commit, CI was red, an old
# copy of the merge script added it, or it came over in a repo move. This asks the merge rules on main
# (merge_pr.sh --check, with the label ignored) whether a human is still needed. If not, the label comes off,
# with a comment that says so. It stays when:
#   - the rules still send the pull request to a human (a stuck finding, a large blast radius, ...), or
#   - the owner wrote a comment starting with /hold (the owner's way to keep a pull request for themselves).
set -eu
PR=${1:?usage: clear_stale_label.sh <pr>}
HERE=$(dirname "$0")
J=$(gh pr view "$PR" --json headRefOid,labels,comments)
get() { printf '%s' "$J" | jq -r "$1"; }
[ "$(get '[.labels[].name] | index("needs-human")')" != null ] || { echo "#$PR has no needs-human label."; exit 0; }
SHA=$(get .headRefOid)
if [ "$(get '[.comments[] | select(.body | startswith("/hold"))] | length')" != 0 ]; then
  echo "#$PR keeps needs-human: the owner wrote /hold."; exit 1
fi
OUT=$(IGNORE_NEEDS_HUMAN=1 "$HERE/merge_pr.sh" "$PR" --check 2>&1) || true
if printf '%s\n' "$OUT" | grep -q 'A human decides'; then
  echo "#$PR keeps needs-human: the rules still need a person."
  printf '%s\n' "$OUT"
  exit 1
fi
gh pr edit "$PR" --remove-label needs-human >/dev/null
gh pr comment "$PR" --body "Took off \`needs-human\`: no rule on main still needs a person for $(printf '%.7s' "$SHA") (\`tools/agent/clear_stale_label.sh\`). The owner keeps a pull request by writing a comment that starts with /hold.

<!-- factory-unlabel sha=$SHA -->" >/dev/null
echo "#$PR: needs-human taken off (stale)."
printf '%s\n' "$OUT"
