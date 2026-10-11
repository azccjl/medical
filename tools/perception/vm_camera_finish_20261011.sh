#!/bin/bash
set +e
source /opt/ros/melodic/setup.bash
export ROS_IP=192.168.12.70 ROS_MASTER_URI=http://192.168.12.1:11311 PYTHONIOENCODING=utf-8
python2 /home/ncut/medical_camera_assist1_20261011/vm_camera_acceptance_20261011.py
capture_exit=$?
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/medical_camera_assist1_20261011/robot_stop_camera_readonly_20261011.sh
stop_exit=$?
echo CAMERA_CAPTURE_EXIT=$capture_exit CAMERA_STOP_EXIT=$stop_exit
test "$capture_exit" = 0 -a "$stop_exit" = 0
