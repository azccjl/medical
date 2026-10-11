#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
helper=/home/ncut/vm_connection_check_20261009.py
stage=/home/ncut/medical_camera_assist1_20261011
python2 "$helper" --upload "$stage/camera_readonly_bridge.py" /home/EPRobot/medical_camera_assist1_20261011/camera_readonly_bridge.py
python2 "$helper" --command-file "$stage/robot_start_camera_bridge_20261011.sh"
