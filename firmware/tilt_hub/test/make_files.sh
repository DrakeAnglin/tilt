#!/bin/sh
# Make the update files the hub test reads (firmware/tilt_hub/test/files/), with tools/release_firmware.py and a test
# key made here. The files are kept in the repo, so the test needs no Python, OpenSSL or detools; run this again only
# when the file format changes. Needs detools (the ESP-IDF Python has it): PY=~/.espressif/python_env/idf5.5_py3.9_env/bin/python
#
# The test key is made new each time and only its public half is kept (files/test-key.pub.hex): it signs nothing
# but these test files, and it is not the release key.
set -e
cd "$(dirname "$0")"
ROOT=$(cd ../../.. && pwd)
PY=${PY:-$(ls ~/.espressif/python_env/*/bin/python 2>/dev/null | head -1)}
PY=${PY:-python3}
F=files
rm -rf "$F" && mkdir -p "$F"
openssl ecparam -name prime256v1 -genkey -noout -out "$F/test-key.pem"
# The public half, uncompressed (65 bytes, 04 | x | y), as hex: what the test checks with.
openssl ec -in "$F/test-key.pem" -pubout -outform DER 2>/dev/null | tail -c 65 | od -An -tx1 | tr -d ' \n' > "$F/test-key.pub.hex"
# Small images shaped like ESP-IDF's: image header (24) | segment header (8) | app description | code | SHA-256 (32).
"$PY" - "$F" <<'EOF'
import hashlib, os, struct, sys
out = sys.argv[1]
def image(project, version, seed):
    head = bytes([0xE9, 1, 2, 0x20]) + bytes(20)                  # image header
    seg = struct.pack('<II', 0x42000020, 256)                      # first segment: load address, length
    desc = struct.pack('<II8s', 0xABCD5432, 0, bytes(8)) + version.encode().ljust(32, b'\0') + project.encode().ljust(32, b'\0')
    desc = desc.ljust(256, b'\0')
    code = b''.join(hashlib.sha256(b'%d %d' % (seed, i)).digest() for i in range(100))   # 3200 bytes; a patch between two is about as big
    body = head + seg + desc + code
    return body + hashlib.sha256(body).digest()
for name, project, version, seed in [('hub-0.3.5', 'tilt_hub', '0.3.5', 1), ('hub-0.3.4', 'tilt_hub', '0.3.4', 2),
                                     ('tilt-2.3.0', 'blinds_matter', '2.3.0', 3), ('tilt-2.2.0', 'blinds_matter', '2.2.0', 4)]:
    open(os.path.join(out, name + '.bin'), 'wb').write(image(project, version, seed))
EOF
export TILT_SIGNING_KEY="$PWD/$F/test-key.pem"
for b in hub-0.3.5 hub-0.3.4 tilt-2.2.0; do "$PY" "$ROOT/tools/release_firmware.py" --sign "$F/$b.bin"; done
"$PY" "$ROOT/tools/release_firmware.py" --sign "$F/tilt-2.3.0.bin" --patch-from "$F/tilt-2.2.0.bin.signed"
rm "$F"/*.bin "$F/test-key.pem"
ls -l "$F"
