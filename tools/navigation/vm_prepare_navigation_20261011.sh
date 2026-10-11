#!/bin/bash
# VMware Ubuntu only. No base startup or physical movement.
exec >/tmp/medical-navigation-prepare-20261011.log 2>&1
set -e
stage=/home/ncut/medical_navigation_prepare_20261011
python2 "$stage/review_navigation_offline.py" --scripts "$stage/src/medical_robot/scripts" \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" --output "$stage/offline-review-ubuntu.json"
source /opt/ros/melodic/setup.bash
export ROS_PACKAGE_PATH="$stage/src:$ROS_PACKAGE_PATH"
for pkg in amcl move_base teb_local_planner navfn costmap_2d actionlib move_base_msgs map_server; do
  echo "DEPENDENCY $pkg $(rospack find "$pkg")"
done
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_prepare_readonly.sh"
for name in navigation_audited_base.py navigation_policy.py route_geometry.py; do
  python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/src/medical_robot/scripts/$name" "/home/EPRobot/medical_navigation_prepare_20261011/$name"
done
python2 /home/ncut/vm_connection_check_20261009.py --upload "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" /home/EPRobot/medical_navigation_prepare_20261011/site_acceptance.template.json
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_verify_staged.sh"
nohup python2 "$stage/src/medical_robot/scripts/route_workbench.py" --bind 192.168.12.71 --port 8083 \
  --raw-map "$stage/maps/raw/map.yaml" --structured-map "$stage/maps/structured/site-geometry-candidate.yaml" \
  --annotations "$stage/maps/structured/site-annotations.json" --acceptance "$stage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --output-dir "$stage/routes" >"$stage/workbench.log" 2>&1 </dev/null &
echo PASSIVE_ROUTE_WORKBENCH_PID=$!
export ROS_MASTER_URI=http://127.0.0.1:11312
export ROS_IP=127.0.0.1
roscore -p 11312 >"$stage/isolated-master.log" 2>&1 &
master_pid=$!
fixture_pid=0;map_pid=0;nav_pid=0
cleanup() {
  for p in "$nav_pid" "$map_pid" "$fixture_pid" "$master_pid"; do
    if [ "$p" -gt 0 ]; then kill -INT "$p" 2>/dev/null || true; fi
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
python2 "$stage/isolated_navigation_review.py" --output "$stage/isolated-review.json"
echo PRE_NAVIGATION_PREPARATION_COMPLETE_NO_ROBOT_MOTION
