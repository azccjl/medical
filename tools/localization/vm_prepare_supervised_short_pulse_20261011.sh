#!/bin/bash
exec >/tmp/medical-short-pulse-prepare-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_supervised_short_pulse_20261011.py /home/EPRobot/medical_supervised_short_pulse_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py 'source /home/EPRobot/medical_robot_env.sh; sha256sum /home/EPRobot/medical_bench_pulse_heading_v6_logrotation.py /home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py; python2 -m py_compile /home/EPRobot/medical_supervised_short_pulse_20261011.py; rostopic info /medical_ground_cmd_vel'
