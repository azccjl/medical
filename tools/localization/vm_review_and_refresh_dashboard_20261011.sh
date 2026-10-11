#!/bin/bash
exec >/tmp/medical-dashboard-refresh-20261011.log 2>&1
set -e
stage=/home/ncut/medical_motion_dashboard_20261011
python2 "$stage/review_motion_dashboard_offline_20261011.py" --output "$stage/dashboard-state-offline-review.json"
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 - <<'PY'
import urllib2,json
s=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
assert not s['busy'] and s['run'] is None,'DO_NOT_RESTART_DURING_RUN'
print('NO_RUN_REQUESTED_BEFORE_PASSIVE_PAGE_REFRESH')
PY
rosnode kill /medical_motion_dashboard
sleep 2
nohup python2 "$stage/medical_motion_dashboard_20261011.py" --bind 192.168.12.71 --port 8082 --output-dir "$stage/evidence" >"$stage/server-refresh.log" 2>&1 </dev/null &
echo PASSIVE_DASHBOARD_REFRESH_PID=$!
sleep 2
python2 - <<'PY'
import urllib2,json,os
s=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
p='/home/ncut/medical_motion_dashboard_20261011/dashboard-live-review.json'
with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(s,f,indent=2,ensure_ascii=True,allow_nan=False)
assert not s['busy'] and s['run'] is None
print('LIVE_PASSIVE_VIEW',json.dumps(dict(ready=s['ready'],blockers=s['blockers'],consecutive=s['consecutive'],motion_requests=0)))
PY
