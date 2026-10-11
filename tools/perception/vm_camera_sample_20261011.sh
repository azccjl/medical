#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/medical_camera_assist1_20261011/robot_camera_sample_20261011.sh > /home/ncut/medical_camera_assist1_20261011/sample.out 2>&1
