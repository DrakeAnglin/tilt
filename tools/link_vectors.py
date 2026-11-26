#!/usr/bin/env python3
"""The hub link's test vectors (firmware/blinds_matter/test/wire/link.json), made with Python's 'cryptography', apart
from the firmware's code: the link key and its four proofs, a proven push, the pairing key with and without the hub's
setup code, and sealed frames (command and reply). The firmware (test/link_test.cpp), the app (Tests/main.swift) and
tools/test_tools.py all check the same file.

    python3 tools/link_vectors.py > firmware/blinds_matter/test/wire/link.json
"""
import json

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _hmac(key, data):
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def link_key(hub_key):
    return _hmac(hub_key, b'tilt-hub-link')


def proof(link, label, boot, msg):
    return _hmac(link, label.encode() + boot + msg.encode())[:16].hex()


def derive_key(shared, salt, cpub, dpub):
    return HKDF(hashes.SHA256(), 32, salt or None, b'blinds-v1' + cpub + dpub).derive(shared)


def seal(key, cid, boot, ctr, cmd):
    nonce = boot + ctr.to_bytes(8, 'big')
    return cid + nonce + AESGCM(key).encrypt(nonce, cmd.encode(), b'blinds-v1' + cid)


def seal_reply(key, cid, nonce, rnd, out):
    return rnd + AESGCM(key).encrypt(rnd, out.encode(), b'blinds-v1r' + cid + nonce)


def make():
    hub_key = bytes(range(32))
    boot = bytes.fromhex('a1b2c3d4')
    link = link_key(hub_key)
    push_json = '{"id":"a0b1c2d3e4f5","boot":"a1b2c3d4","bn":7}'
    push_n = 12
    ota_msg = '123456,d@1795319000'
    shared = bytes([0x11]) * 32
    cpub = b'\x04' + bytes(range(1, 65))
    dpub = b'\x04' + bytes(range(65, 129))
    salt = '12345678'
    key = derive_key(shared, b'', cpub, dpub)
    key_salted = derive_key(shared, salt.encode(), cpub, dpub)
    cid = bytes.fromhex('0102030405060708')
    ctr = 1795319000123
    cmd = '/api/home?b=0&lift=5000'
    rnd = bytes([7]) * 12
    out = '{"ok":1}'
    frame = seal(key, cid, boot, ctr, cmd)
    frame_salted = seal(key_salted, cid, boot, ctr, cmd)
    push_mac = proof(link, 'ctl-push', boot, push_json + str(push_n))
    return {
        'hubKey': hub_key.hex(),
        'boot': boot.hex(),
        'linkKey': link.hex(),
        'pushJson': push_json,
        'pushN': str(push_n),
        'proofPush': push_mac,
        'proofBye': proof(link, 'ctl-bye', boot, ''),
        'timeMsg': '1795319000',
        'proofTime': proof(link, 'hub-time', boot, '1795319000'),
        'otaMsg': ota_msg,
        'proofOta': proof(link, 'hub-ota', boot, ota_msg),
        'pushDatagram': (b'S00' + (push_json + '\n' + str(push_n) + '.' + push_mac).encode()).hex(),
        'shared': shared.hex(),
        'cpub': cpub.hex(),
        'dpub': dpub.hex(),
        'salt': salt,
        'key': key.hex(),
        'keySalted': key_salted.hex(),
        'cid': cid.hex(),
        'ctr': str(ctr),
        'cmd': cmd,
        'frame': frame.hex(),
        'frameSalted': frame_salted.hex(),
        'replyRnd': rnd.hex(),
        'replyOut': out,
        'reply': seal_reply(key, cid, frame[8:20], rnd, out).hex(),
    }


def text():
    return json.dumps(make(), indent=1) + '\n'


if __name__ == '__main__':
    print(text(), end='')
