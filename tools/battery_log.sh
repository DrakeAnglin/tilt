#!/bin/bash
# Log a controller's resting cell voltage every 15 minutes, to compare Thread with Wi-Fi over a day or more.
#   tools/battery_log.sh <address> [minutes]      address: the controller (192.168.50.135) or through a hub
#                                                  (192.168.50.122/c/<id>)
# Writes ~/.tilt/battery-log.csv: time, network, resting volts, percent, input volts, motor seconds so far.
# Leave it running (nohup tools/battery_log.sh ... &). Each reading wakes the controller for a moment.
ADDR=${1:?usage: tools/battery_log.sh <address> [minutes]}
MIN=${2:-15}
PY=${PY:-$HOME/.espressif/python_env/idf5.5_py3.9_env/bin/python}
cd "$(dirname "$0")"
mkdir -p ~/.tilt
OUT=~/.tilt/battery-log.csv
[ -f "$OUT" ] || echo "time,net,rest_v,pct,vin_v,motor_s" > "$OUT"
while true; do
  NET=$("$PY" blinds_client.py --ip "$ADDR" hello 2>/dev/null | sed -n 's/.*"net":"\([a-z]*\)".*/\1/p')
  "$PY" blinds_client.py --ip "$ADDR" --as owner get /api/dev 2>/dev/null | python3 -c "
import sys, json, time
d = json.load(sys.stdin); p = d['pwr']
print('%s,%s,%.3f,,%.2f,%d' % (time.strftime('%Y-%m-%d %H:%M'), '$NET' or '?', p['rest'], p['vin'], d['st']['motorS']))" >> "$OUT" 2>/dev/null \
    || echo "$(date '+%Y-%m-%d %H:%M'),no answer,,,," >> "$OUT"
  sleep $((MIN * 60))
done
