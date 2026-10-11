#!/bin/bash
exec >/tmp/medical-dashboard-final-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
stage=/home/ncut/medical_motion_dashboard_20261011
python2 - <<'PY'
import urllib2,json
s=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
assert not s['busy'] and s['run'] is None
compile(open('/home/ncut/medical_motion_dashboard_20261011/medical_motion_dashboard_20261011.py').read(),'dashboard','exec')
print('FINAL_NO_RUN_AND_SOURCE_COMPILE_OK')
PY
rosnode kill /medical_motion_dashboard
sleep 2
nohup python2 "$stage/medical_motion_dashboard_20261011.py" --bind 192.168.12.71 --port 8082 --output-dir "$stage/evidence" >"$stage/server-final.log" 2>&1 </dev/null &
echo PASSIVE_SERVER_PID=$!
sleep 2
python2 - <<'PY'
import urllib2,json,os
s=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
assert not s['busy'] and s['run'] is None
with os.fdopen(os.open('/home/ncut/medical_motion_dashboard_20261011/dashboard-final-state.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(s,f,indent=2,allow_nan=False)
print('FINAL_STATE',json.dumps(dict(ready=s['ready'],blockers=s['blockers'],run=s['run'])))
PY
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_dashboard_upload_postflight.sh"
