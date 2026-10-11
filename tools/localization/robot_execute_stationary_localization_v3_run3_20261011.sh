#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
for path in /home/EPRobot/medical-stationary-localization-v3-run3-audit-20261011.jsonl /home/EPRobot/medical-stationary-localization-v3-run3-audit-20261011.jsonl.lock /home/EPRobot/medical-stationary-localization-v3-run3-run-20261011.log; do
  test ! -e "$path"
done
python2 - <<'PY'
import hashlib
assert hashlib.sha256(open('/home/EPRobot/medical_stationary_localization_v3_20261011.py','rb').read()).hexdigest()=='aa06ade75f042131310bf2bad910070728472d68c486ebd3592e206a31b6384d'
PY
date -Ins
task_status=0
timeout --signal=INT --kill-after=5s 135s python2 /home/EPRobot/medical_stationary_localization_v3_20261011.py \
  --execute-stationary --vehicle-stationary-confirmed --power-stop-confirmed --duration 120 \
  --audit /home/EPRobot/medical-stationary-localization-v3-run3-audit-20261011.jsonl \
  >/home/EPRobot/medical-stationary-localization-v3-run3-run-20261011.log 2>&1 || task_status=$?
echo STATIONARY_LOCALIZATION_EXIT=$task_status
date -Ins
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
print('POST_STATIONARY_SERIAL_OWNERS '+json.dumps(owners))
if owners:raise RuntimeError('SERIAL_OWNER_REMAINS')
PY
exit "$task_status"
