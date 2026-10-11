#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Reset AMCL after an operator repositions the car; no velocity publisher."""
from __future__ import print_function
import argparse
import ctypes
import json
import math
import os
import threading
import time
import urllib2
import rospy
import rosgraph
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Empty
from medical_stop_window import StopWindow

class Timespec(ctypes.Structure):
    _fields_ = [('seconds', ctypes.c_long), ('nanoseconds', ctypes.c_long)]

libc = ctypes.CDLL('librt.so.1', use_errno=True)
def monotonic():
    value = Timespec()
    if libc.clock_gettime(1, ctypes.byref(value)) != 0:
        raise RuntimeError('MONOTONIC_CLOCK_FAILED')
    return value.seconds + value.nanoseconds / 1e9

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.path.exists(args.output):
        raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
    fd = os.open(args.output + '.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)  # Preserve the lock as evidence and to prevent automatic repetition.
    report = dict(status='REFUSED', odom=[], amcl=[], scans=[], controls=[],
                  seed=dict(x=-.15144, y=-.026359, yaw=0.,
                            front_offset_m=.245, approximate=True,
                            reason='Operator confirmed front on board-one black line, heading right'))
    guard = threading.RLock()
    stop = StopWindow()
    rospy.init_node('medical_stationary_site_reinitialize', anonymous=True)
    master = rosgraph.Master(rospy.get_name())
    def control_check():
        pubs = dict(master.getSystemState()[0])
        types = dict(master.getTopicTypes())
        active = {}
        for name, nodes in pubs.items():
            if name == '/medical_stationary_localization/feedback' and nodes == ['/medical_stationary_localization']:
                continue  # This zero-only candidate publishes measured feedback, not commands.
            if nodes and (types.get(name) in ('geometry_msgs/Twist', 'geometry_msgs/TwistStamped',
                                             'ackermann_msgs/AckermannDrive', 'ackermann_msgs/AckermannDriveStamped')
                          or name in ('/move_base/goal', '/move_base_simple/goal')):
                active[name] = nodes
        report['controls'].append(dict(t=monotonic(), active=active))
        if active:
            raise RuntimeError('ACTIVE_CONTROL_PUBLISHERS %r' % active)
    def odom(msg):
        row = dict(t=monotonic(), stamp=msg.header.stamp.to_sec(),
                   vx=msg.twist.twist.linear.x, vy=msg.twist.twist.linear.y,
                   wz=msg.twist.twist.angular.z,
                   x=msg.pose.pose.position.x, y=msg.pose.pose.position.y,
                   ros_age=(rospy.Time.now()-msg.header.stamp).to_sec())
        with guard:
            report['odom'].append(row)
            stop.feed(row)
    def amcl(msg):
        p = msg.pose.pose
        with guard:
            report['amcl'].append(dict(stamp=msg.header.stamp.to_sec(),
                x=p.position.x, y=p.position.y,
                q=[p.orientation.x,p.orientation.y,p.orientation.z,p.orientation.w],
                covariance=list(msg.pose.covariance)))
    def scan(msg):
        with guard:
            report['scans'].append(dict(stamp=msg.header.stamp.to_sec(), frame=msg.header.frame_id,
                angle_min=msg.angle_min, angle_increment=msg.angle_increment,
                ranges=[r if not math.isnan(r) and not math.isinf(r) else None for r in msg.ranges]))
            report['scans'] = report['scans'][-20:]
    subs = [rospy.Subscriber('/odom', Odometry, odom, queue_size=500),
            rospy.Subscriber('/amcl_pose', PoseWithCovarianceStamped, amcl, queue_size=20),
            rospy.Subscriber('/medical_slam_scan', LaserScan, scan, queue_size=20)]
    pub = None
    try:
        deadline = monotonic()+30
        while monotonic()<deadline:
            control_check()
            with guard:
                evidence = stop.evidence(monotonic())
                fresh = report['odom'] and abs(report['odom'][-1]['ros_age']) <= .2
            if evidence['passed'] and fresh:
                break
            rospy.sleep(.1)
        else:
            raise RuntimeError('STRICT_STOP_WINDOW_NOT_AVAILABLE')
        report['baseline_stop'] = evidence
        pub = rospy.Publisher('/initialpose', PoseWithCovarianceStamped, queue_size=1, latch=True)
        deadline = monotonic()+5
        expected_subscribers = dict(master.getSystemState()[1]).get('/initialpose', [])
        if '/amcl' not in expected_subscribers:
            raise RuntimeError('AMCL_NOT_SUBSCRIBED_TO_INITIALPOSE')
        while pub.get_num_connections()<len(expected_subscribers) and monotonic()<deadline:
            rospy.sleep(.05)
        if pub.get_num_connections()<len(expected_subscribers):
            raise RuntimeError('INITIALPOSE_CONNECTIONS_INCOMPLETE')
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'; msg.header.stamp = rospy.Time.now()
        msg.pose.pose.position.x = report['seed']['x']
        msg.pose.pose.position.y = report['seed']['y']
        msg.pose.pose.orientation.w = 1.
        msg.pose.covariance[0] = msg.pose.covariance[7] = .09
        msg.pose.covariance[35] = math.radians(20)**2
        control_check(); pub.publish(msg)
        report['initialpose_ros_stamp'] = msg.header.stamp.to_sec()
        print('INITIALPOSE_ONLY_NO_VELOCITY')
        rospy.wait_for_service('/request_nomotion_update', timeout=5)
        for unused in range(20):
            control_check()
            rospy.ServiceProxy('/request_nomotion_update', Empty)()
            rospy.sleep(.8)
        deadline = monotonic()+30
        while monotonic()<deadline:
            control_check()
            with guard:
                report['final_stop'] = stop.evidence(monotonic())
            if report['final_stop']['passed']:
                break
            rospy.sleep(.1)
        else:
            raise RuntimeError('STRICT_FINAL_STOP_WINDOW_NOT_AVAILABLE')
        report['view'] = json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state', timeout=5))
        control_check()
        if not report['view'].get('pose', {}).get('fresh'):
            raise RuntimeError('STALE_LOCALIZATION')
        if not report['amcl']:
            raise RuntimeError('NO_AMCL_RESULT')
        after = [row for row in report['amcl'] if row['stamp']>=report['initialpose_ros_stamp']]
        report['reset_result_near_seed'] = bool(after and
            math.hypot(after[-1]['x']-report['seed']['x'], after[-1]['y']-report['seed']['y'])<.6)
        if not report['reset_result_near_seed']:
            raise RuntimeError('INITIALPOSE_NOT_CONFIRMED_NEAR_SEED')
        report['status'] = 'REINITIALIZED_NO_MOTION'
    except Exception as exc:
        report['error'] = str(exc)
        report['status'] = 'INCOMPLETE'
    finally:
        if pub is not None: pub.unregister()
        for sub in subs: sub.unregister()
        with guard:
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as handle:
                json.dump(report, handle, indent=2, allow_nan=False)
        rospy.signal_shutdown('stationary reinitialization capture complete')
    print(report['status'], report.get('error'), 'AMCL', len(report['amcl']))
    return 0 if report['status']=='REINITIALIZED_NO_MOTION' else 1

if __name__ == '__main__':
    raise SystemExit(main())
