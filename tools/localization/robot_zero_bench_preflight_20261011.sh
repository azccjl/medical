#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
date -Ins
rosnode list
python2 - <<'PY'
from __future__ import print_function
import os, glob, hashlib, json
import rosgraph
device=os.path.realpath('/dev/EPRobot_base')
owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device: owners.append((pid,fd))
        except OSError: pass
if owners: raise RuntimeError('SERIAL_STILL_OWNED '+repr(owners))
driver='/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'
digest=hashlib.sha256(open(driver,'rb').read()).hexdigest()
assert digest=='d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'
master=rosgraph.Master('/medical_zero_bench_preflight')
types=dict(master.getTopicTypes())
for topic,publishers in master.getSystemState()[0]:
    if publishers and types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped'):
        raise RuntimeError('CONTROL_PUBLISHER '+repr((topic,publishers)))
print(json.dumps(dict(status='BENCH_PREFLIGHT_PASSED',serial_owners=owners,driver_sha256=digest)))
PY
