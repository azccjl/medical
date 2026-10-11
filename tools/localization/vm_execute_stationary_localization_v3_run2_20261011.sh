#!/bin/bash
exec >/tmp/medical-stationary-localization-execute-v3-run2-20261011.log 2>&1
set -e
assets=/home/ncut/medical_localization_assets_20261011
test ! -e "$assets/zero-only-site-reinitialized-v3-run2-20261011.json"
test ! -e "$assets/zero-only-site-reinitialized-v3-run2-20261011.json.lock"
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_stationary_localization_preflight_v3_20261011.sh
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import rospy
from sensor_msgs.msg import LaserScan
rospy.init_node('medical_zero_only_scan_preflight',anonymous=True)
m=rospy.wait_for_message('/medical_slam_scan',LaserScan,timeout=5)
age=(rospy.Time.now()-m.header.stamp).to_sec()
assert -.02 <= age <= .3, ('STALE_SCAN',age)
print('SCAN_FRESH_BEFORE_ZERO_ONLY_START',m.header.frame_id,age)
PY
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_execute_stationary_localization_v3_run2_20261011.sh >/tmp/medical-stationary-localization-hardware-v3-run2-20261011.log 2>&1 &
task_helper_pid=$!
task_capture_status=0
python2 /tmp/reinitialize_zero_only_site_20261011.py --output "$assets/zero-only-site-reinitialized-v3-run2-20261011.json" || task_capture_status=$?
echo ZERO_ONLY_REINITIALIZE_EXIT=$task_capture_status
if [ "$task_capture_status" -eq 0 ]; then
  curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >"$assets/zero-only-site-live-v3-run2-20261011.json"
  python2 - <<'PY'
from __future__ import print_function
import json
d=json.load(open('/home/ncut/medical_localization_assets_20261011/zero-only-site-live-v3-run2-20261011.json'))
print('ZERO_ONLY_LIVE_STATE',json.dumps({k:d.get(k) for k in ('status','pose','uncertainty','laser_pose')}))
PY
fi
task_hardware_status=0
wait "$task_helper_pid" || task_hardware_status=$?
cat /tmp/medical-stationary-localization-hardware-v3-run2-20261011.log
echo ZERO_ONLY_HARDWARE_EXIT=$task_hardware_status
for name in medical-stationary-localization-v3-run2-run-20261011.log medical-stationary-localization-v3-run2-audit-20261011.jsonl medical-stationary-localization-v3-run2-audit-20261011.jsonl.lock; do
  python2 /home/ncut/vm_connection_check_20261009.py --download "/home/EPRobot/$name" "$assets/$name"
done
echo STATIONARY_STAGE_DOWNLOAD_COMPLETE
if [ "$task_hardware_status" -ne 0 ]; then exit "$task_hardware_status"; fi
exit "$task_capture_status"
