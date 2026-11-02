"""Controller carrier PCB: parts and connections. One source of truth for the KiCad board (board.py) and schematic
(schematic.py).

Same core circuit as the verified dev board (hardware/mechanical/fusion/ControllerV4/DevBoardR.py), with the modules kept:
the ESP32-C6 SuperMini and the USB-C breakout plug into female header sockets; the 18650, the MCP73871 charger module and
the optional solar panel plug into three DIFFERENT JST headers (2-pin XH, 6-pin XH, 2-pin ZH) so no plug fits the wrong
one; the three RJ12 jacks sit on the board edge. All parts through-hole, hand-soldered.

v2 (after review): per-port 0.75 A PTC on battery +, 220 ohm series resistors on IN1 / IN2 (10 ohm on EN, which also
powers the AS5600), 100 k pull-downs on EN, charger header pinned so a misplaced battery plug can't short,
470 uF bulk on battery +, 5 W zener, 100 nF on the input-power divider, test pads, a 3V3 test point.

Pin plan (ESP turned so its USB faces away from the ports; each port's pins are on its own side):
  port 1: IN1 GPIO14, IN2 GPIO18, EN GPIO7, angle GPIO6
  port 2: IN1 GPIO19, IN2 GPIO20, EN GPIO5, angle GPIO4
  port 3: IN1 GPIO16 (TX), IN2 GPIO17 (RX), EN GPIO1, angle GPIO2
  battery voltage GPIO3 (1 M / 1 M + 100 n), input-power voltage GPIO0 (1 M / 1 M + 100 n)
RJ12 pinout (both ends, straight cord): 1 battery +, 2 IN1, 3 GND, 4 angle, 5 EN, 6 IN2.
"""

# footprints from the KiCad standard libraries
FP = {
    'R': 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal',     # lying flat, legs 4 holes apart
    'D': 'Diode_THT:D_DO-41_SOD81_P7.62mm_Horizontal',
    'D5W': 'Diode_THT:D_5W_P10.16mm_Horizontal',
    'C': 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm',                        # the kit's monolithic caps, 5.08 legs
    'CP8': 'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm',
    'PTC': 'Fuse:Fuse_BelFuse_0ZRE0075FF_L11.5mm_W4.8mm',
    'SOCK10': 'Connector_PinSocket_2.54mm:PinSocket_1x10_P2.54mm_Vertical',
    'SOCK6': 'Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical',
    'XH2': 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    'XH6': 'Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical',
    'ZH2': 'Connector_JST:JST_ZH_B2B-ZR_1x02_P1.50mm_Vertical',
    'RJ12': 'Connector_RJ:RJ12_Amphenol_54601-x06_Horizontal',
    'TP': 'TestPoint:TestPoint_THTPad_1.5x1.5mm_Drill0.7mm',
    'HOLE': 'MountingHole:MountingHole_3.2mm_M3',
}

ESP_B = ['5V', 'GND', '3V3', 'GPIO20', 'GPIO19', 'GPIO18', 'GPIO15', 'GPIO14', 'GPIO9', 'GPIO8']    # 5V-side row, pin 1 at USB end
ESP_A = ['GPIO16', 'GPIO17', 'GPIO0', 'GPIO1', 'GPIO2', 'GPIO3', 'GPIO4', 'GPIO5', 'GPIO6', 'GPIO7']  # TX-side row

# which net each ESP pin is on (unused pins left unconnected). '_E' = the ESP side of a series resistor.
ESP_NET = {'5V': '+5V', 'GND': 'GND', '3V3': '+3V3',
           'GPIO14': 'P1_IN1_E', 'GPIO18': 'P1_IN2_E', 'GPIO7': 'P1_EN_E', 'GPIO6': 'P1_ADC',
           'GPIO19': 'P2_IN1_E', 'GPIO20': 'P2_IN2_E', 'GPIO5': 'P2_EN_E', 'GPIO4': 'P2_ADC',
           'GPIO16': 'P3_IN1_E', 'GPIO17': 'P3_IN2_E', 'GPIO1': 'P3_EN_E', 'GPIO2': 'P3_ADC',
           'GPIO3': 'VDIV', 'GPIO0': 'PSENSE'}

