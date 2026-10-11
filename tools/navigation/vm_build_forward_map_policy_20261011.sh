#!/bin/bash
exec >/tmp/medical-forward-map-build1-20261011.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
stage=/home/ncut/medical_navigation_forward_map_build1_20261011
test ! -e "$stage"
mkdir -m 700 "$stage"
python2 - "$stage" <<'PYCODE'
import zipfile,sys,json,hashlib
s=sys.argv[1]
with zipfile.ZipFile('/home/ncut/forward-map-catkin-build1-20261011.zip') as z:z.extractall(s)
for n,h in json.load(open(s+'/manifest.json')).items():assert hashlib.sha256(open(s+'/'+n,'rb').read()).hexdigest()==h,n
print('CATKIN_BUNDLE_SOURCE_MANIFEST_PASSED')
PYCODE
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11312 ROS_IP=127.0.0.1
unset ROS_HOSTNAME
cd "$stage"
chmod +x src/medical_robot/scripts/*.py
catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python2 >"$stage/build.log" 2>&1
catkin_make install >"$stage/install.log" 2>&1
source "$stage/install/setup.bash"
python2 "$stage/review_navigation_offline.py" --scripts "$stage/src/medical_robot/scripts" --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output "$stage/navigation-software-review-ubuntu.json"
rosrun medical_robot navigation_command_gate.py --help >"$stage/installed-gate-help.log"
roslaunch medical_robot navigation_field_staging.launch forward_scan:=true --dump-params >"$stage/forward-launch-params.yaml"
python2 - "$stage" <<'PYCODE'
import sys,yaml,subprocess,json,os
s=sys.argv[1];p=yaml.safe_load(open(s+'/forward-launch-params.yaml'))
for name in ('global_costmap','local_costmap'):
 assert p['/medical_field_move_base/'+name+'/obstacle_layer/laser_scan_sensor/topic']=='/medical_navigation_forward_scan'
 assert p['/medical_field_move_base/'+name+'/obstacle_layer/laser_scan_sensor/inf_is_valid'] is False
out=subprocess.Popen(['python2',s+'/install/lib/medical_robot/navigation_command_gate.py','--acceptance',s+'/src/medical_robot/config/navigation/site_acceptance.template.json','--map-sha','UNACCEPTED','--enable-output','--site-ready-confirmed','--clearance-policy','forward-map','--audit',s+'/never-created-audit.jsonl'],stdout=subprocess.PIPE)
data=out.communicate()[0];assert out.returncode==2,data
assert 'FORWARD_MAP_FIELD_POLICY_NOT_ACCEPTED' in json.loads(data)['errors']
assert not os.path.exists(s+'/never-created-audit.jsonl')
print('INSTALLED_GATE_FORWARD_POLICY_AND_LAUNCH_IMPORTS_PASSED_NO_ROS_NODE_STARTED')
PYCODE
echo FORWARD_MAP_CATKIN_BUILD_INSTALL_AND_DRY_LAUNCH_PASSED_NO_MOTION
