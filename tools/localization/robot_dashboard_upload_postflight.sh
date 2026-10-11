#!/bin/bash
set -e
cd /home/EPRobot/medical_dashboard_20261011
python2 - <<'PY'
import hashlib,json,glob,os
for name,digest in json.load(open('dashboard-manifest.json')).items():
    assert hashlib.sha256(open(name,'rb').read()).hexdigest()==digest
device=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:owners.append(pid)
        except OSError:pass
assert not owners,owners
print('ROBOT_UPLOAD_HASHES_MATCH_SERIAL_UNOWNED_NO_BASE_START')
PY
