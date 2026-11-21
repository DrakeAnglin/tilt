"""Build the v0.8 Bambu Studio project: the new housing parts, on one plate, two materials.

  python3 tools/orient_v08.py && python3 tools/bambu_v08.py   # writes hardware/mechanical/stl/v0.8/tilter_v08i_H2D_PLA_PETG.3mf

Filament 1 = PLA, filament 2 = PETG. Every pair of parts that rubs or meshes is PLA against PETG (see PETG below).
Same presets and method as tools/bambu_v05.py (H2D 0.4 nozzle, 0.12 mm Fine, 4 walls, 40 % infill).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRINT = os.path.join(REPO, 'hardware/mechanical/stl/v0.8/print')
OUT = os.path.join(REPO, 'hardware/mechanical/stl/v0.8/tilter_v08i_H2D_PLA_PETG.3mf')
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
# Rev I: only the parts that must be reprinted, on TWO plates in one project.
#   plate 1 = PLA : the whole housing (one material outside)
#   plate 2 = PETG: the two sensor gears (they turn in the PLA housing)
PETG = {'rod_gear', 'magnet_gear'}
PLATE_STEP = 420.0                 # Bambu Studio lays plates out 1.2 bed widths apart (H2D bed: 350 mm)
# part -> center on its own plate (mm), packed close together (about 8 mm gaps) round the middle of the bed.
LAYOUT = {'case_right': (100, 132), 'case_left': (152, 132), 'bearing_shell': (202, 132), 'motor_shell': (252, 132),
          'tray': (150, 196), 'tray_lid': (196, 196),
          'rod_gear': (166, 160), 'magnet_gear': (188, 160)}

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
    main()                                                 # one project, two plates
    main('PLA', OUT.replace('PLA_PETG', 'PLA_only'))       # the same parts as two plain one-plate projects
    main('PETG', OUT.replace('PLA_PETG', 'PETG_only'))
