#!/bin/bash
set -e
cd /home/EPRobot/medical_navigation_prepare_v2_20261011
python2 navigation_audited_base.py --acceptance site_acceptance.template.json --map-sha UNACCEPTED
python2 - <<'PY'
import os,glob,json,hashlib
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
assert not owners,owners
for name in ('navigation_audited_base.py','navigation_policy.py','route_geometry.py','site_acceptance.template.json'):
    print('STAGED_SHA256',name,hashlib.sha256(open(name,'rb').read()).hexdigest())
print('DEFAULT_NO_ROS_NO_SERIAL_BASE_REMAINS_STOPPED')
PY
