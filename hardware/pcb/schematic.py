"""Write the controller's KiCad schematic from netlist.py (the same source as the board), so the two always agree.

Every part is a standard KiCad symbol; every pin gets a net label (or a no-connect flag), grouped by function on an A3
sheet. Checked by KiCad's ERC and by the board DRC's schematic-parity check:

  python3 hardware/pcb/schematic.py
  kicad-cli sch erc hardware/pcb/controller/controller.kicad_sch
  kicad-cli pcb drc --schematic-parity hardware/pcb/controller/controller.kicad_pcb
"""
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist as N  # noqa: E402

SYMLIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
OUT = os.path.join(HERE, 'controller', 'controller.kicad_sch')
PROJECT = 'controller'

SYM = {  # footprint key -> (library, symbol)
    'R': ('Device', 'R'), 'C': ('Device', 'C'), 'CP8': ('Device', 'C_Polarized'), 'D': ('Device', 'D_Schottky'),
    'D5W': ('Device', 'D_Zener'), 'PTC': ('Device', 'Polyfuse'), 'SOCK10': ('Connector_Generic', 'Conn_01x10'),
    'SOCK6': ('Connector_Generic', 'Conn_01x06'), 'XH2': ('Connector_Generic', 'Conn_01x02'),
    'XH6': ('Connector_Generic', 'Conn_01x06'), 'ZH2': ('Connector_Generic', 'Conn_01x02'),
    'RJ12': ('Connector_Generic', 'Conn_01x06'), 'TP': ('Connector', 'TestPoint'), 'HOLE': ('Mechanical', 'MountingHole'),
}
ZENER = {'D4'}                         # D4 is the zener; the other D parts are Schottkys


def snap(v, g=2.54):
    return round(v / g) * g


def uid():
    return str(uuid.uuid4())


def block(text, start):
    """The balanced (...) expression starting at text[start]."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == '(':
            depth += 1
        elif text[k] == ')':
            depth -= 1
            if depth == 0:
                return text[start:k + 1]
    raise ValueError('unbalanced')


def lib_symbol(lib, name):
    text = open(SYMLIB + lib + '.kicad_sym').read()
    m = re.search(r'\(symbol "%s"' % re.escape(name), text)
    sym = block(text, m.start())
    ext = re.search(r'\(extends "([^"]+)"\)', sym)
    if ext:                            # derived symbol: use the parent's body with this name
        base = lib_symbol(lib, ext.group(1))
        base = base.replace('(symbol "%s:%s"' % (lib, ext.group(1)), '(symbol "%s:%s"' % (lib, name), 1)
        return base.replace('"%s_' % ext.group(1), '"%s_' % name)
    return sym.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1)


def pins(sym):
    """(number, x, y, angle) of every pin's connection point, in symbol coordinates (y up)."""
    out = []
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', sym):
        b = block(sym, m.start())
        num = re.search(r'\(number "([^"]*)"', b).group(1)
        out.append((num, float(m.group(1)), float(m.group(2)), float(m.group(3))))
    return out


