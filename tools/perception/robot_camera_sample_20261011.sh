#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
if [ -f /home/EPRobot/robot_ws/devel_medical_astra/setup.bash ]; then source /home/EPRobot/robot_ws/devel_medical_astra/setup.bash; fi
python2 - <<'PY'
import os, rospy
from sensor_msgs.msg import CompressedImage
rospy.init_node('medical_camera_sample_readonly', anonymous=True)
topic='/medical_astra/rgb/image_raw/compressed'
m=rospy.wait_for_message(topic, CompressedImage, timeout=8.0)
out='/home/EPRobot/medical_camera_assist1_20261011/rgb-sample.jpg'
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
with os.fdopen(fd,'wb') as f:f.write(bytes(bytearray(m.data)))
print('CAMERA_SAMPLE',topic,m.header.stamp.to_sec(),m.format,len(m.data),out)
print('CAMERA_SAMPLE_READONLY_NO_MOTION')
PY
