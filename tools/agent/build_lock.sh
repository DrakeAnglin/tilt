#!/bin/sh
# Run one firmware build at a time on this Mac, across every worktree and session.
#   tools/agent/build_lock.sh firmware/blinds_matter/build.sh
#   tools/agent/build_lock.sh firmware/tilt_hub/build.sh
# ESP-IDF builds take most of the CPU and a few GB of disk each; several at once filled the disk twice.
# The lock is /tmp/tilt-idf-build.lock: its pid file names the process that holds it, and its owner file says
# which checkout. The lock is stale only when that process is gone, never just because a build is long.
# Before it builds, with under 5 GB free, it runs clean_worktrees.sh (the one next to it, saying the build lock
# is held) to clear finished worktrees and old build folders, then measures again. Still under 3 GB: it prints
# what is free and how to see what holds the disk, and exits 75 without building (one build writes about 1 GB).
# TILT_FREE_GB sets the free space for the tests.
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
free_gb() { echo "${TILT_FREE_GB:-$(df -k . | awk 'NR == 2 {print int($4 / 1048576)}')}"; }
FREE=$(free_gb)
if [ "$FREE" -lt 5 ]; then
  echo "build_lock: only ${FREE} GB free; clearing finished worktrees and old build folders first." >&2
  TILT_BUILD_LOCK_HELD=1 "$(dirname "$0")/clean_worktrees.sh" >&2
  FREE=$(free_gb)
  if [ "$FREE" -lt 3 ]; then
    echo "build_lock: only ${FREE} GB free, too little for a build (one writes about 1 GB). See what holds the disk:" >&2
    echo "  tools/agent/clean_worktrees.sh --dry-run" >&2
    echo "  du -sh .claude/worktrees/*/firmware/*/build" >&2
    exit 75
  fi
fi
"$@"
