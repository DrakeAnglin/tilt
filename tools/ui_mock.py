#!/usr/bin/env python3
"""A pretend controller for working on the web app without the board: python3 tools/ui_mock.py [port]
Serves firmware/blinds/ui live (no build step) and fakes the /api. Blind 1 is set up, 2 is not, port 3 is empty.
Add ?battery to the page address once to pretend it runs on battery."""
import json, math, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from build_ui import page

NAN = None
T0 = time.time()
st = dict(name='Office', sync=1, closeUp=1, battMode=0, checkin=15, tx=15, tz='CST6CDT,M3.2.0,M11.1.0', tzn='America/Chicago', battery=False,
          log=['+1s  start 1.0.0-mock (power on), battery 3.95 V, input 4.90 V'])
B = [dict(name='Left window', hid=0, pres=1, up=250.0, open=180.0, down=105.0, ang=180.0, sign=1, speed=100, fav=50, tgt=None, jog=0, jogT=0, last='', moves=3, stalls=0),
     dict(name='Blind 2', hid=0, pres=1, up=NAN, open=NAN, down=NAN, ang=40.0, sign=1, speed=100, fav=50, tgt=None, jog=0, jogT=0, last='', moves=0, stalls=0),
     dict(name='Blind 3', hid=0, pres=0, up=NAN, open=NAN, down=NAN, ang=NAN, sign=1, speed=100, fav=50, tgt=None, jog=0, jogT=0, last='', moves=0, stalls=0)]
SCH = [dict(on=0, days=127, mask=0, min=480, tilt=0) for _ in range(8)]
SCH[0] = dict(on=1, days=62, mask=1, min=450, tilt=0)
SCH[1] = dict(on=1, days=127, mask=3, min=1290, tilt=100)

def diff(a, b): return (a - b + 540) % 360 - 180
def cal(b): return None not in (b['up'], b['open'], b['down'])
def tilt(b):
    if not cal(b) or b['ang'] is None: return None
    x = diff(b['ang'], b['open']) * (1 if diff(b['up'], b['open']) > 0 else -1)
    return x / abs(diff(b['up'], b['open'])) * 100 if x >= 0 else x / abs(diff(b['down'], b['open'])) * 100
def ang_of(b, t):
    s = 1 if diff(b['up'], b['open']) > 0 else -1
    x = t / 100 * abs(diff(b['up'], b['open'])) if t >= 0 else t / 100 * abs(diff(b['down'], b['open']))
    return (b['open'] + x * s) % 360
def log(m): st['log'].append('%02d:%02d:%02d  %s' % (time.localtime()[3:6] + (m,)))
def sim():
    while True:
        time.sleep(0.05)
        for b in B:
            if b['jog'] and time.time() < b['jogT']: b['ang'] = (b['ang'] + b['jog'] * 1.2) % 360
            else: b['jog'] = 0
            if b['tgt'] is not None:
                d = diff(ang_of(b, b['tgt']), b['ang'])
                if abs(d) < 1.3: b['ang'] = ang_of(b, b['tgt']); log('%s: reached at tilt %d' % (b['name'], b['tgt'])); b['tgt'] = None; b['last'] = 'reached'; b['moves'] += 1
                else: b['ang'] = (b['ang'] + math.copysign(1.1, d)) % 360
threading.Thread(target=sim, daemon=True).start()
def moving(): return next((i for i, b in enumerate(B) if b['tgt'] is not None or b['jog']), -1)

