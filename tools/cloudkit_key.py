#!/usr/bin/env python3
"""The Tilt Hub's iCloud key (push alerts, firmware/tilt_hub/main/cloud.h).

  cloudkit_key.py new              make a key pair (~/.tilt/cloudkit-key.pem) and print the public key to paste
                                   into CloudKit Console > Tilt > Tokens & Keys > Server-to-Server Keys
  cloudkit_key.py header DEV_ID PROD_ID
                                   write firmware/tilt_hub/main/cloud_key.h (not in Git) for the next hub build. CloudKit
                                   keys are per environment: add the same public key in Development and in Production
  cloudkit_key.py test TOPIC [KIND] [ENV]
                                   send one Alert from this Mac, signed the same way the hub does it
                                   (ENV: development (default) or production)

Run with the ESP-IDF python (it has `cryptography`):
  ~/.espressif/python_env/idf5.5_py3.9_env/bin/python tools/cloudkit_key.py new
"""
import base64, datetime, hashlib, json, os, sys, time, urllib.request, urllib.error
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

KEY = os.path.expanduser("~/.tilt/cloudkit-key.pem")
IDF = os.path.expanduser("~/.tilt/cloudkit-key-ids.json")
HEADER = os.path.join(os.path.dirname(__file__), "..", "firmware", "tilt_hub", "main", "cloud_key.h")
CONTAINER = "iCloud.app.tilt.blinds"


def load():
    with open(KEY, "rb") as f:
        return serialization.load_pem_private_key(f.read(), None)


def new():
    if os.path.exists(KEY):
        sys.exit(f"{KEY} is already there: delete it first to make a new one")
    os.makedirs(os.path.dirname(KEY), exist_ok=True)
    k = ec.generate_private_key(ec.SECP256R1())
    with open(os.open(KEY, os.O_WRONLY | os.O_CREAT, 0o600), "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    pub = k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    print("Paste this public key into CloudKit Console (Tokens & Keys > Server-to-Server Keys > +):\n")
    print(pub)


def header(key_id, prod_id):
    d = load().private_numbers().private_value.to_bytes(32, "big").hex()
    with open(IDF, "w") as f:
        json.dump({"development": key_id, "production": prod_id}, f)
    with open(HEADER, "w") as f:
        f.write("// The Tilt Hub's iCloud key (push alerts). Made by tools/cloudkit_key.py; never commit it.\n#pragma once\n")
        f.write(f'#define CLOUD_KEY_ID "{key_id}"\n#define CLOUD_KEY_ID_PROD "{prod_id}"\n#define CLOUD_KEY_HEX "{d}"\n')
    print(f"wrote {os.path.normpath(HEADER)}: build and update the hub (tools/flash_hub.sh)")


def post(env, op, body):
    sub = f"/database/1/{CONTAINER}/{env}/public/records/{op}"
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = json.dumps(body, separators=(",", ":")).encode()
    msg = f"{date}:{base64.b64encode(hashlib.sha256(raw).digest()).decode()}:{sub}".encode()
    sig = base64.b64encode(load().sign(msg, ec.ECDSA(hashes.SHA256()))).decode()
    req = urllib.request.Request("https://api.apple-cloudkit.com" + sub, raw, method="POST", headers={
        "Content-Type": "application/json", "X-Apple-CloudKit-Request-KeyID": json.load(open(IDF))[env],
        "X-Apple-CloudKit-Request-ISO8601Date": date, "X-Apple-CloudKit-Request-SignatureV1": sig})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test(topic, kind="test", env="development"):
    rec = {"recordType": "Alert", "recordName": f"alert-{topic}-{kind}-9", "fields": {
        "topic": {"value": topic}, "kind": {"value": kind}, "name": {"value": "Test"}, "detail": {"value": ""},
        "port": {"value": 9}, "n": {"value": int(time.time())}, "at": {"value": int(time.time() * 1000), "type": "TIMESTAMP"}}}
    print(*post(env, "modify", {"operations": [{"operationType": "forceReplace", "record": rec}]}))


def main(a):
    if a[:1] == ["new"]: new()
    elif a[:1] == ["header"] and len(a) == 3: header(a[1], a[2])
    elif a[:1] == ["test"] and len(a) >= 2: test(*a[1:4])
    else: print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
