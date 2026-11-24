#!/usr/bin/env python3
"""Claude Code hook (before every shell command): stops the ways around the pull request rules.

Reads the hook's JSON on stdin. Exit 2 blocks the command and shows the message to the agent.
It looks at each command in the line on its own, so words inside a commit message or a grep do not count.
This is a seat belt, not a wall: branch protection on GitHub is the wall. Tests: tools/agent/test_agent.py
"""
import json
import os
import re
import shlex
import subprocess
import sys

MERGE = 'merge with tools/agent/merge_pr.sh <pr>, or leave it for the owner.'
MAIN = 'nothing is pushed to main; open a pull request.'
HOOK = 'no going around the pre-push hook.'
SEPARATORS = {';', '&&', '||', '|', '&', '(', ')', '|&', ';;', '\n'}
WRAPPERS = {'command', 'env', 'sudo', 'time', 'nohup', 'exec', 'builtin'}
SHELLS = {'sh', 'bash', 'zsh', 'dash'}
GIT_VALUE_FLAGS = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path'}
GH_VALUE_FLAGS = {'-R', '--repo'}
API_MERGE = re.compile(r'pulls/\d+/merge|mergePullRequest|enablePullRequestAutoMerge|merge-upstream', re.I)


def commands(line):
    """The simple commands in a shell line, each as a list of words."""
    lexer = shlex.shlex(line.replace('\n', ' ; '), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out, now = [], []
    for word in lexer:                      # raises ValueError on an open quote
        if word in SEPARATORS:
            out.append(now)
            now = []
        else:
            now.append(word)
    out.append(now)
    return [c for c in out if c]


def on_main(cwd):
    try:
        r = subprocess.run(['git', 'branch', '--show-current'], cwd=cwd or None, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == 'main'
    except Exception:
        return False


def check_git(args, cwd):
    sub, i = None, 0
    while i < len(args):
        a = args[i]
        if a == '-c' and i + 1 < len(args) and args[i + 1].lower().startswith('core.hookspath'):
            return HOOK
        if a == '-C' and i + 1 < len(args):
            cwd = os.path.join(cwd or '', args[i + 1])
        if a in GIT_VALUE_FLAGS:
            i += 2
        elif a.startswith('-'):
            i += 1
        else:
            sub, args = a, args[i + 1:]
            break
    if sub == 'config' and any(a.lower().startswith('core.hookspath') for a in args):
        return HOOK
    if sub != 'push':
        return None
    if '--no-verify' in args:
        return HOOK
    if '--all' in args or '--mirror' in args:
        return MAIN
    names = [a for a in args if not a.startswith('-')]
    refs = names[1:]                        # names[0] is the remote
    for ref in refs:
        to = ref.lstrip('+').split(':')[-1]
        if to in ('main', 'refs/heads/main'):
            return MAIN
    if (not refs or 'HEAD' in refs) and on_main(cwd):
        return MAIN
    return None


def check_gh(args):
    words, i = [], 0
    while i < len(args):
        if args[i] in GH_VALUE_FLAGS:
            i += 2
        elif args[i].startswith('-'):
            i += 1
        else:
            words.append(args[i])
            i += 1
    if words[:2] == ['pr', 'merge']:
        return MERGE
    if words[:1] == ['api'] and any(API_MERGE.search(a) for a in args):
        return MERGE
    return None


def check(line, cwd=None, depth=0):
    """Why this command line is blocked, or None when it is fine."""
    try:
        cmds = commands(line)
    except ValueError:
        return 'could not read this command (open quote?). Write it more simply.'
    for words in cmds:
        while words and (words[0] in WRAPPERS or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', words[0])):
            words = words[1:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        why = None
        if name == 'git':
            why = check_git(args, cwd)
        elif name == 'gh':
            why = check_gh(args)
        elif name == 'curl' and any(API_MERGE.search(a) for a in args):
            why = MERGE
        elif depth < 3 and (name == 'eval' or (name in SHELLS and '-c' in args)):
            inner = ' '.join(args) if name == 'eval' else args[args.index('-c') + 1] if args.index('-c') + 1 < len(args) else ''
            why = check(inner, cwd, depth + 1)
        if why:
            return why
    return None


def main():
    try:
        hook = json.load(sys.stdin)
        line = hook.get('tool_input', {}).get('command', '')
        cwd = hook.get('cwd')
    except Exception:
        print('Blocked: the guard could not read the hook input.', file=sys.stderr)
        return 2
    why = check(line, cwd)
    if why:
        print('Blocked: %s See docs/agents/workflow.md.' % why, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
