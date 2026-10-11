#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
date -Ins
rosnode list
if ! rostopic info /medical_ground_cmd_vel; then
    echo CONTROL_TOPIC_ABSENT_AFTER_DRIVER_STOP
fi
python2 - <<'PY'
from __future__ import print_function
import os, glob, hashlib, json
device=os.path.realpath('/dev/EPRobot_base')
owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:
                owners.append(dict(pid=int(pid),fd=os.path.basename(fd)))
        except OSError: pass
print('SERIAL_OWNERS '+json.dumps(owners))
driver='/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'
print('DRIVER_SHA256 '+hashlib.sha256(open(driver,'rb').read()).hexdigest())
root='/home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063'
# Preserve timestamped original lines, including stationary context.
windows=[('13:02:42','13:02:45'),('13:04:23','13:04:26'),
         ('13:07:00','13:07:03'),('13:08:30','13:08:33'),
         ('13:10:59','13:11:03'),('13:13:55','13:13:59')]
for path in sorted(glob.glob(root+'/base_control-2.log*')):
    print('RAW_SOURCE '+path)
    with open(path,'rb') as handle:
        for line in handle:
            if not line.startswith('[rosout]'): continue
            parts=line.split('2026-10-11 ',1)
            if len(parts)!=2: continue
            clock=parts[1][:8]
            if any(begin<=clock<=end for begin,end in windows):
                print(line.rstrip())
PY
