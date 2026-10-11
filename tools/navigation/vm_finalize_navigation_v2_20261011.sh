#!/bin/bash
# Run inside VMware Ubuntu. Builds/tests only; never starts physical base/gate.
exec >/tmp/medical-navigation-final-v2-20261011.log 2>&1
set -e
stage=/home/ncut/medical_navigation_prepare_v2_20261011
test ! -e "$stage"
mkdir -m 700 "$stage"
python2 - "$stage" <<'PY'
import zipfile,sys,os,json,hashlib
stage=sys.argv[1]
with zipfile.ZipFile('/home/ncut/navigation-staging-v2-20261011.zip') as z:z.extractall(stage)
manifest=json.load(open(stage+'/manifest.json'))
for name,sha in manifest['files'].items():assert hashlib.sha256(open(stage+'/'+name,'rb').read()).hexdigest()==sha,name
print('BUNDLE_MANIFEST_VERIFIED',len(manifest['files']))
PY
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:11312
export ROS_IP=127.0.0.1
unset ROS_HOSTNAME
chmod +x "$stage"/src/medical_robot/scripts/*.py "$stage"/src/medical_robot/scripts/*.sh
cd "$stage"
catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python2 >"$stage/build.log" 2>&1
catkin_make install >"$stage/install.log" 2>&1
source "$stage/devel/setup.bash"
python2 "$stage/review_navigation_offline.py" --scripts "$stage/src/medical_robot/scripts" \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output "$stage/offline-review-ubuntu-v2.json"
python2 "$stage/review_route_runner_mock.py" --scripts "$stage/src/medical_robot/scripts" \
  --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output-dir "$stage/mock-ubuntu-v2"
for root in src/medical_robot/scripts install/lib/medical_robot; do
  python2 "$stage/$root/route_workbench.py" --help >/dev/null
  python2 "$stage/$root/route_action_runner.py" --help >/dev/null
  python2 "$stage/$root/navigation_audited_base.py" --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --map-sha UNACCEPTED
done
rosrun medical_robot route_workbench.py --help >/dev/null
rosrun medical_robot route_action_runner.py --help >/dev/null
echo CATKIN_BUILD_INSTALL_AND_RUNTIME_IMPORTS_PASSED
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_prepare_v2_readonly.sh"
for name in navigation_audited_base.py navigation_policy.py route_geometry.py; do
  python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/src/medical_robot/scripts/$name" "/home/EPRobot/medical_navigation_prepare_v2_20261011/$name"
done
python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" /home/EPRobot/medical_navigation_prepare_v2_20261011/site_acceptance.template.json
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_verify_v2_staged.sh"
# Replace only the passive old route workbench after verifying it has no task.
python2 - <<'PY'
import urllib2,json,os,signal
url='http://192.168.12.71:8083'
c=json.load(urllib2.urlopen(url+'/api/config',timeout=3));assert c['motion_enabled'] is False
try:j=json.load(urllib2.urlopen(url+'/api/job',timeout=3));assert j['job'] is None
except urllib2.HTTPError as e:
    if e.code!=404:raise
matched=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    try:args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError:continue
    if '/home/ncut/medical_navigation_prepare_20261011/src/medical_robot/scripts/route_workbench.py' in args:
        assert '--enable-navigation' not in args
        matched.append(int(pid))
assert len(matched)==1,matched
os.kill(matched[0],signal.SIGTERM)
print('REPLACED_OLD_PASSIVE_ROUTE_WORKBENCH_ONLY',matched)
PY
mkdir -m 700 "$stage/routes"
nohup python2 "$stage/src/medical_robot/scripts/route_workbench.py" --bind 192.168.12.71 --port 8083 \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --annotations "$stage/maps/structured/site-annotations.json" --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --output-dir "$stage/routes" >"$stage/workbench.log" 2>&1 </dev/null &
echo PASSIVE_WORKBENCH_PID=$!
sleep 2
python2 "$stage/review_workbench_http.py" --url http://192.168.12.71:8083 --output "$stage/http-review-v2.json"
# Synthetic planning checks have a separate loopback-only master.
test -z "$(lsof -tiTCP:11312 -sTCP:LISTEN)"
roscore -p 11312 >"$stage/isolated-master.log" 2>&1 &
master_pid=$!;fixture_pid=0;map_pid=0;nav_pid=0
cleanup() {
  for pid in "$nav_pid" "$map_pid" "$fixture_pid" "$master_pid"; do
    if [ "$pid" -gt 0 ]; then kill -INT "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT
sleep 3
python2 "$stage/isolated_navigation_fixture.py" >"$stage/isolated-fixture.log" 2>&1 &
fixture_pid=$!
rosrun map_server map_server "$stage/maps/raw/map.yaml" >"$stage/isolated-map.log" 2>&1 &
map_pid=$!
roslaunch medical_robot navigation_field_staging.launch >"$stage/isolated-navigation.log" 2>&1 &
nav_pid=$!
sleep 5
python2 "$stage/isolated_navigation_review.py" --output "$stage/isolated-review-v2.json"
cleanup
trap - EXIT
for pid in "$nav_pid" "$map_pid" "$fixture_pid" "$master_pid"; do wait "$pid" || true; done
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_verify_v2_staged.sh"
echo SOFTWARE_STAGE_V2_COMPLETE_NO_PHYSICAL_MOTION
