#!/bin/sh
# Remove the worktrees under .claude/worktrees/ whose pull request is merged or closed.
#   tools/agent/clean_worktrees.sh            remove them (and their local branches and build folders)
#   tools/agent/clean_worktrees.sh --dry-run  only say what would go
# A worktree is kept when anything in it could be lost: uncommitted changes, commits that never
# reached its pull request, no pull request at all, or a detached HEAD. The worktree this runs
# from is kept too (a session cannot remove the folder it is standing in): it goes on a later run.
# Runs at the start of every session (.claude/settings.json) and after every merge (merge_pr.sh).
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
trap 'rm -rf "$LOCK"' EXIT INT TERM

git -C "$ROOT" worktree prune
git -C "$ROOT" worktree list --porcelain | awk '/^worktree /{p=substr($0,10)} /^branch /{print p "\t" substr($0,19)} /^detached/{print p "\t"}' |
while IFS="$(printf '\t')" read -r WT BR; do
  case "$WT" in "$DIR"/*) ;; *) continue ;; esac
  NAME=${WT#"$DIR"/}
  keep() { echo "keep   $NAME: $1"; }
  [ "$WT" = "$HERE" ] && { keep "this session is in it"; continue; }
  [ -n "$BR" ] || { keep "detached HEAD (no branch)"; continue; }
  [ -z "$(git -C "$WT" status --porcelain 2>/dev/null)" ] || { keep "uncommitted changes"; continue; }
  PR=$(gh pr list --head "$BR" --state all --limit 1 --json number,state,headRefOid --jq '.[0] // empty | "\(.number) \(.state) \(.headRefOid)"' 2>/dev/null) || { keep "could not ask GitHub"; continue; }
  [ -n "$PR" ] || { keep "no pull request for $BR"; continue; }
  set -- $PR
  case "$2" in MERGED|CLOSED) ;; *) keep "pull request #$1 is $2"; continue ;; esac
  HEAD=$(git -C "$WT" rev-parse HEAD)
  [ "$HEAD" = "$3" ] || { keep "has commits that are not in pull request #$1"; continue; }
  if [ -n "$DRY" ]; then echo "would remove $NAME (#$1 $2)"; continue; fi
  # Build folders are ignored by Git, so remove them first; then the worktree and its branch.
  rm -rf "$WT"/firmware/*/build "$WT"/firmware/*/managed_components "$WT"/app/Tilt/build*
  if git -C "$ROOT" worktree remove --force "$WT"; then
    git -C "$ROOT" branch -D "$BR" >/dev/null 2>&1 || true
    echo "removed $NAME (#$1 $2)"
  else
    keep "git could not remove it"
  fi
done
