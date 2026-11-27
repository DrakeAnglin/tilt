#!/usr/bin/env python3
"""Finds the real cJSON for the Tilt Hub's Mac tests and writes the compiler arguments for it.

  tools/host_cjson.py <out dir>
Writes <out dir>/cjson.args (one argument per line, for `c++ ... @<out dir>/cjson.args`). ESP-IDF's own copy first
($IDF_PATH or ~/esp/esp-idf, components/json/cJSON/cJSON.c: the exact code on the chip), compiled into the out dir;
else the system's (cjson/cJSON.h and -lcjson); else exits 1 with the line to install it. tools/firmware_tests.sh calls it.
"""
import os
import shutil
import subprocess
import sys

INSTALL = 'hub test: no cJSON. Install it (Linux: apt-get install libcjson-dev; a Mac: brew install cjson) or ESP-IDF.'


def idf_source(env, home):
    """ESP-IDF's cJSON.c, or None."""
    idf = env.get('IDF_PATH') or os.path.join(home, 'esp', 'esp-idf')
    src = os.path.join(idf, 'components', 'json', 'cJSON', 'cJSON.c')
    return src if os.path.isfile(src) else None


def system_prefixes():
    """Where a system cJSON may be: Homebrew's (if brew is there), then the usual prefixes."""
    out = []
    if shutil.which('brew'):
        r = subprocess.run(['brew', '--prefix', 'cjson'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            out.append(r.stdout.strip())
    return out + ['/opt/homebrew', '/usr/local', '/usr']


def system_args(prefixes):
    """The arguments for the first prefix with include/cjson/cJSON.h, or None."""
    for p in prefixes:
        inc = os.path.join(p, 'include', 'cjson')
        if os.path.isfile(os.path.join(inc, 'cJSON.h')):
            lib = os.path.join(p, 'lib')
            return ['-I' + inc] + (['-L' + lib] if p != '/usr' else []) + ['-lcjson']
    return None


def find(out_dir, env=None, home=None, prefixes=None, cc='cc'):
    """The compiler arguments for cJSON (compiling ESP-IDF's copy into out_dir when it is there), or None."""
    env = os.environ if env is None else env
    home = os.path.expanduser('~') if home is None else home
    src = idf_source(env, home)
    if src:
        obj = os.path.join(out_dir, 'cJSON.o')
        subprocess.run([cc, '-O1', '-c', src, '-o', obj], check=True)
        return ['-I' + os.path.dirname(src), obj]
    return system_args(system_prefixes() if prefixes is None else prefixes)


def main(argv=None, **kw):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: host_cjson.py <out dir>', file=sys.stderr)
        return 2
    args = find(argv[0], **kw)
    if args is None:
        print(INSTALL, file=sys.stderr)
        return 1
    with open(os.path.join(argv[0], 'cjson.args'), 'w') as f:
        f.write(''.join('"%s"\n' % a.replace('\\', '\\\\').replace('"', '\\"') for a in args))
    return 0


if __name__ == '__main__':
    sys.exit(main())
