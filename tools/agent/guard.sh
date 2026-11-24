#!/bin/sh
# Claude Code hook (before every shell command): stops the ways around the pull request rules.
# Reads the hook's JSON on stdin. Exit 2 blocks the command and shows the message to the agent.
CMD=$(jq -r '.tool_input.command // ""')
stop() { echo "Blocked: $1 See docs/agents/workflow.md." >&2; exit 2; }
case "$CMD" in
  *"gh pr merge"*) stop "merge with tools/agent/merge_pr.sh <pr>, or leave it for the owner." ;;
  *pulls/*/merge*) stop "merge with tools/agent/merge_pr.sh <pr>, or leave it for the owner." ;;
esac
if printf '%s' "$CMD" | grep -qE 'git[^|;&]* push'; then
  printf '%s' "$CMD" | grep -qE -- '--no-verify' && stop "no pushing past the pre-push hook."
  printf '%s' "$CMD" | grep -qE '(^|[ :+])main([ ]|$)' && stop "nothing is pushed to main; open a pull request."
fi
exit 0
