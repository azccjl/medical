#!/bin/bash
exec >/tmp/medical-readonly-control-history-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
# Sends a read-only command through SSH; does not copy any file to the car.
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_motion_history_command.sh >/tmp/medical-robot-motion-history-20261011.log
python2 /tmp/readonly_control_watch.py
