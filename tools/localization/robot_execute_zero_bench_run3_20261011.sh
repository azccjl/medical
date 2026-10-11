#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
test ! -e /home/EPRobot/medical-zero-bench-run3-20261011.log
test ! -e /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl
test ! -e /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl.lock
python2 - <<'PY'
import hashlib
path='/home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py'
assert hashlib.sha256(open(path,'rb').read()).hexdigest()=='b04c466479d72139c02ec27561c81d9f254da5fa75072ac357bca21aa41b4c0f', 'DIAGNOSTIC_UPLOAD_CHANGED'
PY
python2 /home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py --offline-check
date -Ins
task_status=0
# One bounded zero-only bench run. Never start the floor driver here.
timeout --signal=INT --kill-after=5s 40s python2 /home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py \
  --execute-bench --wheels-supported --power-stop-confirmed --duration 30 \
  --audit /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl \
  >/home/EPRobot/medical-zero-bench-run3-20261011.log 2>&1 || task_status=$?
echo ZERO_BENCH_EXIT=$task_status
date -Ins
rosnode list
python2 - <<'PY'
from __future__ import print_function
import os,glob,json
device=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:owners.append((pid,fd))
        except OSError:pass
print('POST_BENCH_SERIAL_OWNERS '+json.dumps(owners))
if owners:raise RuntimeError('SERIAL_OWNER_REMAINS')
PY
exit "$task_status"
