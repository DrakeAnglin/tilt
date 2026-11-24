#!/bin/sh
# Run every test an agent can run on this Mac before opening a pull request. Same tests as CI.
#   tools/agent/check.sh          firmware + tools, and the app tests if app files changed
#   tools/agent/check.sh --all    everything
set -e
cd "$(dirname "$0")/../.."
tools/firmware_tests.sh
python3 -m unittest tools/test_tools.py
if [ "$1" = "--all" ] || git diff --name-only origin/main...HEAD | grep -qE '^(app/|firmware/blinds_matter/test/wire|tools/app_tests\.sh)'; then
  tools/app_tests.sh
else
  echo "app tests skipped: no app files changed (--all runs them)"
fi
echo "check: ok"
