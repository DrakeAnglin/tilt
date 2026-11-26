"""Build the two Tilt print projects for Bambu Studio / MakerWorld.

  python3 tools/orient.py && python3 tools/bambu_project.py     # writes both into hardware/mechanical/stl/

  tilt_bulk_H2D.3mf             one tilter, 3 plates, one material per plate (BULK below):
                                  1 tilter boxes (PLA)  2 tilter gears (PLA)  3 tilter gears (PETG)
  tilt_parts_H2D.3mf            one tilter part per plate, in the order the tilter goes together (SINGLE below).
                                  Reprint one part from here when a bulk plate goes wrong.
  tilt_controller_box_H2D.3mf   the controller box on its own (CONTROLLER below): 1 tray and lid together,
                                  2 tray only, 3 lid only.

Slice them in the Bambu Studio app (Slice all). Studio 2.9's command line will not slice for the H2D ("No valid nozzle
found"), not even the older tilter project.

Settings are set per part, so nothing is changed by hand: a brim on the parts that are tall or tiny and could tip or
lift (BRIM), supports only on the tray lid, the worm and the worm wheel (SUPPORT). Everything else has no brim and no
support. H2D, 0.4 nozzle, 0.12 mm Fine, white PLA on filament 1, white PETG on filament 2 (as tools/bambu.py).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orient import PARTS, copies, read  # noqa: E402
from bambu import CLI, PRESETS, flatten  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STL = os.path.join(REPO, 'hardware/mechanical/stl')

# Where each printed file is. Tilter parts come turned for the bed (tools/orient.py); the box halves already lie flat.
BOX = ('controller_tray', 'controller_lid')


def path(name):
    if name in BOX:
        return os.path.join(STL, 'controller', name + '.stl')
    return os.path.join(STL, 'tilter/print', name + '.stl')


def material(name):
    return 'PLA' if name in BOX else PARTS[name.split('_')[0] if name.startswith('planet') else name][1]


SUPPORT = {'tray_lid', 'worm', 'worm_wheel'}           # the owner's list: the lid's gear shelf, the worm, the wheel
# Brim width in mm. Tall and narrow (worm 4.8 x taller than wide, sleeve 2.4 x, wheel 1.2 x, carrier 1.0 x) or a small
# foot on the bed (magnet gear, planets: 22 mm2 each).
BRIM = {'worm': 5, 'sensor_sleeve': 5, 'worm_wheel': 4, 'carrier': 3, 'magnet_gear': 3,
        'planet': 3, 'planet_2': 3, 'planet_3': 3, 'planet_4': 3}

NAMES = {'case_right': 'Worm case main half', 'case_left': 'Worm case lid', 'worm_wheel': 'Worm wheel',
         'worm': 'Worm', 'ring_cup': 'Ring cup', 'planet': 'Planets (4)', 'carrier': 'Carrier (PETG)',
         'bearing_shell': 'Bearing shell', 'sun_27t': 'Sun gear 27T', 'motor_shell': 'Motor shell',
         'motor_pinion': 'Motor pinion', 'cluster': 'Cluster gear (PETG)', 'sensor_sleeve': 'Sensor sleeve (PETG)',
         'tray': 'Tray', 'magnet_gear': 'Magnet gear (PETG)', 'tray_lid': 'Tray lid',
         'controller_tray': 'Controller box tray', 'controller_lid': 'Controller box lid'}
# One plate per part, in the order the tilter goes together (hardware/mechanical/stl/tilter/README.md, Assembly).
BUILD = ['case_right', 'worm_wheel', 'worm', 'case_left', 'ring_cup', 'planet', 'carrier', 'bearing_shell', 'sun_27t',
         'motor_shell', 'motor_pinion', 'cluster', 'sensor_sleeve', 'tray', 'magnet_gear', 'tray_lid']


def rows(mat):
    """orient.PARTS's plate rows for one material, each row a list of printed file names."""
    out = []
    for name, (_, m, row, _, _) in PARTS.items():
        if m == mat:
            out += [[] for _ in range(row + 1 - len(out))]
            out[row] += copies(name)
    return out


