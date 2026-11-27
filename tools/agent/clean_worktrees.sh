#!/bin/sh
# Remove the worktrees under .claude/worktrees/ whose pull request is merged or closed, and trim the rest.
#   tools/agent/clean_worktrees.sh            remove them (and their local branches and build folders)
#   tools/agent/clean_worktrees.sh --dry-run  only say what would go
# The pull request is found by the worktree's branch name; with none (the app names the local branch
# worktree-<x> while the pull request's branch is often <x>), or on a detached HEAD, by the worktree's
# HEAD commit: the pull request whose head commit is exactly HEAD.
# A worktree is kept when anything in it could be lost: uncommitted changes, commits that never
# reached its pull request, or no pull request at all. A detached HEAD goes like any other worktree when
# its commit is a finished pull request's head; a branch is deleted only when there is one.
# Session locks (git worktree lock, "claude session <name> (pid <n> ...)"): a lock whose pid is gone is
# stale, so it is taken off and the worktree goes. A lock whose pid is alive, or with no pid in it, keeps
# the worktree ("a session is in it"): a session cannot lose the folder it is standing in. The worktree
# this runs from is kept for the same reason: it goes on a later run.
# Every kept worktree loses its firmware/*/build folders (a cache: build.sh makes them again), except the
# one this runs from and one a live session holds while its pull request is not merged or closed (that
# session may still build). Trimming happens only while holding the build lock (build_lock.sh), taken
# without waiting, or when TILT_BUILD_LOCK_HELD=1 says the caller holds it; a live build skips the trim.
# Runs at the start of every session (.claude/settings.json), after every merge (merge_pr.sh), and from
# build_lock.sh when the disk is nearly full.
set -u
DRY=""
[ "${1:-}" = --dry-run ] && DRY=1

COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
ROOT=$(dirname "$COMMON")
HERE=$(git rev-parse --show-toplevel 2>/dev/null || true)
DIR="$ROOT/.claude/worktrees"
[ -d "$DIR" ] || exit 0

# One cleaner at a time (several sessions can start together). A lock older than 10 minutes is stale.
LOCK="$COMMON/clean-worktrees.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || exit 0
  else echo "clean_worktrees: another run is going; skipped."; exit 0; fi
fi
BLOCK=${TILT_BUILD_LOCK:-/tmp/tilt-idf-build.lock}
BUILD=""  # held | busy | "" (not tried yet)
[ "${TILT_BUILD_LOCK_HELD:-}" = 1 ] && BUILD=held
OURS=""
trap 'rm -rf "$LOCK"; [ -n "$OURS" ] && [ "$(cat "$BLOCK/pid" 2>/dev/null)" = $$ ] && rm -rf "$BLOCK"' EXIT
trap 'exit 130' INT TERM

# Take the build lock without waiting, the way build_lock.sh writes it. Stale when its pid is gone.
build_lock() {
  [ -n "$BUILD" ] && { [ "$BUILD" = held ]; return; }
  for _ in 1 2; do
    if mkdir "$BLOCK" 2>/dev/null; then
      echo $$ > "$BLOCK/pid"
      echo "$(basename "$ROOT") clean_worktrees pid $$" > "$BLOCK/owner"
      BUILD=held; OURS=1; return 0
    fi
    HOLDER=$(cat "$BLOCK/pid" 2>/dev/null || true)
    [ -n "$HOLDER" ] && ! kill -0 "$HOLDER" 2>/dev/null || break
    mv "$BLOCK" "$BLOCK.stale.$$" 2>/dev/null && rm -rf "$BLOCK.stale.$$"
  done
  BUILD=busy
  echo "clean_worktrees: a build is running ($(cat "$BLOCK/owner" 2>/dev/null || echo build lock held)); build folders not trimmed this run."
  return 1
}

# Remove the build folders of a worktree that stays.
trim() {
  ls -d "$WT"/firmware/*/build >/dev/null 2>&1 || return 0
  if [ -n "$DRY" ]; then echo "would trim $NAME: build folders"; return; fi
  build_lock || return 0
  rm -rf "$WT"/firmware/*/build && echo "trimmed $NAME: build folders"
  # Give the build lock back right away, so a build does not wait on the GitHub calls for the next worktrees.
  [ -n "$OURS" ] && [ "$(cat "$BLOCK/pid" 2>/dev/null)" = $$ ] && rm -rf "$BLOCK" && { OURS=""; BUILD=""; }
  return 0
}

