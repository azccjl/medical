#!/bin/bash
exec >/tmp/medical-map-display-inspection-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import os, json, rosgraph
master=rosgraph.Master('/medical_map_display_inspect')
pubs=dict(master.getSystemState()[0])
for topic in ['/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/move_base/goal','/move_base_simple/goal']:
    print('CONTROL_PUBLISHERS',topic,pubs.get(topic,[]))
    assert not pubs.get(topic), ('CONTROL_ACTIVE',topic)
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try:
        args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
        if any(arg.endswith('/site_localization_view.py') for arg in args):
            print('DISPLAY_PROCESS',pid,json.dumps(args))
    except IOError: pass
PY
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state >/tmp/medical-map-display-before-20261011.json
python2 - <<'PY'
from __future__ import print_function
import json
d=json.load(open('/tmp/medical-map-display-before-20261011.json'))
print('VIEW_STATUS',d.get('status').encode('utf-8'))
print('MAP_METADATA',json.dumps({k:{p:v[p] for p in ['width','height','origin','resolution']} for k,v in d['maps'].items()}))
print('ANNOTATIONS_SCHEMA',d['annotations'].get('schema_version',1))
PY
echo DISPLAY_INSPECTION_ONLY_COMPLETE
