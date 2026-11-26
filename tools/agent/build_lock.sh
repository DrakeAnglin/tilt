#!/bin/sh
# Run one firmware build at a time on this Mac, across every worktree and session.
#   tools/agent/build_lock.sh firmware/blinds_matter/build.sh
#   tools/agent/build_lock.sh firmware/tilt_hub/build.sh
# ESP-IDF builds take most of the CPU and a few GB of disk each; several at once filled the disk twice.
# The lock is /tmp/tilt-idf-build.lock: its pid file names the process that holds it, and its owner file says
# which checkout. The lock is stale only when that process is gone, never just because a build is long.
# Before it builds, it warns when the disk has under 5 GB free.
set -u
[ $# -gt 0 ] || { echo "usage: build_lock.sh <command> [args...]" >&2; exit 2; }
LOCK=${TILT_BUILD_LOCK:-/tmp/tilt-idf-build.lock}
until mkdir "$LOCK" 2>/dev/null; do
  HOLDER=$(cat "$LOCK/pid" 2>/dev/null || true)
  if [ -n "$HOLDER" ] && ! kill -0 "$HOLDER" 2>/dev/null; then
    echo "build_lock: the holder ($(cat "$LOCK/owner" 2>/dev/null)) is gone; taking the lock." >&2
    mv "$LOCK" "$LOCK.stale.$$" 2>/dev/null && rm -rf "$LOCK.stale.$$"; continue
  fi
  # No pid file yet: the holder is between mkdir and writing it. Give it a moment.
  echo "build_lock: waiting for $(cat "$LOCK/owner" 2>/dev/null || echo another build)..." >&2
  sleep 30
done
echo $$ > "$LOCK/pid"
echo "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)") pid $$" > "$LOCK/owner"
# Remove the lock only while it is still ours. INT or TERM ends this script (and so the lock) after the build stops.
trap '[ "$(cat "$LOCK/pid" 2>/dev/null)" = $$ ] && rm -rf "$LOCK"' EXIT
trap 'exit 130' INT TERM
FREE=$(df -k . | awk 'NR == 2 {print int($4 / 1048576)}')
[ "$FREE" -ge 5 ] || echo "build_lock: only ${FREE} GB free. Worktrees of merged pull requests go with tools/agent/clean_worktrees.sh." >&2
"$@"
