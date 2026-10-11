#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
test ! -e /home/EPRobot/medical-supported-wheel-pulse-audit2-20261011.jsonl
test ! -e /home/EPRobot/medical-supported-wheel-pulse-audit2-20261011.jsonl.lock
test ! -e /home/EPRobot/medical-supported-wheel-pulse-run2-20261011.log
python2 - <<'PY'
import hashlib,sys
candidate='/home/EPRobot/medical_supported_wheel_pulse_20261011.py'
assert hashlib.sha256(open(candidate,'rb').read()).hexdigest()=='7870c57e4865f5cd04f826f257a6c4d79d0abdddef4ecbb230ff27ad02ca7c0f'
sys.path.insert(0,'/home/EPRobot/robot_ws/src/eprobot_start/script')
import medical_stop_window
path=medical_stop_window.__file__
if path.endswith('.pyc'):path=path[:-1]
assert hashlib.sha256(open(path,'rb').read()).hexdigest()=='15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43', 'STOP_WINDOW_SOURCE_CHANGED'
print('CANDIDATE_AND_STRICT_STOP_IDENTITY_PASSED')
PY
date -Ins
task_status=0
timeout --signal=INT --kill-after=5s 40s python2 /home/EPRobot/medical_supported_wheel_pulse_20261011.py \
  --execute-wheel-pulse --wheels-supported --power-stop-confirmed --duration 30 \
  --audit /home/EPRobot/medical-supported-wheel-pulse-audit2-20261011.jsonl \
  >/home/EPRobot/medical-supported-wheel-pulse-run2-20261011.log 2>&1 || task_status=$?
echo SUPPORTED_PULSE_EXIT=$task_status
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
print('POST_SUPPORTED_PULSE_SERIAL_OWNERS '+json.dumps(owners))
if owners:raise RuntimeError('SERIAL_OWNER_REMAINS')
PY
exit "$task_status"
