#!/usr/bin/env python3
"""A device's identity, made on this Mac at its first USB flash, and its setup label.

  tools/device_identity.py flash hub|controller --port <p> [--new-identity] [--label-size WxH]
  tools/device_identity.py labels [<id or short id> | --all] [--label-size WxH]

A Tilt Hub gets its Apple Home code (passcode, discriminator, salt, SPAKE2+ verifier) and its 8-digit setup code here,
written into its saved data (NVS namespace "hub") before its first start; the firmware uses them when they are there
and makes its own when they are not. A controller gets a record and an ID label, no code. Records are one JSON file per
device in ~/.tilt/devices/ (TILT_DEVICES overrides): secrets, never in Git, CI, logs or releases. No code is ever
printed: the tool prints the label's path. tools/flash_hub.sh --usb and tools/flash.sh --usb call this.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FW = {'hub': os.path.join(ROOT, 'firmware', 'tilt_hub'), 'controller': os.path.join(ROOT, 'firmware', 'blinds_matter')}
HOME_CODE_MAGIC = 0x48430001                     # logic.h
ITERATIONS = 1000
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


# ---- the Matter setup code: the same rules and the same strings as the firmware (logic.h, hub_matter.h)
def pin_valid(pin):
    """setupPinValid in logic.h: 1..99999998, not 11111111 and the like, not 12345678 or 87654321."""
    if pin <= 0 or pin > 99999998 or pin in (12345678, 87654321):
        return False
    return pin % 11111111 != 0


def verifier(pin, salt, iterations):
    """The 97-byte SPAKE2+ verifier Matter keeps: w0 (32 bytes) and L = w1 * G (65 bytes, uncompressed)."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    ws = hashlib.pbkdf2_hmac('sha256', struct.pack('<I', pin), salt, iterations, 80)
    w0 = int.from_bytes(ws[:40], 'big') % P256_N
    w1 = int.from_bytes(ws[40:], 'big') % P256_N
    L = ec.derive_private_key(w1, ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return w0.to_bytes(32, 'big') + L


_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4]]
for _i in range(2, 8):
    _P.append([_P[1][_P[_i - 1][j]] for j in range(10)])
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff(digits, check_appended):
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + (0 if check_appended else 1)) % 8][int(ch)]]
    return c


def verhoeff_ok(digits):
    return _verhoeff(digits, True) == 0


def manual_code(disc, pin):
    """The 11-digit code (standard flow): version 0, no vendor and product, the discriminator's top 4 bits."""
    short = disc >> 8
    body = '%d%05d%04d' % (short >> 2, ((short & 3) << 14) | (pin & 0x3FFF), pin >> 14)
    return body + str(_INV[_verhoeff(body, False)])


_B38 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.'


def qr_payload(disc, pin, vid, pid):
    """The MT: text in the QR: version 0, BLE (2), standard flow, packed least significant bit first, in Base38."""
    v = vid << 3 | pid << 19 | 0 << 35 | 2 << 37 | disc << 45 | pin << 57
    data = v.to_bytes(11, 'little')
    out = ''
    for i in range(0, len(data), 3):
        chunk = data[i:i + 3]
        n = int.from_bytes(chunk, 'little')
        for _ in range([2, 4, 5][len(chunk) - 1]):
            out += _B38[n % 38]
            n //= 38
    return 'MT:' + out


# ---- a hub's identity: its Apple Home code and its setup code
def new_identity():
    """A new random Apple Home code and 8-digit setup code (Python's secrets: the OS's random source)."""
    pin = 0
    while not pin_valid(pin):
        pin = secrets.randbelow(100000000)
    salt = secrets.token_bytes(32)
    return {'passcode': pin, 'discriminator': secrets.randbelow(4096), 'iterations': ITERATIONS, 'salt': salt.hex(),
            'verifier': verifier(pin, salt, ITERATIONS).hex(), 'setup_code': '%08d' % secrets.randbelow(100000000)}


_make_identity = new_identity                    # flash() has a flag of the same name