# where each group of parts goes on the sheet (mm, y down) and how they're spaced
GROUPS = [
    ('ESP32-C6 SuperMini (sockets)', ['J1', 'J2'], (40, 40), (40, 0)),
    ('Power: charger, battery, USB-C, solar', ['J5', 'J4', 'J3', 'J8'], (140, 40), (35, 0)),
    ('Power path and dividers', ['D1', 'D2', 'D4', 'R3', 'R4', 'C6', 'D3', 'C1', 'R1', 'R2', 'C2', 'C9'], (40, 115), (20, 0)),
    ('Port 1', ['J9', 'F1', 'R8', 'R9', 'R10', 'R11', 'R5', 'C3'], (40, 175), (18, 0)),
    ('Port 2', ['J10', 'F2', 'R12', 'R13', 'R14', 'R15', 'R6', 'C4'], (40, 215), (18, 0)),
    ('Port 3', ['J11', 'F3', 'R16', 'R17', 'R18', 'R19', 'R7', 'C5'], (40, 255), (18, 0)),
    ('Test pads, mounting holes', ['TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'H1', 'H2', 'H3'], (300, 40), (14, 0)),
]


def main():
    root = uid()
    parts = {ref: (value, key, pads, note) for ref, value, key, pads, note in N.PARTS}
    libs, out, labels = {}, [], []
    for title, refs, (x0, y0), (dx, dy) in GROUPS:
        labels.append('(text "%s" (exclude_from_sim no) (at %.2f %.2f 0) (effects (font (size 2 2) bold) (justify left)) (uuid "%s"))'
                      % (title, x0 - 10, y0 - 18, uid()))
        for k, ref in enumerate(refs):
            value, key, pads, note = parts[ref]
            lib, name = SYM[key]
            if ref in ZENER:
                lib, name = 'Device', 'D_Zener'
            lid = '%s:%s' % (lib, name)
            if lid not in libs:
                libs[lid] = lib_symbol(lib, name)
            x, y = snap(x0 + k * dx), snap(y0 + k * dy)        # on KiCad's 1.27 mm connection grid
            pin_uuid = ''.join('(pin "%s" (uuid "%s"))' % (num, uid()) for num, *_ in pins(libs[lid]))
            fp = N.FP[key]
            in_bom = 'no' if ref[0] in 'HT' else 'yes'          # mounting holes and test pads aren't bought parts
            out.append('''(symbol (lib_id "%s") (at %.2f %.2f 0) (unit 1) (exclude_from_sim no) (in_bom %s) (on_board yes) (dnp no) (uuid "%s")
  (property "Reference" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27))))
  (property "Value" "%s" (at %.2f %.2f 0) (effects (font (size 1.0 1.0))))
  (property "Footprint" "%s" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) (hide yes)))
  (property "Datasheet" "" (at %.2f %.2f 0) (effects (font (size 1.27 1.27)) (hide yes)))
  %s
  (instances (project "%s" (path "/%s" (reference "%s") (unit 1)))))''' % (
                lid, x, y, in_bom, uid(), ref, x + 2, y - 6, value.replace('"', "'"), x + 2, y + 7, fp, x, y, x, y,
                pin_uuid, PROJECT, root, ref))
            for num, px, py, ang in pins(libs[lid]):
                wx, wy = x + px, y - py                    # symbol y is up, sheet y is down
                net = pads.get(int(num)) if num.isdigit() else None
                if net:
                    la = (ang + 180) % 360               # the label points away from the part
                    labels.append('(global_label "%s" (shape passive) (at %.2f %.2f %d) (fields_autoplaced yes) '
                                  '(effects (font (size 1.0 1.0)) (justify %s)) (uuid "%s"))'
                                  % (net, wx, wy, la, 'right' if la in (180, 270) else 'left', uid()))
                else:
                    labels.append('(no_connect (at %.2f %.2f) (uuid "%s"))' % (wx, wy, uid()))
    sch = '''(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0") (uuid "%s") (paper "A3")
  (title_block (title "Automated blinds controller v2 (carrier board)") (company "github: automated-blinds") (comment 1 "Generated from hardware/pcb/netlist.py"))
  (lib_symbols
%s
  )
%s
%s
  (sheet_instances (path "/" (page "1")))
)
''' % (root, '\n'.join(libs.values()), '\n'.join(out), '\n'.join(labels))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w').write(sch)
    # project library tables pointing at KiCad's own libraries (so ERC / DRC find them without a global setup)
    d = os.path.dirname(OUT)
    sym_libs = sorted({lib for lib, _ in SYM.values()})
    open(os.path.join(d, 'sym-lib-table'), 'w').write('(sym_lib_table\n  (version 7)\n%s)\n' % ''.join(
        '  (lib (name "%s")(type "KiCad")(uri "%s%s.kicad_sym")(options "")(descr ""))\n' % (l, SYMLIB, l) for l in sym_libs))
    fp_libs = sorted({N.FP[k].split(':')[0] for k in N.FP})
    fplib = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
    open(os.path.join(d, 'fp-lib-table'), 'w').write('(fp_lib_table\n  (version 7)\n%s)\n' % ''.join(
        '  (lib (name "%s")(type "KiCad")(uri "%s%s.pretty")(options "")(descr ""))\n' % (l, fplib, l) for l in fp_libs))
    pro = os.path.join(os.path.dirname(OUT), PROJECT + '.kicad_pro')
    if not os.path.exists(pro):
        open(pro, 'w').write('{"meta": {"filename": "%s.kicad_pro", "version": 1}}\n' % PROJECT)
    print('wrote', OUT, '(%d symbols)' % len(out))


if __name__ == '__main__':
    main()
