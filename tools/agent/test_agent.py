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
    'gh pr edit 51 --add-label two-way-door --remove-label one-way-door',
    'gh pr edit 51 --remove-label=one-way-door',
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

class OnlyAddsTests(unittest.TestCase):
    """tools/agent/only_adds_tests.awk: may an agent merge this change to a test script?"""

    AWK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'only_adds_tests.awk')

    def ok(self, patch):
        import subprocess
        return subprocess.run(['awk', '-f', self.AWK], input=patch, text=True).returncode == 0

    ADD = ('@@ -1,7 +1,9 @@\n #!/bin/sh\n-# Run the logic tests.\n+# Run the logic tests and the link test.\n'
           ' set -e\n "$OUT/logic_test"\n+c++ -std=c++17 -o "$OUT/link_test" link_test.cpp\n+"$OUT/link_test"\n')

    def test_adding_a_test_is_fine(self):
        self.assertTrue(self.ok(self.ADD))

    def test_removing_a_command_is_not(self):
        self.assertFalse(self.ok('@@ -1,3 +1,2 @@\n set -e\n-"$OUT/logic_test"\n'))
        self.assertFalse(self.ok('@@ -1,3 +1,2 @@\n-set -e\n "$OUT/logic_test"\n'))
        self.assertFalse(self.ok('@@ -1,2 +1,2 @@\n-#!/bin/sh\n+#!/bin/bash\n'))

    def test_hiding_a_failure_is_not(self):
        for line in ['"$OUT/link_test" || true', '"$OUT/link_test" ||:', 'set +e', 'exit 0',
                     'if x; then exit; fi', 'exec true', 'a && exit 0; b',
                     '"$X" || echo skipped', '"$X" || return 0', 'set +o errexit', 'trap "exit 0" EXIT',
                     '"$X" &', '[ -f x ] || { echo no; exit 1; }',
                     '"$X" | tee log', '"$X" && echo ok', '! "$X"', 'if "$X"; then :; fi', 'set -n',
                     'exit 256', 'if false; then', ": <<'EOF'", 'c++() { :; }', 'cd /', 'echo hi',
                     'c++ -o "$OUT/a" a.cpp \\', '"$OUT/a" \'', 'c++ -o "$OUT/a a.cpp',
                     '"$OUT/t" "a\' "b\'', '"$OUT/t" \'a" \'b"']:
            self.assertFalse(self.ok('@@ -1,1 +1,2 @@\n set -e\n+' + line + '\n'), line)

    def test_a_cleanup_trap_is_fine(self):
        self.assertTrue(self.ok('@@ -1,1 +1,2 @@\n set -e\n+trap \'rm -rf "$OUT"\' EXIT\n'))

    def test_a_minus_minus_line_is_still_read(self):
        # A removed line starting with "--" looks like a file header; inside a hunk it is a removed line.
        self.assertFalse(self.ok('--- a/x\n+++ b/x\n@@ -1,2 +1,1 @@\n set -e\n---verbose "$OUT/t"\n'))

    def test_generator_and_run_with_args_are_fine(self):
        self.assertTrue(self.ok('@@ -1,1 +1,3 @@\n set -e\n+python3 make_ota_files.py "$OUT"\n+"$OUT/ota_test" "$OUT"\n'))

    def test_quotes_inside_quotes_are_fine(self):
        self.assertTrue(self.ok('@@ -1,1 +1,2 @@\n set -e\n+"$OUT/t" "it\'s" \'say "hi"\'\n'))

    def test_an_empty_patch_is_not(self):
        self.assertFalse(self.ok(''))

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


FAKE_GH = '''#!/usr/bin/env python3
import sys, json, subprocess
d = json.loads(open(sys.argv[0] + ".json").read())
a = sys.argv[1:]
def out(v):
    if "--jq" in a:
        subprocess.run(["jq", "-c", a[a.index("--jq") + 1]], input=json.dumps(v), text=True)
    else:
        print(json.dumps(v))
if a[:2] == ["pr", "view"]: out(d["pr"])
elif a[:2] == ["pr", "checks"]: out(d["checks"])
elif a[:2] == ["api", "user"]: print("me")
elif a[0] == "api": out(d["files"])
else: sys.exit("unexpected gh " + " ".join(a))
'''


