"""Dev board, rotated variant: the ESP32-C6 turned 90 degrees so its two pin rows run ACROSS the board (rows 3 and 9,
columns a-j). Every ESP pin then has its own straight lane of holes leading away from it, so most connections are
bridges instead of wires. Same perfboard (a-j x 1-24), same parts, same charger wiring as ControllerV4's layout.

Pin plan changes with the rotation (all ADC pins stay on GPIO0-6):
  ANG 1/2/3 -> GPIO 0/2/4, EN 1/2/3 -> GPIO 1/5/7, battery -> GPIO3, input power -> GPIO6,
  IN1/IN2: port 1 -> 18/19, port 2 -> 20/14, port 3 -> TX16/RX17 (unchanged).

  python3 tools/devboard_check.py --rot      python3 tools/devboard_guide.py --rot --png
"""
import importlib.util
import math
import os

_spec = importlib.util.spec_from_file_location('cv4', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ControllerV4.py'))
CV4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CV4)
C, Part, H, HN, X, Y, COLS, NI, NM, check = CV4.C, CV4.Part, CV4.H, CV4.HN, CV4.X, CV4.Y, CV4.COLS, CV4.NI, CV4.NM, CV4.check
NAME = 'rotated'


def layout():
    """Chip side up, USB-C over the column-a edge. 5V / GND / 3V3 ... 8 across row 3 (a-j), TX / RX / 0-7 across
    row 9 (a-j). Rows 4-8 are under the ESP (nothing on top there)."""
    t = C['pb_top']
    parts = []
    side_b = ['5V', 'GND', '3V3', '20', '19', '18', '15', '14', '9', '8']
    side_a = ['TX16', 'RX17', '0', '1', '2', '3', '4', '5', '6', '7']
    esp_pins = [(2, m, lab) for m, lab in enumerate(side_b)] + [(8, m, lab) for m, lab in enumerate(side_a)]
    xc, yc = (X(2) + X(8)) / 2, (Y(0) + Y(9)) / 2
    z0 = C['mod_z']
    parts.append(Part('ESP32-C6', esp_pins, [
        ('ESP32-C6 PCB', xc - 9, xc + 9, yc - 13, yc + 13, z0, z0 + 1.0),
        ('ESP32-C6 USB-C', xc - 4.47, xc + 4.47, yc - 13 - 0.8, yc - 13 - 0.8 + 7.35, z0 + 1.0, z0 + 4.26),
        ('ESP32-C6 headers', X(2) - 1.27, X(2) + 1.27, Y(0) - 1.27, Y(9) + 1.27, t, z0),
        ('ESP32-C6 headers 2', X(8) - 1.27, X(8) + 1.27, Y(0) - 1.27, Y(9) + 1.27, t, z0)]))
    parts.append(Part('MCP73871', [], [], note='off the board (30.5 x 31.5 mm + 16 x 26 mm capacitor); wired in, see the charger table'))

    def upright(name, h_body, h_lead, d=2.3, h=8.0, labels=('', '')):
        i0, m0 = H(h_body)
        i1, m1 = H(h_lead)
        return Part(name, [(i0, m0, labels[0]), (i1, m1, labels[1])],
                    cyls=[(name, (X(i0), Y(m0), t + 0.5), (X(i0), Y(m0), t + 0.5 + h), d / 2)])

    def disc(name, ha, hb, labels=('', '')):
        (i0, m0), (i1, m1) = H(ha), H(hb)
        assert (i0 == i1 or m0 == m1) and abs(i0 - i1) + abs(m0 - m1) == 2, name + ': ceramic caps span 3 holes'
        xm, ym = (X(i0) + X(i1)) / 2, (Y(m0) + Y(m1)) / 2
        if i0 == i1:
            box = (name, xm - 1.0, xm + 1.0, ym - 2.4, ym + 2.4, t, t + 5.0)
        else:
            box = (name, xm - 2.4, xm + 2.4, ym - 1.0, ym + 1.0, t, t + 5.0)
        return Part(name, [(i0, m0, labels[0]), (i1, m1, labels[1])], [box])

    # ESP power, row 1 (the 10 u lies along row 1, clear of the ESP's edge)
    parts += [disc('C 10u', 'a1', 'c1', ('5V', 'G')),
              upright('D3 1N5819', 'i13', 'i12', 2.7, 8.0, ('A', 'K'))]          # body on the VBAT side, next to the rail
    # angle filters: cap straight below its ESP pin, 1 k in the neighbouring lane, angle lead below the 1 k
    parts += [disc('C ADC1 100n', 'c10', 'c12'), upright('R ADC1 1k', 'b11', 'b12'),
              disc('C ADC2 100n', 'e10', 'e12'), upright('R ADC2 1k', 'd11', 'd12'),
              disc('C ADC3 100n', 'g10', 'g12'), upright('R ADC3 1k', 'h11', 'h12')]
    # battery divider: 100 n right at GPIO3, the two 1 M next to the VBAT rail
    parts += [disc('C div 100n', 'f11', 'f13'), upright('R div top 1M', 'i17', 'i16'), upright('R div bot 1M', 'h16', 'h15')]
    # input-power sense (same place as the straight layout)
    parts += [upright('R pwr top 1M', 'g22', 'g21'), upright('R pwr bot 1M', 'g20', 'g19')]
    # power row: diodes and zener (rows 22-23), connectors (row 24)
    parts += [upright('D1 1N5819 USB', 'e23', 'e22', 2.7, 8.0, ('A', 'K')),
              upright('D2 1N5819 solar', 'h23', 'g23', 2.7, 8.0, ('A', 'K')),
              upright('Z 6.2V', 'd22', 'd23', 2.7, 8.0, ('K', 'A'))]
    parts.append(Part('Battery pins', [H('a24') + ('B-',), H('b24') + ('B+',)],
                      [('Battery pins', X(23) - 1.27, X(23) + 1.27, Y(0) - 1.27, Y(1) + 1.27, t, t + 2.5),
                       ('XH plug', X(23) - 2.45, X(23) + 2.45, Y(0) - 2.45, Y(1) + 2.45, t + 2.5, t + 8.5)]))
    parts.append(Part('USB leads', [H('d24') + ('V-',), H('e24') + ('V+',)]))
    parts.append(Part('Solar leads', [H('h24') + ('S+',), H('i24') + ('S-',)]))
    parts.append(Part('Port leads', [H(n) + (lab,) for n, lab in (
        ('a10', 'P3 IN1'), ('b10', 'P3 IN2'), ('f2', 'P1 IN1'), ('e2', 'P1 IN2'), ('d2', 'P2 IN1'), ('h2', 'P2 IN2'),
        ('d10', 'P1 EN'), ('h10', 'P2 EN'), ('j10', 'P3 EN'), ('b13', 'P1 ANG'), ('d13', 'P2 ANG'), ('h13', 'P3 ANG'),
        ('j15', 'P1 VBAT'), ('j16', 'P2 VBAT'), ('j18', 'P3 VBAT'), ('a15', 'P1 GND'), ('a16', 'P2 GND'), ('a17', 'P3 GND'))]))
    return parts


