#!/bin/bash
set -e
python2 - <<'PY'
import os,glob
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
assert not owners,owners
print('BASE_SERIAL_UNOWNED_BEFORE_FILE_UPLOAD')
PY
test ! -e /home/EPRobot/medical_navigation_prepare_20261011
mkdir -m 700 /home/EPRobot/medical_navigation_prepare_20261011
