#!/bin/bash
set -e
python2 - <<'PY'
import os, signal, time
stopped=[]
target='/home/ncut/medical_camera_assist1_20261011/camera_vision_web_20261011.py'
for p in os.listdir('/proc'):
 if not p.isdigit(): continue
 try: args=open('/proc/'+p+'/cmdline','rb').read().split('\0')
 except IOError: continue
 if len(args)>1 and args[1]==target:
  os.kill(int(p),signal.SIGTERM)
  stopped.append(p)
  print('STOPPED_VISION_ONLY',p)
time.sleep(2)
for p in stopped:
 try: args=open('/proc/'+p+'/cmdline','rb').read().split('\0')
 except IOError: continue
 if len(args)>1 and args[1]==target:
  os.kill(int(p),signal.SIGKILL)
  print('FORCED_VISION_ONLY',p)
time.sleep(1)
PY
bash /home/ncut/medical_camera_assist1_20261011/vm_start_camera_vision_web_20261011.sh
