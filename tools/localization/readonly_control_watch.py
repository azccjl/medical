#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Passive 30 second control and odometry capture. No ROS publishers."""
from __future__ import print_function
import os,json,threading,urllib2
import rospy,rosgraph
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from reinitialize_stationary_site import monotonic
output='/home/ncut/medical_localization_assets_20261011/readonly-control-watch-20261011.json'
if os.path.exists(output):raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
os.close(os.open(output+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
rospy.init_node('medical_control_watch_readonly',anonymous=True)
master=rosgraph.Master(rospy.get_name());guard=threading.RLock()
rows=[];commands=[];graphs=[];subs=[]
def odom(m):
    with guard:rows.append(dict(t=monotonic(),stamp=m.header.stamp.to_sec(),vx=m.twist.twist.linear.x,
        vy=m.twist.twist.linear.y,wz=m.twist.twist.angular.z,x=m.pose.pose.position.x,y=m.pose.pose.position.y))
def callback(topic):
    def record(m):
        with guard:commands.append(dict(t=monotonic(),topic=topic,caller=m._connection_header.get('callerid'),
            linear=[m.linear.x,m.linear.y,m.linear.z],angular=[m.angular.x,m.angular.y,m.angular.z]))
    return record
subs.append(rospy.Subscriber('/odom',Odometry,odom,queue_size=500))
for topic in ['/medical_ground_cmd_vel','/cmd_vel','/medical_nav_cmd_vel','/medical_nav_preview_cmd_vel','/joy_raw','/feedback_vel']:
    subs.append(rospy.Subscriber(topic,Twist,callback(topic),queue_size=100))
deadline=monotonic()+30
while monotonic()<deadline:
    pubs=master.getSystemState()[0]
    graphs.append(dict(t=monotonic(),publishers=pubs))
    rospy.sleep(.5)
for sub in subs:sub.unregister()
with guard:report=dict(duration_s=30,odom=rows,commands=commands,graphs=graphs,
    note='Passive observation; not an upload or a motion experiment.')
report['view']=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle:
    json.dump(report,handle,indent=2,allow_nan=False)
print('READ_ONLY_CONTROL_CAPTURE_SAVED',len(rows),len(commands))
