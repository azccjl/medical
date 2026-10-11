#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""One supervised short straight motion; records evidence and always stops."""
from __future__ import print_function
import os, json, time, math, threading, urllib2
import rospy, rosgraph
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan

OUT = '/home/ncut/medical_localization_assets_20261011/short-motion-localization-20261011.json'
LOCK = OUT + '.lock'
TOPIC = '/medical_ground_cmd_vel'
SPEED = 0.05
SECONDS = 4.0
STATIONARY_LIMIT = 0.002

if os.path.exists(OUT) or os.path.exists(LOCK):
    raise RuntimeError('PRESERVE_EXISTING_OUTPUT_OR_LOCK')
fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.close(fd)

lock = threading.RLock()
rows, amcl, scans, commands, errors = [], [], [], [], []
latest_scan = [None]
active = [True]
pub = [None]

def finite(x):
    return not math.isnan(x) and not math.isinf(x)

def graph_state(master):
    return dict(master.getSystemState()[0])

def check_control_graph(master, own=False):
    pubs = graph_state(master)
    foreign = list(pubs.get(TOPIC, []))
    allowed = [rospy.get_name()] if own else []
    if sorted(foreign) != sorted(allowed):
        raise RuntimeError('UNEXPECTED_CONTROL_PUBLISHERS %r' % (foreign,))
    for t in ['/cmd_vel', '/medical_nav_cmd_vel', '/move_base/goal', '/move_base_simple/goal']:
        if pubs.get(t):
            raise RuntimeError('UNEXPECTED_CONTROL_TOPIC %s %r' % (t, pubs[t]))

def send(x):
    msg = Twist(); msg.linear.x = x
    with lock:
        if pub[0] is not None:
            pub[0].publish(msg)
            commands.append(dict(wall=time.time(), x=x))

def odom_cb(msg):
    with lock:
        if not active[0]: return
        p = msg.pose.pose.position; q = msg.pose.pose.orientation
        rows.append(dict(wall=time.time(), stamp=msg.header.stamp.to_sec(),
                         x=p.x, y=p.y, vx=msg.twist.twist.linear.x,
                         vy=msg.twist.twist.linear.y, wz=msg.twist.twist.angular.z,
                         q=[q.x,q.y,q.z,q.w]))

def amcl_cb(msg):
    with lock:
        if active[0]:
            p = msg.pose.pose.position; q = msg.pose.pose.orientation
            amcl.append(dict(wall=time.time(), stamp=msg.header.stamp.to_sec(),
                             x=p.x, y=p.y, q=[q.x,q.y,q.z,q.w],
                             covariance=list(msg.pose.covariance)))

def scan_cb(msg):
    with lock:
        if not active[0]: return
        latest_scan[0] = (time.time(), msg)
        if not scans or time.time()-scans[-1]['wall'] >= .18:
            scans.append(dict(wall=time.time(), stamp=msg.header.stamp.to_sec(),
                              frame=msg.header.frame_id, angle_min=msg.angle_min,
                              angle_increment=msg.angle_increment,
                              ranges=[r if finite(r) else None for r in msg.ranges]))

def corridor():
    with lock: item = latest_scan[0]
    if item is None or time.time()-item[0] > .5: raise RuntimeError('SCAN_STALE')
    msg = item[1]
    if msg.header.frame_id != 'base_laser_link': raise RuntimeError('SCAN_FRAME')
    xs = []
    for i, r in enumerate(msg.ranges):
        if r is None: continue
        if r < msg.range_min or r > msg.range_max: continue
        a = msg.angle_min + i*msg.angle_increment
        x = .135 + r*math.cos(a); y = r*math.sin(a)
        if x > .245 and abs(y) <= .21: xs.append(x)
    if len(xs) < 3 or min(xs) < .75:
        raise RuntimeError('FRONT_CORRIDOR_NOT_CLEAR %.3f' % (min(xs) if xs else -1))
    return dict(min_x_from_base_m=min(xs), returns=len(xs))

def stationary_for(seconds, deadline):
    started = None
    while time.time() < deadline:
        with lock: last = rows[-1] if rows else None
        if last and abs(last['vx']) <= STATIONARY_LIMIT and abs(last['vy']) <= STATIONARY_LIMIT and abs(last['wz']) <= STATIONARY_LIMIT:
            if started is None: started = time.time()
            if time.time()-started >= seconds: return dict(passed=True, duration=time.time()-started, last=last)
        else:
            started = None
        time.sleep(.05)
    raise RuntimeError('STRICT_STATIONARY_WINDOW_TIMEOUT')

report = dict(status='REFUSED', speed_m_s=SPEED, command_seconds=SECONDS,
              stationary_limit=STATIONARY_LIMIT, events=[], errors=errors)
rospy.init_node('medical_short_motion_localization_20261011', anonymous=True, disable_signals=True)
master = rosgraph.Master(rospy.get_name())
sub_odom = rospy.Subscriber('/odom', Odometry, odom_cb, queue_size=1000)
sub_amcl = rospy.Subscriber('/amcl_pose', PoseWithCovarianceStamped, amcl_cb, queue_size=20)
sub_scan = rospy.Subscriber('/medical_slam_scan', LaserScan, scan_cb, queue_size=20)
try:
    rospy.sleep(.8)
    check_control_graph(master)
    report['baseline_stationary'] = stationary_for(2.0, time.time()+12)
    report['initial_corridor'] = corridor()
    pub[0] = rospy.Publisher(TOPIC, Twist, queue_size=1, latch=False)
    deadline = time.time()+5
    while pub[0].get_num_connections() < 1 and time.time() < deadline: rospy.sleep(.05)
    if pub[0].get_num_connections() != 1: raise RuntimeError('BASE_CONTROL_CONNECTION_NOT_UNIQUE')
    check_control_graph(master, own=True)
    report['events'].append(dict(name='STRAIGHT_BEGIN', wall=time.time(), speed=SPEED))
    begin = time.time()
    while time.time()-begin < SECONDS:
        check_control_graph(master, own=True); corridor(); send(SPEED); rospy.sleep(.05)
    report['events'].append(dict(name='STRAIGHT_END_SEND_STOP', wall=time.time()))
    for unused in range(12): send(0.0); rospy.sleep(.05)
    report['post_stop_stationary'] = stationary_for(4.0, time.time()+15)
    report['status'] = 'STOPPED_STATIC_WINDOW_PASSED'
except Exception as exc:
    errors.append(str(exc)); report['status'] = 'ABORTED'
finally:
    active[0] = False
    for unused in range(12):
        try: send(0.0); rospy.sleep(.03)
        except Exception: break
    if pub[0] is not None: pub[0].unregister()
    sub_odom.unregister(); sub_amcl.unregister(); sub_scan.unregister()
    with lock:
        report['commands'] = commands; report['odom'] = rows; report['amcl'] = amcl; report['scans'] = scans
    report['ended_wall'] = time.time()
    with open(OUT, 'w') as handle: json.dump(report, handle, indent=2, allow_nan=False)
    try: os.unlink(LOCK)
    except OSError: pass
    rospy.signal_shutdown('single supervised short motion complete')
print(json.dumps(dict(status=report['status'], errors=errors, odom=len(rows), amcl=len(amcl), scans=len(scans))))
