#!/usr/bin/env python3
"""The coverage rule (docs/agents/workflow.md, "Coverage"): every pull request covers at least 90% of its changed
lines in our own code, and no area drops under its floor (tools/coverage-floors.txt).

  tools/coverage_gate.py check --area <area> --lcov <file> --log <file> [--base <ref>] [--out <dir>]
      One area: tests passed and failed, overall coverage, changed-lines coverage against <ref> (left out: no
      changed-lines gate, as on a push to main), the uncovered changed lines. Exit 1 when the area fails.
  tools/coverage_gate.py comment --results <dir> --head <sha> --run-url <url> [--main <dir>] [--skip <area>=<why>]...
                                 [--summary <file>] [--post <pr> --repo <owner/name>]
      The table for every area, from the results `check --out` wrote: to the job summary file, and posted as the one
      coverage comment on the pull request (edited in place). Exit 1 when any area failed or left no result.
  tools/coverage_gate.py readme [--check]
      Rewrites the coverage table in README.md from the floors (--check: only says whether it is up to date).

The areas are the Tilt app, the controller firmware, the Tilt Hub firmware and the tools. The coverage itself comes
from tools/coverage.sh as LCOV; this is the one place that knows the rule. Standard library only, Python 3.9 and up.
Tests: tools/test_tools.py.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = 90.0
MARKER = '<!-- tilt-coverage -->'
BOT = 'github-actions[bot]'
FLOORS = 'tools/coverage-floors.txt'
README = 'README.md'
CI_RUNS = 'https://github.com/DrakeAnglin/tilt/actions/workflows/ci.yml'
MAX_LISTED = 200          # uncovered changed lines shown in the comment; the rest are in the report

# Each area: its name (CONTEXT.md), which files are ours (test files never are), and its exclusion list.
AREAS = {
    'app': ('Tilt app', r'app/Tilt/(?!Tests/).*\.swift', 'app/Tilt/coverage-exclude.txt'),
    'controller': ('controller firmware', r'firmware/blinds_matter/main/[^/]+\.(h|cpp)',
                   'firmware/blinds_matter/coverage-exclude.txt'),
    'hub': ('Tilt Hub firmware', r'firmware/tilt_hub/main/[^/]+\.(h|cpp)', 'firmware/tilt_hub/coverage-exclude.txt'),
    'tools': ('tools', r'tools/(?:[^/]+/)*(?!test_)[^/]+\.py', 'tools/coverage-exclude.txt'),
}


def area_of(path):
    """The area a repo path belongs to, or None."""
    for area, (_, pattern, _) in AREAS.items():
        if re.fullmatch(pattern, path):
            return area
    return None


def parse_exclusions(text, list_path, files):
    """-> (excluded paths, errors). A line: `<path or glob, from the list's folder>  # <reason>`; whole files only."""
    base = os.path.dirname(list_path)
    excluded, errors = set(), []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        pattern, _, reason = line.partition('#')
        pattern, where = pattern.strip(), '%s:%d' % (list_path, n)
        if not reason.strip():
            errors.append('%s: `%s` has no reason (write `<path>  # <why no test can run it>`)' % (where, pattern))
            continue
        full = base + '/' + pattern if base else pattern
        hit = {f for f in files if fnmatch.fnmatchcase(f, full)}
        if not hit:
            errors.append('%s: `%s` matches no file of this area' % (where, pattern))
        excluded |= hit
    return excluded, errors


def parse_lcov(text, root=ROOT):
    """-> {repo path: {line: hits}}. Records of the same file (one per test program) add up."""
    real = os.path.realpath(root)
    cov, path = {}, None
    for line in text.splitlines():
        if line.startswith('SF:'):
            p = line[3:].strip()
            if os.path.isabs(p):
                p = os.path.realpath(p)
                p = os.path.relpath(p, real) if p.startswith(real + os.sep) else None
            path = p.replace(os.sep, '/') if p else None
        elif line.startswith('DA:') and path:
            n, hits = line[3:].split(',')[:2]
            lines = cov.setdefault(path, {})
            lines[int(n)] = lines.get(int(n), 0) + int(hits)
        elif line.startswith('end_of_record'):
            path = None
    return cov


def diff_lines(text):
    """-> {path: {added or changed line numbers}} from `git diff -U0`."""
    out, path = {}, None
    for line in text.splitlines():
        if line.startswith('+++ '):
            target = line[4:].strip()
            path = None if target == '/dev/null' else (target[2:] if target.startswith('b/') else target)
        elif line.startswith('@@') and path:
            m = re.match(r'@@ -\S+ \+(\d+)(?:,(\d+))? @@', line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
                out.setdefault(path, set()).update(range(start, start + count))
    return out


def code_lines(path, text):
    """The lines of a file no test compiled that count: every line that is not blank or a comment."""
    lines, in_block = set(), False
    python = path.endswith('.py')
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if python:
            if s and not s.startswith('#'):
                lines.add(n)
            continue
        if in_block:
            if '*/' not in s:
                continue
            in_block, s = False, s.split('*/', 1)[1].strip()
        if s.startswith('/*'):
            if '*/' not in s:
                in_block = True
                continue
            s = s.split('*/', 1)[1].strip()
        if s and not s.startswith('//'):
            lines.add(n)
    return lines


def test_counts(log):
    """-> (passed, failed) from test output: the firmware and app tests' `N passed, M failed`, unittest's summary."""
    passed = failed = 0
    for p, f in re.findall(r'(\d+) passed, (\d+) failed', log):
        passed, failed = passed + int(p), failed + int(f)
    for m in re.finditer(r'^Ran (\d+) tests? in .*$\s*^(OK|FAILED)(?: \(([^)]*)\))?', log, re.M):
        bad = sum(int(v) for k, v in re.findall(r'(\w+)=(\d+)', m.group(3) or '') if k in ('failures', 'errors'))
        passed, failed = passed + int(m.group(1)) - bad, failed + bad
    return passed, failed


def measure(area, sources, cov, changed=None, excluded=(), floor=0, log='', errors=()):
    """One area's result. sources: {path: text} of the area's files; cov: parse_lcov(); changed: diff_lines(), or
    None for no changed-lines gate. A file of ours that is in no LCOV record counts as all not covered."""
    lines = {}
    for path in sorted(sources):
        if path in excluded:
            continue
        if path in cov:
            lines[path] = {n: hits > 0 for n, hits in cov[path].items()}
        else:
            lines[path] = {n: False for n in code_lines(path, sources[path])}
    files = [(p, sum(v.values()), len(v)) for p, v in lines.items()]
    covered, total = sum(f[1] for f in files), sum(f[2] for f in files)
    passed, failed = test_counts(log)
    r = {'area': area, 'name': AREAS[area][0], 'passed': passed, 'failed': failed, 'covered': covered,
         'total': total, 'overall': 100.0 * covered / total if total else 100.0, 'floor': floor,
         'gated': changed is not None, 'changed': None, 'changed_covered': 0, 'changed_total': 0, 'uncovered': [],
         'errors': list(errors), 'notes': [], 'files': files}
    if changed is not None:
        for path in sorted(changed):
            for n in sorted(changed[path]):
                if n in lines.get(path, {}):
                    r['changed_total'] += 1
                    if lines[path][n]:
                        r['changed_covered'] += 1
                    else:
                        r['uncovered'].append('%s:%d' % (path, n))
        if r['changed_total']:
            r['changed'] = 100.0 * r['changed_covered'] / r['changed_total']
    ok = not r['errors']
    if r['changed'] is not None and r['changed'] < GATE:
        ok = False
        r['notes'].append('changed lines %.1f%% covered, under the %d%% gate: add tests for the lines listed'
                          % (r['changed'], GATE))
    elif r['gated'] and r['changed'] is None:
        r['notes'].append('no changed lines')
    if covered * 100 < floor * total:
        ok = False
        r['notes'].append('overall %.1f%% is under the floor of %d%% by %.1f points'
                          % (r['overall'], floor, floor - r['overall']))
    elif int(r['overall']) > floor:
        r['notes'].append('floor can go up to %d (%s)' % (int(r['overall']), FLOORS))
    r['ok'] = ok
    return r


def read_floors(text):
    """`<area> <whole percent>` per line -> {area: percent}."""
    floors = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0].split()
        if len(line) == 2:
            floors[line[0]] = int(line[1])
    return floors


# ---- the repo

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8', errors='replace') as f:
        return f.read()


def repo_files():
    """Tracked files, plus new ones not yet added (a local check before a commit)."""
    names = git('ls-files').splitlines() + git('ls-files', '--others', '--exclude-standard').splitlines()
    return sorted({n for n in names if os.path.isfile(os.path.join(ROOT, n))})


def changed_since(base):
    """Lines changed since this branch left <base>, the working tree included."""
    start = git('merge-base', base, 'HEAD').strip()
    changed = diff_lines(git('diff', '-U0', '-M', '--no-color', '--no-ext-diff', start))
    for path in git('ls-files', '--others', '--exclude-standard').splitlines():
        if os.path.isfile(os.path.join(ROOT, path)):
            changed[path] = set(range(1, len(read(path).splitlines()) + 1))
    return changed


def area_inputs(area, files=None):
    """-> (sources, excluded, errors) for an area, from the repo."""
    files = [f for f in (repo_files() if files is None else files) if area_of(f) == area]
    list_path = AREAS[area][2]
    if os.path.isfile(os.path.join(ROOT, list_path)):
        excluded, errors = parse_exclusions(read(list_path), list_path, files)
    else:
        excluded, errors = set(), ['%s is missing' % list_path]
    return {f: read(f) for f in files}, excluded, errors


def check(args):
    sources, excluded, errors = area_inputs(args.area)
    floors = read_floors(read(FLOORS))
    if args.area not in floors:
        errors.append('no floor for %s in %s' % (args.area, FLOORS))
    cov = {}
    if os.path.isfile(args.lcov):
        with open(args.lcov) as f:
            cov = parse_lcov(f.read())
    else:
        errors.append('no coverage file %s (did tools/coverage.sh run?)' % args.lcov)
    log = ''
    if args.log and os.path.isfile(args.log):
        with open(args.log, errors='replace') as f:
            log = f.read()
    r = measure(args.area, sources, cov, changed_since(args.base) if args.base else None, excluded,
                floors.get(args.area, 0), log, errors)
    print('%s: %s' % (r['name'], summary_line(r)))
    for line in r['errors'] + r['notes']:
        print('  ' + line)
    for line in r['uncovered'][:MAX_LISTED]:
        print('  not covered: ' + line)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, args.area + '.json'), 'w') as f:
            json.dump(r, f, indent=1)
        with open(os.path.join(args.out, args.area + '-files.txt'), 'w') as f:
            f.write('%-60s %9s %7s\n' % ('file', 'lines', 'covered'))
            for path, c, t in r['files']:
                f.write('%-60s %4d/%-4d %6.1f%%\n' % (path, c, t, 100.0 * c / t if t else 100.0))
    return 0 if r['ok'] else 1


# ---- the comment

def pct(v):
    return 'n/a' if v is None else '%.1f%%' % v


def summary_line(r):
    return 'tests %d passed, %d failed; overall %s (floor %d%%); changed lines: %s; %s' % (
        r['passed'], r['failed'], pct(r['overall']), r['floor'], changed_cell(r), 'pass' if r['ok'] else 'FAIL')


def changed_cell(r):
    if not r['gated']:
        return 'not gated (main)'
    if r['changed'] is None:
        return 'no changed lines'
    return '%s (%d of %d)' % (pct(r['changed']), r['changed_covered'], r['changed_total'])


def render(results, skipped, head, run_url, main=None):
    """The comment and job summary. results: {area: measure()}; skipped: {area: why it did not run};
    main: {area: result} of the latest run on main, for the change (information only)."""
    main = main or {}
    rows = ['| Area | Tests | Overall | Change from `main` | Changed lines (gate %d%%) | Result |' % GATE,
            '|---|---|---|---|---|---|']
    notes, uncovered = [], []
    for area, (name, _, _) in AREAS.items():
        r = results.get(area)
        if r is None:
            why = skipped.get(area)
            rows.append('| %s | | | | | %s |' % (name, 'did not run: ' + why if why else '**fail**: no result'))
            continue
        base = main.get(area)
        change = 'n/a' if base is None else '%+.1f points' % (r['overall'] - base['overall'])
        rows.append('| %s | %d passed, %d failed | %s (floor %d%%) | %s | %s | %s |' % (
            name, r['passed'], r['failed'], pct(r['overall']), r['floor'], change, changed_cell(r),
            'pass' if r['ok'] else '**fail**'))
        notes += ['%s: %s' % (name, n) for n in r['errors'] + r['notes']]
        uncovered += r['uncovered']
    out = [MARKER, '## Coverage', ''] + rows + ['']
    if notes:
        out += ['- ' + n for n in notes] + ['']
    if uncovered:
        shown = uncovered[:MAX_LISTED]
        out += ['<details><summary>Changed lines not covered (%d)</summary>' % len(uncovered), '']
        out += ['- `%s`' % u for u in shown]
        if len(uncovered) > len(shown):
            out.append('- and %d more: see the report' % (len(uncovered) - len(shown)))
        out += ['', '</details>', '']
    out.append('Made from %s. [The run, its report and artifact](%s)' % (head, run_url))
    return '\n'.join(out) + '\n'


def failing(results, skipped):
    """The areas that fail: a failed result, or no result from an area that should have run."""
    return [a for a in AREAS if (a in results and not results[a]['ok']) or (a not in results and a not in skipped)]


def gh_json(gh, *args):
    """`gh api --paginate` prints one JSON array per page, back to back: read them all."""
    text = subprocess.run([gh, 'api', '--paginate', *args], capture_output=True, text=True, check=True).stdout
    items, at, dec = [], 0, json.JSONDecoder()
    while at < len(text):
        if text[at].isspace():
            at += 1
            continue
        v, at = dec.raw_decode(text, at)
        items += v if isinstance(v, list) else [v]
    return items


def post(body, repo, pr, gh='gh'):
    """Edit the one coverage comment on the pull request, or make it. Only a comment by GitHub Actions counts:
    anyone can write the marker in a comment of their own."""
    mine = [c for c in gh_json(gh, 'repos/%s/issues/%s/comments' % (repo, pr))
            if (c.get('user') or {}).get('login') == BOT and MARKER in (c.get('body') or '')]
    payload = json.dumps({'body': body})
    if mine:
        cmd = [gh, 'api', '-X', 'PATCH', 'repos/%s/issues/comments/%s' % (repo, mine[0]['id']), '--input', '-']
    else:
        cmd = [gh, 'api', '-X', 'POST', 'repos/%s/issues/%s/comments' % (repo, pr), '--input', '-']
    subprocess.run(cmd, input=payload, capture_output=True, text=True, check=True)
    return 'edited' if mine else 'made'


def load_results(folder):
    results = {}
    if folder and os.path.isdir(folder):
        for area in AREAS:
            p = os.path.join(folder, area + '.json')
            if os.path.isfile(p):
                with open(p) as f:
                    results[area] = json.load(f)
    return results


def comment(args):
    results = load_results(args.results)
    skipped = dict(s.split('=', 1) for s in args.skip)
    body = render(results, skipped, args.head, args.run_url, load_results(args.main))
    print(body)
    if args.summary:
        with open(args.summary, 'a') as f:
            f.write(body)
    if args.post:
        print('coverage comment: %s' % post(body, args.repo, args.post))
    bad = failing(results, skipped)
    if bad:
        print('coverage: failed for %s' % ', '.join(AREAS[a][0] for a in bad), file=sys.stderr)
    return 1 if bad else 0


# ---- the README

def readme_block(floors):
    lines = ['<!-- coverage:start -->',
             '[![CI](%s/badge.svg?branch=main)](%s?query=branch%%3Amain)' % (CI_RUNS, CI_RUNS), '',
             '| Area | Line coverage |', '|---|---|']
    lines += ['| %s | at least %d%% |' % (name, floors.get(a, 0)) for a, (name, _, _) in AREAS.items()]
    lines += ['', 'Every pull request covers at least %d%% of the lines it changes in our own code, and no area may '
              'drop under its floor (`%s`). The live numbers: the `coverage` job of the [latest CI run on main]'
              '(%s?query=branch%%3Amain). The rule: [docs/agents/workflow.md](docs/agents/workflow.md#coverage).'
              % (GATE, FLOORS, CI_RUNS), '<!-- coverage:end -->']
    return '\n'.join(lines)


def rewrite_readme(text, floors):
    return re.sub(r'<!-- coverage:start -->.*?<!-- coverage:end -->', lambda _: readme_block(floors), text,
                  flags=re.S)


def readme(args):
    text = read(README)
    new = rewrite_readme(text, read_floors(read(FLOORS)))
    if new == text:
        print('README coverage table: up to date')
        return 0
    if args.check:
        print('README coverage table: out of date (run tools/coverage_gate.py readme)')
        return 1
    with open(os.path.join(ROOT, README), 'w') as f:
        f.write(new)
    print('README coverage table: rewritten')
    return 0


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('--area', required=True, choices=list(AREAS))
    c.add_argument('--lcov', required=True)
    c.add_argument('--log')
    c.add_argument('--base')
    c.add_argument('--out')
    m = sub.add_parser('comment')
    m.add_argument('--results', required=True)
    m.add_argument('--head', required=True)
    m.add_argument('--run-url', required=True)
    m.add_argument('--main')
    m.add_argument('--skip', action='append', default=[])
    m.add_argument('--summary')
    m.add_argument('--post')
    m.add_argument('--repo')
    r = sub.add_parser('readme')
    r.add_argument('--check', action='store_true')
    args = p.parse_args(argv)
    return {'check': check, 'comment': comment, 'readme': readme}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
