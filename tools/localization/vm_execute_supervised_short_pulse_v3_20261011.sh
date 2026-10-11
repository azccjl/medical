#!/bin/bash
exec >/tmp/medical-supervised-short-pulse-execute-v3-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_bench_pulse_heading_v8_logclassification.py /home/EPRobot/medical_bench_pulse_heading_v8_logclassification.py
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_supervised_short_pulse_v3_20261011.py /home/EPRobot/medical_supervised_short_pulse_v3_20261011.py
task_status=0
python2 /home/ncut/vm_connection_check_20261009.py 'source /home/EPRobot/medical_robot_env.sh; python2 /home/EPRobot/medical_supervised_short_pulse_v3_20261011.py --execute --clear-floor --power-stop-confirmed' || task_status=$?
echo PULSE_EXECUTE_EXIT=$task_status
python2 /home/ncut/vm_connection_check_20261009.py --download /home/EPRobot/medical-supervised-short-pulse-v3-20261011.json /home/ncut/medical_localization_assets_20261011/medical-supervised-short-pulse-v3-20261011.json
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
rostopic info /medical_ground_cmd_vel
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >/tmp/medical-short-pulse-final-view-v3-20261011.json
exit "$task_status"
