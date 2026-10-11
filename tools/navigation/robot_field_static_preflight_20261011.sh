#!/bin/bash
# Read-only preflight. Does not open serial or start hardware.
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
from __future__ import print_function
import os,glob,hashlib,json,rosgraph,time,imp,sys
sys.path.insert(0,'/home/EPRobot/robot_ws/src/eprobot_start/script')
handle,stop_path,description=imp.find_module('medical_stop_window')
if handle is not None:handle.close()
checks={
'/home/EPRobot/medical_stationary_localization_v3_20261011.py':'aa06ade75f042131310bf2bad910070728472d68c486ebd3592e206a31b6384d',
'/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py':'d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1',
stop_path:'15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43'}
for path,digest in checks.items():assert hashlib.sha256(open(path,'rb').read()).hexdigest()==digest,path
device=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:owners.append(pid)
        except OSError:pass
assert not owners,owners
master=rosgraph.Master('/medical_field_static_readonly');types=dict(master.getTopicTypes())
pubs=dict(master.getSystemState()[0]);active={}
for topic,nodes in pubs.items():
    if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped',
        'ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped','move_base_msgs/MoveBaseActionGoal') or topic=='/odom'):
        active[topic]=nodes
assert not active,active
print(json.dumps(dict(status='ROBOT_FIELD_STATIC_PREFLIGHT_PASSED',wall=time.time(),serial_owners=owners,
                      source_hashes=checks,publishers=pubs,use_sim_time=master.getParam('/use_sim_time') if master.hasParam('/use_sim_time') else False)))
PY
