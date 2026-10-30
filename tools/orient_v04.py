"""Rotate the v0.4 STLs into their print orientations (flat face on the bed, no supports) and drop them onto Z=0.

  python3 tools/orient_v04.py        # writes hardware/mechanical/stl/v0.4/print/*.stl

The exported STLs are in each part's own frame (cases: assembly frame, X along the rod).
"""
import glob
import os
import struct

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'hardware/mechanical/stl/v0.4')
OUT = os.path.join(SRC, 'print')

ID = lambda x, y, z: (x, y, z)
FLIP = lambda x, y, z: (x, -y, -z)          # 180° about X
X_UP = lambda x, y, z: (z, y, -x)           # 90° about Y: -X becomes up
X_DOWN = lambda x, y, z: (-z, y, x)         # -90° about Y: -X goes down onto the bed

ORIENT = {
    'case_left': (X_DOWN, 'outer face down (flat), split face and pockets up'),
    'case_right': (X_UP, 'back face down (bolt countersinks on the bed), split face, pegs and pin up'),
    'worm': (ID, 'one piece, standing on its thread end (brim), loop up; no supports needed'),
    'worm_wheel': (ID, 'barrel end down'),
    'motor_pinion': (ID, 'on a gear face (45° helical teeth print as 45° overhangs)'),
    'sensor_gear': (ID, 'gear face down, magnet pocket up'),
    'sensor_module': (X_DOWN, 'end wall on the bed, open face up; no supports'),
    'controller_tray': (ID, 'floor on the bed; no supports'),
    'controller_lid': (FLIP, 'top face on the bed, rod tunnel up; no supports'),
}


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
    shift = (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2])     # centred, standing on Z=0
    moved = []
    for t in out:
        v = list(t)
        for k in range(1, 4):
            for j in range(3):
                v[3 * k + j] += shift[j]
        moved.append(tuple(v))
    return moved, [h - l for h, l in zip(hi, lo)]


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(SRC, '*.stl'))):
        name = os.path.splitext(os.path.basename(path))[0]
        rot, how = ORIENT[name]
        tris, size = orient(read(path), rot)
        write(os.path.join(OUT, name + '.stl'), tris)
        print('%-13s %5.1f x %5.1f x %5.1f mm  %s' % (name, size[0], size[1], size[2], how))
