#!/bin/bash
set +e
pidfile=/home/ncut/medical_camera_assist1_20261011/vision-web.pid
python2 - <<'PY'
import os,signal
f='/home/ncut/medical_camera_assist1_20261011/vision-web.pid'
if os.path.isfile(f):
 p=open(f).read().strip()
 try:a=open('/proc/'+p+'/cmdline','rb').read().split('\0')
 except IOError:a=[]
 if len(a)>1 and a[1]=='/home/ncut/medical_camera_assist1_20261011/camera_vision_web_20261011.py':
  os.kill(int(p),signal.SIGTERM)
PY
echo "VISION_WEB_STOPPED"
