#!/usr/bin/env python3
"""The GitHub Action's helpers for a firmware release (.github/workflows/release.yml).

  python3 tools/release_ci.py check-tag fw-v2.3.0      the tag must match the version in the code; prints kind, version, channel
  python3 tools/release_ci.py fetch                    the published firmware.json and earlier images into firmware/releases/
  python3 tools/release_ci.py verify PUB.pem           check the signature on each file this run built
  python3 tools/release_ci.py files                    every file the new firmware.json names (all go on the new release)

Tags: fw-v<version> is a controller release (stable; a version with a dash, like 2.3.0-beta1, goes to beta),
hub-v<version> a Tilt Hub release. The app reads only the newest release on DrakeAnglin/tilt-site
(releases/latest/download/firmware.json), so each release carries every file its firmware.json names.
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'firmware', 'releases')
SITE = 'DrakeAnglin/tilt-site'
PATCH_BASES = 3                      # release_firmware.py makes patches from the last three controller images


def parse_tag(tag):
    """'fw-v2.3.0' -> ('controller', '2.3.0', 'stable'); 'fw-v2.3.0-beta1' -> beta; 'hub-v0.3.4' -> ('hub', '0.3.4', 'hub')."""
    m = re.fullmatch(r'(fw|hub)-v(\d+\.\d+\.\d+(?:-[a-z0-9]+)?)', tag)
    if not m: raise ValueError('not a release tag: %s (fw-v1.2.3, fw-v1.2.3-beta1 or hub-v1.2.3)' % tag)
    if m.group(1) == 'hub': return 'hub', m.group(2), 'hub'
    return 'controller', m.group(2), 'beta' if '-' in m.group(2) else 'stable'


def code_version(kind, root=ROOT):
    """The version the code says it is: FW_VERSION in web.h, or the hub's PROJECT_VER."""
    if kind == 'hub':
        text, pat = open(os.path.join(root, 'firmware', 'tilt_hub', 'CMakeLists.txt')).read(), r'set\(PROJECT_VER "([^"]+)"\)'
    else:
        text, pat = open(os.path.join(root, 'firmware', 'blinds_matter', 'main', 'web.h')).read(), r'#define FW_VERSION "([^"]+)"'
    return re.search(pat, text).group(1)


def listed_files(listing):
    """Every file a firmware.json names: each channel's image and its patches."""
    out = []
    for entry in listing.values():
        for f in [entry['file']] + [p['file'] for p in entry.get('patches') or []]:
            if f not in out: out.append(f)
    return out


def raw_to_der(sig):
    """r | s (32 bytes each), as our files carry it, to the DER that openssl reads."""
    def integer(v):
        v = v.lstrip(b'\0') or b'\0'
        v = b'\0' + v if v[0] & 0x80 else v
        return b'\x02' + bytes([len(v)]) + v
    body = integer(sig[:32]) + integer(sig[32:64])
    return b'\x30' + bytes([len(body)]) + body


def signed_part(data):
    """A published file to (what was signed, the signature): image | sig | "TILTSIG1", or patch body | sig | "TILTDLT1"."""
    if data[-8:] not in (b'TILTSIG1', b'TILTDLT1'): raise ValueError('not a signed Tilt file')
    return data[:-72], data[-72:-8]


FETCHED = 1_000_000_000              # fetch() dates the files it downloads in 2001; anything newer was built here


def verify(pub, out=OUT):
    import subprocess, tempfile
    built = [f for f in sorted(os.listdir(out)) if f.endswith(('.bin', '.patch')) and os.path.getmtime(os.path.join(out, f)) > FETCHED + 10**6]
    if not built: sys.exit('nothing was built')
    for f in built:
        body, sig = signed_part(open(os.path.join(out, f), 'rb').read())
        with tempfile.NamedTemporaryFile() as s:
            s.write(raw_to_der(sig)); s.flush()
            r = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', pub, '-signature', s.name], input=body, capture_output=True)
        if r.returncode: sys.exit('bad signature: ' + f)
        print('signature ok: ' + f)


def _get(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'tilt-release'})
    return urllib.request.urlopen(req, timeout=60).read()


def fetch(out=OUT):
    """Download what is published now: the newest firmware.json and the files it names (they go on the new release
    again), and the last few controller images (release_firmware.py makes patches from them, newest last by time)."""
    os.makedirs(out, exist_ok=True)
    releases = [r for r in json.loads(_get('https://api.github.com/repos/%s/releases?per_page=30' % SITE))
                if not r['draft'] and not r['prerelease']]
    if not releases: print('nothing published yet'); return
    releases.sort(key=lambda r: r['published_at'])
    assets = {}                                   # file -> (url, release time): the newest copy of each name
    for r in releases:
        for a in r['assets']: assets[a['name']] = (a['browser_download_url'], r['published_at'])
    listing = json.loads(_get(assets['firmware.json'][0])) if 'firmware.json' in assets else {}
    images = [n for n in assets if re.fullmatch(r'tilt-\d[^/]*\.bin', n)]
    images.sort(key=lambda n: assets[n][1])
    want = listed_files(listing) + [n for n in images[-PATCH_BASES:] if n not in listed_files(listing)]
    for name in want:
        if name not in assets: sys.exit('firmware.json names %s, but no release has it' % name)
        open(os.path.join(out, name), 'wb').write(_get(assets[name][0]))
    for name in images:                           # the order release_firmware.py reads: oldest first
        p = os.path.join(out, name)
        if os.path.exists(p):
            t = images.index(name) + FETCHED
            os.utime(p, (t, t))
    json.dump(listing, open(os.path.join(out, 'firmware.json'), 'w'), indent=2)
    print('fetched: ' + ', '.join(want))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'check-tag':
        kind, version, channel = parse_tag(sys.argv[2])
        have = code_version(kind)
        if have != version: sys.exit('the tag says %s, the code says %s: tag the commit that has that version' % (version, have))
        print('kind=%s\nversion=%s\nchannel=%s' % (kind, version, channel))
    elif cmd == 'fetch':
        fetch()
    elif cmd == 'verify':
        verify(sys.argv[2])
    elif cmd == 'files':
        listing = json.load(open(os.path.join(OUT, 'firmware.json')))
        for f in ['firmware.json'] + listed_files(listing):
            path = os.path.join(OUT, f)
            if not os.path.exists(path): sys.exit('missing ' + path)
            print(path)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
