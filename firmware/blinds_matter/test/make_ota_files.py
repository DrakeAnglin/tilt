#!/usr/bin/env python3
"""Firmware files for test/ota_test.cpp, made the way a release is: signed by tools/release_firmware.py, here with a
throwaway key made on the spot (never the release key).

  python3 make_ota_files.py OUT

Writes into OUT:
  base.bin               the image the controller "runs" (2.3.0)
  new.bin, new.bin.signed, old.bin.signed   2.4.0 and 2.2.0 as full files (image | signature | "TILTSIG1")
  new.patch              base -> new as a patch file, from release_firmware's own make_patch. The patch inside is a
                         stand-in (the new image itself, which the test's fake applies by copying): a stand-in detools
                         module writes it, so detools is not needed; the rest is release_firmware's.
  other.patch            the same, made for a firmware this controller does not run
  signed.txt             "sha256 signature" (hex) for each image the key signed: the fake's signature check
The images are shaped like ESP-IDF's: the app description (and its version) 32 bytes in, the SHA-256 at the end.
"""
import hashlib, os, random, subprocess, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', 'tools')
sys.path.insert(0, TOOLS)
import release_firmware  # noqa: E402

# A stand-in for detools: the "patch" is the new image itself. Only make_patch's import sees it.
_detools = types.ModuleType('detools')
_detools.create_patch = lambda base, new, out, compression=None: out.write(new.read())
sys.modules.setdefault('detools', _detools)

def image(version, size, seed):
    rnd = random.Random(seed)
    head = bytes([0xE9, 3, 2, 0]) + bytes(20) + bytes(8)            # image header (24) + first segment header (8)
    desc = (0xABCD5432).to_bytes(4, 'little') + bytes(12) + version.encode().ljust(32, b'\0') + b'blinds_matter'.ljust(32, b'\0')
    body = head + desc
    body += bytes(rnd.randrange(256) for _ in range(size - 32 - len(body)))
    return body + hashlib.sha256(body).digest()                   # esptool appends the image's SHA-256

def main():
    out = sys.argv[1]
    key = os.path.join(out, 'test-key.pem')
    subprocess.run(['openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout', '-out', key], check=True)
    release_firmware.KEY = key
    imgs = {'base': image('2.3.0', 4000, 1), 'new': image('2.4.0', 4970, 2), 'old': image('2.2.0', 3100, 3),
            'other': image('2.3.1', 4000, 4)}
    for name, b in imgs.items():
        open(os.path.join(out, name + '.bin'), 'wb').write(b)
    signed = []
    for name in ['new', 'old']:
        sys.argv = ['release_firmware.py', '--sign', os.path.join(out, name + '.bin')]
        release_firmware.main()                                   # the real --sign path, with KEY set above
        f = open(os.path.join(out, name + '.bin.signed'), 'rb').read()
        signed.append((hashlib.sha256(imgs[name]).hexdigest(), f[-72:-8].hex()))
    for name, base in [('new', 'base'), ('other', 'other')]:
        p = release_firmware.make_patch(imgs[base], imgs['new'])
        open(os.path.join(out, name + '.patch'), 'wb').write(p)
        signed.append((hashlib.sha256(imgs['new']).hexdigest(), p[-136:-72].hex()))
    open(os.path.join(out, 'signed.txt'), 'w').write(''.join('%s %s\n' % s for s in signed))

if __name__ == '__main__':
    main()
