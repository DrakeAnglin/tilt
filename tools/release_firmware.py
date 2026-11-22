#!/usr/bin/env python3
"""Sign a built firmware and add it to the release list the app reads.

  python3 tools/release_firmware.py [stable|beta] [--notes "What changed"]

Builds a public release with no secrets in it (no Wi-Fi, no update password: idf.py -DTILT_RELEASE=1, into
firmware/blinds_matter/build-release), checks none of secrets.h's values ended up in it, signs it with
~/.tilt/firmware-signing-key.pem, and writes into firmware/releases/:
  tilt-<version>.bin   the image | signature (64 bytes) | "TILTSIG1"  (the controller checks the signature)
  firmware.json        {"stable": {...}, "beta": {...}}  the newest version on each channel; the file name is relative
Upload both files to the same place (a GitHub release) and the app finds them at its update address.
"""
import argparse, hashlib, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, 'firmware', 'blinds_matter')
OUT = os.path.join(ROOT, 'firmware', 'releases')
KEY = os.path.expanduser('~/.tilt/firmware-signing-key.pem')

def der_to_raw(der):
    """An ECDSA signature as OpenSSL writes it (DER) to r | s, 32 bytes each."""
    assert der[0] == 0x30
    i = 2 if der[1] < 0x80 else 2 + (der[1] & 0x7f)
    out = b''
    for _ in range(2):
        assert der[i] == 0x02
        n = der[i + 1]
        out += der[i + 2:i + 2 + n].lstrip(b'\0').rjust(32, b'\0')
        i += 2 + n
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('channel', nargs='?', default='beta', choices=['stable', 'beta'])
    ap.add_argument('--notes', default='')
    ap.add_argument('--sign', metavar='BIN', help='only sign this file (a developer build) and write BIN.signed; no release')
    a = ap.parse_args()
    if not os.path.exists(KEY): sys.exit('no signing key at ' + KEY)
    if a.sign:
        image = open(a.sign, 'rb').read()
        der = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', KEY], input=image, capture_output=True, check=True).stdout
        open(a.sign + '.signed', 'wb').write(image + der_to_raw(der) + b'TILTSIG1')
        return
    log = open(os.path.join(FW, 'build-release.log'), 'w')
    if subprocess.run([os.path.join(FW, 'build.sh'), '-B', 'build-release', '-DTILT_RELEASE=1', 'build'], cwd=FW, stdout=log, stderr=log).returncode:
        sys.exit('the release build failed: see firmware/blinds_matter/build-release.log')
    a.bin = os.path.join(FW, 'build-release', 'blinds_matter.bin')
    secrets = os.path.join(FW, 'main', 'secrets.h')
    if os.path.exists(secrets):                  # never publish a file with a password in it
        data = open(a.bin, 'rb').read()
        for v in re.findall(r'#define \w+ "([^"]{4,})"', open(secrets).read()):
            if v.encode() in data: sys.exit('a value from secrets.h is inside the release build: not published')
    version = re.search(r'#define FW_VERSION "([^"]+)"', open(os.path.join(FW, 'main', 'web.h')).read()).group(1)
    image = open(a.bin, 'rb').read()
    der = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', KEY], input=image, capture_output=True, check=True).stdout
    signed = image + der_to_raw(der) + b'TILTSIG1'
    os.makedirs(OUT, exist_ok=True)
    name = 'tilt-%s.bin' % version
    open(os.path.join(OUT, name), 'wb').write(signed)
    path = os.path.join(OUT, 'firmware.json')
    listing = json.load(open(path)) if os.path.exists(path) else {}
    entry = {'version': version, 'file': name, 'size': len(signed), 'sha256': hashlib.sha256(signed).hexdigest(), 'notes': a.notes}
    listing[a.channel] = entry
    if a.channel == 'stable' and 'beta' not in listing: listing['beta'] = entry
    json.dump(listing, open(path, 'w'), indent=2)
    print('%s %s: %s (%d bytes)' % (a.channel, version, name, len(signed)))

if __name__ == '__main__':
    main()