def home_code_blob(ident):
    """struct HomeCode in logic.h, as the firmware keeps it: magic, pin, iter, disc, salt[32], verifier[97], 1 pad byte."""
    salt, ver = bytes.fromhex(ident['salt']), bytes.fromhex(ident['verifier'])
    if len(salt) != 32 or len(ver) != 97:
        raise ValueError('salt must be 32 bytes and verifier 97')
    return struct.pack('<IIIH32s97sx', HOME_CODE_MAGIC, ident['passcode'], ident['iterations'], ident['discriminator'], salt, ver)


def nvs_csv(ident):
    """The NVS image's contents (esp-idf nvs_partition_gen): the hub's namespace with its two codes, nothing else."""
    return ('key,type,encoding,value\nhub,namespace,,\nhomecode,data,hex2bin,%s\npin,data,string,%s\n'
            % (home_code_blob(ident).hex(), ident['setup_code']))


# ---- what a USB flash does
def has_code(nvs_dump):
    """Whether the device's saved data holds an Apple Home code (the key name, as NVS stores it: 16 bytes, 0-padded)."""
    return b'homecode\0' in nvs_dump


def plan(record, nvs_dump, new_identity):
    """new: make one and write it. restore: write the saved one back. firmware: firmware only. own: firmware only, the
    device made its own code. replace: wipe and make a new one (--new-identity, asked first).
    A run that made a code did not finish (its record is still marked pending):
      finish: the hub already holds that code; firmware only, then the record is done.
      resume: the hub holds no code; write the pending one.
      resume_replace: the hub holds another code (it may be in a home); wipe and write only if the owner says so."""
    if new_identity:
        return 'replace'
    if record and record.get('pending'):
        if not has_code(nvs_dump):
            return 'resume'
        return 'finish' if holds(nvs_dump, record) else 'resume_replace'
    if has_code(nvs_dump):
        return 'firmware' if record else 'own'
    return 'restore' if record else 'new'


def holds(nvs_dump, record):
    """Whether the hub holds this record's Apple Home code: NVS keeps a blob's bytes in a row, so its 144 bytes are
    in the dump."""
    return 'salt' in record and home_code_blob(record) in nvs_dump


# ---- records on this Mac only
def devices_dir():
    return os.environ.get('TILT_DEVICES') or os.path.join(os.path.expanduser('~'), '.tilt', 'devices')


def _path(device_id):
    if not re.fullmatch(r'[0-9a-z]+', device_id):
        raise ValueError('not a device id: %r' % device_id)
    return os.path.join(devices_dir(), device_id + '.json')


