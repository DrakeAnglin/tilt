#!/usr/bin/env python3
"""Talk to a blinds controller over its secured connection, the way the phone app does. For testing.
Needs the 'cryptography' package (it is in the ESP-IDF python: . ~/esp/esp-idf/export.sh).

  blinds_client.py hello                     who is there
  blinds_client.py pair [name]               first phone: become the owner
  blinds_client.py join <inv> <secret> [name]  pair with an invite the owner made
  blinds_client.py get '/api/s'              a command (any /api path with its ?query)
The key is kept in tools/.blinds_client.json (never commit it). --as NAME picks another saved identity; --ip sets the address.
"""
import base64, hashlib, hmac, json, os, struct, sys, time, urllib.request, urllib.error
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization

args = sys.argv[1:]
def opt(flag, default):
    if flag in args:
        i = args.index(flag); v = args[i + 1]; del args[i:i + 2]; return v
    return default
IP = opt('--ip', '192.168.50.135'); WHO = opt('--as', 'mac')
STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.blinds_client.json')
def load(): return json.load(open(STORE)) if os.path.exists(STORE) else {}
def save(d):
    json.dump(d, open(STORE, 'w'), indent=1); os.chmod(STORE, 0o600)
def http(path, data=None):
    req = urllib.request.Request('http://%s%s' % (IP, path), data=data, method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=8) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()

def pair(name, inv=None, secret=None):
    priv = ec.generate_private_key(ec.SECP256R1())
    cpub = priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    body = {'pub': base64.b64encode(cpub).decode(), 'name': name}
    salt = None
    if inv:
        salt = bytes.fromhex(secret)
        body['inv'] = inv; body['mac'] = hmac.new(salt, cpub, hashlib.sha256).hexdigest()
    st, raw = http('/x/pair', json.dumps(body).encode())
    if st != 200: raise SystemExit('pairing refused: %d %s' % (st, raw.decode()))
    r = json.loads(raw); dpub = base64.b64decode(r['pub'])
    shared = priv.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), dpub))
    key = HKDF(hashes.SHA256(), 32, salt, b'blinds-v1' + cpub + dpub).derive(shared)
    if hmac.new(key, b'confirm', hashlib.sha256).hexdigest()[:16] != r['check']: raise SystemExit('the controller derived a different key: not trusted')
    d = load(); d[WHO] = {'cid': r['cid'], 'key': key.hex(), 'ctr': 0}; save(d)
    print('paired as %s%s' % (name, ' (owner)' if r['owner'] else ''))

def call(cmd, raw_out=False, replay=None):
    d = load(); me = d[WHO]; cid = bytes.fromhex(me['cid']); key = bytes.fromhex(me['key'])
    for attempt in range(2):
        boot = bytes.fromhex(json.loads(http('/x/hello')[1])['boot'])
        me['ctr'] = max(me['ctr'] + 1, int(time.time() * 1000)); save(d)
        nonce = boot + struct.pack('>Q', me['ctr'])
        pkt = replay or (cid + nonce + AESGCM(key).encrypt(nonce, cmd.encode(), b'blinds-v1' + cid))
        st, raw = http('/x', pkt)
        if st == 200:
            out = AESGCM(key).decrypt(raw[:12], raw[12:], b'blinds-v1r' + cid + pkt[8:20])
            return (pkt, out.decode()) if raw_out else out.decode()
        if st != 409 or replay: return (pkt, 'refused: %d %s' % (st, raw.decode())) if raw_out else 'refused: %d %s' % (st, raw.decode())
    return 'refused'

if __name__ == '__main__':
    c = args[0] if args else 'hello'
    if c == 'hello': print(http('/x/hello')[1].decode())
    elif c == 'pair': pair(args[1] if len(args) > 1 else 'Mac test')
    elif c == 'join': pair(args[3] if len(args) > 3 else 'Mac guest', args[1], args[2])
    elif c == 'get': print(call(args[1]))
