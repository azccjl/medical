#!/bin/bash
exec >/tmp/medical-dashboard-inventory-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py 'hostname; date -u; fuser /dev/EPRobot_base 2>/dev/null || true; ps -eo pid,args | grep -E "[m]edical_ground_straight|[m]edical_stationary|[a]rt_racecar" || true'
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import rospy,rosgraph,math,json
from sensor_msgs.msg import LaserScan
rospy.init_node('medical_dashboard_readonly_inventory',anonymous=True)
m=rosgraph.Master(rospy.get_name())
print('GRAPH',json.dumps(m.getSystemState()[0]))
for topic in ['/scan','/medical_slam_scan']:
    rows=[]
    for unused in range(10):
        s=rospy.wait_for_message(topic,LaserScan,timeout=4)
        f=[]
        for i,r in enumerate(s.ranges):
            a=math.atan2(math.sin(s.angle_min+i*s.angle_increment),math.cos(s.angle_min+i*s.angle_increment))
            if abs(a)<=math.radians(20)+1e-6:f.append((a,not math.isnan(r) and not math.isinf(r) and s.range_min<=r<=s.range_max))
        f.sort();run=mx=0
        for a,v in f:
            run=0 if v else run+1;mx=max(mx,run)
        rows.append(dict(age=(rospy.Time.now()-s.header.stamp).to_sec(),unknown=[round(math.degrees(a),2) for a,v in f if not v],gap_deg=mx*abs(s.angle_increment)*180/math.pi,edge=[f[0][1],f[-1][1]],valid_pct=100.*sum(v for a,v in f)/len(f)))
    print('SCAN_COMPARISON',topic,json.dumps(rows))
PY