class Hd(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def out(self, o, ct='application/json'):
        d = o if isinstance(o, bytes) else json.dumps(o).encode()
        self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Content-Length', str(len(d))); self.end_headers(); self.wfile.write(d)
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0); body = self.rfile.read(n)
        if self.path.startswith('/api/update'): return self.out(dict(ok=0, err='this is the pretend controller'))
        self.out(dict(ok=1))
    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}; p = u.path
        if p == '/':
            if 'battery' in q: st['battery'] = True
            if 'usb' in q: st['battery'] = False
            return self.out(page().encode(), 'text/html')
        if not p.startswith('/api/'): self.send_response(404); self.end_headers(); return
        a = p[5:]; bat = st['battery']; mvp = moving()
        if a == 's':
            return self.out(dict(v='1.0.0-mock', name=st['name'], t=int(time.time()), tok=1, up=int(time.time() - T0),
                batt=dict(v=3.82 if bat else 3.95, pct=58 if bat else 76, st='battery' if bat else 'charging', vin=0.1 if bat else 4.9, low=0),
                pw=dict(mode=st['battMode'], sleepIn=95 if bat and not st['battMode'] else -1, checkin=st['checkin']), closeUp=st['closeUp'], sync=st['sync'], ap=0, mv=mvp, log=len(st['log']),
                b=[dict(name=b['name'], hid=b['hid'], pres=b['pres'], seen=1, cal=1 if cal(b) else 0, tilt=tilt(b), tgt=b['tgt'], mov=1 if (b['tgt'] is not None or b['jog']) else 0, q=0, fav=b['fav'], ang=b['ang'], last=b['last']) for b in B]))
        if a == 'dev':
            return self.out(dict(sys=dict(fw='1.0.0-mock', build='Nov 15 2026 12:00:00', core='3.3.12', idf='v5.5.1', chip='ESP32-C6', rev=2, mhz=160, flash=4194304, app=1198000, appMax=1310720, part='app0', md5='0123456789abcdef', heap=265000, heapMin=230000, temp=33.5, rst='power on', up=int(time.time() - T0), pending=0, mac='AA:BB:CC:DD:EE:FF'),
                wifi=dict(ssid='HomeNet', cfg='HomeNet', own=0, ip='192.168.50.135', rssi=-61, ch=6, host='blinds-pcb.local', tx=st['tx'], ap=0),
                pwr=dict(vdd=3.02, vbat=3.79, rest=3.82, vin=0.1 if bat else 4.9, powered=0 if bat else 1, awakeS=1260, motorMs=42000, wakes=2100, since=int(time.time()) - 86400, keep=0, next=int(time.time()) + 5400),
                tune=dict(grace=12000, stall=2500, deg10=10, max=180), st=dict(boots=12, brown=2, crash=0, wdt=0, wakes=5321, checkins=96, ota=3, motorS=210),
                mv=dict(kind=1 if mvp >= 0 else 0, port=mvp, st=1, nudges=0, live=B[mvp]['ang'] if mvp >= 0 else None),
                p=[dict(ang=b['ang'], mv=int((b['ang'] or 0) / 360 * 3300), pres=b['pres'], up=b['up'], open=b['open'], down=b['down'], sign=b['sign'], signSeen=1, bias=4.0, speed=b['speed'], moves=b['moves'], stalls=b['stalls'], prob=None if cal(b) else 'not all three positions are marked') for b in B]))
        if a == 'cfg': return self.out(dict(name=st['name'], sync=st['sync'], closeUp=st['closeUp'], battMode=st['battMode'], checkin=st['checkin'], tx=st['tx'], tz=st['tz'], tzn=st['tzn'], b=[dict(name=b['name'], hid=b['hid'], speed=b['speed'], fav=b['fav']) for b in B], sched=SCH))
        if a == 'log': s = int(q.get('since', 0)); return self.out(dict(seq=len(st['log']), lines=st['log'][s:]))
        if a == 'hist': return self.out(dict(h=[0] * 60 + [int((3.6 + 0.5 * abs(math.sin(i / 17)) - 2.5) * 100) for i in range(108)]))
        if a == 'scan': time.sleep(1); return self.out(dict(nets=[dict(ssid='HomeNet', rssi=-55, lock=1), dict(ssid='Guest', rssi=-70, lock=0)]))
        if a == 'go':
            ok = 0
            for i, b in enumerate(B):
                every = q.get('b') == 'all' or (st['sync'] and not q.get('solo'))
                if q.get('b') != 'all' and int(q['b']) != i and not every: continue
                if (every and (q.get('b') == 'all' or int(q['b']) != i)) and (b['hid'] or not cal(b) or not b['pres']): continue
                if not cal(b): return self.out(dict(ok=0, err='not set up yet'))
                to = q.get('to'); t = float(q['t']) if 't' in q else {'open': 0, 'up': 100, 'down': -100, 'close': 100 if st['closeUp'] else -100, 'fav': B[0 if q.get('b') == 'all' else int(q['b'])]['fav']}[to]
                b['tgt'] = max(-100, min(100, t)); ok += 1
            return self.out(dict(ok=1) if ok else dict(ok=0, err='no blind is set up'))
        if a == 'stop':
            for b in B: b['tgt'] = None; b['jog'] = 0
        elif a == 'jog': b = B[int(q['b'])]; b['jog'] = int(q['d']); b['jogT'] = time.time() + int(q['ms']) / 1000
        elif a == 'angle': pass
        elif a == 'mark':
            b = B[int(q['b'])]; w = q['w']
            if w == 'clear': b['up'] = b['open'] = b['down'] = None
            else: b[w] = b['ang']
            log('%s: marked %s at %.1f deg' % (b['name'], w, b['ang'] or 0))
            prob = None
            if cal(b):
                u, d = diff(b['up'], b['open']), diff(b['down'], b['open'])
                if abs(u) < 8 or abs(d) < 8: prob = 'open is too close to a closed mark'
                elif (u > 0) == (d > 0): prob = 'open must be between the two closed marks'
            return self.out(dict(ok=1, ang=b['ang'], prob=prob))
        elif a == 'set':
            k, v = q['k'], q.get('v', '')
            if k[0] == 'b' and k[2] == '.': b = B[int(k[1])]; f = k[3:]; b[{'hid': 'hid', 'name': 'name', 'fav': 'fav', 'speed': 'speed', 'sign': 'sign'}[f]] = v if f == 'name' else int(v)
            elif k == 'name': st['name'] = v
            elif k == 'tz': st['tz'] = v; st['tzn'] = q.get('n', '')
            else: st[{'checkin': 'checkin'}.get(k, k)] = int(v)
        elif a == 'sched': SCH[int(q['i'])] = dict(on=int(q['on']), days=int(q['days']), mask=int(q['mask']), min=int(q['min']), tilt=int(q['tilt']))
        self.out(dict(ok=1))

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print('pretend controller on http://localhost:%d' % port)
    ThreadingHTTPServer(('127.0.0.1', port), Hd).serve_forever()
