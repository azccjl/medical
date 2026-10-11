#!/usr/bin/env python2
"""Synthetic sensors only on loopback master 11312, no serial or robot connection."""
from __future__ import print_function
import os,math,json,threading,sys
if os.environ.get('ROS_MASTER_URI')!='http://127.0.0.1:11312' or os.environ.get('ROS_IP')!='127.0.0.1':
    raise RuntimeError('ISOLATED_LOOPBACK_MASTER_REQUIRED')
import rospy,tf
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped
rospy.init_node('medical_isolated_synthetic_fixture')
bc=tf.TransformBroadcaster();odom=rospy.Publisher('/odom',Odometry,queue_size=1)
scan=rospy.Publisher('/medical_slam_scan',LaserScan,queue_size=1)
amcl=rospy.Publisher('/amcl_pose',PoseWithCovarianceStamped,queue_size=1)
rate=rospy.Rate(20)
while not rospy.is_shutdown():
    stamp=rospy.Time.now()
    bc.sendTransform((0,0,0),(0,0,0,1),stamp,'odom','map')
    bc.sendTransform((-.35,.075,0),(0,0,0,1),stamp,'base_footprint','odom')
    bc.sendTransform((.135,0,.135),(0,0,0,1),stamp,'base_laser_link','base_footprint')
    o=Odometry();o.header.frame_id='odom';o.child_frame_id='base_footprint';o.header.stamp=stamp
    o.pose.pose.position.x=-.35;o.pose.pose.position.y=.075;o.pose.pose.orientation.w=1;odom.publish(o)
    s=LaserScan();s.header.frame_id='base_laser_link';s.header.stamp=stamp;s.angle_min=-math.pi
    s.angle_increment=2*math.pi/720;s.angle_max=s.angle_min+719*s.angle_increment
    s.range_min=.10;s.range_max=100.;s.scan_time=.05;s.ranges=[float('inf')]*720;scan.publish(s)
    p=PoseWithCovarianceStamped();p.header.frame_id='map';p.header.stamp=stamp;p.pose=o.pose;amcl.publish(p)
    rate.sleep()
