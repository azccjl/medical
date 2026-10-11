#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
from __future__ import print_function
import glob, os, hashlib, sys, json, rosgraph
path='/home/EPRobot/medical_stationary_localization_v2_20261011.py'
assert hashlib.sha256(open(path,'rb').read()).hexdigest()=='dff2da00fc4d6459c64ad7b8b95acd51a959babc2a04a0c5daf58a47d9fa7495'
sys.path.insert(0,'/home/EPRobot/robot_ws/src/eprobot_start/script')
import medical_stop_window
stop_path=medical_stop_window.__file__
if stop_path.endswith('.pyc'): stop_path=stop_path[:-1]
assert hashlib.sha256(open(stop_path,'rb').read()).hexdigest()=='15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43'
device=os.path.realpath('/dev/EPRobot_base'); owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device: owners.append(pid)
        except OSError: pass
assert not owners, owners
master=rosgraph.Master('/medical_stationary_upload_preflight')
types=dict(master.getTopicTypes()); pubs=dict(master.getSystemState()[0])
for topic,nodes in pubs.items():
    if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped') or topic in ('/move_base/goal','/move_base_simple/goal','/odom')):
        raise RuntimeError('UNEXPECTED_PUBLISHER '+repr((topic,nodes)))
print(json.dumps(dict(status='STATIONARY_PREFLIGHT_PASSED',serial_owners=owners,stop_source=stop_path)))
PY
python2 -m py_compile /home/EPRobot/medical_stationary_localization_v2_20261011.py
python2 /home/EPRobot/medical_stationary_localization_v2_20261011.py
python2 /home/EPRobot/medical_stationary_localization_v2_20261011.py --offline-check
