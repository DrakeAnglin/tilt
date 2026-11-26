#!/usr/bin/env python3
"""Claim an issue so no other agent starts on it at the same time.

    tools/agent/claim.py <issue> <id>             claim it, or refresh your own claim
    tools/agent/claim.py <issue> <id> --resume    the same, but an open pull request for the issue does not stop you
                                                  (you are taking over that pull request)
    tools/agent/claim.py <issue> <id> --release   take your claim off

<id> is any name for this session that no other session uses, for example the worktree name.
Exit 0: yours. Exit 3: someone else has it (it says who). Exit 2: usage or a gh error.

Every agent here uses the same GitHub account, so the assignee cannot say which agent has an issue.
A claim is a comment with a marker, from that account. It holds for STALE_HOURS after it was made or
last refreshed; after that it is abandoned and anyone may claim. Two agents that claim at the same
moment both post, then both read again: the earlier comment wins and the other takes its own off.
Tests: tools/agent/test_agent.py
"""
import datetime
import json
import re
import subprocess
import sys

STALE_HOURS = 4
MARK = re.compile(r'<!-- agent-claim id=(\S+) -->')


def parse_time(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)


def live_claims(comments, me, now):
    """Claims by `me` that have not gone stale, earliest first: [(claim id, comment id)]."""
    out = []
    for c in comments:
        m = MARK.search(c.get('body') or '')
        if not m or (c.get('user') or {}).get('login') != me:
            continue
        if now - parse_time(c['updated_at']) > datetime.timedelta(hours=STALE_HOURS):
            continue
        out.append((parse_time(c['created_at']), c['id'], m.group(1)))
    return [(cid, comment) for _, comment, cid in sorted(out)]


def holder(comments, me, now, my_id):
    """Who has the issue: None when nobody else does, else the other claim's id."""
    claims = live_claims(comments, me, now)
    if not claims:
        return None
    first = claims[0][0]
    return None if first == my_id else first


def body(my_id, now):
    until = (now + datetime.timedelta(hours=STALE_HOURS)).strftime('%Y-%m-%d %H:%M UTC')
    return ('Claimed by agent `%s` at %s. Other agents: leave this issue alone until %s unless this claim is '
            'refreshed (`tools/agent/claim.py`).\n\n<!-- agent-claim id=%s -->'
            % (my_id, now.strftime('%Y-%m-%d %H:%M UTC'), until, my_id))


def gh(*args):
    r = subprocess.run(['gh', *args], capture_output=True, text=True)
    if r.returncode != 0:
        print('gh %s failed: %s' % (' '.join(args[:2]), r.stderr.strip()), file=sys.stderr)
        sys.exit(2)
    return r.stdout


def comments(issue):
    out = gh('api', '--paginate', 'repos/{owner}/{repo}/issues/%s/comments' % issue)
    # --paginate prints one JSON array per page.
    return [c for page in re.split(r'(?<=\])\s*(?=\[)', out.strip()) if page for c in json.loads(page)]


def main(argv):
    if len(argv) < 2 or len(argv) > 3 or (len(argv) == 3 and argv[2] not in ('--resume', '--release')):
        print(__doc__.strip().split('\n\n')[0], file=sys.stderr)
        return 2
    issue, my_id, mode = argv[0], argv[1], (argv[2] if len(argv) == 3 else '')
    if not issue.isdigit() or not re.fullmatch(r'[A-Za-z0-9._-]+', my_id):
        print('issue must be a number, id only letters, digits, . _ -', file=sys.stderr)
        return 2
    me = gh('api', 'user', '--jq', '.login').strip()
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    found = comments(issue)
    mine = [c for c in found
            if (c.get('user') or {}).get('login') == me and MARK.search(c.get('body') or '')
            and MARK.search(c['body']).group(1) == my_id]

    if mode == '--release':
        for c in mine:
            gh('api', '-X', 'DELETE', 'repos/{owner}/{repo}/issues/comments/%s' % c['id'])
        print('released #%s' % issue)
        return 0

    other = holder(found, me, now, my_id)
    if other:
        print('#%s is taken: agent `%s` has a live claim. Pick another issue.' % (issue, other))
        return 3
    live = [comment for _, comment in live_claims(found, me, now)]
    stale_mine = [c for c in mine if c['id'] not in live]
    mine = [c for c in mine if c['id'] in live]
    if mode != '--resume' and not mine:
        prs = json.loads(gh('pr', 'list', '--state', 'open', '--json', 'number,closingIssuesReferences'))
        open_pr = [p['number'] for p in prs if any(str(i.get('number')) == issue for i in p['closingIssuesReferences'])]
        if open_pr:
            print('#%s is taken: pull request #%s is open for it. Pick another issue.' % (issue, open_pr[0]))
            return 3
    for c in stale_mine:
        # A stale claim of ours is not brought back: its old time would win a race it should lose.
        gh('api', '-X', 'DELETE', 'repos/{owner}/{repo}/issues/comments/%s' % c['id'])
    if mine:
        gh('api', '-X', 'PATCH', 'repos/{owner}/{repo}/issues/comments/%s' % mine[0]['id'], '-f', 'body=' + body(my_id, now))
    else:
        gh('issue', 'comment', issue, '--body', body(my_id, now))
    gh('issue', 'edit', issue, '--add-assignee', '@me')

    # Two agents may have claimed at the same moment: read again, the earliest live claim wins.
    other = holder(comments(issue), me, now, my_id)
    if other:
        for c in comments(issue):
            m = MARK.search(c.get('body') or '')
            if m and m.group(1) == my_id and (c.get('user') or {}).get('login') == me:
                gh('api', '-X', 'DELETE', 'repos/{owner}/{repo}/issues/comments/%s' % c['id'])
        print('#%s is taken: agent `%s` claimed it at the same time, first. Pick another issue.' % (issue, other))
        return 3
    print('claimed #%s as `%s` until %s hours from now; run again to refresh' % (issue, my_id, STALE_HOURS))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
