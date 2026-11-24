"""Tests for the agent guard (tools/agent/guard.py).

  python3 -m unittest tools/agent/test_agent.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard  # noqa: E402

BLOCKED = [
    'gh pr merge 51 --squash',
    'gh  pr   merge 51',
    'gh pr -R DrakeAnglin/tilt merge 51',
    'gh -R DrakeAnglin/tilt pr merge 51 --auto',
    'cd x && gh pr merge 51',
    'gh api -X PUT repos/DrakeAnglin/tilt/pulls/51/merge',
    "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
    'curl -X PUT https://api.github.com/repos/DrakeAnglin/tilt/pulls/51/merge',
    'git push origin main',
    'git push origin main; echo done',
    'git push origin "main"',
    "git push origin 'HEAD:main'",
    'git push origin refs/heads/main',
    'git push origin HEAD:refs/heads/main',
    'git push origin +issue-5:main',
    'git push -f origin issue-5:main',
    'git -C somewhere push origin main',
    'git push --all origin',
    'git push --no-verify origin issue-5',
    'git -c core.hooksPath=/dev/null push origin issue-5',
    'git config core.hooksPath /dev/null',
    'FOO=1 git push origin main',
    'sh -c "git push origin main"',
    'eval git push origin main',
    'bash -c \'gh pr merge 5\'',
    'git push origin "main',                       # open quote: cannot be read, so blocked
]

ALLOWED = [
    'git push -u origin issue-12-fix',
    'git push -u origin issue-12-fix && gh pr create --base main --fill',
    'git commit -m "tidy main loop" && git push -u origin issue-12-fix',
    'git push origin maintenance-x',
    'git push origin --delete issue-12-fix',
    'git fetch origin main',
    'git diff origin/main...HEAD',
    'grep -rn "gh pr merge" docs',
    'gh pr comment 51 --body "never use gh pr merge here"',
    'gh pr view 51',
    'gh pr checks 51 --watch',
    'gh api repos/DrakeAnglin/tilt/pulls/51/files',
    'tools/agent/merge_pr.sh 51',
    'ls main',
    'echo "git push origin main"',
]


class Guard(unittest.TestCase):
    def test_blocked(self):
        for line in BLOCKED:
            self.assertIsNotNone(guard.check(line, cwd='/'), line)

    def test_allowed(self):
        for line in ALLOWED:
            self.assertIsNone(guard.check(line, cwd='/'), line)


if __name__ == '__main__':
    unittest.main()
