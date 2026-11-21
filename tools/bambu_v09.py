"""Build the v0.9 Bambu Studio project: EVERY printed part of one tilter, on two plates.

  python3 tools/orient_v09.py && python3 tools/bambu_v09.py   # writes hardware/mechanical/stl/v0.9/tilter_v09_H2D_PLA_PETG.3mf

Plate 1 = PLA (filament 1): the whole housing and the gears that ran in PLA before.
Plate 2 = PETG (filament 2): the parts that rub or mesh against PLA all the time: carrier (its hub turns in the worm
wheel), cluster (meshes with the sun piece and the motor pinion), sensor sleeve and magnet gear.
Presets and method are tools/bambu_v08.py's (H2D 0.4 nozzle, 0.12 mm Fine, 4 walls, 40 % infill, auto brim, tree
support where needed: the lid's gear shelf). Parts are packed in rows about 7 mm apart round the middle of the bed.
"""
import importlib.util
import os
import struct

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('b8', os.path.join(REPO, 'tools/bambu_v08.py'))
b8 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(b8)

PRINT = os.path.join(REPO, 'hardware/mechanical/stl/v0.9/print')
OUT = os.path.join(REPO, 'hardware/mechanical/stl/v0.9/tilter_v09_H2D_PLA_PETG.3mf')
PETG = {'carrier', 'cluster', 'sensor_sleeve', 'magnet_gear'}
ROWS_PLA = [['case_right', 'case_left', 'bearing_shell', 'motor_shell', 'tray', 'tray_lid'],
            ['ring_cup', 'sun_27t', 'worm_wheel', 'worm', 'motor_pinion', 'planet', 'planet_2', 'planet_3', 'planet_4']]
ROWS_PETG = [['carrier', 'cluster', 'sensor_sleeve', 'magnet_gear']]
GAP, BED = 7.0, (175.0, 160.0)


def size(name):
    b = open(os.path.join(PRINT, name + '.stl'), 'rb').read()
    n = struct.unpack('<I', b[80:84])[0]
    xs, ys = [], []
    for i in range(n):
        t = struct.unpack('<12f', b[84 + 50 * i:84 + 50 * i + 48])
        xs += [t[3], t[6], t[9]]
        ys += [t[4], t[7], t[10]]
    return max(xs) - min(xs), max(ys) - min(ys)


def pack(rows):
    """Rows of parts, each row centered on the bed, rows stacked front to back."""
    sz = {n: size(n) for r in rows for n in r}
    depth = [max(sz[n][1] for n in r) for r in rows]
    total = sum(depth) + GAP * (len(rows) - 1)
    out, y = {}, BED[1] + total / 2
    for r, d in zip(rows, depth):
        w = sum(sz[n][0] for n in r) + GAP * (len(r) - 1)
        x = BED[0] - w / 2
        for n in r:
            out[n] = (round(x + sz[n][0] / 2, 1), round(y - d / 2, 1))
            x += sz[n][0] + GAP
        y -= d + GAP
    return out


if __name__ == '__main__':
    b8.PRINT, b8.PETG = PRINT, PETG
    b8.LAYOUT = {}
    b8.LAYOUT.update(pack(ROWS_PLA))
    b8.LAYOUT.update(pack(ROWS_PETG))
    for n, c in b8.LAYOUT.items():
        print('%-14s %s  %s' % (n, 'PETG' if n in PETG else 'PLA ', c))
    b8.main(None, OUT)
    b8.main('PLA', OUT.replace('PLA_PETG', 'PLA_only'))
    b8.main('PETG', OUT.replace('PLA_PETG', 'PETG_only'))
