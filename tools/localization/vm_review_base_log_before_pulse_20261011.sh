#!/bin/bash
exec >/tmp/medical-base-log-before-pulse-review-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py 'source /home/EPRobot/medical_robot_env.sh; date -Is; grep -n -C 4 -E "MEDICAL_SERIAL_WRITE_FAILED|Traceback|Invalid Index" /home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063/base_control-2.log; tail -n 25 /home/EPRobot/.ros/log/80c853f4-c529-11f1-9368-88a29e1b8063/base_control-2.log; rostopic info /medical_ground_cmd_vel'
