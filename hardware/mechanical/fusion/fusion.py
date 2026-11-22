#!/usr/bin/env python3
"""Command-line client for the FusionBridge add-in.

  python3 fusion.py ping
  python3 fusion.py exec  file.py            # run a file inside Fusion (assign `result` to return data)
                                             # the code gets __file__ (the file's path) and REPO (the repo root)
  python3 fusion.py exec  -c "result = design.rootComponent.name"
  python3 fusion.py shot  out.png [--view iso|front|top|right|home|current] [--size 1600x1000] [--no-fit]
"""

import argparse
import json
import os
import sys
import urllib.request

STATE_DIR = os.path.join(os.path.expanduser('~'), '.fusion_bridge')
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))   # hardware/mechanical/fusion -> repo


def _conn():
    try:
        token = open(os.path.join(STATE_DIR, 'token')).read().strip()
        port = open(os.path.join(STATE_DIR, 'port')).read().strip()
    except OSError:
        sys.exit('FusionBridge is not running (no token in ~/.fusion_bridge). Start the add-in in Fusion.')
    return 'http://127.0.0.1:{}'.format(port), token


def call(path, payload=None, timeout=150):
    base, token = _conn()
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, method='GET' if payload is None else 'POST',
                                 headers={'X-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def show(resp):
    if resp.get('stdout'):
        sys.stdout.write(resp['stdout'])
    if not resp.get('ok'):
        sys.stderr.write(resp.get('error', 'failed') + '\n')
        sys.exit(1)
    if resp.get('result') is not None:
        r = resp['result']
        print(r if isinstance(r, str) else json.dumps(r, indent=2))
    elif 'path' in resp:
        print(resp['path'])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('ping')
    e = sub.add_parser('exec')
    e.add_argument('file', nargs='?')
    e.add_argument('-c', dest='code')
    e.add_argument('--timeout', type=int, default=120, help='seconds to wait for Fusion (long checks need more)')
    s = sub.add_parser('shot')
    s.add_argument('path')
    s.add_argument('--view', default='iso')
    s.add_argument('--size', default='1600x1000')
    s.add_argument('--no-fit', action='store_true')
    a = ap.parse_args()

    if a.cmd == 'ping':
        show({'ok': True, 'result': call('/ping')})
    elif a.cmd == 'exec':
        if a.code is not None:
            code = 'REPO = %r\n' % REPO + a.code
        else:
            path = os.path.abspath(a.file)
            code = '__file__ = %r; REPO = %r\n' % (path, REPO) + open(path).read()   # one line, so tracebacks are only one line off
        show(call('/exec', {'code': code, 'timeout': a.timeout}, timeout=a.timeout + 30))
    elif a.cmd == 'shot':
        w, h = (int(x) for x in a.size.lower().split('x'))
        show(call('/screenshot', {'path': os.path.abspath(a.path), 'width': w, 'height': h,
                                  'view': a.view, 'fit': not a.no_fit}))


if __name__ == '__main__':
    main()