# (ref, value, footprint key, {pad: net}, note)
PARTS = [
    ('J1', 'ESP32-C6 SuperMini socket (5V row)', 'SOCK10', {k + 1: ESP_NET.get(p, '') for k, p in enumerate(ESP_B)}, 'female socket'),
    ('J2', 'ESP32-C6 SuperMini socket (TX row)', 'SOCK10', {k + 1: ESP_NET.get(p, '') for k, p in enumerate(ESP_A)}, 'female socket'),
    ('J3', 'USB-C breakout socket', 'SOCK6', {1: 'VBUS', 2: 'GND', 3: '', 4: '', 5: '', 6: ''}, 'VBUS GND CC1 D- D+ CC2'),
    ('J4', 'Battery (18650, JST-XH 2-pin)', 'XH2', {1: 'GND', 2: 'BATT+'}, 'pin 1 = -'),
    # pins 3 and 5 empty, one GND (the module's GND pads are common): the cell's 2-pin XH plug, pushed into this 6-pin
    # header at ANY offset, either lands correctly (GND / BATT+) or touches only one live pin - it can never short
    ('J5', 'Charger (JST-XH 6-pin)', 'XH6', {1: 'GND', 2: 'BATT+', 3: '', 4: 'VBAT', 5: '', 6: 'PWR'},
     'GND, BATT+, -, LOAD+, -, PWR+'),
    ('J8', 'Solar (optional, JST-ZH 2-pin)', 'ZH2', {1: 'GND', 2: 'SOL+'}, 'pin 1 = -'),
    ('C1', '10uF', 'C', {1: '+5V', 2: 'GND'}, 'ESP 5V'),
    ('C9', '470uF 10V', 'CP8', {1: 'VBAT', 2: 'GND'}, 'bulk on battery +, pad 1 = +'),
    ('D3', '1N5819', 'D', {1: '+5V', 2: 'VBAT'}, 'pad 1 = cathode (band)'),
    ('R1', '1M', 'R', {1: 'VBAT', 2: 'VDIV'}, 'battery divider top'),
    ('R2', '1M', 'R', {1: 'VDIV', 2: 'GND'}, 'battery divider bottom'),
    ('C2', '100nF', 'C', {1: 'VDIV', 2: 'GND'}, 'battery divider filter'),
    ('D1', '1N5819', 'D', {1: 'PWR', 2: 'VBUS'}, 'USB input'),
    ('D2', '1N5819', 'D', {1: 'PWR', 2: 'SOL+'}, 'solar input'),
    ('D4', '1N5341B 6.2V 5W', 'D5W', {1: 'PWR', 2: 'GND'}, 'solar clamp'),
    ('R3', '1M', 'R', {1: 'PWR', 2: 'PSENSE'}, 'input-power divider top'),
    ('R4', '1M', 'R', {1: 'PSENSE', 2: 'GND'}, 'input-power divider bottom'),
    ('C6', '100nF', 'C', {1: 'PSENSE', 2: 'GND'}, 'input-power divider filter'),
    ('TP1', 'BAT+', 'TP', {1: 'VBAT'}, 'test pad'), ('TP2', '5V', 'TP', {1: '+5V'}, 'test pad'),
    ('TP3', '3V3', 'TP', {1: '+3V3'}, 'test pad'), ('TP4', 'PWR', 'TP', {1: 'PWR'}, 'test pad'),
    ('TP5', 'GND', 'TP', {1: 'GND'}, 'test pad'),
]
for k in (1, 2, 3):
    PARTS += [
        ('J%d' % (8 + k), 'RJ12 port %d' % k, 'RJ12',
         {1: 'P%d_VBAT' % k, 2: 'P%d_IN1' % k, 3: 'GND', 4: 'P%d_ANG' % k, 5: 'P%d_EN' % k, 6: 'P%d_IN2' % k}, '6P6C'),
        ('F%d' % k, '0.75A PTC', 'PTC', {1: 'VBAT', 2: 'P%d_VBAT' % k}, 'resettable fuse, port %d battery +' % k),
        ('R%d' % (4 + k), '1k', 'R', {1: 'P%d_ANG' % k, 2: 'P%d_ADC' % k}, 'angle filter'),
        ('C%d' % (2 + k), '100nF', 'C', {1: 'P%d_ADC' % k, 2: 'GND'}, 'angle filter'),
        ('R%d' % (8 + 4 * (k - 1)), '220', 'R', {1: 'P%d_IN1' % k, 2: 'P%d_IN1_E' % k}, 'series, port %d IN1' % k),
        ('R%d' % (9 + 4 * (k - 1)), '220', 'R', {1: 'P%d_IN2' % k, 2: 'P%d_IN2_E' % k}, 'series, port %d IN2' % k),
        # EN also powers the tilter's AS5600 (~6.5 mA): only 10 ohm here, or the sensor's supply would sag
        ('R%d' % (10 + 4 * (k - 1)), '10', 'R', {1: 'P%d_EN' % k, 2: 'P%d_EN_E' % k}, 'series, port %d EN' % k),
        ('R%d' % (11 + 4 * (k - 1)), '100k', 'R', {1: 'P%d_EN' % k, 2: 'GND'}, 'pull-down, port %d EN' % k),
    ]
PARTS += [('H%d' % k, 'M3', 'HOLE', {}, 'mounting hole') for k in (1, 2, 3)]


def nets():
    out = {}
    for ref, _, _, pads, _ in PARTS:
        for pad, net in pads.items():
            if net:
                out.setdefault(net, []).append((ref, pad))
    return out


if __name__ == '__main__':
    for net, conns in sorted(nets().items()):
        print('%-10s %s' % (net, ' '.join('%s.%s' % c for c in conns)))
