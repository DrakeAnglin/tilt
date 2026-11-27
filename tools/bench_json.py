#!/usr/bin/env python3
"""Read what a Tilt Hub or a controller answers on the bench, for tools/flash.sh and tools/battery_log.sh.
Each command reads the JSON on stdin and prints one line.

  bench_json.py ota-progress <controller id>   from the hub's /api/info: update state, percent, error ('?': not listed)
  bench_json.py hub-cid <controller id>        from the hub's /api/info: the controller's hub key id (empty: none)
  bench_json.py battery-row <network>          from a controller's /api/dev: one CSV row for battery-log.csv
"""
import json
import sys
import time


def _member(info, cid):
    return next((c for c in info['c'] if c['id'] == cid), None)


def ota_progress(info, cid):
    """'<state> <percent> <error>' of one controller's update, or '?' when the hub does not list it."""
    m = _member(info, cid)
    if m is None:
        return '?'
    return ' '.join(str(v) for v in (m.get('ota', 0), m.get('otaPct', 0), m.get('otaErr', '')))


def hub_cid(info, cid):
    """The hub key id the hub has for this controller; '' when there is none."""
    m = _member(info, cid)
    return m.get('hubCid', '') if m else ''


def battery_row(dev, net, now):
    """time, network, resting volts, percent (left empty), input volts, motor seconds so far."""
    p = dev['pwr']
    return '%s,%s,%.3f,,%.2f,%d' % (time.strftime('%Y-%m-%d %H:%M', time.localtime(now)), net or '?', p['rest'],
                                    p['vin'], dev['st']['motorS'])


def main(argv):
    if len(argv) != 2 or argv[0] not in ('ota-progress', 'hub-cid', 'battery-row'):
        print('usage: ' + __doc__.split('\n\n')[1].strip(), file=sys.stderr)
        return 2
    data = json.load(sys.stdin)
    if argv[0] == 'ota-progress':
        print(ota_progress(data, argv[1]))
    elif argv[0] == 'hub-cid':
        print(hub_cid(data, argv[1]))
    else:
        print(battery_row(data, argv[1], time.time()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