def save(record):
    d = devices_dir()
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)
    path = _path(record['id'])
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(record, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
    return path


def load(device_id):
    try:
        with open(_path(device_id)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def records():
    d = devices_dir()
    names = sorted(os.listdir(d)) if os.path.isdir(d) else []
    return [load(n[:-5]) for n in names if re.fullmatch(r'[0-9a-z]+\.json', n)]


def find(key):
    key = key.lower()
    hits = [r for r in records() if r and key in (r['id'], r.get('short'))]
    if not hits:
        raise LookupError('no device %s in %s' % (key, devices_dir()))
    if len(hits) > 1:
        raise LookupError('%s is the short ID of more than one device: %s (use the full ID)'
                          % (key, ', '.join(r['id'] for r in hits)))
    return hits[0]


# ---- the setup label (Pillow + qrcode)
DEFAULT_SIZE = (25.0, 25.0)                      # mm: a 1 x 1 in square label (the issue's default)
DPI = 300
MIN_MODULE_PX = 3                                # the smallest QR module a phone still reads at 300 dpi


def parse_size(text):
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*', text)
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        raise ValueError('label size is W x H in mm, for example 25x25')
    return float(m.group(1)), float(m.group(2))


def dashed(code):
    return '%s-%s-%s' % (code[:4], code[4:7], code[7:]) if len(code) == 11 else '%s-%s' % (code[:4], code[4:])


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                            # Pillow before 10.1: one small built-in font
        return ImageFont.load_default()


def _text(draw, box, lines):
    """Lines in the box (x0, y0, x1, y1), all at one size, as large as fits."""
    x0, y0, x1, y1 = box
    size = int((y1 - y0) / (len(lines) * 1.15))
    while size > 6:
        font = _font(size)
        if all(draw.textlength(t, font=font) <= x1 - x0 for t in lines):
            break
        size -= 1
    font = _font(size)
    step = (y1 - y0) / len(lines)
    for i, t in enumerate(lines):
        draw.text((x0, y0 + i * step + step / 2), t, fill=0, font=font, anchor='lm')


def label_image(record, size_mm=DEFAULT_SIZE, dpi=DPI):
    """The label as a Pillow image, and where the QR is: (x0, y0, pixels per module), or None (a controller)."""
    from PIL import Image, ImageDraw
    w, h = (round(v / 25.4 * dpi) for v in size_mm)
    img = Image.new('L', (w, h), 255)
    draw = ImageDraw.Draw(img)
    pad = max(2, h // 20)
    if record['kind'] != 'hub':
        _text(draw, (pad, pad, w - pad, h - pad), ['Tilt controller', 'ID ' + record['short']])
        return img, None
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    q.add_data(record['qr'])
    q.make(fit=True)
    matrix = q.get_matrix()                       # with its 4-module quiet zone
    n = len(matrix)
    wide = w >= 1.6 * h                          # wide: the QR on the left; square or tall: the QR above the text
    side = min(h, w // 2) if wide else min(w, int(h * 0.55))
    px = side // n
    if px < MIN_MODULE_PX:
        need = MIN_MODULE_PX * n
        mm = lambda p: -(-p * 254 // (dpi * 10))  # px to whole mm, rounded up
        raise ValueError('a %g x %g mm label is too small for a QR that scans: the smallest that works is %d x %d mm'
                         % (size_mm[0], size_mm[1], mm(2 * need), mm(need)))
    if wide:
        x0, y0 = (side - px * n) // 2, (h - px * n) // 2
        box = (side + pad, pad, w - pad, h - pad)
        lines = ['Apple Home', dashed(record['manual_code']), 'Tilt app', dashed(record['setup_code']), 'ID ' + record['short']]
    else:
        x0, y0 = (w - px * n) // 2, 0
        box = (pad, px * n, w - pad, h - pad)
        lines = ['Apple Home ' + dashed(record['manual_code']), 'Tilt app ' + dashed(record['setup_code']), 'ID ' + record['short']]
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                draw.rectangle([x0 + c * px, y0 + r * px, x0 + (c + 1) * px - 1, y0 + (r + 1) * px - 1], fill=0)
    _text(draw, box, lines)
    return img, (x0, y0, px)


def label(record, size_mm=DEFAULT_SIZE, dpi=DPI):
    """Write <id>.png and <id>.pdf next to the record (owner-only files); returns their paths."""
    img, _ = label_image(record, size_mm, dpi)
    out = []
    for ext, kw in (('png', {'dpi': (dpi, dpi)}), ('pdf', {'resolution': dpi})):
        path = os.path.join(devices_dir(), '%s.%s' % (record['id'], ext))
        os.makedirs(devices_dir(), mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            img.save(f, ext.upper(), **kw)
        out.append(path)
    return tuple(out)


# ---- the runner: the only part that talks to the device (esptool), the NVS image tool and build.sh, all through run()
def _run(cmd, cwd=None):                         # hardware glue: the tests swap it for a fake device
    r = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode:
        raise RuntimeError('%s failed:\n%s' % (os.path.basename(cmd[0]) if cmd[0] != sys.executable else cmd[2],
                                               '\n'.join(r.stdout.splitlines()[-15:])))
    return r.stdout


def _ask(prompt):
    if not sys.stdin.isatty():
        return None
    return input(prompt)


def parse_mac(text):
    """The chip's base MAC (the one the firmware reads as ESP_MAC_WIFI_STA), from esptool read_mac, as 12 hex digits."""
    six = r'((?:[0-9a-f]{2}:){5}[0-9a-f]{2})(?![0-9a-f:])'
    m = re.search(r'BASE MAC: ' + six, text, re.I)
    if not m:
        found = list(re.finditer(r'\bMAC: ' + six, text, re.I))
        m = found[-1] if found else None
    if not m:
        raise RuntimeError('esptool did not give the chip\'s MAC')
    return m.group(1).replace(':', '').lower()


def vendor_product(fw_dir):
    """The vendor and product ID the build uses (its sdkconfig), so they are never typed in twice."""
    with open(os.path.join(fw_dir, 'sdkconfig')) as f:
        text = f.read()
    get = lambda k: int(re.search(r'^CONFIG_DEVICE_%s_ID=(\S+)' % k, text, re.M).group(1), 0)
    return get('VENDOR'), get('PRODUCT')


def nvs_area(fw_dir):
    """The NVS partition's offset and size, from the firmware's partitions.csv."""
    with open(os.path.join(fw_dir, 'partitions.csv')) as lines:
        for line in lines:
            f = [x.strip() for x in line.split('#')[0].split(',')]
            if len(f) >= 5 and f[0] == 'nvs':
                return f[3], f[4]
    raise RuntimeError('no nvs partition in partitions.csv')


def _today():
    return datetime.date.today().isoformat()


def no_label_libraries(short):
    """What to run when Pillow or qrcode is missing: with this same Python, which also has esptool."""
    import shlex
    py, me = shlex.quote(sys.executable), shlex.quote(os.path.abspath(__file__))
    return ('no label: this Python has no Pillow or qrcode. Once: %s -m pip install pillow qrcode\n'
            'then: %s %s labels %s' % (py, py, me, shlex.quote(short)))


def _write_label(rec, size_mm, out):
    try:
        png, _ = label(rec, size_mm)
    except ImportError:
        print('record saved. ' + no_label_libraries(rec['short']), file=out)
        return
    print('label: %s (and .pdf)' % png, file=out)


def _check_size(kind, size_mm):
    """Refuse a label size before anything touches the device (a dummy code of the real length)."""
    dummy = {'kind': kind, 'id': 'hub000000000000', 'short': '0000', 'manual_code': '0' * 11, 'setup_code': '0' * 8,
             'qr': qr_payload(0xFFF, 99999998, 0xFFFF, 0xFFFF)}
    try:
        label_image(dummy, size_mm)
    except ImportError:
        pass


UNPLUG = 'Unplug the device and plug it back in to start it.'


def flash(kind, port, new_identity=False, size_mm=DEFAULT_SIZE, run=_run, ask=_ask, out=None, fw_dir=None):
    """A USB flash of a hub or a controller. Returns 0, or 1 when it refuses or a step fails."""
    out = out or sys.stdout
    fw_dir = fw_dir or FW[kind]
    build = os.path.join(fw_dir, 'build.sh')
    esptool = [sys.executable, '-m', 'esptool', '--chip', 'esp32c6', '--port', port, '--after', 'no_reset']
    if new_identity and kind != 'hub':
        print('refused: a controller has no code from the Mac (reset it from the app)', file=out)
        return 1
    try:
        _check_size(kind, size_mm)
    except ValueError as e:
        print('refused: %s' % e, file=out)
        return 1
    typed = None
    if new_identity:
        typed = ask('This wipes the hub\'s saved data and gives it a new code: the old label stops working.\n'
                    'Type the short ID on its label to go on: ') if ask else None
        if typed is None:
            print('refused: --new-identity asks first, and there is no terminal to ask on', file=out)
            return 1
    tmp = tempfile.mkdtemp(prefix='tilt-nvs-')    # 0700; the device's saved data and the NVS image never stay
    record = None
    try:
        mac = parse_mac(run(esptool + ['read_mac']))
        dev_id = ('hub' if kind == 'hub' else '') + mac
        short = dev_id[-4:]
        if typed is not None and typed.strip().lower() != short:
            print('refused: that is not this hub\'s short ID; nothing was changed. ' + UNPLUG, file=out)
            return 1
        from release_ci import code_version
        record = load(dev_id)
        if kind == 'controller':
            run([build], cwd=fw_dir)
            run([build, '-p', port, 'flash'], cwd=fw_dir)
            record = dict(record or {}, kind='controller', id=dev_id, short=short, flashed=_today(),
                          firmware=code_version('controller'))
            print('record: %s' % save(record), file=out)
            _write_label(record, size_mm, out)
            return 0
        offset, size = nvs_area(fw_dir)
        dump = os.path.join(tmp, 'nvs-read.bin')
        run(esptool + ['read_flash', offset, size, dump])
        with open(dump, 'rb') as f:
            saved = f.read()
        action = plan(record, saved, new_identity)
        mismatch = action == 'firmware' and not holds(saved, record)
        if action == 'resume_replace':
            typed = ask('A run of this tool did not finish, and this hub now holds another code (it may be in a home).\n'
                        'Writing the code saved on this Mac wipes its saved data. Type its short ID to go on: '
                        ) if ask else None
            if typed is None or typed.strip().lower() != short:
                record = None                     # nothing pending was touched: no "run again" hint
                print('refused: nothing was changed. To keep the hub as it is, delete %s; to give it the code '
                      'saved on this Mac, run again on a terminal and type its short ID. %s' % (_path(dev_id), UNPLUG),
                      file=out)
                return 1
        print('building the firmware (a few minutes)', file=out)
        run([build], cwd=fw_dir)
        if action in ('new', 'replace'):
            vid, pid = vendor_product(fw_dir)
            ident = _make_identity()
            fresh = dict(ident, kind='hub', id=dev_id, short=short, flashed=_today(), firmware=code_version('hub'),
                         manual_code=manual_code(ident['discriminator'], ident['passcode']),
                         qr=qr_payload(ident['discriminator'], ident['passcode'], vid, pid), pending=True)
            old = _path(dev_id)
            if action == 'replace' and os.path.exists(old):
                os.replace(old, old[:-5] + '.replaced-%s.json' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
            record = fresh
            save(record)                          # before anything is written to the hub: a code is never lost
        if action in ('replace', 'resume_replace'):
            run(esptool + ['erase_region', offset, size])
        if action in ('new', 'restore', 'replace', 'resume', 'resume_replace'):
            csv_path, image = os.path.join(tmp, 'nvs.csv'), os.path.join(tmp, 'nvs.bin')
            fd = os.open(csv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(nvs_csv(record))
            run([sys.executable, '-m', 'esp_idf_nvs_partition_gen', 'generate', csv_path, image, size])
            run(esptool + ['write_flash', offset, image])
        run([build, '-p', port, 'flash'], cwd=fw_dir)
        if action in ('new', 'replace', 'resume', 'resume_replace', 'finish'):
            record.pop('pending', None)
            print('record: %s' % save(record), file=out)
            _write_label(record, size_mm, out)
        elif action == 'restore':
            print('wrote its saved code back: the old label still works', file=out)
        elif action == 'own':
            print('this hub made its own code before (the app shows it); no record or label made', file=out)
        elif mismatch:
            print('firmware only. Warning: the code on this hub is not the one saved on this Mac, so its label from '
                  'this Mac does not match it (the app shows the hub\'s own code)', file=out)
        else:
            print('firmware only: its code is unchanged', file=out)
        return 0
    except RuntimeError as e:
        print(str(e), file=out)
        if record and record.get('pending'):
            print('Its new code is saved on this Mac: run the same command again, without --new-identity, to finish.',
                  file=out)
        print(UNPLUG, file=out)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('flash', help='a first flash over USB')
    f.add_argument('kind', choices=['hub', 'controller'])
    f.add_argument('--port', required=True)
    f.add_argument('--new-identity', action='store_true',
                   help='developer flag: wipe the hub\'s saved data and make a new code (asks first)')
    f.add_argument('--label-size', type=parse_size, default=DEFAULT_SIZE, metavar='WxH', help='mm (default 25x25)')
    lb = sub.add_parser('labels', help='write a saved device\'s label again')
    lb.add_argument('device', nargs='?', help='full or short ID')
    lb.add_argument('--all', action='store_true')
    lb.add_argument('--label-size', type=parse_size, default=DEFAULT_SIZE, metavar='WxH', help='mm (default 25x25)')
    a = p.parse_args(argv)
    if a.cmd == 'flash':
        return flash(a.kind, a.port, a.new_identity, a.label_size)
    try:
        chosen = [r for r in records() if r] if a.all else [find(a.device or '')]
        for r in chosen:
            print('label: %s (and .pdf)' % label(r, a.label_size)[0])
    except (LookupError, ValueError) as e:
        print(e)
        return 1
    except ImportError:
        print(no_label_libraries(a.device or '--all'))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
