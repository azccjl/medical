#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
import os,signal,time,glob
targets=[]
for p in os.listdir('/proc'):
 if not p.isdigit():continue
 try:a=open('/proc/'+p+'/cmdline','rb').read().split('\0')
 except IOError:continue
 if (len(a)>1 and a[1]=='/home/EPRobot/medical_camera_assist1_20261011/camera_readonly_bridge.py') or \
    ('/opt/ros/melodic/bin/roslaunch' in a and 'astra_camera' in a and 'camera:=medical_astra' in a) or \
    ('/opt/ros/melodic/bin/rostopic' in a and 'hz' in a and '/medical_astra/rgb/image_raw' in a):
  targets.append(p);os.kill(int(p),signal.SIGINT);print('CAMERA_STOP_SENT',p)
time.sleep(20)
for p in targets:
 if os.path.exists('/proc/'+p+'/cmdline'):
  try:cmd=open('/proc/'+p+'/cmdline','rb').read()
  except IOError:continue
  if cmd:
   print('CAMERA_PROCESS_STILL_PRESENT',p,cmd.replace('\0',' '))
   raise SystemExit(2)
device=os.path.realpath('/dev/EPRobot_base');owners=[]
for p in os.listdir('/proc'):
 if not p.isdigit():continue
 for f in glob.glob('/proc/'+p+'/fd/*'):
  try:
   if os.readlink(f)==device:owners.append(p)
  except OSError:pass
print('BASE_SERIAL_OWNERS',owners)
assert not owners
print('CAMERA_STOP_COMPLETE_NO_MOTION')
PY
