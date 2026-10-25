#!/usr/bin/env python3
"""Command-line client for the FusionBridge add-in.

  python3 fusion.py ping
  python3 fusion.py exec  file.py            # run a file inside Fusion (assign `result` to return data)
  python3 fusion.py exec  -c "result = design.rootComponent.name"
  python3 fusion.py shot  out.png [--view iso|front|top|right|home|current] [--size 1600x1000] [--no-fit]
  python3 fusion.py layout                   # rebuild the TiltLayout study in the active design, print the fit report
"""

import argparse
import json
import os
import sys
import urllib.request

STATE_DIR = os.path.join(os.path.expanduser('~'), '.fusion_bridge')
HERE = os.path.dirname(os.path.abspath(__file__))


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


LAYOUT_CODE = """
mod = load_script({path!r})
d = design
if d is None:
    app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    d = adsk.fusion.Design.cast(app.activeProduct)
mod.remove_old(d)
result = mod.build(d)
"""


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('ping')
    e = sub.add_parser('exec')
    e.add_argument('file', nargs='?')
    e.add_argument('-c', dest='code')
    s = sub.add_parser('shot')
    s.add_argument('path')
    s.add_argument('--view', default='iso')
    s.add_argument('--size', default='1600x1000')
    s.add_argument('--no-fit', action='store_true')
    sub.add_parser('layout')
    a = ap.parse_args()

    if a.cmd == 'ping':
        show({'ok': True, 'result': call('/ping')})
    elif a.cmd == 'exec':
        code = a.code if a.code is not None else open(a.file).read()
        show(call('/exec', {'code': code}))
    elif a.cmd == 'shot':
        w, h = (int(x) for x in a.size.lower().split('x'))
        show(call('/screenshot', {'path': os.path.abspath(a.path), 'width': w, 'height': h,
                                  'view': a.view, 'fit': not a.no_fit}))
    elif a.cmd == 'layout':
        path = os.path.join(HERE, 'TiltLayout', 'TiltLayout.py')
        show(call('/exec', {'code': LAYOUT_CODE.format(path=path)}))


if __name__ == '__main__':
    main()
