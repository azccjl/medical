#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
stage=/home/EPRobot/medical_camera_assist1_20261011
python2 - <<'PY'
import rosgraph
nodes=rosgraph.Master('/medical_camera_bridge_preflight').getSystemState()[0]
if any('/medical_camera_readonly_bridge' in owners for topic,owners in nodes):
 raise SystemExit('Refusing duplicate camera bridge')
PY
nohup python2 "$stage/camera_readonly_bridge.py" >> "$stage/bridge.log" 2>&1 < /dev/null &
echo $! > "$stage/bridge.pid"
sleep 3
kill -0 "$(cat "$stage/bridge.pid")"
echo CAMERA_BRIDGE_STARTED_NO_BASE_NO_TF_NO_INITIALPOSE