WIRES = [
    # rails: GND across row 14 and down column a, battery + down column j
    ('a14', 'i14', 'GND rail: bare wire across row 14, a-i'),
    ('a14', 'a24', 'GND rail: bare wire down column a, rows 14-24'),
    ('j11', 'j24', 'VBAT rail: bare wire down column j, rows 11-24'),
    # side B (row 3) to row 2 / row 1
    ('a3', 'a2', 'bridge: ESP 5V'), ('a2', 'a1', 'bridge: ESP 5V -> C 10u'),
    ('b3', 'b2', 'bridge: ESP GND'), ('b2', 'b1', 'bridge: ESP GND'), ('b1', 'c1', 'bridge: ESP GND -> C 10u'),
    ('d3', 'd2', 'bridge: port 2 IN1 -> GPIO20'), ('e3', 'e2', 'bridge: port 1 IN2 -> GPIO19'),
    ('f3', 'f2', 'bridge: port 1 IN1 -> GPIO18'), ('h3', 'h2', 'bridge: port 2 IN2 -> GPIO14'),
    ('b2', 'a14', 'wire: ESP GND -> GND rail'),
    # side A (row 9) to row 10 and down each lane
    ('a9', 'a10', 'bridge: port 3 IN1 -> GPIO16'), ('b9', 'b10', 'bridge: port 3 IN2 -> GPIO17'),
    ('d9', 'd10', 'bridge: port 1 EN -> GPIO1'), ('h9', 'h10', 'bridge: port 2 EN -> GPIO5'), ('j9', 'j10', 'bridge: port 3 EN -> GPIO7'),
    ('c9', 'c10', 'bridge: filter 1 -> GPIO0'), ('c10', 'c11', 'bridge: filter 1 node'), ('c11', 'b11', 'bridge: filter 1 node -> R ADC1'),
    ('b12', 'b13', 'bridge: port 1 ANGLE -> R ADC1'), ('c12', 'c13', 'bridge: C ADC1 GND'), ('c13', 'c14', 'bridge: C ADC1 GND -> GND rail'),
    ('e9', 'e10', 'bridge: filter 2 -> GPIO2'), ('e10', 'e11', 'bridge: filter 2 node'), ('e11', 'd11', 'bridge: filter 2 node -> R ADC2'),
    ('d12', 'd13', 'bridge: port 2 ANGLE -> R ADC2'), ('e12', 'e13', 'bridge: C ADC2 GND'), ('e13', 'e14', 'bridge: C ADC2 GND -> GND rail'),
    ('g9', 'g10', 'bridge: filter 3 -> GPIO4'), ('g10', 'g11', 'bridge: filter 3 node'), ('g11', 'h11', 'bridge: filter 3 node -> R ADC3'),
    ('h12', 'h13', 'bridge: port 3 ANGLE -> R ADC3'), ('g12', 'g13', 'bridge: C ADC3 GND'), ('g13', 'g14', 'bridge: C ADC3 GND -> GND rail'),
    ('f9', 'f10', 'bridge: battery divider -> GPIO3'), ('f10', 'f11', 'bridge: battery divider -> C div'),
    ('f13', 'f14', 'bridge: C div GND -> GND rail'),
    ('i9', 'i10', 'bridge: input-power sense -> GPIO6'),
    # D3: VBAT rail -> 5V
    ('j13', 'i13', 'bridge: VBAT rail -> D3 anode (battery +)'), ('i12', 'i11', 'bridge: D3 cathode (5V)'),
    ('i11', 'a2', 'wire: D3 cathode -> ESP 5V'),
    # battery divider
    ('j17', 'i17', 'bridge: VBAT rail -> R div top (battery +)'), ('i16', 'h16', 'bridge: divider node'),
    ('i16', 'i15', 'bridge: divider node'), ('i15', 'f10', 'wire: divider node -> GPIO3'),
    ('h15', 'h14', 'bridge: R div bot -> GND rail'),
    # input-power sense
    ('g22', 'g23', 'bridge: PWR node -> R pwr top'), ('g21', 'g20', 'bridge: input-power sense node'),
    ('g21', 'f21', 'bridge: input-power sense node'), ('f21', 'i10', 'wire: input-power sense -> GPIO6'),
    ('g19', 'f19', 'bridge: R pwr bot GND'), ('f19', 'a19', 'wire: R pwr bot -> GND rail'),
    # power row (as in the straight layout)
    ('e24', 'e23', 'bridge: USB V+ -> D1 anode'), ('h24', 'h23', 'bridge: solar + -> D2 anode'),
    ('d22', 'e22', 'bridge: PWR node (zener cathode, D1 cathode)'), ('e22', 'f22', 'bridge: PWR node'),
    ('f22', 'g22', 'bridge: PWR node -> R pwr top'), ('g23', 'g24', 'bridge: PWR node -> charger PWR + hole'),
    ('d24', 'd23', 'bridge: USB V- -> zener anode (GND)'), ('d23', 'c23', 'bridge: GND link'), ('c23', 'b23', 'bridge: GND link'),
    ('b23', 'a23', 'bridge: GND link -> GND rail'),
    ('b24', 'c24', 'bridge: battery + -> charger BATT + hole'),
    ('i24', 'i23', 'bridge: solar - (GND)'), ('i23', 'a18', 'wire: solar - -> GND rail'),
]

