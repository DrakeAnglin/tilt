#!/usr/bin/env python3
"""Read the board's USB log for N seconds: python3 mon.py [seconds] [--reset] [port]
Opens the port without touching the reset lines (on this chip's USB they can drop it into flashing mode)."""
import sys, time, serial
args = [a for a in sys.argv[1:] if not a.startswith('--')]
secs = float(args[0]) if args else 10
port = args[1] if len(args) > 1 else '/dev/cu.usbmodem21101'
def opened():
    s = serial.Serial()
    s.port = port; s.baudrate = 115200; s.timeout = 0.2; s.dtr = False; s.rts = False
    s.open()
    return s
t0 = time.time(); buf = b''; first = '--reset' in sys.argv
while time.time() - t0 < secs:
    try:
        s = opened()
        if first:
            first = False
            s.rts = True; time.sleep(0.15); s.rts = False
        while time.time() - t0 < secs:
            d = s.read(4096)
            if d: sys.stdout.buffer.write(d); sys.stdout.buffer.flush()
    except Exception:
        time.sleep(0.1)
