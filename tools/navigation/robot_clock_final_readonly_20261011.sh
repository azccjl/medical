#!/bin/bash
set -e
systemctl is-active chrony
systemctl is-enabled chrony
chronyc tracking
chronyc -n sources -v
systemctl is-active systemd-timesyncd || true
systemctl show chrony --property=Restart --property=RestartUSec
cat /etc/chrony/chrony.conf
python2 - <<'PY'
import os,glob
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for p in os.listdir('/proc'):
    if not p.isdigit():continue
    for f in glob.glob('/proc/'+p+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(p)
        except OSError:pass
print('FINAL_BASE_SERIAL_OWNERS',owners)
assert not owners, owners
PY
