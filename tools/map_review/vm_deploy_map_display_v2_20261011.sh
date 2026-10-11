#!/bin/bash
exec >/tmp/medical-map-display-v2-deploy-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
task_assets=/home/ncut/medical_map_display_v2_20261011
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_map_display_20261011.sh
python2 - "$task_assets" <<'PY'
from __future__ import print_function
import hashlib, json, os, signal, sys, time, rosgraph, py_compile, yaml
root=sys.argv[1]
py_compile.compile(root+'/site_localization_view_v2.py',doraise=True)
sha=lambda path:hashlib.sha256(open(path,'rb').read()).hexdigest()
raw_dir='/home/ncut/medical_localization_assets_20261011'
raw_image=yaml.safe_load(open(raw_dir+'/map.yaml'))['image']
assert sha(os.path.join(raw_dir,raw_image))=='e301b8e583d1e019f88d42bebba92234fba7c3af62a274a46a72904b7f5be88c'
assert sha(root+'/site-geometry-candidate.pgm')==sha('/home/ncut/medical_localization_assets_20261011/site-geometry-candidate.pgm')=='93903a951828d76c4f9e763cab1549c9a31ae0749569b0b5afdc80333af64d41'
annotations=json.load(open(root+'/site-annotations.json'))
assert annotations['schema_version']==2
assert set(annotations['windows'])==set('1234ABC')
pubs=dict(rosgraph.Master('/medical_display_update_preflight').getSystemState()[0])
for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
    assert not pubs.get(topic), ('CONTROL_ACTIVE',topic)
targets=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try: args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError: continue
    if '/home/ncut/medical_ws/src/medical_robot/scripts/site_localization_view.py' in args and '--port' in args:
        if args[args.index('--port')+1]=='8080':
            assert '--resume-initialized' in args
            targets.append(int(pid))
assert len(targets)==1, ('EXPECTED_SINGLE_DISPLAY_PROCESS',targets)
pid=targets[0]
os.kill(pid,signal.SIGINT)
for i in range(50):
    if not os.path.exists('/proc/'+str(pid)): break
    time.sleep(.1)
else: raise RuntimeError('Previous display did not exit; refusing to force-kill')
print('ONLY_DISPLAY_RESTARTED',pid)
PY
nohup python2 "$task_assets/site_localization_view_v2.py" \
  --raw-map /home/ncut/medical_localization_assets_20261011/map.yaml \
  --structured-map "$task_assets/site-geometry-candidate.yaml" \
  --annotations "$task_assets/site-annotations.json" \
  --port 8080 --resume-initialized \
  >"$task_assets/display.log" 2>&1 </dev/null &
echo DISPLAY_V2_PID=$!
sleep 3
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >"$task_assets/display-state-after.json"
python2 - "$task_assets" <<'PY'
from __future__ import print_function
import sys,json,rosgraph
d=json.load(open(sys.argv[1]+'/display-state-after.json'))
assert d['annotations']['schema_version']==2
assert d['maps']['raw']['data']==json.load(open('/tmp/medical-map-display-before-20261011.json'))['maps']['raw']['data']
print('DISPLAY_STATUS',d['status'].encode('utf-8'))
print('GEOMETRY_AND_SEMANTICS_V2_AVAILABLE')
pubs=dict(rosgraph.Master('/medical_display_update_postflight').getSystemState()[0])
for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
    assert not pubs.get(topic), ('CONTROL_ACTIVE',topic)
print('CONTROL_PUBLISHERS_EMPTY_AFTER_DISPLAY_UPDATE')
assert not any('/medical_site_localization_view' in nodes for topic,nodes in pubs.items() if topic!='/rosout'), 'VIEW_MUST_HAVE_NO_DATA_PUBLISHERS'
PY
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_map_display_20261011.sh
echo DISPLAY_UPDATE_COMPLETE_NO_MOTION