class MergeScriptTest(unittest.TestCase):
    """tools/agent/merge_pr.sh --check with a fake gh: whether the two agents agree decides, not which files."""

    def run_check(self, review, files=('tools/agent/merge_pr.sh', 'docs/agents/review-policy.md')):
        import subprocess, tempfile, json
        here = os.path.dirname(os.path.abspath(__file__))
        sha = 'a' * 40
        me = lambda body: {'author': {'login': 'me'}, 'body': body}
        pr = {'number': 7, 'state': 'OPEN', 'isDraft': False, 'isCrossRepository': False, 'baseRefName': 'main',
              'headRefName': 'b', 'headRefOid': sha, 'mergeable': 'MERGEABLE', 'additions': 1, 'deletions': 1,
              'labels': [], 'comments': [
                  me('<!-- factory-review sha=%s door=two-way blast=small %s -->' % (sha, review)),
                  me('<!-- factory-gate sha=%s verdict=merge -->' % sha)]}
        data = {'pr': pr, 'checks': [{'name': 'ci', 'bucket': 'pass'}],
                'files': [{'filename': f, 'additions': 1, 'deletions': 1, 'status': 'modified', 'patch': ''} for f in files]}
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'gh')
            with open(fake, 'w') as f:
                f.write(FAKE_GH)
            with open(fake + '.json', 'w') as f:
                json.dump(data, f)
            os.chmod(fake, 0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'])
            r = subprocess.run([os.path.join(here, 'merge_pr.sh'), '7', '--check'], env=env, capture_output=True, text=True)
            return r.returncode, r.stdout + r.stderr

    def test_an_agreed_change_to_the_rules_merges(self):
        code, out = self.run_check('must-fix=0 stuck=0')
        self.assertEqual(code, 0, out)
        self.assertIn('passes every rule', out)

    def test_a_review_without_stuck_still_reads(self):
        code, out = self.run_check('must-fix=0')
        self.assertEqual(code, 0, out)

    def test_no_agreement_goes_to_a_human(self):
        code, out = self.run_check('must-fix=1 stuck=1')
        self.assertEqual(code, 1, out)
        self.assertIn('A human decides', out)
        self.assertIn('cannot agree', out)

    def test_open_findings_go_back_to_the_author(self):
        code, out = self.run_check('must-fix=2 stuck=0')
        self.assertEqual(code, 1, out)
        self.assertNotIn('A human decides', out)
        self.assertIn('answer them on the pull request', out)

    def test_a_test_script_change_still_goes_to_a_human(self):
        code, out = self.run_check('must-fix=0 stuck=0', files=('tools/firmware_tests.sh',))
        self.assertEqual(code, 1, out)
        self.assertIn('How the tests run changed', out)

CLAIM_GH = """#!/usr/bin/env python3
import json, os, sys, time
state_file = os.environ['CLAIM_STATE']
st = json.load(open(state_file))
a = sys.argv[1:]
out = ''
now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
if a[:2] == ['api', 'user']:
    out = st['me']
elif a[0] == 'api' and a[1] == '--paginate':
    out = json.dumps(st['comments'])
elif a[:3] == ['api', '-X', 'DELETE']:
    cid = int(a[3].rsplit('/', 1)[1])
    st['comments'] = [c for c in st['comments'] if c['id'] != cid]
elif a[:3] == ['api', '-X', 'PATCH']:
    cid = int(a[3].rsplit('/', 1)[1])
    for c in st['comments']:
        if c['id'] == cid:
            c['body'] = a[5][len('body='):]
            c['updated_at'] = now
elif a[:2] == ['issue', 'comment']:
    st['next'] += 1
    st['comments'].append({'id': st['next'], 'user': {'login': st['me']}, 'body': a[4], 'created_at': now, 'updated_at': now})
    if st.get('rival'):  # another agent posts in the same moment, a little earlier
        st['comments'].insert(len(st['comments']) - 1, st.pop('rival'))
elif a[:2] == ['pr', 'list']:
    out = json.dumps(st['prs'])
json.dump(st, open(state_file, 'w'))
print(out)
"""


class ClaimTest(unittest.TestCase):
    """tools/agent/claim.py: one agent per issue."""

    def at(self, hours_ago):
        import datetime
        t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
        return t.strftime('%Y-%m-%dT%H:%M:%SZ')

    def claim_comment(self, cid, claim_id, hours_ago=0, login='me'):
        t = self.at(hours_ago)
        return {'id': cid, 'user': {'login': login}, 'body': 'x <!-- agent-claim id=%s -->' % claim_id,
                'created_at': t, 'updated_at': t}

    def run_claim(self, comments=(), prs=(), args=('5', 'loop-a'), rival=None):
        import subprocess, tempfile, json
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'gh')
            with open(fake, 'w') as f:
                f.write(CLAIM_GH)
            os.chmod(fake, 0o755)
            state = os.path.join(tmp, 'state.json')
            with open(state, 'w') as f:
                json.dump({'me': 'me', 'comments': list(comments), 'prs': list(prs), 'next': 100, 'rival': rival}, f)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'], CLAIM_STATE=state)
            r = subprocess.run([sys.executable, os.path.join(here, 'claim.py'), *args], env=env,
                               capture_output=True, text=True)
            with open(state) as f:
                return r.returncode, r.stdout + r.stderr, json.load(f)['comments']

    def ids(self, comments):
        import re
        return [re.search(r'id=(\S+) -->', c['body']).group(1) for c in comments if 'agent-claim' in c['body']]

    def test_a_free_issue_is_claimed(self):
        code, out, comments = self.run_claim()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(comments), ['loop-a'])

    def test_a_live_claim_by_another_agent_blocks(self):
        code, out, comments = self.run_claim([self.claim_comment(1, 'work-b', hours_ago=1)])
        self.assertEqual(code, 3, out)
        self.assertIn('work-b', out)
        self.assertEqual(self.ids(comments), ['work-b'])

    def test_a_stale_claim_does_not_block(self):
        code, out, comments = self.run_claim([self.claim_comment(1, 'work-b', hours_ago=5)])
        self.assertEqual(code, 0, out)

    def test_a_claim_from_a_stranger_does_not_count(self):
        code, out, _ = self.run_claim([self.claim_comment(1, 'x', login='stranger')])
        self.assertEqual(code, 0, out)

    def test_claiming_again_refreshes_and_does_not_post_twice(self):
        code, out, comments = self.run_claim([self.claim_comment(1, 'loop-a', hours_ago=2)])
        self.assertEqual(code, 0, out)
        self.assertEqual([c['id'] for c in comments], [1])
        self.assertEqual(comments[0]['updated_at'][:13], self.at(0)[:13])

    def test_an_open_pull_request_blocks_unless_resuming(self):
        prs = [{'number': 9, 'closingIssuesReferences': [{'number': 5}]}]
        code, out, _ = self.run_claim(prs=prs)
        self.assertEqual(code, 3, out)
        self.assertIn('#9', out)
        code, out, _ = self.run_claim(prs=prs, args=('5', 'loop-a', '--resume'))
        self.assertEqual(code, 0, out)

    def test_two_at_once_the_earlier_wins_and_the_other_backs_off(self):
        code, out, comments = self.run_claim(rival=self.claim_comment(50, 'work-b'))
        self.assertEqual(code, 3, out)
        self.assertEqual(self.ids(comments), ['work-b'])

    def test_release_takes_the_claim_off(self):
        code, out, comments = self.run_claim([self.claim_comment(1, 'loop-a')], args=('5', 'loop-a', '--release'))
        self.assertEqual(code, 0, out)
        self.assertEqual(comments, [])

    def test_bad_arguments(self):
        code, _, _ = self.run_claim(args=('five', 'loop-a'))
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
