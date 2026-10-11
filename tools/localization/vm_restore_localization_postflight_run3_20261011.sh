#!/bin/bash
exec >/tmp/medical-localization-restore-postflight-run3-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_verify_staged_files_20261011.sh
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
python2 - <<'PY'
from __future__ import print_function
import rosgraph,json,urllib2
master=rosgraph.Master('/medical_restore_final_readonly')
types=dict(master.getTopicTypes())
for topic,nodes in master.getSystemState()[0]:
    if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped') or topic in ('/move_base/goal','/move_base_simple/goal','/odom')):
        raise RuntimeError('UNEXPECTED_PUBLISHER '+repr((topic,nodes)))
d=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
print('FINAL_VIEW_STATUS',d['status'].encode('utf-8'))
print('FINAL_POSE',json.dumps(d.get('pose')))
print('CONTROL_AND_ODOM_PUBLISHERS_EMPTY')
print('RESTORE_FINITE_OBSERVATION_COMPLETE_BASE_CLOSED')
PY
