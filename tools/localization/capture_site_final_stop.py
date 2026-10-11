#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only final stop check after reinitialization; no publishers."""
from __future__ import print_function
import os, json, threading, urllib2
import rospy, rosgraph
from nav_msgs.msg import Odometry
from medical_stop_window import StopWindow
from reinitialize_stationary_site import monotonic

output='/home/ncut/medical_localization_assets_20261011/site-final-stop-after-reset-20261011.json'
if os.path.exists(output):raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
os.close(os.open(output+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
rospy.init_node('medical_site_final_stop_readonly',anonymous=True)
master=rosgraph.Master(rospy.get_name());guard=threading.RLock();stop=StopWindow();rows=[];checks=[]
def callback(msg):
    row=dict(t=monotonic(),stamp=msg.header.stamp.to_sec(),
             vx=msg.twist.twist.linear.x,vy=msg.twist.twist.linear.y,wz=msg.twist.twist.angular.z,
             ros_age=(rospy.Time.now()-msg.header.stamp).to_sec())
    with guard:rows.append(row);stop.feed(row)
sub=rospy.Subscriber('/odom',Odometry,callback,queue_size=500)
report=dict(status='INCOMPLETE')
try:
    deadline=monotonic()+30
    while monotonic()<deadline:
        pubs=dict(master.getSystemState()[0]);types=dict(master.getTopicTypes())
        active={t:n for t,n in pubs.items() if n and
            (types.get(t) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped')
             or t in ('/move_base/goal','/move_base_simple/goal')) and
            not(t=='/feedback_vel' and n==['/base_control'])}
        checks.append(dict(t=monotonic(),active=active))
        if active:raise RuntimeError('CONTROL_PUBLISHERS_APPEARED')
        with guard:
            e=stop.evidence(monotonic());fresh=bool(rows and abs(rows[-1]['ros_age'])<=.2)
        if e['passed'] and fresh:
            report['status']='STRICT_STOP_CONFIRMED';break
        rospy.sleep(.1)
    report['evidence']=e
    report['view']=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
except Exception as exc:report['error']=str(exc)
finally:
    sub.unregister()
    with guard:report['odom']=rows;report['controls']=checks
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle:
        json.dump(report,handle,indent=2,allow_nan=False)
print(report['status'],report.get('error'))
raise SystemExit(0 if report['status']=='STRICT_STOP_CONFIRMED' else 1)
