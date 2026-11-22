"""Rotate the tilter's STLs into their print orientations (support-free) and drop them onto Z=0.

  python3 tools/orient.py        # writes hardware/mechanical/stl/tilter/print/*.stl
"""
import os
import shutil
import struct

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'hardware/mechanical/stl/tilter')
OUT = os.path.join(SRC, 'print')
ID = lambda x, y, z: (x, y, z)
FLIP = lambda x, y, z: (x, -y, -z)          # 180 deg about X
X_UP = lambda x, y, z: (z, y, -x)           # 90 deg about Y: -X becomes up
X_DOWN = lambda x, y, z: (-z, y, x)         # -90 deg about Y: -X goes down onto the bed


def read(path):
    """Triangles of a binary STL: (normal, v1, v2, v3) as 12 floats each."""
    with open(path, 'rb') as f:
        b = f.read()
    n = struct.unpack('<I', b[80:84])[0]
    return [struct.unpack('<12f', b[84 + 50 * i:84 + 50 * i + 48]) for i in range(n)]


def write(path, tris):
    with open(path, 'wb') as f:
        f.write(b'oriented for printing'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            f.write(struct.pack('<12fH', *t, 0))


def orient(tris, rot):
    out = []
    for t in tris:
        n = rot(*t[0:3])
        vs = [rot(*t[3 + 3 * k:6 + 3 * k]) for k in range(3)]
        out.append(n + vs[0] + vs[1] + vs[2])
    lo = [min(t[3 + 3 * k + j] for t in out for k in range(3)) for j in range(3)]
    hi = [max(t[3 + 3 * k + j] for t in out for k in range(3)) for j in range(3)]
    shift = (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])     # centered, standing on Z=0
    moved = []
    for t in out:
        v = list(t)
        for k in range(1, 4):
            for j in range(3):
                v[3 * k + j] += shift[j]
        moved.append(tuple(v))
    return moved, [h - l for h, l in zip(hi, lo)]


# Every printed part of one tilter: name -> (rotation, material, row on its Bambu plate, copies, how it sits).
# Listed in plate order (bambu.py packs each row left to right in this order).
PARTS = {
    # PLA row 0: housing
    'case_right': (X_UP, 'PLA', 0, 1, 'main half: back face down'),
    'case_left': (X_DOWN, 'PLA', 0, 1, 'lid: outer face down'),
    'bearing_shell': (X_DOWN, 'PLA', 0, 1, 'gear-side face down, cup bore up'),
    'motor_shell': (X_DOWN, 'PLA', 0, 1, 'motor face down, gear room up'),
    'tray': (ID, 'PLA', 0, 1, 'floor down, open top up'),
    'tray_lid': (FLIP, 'PLA', 0, 1, 'top face down, columns up; SUPPORT under the gear shelf'),
    # PLA row 1: drive
    'ring_cup': (X_UP, 'PLA', 1, 1, 'floor down, open end up'),
    'sun_27t': (X_DOWN, 'PLA', 1, 1, '27T down, sun up'),
    'worm_wheel': (FLIP, 'PLA', 1, 1, 'plain barrel end down, hex up'),
    'worm': (ID, 'PLA', 1, 1, 'standing on its thread end (brim), loop up'),
    'motor_pinion': (X_DOWN, 'PLA', 1, 1, 'flat'),
    'planet': (X_DOWN, 'PLA', 1, 4, 'flat'),
    # PETG: the parts that rub or mesh against PLA all the time
    'carrier': (X_DOWN, 'PETG', 0, 1, 'disc down, hub up'),
    'cluster': (X_UP, 'PETG', 0, 1, '20T down, 9T up'),
    'sensor_sleeve': (X_DOWN, 'PETG', 0, 1, 'gear face down on the bed, lugs up'),
    'magnet_gear': (FLIP, 'PETG', 0, 1, 'gear face down, magnet hub up'),
}


def copies(name):
    """File names of a part's printed copies: planet, planet_2, planet_3, planet_4."""
    return [name] + ['%s_%d' % (name, k) for k in range(2, PARTS[name][3] + 1)]


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (rot, _, _, count, how) in PARTS.items():
        tris, size = orient(read(os.path.join(SRC, name + '.stl')), rot)
        write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s%s' % (name, size[0], size[1], size[2], how,
                                                     ' (print %d)' % count if count > 1 else ''))
        for copy in copies(name)[1:]:
            shutil.copy(os.path.join(OUT, name + '.stl'), os.path.join(OUT, copy + '.stl'))
