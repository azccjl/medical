#!/bin/bash
# Final passive UI update; does not contact/start robot base.
exec >/tmp/medical-navigation-passive-${1:-final}-update.log 2>&1
set -e
stage=/home/ncut/medical_navigation_prepare_v2_20261011
incoming=/home/ncut/navigation_passive_final_update
run_suffix=${1:-final}
case "$run_suffix" in final|release) ;; *) exit 2 ;; esac
python2 - <<'PY'
import urllib2,json
c=json.load(urllib2.urlopen('http://192.168.12.71:8083/api/config',timeout=3))
j=json.load(urllib2.urlopen('http://192.168.12.71:8083/api/job',timeout=3))
assert c['motion_enabled'] is False and j['job'] is None
PY
for name in route_workbench navigation_command_gate route_action_runner; do
  test ! -e "$stage/src/medical_robot/scripts/$name.pre-$run_suffix.py"
  cp "$stage/src/medical_robot/scripts/$name.py" "$stage/src/medical_robot/scripts/$name.pre-$run_suffix.py"
  cp "$incoming/$name.py" "$stage/src/medical_robot/scripts/$name.py"
done
cp "$incoming/review_navigation_offline.py" "$stage/review_navigation_offline.$run_suffix.py"
cp "$incoming/review_route_runner_mock.py" "$stage/review_route_runner_mock.$run_suffix.py"
source /opt/ros/melodic/setup.bash
source "$stage/devel/setup.bash"
cd "$stage"
catkin_make install >"$stage/install-$run_suffix.log" 2>&1
python2 "$stage/review_navigation_offline.$run_suffix.py" --scripts "$stage/src/medical_robot/scripts" \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output "$stage/offline-review-ubuntu-$run_suffix.json"
python2 "$stage/review_route_runner_mock.$run_suffix.py" --scripts "$stage/install/lib/medical_robot" \
  --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output-dir "$stage/mock-install-$run_suffix"
python2 - <<'PY'
import os,signal
matched=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    try:args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError:continue
    if '/home/ncut/medical_navigation_prepare_v2_20261011/src/medical_robot/scripts/route_workbench.py' in args:
        assert '--enable-navigation' not in args;matched.append(int(pid))
assert len(matched)==1,matched
os.kill(matched[0],signal.SIGTERM)
PY
nohup python2 "$stage/src/medical_robot/scripts/route_workbench.py" --bind 192.168.12.71 --port 8083 \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --annotations "$stage/maps/structured/site-annotations.json" --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --output-dir "$stage/routes" >"$stage/workbench-$run_suffix.log" 2>&1 </dev/null &
sleep 2
python2 "$stage/review_workbench_http.py" --url http://192.168.12.71:8083 --output "$stage/http-review-$run_suffix.json"
echo FINAL_PASSIVE_UI_REVIEW_COMPLETE
