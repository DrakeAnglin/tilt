#!/usr/bin/env python3
"""Sign a built firmware and add it to the release list the app reads.

  python3 tools/release_firmware.py [stable|beta] [--notes "What changed"]

Builds a public release with no secrets in it (idf.py -DTILT_RELEASE=1, into
firmware/blinds_matter/build-release), checks none of secrets.h's values ended up in it, signs it with
~/.tilt/firmware-signing-key.pem, and writes into firmware/releases/:
  tilt-<version>.bin   the image | signature (64 bytes) | "TILTSIG1"  (the controller checks the signature)
  tilt-<version>-from-<old>.patch   only what changed since an earlier release (esp_delta_ota): header | patch |
                       the new image's signature | the patch file's signature | "TILTDLT1". A controller running
                       exactly <old> takes it in about a minute over Thread instead of seven.
  firmware.json        {"stable": {...}, "beta": {...}}  the newest version on each channel; the file name is relative
Normally the GitHub Action runs this on a version tag and publishes the result (docs/developer/firmware-release.md). By hand:
put firmware.json and every file it names on a new release of this repo (the app reads its latest release):
  gh release create <tag> --repo DrakeAnglin/tilt firmware/releases/firmware.json firmware/releases/<each file it names>
"""
import argparse, hashlib, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, 'firmware', 'blinds_matter')
OUT = os.path.join(ROOT, 'firmware', 'releases')
# TILT_SIGNING_KEY: another key, for test files only (firmware/tilt_hub/test/make_files.sh).
KEY = os.environ.get('TILT_SIGNING_KEY') or os.path.expanduser('~/.tilt/firmware-signing-key.pem')

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

def sign(data):
    der = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', KEY], input=data, capture_output=True, check=True).stdout
    return der_to_raw(der)

def make_patch(base, new):
    """A signed patch that turns the image `base` into the image `new` (both as built, without our signature).
    Its header names base by the SHA-256 esptool appends to every image (its last 32 bytes): the controller only
    applies it to exactly that firmware."""
    import io, detools
    out = io.BytesIO()
    detools.create_patch(io.BytesIO(base), io.BytesIO(new), out, compression='heatshrink')
    body = (0xfccdde10).to_bytes(4, 'little') + base[-32:] + bytes(28) + out.getvalue() + sign(new)
    return body + sign(body) + b'TILTDLT1'

def image_of(signed):
    """A file as published (image | signature | "TILTSIG1") back to the image."""
    return signed[:-72] if signed.endswith(b'TILTSIG1') else signed

def check_no_secrets(image):
    """Never publish a file with a password in it: no value from a secrets.h on this machine may be in the image."""
    for secrets in [os.path.join(FW, 'main', 'secrets.h'), os.path.join(ROOT, 'firmware', 'tilt_hub', 'main', 'secrets.h')]:
        if os.path.exists(secrets):
            for v in re.findall(r'#define \w+ "([^"]{4,})"', open(secrets).read()):
                if v.encode() in image: sys.exit('a value from %s is inside the release build: not published' % secrets)

def add_to_listing(listing, channel, entry):
    """Put a release on its channel. A stable release also goes to beta when beta has nothing newer, so a phone that
    follows beta is offered it too."""
    def key(v): return [int(x) if x.isdigit() else x for x in re.split(r'[.-]', v)]
    listing[channel] = entry
    if channel == 'stable':
        b = listing.get('beta')
        if not b or key(b['version'].split('-')[0]) <= key(entry['version']): listing['beta'] = entry
    return listing

