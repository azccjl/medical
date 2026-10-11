#!/bin/bash
exec >/tmp/medical-base-stop-investigation-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
rosnode kill /base_control
sleep 3
rosnode list
python2 /home/ncut/vm_connection_check_20261009.py 'ps -eo pid,comm,args | grep -E "[m]edical_art_racecar_heading_v2_candidate|[e]probot_joy_node|[m]ove_base"; true'
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >/tmp/medical-base-stopped-view-20261011.json
