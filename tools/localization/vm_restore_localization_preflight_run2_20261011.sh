#!/bin/bash
exec >/tmp/medical-localization-restore-preflight-run2-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_verify_staged_files_20261011.sh
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import json,rospy,rosgraph,urllib2
from sensor_msgs.msg import LaserScan
rospy.init_node('medical_restore_readonly_preflight',anonymous=True)
master=rosgraph.Master(rospy.get_name())
pubs=dict(master.getSystemState()[0]);types=dict(master.getTopicTypes())
for topic,nodes in pubs.items():
    if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped') or topic in ('/move_base/goal','/move_base_simple/goal','/odom')):
        raise RuntimeError('UNEXPECTED_PUBLISHER '+repr((topic,nodes)))
nodes=rospy.get_master().getSystemState()[2]
for required in ['/amcl','/medical_map_server','/medical_site_localization_view']:
    assert any(required in entry[1] for group in nodes for entry in group), ('REQUIRED_NODE_ABSENT',required)
print('MAP_LOCALIZATION_VIEW_READY_NO_CONTROL_PUBLISHERS')
for unused in range(5):
    m=rospy.wait_for_message('/medical_slam_scan',LaserScan,timeout=5)
    age=(rospy.Time.now()-m.header.stamp).to_sec()
    print('SCAN_AGE',age,'FRAME',m.header.frame_id)
    assert -.02<=age<=.3, ('STALE_SCAN',age)
    assert m.header.frame_id=='base_laser_link'
d=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
assert d['annotations']['schema_version']==2
print('CURRENT_DISPLAY_STATUS',d['status'].encode('utf-8'))
print('RESTORE_PREFLIGHT_PASSED_NO_HARDWARE_STARTED')
PY
