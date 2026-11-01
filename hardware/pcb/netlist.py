"""Controller carrier PCB: parts and connections. One source of truth for the KiCad board generator (board.py).

Same circuit as the verified dev board (hardware/mechanical/fusion/ControllerV4/DevBoardR.py), with the modules kept:
the ESP32-C6 SuperMini and the USB-C breakout plug into female header sockets, the MCP73871 charger module and the
18650 plug into JST-XH headers, and the three RJ12 jacks sit on the board edge. All parts through-hole, hand-soldered.

Pin plan (motor IN pins chosen so each port's traces stay on its own side of the ESP; angle / EN as on the dev board):
  port 1: IN1 GPIO16 (TX), IN2 GPIO17 (RX), EN GPIO1, angle GPIO0
  port 2: IN1 GPIO20, IN2 GPIO19, EN GPIO5, angle GPIO2
  port 3: IN1 GPIO18, IN2 GPIO14, EN GPIO7, angle GPIO4
  battery voltage GPIO3 (1 M / 1 M + 100 n), input-power voltage GPIO6 (1 M / 1 M)
RJ12 pinout (both ends, straight cord): 1 battery +, 2 IN1, 3 GND, 4 angle, 5 EN, 6 IN2.
"""

# footprints from the KiCad standard libraries
FP = {
    'R': 'Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal',     # lying flat, legs 4 holes apart
    'D': 'Diode_THT:D_DO-41_SOD81_P7.62mm_Horizontal',
    'C': 'Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm',                        # the kit's monolithic caps, 5.08 legs
    'SOCK10': 'Connector_PinSocket_2.54mm:PinSocket_1x10_P2.54mm_Vertical',
    'SOCK6': 'Connector_PinSocket_2.54mm:PinSocket_1x06_P2.54mm_Vertical',
    'XH2': 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    'XH3': 'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',
    'RJ12': 'Connector_RJ:RJ12_Amphenol_54601-x06_Horizontal',
    'HOLE': 'MountingHole:MountingHole_3.2mm_M3',
}

ESP_B = ['5V', 'GND', '3V3', 'GPIO20', 'GPIO19', 'GPIO18', 'GPIO15', 'GPIO14', 'GPIO9', 'GPIO8']    # 5V-side row, pin 1 at USB end
ESP_A = ['GPIO16', 'GPIO17', 'GPIO0', 'GPIO1', 'GPIO2', 'GPIO3', 'GPIO4', 'GPIO5', 'GPIO6', 'GPIO7']  # TX-side row

# which net each ESP pin is on (unused pins left unconnected)
ESP_NET = {'5V': '+5V', 'GND': 'GND',
           'GPIO16': 'P1_IN1', 'GPIO17': 'P1_IN2', 'GPIO1': 'P1_EN', 'GPIO0': 'P1_ADC',
           'GPIO20': 'P2_IN1', 'GPIO19': 'P2_IN2', 'GPIO5': 'P2_EN', 'GPIO2': 'P2_ADC',
           'GPIO18': 'P3_IN1', 'GPIO14': 'P3_IN2', 'GPIO7': 'P3_EN', 'GPIO4': 'P3_ADC',
           'GPIO3': 'VDIV', 'GPIO6': 'PSENSE'}

# (ref, value, footprint key, {pad: net}, note)
PARTS = [
    ('J1', 'ESP32-C6 SuperMini socket (5V row)', 'SOCK10', {k + 1: ESP_NET.get(p, '') for k, p in enumerate(ESP_B)}, 'female socket'),
    ('J2', 'ESP32-C6 SuperMini socket (TX row)', 'SOCK10', {k + 1: ESP_NET.get(p, '') for k, p in enumerate(ESP_A)}, 'female socket'),
    ('J3', 'USB-C breakout socket', 'SOCK6', {1: 'VBUS', 2: 'GND', 3: '', 4: '', 5: '', 6: ''}, 'VBUS GND CC1 D- D+ CC2'),
    ('J4', 'Battery (18650, JST-XH)', 'XH2', {1: 'GND', 2: 'BATT+'}, 'pin 1 = -'),
    ('J5', 'Charger + (BATT+, PWR+)', 'XH2', {1: 'BATT+', 2: 'PWR'}, ''),
    ('J6', 'Charger LOAD+', 'XH2', {1: 'VBAT', 2: 'VBAT'}, 'both pins battery +'),
    ('J7', 'Charger GND (PWR-, BATT-, LOAD-)', 'XH3', {1: 'GND', 2: 'GND', 3: 'GND'}, ''),
    ('J8', 'Solar (optional)', 'XH2', {1: 'GND', 2: 'SOL+'}, 'pin 1 = -'),
    ('C1', '10uF', 'C', {1: '+5V', 2: 'GND'}, 'ESP 5V'),
    ('D3', '1N5819', 'D', {1: '+5V', 2: 'VBAT'}, 'pad 1 = cathode (band)'),
    ('R1', '1M', 'R', {1: 'VBAT', 2: 'VDIV'}, 'battery divider top'),
    ('R2', '1M', 'R', {1: 'VDIV', 2: 'GND'}, 'battery divider bottom'),
    ('C2', '100nF', 'C', {1: 'VDIV', 2: 'GND'}, 'battery divider filter'),
    ('D1', '1N5819', 'D', {1: 'PWR', 2: 'VBUS'}, 'USB input'),
    ('D2', '1N5819', 'D', {1: 'PWR', 2: 'SOL+'}, 'solar input'),
    ('D4', '6.2V zener 1W', 'D', {1: 'PWR', 2: 'GND'}, 'solar clamp'),
    ('R3', '1M', 'R', {1: 'PWR', 2: 'PSENSE'}, 'input-power divider top'),
    ('R4', '1M', 'R', {1: 'PSENSE', 2: 'GND'}, 'input-power divider bottom'),
]
for k in (1, 2, 3):
    parts_k = [
        ('J%d' % (8 + k), 'RJ12 port %d' % k, 'RJ12',
         {1: 'VBAT', 2: 'P%d_IN1' % k, 3: 'GND', 4: 'P%d_ANG' % k, 5: 'P%d_EN' % k, 6: 'P%d_IN2' % k}, '6P6C'),
        ('R%d' % (4 + k), '1k', 'R', {1: 'P%d_ANG' % k, 2: 'P%d_ADC' % k}, 'angle filter'),
        ('C%d' % (2 + k), '100nF', 'C', {1: 'P%d_ADC' % k, 2: 'GND'}, 'angle filter'),
    ]
    PARTS += parts_k
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
        print('%-8s %s' % (net, ' '.join('%s.%s' % c for c in conns)))
