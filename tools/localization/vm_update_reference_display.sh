#!/bin/bash
# Execute in VMware Ubuntu. Only the display node is replaced.
exec >/tmp/medical-reference-display-update.txt 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
assets=/home/ncut/medical_localization_assets_20261011
python2 - <<'PY'
# -*- coding: utf-8 -*-
import json,os,rosgraph,urllib2
path='/home/ncut/medical_localization_assets_20261011/reference-display-before-retry2.json'
if os.path.exists(path):raise RuntimeError('OUTPUT_EXISTS')
state=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
assert state.get('pose',{}).get('fresh'), 'STALE_POSE'
assert state.get('uncertainty'), 'MISSING_AMCL_RESULT'
assert state['status'].startswith(u'位置估计更新中'), state['status']
master=rosgraph.Master('/medical_display_preflight')
pubs=dict(master.getSystemState()[0])
for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
    assert not pubs.get(topic),(topic,pubs.get(topic))
with open(path,'w') as handle:json.dump(dict(state=state,publishers=pubs),handle,indent=2)
print('PRECHECK_FRESH_INITIALIZED_NO_CONTROL_PUBLISHERS')
PY
python2 -m py_compile /tmp/site_localization_view_reference.py
cp /tmp/site_localization_view_reference.py /home/ncut/medical_ws/src/medical_robot/scripts/site_localization_view.py
rosnode kill /medical_site_localization_view
sleep 2
nohup python2 /home/ncut/medical_ws/src/medical_robot/scripts/site_localization_view.py \
  --raw-map "$assets/map.yaml" --structured-map "$assets/site-geometry-candidate.yaml" \
  --annotations "$assets/site-annotations.json" --port 8080 --resume-initialized \
  >/tmp/medical-reference-display.log 2>&1 < /dev/null &
echo DISPLAY_PID=$!
sleep 3
python2 - <<'PY'
# -*- coding: utf-8 -*-
import json,os,time,math,urllib2,rospy,rosgraph
from std_srvs.srv import Empty
path='/home/ncut/medical_localization_assets_20261011/reference-display-after-retry2.json'
if os.path.exists(path):raise RuntimeError('OUTPUT_EXISTS')
rospy.init_node('medical_reference_display_verify',anonymous=True)
master=rosgraph.Master(rospy.get_name())
def check():
    pubs=dict(master.getSystemState()[0])
    for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
        assert not pubs.get(topic),(topic,pubs.get(topic))
    assert pubs.get('/map')==['/medical_map_server'],pubs.get('/map')
    assert pubs.get('/amcl_pose')==['/amcl'],pubs.get('/amcl_pose')
    return pubs
checks=[]
rospy.wait_for_service('/request_nomotion_update',timeout=5)
for attempt in range(3):
    checks.append(check())
    rospy.ServiceProxy('/request_nomotion_update',Empty)()
    time.sleep(1)
    state=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
    if state.get('uncertainty'):break
p=state['pose'];l=state['laser_pose']
assert p['fresh'] and l['fresh'], 'STALE_REFERENCE_DATA'
assert state.get('uncertainty'),'NO_AMCL_RESULT'
distance=math.hypot(l['x']-p['x'],l['y']-p['y'])
forward=(l['x']-p['x'])*math.cos(p['yaw'])+(l['y']-p['y'])*math.sin(p['yaw'])
left=-(l['x']-p['x'])*math.sin(p['yaw'])+(l['y']-p['y'])*math.cos(p['yaw'])
assert abs(distance-.135)<.01 and abs(forward-.135)<.01 and abs(left)<.01,(distance,forward,left)
checks.append(check())
with open(path,'w') as handle:json.dump(dict(state=state,offset_m=dict(distance=distance,forward=forward,left=left),control_checks=checks),handle,indent=2)
print('REFERENCE_OFFSET_METRES',distance,forward,left)
print('DISPLAY_UPDATED_NO_MOTION_COMMANDS',state['status'].encode('utf-8'))
PY