def build_signed(version):
    """Build the public release with no secrets in it, sign it, write it to OUT."""
    log = open(os.path.join(FW, 'build-release.log'), 'w')
    env = dict(os.environ, BUILD_DIR='build-release', SDKCONFIG_FILE='sdkconfig.release')
    if subprocess.run([os.path.join(FW, 'build.sh'), '-DTILT_RELEASE=1', 'build'], cwd=FW, stdout=log, stderr=log, env=env).returncode:
        sys.exit('the release build failed: see firmware/blinds_matter/build-release.log')
    image = open(os.path.join(FW, 'build-release', 'blinds_matter.bin'), 'rb').read()
    check_no_secrets(image)
    signed = image + sign(image) + b'TILTSIG1'
    name = 'tilt-%s.bin' % version
    open(os.path.join(OUT, name), 'wb').write(signed)
    return name, signed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('channel', nargs='?', default='beta', choices=['stable', 'beta'])
    ap.add_argument('--notes', default='')
    ap.add_argument('--sign', metavar='BIN', help='only sign this file (a developer build) and write BIN.signed; no release')
    ap.add_argument('--patch-from', metavar='BASE', help='with --sign: also write BIN.patch, from the image BASE')
    ap.add_argument('--hub', action='store_true', help='release the Tilt Hub firmware instead (listed as "hub"; the app offers it on the hub page)')
    a = ap.parse_args()
    if not os.path.exists(KEY): sys.exit('no signing key at ' + KEY)
    if a.sign:
        image = open(a.sign, 'rb').read()
        open(a.sign + '.signed', 'wb').write(image + sign(image) + b'TILTSIG1')
        if a.patch_from:
            p = make_patch(image_of(open(a.patch_from, 'rb').read()), image)
            open(a.sign + '.patch', 'wb').write(p)
            print('patch: %d bytes (the full file is %d)' % (len(p), len(image) + 72))
        return
    if a.hub:
        hubdir = os.path.join(ROOT, 'firmware', 'tilt_hub')
        hv = re.search(r'set\(PROJECT_VER "([^"]+)"\)', open(os.path.join(hubdir, 'CMakeLists.txt')).read()).group(1)
        log = open(os.path.join(hubdir, 'build-release.log'), 'w')
        env = dict(os.environ, BUILD_DIR='build-release')
        if subprocess.run([os.path.join(hubdir, 'build.sh'), '-B', 'build-release', '-DTILT_RELEASE=1', 'build'], cwd=hubdir, stdout=log, stderr=log, env=env).returncode:
            sys.exit('the hub release build failed: see firmware/tilt_hub/build-release.log')
        image = open(os.path.join(hubdir, 'build-release', 'tilt_hub.bin'), 'rb').read()
        check_no_secrets(image)
        os.makedirs(OUT, exist_ok=True)
        name = 'tilt-hub-%s.bin' % hv
        signed = image + sign(image) + b'TILTSIG1'
        open(os.path.join(OUT, name), 'wb').write(signed)
        path = os.path.join(OUT, 'firmware.json')
        listing = json.load(open(path)) if os.path.exists(path) else {}
        listing['hub'] = {'version': hv, 'file': name, 'size': len(signed), 'sha256': hashlib.sha256(signed).hexdigest(), 'notes': a.notes}
        json.dump(listing, open(path, 'w'), indent=2)
        print('hub %s: %s (%d bytes)' % (hv, name, len(signed)))
        return
    version = re.search(r'#define FW_VERSION "([^"]+)"', open(os.path.join(FW, 'main', 'web.h')).read()).group(1)
    os.makedirs(OUT, exist_ok=True)
    name, signed = build_signed(version)
    path = os.path.join(OUT, 'firmware.json')
    listing = json.load(open(path)) if os.path.exists(path) else {}
    entry = {'version': version, 'file': name, 'size': len(signed), 'sha256': hashlib.sha256(signed).hexdigest(), 'notes': a.notes}
    # Patches from the last few releases: the app uses one when the controller runs exactly that firmware ("from":
    # the image's SHA-256, which the controller's hello shows as "img").
    olds = sorted((f for f in os.listdir(OUT) if re.fullmatch(r'tilt-[^-]+(-[a-z0-9]+)?\.bin', f) and f != name), key=lambda f: os.path.getmtime(os.path.join(OUT, f)))[-3:]
    entry['patches'] = []
    for old in olds:
        base = image_of(open(os.path.join(OUT, old), 'rb').read())
        p = make_patch(base, image_of(signed))
        pname = 'tilt-%s-from-%s.patch' % (version, old[5:-4])
        open(os.path.join(OUT, pname), 'wb').write(p)
        entry['patches'].append({'from': base[-32:].hex(), 'file': pname, 'size': len(p), 'sha256': hashlib.sha256(p).hexdigest()})
        print('  patch from %s: %d bytes' % (old, len(p)))
    add_to_listing(listing, a.channel, entry)
    json.dump(listing, open(path, 'w'), indent=2)
    print('%s %s: %s (%d bytes)' % (a.channel, version, name, len(signed)))

if __name__ == '__main__':
    main()
