#!/bin/bash
set -e
systemctl is-active chrony
chronyc tracking
chronyc -n sources -v
python2 - <<'PY'
import os,glob
d=os.path.realpath('/dev/EPRobot_base'); owners=[]
for p in os.listdir('/proc'):
    if not p.isdigit():continue
    for f in glob.glob('/proc/'+p+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(p)
        except OSError:pass
print('BASE_SERIAL_OWNERS',owners)
assert not owners, owners
PY
test ! -e /home/EPRobot/medical-clock-verify-udp-v2-20261011.log
nohup timeout --signal=INT 240s python2 /home/EPRobot/medical_offline_clock.py server \
  --bind 192.168.12.1 --allow-client 192.168.12.71 --port 18081 \
  >/home/EPRobot/medical-clock-verify-udp-v2-20261011.log 2>&1 </dev/null &
echo READONLY_CLOCK_OBSERVER_V2_STARTED
