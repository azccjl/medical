#!/bin/bash
set -e
mkdir -p /home/ncut/medical_camera_assist1_20261011
if [ -f /home/ncut/medical_camera_assist1_20261011/vision-web.pid ] && kill -0 "$(cat /home/ncut/medical_camera_assist1_20261011/vision-web.pid)" 2>/dev/null; then
  echo "VISION_WEB_ALREADY_RUNNING pid=$(cat /home/ncut/medical_camera_assist1_20261011/vision-web.pid)"
  exit 0
fi
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
unset ROS_HOSTNAME
export ROS_IP=$(python2 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('192.168.12.1',11311)); print(s.getsockname()[0]); s.close()")
export PYTHONUNBUFFERED=1
export MEDICAL_VISION_PORT=8085
nohup python2 /home/ncut/medical_camera_assist1_20261011/camera_vision_web_20261011.py \
  >> /home/ncut/medical_camera_assist1_20261011/vision-web.log 2>&1 < /dev/null &
echo $! > /home/ncut/medical_camera_assist1_20261011/vision-web.pid
sleep 3
kill -0 "$(cat /home/ncut/medical_camera_assist1_20261011/vision-web.pid)"
echo "VISION_WEB_STARTED pid=$(cat /home/ncut/medical_camera_assist1_20261011/vision-web.pid) url=http://$ROS_IP:8085/"
