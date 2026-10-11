#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
if [ -f /home/EPRobot/robot_ws/devel_medical_astra/setup.bash ]; then source /home/EPRobot/robot_ws/devel_medical_astra/setup.bash; fi
python2 - <<'PY'
from __future__ import print_function
import json,os,glob,subprocess,rosgraph,rospy
master=rosgraph.Master('/medical_camera_inventory_readonly')
print('ROS_TOPICS',json.dumps(master.getTopicTypes()))
print('ROS_PUBLISHERS',json.dumps(master.getSystemState()[0]))
for key in ('astra_camera','web_video_server','cv_bridge','camera_calibration','image_proc','aruco_ros','apriltag_ros'):
 try:print('PACKAGE',key,subprocess.check_output(['rospack','find',key]).strip())
 except subprocess.CalledProcessError:print('PACKAGE_UNAVAILABLE',key)
procs=[]
for pid in os.listdir('/proc'):
 if not pid.isdigit():continue
 try:args=open('/proc/'+pid+'/cmdline','rb').read().split('\0');cmd=' '.join(args)
 except IOError:continue
 if any(os.path.basename(x) in ('nodelet','uvc_camera','web_video_server') for x in args[:2]) or ('astra.launch' in args and 'astra_camera' in args):procs.append([pid,cmd])
print('CAMERA_PROCESSES',json.dumps(procs))
for f in ('/home/EPRobot/robot_ws/src/ros_astra_camera/launch/astra.launch','/home/EPRobot/medical_robot_env.sh'):
 if os.path.exists(f):print('SOURCE_FILE',f,open(f).read())
rospy.init_node('medical_camera_inventory_readonly',anonymous=True)
from sensor_msgs.msg import CameraInfo
for topic,kind in master.getTopicTypes():
 if kind=='sensor_msgs/CameraInfo':
  try:
   m=rospy.wait_for_message(topic,CameraInfo,timeout=3)
   print('CAMERA_INFO',json.dumps(dict(topic=topic,width=m.width,height=m.height,K=list(m.K),D=list(m.D),P=list(m.P),frame=m.header.frame_id)))
  except rospy.ROSException as e:print('CAMERA_INFO_UNAVAILABLE',topic,str(e))
print('BASE_SERIAL_INVENTORY')
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
 if not pid.isdigit():continue
 for f in glob.glob('/proc/'+pid+'/fd/*'):
  try:
   if os.readlink(f)==d:owners.append(pid)
  except OSError:pass
print('BASE_SERIAL_OWNERS',owners)
assert not owners,owners
print('CAMERA_READONLY_INVENTORY_COMPLETE_NO_MOTION')
PY