PLA_ROWS = rows('PLA')               # orient.PARTS row 0 is the housing, row 1 the drive
BULK = [('1 Tilter boxes (PLA)', [PLA_ROWS[0][:3], PLA_ROWS[0][3:]]),
        ('2 Tilter gears (PLA)', [PLA_ROWS[1]]),
        ('3 Tilter gears (PETG)', rows('PETG'))]
SINGLE = [('%02d %s' % (k + 1, NAMES[n]), [copies(n)] if n in PARTS else [[n]]) for k, n in enumerate(BUILD)]
CONTROLLER = [('1 Controller box (PLA)', [[BOX[0]], [BOX[1]]]),
              ('2 %s' % NAMES[BOX[0]], [[BOX[0]]]),
              ('3 %s' % NAMES[BOX[1]], [[BOX[1]]])]
PROJECTS = {'tilt_bulk_H2D.3mf': BULK, 'tilt_parts_H2D.3mf': SINGLE, 'tilt_controller_box_H2D.3mf': CONTROLLER}

H2D = (350.0, 320.0)                # bed
GAP = 7.0                           # between parts on a plate (owner: keep parts close together)


def stride(n):
    """Bambu Studio puts plate k of n at a grid spot: ceil(sqrt(n)) columns, 1.2 bed widths apart, rows going -Y."""
    cols = int(n ** 0.5)
    cols += cols * cols < n
    return cols, H2D[0] * 1.2, H2D[1] * 1.2


def size(name):
    """Footprint (x, y) on the bed, brim included."""
    tris = read(path(name))
    xs = [t[j] for t in tris for j in (3, 6, 9)]
    ys = [t[j] for t in tris for j in (4, 7, 10)]
    b = 2 * BRIM.get(name, 0)
    return max(xs) - min(xs) + b, max(ys) - min(ys) + b


def pack(rows):
    """Each row centered on the bed, rows stacked front to back round the bed's middle: {file name: (x, y)}."""
    sz = {n: size(n) for r in rows for n in r}
    depth = [max(sz[n][1] for n in r) for r in rows]
    total = sum(depth) + GAP * (len(rows) - 1)
    out, y = {}, H2D[1] / 2 + total / 2
    for r, d in zip(rows, depth):
        w = sum(sz[n][0] for n in r) + GAP * (len(r) - 1)
        assert w < H2D[0] - 20 and total < H2D[1] - 20, 'plate too full'
        x = H2D[0] / 2 - w / 2
        for n in r:
            out[n] = (x + sz[n][0] / 2, y - d / 2)
            x += sz[n][0] + GAP
        y -= d + GAP
    return out


TWEAKS = {'filament_colour': ['#FFFFFF', '#FFFFFF'], 'wall_loops': '4', 'sparse_infill_density': '40%',
          'filament_map': ['1', '2'], 'filament_map_mode': 'Manual', 'curr_bed_type': 'Textured PEI Plate',
          # off for the project; switched on per part below
          'brim_type': 'no_brim', 'enable_support': '0',
          'support_type': 'tree(auto)', 'support_on_build_plate_only': '0', 'support_threshold_angle': '30'}


def object_settings(name):
    """Per-part settings, written into the part's <object> in model_settings.config."""
    out = {}
    if name in SUPPORT:
        out['enable_support'] = '1'
    if name in BRIM:
        out.update({'brim_type': 'outer_only', 'brim_width': str(BRIM[name]), 'brim_object_gap': '0.1'})
    return out


