"""Check the Markdown docs: links, anchors and leftovers from one house.

  python3 tools/check_docs.py        prints "file:line: message" for each problem, exits 1 if any

Checks every tracked .md file outside .claude/:
  1. each relative link points at a file or folder that exists
  2. each #anchor on a relative or same-page link matches a heading in the target
  3. public pages have no house leftovers (our counts, "the owner's", private IPs, fixed serial ports)
Web links are not fetched. Standard library only.
"""
import os
import re
import subprocess
import sys

LINK = re.compile(r'!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
REF_LINK = re.compile(r'^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+"[^"]*")?\s*$')
HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
HTML_ANCHOR = re.compile(r'<a\s+(?:name|id)="([^"]+)"', re.I)
FENCE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE = re.compile(r'`[^`]*`')

HOUSE = [
    (re.compile(r'\b8 blinds\b', re.I), '"8 blinds"'),
    (re.compile(r'\b3 controllers\b', re.I), '"3 controllers"'),
    (re.compile(r'3 \+ 3 \+ 2'), '"3 + 3 + 2"'),
    (re.compile(r"\bthe owner['’]s\b", re.I), '"the owner\'s"'),
    (re.compile(r'\b(my|our) house\b', re.I), '"my/our house"'),
    (re.compile(r'\b(10\.\d{1,3}|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b'), 'private IP address'),
    (re.compile(r'/dev/cu\.usbmodem\d'), 'fixed serial port'),
]
# Pages for people working on Tilt itself, and records that are not reworded.
HOUSE_SKIP = ('docs/agents/', 'docs/adr/', 'docs/developer/', 'CLAUDE.md', 'CONTEXT.md')
EXAMPLE = re.compile(r'^[\s>*_#\-+\d.|]*Example:', re.I)


def md_files(root):
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '*.md'], cwd=root, capture_output=True, check=True).stdout
        files = [f for f in out.decode().split('\0') if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x not in ('.git', '.claude')]
            files += [os.path.relpath(os.path.join(d, n), root) for n in names if n.endswith('.md')]
    return sorted(f.replace(os.sep, '/') for f in files
                  if not f.startswith('.claude/') and os.path.isfile(os.path.join(root, f)))


def lines_outside_code(text):
    """(line number, line with inline code removed) for each line outside fenced code."""
    fence = None
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            yield n, line


def slug(heading):
    """GitHub's heading-to-anchor rule."""
    h = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', heading)  # links keep their text
    h = re.sub(r'<[^>]+>', '', h)
    h = h.strip().lower()
    h = re.sub(r'[^\w\- ]', '', h)
    return h.replace(' ', '-')


def anchors(path):
    found, seen = set(), {}
    with open(path, encoding='utf-8') as f:
        text = f.read()
    for _, line in lines_outside_code(text):
        found.update(HTML_ANCHOR.findall(line))
        m = HEADING.match(line)
        if m:
            s = slug(m.group(2))
            n = seen.get(s, 0)
            seen[s] = n + 1
            found.add(s if n == 0 else f'{s}-{n}')
    return found


def link_problems(root, page, n, target, cache):
    if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('/') or '{{' in target:
        return []  # web, mail, site-absolute and Jekyll links are not checked
    if page.startswith('site/') and not target.split('#')[0].endswith('.md'):
        return []  # Jekyll pages link to the built .html
    path, _, anchor = target.partition('#')
    full = os.path.normpath(os.path.join(root, os.path.dirname(page), path)) if path else os.path.join(root, page)
    if not os.path.exists(full):
        return [f'{page}:{n}: broken link {target}']
    if anchor and os.path.isfile(full) and full.endswith('.md'):
        if full not in cache:
            cache[full] = anchors(full)
        if anchor.lower() not in cache[full]:
            return [f'{page}:{n}: no heading for #{anchor} in {path or page}']
    return []


def problems(root):
    out, cache = [], {}
    for page in md_files(root):
        with open(os.path.join(root, page), encoding='utf-8') as f:
            text = f.read()
        public = not page.startswith(HOUSE_SKIP)
        for n, line in lines_outside_code(text):
            bare = INLINE_CODE.sub('', line)
            targets = LINK.findall(bare)
            m = REF_LINK.match(bare)
            if m:
                targets.append(m.group(1))
            for t in targets:
                out += link_problems(root, page, n, t, cache)
            if public and not EXAMPLE.match(line):
                out += [f'{page}:{n}: house leftover {what}' for rx, what in HOUSE if rx.search(line)]
    return out


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    found = problems(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, '..'))
    print('\n'.join(found) or 'docs: ok')
    sys.exit(1 if found else 0)