# Sets PR to "<number> <state> <head>" (empty when there is none). Fails when GitHub cannot be asked.
find_pr() {
  PR=""
  if [ -n "$BR" ]; then
    PR=$(gh pr list --head "$BR" --state all --limit 1 --json number,state,headRefOid --jq '.[0] // empty | "\(.number) \(.state) \(.headRefOid)"' </dev/null 2>/dev/null) || return 1
  fi
  [ -n "$PR" ] && return 0
  PR=$(gh pr list --state all --search "$HEAD" --json number,state,headRefOid --jq '.[] | "\(.number) \(.state) \(.headRefOid)"' </dev/null 2>/dev/null) || return 1
  # Several with this head (closed and opened again, or a second base): an open one wins, so the worktree stays.
  PR=$(printf '%s\n' "$PR" | awk -v h="$HEAD" '$3 == h { if ($2 == "OPEN") { print; found = 1; exit } if (first == "") first = $0 }
    END { if (!found && first != "") print first }')
}

git -C "$ROOT" worktree prune
US=$(printf '\037')
# One line per worktree: path, branch (empty when detached), "locked" or empty, the lock's reason.
LIST=$(git -C "$ROOT" worktree list --porcelain | awk -v s="$US" '
  function out() { if (p != "") print p s b s l s r; p = b = l = r = "" }
  /^worktree / { out(); p = substr($0, 10) }
  /^branch / { b = substr($0, 19) }
  /^locked/ { l = "locked"; r = substr($0, 8) }
  END { out() }')

while IFS="$US" read -r WT BR LOCKED REASON; do
  case "$WT" in "$DIR"/*) ;; *) continue ;; esac
  NAME=${WT#"$DIR"/}
  keep() { echo "keep   $NAME: $1"; }
  [ "$WT" = "$HERE" ] && { keep "this session is in it"; continue; }
  HEAD=$(git -C "$WT" rev-parse HEAD </dev/null)
  SESSION=""  # live | stale | "" (no lock)
  if [ -n "$LOCKED" ]; then
    LPID=$(printf '%s\n' "$REASON" | sed -n 's/.*(pid \([0-9][0-9]*\).*/\1/p')
    if [ -n "$LPID" ] && ! kill -0 "$LPID" 2>/dev/null; then SESSION=stale; else SESSION=live; fi
  fi
  if [ "$SESSION" = live ]; then
    keep "a session is in it"
    # Its build folders go only when its pull request is finished: otherwise the session may still build.
    find_pr && [ -n "$PR" ] && case "$PR" in *" MERGED "*|*" CLOSED "*) trim ;; esac
    continue
  fi
  [ -z "$(git -C "$WT" status --porcelain </dev/null 2>/dev/null)" ] || { keep "uncommitted changes"; trim; continue; }
  find_pr || { keep "could not ask GitHub"; trim; continue; }
  [ -n "$PR" ] || { keep "no pull request for ${BR:-detached HEAD $HEAD}"; trim; continue; }
  set -- $PR
  case "$2" in MERGED|CLOSED) ;; *) keep "pull request #$1 is $2"; trim; continue ;; esac
  [ "$HEAD" = "$3" ] || { keep "has commits that are not in pull request #$1"; trim; continue; }
  if [ -n "$DRY" ]; then echo "would remove $NAME (#$1 $2)"; continue; fi
  [ "$SESSION" = stale ] && { git -C "$ROOT" worktree unlock "$WT" </dev/null; echo "unlocked $NAME: its session (pid $LPID) is gone"; }
  # Build folders are ignored by Git, so remove them first; then the worktree and its branch.
  rm -rf "$WT"/firmware/*/build "$WT"/firmware/*/managed_components "$WT"/app/Tilt/build*
  if git -C "$ROOT" worktree remove --force "$WT" </dev/null; then
    [ -n "$BR" ] && { git -C "$ROOT" branch -D "$BR" >/dev/null 2>&1 || true; }
    echo "removed $NAME (#$1 $2)"
  else
    keep "git could not remove it"
  fi
done <<EOF
$LIST
EOF
