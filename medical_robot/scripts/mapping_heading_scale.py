#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Mapping-only odometry branch; no control, hardware, or original TF writes."""
from __future__ import print_function
import math
import copy
import threading


def finite(v):
    return not math.isnan(v) and not math.isinf(v)


class MappingPoseScale(object):
    def __init__(self, scale=1.0):
        if not finite(scale) or not .9 <= scale <= 1.1:
            raise ValueError('mapping heading scale must be finite in 0.9..1.1')
        self.scale = scale
        self.previous = None
        self.x = self.y = self.yaw = 0.0

    def update(self, stamp, x, y, yaw):
        if not all(finite(v) for v in (stamp, x, y, yaw)) or stamp <= 0:
            raise ValueError('invalid source pose')
        if self.previous is not None:
            pt, px, py, pa = self.previous
            if not 0 < stamp-pt <= .2:
                raise ValueError('source odometry time discontinuity')
            da = math.atan2(math.sin(yaw-pa), math.cos(yaw-pa))
            oldmid = pa + da/2
            newmid = self.yaw + self.scale*da/2
            angle = newmid-oldmid
            dx, dy = x-px, y-py
            self.x += math.cos(angle)*dx-math.sin(angle)*dy
            self.y += math.sin(angle)*dx+math.cos(angle)*dy
            self.yaw += self.scale*da
        self.previous = stamp, x, y, yaw
        return self.x, self.y, self.yaw


def main():
    import rospy
    import tf2_ros
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from geometry_msgs.msg import TransformStamped
    rospy.init_node('medical_mapping_heading_scale')
    state = MappingPoseScale(float(rospy.get_param('~heading_scale', 1.0)))
    odom_in = rospy.get_param('~odom_input', '/odom')
    scan_in = rospy.get_param('~scan_input', '/medical_slam_scan')
    odom_out = '/medical_mapping_odom'
    scan_out = '/medical_mapping_scan'
    if rospy.resolve_name(odom_in) == odom_out or rospy.resolve_name(scan_in) == scan_out:
        raise ValueError('input/output feedback loop')
    odom_frame = 'medical_mapping_odom'
    base_frame = 'medical_mapping_base'
    laser_frame = 'medical_mapping_laser'
    odom_pub = rospy.Publisher(odom_out, Odometry, queue_size=20)
    scan_pub = rospy.Publisher(scan_out, LaserScan, queue_size=5)
    broadcaster = tf2_ros.TransformBroadcaster()
    static = tf2_ros.StaticTransformBroadcaster()
    tr = TransformStamped()
    tr.header.stamp = rospy.Time.now()
    tr.header.frame_id, tr.child_frame_id = base_frame, laser_frame
    # Existing measured/install profile. Check physical mounting before reuse.
    tr.transform.translation.x = .135
    tr.transform.translation.z = .135
    tr.transform.rotation.w = 1.
    static.sendTransform(tr)
    buffer = tf2_ros.Buffer(rospy.Duration(30))
    listener = tf2_ros.TransformListener(buffer)
    stats = {'odom_received':0,'scan_received':0,'scan_published':0,'scan_no_tf':0,'scan_invalid':0}
    wall_wait = threading.Event()
    def odom_callback(msg):
        try:
            stats['odom_received'] += 1
            if msg.header.frame_id != 'odom' or msg.child_frame_id != 'base_footprint':
                raise ValueError('source odometry frame changed')
            q = msg.pose.pose.orientation
            if not all(finite(v) for v in (q.x,q.y,q.z,q.w)) or abs(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w-1) > .02:
                raise ValueError('invalid source quaternion')
            a = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
            p = msg.pose.pose.position
            x,y,a = state.update(msg.header.stamp.to_sec(),p.x,p.y,a)
            out = copy.deepcopy(msg)
            out.header.frame_id, out.child_frame_id = odom_frame, base_frame
            out.pose.pose.position.x, out.pose.pose.position.y = x,y
            out.pose.pose.position.z = 0.
            out.pose.pose.orientation.x = out.pose.pose.orientation.y = 0.
            out.pose.pose.orientation.z, out.pose.pose.orientation.w = math.sin(a/2),math.cos(a/2)
            out.twist.twist.angular.z *= state.scale
            # This candidate does not claim calibrated covariance.
            odom_pub.publish(out)
            tr = TransformStamped()
            tr.header = copy.deepcopy(out.header)
            tr.child_frame_id = base_frame
            tr.transform.translation.x, tr.transform.translation.y = x,y
            tr.transform.rotation = copy.deepcopy(out.pose.pose.orientation)
            broadcaster.sendTransform(tr)
        except ValueError as e:
            rospy.logerr('MAPPING_POSE_REFUSED: %s',str(e))
            rospy.signal_shutdown('invalid mapping-only source; no control output')
    def scan_callback(msg):
        stats['scan_received'] += 1
        if msg.header.frame_id != 'base_laser_link' or msg.header.stamp.to_sec() <= 0:
            stats['scan_invalid'] += 1
            rospy.logerr_throttle(2.,'Mapping scan source frame/time invalid')
            return
        ready = False
        # Wait for the odom subscriber/listener to catch up, at most 200ms wall
        # time. Bounded iterations also work when a replay's /clock freezes.
        for unused in range(40):
            if rospy.is_shutdown():return
            if buffer.can_transform(odom_frame,base_frame,msg.header.stamp,rospy.Duration(0)):
                ready = True
                break
            wall_wait.wait(.005)
        if not ready:
            stats['scan_no_tf'] += 1
            rospy.logwarn_throttle(2.,'Waiting for mapping-only TF at scan time')
            return
        out = copy.deepcopy(msg)
        out.header.frame_id = laser_frame
        scan_pub.publish(out)
        stats['scan_published'] += 1
    # Separate subscriber callback threads; state is updated only by odom callback.
    rospy.Subscriber(odom_in,Odometry,odom_callback,queue_size=200)
    rospy.Subscriber(scan_in,LaserScan,scan_callback,queue_size=20)
    rospy.loginfo('MAPPING_ONLY_SCALE_READY scale=%.9f; original odom/control unchanged',state.scale)
    rospy.on_shutdown(lambda: rospy.loginfo('MAPPING_BRANCH_STATS %s',str(stats)))
    rospy.spin()


if __name__ == '__main__':
    main()
