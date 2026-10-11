#!/bin/bash
exec >/tmp/medical-field-static-preflight-run1-20261011.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
date -u -Ins
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_field_static_preflight_20261011.sh
python2 - <<'PY'
from __future__ import print_function
import json,urllib2,rospy,rosgraph,hashlib,os
from sensor_msgs.msg import LaserScan
c=json.load(urllib2.urlopen('http://192.168.12.71:8083/api/config',timeout=3))
j=json.load(urllib2.urlopen('http://192.168.12.71:8083/api/job',timeout=3))
d=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
assert not c['motion_enabled'] and j['job'] is None and not d['busy'] and d['run'] is None
v=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=3))
print('OLD_DISPLAY_STATE',json.dumps({k:v.get(k) for k in ('status','pose','uncertainty')},ensure_ascii=True))
rospy.init_node('medical_field_static_preflight',anonymous=True)
master=rosgraph.Master(rospy.get_name());print('ROS_NODES',json.dumps(master.getSystemState()))
assert not rospy.get_param('/use_sim_time',False)
for unused in range(3):
    scan=rospy.wait_for_message('/medical_slam_scan',LaserScan,timeout=5)
    age=(rospy.Time.now()-scan.header.stamp).to_sec()
    assert -.02<=age<=.30,('SCAN_CLOCK_OR_FRESHNESS',age)
    print('SCAN_FRESH',scan.header.frame_id,len(scan.ranges),age)
assert hashlib.sha256(open('/tmp/reinitialize_zero_only_site_v2_20261011.py','rb').read()).hexdigest()==hashlib.sha256(open('/home/ncut/medical_navigation_field_static_run1_20261011/reinitialize_zero_only_site_v2_20261011.py','rb').read()).hexdigest()
assert '/amcl' in dict(master.getSystemState()[1]).get('/initialpose',[])
print('FIELD_STATIC_PREFLIGHT_PASSED_NO_HARDWARE_STARTED')
PY
