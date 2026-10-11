#!/bin/bash
exec >/tmp/medical-navigation-preview-start-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 - <<'PY'
import rosgraph
pubs,subs,services=rosgraph.Master('/medical_preview_preflight').getSystemState()
for topic,nodes in pubs:
    if topic in ['/medical_ground_cmd_vel','/cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
        assert not nodes,(topic,nodes)
assert not dict(subs).get('/medical_nav_preview_cmd_vel'),'PREVIEW_BRIDGE_EXISTS'
assert not any('/medical_navigation_preview' in n for t,n in pubs),'PREVIEW_ALREADY_RUNNING'
PY
nohup roslaunch medical_robot navigation_plan_preview.launch >/tmp/medical-navigation-preview-20261011.log 2>&1 < /dev/null &
echo PREVIEW_PID=$!
sleep 8
python2 /tmp/capture_navigation_preview.py
rostopic info /medical_ground_cmd_vel
rostopic info /medical_nav_preview_cmd_vel
