#!/bin/bash
exec >/tmp/medical-plan-preview-finish-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
rosnode kill /medical_navigation_preview
sleep 2
rostopic info /medical_ground_cmd_vel
rosnode list
python2 /tmp/medical_supervised_short_pulse_20261011.py
