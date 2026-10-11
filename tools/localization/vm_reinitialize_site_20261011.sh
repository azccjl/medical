#!/bin/bash
exec >/tmp/medical-site-reinitialize-v2-20261011.log 2>&1
set -e
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 /tmp/reinitialize_stationary_site.py --output /home/ncut/medical_localization_assets_20261011/site-reinitialized-after-relocation-v2-20261011.json
rostopic info /medical_ground_cmd_vel
echo NAVIGATION_PACKAGES
for pkg in move_base teb_local_planner navfn; do rospack find "$pkg" || true; done
df -h /home/ncut
