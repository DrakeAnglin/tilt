#!/bin/sh
# Run one firmware build at a time on this Mac, across every worktree and session.
#   tools/agent/build_lock.sh firmware/blinds_matter/build.sh
#   tools/agent/build_lock.sh firmware/tilt_hub/build.sh
# ESP-IDF builds take most of the CPU and a few GB of disk each; several at once filled the disk twice.
# The lock is /tmp/tilt-idf-build.lock (its owner file says who holds it). A lock older than 45 minutes is stale.
# Before it builds, it warns when the disk has under 5 GB free.
set -u
[ $# -gt 0 ] || { echo "usage: build_lock.sh <command> [args...]" >&2; exit 2; }
LOCK=${TILT_BUILD_LOCK:-/tmp/tilt-idf-build.lock}
WHO="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)") pid $$"
until mkdir "$LOCK" 2>/dev/null; do
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +45 2>/dev/null)" ]; then
    echo "build_lock: stale lock ($(cat "$LOCK/owner" 2>/dev/null)); taking it." >&2; rm -rf "$LOCK"; continue
  fi
  echo "build_lock: waiting for $(cat "$LOCK/owner" 2>/dev/null || echo another build)..." >&2
  sleep 30
done
trap 'rm -rf "$LOCK"' EXIT INT TERM
echo "$WHO" > "$LOCK/owner"
FREE=$(df -k . | awk 'NR == 2 {print int($4 / 1048576)}')
[ "$FREE" -ge 5 ] || echo "build_lock: only ${FREE} GB free. Worktrees of merged pull requests go with tools/agent/clean_worktrees.sh." >&2
"$@"
