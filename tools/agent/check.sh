#!/bin/sh
# Run every test an agent can run on this Mac before opening a pull request. Same tests as CI, then the same
# coverage gate as CI (docs/agents/workflow.md, "Coverage").
#   tools/agent/check.sh          firmware + tools, and the app tests if app files changed
#   tools/agent/check.sh --all    everything
set -e
cd "$(dirname "$0")/../.."
# The gate needs the coverage package: fail now, not after the tests (a skipped gate would hide a failure).
python3 -c 'import coverage' 2>/dev/null || {
  echo "check: the coverage package is missing. Install it: python3 -m pip install --user 'coverage>=7.10'" >&2
  exit 1
}
tools/firmware_tests.sh
python3 -m unittest tools/test_tools.py
python3 -m unittest tools/agent/test_agent.py
python3 -m unittest hardware/mechanical/fusion/test_geometry.py
# Changed files: commits since main, plus anything not committed yet. If that cannot be worked out, run the app tests.
CHANGED=$( { git diff --name-only origin/main...HEAD && git status --porcelain | cut -c4-; } 2>/dev/null ) || CHANGED="app/"
APP=""
if [ "${1:-}" = "--all" ] || printf '%s\n' "$CHANGED" | grep -qE '^(app/|firmware/blinds_matter/test/wire|tools/app_tests\.sh|tools/coverage)'; then
  tools/app_tests.sh
  APP=1
else
  echo "app tests skipped: no app files changed (--all runs them)"
fi

# The coverage gate: the same tests again with coverage on, then each area against main.
COV=$(mktemp -d)
trap 'rm -rf "$COV"' EXIT
covrun() {
  tools/coverage.sh "$1" "$COV" >"$COV/$1.out" 2>&1 || { tail -40 "$COV/$1.out"; echo "check: the $1 tests failed with coverage on" >&2; exit 1; }
}
covrun firmware
covrun tools
AREAS="controller:firmware hub:firmware tools:tools"
[ -z "$APP" ] || { covrun app; AREAS="$AREAS app:app"; }
FAIL=""
for A in $AREAS; do
  python3 tools/coverage_gate.py check --area "${A%%:*}" --lcov "$COV/${A#*:}.lcov" --log "$COV/${A#*:}.log" --base origin/main ||
    FAIL="$FAIL ${A%%:*}"
done
[ -z "$FAIL" ] || { echo "check: the coverage gate failed for:$FAIL (docs/agents/workflow.md, \"Coverage\")" >&2; exit 1; }
echo "check: ok"
