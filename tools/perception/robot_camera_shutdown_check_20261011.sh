#!/bin/bash
set -e
python2 - <<'PY'
import os,glob,json
camera=[]; owners=[]
device=os.path.realpath('/dev/EPRobot_base')
for p in os.listdir('/proc'):
 if not p.isdigit():continue
 try:a=open('/proc/'+p+'/cmdline','rb').read().split('\0')
 except IOError:continue
 if any(x in ('__name:=medical_astra_nodelet_manager','__name:=driver') for x in a) and any('medical_astra' in x for x in a):camera.append([p,a])
 if len(a)>1 and a[1]=='/home/EPRobot/medical_camera_assist1_20261011/camera_readonly_bridge.py':camera.append([p,a])
 if '/opt/ros/melodic/bin/roslaunch' in a and 'camera:=medical_astra' in a:camera.append([p,a])
 for f in glob.glob('/proc/'+p+'/fd/*'):
  try:
   if os.readlink(f)==device:owners.append(p)
  except OSError:pass
print(json.dumps(dict(camera_processes=camera,base_serial_owners=owners,motion_sent=False)))
assert not camera and not owners
print('CAMERA_SHUTDOWN_CONFIRMED_BASE_CLOSED')
PY
