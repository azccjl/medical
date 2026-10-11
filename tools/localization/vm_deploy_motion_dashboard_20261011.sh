#!/bin/bash
# Execute only in VMware Ubuntu. Uploads files and starts passive web service.
exec >/tmp/medical-dashboard-deploy-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
stage=/home/ncut/medical_motion_dashboard_20261011
python2 - <<'PY'
import hashlib,json,os
root='/home/ncut/medical_motion_dashboard_20261011'
for n,h in json.load(open(root+'/dashboard-manifest.json')).items():
    assert hashlib.sha256(open(root+'/'+n,'rb').read()).hexdigest()==h
print('STAGED_HASHES_VERIFIED')
PY
python2 "$stage/medical_ground_straight_pulse_v5_20261011.py" --offline-check
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_dashboard_upload_preflight.sh"
python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/medical_ground_straight_pulse_v5_20261011.py" /home/EPRobot/medical_dashboard_20261011/medical_ground_straight_pulse_v5_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/medical_scan_report_20261011.py" /home/EPRobot/medical_dashboard_20261011/medical_scan_report_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/dashboard-manifest.json" /home/EPRobot/medical_dashboard_20261011/dashboard-manifest.json
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_dashboard_upload_postflight.sh"
nohup python2 "$stage/medical_motion_dashboard_20261011.py" --bind 192.168.12.71 --port 8082 --output-dir "$stage/evidence" >"$stage/server.log" 2>&1 </dev/null &
echo PASSIVE_DASHBOARD_PID=$!
echo FILE_UPLOAD_ONLY_NO_BASE_START_NO_MOTION
