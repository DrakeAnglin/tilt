#!/usr/bin/env python3
"""Talk to a blinds controller over its secured connection, the way the phone app does. For testing.
Needs the 'cryptography' package (it is in the ESP-IDF python: . ~/esp/esp-idf/export.sh).

  blinds_client.py hello                     who is there
  blinds_client.py pair [name]               first phone: become the owner
  blinds_client.py join <inv> <secret> [name]  pair with an invite the owner made
  blinds_client.py get '/api/s'              a command (any /api path with its ?query)
The key is kept in tools/.blinds_client.json (never commit it). --as NAME picks another saved identity; --ip sets the
address (default: $BLINDS_IP, else 192.168.50.135).
"""
import base64, hashlib, hmac, json, os, struct, sys, time, urllib.request, urllib.error
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization

IP = os.environ.get('BLINDS_IP', '192.168.50.135')
WHO = 'mac'
STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.blinds_client.json')


def load():
    if not os.path.exists(STORE):
        return {}
    with open(STORE) as f:
        return json.load(f)


def save(d):
    # 0600 from the start: the file holds the keys
    with os.fdopen(os.open(STORE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
        json.dump(d, f, indent=1)
    os.chmod(STORE, 0o600)                     # an older file made before this may be wider


def http(path, data=None):
    req = urllib.request.Request('http://%s%s' % (IP, path), data=data, method='POST' if data is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=8) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()


# ---- the protocol, as pure functions
def derive_key(shared, salt, cpub, dpub):
    return HKDF(hashes.SHA256(), 32, salt, b'blinds-v1' + cpub + dpub).derive(shared)


def confirm(key):
    return hmac.new(key, b'confirm', hashlib.sha256).hexdigest()[:16]


def seal(key, cid, boot, ctr, cmd):
    """A command packet: cid (8) + nonce (boot 4 + counter 8) + AES-GCM of the command."""
    nonce = boot + struct.pack('>Q', ctr)
    return cid + nonce + AESGCM(key).encrypt(nonce, cmd.encode(), b'blinds-v1' + cid)


def open_reply(key, cid, pkt, raw):
    """The controller's answer to pkt: nonce (12) + AES-GCM, bound to the command's nonce."""
    return AESGCM(key).decrypt(raw[:12], raw[12:], b'blinds-v1r' + cid + pkt[8:20]).decode()


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
    key = derive_key(shared, salt, cpub, dpub)
    if confirm(key) != r['check']: raise SystemExit('the controller derived a different key: not trusted')
    d = load(); d[WHO] = {'cid': r['cid'], 'key': key.hex(), 'ctr': 0}; save(d)
    print('paired as %s%s' % (name, ' (owner)' if r['owner'] else ''))


def call(cmd, raw_out=False, replay=None):
    """Send one command. Returns the answer, or 'refused: ...'; with raw_out, (packet sent, that text)."""
    d = load()
    if WHO not in d: raise SystemExit('no saved identity "%s": pair first' % WHO)
    me = d[WHO]; cid = bytes.fromhex(me['cid']); key = bytes.fromhex(me['key'])
    for attempt in range(2):                   # a 409 means a stale boot id or counter: try once more
        boot = bytes.fromhex(json.loads(http('/x/hello')[1])['boot'])
        me['ctr'] = max(me['ctr'] + 1, int(time.time() * 1000)); save(d)
        pkt = replay or seal(key, cid, boot, me['ctr'], cmd)
        st, raw = http('/x', pkt)
        out = open_reply(key, cid, pkt, raw) if st == 200 else 'refused: %d %s' % (st, raw.decode())
        if st != 409 or replay: break
    return (pkt, out) if raw_out else out


def main(args):
    global IP, WHO
    def opt(flag, default):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args): raise SystemExit('%s needs a value' % flag)
            v = args[i + 1]; del args[i:i + 2]; return v
        return default
    IP = opt('--ip', IP); WHO = opt('--as', WHO)
    c = args[0] if args else 'hello'
    if c == 'hello': print(http('/x/hello')[1].decode())
    elif c == 'pair': pair(args[1] if len(args) > 1 else 'Mac test')
    elif c == 'join':
        if len(args) < 3: raise SystemExit('usage: blinds_client.py join <inv> <secret> [name]')
        pair(args[3] if len(args) > 3 else 'Mac guest', args[1], args[2])
    elif c == 'get':
        if len(args) < 2: raise SystemExit("usage: blinds_client.py get '/api/s'")
        out = call(args[1])
        if out.startswith('refused'): raise SystemExit(out)
        print(out)
    else:
        raise SystemExit('unknown command "%s" (hello, pair, join, get)' % c)


if __name__ == '__main__':
    main(sys.argv[1:])
