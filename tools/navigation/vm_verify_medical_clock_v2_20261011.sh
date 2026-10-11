#!/bin/bash
exec >/tmp/medical-clock-verification-v2-20261011.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
systemctl is-active chrony
chronyc tracking
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_verify_v2_20261011.sh
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 /home/ncut/medical_clock_sync_20261011/vm_verify_medical_clock_v2_20261011.py \
  --output /home/ncut/medical_clock_sync_20261011/verification-v2.json --port 18081
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_field_static_preflight_20261011.sh
