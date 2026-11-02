"""One net (or a few) of the dev board on its own: the underside copper of just those nets, plus every part pin and
lead on them, labelled. Default: the two battery-voltage nets.

  python3 tools/devboard_net.py            # writes docs/renders/devboard-hot.svg / .png
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WHICH = sys.argv[1] if len(sys.argv) > 1 else 'hot'
sys.argv = [sys.argv[0]]                         # the imported modules read their own flags
sys.path.insert(0, HERE)
import devboard_guide as G                      # noqa: E402  (drawing helpers, layout, wires)
import devboard_check as C                      # noqa: E402  (net union-find)

M, HN, H = G.M, G.HN, G.H
VIEWS = {
    'hot': ('battery + connections only', [
        ('VBAT', '#d62728', 'battery + rail (charger LOAD+ output: feeds the ports, D3 -> ESP, battery divider)'),
        ('BATT+', '#ff7f0e', 'cell + (battery pin -> charger BATT+ input only)')]),
    'angle1': ('port 1 angle line only', [
        ('ANG1', '#888888', 'RJ12 pin 4 lead -> 1 kOhm resistor (lead side)'),
        ('ADC0', '#1f77b4', '1 kOhm resistor (ESP side) -> ESP GPIO0, + the 100 nF filter cap')]),
}
TITLE, NETS = VIEWS[WHICH]
find = C.netlist()
expect = M.EXPECT
root = {name: find(expect[name][0]) for name, _, _ in NETS}


def net_of(h):
    r = find(h)
    for name, _, _ in NETS:
        if r == root[name]:
            return name
    return None


def run():
    o = G.board('Dev board: %s (underside)' % TITLE,
                'Bottom view (column a at the top). Only these nets are drawn; everything else is left out.', True)
    col = {n: c for n, c, _ in NETS}
    # copper: rails, bridges, wires on these nets
    for f, t, note in M.WIRES:
        n = net_of(f)
        if not n:
            continue
        (x0, y0), (x1, y1) = G.pos(f, True), G.pos(t, True)
        if note.startswith('wire'):
            o.append('<path d="M%.0f %.0f Q%.0f %.0f %.0f %.0f" fill="none" stroke="%s" stroke-width="3" stroke-dasharray="7,3"/>' % (
                x0, y0, (x0 + x1) / 2, (y0 + y1) / 2 - 14, x1, y1, col[n]))
        else:
            o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="%d" stroke-linecap="round"/>' % (
                x0, y0, x1, y1, col[n], 7 if 'rail' in note.split(':')[0] else 5))
    # a part joining two of the drawn nets (e.g. the 1 k between the lead and the ESP): its body, on the top side
    for p in M.layout():
        if len(p.pins) == 2:
            (i0, m0, _), (i1, m1, _) = p.pins
            h0, h1 = HN(i0, m0), HN(i1, m1)
            n0, n1 = net_of(h0), net_of(h1)
            if n0 and n1 and n0 != n1:
                (x0, y0), (x1, y1) = G.pos(h0, True), G.pos(h1, True)
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
                o.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#8a6a2a" stroke-width="2" stroke-dasharray="4,3"/>' % (x0, y0, x1, y1))
                o.append('<rect x="%.0f" y="%.0f" width="%.0f" height="16" rx="7" fill="#e8c88a" stroke="#8a6a2a" opacity="0.9"/>' % (
                    xm - abs(x1 - x0) * 0.32, ym - 8, abs(x1 - x0) * 0.64))
                o.append('<text x="%.0f" y="%.0f" font-size="10" font-weight="bold" text-anchor="middle">%s (on top)</text>' % (
                    xm, ym + 4, p.name.split()[-1]))
    # what plugs / solders onto these nets: numbered dots, key underneath
    seen, key = set(), []
    pins = []
    for p in M.layout():
        for i, m, lab in p.pins:
            h = HN(i, m)
            n = net_of(h)
            if n and h not in seen:
                seen.add(h)
                name = {'Port leads': 'RJ12 lead %s' % lab.replace(' VBAT', ' battery +'), 'JST battery': 'battery JST %s' % lab,
                        'JST charger +': 'charger JST %s' % lab, 'JST charger LOAD': 'charger JST %s' % lab
                        }.get(p.name, '%s %s' % (p.name, lab))
                pins.append((H(h), h, n, name.strip()))
    pins.sort()
    for k, (_, h, n, name) in enumerate(pins):
        x, y = G.pos(h, True)
        o.append('<circle cx="%.0f" cy="%.0f" r="9" fill="%s"/>' % (x, y, col[n]))
        o.append('<text x="%.0f" y="%.0f" font-size="10" font-weight="bold" fill="#fff" text-anchor="middle">%d</text>' % (x, y + 4, k + 1))
        key.append((k + 1, h, n, name))
    y = G.MY + G.S * (M.NM - 1) + G.S * 1.6
    for k, (n, c, t) in enumerate(NETS):
        o.append('<rect x="%d" y="%.0f" width="22" height="6" fill="%s"/><text x="%d" y="%.0f" font-size="13">%s: %s</text>' % (
            G.MX - 40, y + 22 * k - 6, c, G.MX - 10, y + 22 * k, n, t))
    y += 52
    for k, (num, h, n, name) in enumerate(key):
        cx = G.MX - 40 + (k % 3) * 420
        cy = y + (k // 3) * 22
        o.append('<circle cx="%d" cy="%.0f" r="9" fill="%s"/><text x="%d" y="%.0f" font-size="10" font-weight="bold" fill="#fff" '
                 'text-anchor="middle">%d</text><text x="%d" y="%.0f" font-size="13"><tspan font-weight="bold">%s</tspan>  %s</text>' % (
                     cx + 9, cy - 4, col[n], cx + 9, cy, num, cx + 26, cy, h, name))
    y += ((len(key) + 2) // 3) * 22 + 14
    bridges = [(f, t) for f, t, note in M.WIRES if net_of(f) and not note.startswith(('GND rail', 'VBAT rail'))]
    rails = [(f, t) for f, t, note in M.WIRES if net_of(f) and note.startswith(('GND rail', 'VBAT rail'))]
    o.append('<text x="%d" y="%.0f" font-size="13"><tspan font-weight="bold">Underneath:</tspan> rail %s; bridges %s</text>' % (
        G.MX - 40, y, ', '.join('%s-%s' % r for r in rails), ', '.join('%s-%s' % b for b in bridges)))
    o.append('<text x="%d" y="%.0f" font-size="12" fill="#444">Solid = bare rail / bridge; numbered dots = part pins and leads soldered '
             'in from the top. Every dot of one colour must beep to every other dot of that colour, and never to the other colour.</text>'
             % (G.MX - 40, y + 22))
    hgt = int(y + 50)
    o[0] = o[0].replace('height="%d"' % G.HGT, 'height="%d"' % hgt)
    o.append('</svg>')
    out = os.path.join(G.OUT, 'devboard-%s.svg' % WHICH)
    open(out, 'w').write('\n'.join(o))
    head = open(out).read(300)
    w, h = head.split('width="')[1].split('"')[0], head.split('height="')[1].split('"')[0]
    subprocess.run([G.CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                    '--window-size=%s,%s' % (w, h), '--screenshot=' + os.path.abspath(out[:-4] + '.png'), 'file://' + os.path.abspath(out)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('wrote', out)


run()
