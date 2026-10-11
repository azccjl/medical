#!/bin/bash
set -e
cd /home/EPRobot/medical_navigation_prepare_20261011
python2 navigation_audited_base.py --acceptance site_acceptance.template.json --map-sha UNACCEPTED
python2 - <<'PY'
import os,glob,json
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
assert not owners,owners
print('STAGED_DEFAULT_DID_NOT_IMPORT_ROS_OR_OPEN_SERIAL')
PY
