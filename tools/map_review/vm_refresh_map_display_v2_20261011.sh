#!/bin/bash
exec >/tmp/medical-map-display-v2-refresh-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
task_assets=/home/ncut/medical_map_display_v2_20261011
python2 - "$task_assets" <<'PY'
from __future__ import print_function
import os,signal,sys,time,py_compile,rosgraph
root=sys.argv[1]
py_compile.compile(root+'/site_localization_view_v2.py',doraise=True)
pubs=dict(rosgraph.Master('/medical_display_refresh_preflight').getSystemState()[0])
for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
    assert not pubs.get(topic), ('CONTROL_ACTIVE',topic)
targets=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try: args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError: continue
    if root+'/site_localization_view_v2.py' in args and '--port' in args and args[args.index('--port')+1]=='8080':
        targets.append(int(pid))
assert len(targets)==1, ('EXPECTED_SINGLE_DISPLAY_V2',targets)
pid=targets[0]
os.kill(pid,signal.SIGINT)
for i in range(50):
    if not os.path.exists('/proc/'+str(pid)): break
    time.sleep(.1)
else: raise RuntimeError('Display did not exit')
print('ONLY_DISPLAY_V2_RESTARTED',pid)
PY
nohup python2 "$task_assets/site_localization_view_v2.py" \
  --raw-map /home/ncut/medical_localization_assets_20261011/map.yaml \
  --structured-map "$task_assets/site-geometry-candidate.yaml" \
  --annotations "$task_assets/site-annotations.json" \
  --port 8080 --resume-initialized \
  >"$task_assets/display-refresh.log" 2>&1 </dev/null &
echo DISPLAY_V2_PID=$!
sleep 3
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >"$task_assets/display-state-final.json"
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_map_display_20261011.sh
echo DISPLAY_REFRESH_COMPLETE_NO_MOTION
