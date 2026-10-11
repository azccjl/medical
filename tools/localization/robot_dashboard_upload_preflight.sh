#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
import os,glob,rosgraph,json
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
print('SERIAL_OWNERS',json.dumps(owners));assert not owners
m=rosgraph.Master('/medical_dashboard_upload_preflight');types=dict(m.getTopicTypes())
for topic,nodes in m.getSystemState()[0]:
    if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped') or topic in ('/odom','/move_base/goal','/move_base_simple/goal')):
        raise RuntimeError('UNEXPECTED_PUBLISHER_'+topic)
print('NO_CONTROL_OR_ODOM_PUBLISHERS')
PY
test ! -e /home/EPRobot/medical_dashboard_20261011
mkdir -m 700 /home/EPRobot/medical_dashboard_20261011