def build(out, PLATES):
    tmp = tempfile.mkdtemp()
    preset = []
    for n, (kind, name) in enumerate(PRESETS):
        d = flatten(kind, name)
        d.pop('inherits', None)
        d.update({'from': 'system', 'instantiation': 'true', 'name': name})
        p = os.path.join(tmp, '%s%d.json' % (kind, n))
        json.dump(d, open(p, 'w'), indent=1)
        preset.append(p)
    # One object per part per plate. Each copy is loaded from its own file "<plate>__<part>.stl" so it can be found again.
    cols, sx, sy = stride(len(PLATES))
    place, stls = {}, []
    for k, (_, prow) in enumerate(PLATES):
        ox, oy = (k % cols) * sx, -(k // cols) * sy
        for n, (x, y) in pack(prow).items():
            key = '%02d__%s' % (k + 1, n)
            place[key] = (k + 1, n, x + ox, y + oy)
            f = os.path.join(tmp, key + '.stl')
            shutil.copy(path(n), f)
            stls.append(f)
    raw = os.path.join(tmp, 'raw.3mf')
    subprocess.run([CLI, '--debug', '1', '--load-settings', preset[0] + ';' + preset[1],
                    '--load-filaments', preset[2] + ';' + preset[3], '--arrange', '1', '--orient', '0',
                    '--export-3mf', raw] + stls, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    src = zipfile.ZipFile(raw)
    cfg = src.read('Metadata/model_settings.config').decode()
    key_of = dict(re.findall(r'<object id="(\d+)">\s*<metadata key="name" value="([^"]+)\.stl"', cfg))
    assert sorted(key_of.values()) == sorted(place), 'Bambu Studio did not load every part'

    model = src.read('3D/3dmodel.model').decode()

    # Studio keeps a mesh's own origin as a component offset; the box halves are not centered on theirs. Take the
    # offset off so the part's middle lands where pack() put it.
    offset = {o: tuple(map(float, t.split()[9:11])) for o, t in
              re.findall(r'<object id="(\d+)"[^>]*>\s*<components>\s*<component [^>]*?transform="([^"]+)"', model)}

    def move(m):
        _, _, x, y = place[key_of[m.group(2)]]
        z = m.group(3).split()[11]
        dx, dy = offset.get(m.group(2), (0, 0))
        return '%stransform="1 0 0 0 1 0 0 0 1 %.2f %.2f %s"' % (m.group(1), x - dx, y - dy, z)
    model = re.sub(r'(<item objectid="(\d+)"[^>]*?)transform="([^"]+)"', move, model)

    def obj(m):
        """Name the object after its part, pick its filament, add its own settings."""
        plate, n = place[m.group(2)][:2]
        extra = ''.join('\n    <metadata key="%s" value="%s"/>' % kv for kv in object_settings(n).items())
        return '%s%s"/>\n    <metadata key="extruder" value="%s"/>%s' % (
            m.group(1), n, '2' if material(n) == 'PETG' else '1', extra)
    cfg = re.sub(r'(<object id="\d+">\s*<metadata key="name" value=")([^"]+)\.stl"/>\s*<metadata key="extruder" value="\d+"/>',
                 obj, cfg)
    cfg = re.sub(r'(<part id="\d+" subtype="normal_part"[^>]*>\s*<metadata key="name" value=")\d+__([^"]+)\.stl"',
                 r'\1\2"', cfg)
    # Throw away the plates Studio made (its arrange spreads the parts over as many as it needs) and write ours.
    first = re.search(r'  <plate>.*?  </plate>\n', cfg, re.S)
    head = first.group(0)[:first.group(0).index('    <model_instance>')]
    inst = {key_of[re.search(r'object_id" value="(\d+)"', i).group(1)]: i
            for i in re.findall(r'    <model_instance>.*?    </model_instance>\n', cfg, re.S)}
    assert len(inst) == len(place), 'every object needs its instance'
    plates = ''
    for k, (title, _) in enumerate(PLATES):
        h = re.sub(r'plater_id" value="\d+"', 'plater_id" value="%d"' % (k + 1), head)
        h = re.sub(r'plater_name" value="[^"]*"', 'plater_name" value="%s"' % title, h)
        h = re.sub(r'_1\.png', '_%d.png' % (k + 1), h)
        plates += h + ''.join(i for key, i in sorted(inst.items()) if place[key][0] == k + 1) + '  </plate>\n'
    cfg = re.sub(r'  <plate>.*  </plate>\n', lambda _: plates, cfg, flags=re.S)
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
                dst.writestr(info, json.dumps({'plate_%d' % (k + 1): {'nozzle_sequence': [], 'optimal_assignment': [],
                                                                       'sequence': []} for k in range(len(PLATES))}))
            elif not info.filename.endswith('.png'):
                dst.writestr(info, src.read(info.filename))
    shutil.rmtree(tmp)
    print('wrote', os.path.relpath(out, REPO), '-', len(PLATES), 'plates,', len(place), 'objects')


if __name__ == '__main__':
    for name, plates in PROJECTS.items():
        build(os.path.join(STL, name), plates)
