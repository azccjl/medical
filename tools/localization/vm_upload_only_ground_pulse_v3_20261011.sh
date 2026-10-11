#!/bin/bash
exec >/tmp/medical-upload-only-ground-v3-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import json,hashlib,rosgraph
p='/tmp/medical_ground_straight_pulse_v3_20261011.py'
sha=hashlib.sha256(open(p,'rb').read()).hexdigest()
assert sha=='c997fda7951424d7c29053b530809beff8cb6b658abdf7664b55807686dbd71c'
review=json.load(open('/home/ncut/medical_localization_assets_20261011/ground-pulse-v3-offline-review-20261011.json'))
assert review['status']=='OFFLINE_REVIEW_PASSED' and review['source_sha256']==sha
master=rosgraph.Master('/medical_upload_only_preflight')
kinds=dict(master.getTopicTypes())
control_types=('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped')
for topic,nodes in master.getSystemState()[0]:
    if nodes and (kinds.get(topic) in control_types or topic in ('/move_base/goal','/move_base_simple/goal')):
        raise RuntimeError('CONTROL_PUBLISHER_PRESENT_'+topic)
print('NO_CONTROL_PUBLISHERS_BEFORE_UPLOAD')
PY
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_verify_staged_files_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_ground_straight_pulse_v3_20261011.py /home/EPRobot/medical_ground_straight_pulse_v3_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_staged_files_20261011.json /home/EPRobot/medical_staged_files_20261011.json
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_verify_staged_files_20261011.sh
python2 - <<'PY'
from __future__ import print_function
import rosgraph
master=rosgraph.Master('/medical_upload_only_postflight')
kinds=dict(master.getTopicTypes())
control_types=('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped')
for topic,nodes in master.getSystemState()[0]:
    if nodes and (kinds.get(topic) in control_types or topic in ('/move_base/goal','/move_base_simple/goal')):
        raise RuntimeError('CONTROL_PUBLISHER_PRESENT_'+topic)
print('NO_CONTROL_PUBLISHERS_AFTER_UPLOAD')
PY
echo UPLOAD_ONLY_COMPLETE_NO_BASE_START_NO_MOTION
