"""Dev board, rotated layout (the one to build): the ESP32-C6 turned 90 degrees so its two pin rows run ACROSS the board (rows 3 and 9,
columns a-j). Every ESP pin then has its own straight lane of holes leading away from it, so most connections are
bridges instead of wires. Same perfboard (a-j x 1-24), same parts, resistors and diodes lying flat across 4 holes; the ESP and the USB-C breakout plug into
female header sockets (replaceable, reusable).
The USB-C faces the numbered edge (column a): on the real 30 x 70 mm board nothing overhangs.

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
SOCKET = 8.5                 # female header socket ('pin stand') height from the kit: the ESP and USB-C boards plug in


def layout():
    """Chip side up, USB-C over the column-a edge. 5V / GND / 3V3 ... 8 across row 3 (a-j), TX / RX / 0-7 across
    row 9 (a-j). Rows 4-8 are under the ESP (nothing on top there)."""
    t = C['pb_top']
    parts = []
    side_b = ['5V', 'GND', '3V3', '20', '19', '18', '15', '14', '9', '8']
    side_a = ['TX16', 'RX17', '0', '1', '2', '3', '4', '5', '6', '7']
    esp_pins = [(2, m, lab) for m, lab in enumerate(side_b)] + [(8, m, lab) for m, lab in enumerate(side_a)]
    xc, yc = (X(2) + X(8)) / 2, (Y(0) + Y(9)) / 2
    z0 = t + SOCKET                                       # plugged into female header sockets: replaceable / reusable
    parts.append(Part('ESP32-C6', esp_pins, [
        ('ESP32-C6 PCB', xc - 9, xc + 9, yc - 13, yc + 13, z0, z0 + 1.0),
        ('ESP32-C6 USB-C', xc - 4.47, xc + 4.47, yc - 13 - 0.8, yc - 13 - 0.8 + 7.35, z0 + 1.0, z0 + 4.26),
        ('ESP32-C6 sockets', X(2) - 1.27, X(2) + 1.27, Y(0) - 1.27, Y(9) + 1.27, t, z0),
        ('ESP32-C6 sockets 2', X(8) - 1.27, X(8) + 1.27, Y(0) - 1.27, Y(9) + 1.27, t, z0)]))
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

    def flat(name, h0, h1, kind='R', labels=('', '')):
        """Resistor (6.3 x 2.3 mm body) or 1N5819 / zener (5.2 x 2.7 mm) lying flat across 4 holes (legs 7.62 mm apart)."""
        (i0, m0), (i1, m1) = H(h0), H(h1)
        assert (i0 == i1 or m0 == m1) and abs(i0 - i1) + abs(m0 - m1) == 3, name + ': flat parts span 4 holes'
        ln, d = (6.3, 2.3) if kind == 'R' else (5.2, 2.7)
        xm, ym = (X(i0) + X(i1)) / 2, (Y(m0) + Y(m1)) / 2
        ux, uy = (i1 - i0) / 3.0, (m1 - m0) / 3.0
        p1 = (xm - ux * ln / 2, ym - uy * ln / 2, t + d / 2)
        p2 = (xm + ux * ln / 2, ym + uy * ln / 2, t + d / 2)
        return Part(name, [(i0, m0, labels[0]), (i1, m1, labels[1])], cyls=[(name, p1, p2, d / 2)])

    # ESP power, row 1 (the 10 u stands along row 1, clear of the ESP's edge)
    parts += [disc('C 10u', 'a1', 'c1', ('5V', 'G'))]
    # angle filters: 100 n straight below its ESP pin, the 1 k flat in the neighbouring lane
    parts += [disc('C ADC1 100n', 'c10', 'c12'), flat('R ADC1 1k', 'b11', 'b14'),
              disc('C ADC2 100n', 'e10', 'e12'), flat('R ADC2 1k', 'd11', 'd14'),
              disc('C ADC3 100n', 'g10', 'g12'), flat('R ADC3 1k', 'h11', 'h14')]
    parts += [disc('C div 100n', 'f11', 'f13')]                                  # battery divider's 100 n at GPIO3
    # flat parts, band 1 (rows 15-18, lanes c e g i) and band 2 (rows 20-23, lanes b d f h): never side by side
    parts += [flat('R pwr bot 1M', 'c15', 'c18'), flat('R pwr top 1M', 'e15', 'e18'),
              flat('R div bot 1M', 'g15', 'g18'), flat('D3 1N5819', 'i15', 'i18', 'D', ('A', 'K')),
              flat('D1 1N5819 USB', 'b23', 'b20', 'D', ('A', 'K')), flat('Z 6.2V', 'd20', 'd23', 'D', ('K', 'A')),
              flat('D2 1N5819 solar', 'f23', 'f20', 'D', ('A', 'K')), flat('R div top 1M', 'h23', 'h20')]
    # battery: 2 header pins for the cell's JST-XH plug (the plug's 9.8 x 5.8 mm body sits over a-c, rows 18-20: kept clear)
    parts.append(Part('Battery pins', [H('a19') + ('B-',), H('b19') + ('B+',)],
                      [('Battery pins', X(18) - 1.27, X(18) + 1.27, Y(0) - 1.27, Y(1) + 1.27, t, t + 2.5),
                       ('XH plug', X(18) - 2.9, X(18) + 2.9, (Y(0) + Y(1)) / 2 - 4.9, (Y(0) + Y(1)) / 2 + 4.9, t + 2.5, t + 8.5)]))
    # USB-C breakout (0.50 x 0.85 in) plugged into a 6-way female socket in row 24, socket overhanging the board end
    usb = ['VBUS', 'GND', 'CC1', 'D-', 'D+', 'CC2']
    x_in, yu, zu = X(23) - 1.5, (Y(1) + Y(6)) / 2, t + SOCKET                # pins 1.5 mm in from its back edge
    parts.append(Part('USB-C breakout', [H('%s24' % COLS[1 + k]) + (lab,) for k, lab in enumerate(usb)],
                      [('USB-C socket strip', X(23) - 1.27, X(23) + 1.27, Y(1) - 1.27, Y(6) + 1.27, t, zu),
                       ('USB-C PCB', x_in, x_in + 12.7, yu - 10.8, yu + 10.8, zu, zu + 1.6),
                       ('USB-C socket', x_in + 12.7 - 7.35 + 1.0, x_in + 12.7 + 1.0, yu - 4.47, yu + 4.47, zu + 1.6, zu + 4.9)],
                      note='VBUS, GND, CC1, D-, D+, CC2 from column b; only VBUS and GND are used (the board has its own CC resistors)'))
    parts.append(Part('Solar leads', [H('g23') + ('S+',), H('a17') + ('S-',)]))
    parts.append(Part('Port leads', [H(n) + (lab,) for n, lab in (
        ('a10', 'P3 IN1'), ('b10', 'P3 IN2'), ('f2', 'P1 IN1'), ('e2', 'P1 IN2'), ('d2', 'P2 IN1'), ('h2', 'P2 IN2'),
        ('d10', 'P1 EN'), ('h10', 'P2 EN'), ('j10', 'P3 EN'), ('b15', 'P1 ANG'), ('e14', 'P2 ANG'), ('h15', 'P3 ANG'),
        ('j16', 'P1 VBAT'), ('j17', 'P2 VBAT'), ('j18', 'P3 VBAT'), ('a14', 'P1 GND'), ('a15', 'P2 GND'), ('a16', 'P3 GND'))]))
    return parts


WIRES = [
    # rails: GND across row 13 and down column a, battery + down column j
    ('a13', 'i13', 'GND rail: bare wire across row 13, a-i'),
    ('a13', 'a24', 'GND rail: bare wire down column a, rows 13-24'),
    ('j11', 'j24', 'VBAT rail: bare wire down column j, rows 11-24'),
    # side B (row 3) to rows 2 / 1
    ('a3', 'a2', 'bridge: ESP 5V'), ('a2', 'a1', 'bridge: ESP 5V -> C 10u'),
    ('b3', 'b2', 'bridge: ESP GND'), ('b2', 'b1', 'bridge: ESP GND'), ('b1', 'c1', 'bridge: ESP GND -> C 10u'),
    ('d3', 'd2', 'bridge: port 2 IN1 -> GPIO20'), ('e3', 'e2', 'bridge: port 1 IN2 -> GPIO19'),
    ('f3', 'f2', 'bridge: port 1 IN1 -> GPIO18'), ('h3', 'h2', 'bridge: port 2 IN2 -> GPIO14'),
    ('b2', 'a13', 'wire: ESP GND -> GND rail (under the ESP)'),
    # side A (row 9) to row 10 and down each lane
    ('a9', 'a10', 'bridge: port 3 IN1 -> GPIO16'), ('b9', 'b10', 'bridge: port 3 IN2 -> GPIO17'),
    ('d9', 'd10', 'bridge: port 1 EN -> GPIO1'), ('h9', 'h10', 'bridge: port 2 EN -> GPIO5'), ('j9', 'j10', 'bridge: port 3 EN -> GPIO7'),
    ('c9', 'c10', 'bridge: filter 1 -> GPIO0'), ('c10', 'c11', 'bridge: filter 1 node'), ('c11', 'b11', 'bridge: filter 1 node -> R ADC1'),
    ('b14', 'b15', 'bridge: port 1 ANGLE -> R ADC1'), ('c12', 'c13', 'bridge: C ADC1 GND -> GND rail'),
    ('e9', 'e10', 'bridge: filter 2 -> GPIO2'), ('e10', 'e11', 'bridge: filter 2 node'), ('e11', 'd11', 'bridge: filter 2 node -> R ADC2'),
    ('d14', 'e14', 'bridge: port 2 ANGLE -> R ADC2'), ('e12', 'e13', 'bridge: C ADC2 GND -> GND rail'),
    ('g9', 'g10', 'bridge: filter 3 -> GPIO4'), ('g10', 'g11', 'bridge: filter 3 node'), ('g11', 'h11', 'bridge: filter 3 node -> R ADC3'),
    ('h14', 'h15', 'bridge: port 3 ANGLE -> R ADC3'), ('g12', 'g13', 'bridge: C ADC3 GND -> GND rail'),
    ('f9', 'f10', 'bridge: battery divider -> GPIO3'), ('f10', 'f11', 'bridge: battery divider -> C div'),
    ('i9', 'i10', 'bridge: input-power sense -> GPIO6'),
    # D3: VBAT rail -> 5V
    ('i15', 'j15', 'bridge: VBAT rail -> D3 anode (battery +)'), ('i18', 'i19', 'bridge: D3 cathode (5V)'),
    ('i19', 'a2', 'wire: D3 cathode -> ESP 5V (under the ESP)'),
    # battery divider
    ('h23', 'i23', 'bridge: R div top (battery +)'), ('i23', 'j23', 'bridge: VBAT rail -> R div top'),
    ('g15', 'g14', 'bridge: R div bot GND'), ('g14', 'g13', 'bridge: R div bot -> GND rail'),
    ('g18', 'h18', 'bridge: divider node'), ('h18', 'h19', 'bridge: divider node'), ('h19', 'h20', 'bridge: divider node -> R div top'),
    ('h19', 'f10', 'wire: divider node -> GPIO3'),
    # input-power sense
    ('e18', 'e19', 'bridge: PWR node -> R pwr top'), ('e19', 'e20', 'bridge: PWR node'),
    ('e15', 'd15', 'bridge: input-power sense node'), ('d15', 'c15', 'bridge: input-power sense node -> R pwr bot'),
    ('d15', 'd16', 'bridge: input-power sense node'), ('d16', 'i10', 'wire: input-power sense -> GPIO6'),
    ('c18', 'b18', 'bridge: R pwr bot GND'), ('b18', 'a18', 'bridge: R pwr bot -> GND rail'),
    # power row
    ('b20', 'c20', 'bridge: PWR node (D1 cathode)'), ('c20', 'd20', 'bridge: PWR node (zener cathode)'),
    ('d20', 'e20', 'bridge: PWR node'), ('e20', 'f20', 'bridge: PWR node (D2 cathode)'),
    ('b24', 'b23', 'bridge: USB VBUS -> D1 anode'), ('f23', 'g23', 'bridge: solar + -> D2 anode'),
    ('c24', 'c23', 'bridge: USB GND'), ('c23', 'd23', 'bridge: USB GND -> zener anode'), ('c23', 'c22', 'bridge: USB GND'),
    ('c22', 'b22', 'bridge: USB GND'), ('b22', 'a22', 'bridge: USB GND -> GND rail'),
    ('b19', 'c19', 'bridge: battery + -> charger BATT + hole'), ('c19', 'd19', 'bridge: battery + -> charger BATT + hole'),
]

CHARGER = [(pad, {'PWR + (input)': 'e19', 'PWR - / GND': 'a21', 'BATT +': 'd19', 'BATT -': 'a22', 'LOAD + (output)': 'j20',
                  'LOAD -': 'a23'}.get(pad, h), net.replace('bridged from b24', 'bridged from b19'))
           for pad, h, net in CV4.CHARGER]

EXPECT = {
    'GND': ['b3', 'b2', 'c1', 'a13', 'i13', 'a24', 'c12', 'e12', 'g12', 'f13', 'g15', 'c18', 'd23', 'c24', 'a19', 'a17',
            'a14', 'a15', 'a16', 'a18', 'a21', 'a22', 'a23'],
    'VBAT': ['j11', 'j24', 'i15', 'h23', 'j16', 'j17', 'j18', 'j20'],
    '5V': ['a3', 'a1', 'i18', 'i19'],
    'VDIV': ['f9', 'f11', 'h19', 'g18', 'h20', 'f10'],
    'PSENSE': ['i9', 'i10', 'e15', 'c15', 'd16'],
    'ADC0': ['c9', 'c10', 'b11'], 'ADC2': ['e9', 'e10', 'd11'], 'ADC4': ['g9', 'g10', 'h11'],
    'ANG1': ['b14', 'b15'], 'ANG2': ['d14', 'e14'], 'ANG3': ['h14', 'h15'],
    'EN1': ['d9', 'd10'], 'EN2': ['h9', 'h10'], 'EN3': ['j9', 'j10'],
    'P3IN1': ['a9', 'a10'], 'P3IN2': ['b9', 'b10'], 'P1IN1': ['f3', 'f2'], 'P1IN2': ['e3', 'e2'],
    'P2IN1': ['d3', 'd2'], 'P2IN2': ['h3', 'h2'],
    'PWR': ['b20', 'd20', 'f20', 'e18', 'e19'], 'USB+': ['b24', 'b23'], 'SOL+': ['f23', 'g23'], 'BATT+': ['b19', 'd19'],
}
