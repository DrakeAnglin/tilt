#!/bin/sh
# Run every test an agent can run on this Mac before opening a pull request. Same tests as CI.
#   tools/agent/check.sh          firmware + tools, and the app tests if app files changed
#   tools/agent/check.sh --all    everything
set -e
cd "$(dirname "$0")/../.."
tools/firmware_tests.sh
python3 -m unittest tools/test_tools.py
python3 -m unittest tools/agent/test_agent.py
# Changed files: commits since main, plus anything not committed yet. If that cannot be worked out, run the app tests.
CHANGED=$( { git diff --name-only origin/main...HEAD && git status --porcelain | cut -c4-; } 2>/dev/null ) || CHANGED="app/"
if [ "${1:-}" = "--all" ] || printf '%s\n' "$CHANGED" | grep -qE '^(app/|firmware/blinds_matter/test/wire|tools/app_tests\.sh)'; then
  tools/app_tests.sh
else
  echo "app tests skipped: no app files changed (--all runs them)"
fi
echo "check: ok"
