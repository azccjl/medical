#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
if [ -f /home/EPRobot/robot_ws/devel_medical_astra/setup.bash ]; then source /home/EPRobot/robot_ws/devel_medical_astra/setup.bash; fi
mkdir -p /home/EPRobot/medical_camera_assist1_20261011
log=/home/EPRobot/medical_camera_assist1_20261011/astra-rgb.log
pidfile=/home/EPRobot/medical_camera_assist1_20261011/astra-rgb.launch.pid

python2 - <<'PY'
import rosgraph
state=rosgraph.Master('/medical_astra_start_preflight').getSystemState()
owners=set(n for group in state for topic,nodes in group for n in nodes)
if any(n.startswith('/medical_astra/') for n in owners):
 raise SystemExit('Camera namespace already active; reuse it rather than starting a duplicate')
PY

echo "CAMERA_START $(date -Is)" >> "$log"
nohup roslaunch --screen astra_camera astra.launch \
  camera:=medical_astra \
  depth_registration:=false \
  rgb_processing:=true \
  depth_processing:=false \
  depth_registered_processing:=false \
  hw_registered_processing:=false \
  sw_registered_processing:=false \
  publish_tf:=false \
  respawn:=false >> "$log" 2>&1 &
pid=$!
echo "$pid" > "$pidfile"
echo "CAMERA_LAUNCH_STARTED pid=$pid"
sleep 8
if ! kill -0 "$pid" 2>/dev/null; then
  echo "CAMERA_LAUNCH_EXITED"
  tail -n 80 "$log"
  exit 2
fi
echo "CAMERA_LAUNCH_ALIVE pid=$pid"
rostopic list | grep -E '^/medical_astra/rgb/(image_raw|camera_info)$' || true
timeout 5s rostopic hz -w 5 /medical_astra/rgb/image_raw 2>&1 | tail -n 8 || true
echo "CAMERA_START_READONLY_NO_MOTION"
