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
    '# ship it\ngit push origin main',
    'git status # check\ngit push origin HEAD:main',
    '# merge\ngh pr merge 51 --squash',
    'git push origin \\\nmain',
    'gh \\\npr merge 51',
    'if tools/agent/check.sh; then git push origin main; fi',
    'for p in 51; do gh pr merge $p --squash; done',
    'true && { git push origin main; }',
    '! git push origin main',
    'bash -lc "gh pr merge 51"',
    'sh -ec "git push origin main"',
    'timeout 60 git push origin main',
    'echo 51 | xargs gh pr merge',
    'echo `git push origin main`',
    'echo $(gh pr merge 51)',
    'git checkout main && git merge issue-5 && git push',
    'git push origin heads/main',
    'git push origin main 2>&1 | tail -3',
    'git push origin HEAD:main > /dev/null',
    'git checkout main && git merge issue-5 && git push 2>&1 | tail -3',
    'git config --unset core.hooksPath',
    'git push --branches origin',
    'git -ccore.hooksPath=/x push origin issue-5',
    'GIT_CONFIG_COUNT=1 git push origin issue-5',
    'gh api -X POST repos/DrakeAnglin/tilt/merges',
    'gh api -X PATCH repos/DrakeAnglin/tilt/git/refs/heads/main -f sha=abc',
    'gh pr edit 51 --remove-label needs-human',
    'gh pr edit 51 --add-label auto-merge-ok --remove-label needs-human',
    'gh pr edit 51 --remove-label=one-way-door',
    "cat > f <<'EOF'\ntext\nEOF\ngit push origin main",
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
    "cat > /tmp/body.md <<'EOF'\nIt doesn't matter what is in here.\ngh pr merge 51\ngit push origin main\nEOF",
    "git commit -F - <<'EOF'\nDon't push to main\nEOF",
    'gh pr comment 51 --body-file - <<EOF\nA lone " quote\nEOF\ngit status',
    'git config --get core.hooksPath',
    'git push origin fix/main',
    'git checkout -b issue-12 main && git push -u origin HEAD',
    'GIT_CONFIG_GLOBAL=/dev/null git status',
    'git push -u origin issue-12 2>&1 | tail -3',
    'tools/agent/check.sh > /tmp/out.txt 2>&1',
    'git config core.hooksPath .githooks',
    'gh api repos/DrakeAnglin/tilt/pulls/51/merge',
    'gh pr edit 51 --add-label needs-human',
    'gh pr edit 51 --remove-label auto-merge-ok',
    'gh pr edit 51 --add-label two-way-door',
    'timeout 60 tools/agent/check.sh',
    'if git diff --quiet; then echo clean; fi',
    'git commit -m "first line\n\nsecond; line # not a comment"',
]


class Guard(unittest.TestCase):
    def test_blocked(self):
        for line in BLOCKED:
            self.assertIsNotNone(guard.check(line, cwd='/'), line)

    def test_allowed(self):
        for line in ALLOWED:
            self.assertIsNone(guard.check(line, cwd='/'), line)


    def test_plain_push_from_main(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(['git', 'init', '-q', '-b', 'main', repo], check=True)
            for line in ['git push', 'git push 2>&1', 'git push > /dev/null', 'git push origin 2>&1 | tail',
                         'git commit -am x && git push 2>&1 | tail -3', 'git push -u origin HEAD']:
                self.assertIsNotNone(guard.check(line, cwd=repo), line)
            subprocess.run(['git', '-C', repo, 'checkout', '-q', '-b', 'issue-5'], check=True)
            for line in ['git push', 'git push 2>&1 | tail -3', 'git push -u origin HEAD']:
                self.assertIsNone(guard.check(line, cwd=repo), line)

    def test_bad_input_blocks(self):
        import subprocess
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'guard.py')
        run = lambda text: subprocess.run([sys.executable, script], input=text, capture_output=True, text=True).returncode
        self.assertEqual(run('not json'), 2)
        self.assertEqual(run('{"tool_input": {"command": "ls"}}'), 0)
        self.assertEqual(run('{"tool_input": {"command": "gh pr merge 5"}}'), 2)


class ShellSyntaxTest(unittest.TestCase):
    def test_agent_scripts_parse(self):
        import glob, subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        for script in sorted(glob.glob(os.path.join(here, '*.sh'))):
            r = subprocess.run(['sh', '-n', script], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, script + ': ' + r.stderr)


class CleanWorktreesTest(unittest.TestCase):
    """tools/agent/clean_worktrees.sh with a fake gh."""

    def test_removes_only_finished_clean_worktrees(self):
        import subprocess, tempfile, json
        here = os.path.dirname(os.path.abspath(__file__))
        script = os.path.join(here, 'clean_worktrees.sh')
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.realpath(os.path.join(tmp, 'repo'))
            git = lambda *a, cwd=repo: subprocess.run(['git', '-C', cwd, *a], check=True, capture_output=True, text=True).stdout.strip()
            os.makedirs(repo)
            git('init', '-q', '-b', 'main')
            git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '--allow-empty', '-m', 'root')
            wts = os.path.join(repo, '.claude', 'worktrees')
            prs = {}
            git('worktree', 'add', '-q', '--detach', os.path.join(wts, 'loose'))
            for name, state in [('done', 'MERGED'), ('closed', 'CLOSED'), ('open', 'OPEN'), ('dirty', 'MERGED'), ('extra', 'MERGED'), ('nopr', None)]:
                path = os.path.join(wts, name)
                git('worktree', 'add', '-q', '-b', 'b-' + name, path)
                git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '--allow-empty', '-m', name, cwd=path)
                if state:
                    prs['b-' + name] = {'number': len(prs) + 1, 'state': state, 'headRefOid': git('rev-parse', 'HEAD', cwd=path)}
            with open(os.path.join(wts, 'dirty', 'new.txt'), 'w') as f:
                f.write('x')
            git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '--allow-empty', '-m', 'after', cwd=os.path.join(wts, 'extra'))
            os.makedirs(os.path.join(wts, 'done', 'firmware', 'x', 'build'))
            # Fake gh: answers "gh pr list --head <branch> ... --jq <expr>" from the table above.
            bin_dir = os.path.join(tmp, 'bin')
            os.makedirs(bin_dir)
            fake = os.path.join(bin_dir, 'gh')
            with open(fake, 'w') as f:
                f.write('#!/usr/bin/env python3\nimport sys, json\nprs = json.loads(%r)\na = sys.argv\nb = a[a.index("--head") + 1]\np = prs.get(b)\nprint(f"{p[\'number\']} {p[\'state\']} {p[\'headRefOid\']}" if p else "")\n' % json.dumps(prs))
            os.chmod(fake, 0o755)
            env = dict(os.environ, PATH=bin_dir + os.pathsep + os.environ['PATH'])
            out = subprocess.run([script], cwd=repo, env=env, capture_output=True, text=True).stdout
            left = sorted(os.listdir(wts))
            self.assertEqual(left, ['dirty', 'extra', 'loose', 'nopr', 'open'], out)
            branches = git('branch', '--format=%(refname:short)').split()
            self.assertNotIn('b-done', branches)
            self.assertNotIn('b-closed', branches)
            self.assertIn('b-open', branches)


if __name__ == '__main__':
    unittest.main()
