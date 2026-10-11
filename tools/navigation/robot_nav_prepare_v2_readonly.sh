#!/bin/bash
set -e
python2 - <<'PY'
import os,glob,hashlib
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
assert not owners,owners
driver='/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'
assert hashlib.sha256(open(driver,'rb').read()).hexdigest()=='d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'
print('BASE_SERIAL_UNOWNED_LEGACY_SOURCE_UNCHANGED')
PY
test ! -e /home/EPRobot/medical_navigation_prepare_v2_20261011
mkdir -m 700 /home/EPRobot/medical_navigation_prepare_v2_20261011
