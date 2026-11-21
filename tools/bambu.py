"""Build the tilter's Bambu Studio project: every printed part of one tilter, on two plates.

  python3 tools/orient.py && python3 tools/bambu.py   # writes hardware/mechanical/stl/tilter/tilter_H2D_PLA_PETG.3mf

Plate 1 = PLA (filament 1): the whole housing and the gears that run in PLA.
Plate 2 = PETG (filament 2): the parts that rub or mesh against PLA all the time: carrier, cluster, sensor sleeve and
magnet gear. H2D 0.4 nozzle, 0.12 mm Fine, 4 walls, 40 % infill, auto brim, tree support where needed (the lid's gear
shelf). Parts are packed in rows about 7 mm apart round the middle of the bed. Also writes a PLA-only and a PETG-only
project.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT = os.path.join(REPO, 'hardware/mechanical/stl/tilter/print')
OUT = os.path.join(REPO, 'hardware/mechanical/stl/tilter/tilter_H2D_PLA_PETG.3mf')
SYSTEM = os.path.expanduser('~/Library/Application Support/BambuStudio/system/BBL')
CLI = '/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'

PRESETS = (('machine', 'Bambu Lab H2D 0.4 nozzle'), ('process', '0.12mm Fine @BBL H2D'),
           ('filament', 'Bambu PLA Basic @BBL H2D'), ('filament', 'Bambu PETG Basic @BBL H2D 0.4 nozzle'))
# Both filaments white (owner's choice): filament 1 = white PLA, filament 2 = white PETG.
TWEAKS = {'filament_colour': ['#FFFFFF', '#FFFFFF'], 'wall_loops': '4', 'sparse_infill_density': '40%',
          'brim_type': 'auto_brim',
          # PLA on one nozzle, PETG on the other; textured PEI suits both
          'filament_map': ['1', '2'], 'curr_bed_type': 'Textured PEI Plate',
          'enable_support': '1', 'support_type': 'tree(auto)', 'support_on_build_plate_only': '0',
          'support_threshold_angle': '30'}
PETG = {'carrier', 'cluster', 'sensor_sleeve', 'magnet_gear'}
PLATE_STEP = 420.0                 # Bambu Studio lays plates out 1.2 bed widths apart (H2D bed: 350 mm)
ROWS_PLA = [['case_right', 'case_left', 'bearing_shell', 'motor_shell', 'tray', 'tray_lid'],
            ['ring_cup', 'sun_27t', 'worm_wheel', 'worm', 'motor_pinion', 'planet', 'planet_2', 'planet_3', 'planet_4']]
ROWS_PETG = [['carrier', 'cluster', 'sensor_sleeve', 'magnet_gear']]
GAP, BED = 7.0, (175.0, 160.0)
LAYOUT = {}


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


def flatten(kind, name):
    d = json.load(open(os.path.join(SYSTEM, kind, name + '.json')))
    if d.get('inherits'):
        base = flatten(kind, d['inherits'])
        base.update(d)
        d = base
    return d


def main(only=None, out=OUT):
    """only=None: one project, two plates. only='PLA' / 'PETG': a one-plate project with just that material's parts."""
    if isinstance(only, (set, list, tuple)):               # a one-plate project with just the named parts
        names = [n for n in LAYOUT if n in only]
    else:
        names = [n for n in LAYOUT if only is None or (n in PETG) == (only == 'PETG')]
    tmp = tempfile.mkdtemp()
    files = []
    for n, (kind, name) in enumerate(PRESETS):
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        path = os.path.join(tmp, '%s%d.json' % (kind, n))
        json.dump(d, open(path, 'w'), indent=1)
        files.append(path)
    raw = os.path.join(tmp, 'raw.3mf')
    stls = [os.path.join(PRINT, n + '.stl') for n in names]
    subprocess.run([CLI, '--debug', '1', '--load-settings', files[0] + ';' + files[1], '--load-filaments', files[2] + ';' + files[3],
                    '--arrange', '1', '--orient', '0', '--export-3mf', raw] + stls,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = zipfile.ZipFile(raw)
    # object id -> part name (the project's object list is not in load order)
    part_of = dict(re.findall(r'<object id="(\d+)">\s*<metadata key="name" value="([^"]+)\.stl"',
                              src.read('Metadata/model_settings.config').decode()))
    model = src.read('3D/3dmodel.model').decode()

    def square(m):
        x, y = LAYOUT[part_of[m.group(2)]]
        if only is None and part_of[m.group(2)] in PETG:
            x += PLATE_STEP                                  # second plate
        z = m.group(3).split()[11]
        return '%stransform="1 0 0 0 1 0 0 0 1 %g %g %s"' % (m.group(1), x, y, z)   # no spin about Z
    model = re.sub(r'(<item objectid="(\d+)"[^>]*?)transform="([^"]+)"', square, model)
    order = [part_of[i] for i in re.findall(r'<item objectid="(\d+)"', model)]
    cfg = src.read('Metadata/model_settings.config').decode()

    def material(m):
        return m.group(1) + ('2' if m.group(2) in PETG else '1') + '"/>'
    cfg = re.sub(r'(<metadata key="name" value="([^"]+)\.stl"/>\s*<metadata key="extruder" value=")\d+"/>', material, cfg, )
    # split the single plate into two: PLA parts stay on plate 1, PETG parts go to a new plate 2
    plate = re.search(r'  <plate>.*?  </plate>\n', cfg, re.S).group(0) if only is None else None
    if plate:
        head = plate[:plate.index('    <model_instance>')]
        inst = re.findall(r'    <model_instance>.*?    </model_instance>\n', plate, re.S)
        def on(n, petg):
            return ''.join(i for i in inst if (part_of[re.search(r'object_id" value="(\d+)"', i).group(1)] in PETG) == petg)
        p1 = head + on(1, False) + '  </plate>\n'
        p2 = (head.replace('plater_id" value="1"', 'plater_id" value="2"').replace('_1.png', '_2.png')) + on(2, True) + '  </plate>\n'
        p1 = p1.replace('plater_name" value=""', 'plater_name" value="PLA housing"')
        p2 = p2.replace('plater_name" value=""', 'plater_name" value="PETG sensor gears"')
        cfg = cfg.replace(plate, p1 + p2)
    settings = json.loads(src.read('Metadata/project_settings.config'))
    settings.update(TWEAKS)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == '3D/3dmodel.model':
                dst.writestr(info, model)
            elif info.filename == 'Metadata/model_settings.config':
                dst.writestr(info, cfg)
            elif info.filename == 'Metadata/project_settings.config':
                dst.writestr(info, json.dumps(settings, indent=4))
            elif info.filename == 'Metadata/filament_sequence.json':
                dst.writestr(info, json.dumps({'plate_%d' % k: {'nozzle_sequence': [], 'optimal_assignment': [], 'sequence': []} for k in ((1, 2) if only is None else (1,))}))
            elif not info.filename.endswith('.png'):         # plate thumbnails are stale after the re-layout
                dst.writestr(info, src.read(info.filename))
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(out, REPO))
    print('PLA :', ', '.join(p for p in order if p not in PETG))
    print('PETG:', ', '.join(p for p in order if p in PETG))



if __name__ == '__main__':
    LAYOUT.update(pack(ROWS_PLA))
    LAYOUT.update(pack(ROWS_PETG))
    main(None, OUT)
    main('PLA', OUT.replace('PLA_PETG', 'PLA_only'))
    main('PETG', OUT.replace('PLA_PETG', 'PETG_only'))
