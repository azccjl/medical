#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
from __future__ import print_function
import os, glob, json
device=os.path.realpath('/dev/EPRobot_base')
owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:
                owners.append({'pid':int(pid),'fd':os.path.basename(fd)})
        except OSError: pass
print('SERIAL_OWNERS',json.dumps(owners))
assert not owners, 'BASE_SERIAL_IN_USE'
PY
echo NO_BASE_SERIAL_OPENED_BY_THIS_CHECK
