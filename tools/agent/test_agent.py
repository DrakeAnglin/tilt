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
    """tools/agent/clean_worktrees.sh in a throwaway repo, with a fake gh and the build lock in a temp folder."""

    def setUp(self):
        import tempfile
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = os.path.realpath(t.name)
        self.repo = os.path.join(self.tmp, 'repo')
        self.wts = os.path.join(self.repo, '.claude', 'worktrees')
        self.lock = os.path.join(self.tmp, 'build.lock')
        self.heads, self.search = {}, {}  # gh pr list --head <branch> / --search <sha>
        os.makedirs(self.repo)
        self.git('init', '-q', '-b', 'main')
        with open(os.path.join(self.repo, '.gitignore'), 'w') as f:
            f.write('build/\n')
        self.git('add', '.gitignore')
        self.commit('root')

    def git(self, *a, cwd=None):
        import subprocess
        return subprocess.run(['git', '-C', cwd or self.repo, *a], check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, msg, cwd=None):
        self.git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-q', '--allow-empty', '-m', msg, cwd=cwd)
        return self.git('rev-parse', 'HEAD', cwd=cwd)

    def add(self, name, branch=None):
        """A worktree with one commit of its own (detached when no branch); returns (path, HEAD)."""
        path = os.path.join(self.wts, name)
        if branch:
            self.git('worktree', 'add', '-q', '-b', branch, path)
        else:
            self.git('worktree', 'add', '-q', '--detach', path)
        return path, self.commit(name, cwd=path)

    def pr(self, state, head, branch=None, by_commit=None):
        p = {'number': 100 + len(self.heads) + len(self.search), 'state': state, 'headRefOid': head}
        if branch:
            self.heads[branch] = p
        if by_commit:
            self.search.setdefault(by_commit, []).append(p)

    def build_folder(self, path):
        b = os.path.join(path, 'firmware', 'x', 'build')
        os.makedirs(b)
        with open(os.path.join(b, 'out.bin'), 'w') as f:
            f.write('x')
        return b

    def session_lock(self, path, pid):
        self.git('worktree', 'lock', '--reason', 'claude session t (pid %d)' % pid, path)

    def dead_pid(self):
        import subprocess
        p = subprocess.Popen(['true'])
        p.wait()
        return p.pid

    def run_clean(self, *args, **env_extra):
        import subprocess, json
        bin_dir = os.path.join(self.tmp, 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        fake = os.path.join(bin_dir, 'gh')
        with open(fake + '.json', 'w') as f:
            json.dump({'heads': self.heads, 'search': self.search}, f)
        # Fake gh: prints what the script's --jq would make of "gh pr list --head <branch>" or "--search <sha>".
        with open(fake, 'w') as f:
            f.write('#!/usr/bin/env python3\nimport sys, json\nd = json.load(open(sys.argv[0] + ".json"))\na = sys.argv\n'
                    'line = lambda p: print(f"{p[\'number\']} {p[\'state\']} {p[\'headRefOid\']}")\n'
                    'if "--head" in a:\n    p = d["heads"].get(a[a.index("--head") + 1])\n    p and line(p)\n'
                    'elif "--search" in a:\n    [line(p) for p in d["search"].get(a[a.index("--search") + 1], [])]\n'
                    'else:\n    sys.exit("unexpected gh " + " ".join(a[1:]))\n')
        os.chmod(fake, 0o755)
        env = dict(os.environ, PATH=bin_dir + os.pathsep + os.environ['PATH'], TILT_BUILD_LOCK=self.lock)
        env.pop('TILT_BUILD_LOCK_HELD', None)
        env.update(env_extra)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clean_worktrees.sh')
        r = subprocess.run([script, *args], cwd=self.repo, env=env, capture_output=True, text=True)
        return r.stdout + r.stderr

    def left(self):
        return sorted(os.listdir(self.wts))

    def branches(self):
        return self.git('branch', '--format=%(refname:short)').split()

    def test_removes_only_finished_clean_worktrees(self):
        self.add('loose')
        for name, state in [('done', 'MERGED'), ('closed', 'CLOSED'), ('open', 'OPEN'), ('dirty', 'MERGED'), ('extra', 'MERGED'), ('nopr', None)]:
            path, head = self.add(name, 'b-' + name)
            if state:
                self.pr(state, head, branch='b-' + name)
        with open(os.path.join(self.wts, 'dirty', 'new.txt'), 'w') as f:
            f.write('x')
        self.commit('after', cwd=os.path.join(self.wts, 'extra'))
        self.build_folder(os.path.join(self.wts, 'done'))
        out = self.run_clean()
        self.assertEqual(self.left(), ['dirty', 'extra', 'loose', 'nopr', 'open'], out)
        self.assertNotIn('b-done', self.branches())
        self.assertNotIn('b-closed', self.branches())
        self.assertIn('b-open', self.branches())

    def test_finds_the_pull_request_by_head_commit_when_the_branch_name_differs(self):
        path, head = self.add('renamed', 'worktree-renamed')
        self.pr('MERGED', head, branch='renamed', by_commit=head)
        out = self.run_clean()
        self.assertEqual(self.left(), [], out)
        self.assertNotIn('worktree-renamed', self.branches())

    def test_a_detached_head_goes_only_with_a_finished_pull_request(self):
        _, head = self.add('det-done')
        self.pr('MERGED', head, by_commit=head)
        self.add('det-none')
        out = self.run_clean()
        self.assertEqual(self.left(), ['det-none'], out)

    def test_found_by_commit_but_with_one_more_commit_is_kept(self):
        path, first = self.add('moved', 'worktree-moved')
        now = self.commit('one more', cwd=path)
        self.pr('MERGED', first, branch='moved', by_commit=now)
        out = self.run_clean()
        self.assertEqual(self.left(), ['moved'], out)

    def test_an_open_pull_request_with_the_same_head_wins(self):
        path, head = self.add('twice', 'worktree-twice')
        self.pr('CLOSED', head, by_commit=head)
        self.pr('OPEN', head, by_commit=head)
        out = self.run_clean()
        self.assertEqual(self.left(), ['twice'], out)
        self.assertIn('worktree-twice', self.branches())

    def test_a_session_lock_with_no_pid_keeps_the_worktree(self):
        path, head = self.add('nopid', 'b-nopid')
        self.pr('MERGED', head, branch='b-nopid')
        self.git('worktree', 'lock', '--reason', 'claude session t', path)
        out = self.run_clean()
        self.assertEqual(self.left(), ['nopid'], out)
        self.assertIn('keep   nopid: a session is in it', out)

    def test_a_session_lock_whose_pid_is_gone_is_taken_off(self):
        path, head = self.add('stale', 'b-stale')
        self.pr('MERGED', head, branch='b-stale')
        self.session_lock(path, self.dead_pid())
        out = self.run_clean()
        self.assertEqual(self.left(), [], out)
        self.assertNotIn('b-stale', self.branches())

    def test_a_live_session_keeps_its_worktree_but_not_its_build_folder(self):
        path, head = self.add('live', 'b-live')
        self.pr('MERGED', head, branch='b-live')
        self.session_lock(path, os.getpid())
        build = self.build_folder(path)
        dry = self.run_clean('--dry-run')
        self.assertIn('keep   live: a session is in it', dry)
        self.assertNotIn('would remove', dry)
        self.assertTrue(os.path.exists(build))
        out = self.run_clean()
        self.assertIn('keep   live: a session is in it', out)
        self.assertEqual(self.left(), ['live'], out)
        self.assertFalse(os.path.exists(build), out)

    def test_a_kept_worktree_loses_only_its_build_folder(self):
        path, _ = self.add('nopr', 'b-nopr')
        build = self.build_folder(path)
        other = os.path.join(path, 'firmware', 'x', 'main.c')
        with open(other, 'w') as f:
            f.write('x')
        out = self.run_clean()
        self.assertEqual(self.left(), ['nopr'], out)
        self.assertFalse(os.path.exists(build), out)
        self.assertTrue(os.path.exists(other))
        self.assertIn('trimmed nopr: build folders', out)
        self.assertNotIn('trimmed', self.run_clean())  # nothing left to trim: nothing said

    def test_a_live_session_with_an_open_pull_request_keeps_its_build_folder(self):
        path, head = self.add('busy', 'b-busy')
        self.pr('OPEN', head, branch='b-busy')
        self.session_lock(path, os.getpid())
        build = self.build_folder(path)
        out = self.run_clean()
        self.assertTrue(os.path.exists(build), out)
        self.assertNotIn('trimmed', out)

    def test_no_trim_while_a_build_holds_the_lock(self):
        path, _ = self.add('nopr', 'b-nopr')
        build = self.build_folder(path)
        os.makedirs(self.lock)
        with open(os.path.join(self.lock, 'pid'), 'w') as f:
            f.write(str(os.getpid()))
        out = self.run_clean()
        self.assertTrue(os.path.exists(build), out)
        self.assertIn('not trimmed', out)
        self.assertTrue(os.path.exists(self.lock))
        out = self.run_clean(TILT_BUILD_LOCK_HELD='1')
        self.assertFalse(os.path.exists(build), out)

    def test_takes_a_stale_build_lock_to_trim_and_gives_it_back(self):
        path, _ = self.add('nopr', 'b-nopr')
        build = self.build_folder(path)
        os.makedirs(self.lock)
        with open(os.path.join(self.lock, 'pid'), 'w') as f:
            f.write(str(self.dead_pid()))
        out = self.run_clean()
        self.assertFalse(os.path.exists(build), out)
        self.assertFalse(os.path.exists(self.lock), out)

    def test_dry_run_removes_nothing(self):
        p1, h1 = self.add('renamed', 'worktree-renamed')
        self.pr('MERGED', h1, branch='renamed', by_commit=h1)
        p2, h2 = self.add('stale', 'b-stale')
        self.pr('MERGED', h2, branch='b-stale')
        self.session_lock(p2, self.dead_pid())
        p3, _ = self.add('nopr', 'b-nopr')
        builds = [self.build_folder(p) for p in (p1, p2, p3)]
        out = self.run_clean('--dry-run')
        self.assertEqual(self.left(), ['nopr', 'renamed', 'stale'], out)
        self.assertTrue(all(os.path.exists(b) for b in builds), out)
        self.assertIn('would remove renamed', out)
        self.assertIn('would remove stale', out)
        self.assertIn('would trim nopr: build folders', out)
        self.assertFalse(os.path.exists(self.lock))


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

    def run_check(self, review, files=('tools/agent/merge_pr.sh', 'docs/agents/review-policy.md'), labels=(), env_extra=None, rounds=0):
        import subprocess, tempfile, json
        here = os.path.dirname(os.path.abspath(__file__))
        sha = 'a' * 40
        me = lambda body: {'author': {'login': 'me'}, 'body': body}
        earlier = [me('<!-- factory-review sha=%s door=two-way blast=small must-fix=0 stuck=0 round=merge -->' % ('b' * 40))] * rounds
        pr = {'number': 7, 'state': 'OPEN', 'isDraft': False, 'isCrossRepository': False, 'baseRefName': 'main',
              'headRefName': 'b', 'headRefOid': sha, 'mergeable': 'MERGEABLE', 'additions': 1, 'deletions': 1,
              'labels': [{'name': n} for n in labels], 'comments': earlier + [
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
            # MERGE_PR_FROM_MAIN: test this copy, not main's.
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'], MERGE_PR_FROM_MAIN='1', **(env_extra or {}))
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

    def test_the_label_still_stops_a_merge(self):
        code, out = self.run_check('must-fix=0 stuck=0', labels=('needs-human',))
        self.assertEqual(code, 1, out)
        self.assertIn('has the needs-human label', out)

    def test_the_stale_label_question_ignores_the_label(self):
        code, out = self.run_check('must-fix=0 stuck=0', labels=('needs-human',), env_extra={'IGNORE_NEEDS_HUMAN': '1'})
        self.assertEqual(code, 0, out)

    def test_looks_after_a_merge_from_main_do_not_count(self):
        code, out = self.run_check('must-fix=0 stuck=0', rounds=12)
        self.assertEqual(code, 0, out)


FAKE_GH_LABEL = r'''#!/usr/bin/env python3
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
a = sys.argv[1:]
if a[:2] == ['pr', 'view']:
    print(open(os.path.join(here, 'pr.json')).read())
elif a[:2] == ['api', 'user']:
    print('me')
else:
    with open(os.path.join(here, 'calls.log'), 'a') as f:
        f.write(' '.join(a) + '\n')
'''


class ClearStaleLabelTest(unittest.TestCase):
    """tools/agent/clear_stale_label.sh with a fake gh and a fake merge_pr.sh."""

    def run_clear(self, rules_say, comments=(), rc=1):
        import subprocess, tempfile, json, shutil
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(here, 'clear_stale_label.sh'), tmp)
            with open(os.path.join(tmp, 'merge_pr.sh'), 'w') as f:
                f.write('#!/bin/sh\n[ "$IGNORE_NEEDS_HUMAN" = 1 ] || exit 9\necho "%s"\nexit %d\n' % (rules_say, rc))
            with open(os.path.join(tmp, 'gh'), 'w') as f:
                f.write(FAKE_GH_LABEL)
            for n in ('merge_pr.sh', 'gh'):
                os.chmod(os.path.join(tmp, n), 0o755)
            with open(os.path.join(tmp, 'pr.json'), 'w') as f:
                json.dump({'headRefOid': 'c' * 40, 'labels': [{'name': 'needs-human'}],
                           'comments': [{'author': {'login': who}, 'body': b} for who, b in comments]}, f)
            # CLEAR_FROM_MAIN: test this copy, not main's.
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'], CLEAR_FROM_MAIN='1')
            r = subprocess.run([os.path.join(tmp, 'clear_stale_label.sh'), '7'], env=env, capture_output=True, text=True)
            log = ''
            if os.path.exists(os.path.join(tmp, 'calls.log')):
                with open(os.path.join(tmp, 'calls.log')) as f:
                    log = f.read()
            return r.returncode, r.stdout + r.stderr, log

    def test_every_rule_passing_frees_it(self):
        code, out, log = self.run_clear('#7 passes every rule.', rc=0)
        self.assertEqual(code, 0, out)
        self.assertIn('remove-label needs-human', log)

    def test_an_error_keeps_it(self):
        code, out, log = self.run_clear('gh: API rate limit exceeded')
        self.assertEqual(code, 1, out)
        self.assertNotIn('remove-label', log)

    def test_a_sticky_verdict_keeps_it(self):
        marker = '<!-- factory-gate sha=%s verdict=human sticky=1 -->' % ('d' * 40)
        code, out, log = self.run_clear('Not merging #7 yet:\n- the review is for an older commit', comments=(('me', marker),))
        self.assertEqual(code, 1, out)
        self.assertNotIn('remove-label', log)

    def test_a_stranger_cannot_hold_it(self):
        code, out, log = self.run_clear('Not merging #7 yet:', comments=(('stranger', '/hold'),))
        self.assertEqual(code, 0, out)
        self.assertIn('remove-label', log)

    def test_a_label_with_no_reason_left_comes_off(self):
        code, out, log = self.run_clear('Not merging #7 yet:\n- the review is for an older commit')
        self.assertEqual(code, 0, out)
        self.assertIn('pr edit 7 --remove-label needs-human', log)
        self.assertIn('pr comment 7', log)

    def test_a_label_the_rules_still_need_stays(self):
        code, out, log = self.run_clear('Not merging #7. A human decides:\n- cannot agree')
        self.assertEqual(code, 1, out)
        self.assertNotIn('remove-label', log)

    def test_the_owner_can_hold_it(self):
        code, out, log = self.run_clear('Not merging #7 yet:', comments=(('me', '/hold until the bench'),))
        self.assertEqual(code, 1, out)
        self.assertNotIn('remove-label', log)


class BuildLockTest(unittest.TestCase):
    def test_runs_the_command_and_lets_go(self):
        import subprocess, tempfile
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, 'lock')
            env = dict(os.environ, TILT_BUILD_LOCK=lock, TILT_FREE_GB='10')
            r = subprocess.run([os.path.join(here, 'build_lock.sh'), 'sh', '-c', 'cat "$TILT_BUILD_LOCK/owner"; exit 3'],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn('pid', r.stdout)
            self.assertFalse(os.path.exists(lock))

    def test_a_nearly_full_disk_stops_before_the_build(self):
        import subprocess, tempfile
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, 'lock')
            ran = os.path.join(tmp, 'ran')
            env = dict(os.environ, TILT_BUILD_LOCK=lock, TILT_FREE_GB='2')
            env.pop('TILT_BUILD_LOCK_HELD', None)
            # cwd is not a Git checkout, so the cleanup it runs first has nothing to touch.
            r = subprocess.run([os.path.join(here, 'build_lock.sh'), 'touch', ran], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 75, r.stderr)
            self.assertFalse(os.path.exists(ran))
            self.assertFalse(os.path.exists(lock))
            self.assertIn('2 GB free', r.stderr)
            self.assertIn('clean_worktrees.sh --dry-run', r.stderr)
            self.assertIn('du -sh .claude/worktrees/*/firmware/*/build', r.stderr)

    def test_a_low_disk_runs_the_cleanup_under_the_lock_before_the_build(self):
        import subprocess, tempfile, shutil
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            # A copy of build_lock.sh next to a fake clean_worktrees.sh that says how it was run.
            shutil.copy(os.path.join(here, 'build_lock.sh'), tmp)
            seen = os.path.join(tmp, 'seen')
            with open(os.path.join(tmp, 'clean_worktrees.sh'), 'w') as f:
                f.write('#!/bin/sh\n[ -d "$TILT_BUILD_LOCK" ] && echo "held=$TILT_BUILD_LOCK_HELD" > "%s"\n' % seen)
            os.chmod(os.path.join(tmp, 'clean_worktrees.sh'), 0o755)
            lock = os.path.join(tmp, 'lock')
            env = dict(os.environ, TILT_BUILD_LOCK=lock)
            env.pop('TILT_BUILD_LOCK_HELD', None)
            build = ['sh', '-c', 'cat "%s"' % seen]
            r = subprocess.run([os.path.join(tmp, 'build_lock.sh'), *build], cwd=tmp, env=dict(env, TILT_FREE_GB='4'), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), 'held=1')
            os.remove(seen)
            r = subprocess.run([os.path.join(tmp, 'build_lock.sh'), 'true'], cwd=tmp, env=dict(env, TILT_FREE_GB='10'), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(os.path.exists(seen))  # enough disk: no cleanup

    def test_takes_a_lock_whose_holder_is_gone_but_not_a_live_one(self):
        import subprocess, tempfile
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, 'lock')
            dead = subprocess.Popen(['true'])
            dead.wait()
            os.makedirs(lock)
            with open(os.path.join(lock, 'pid'), 'w') as f:
                f.write(str(dead.pid))
            env = dict(os.environ, TILT_BUILD_LOCK=lock, TILT_FREE_GB='10')
            r = subprocess.run([os.path.join(here, 'build_lock.sh'), 'true'], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(os.path.exists(lock))
            # A live holder (this test) is waited for, not taken over.
            os.makedirs(lock)
            with open(os.path.join(lock, 'pid'), 'w') as f:
                f.write(str(os.getpid()))
            with self.assertRaises(subprocess.TimeoutExpired):
                subprocess.run([os.path.join(here, 'build_lock.sh'), 'true'], env=env, capture_output=True, timeout=3)
            self.assertTrue(os.path.exists(lock))


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
    half = len(st['comments']) // 2  # two pages, as gh prints them
    out = json.dumps(st['comments'][:half]) + json.dumps(st['comments'][half:])
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
elif a[0] == 'api' and a[1].endswith('/issues/5'):
    out = json.dumps(st.get('assignees', []))
elif a[:2] == ['issue', 'edit'] and '--remove-assignee' in a:
    st['assignees'] = []
elif a[:2] == ['issue', 'edit']:
    st['assignees'] = [st['me']]
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

    def run_claim(self, comments=(), prs=(), args=('5', 'loop-a'), rival=None, assignees=()):
        import subprocess, tempfile, json
        here = os.path.dirname(os.path.abspath(__file__))
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, 'gh')
            with open(fake, 'w') as f:
                f.write(CLAIM_GH)
            os.chmod(fake, 0o755)
            state = os.path.join(tmp, 'state.json')
            with open(state, 'w') as f:
                json.dump({'me': 'me', 'comments': list(comments), 'prs': list(prs), 'next': 100, 'rival': rival,
                           'assignees': list(assignees)}, f)
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
        code, out, comments = self.run_claim([self.claim_comment(1, 'loop-a')], args=('5', 'loop-a', '--release'),
                                             assignees=['me'])
        self.assertEqual(code, 0, out)
        self.assertEqual(comments, [])

    def test_text_that_looks_like_a_page_break_reads(self):
        odd = {'id': 2, 'user': {'login': 'x'}, 'body': '- [x] [ ] todo ] [ done', 'created_at': self.at(1), 'updated_at': self.at(1)}
        code, out, _ = self.run_claim([odd, self.claim_comment(3, 'work-b', hours_ago=1)])
        self.assertEqual(code, 3, out)
        self.assertIn('work-b', out)

    def test_assigned_with_no_claim_is_taken(self):
        code, out, _ = self.run_claim(assignees=['me'])
        self.assertEqual(code, 3, out)
        self.assertIn('assigned', out)

    def test_assigned_with_only_a_stale_claim_is_free(self):
        code, out, _ = self.run_claim([self.claim_comment(1, 'work-b', hours_ago=5)], assignees=['me'])
        self.assertEqual(code, 0, out)

    def test_refreshing_a_stale_own_claim_with_its_pull_request_open(self):
        prs = [{'number': 9, 'closingIssuesReferences': [{'number': 5}]}]
        code, out, comments = self.run_claim([self.claim_comment(1, 'loop-a', hours_ago=5)], prs=prs, assignees=['me'])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.ids(comments), ['loop-a'])

    def test_bad_arguments(self):
        code, _, _ = self.run_claim(args=('five', 'loop-a'))
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
