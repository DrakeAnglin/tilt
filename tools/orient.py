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
    b = open(path, 'rb').read()
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



ORIENT = {
    # housing
    'case_right': (X_UP, 'main half: back face down'),
    'case_left': (X_DOWN, 'lid: outer face down'),
    'bearing_shell': (X_DOWN, 'gear-side face down, cup bore up'),
    'motor_shell': (X_DOWN, 'motor face down, gear room up'),
    'tray': (ID, 'floor down, open top up'),
    'tray_lid': (FLIP, 'top face down, columns up; SUPPORT under the gear shelf'),
    'worm': (ID, 'standing on its thread end (brim), loop up'),
    # sensor
    'sensor_sleeve': (X_DOWN, 'gear face down on the bed, lugs up'),
    'magnet_gear': (FLIP, 'gear face down, magnet hub up'),
    # drive
    'worm_wheel': (FLIP, 'plain barrel end down, hex up'),
    'ring_cup': (X_UP, 'floor down, open end up'),
    'carrier': (X_DOWN, 'disc down, hub up'),
    'planet': (X_DOWN, 'flat (print 4)'),
    'sun_27t': (X_DOWN, '27T down, sun up'),
    'cluster': (X_UP, '20T down, 9T up'),
    'motor_pinion': (X_DOWN, 'flat'),
}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for name, (rot, how) in ORIENT.items():
        tris, size = orient(read(os.path.join(SRC, name + '.stl')), rot)
        write(os.path.join(OUT, name + '.stl'), tris)
        print('%-15s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
    for k in (2, 3, 4):
        shutil.copy(os.path.join(OUT, 'planet.stl'), os.path.join(OUT, 'planet_%d.stl' % k))