CHARGER = CV4.CHARGER

EXPECT = {
    'GND': ['b3', 'b2', 'c1', 'a14', 'i14', 'a24', 'c12', 'e12', 'g12', 'f13', 'h15', 'g19', 'd23', 'd24', 'i24',
            'a15', 'a16', 'a17', 'a18', 'a19', 'a20', 'a21', 'a22', 'a23'],
    'VBAT': ['j11', 'j24', 'i13', 'i17', 'j15', 'j16', 'j18', 'j20'],
    '5V': ['a3', 'a1', 'i12', 'i11'],
    'VDIV': ['f9', 'f11', 'i16', 'h16', 'i15'],
    'PSENSE': ['i9', 'i10', 'g21', 'g20'],
    'ADC0': ['c9', 'c10', 'b11'], 'ADC2': ['e9', 'e10', 'd11'], 'ADC4': ['g9', 'g10', 'h11'],
    'ANG1': ['b12', 'b13'], 'ANG2': ['d12', 'd13'], 'ANG3': ['h12', 'h13'],
    'EN1': ['d9', 'd10'], 'EN2': ['h9', 'h10'], 'EN3': ['j9', 'j10'],
    'P3IN1': ['a9', 'a10'], 'P3IN2': ['b9', 'b10'], 'P1IN1': ['f3', 'f2'], 'P1IN2': ['e3', 'e2'],
    'P2IN1': ['d3', 'd2'], 'P2IN2': ['h3', 'h2'],
    'PWR': ['d22', 'e22', 'g23', 'g22', 'g24'], 'USB+': ['e23', 'e24'], 'SOL+': ['h23', 'h24'], 'BATT+': ['b24', 'c24'],
}
