#!/bin/bash
exec >/tmp/medical-site-final-stop-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 /tmp/capture_site_final_stop.py
