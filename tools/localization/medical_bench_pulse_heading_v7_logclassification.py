#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""One fixed wheels-off-ground pulse; no repeat, reverse or steering commands.

Sends +0.10 m/s at 20Hz for at most 0.50s, then no commands for 1.20s.
Normal/error cleanup and a separate timed guard publish zero afterwards.
Reports odometry as evidence, not as independent physical-stop certification.
"""
from __future__ import print_function
import argparse
import ctypes
import hashlib
import io
import json
import math
import os
import signal
import socket
import sys
import threading
import time


TOPIC = '/medical_ground_cmd_vel'
DRIVER = '/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'
DRIVER_SHA = 'd671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'
REPORT = '/home/EPRobot/medical-stage2-pulse-v5-20261010.json'
SPEED, PULSE_SECONDS, SILENCE_SECONDS = 0.10, 0.50, 1.20

if hasattr(time, 'monotonic'):
    now = time.monotonic
else:
    class Timespec(ctypes.Structure):
        _fields_ = [('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long)]
    libc = ctypes.CDLL('libc.so.6', use_errno=True)
    libc.clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(Timespec)]
    libc.clock_gettime.restype = ctypes.c_int
    def now():
        stamp = Timespec()
        if libc.clock_gettime(1, ctypes.byref(stamp)) != 0:
            raise OSError(ctypes.get_errno(), 'CLOCK_MONOTONIC failed')
        return stamp.tv_sec + stamp.tv_nsec / 1e9


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def emit(event, **fields):
    fields['event'] = event
    print(json.dumps(fields, ensure_ascii=True, sort_keys=True))
    sys.stdout.flush()


def fixed_sequence(channel, clock, sleep):
    """Bounded schedule shared by real execution and non-ROS fixture checks."""
    began = clock()
    last = None
    channel.event('PULSE_BEGIN', speed=SPEED, max_seconds=PULSE_SECONDS)
    while clock() - began < PULSE_SECONDS:
        channel.check()
        # Recheck after checks: a delayed check must not prolong positive output.
        if clock() - began >= PULSE_SECONDS:
            break
        channel.send(SPEED)
        last = clock()
        sleep(0.05)
    if last is None:
        raise RuntimeError('No pulse sent; do not repeat automatically')
    ended = clock()
    channel.event('COMMAND_SILENCE_BEGIN', observation_seconds=SILENCE_SECONDS)
    while clock() - ended < SILENCE_SECONDS:
        channel.check()
        sleep(0.02)
    return {'pulse_begin': began, 'last_positive_publish': last, 'silence_begin': ended,
            'silence_end': clock()}


def driver_identity():
    with open(DRIVER, 'rb') as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    if digest != DRIVER_SHA:
        raise RuntimeError('Protected driver SHA changed; no commands sent')
    drivers, forbidden = [], []
    for pid in os.listdir('/proc'):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            with open('/proc/' + pid + '/cmdline', 'rb') as stream:
                args = [p.decode('utf-8', 'replace') for p in stream.read().split(b'\0') if p]
        except (IOError, OSError):
            continue
        names = [os.path.basename(p) for p in args]
        if any(n in names for n in ['art_racecar.py', 'eprobot_joy_node', 'huanyu_joy_node', 'move_base']):
            forbidden.append({'pid': int(pid), 'args': args})
        if DRIVER in args:
            drivers.append({'pid': int(pid), 'args': args})
    if forbidden or len(drivers) != 1:
        raise RuntimeError('Need exactly one protected base and no old/joy/navigation driver: ' +
                           json.dumps({'drivers': drivers, 'forbidden': forbidden}))
    row = drivers[0]
    logs = [a[len('__log:='):] for a in row['args'] if a.startswith('__log:=')]
    if len(logs) != 1 or not logs[0].startswith('/home/EPRobot/.ros/log/'):
        raise RuntimeError('Cannot identify current base ROS log')
    # A long-lived node rotates its log; retain startup evidence from the
    # same basename in the same ROS run, and inspect all segments for errors.
    import glob
    paths = sorted(glob.glob(logs[0] + '.[0-9]*')) + [logs[0]]
    ready = False
    for path in paths:
        with open(path, 'rb') as stream:
            known_handshakes = 0
            for line in stream:
                ready = ready or b'MEDICAL_DRIVER_READY command_timeout=0.350' in line
                if b'MEDICAL_SERIAL_WRITE_FAILED' in line or b'Invalid Index' in line:
                    raise RuntimeError('Current driver log segment contains serial/parser errors: ' + path)
                if b'Traceback' in line:
                    expected = [
                        b'Traceback (most recent call last):\n',
                        b'  File "/opt/ros/melodic/lib/python2.7/dist-packages/rospy/impl/tcpros_base.py", line 332, in _tcp_server_callback\n',
                        b'    header = read_ros_handshake_header(sock, StringIO(), buff_size)\n',
                        b'  File "/opt/ros/melodic/lib/python2.7/dist-packages/rosgraph/network.py", line 359, in read_ros_handshake_header\n',
                        b'    raise ROSHandshakeException("connection from sender terminated before handshake header received. %s bytes were received. Please check sender for additional details."%b.tell())\n',
                        b'ROSHandshakeException: connection from sender terminated before handshake header received. 0 bytes were received. Please check sender for additional details.\n']
                    observed = [line] + [stream.readline() for unused in range(5)]
                    if observed != expected:
                        raise RuntimeError('Unclassified driver traceback: ' + path)
                    known_handshakes += 1
            if known_handshakes:
                emit('CLASSIFIED_OBSERVER_HANDSHAKE_DISCONNECT', log=path, count=known_handshakes)
    data = b'MEDICAL_DRIVER_READY command_timeout=0.350' if ready else b''
    if b'MEDICAL_DRIVER_READY command_timeout=0.350' not in data:
        raise RuntimeError('Current base is not READY; no commands sent')
    if any(word in data for word in [b'MEDICAL_SERIAL_WRITE_FAILED', b'Traceback', b'Invalid Index']):
        raise RuntimeError('Current driver log contains errors; no commands sent')
    return {'pid': row['pid'], 'sha256': digest, 'log': logs[0]}


class Channel(object):
    def __init__(self, rospy, master, twist, report):
        self.rospy, self.master, self.twist, self.report = rospy, master, twist, report
        self.started = now()
        self.rows = []
        self.errors = []
        self.lock = threading.RLock()
        self.tx_lock = threading.RLock()
        self.guard_stop = threading.Event()
        self.guard_fired = threading.Event()
        self.pub = None
        self.guard = None
        self.armed = False

    def event(self, event, **fields):
        row = dict(fields, event=event, t=now()-self.started)
        self.report['events'].append(row)
        emit(event, **fields)

    def callback(self, msg):
        row = {'t': now()-self.started, 'stamp': msg.header.stamp.to_sec(),
               'vx': msg.twist.twist.linear.x, 'vy': msg.twist.twist.linear.y,
               'wz': msg.twist.twist.angular.z,
               'x': msg.pose.pose.position.x, 'y': msg.pose.pose.position.y}
        if not all(finite(row[k]) for k in row):
            self.errors.append('Non-finite odometry')
            return
        with self.lock:
            self.rows.append(row)

    def graph(self, own_publisher=False):
        pubs, subs, unused = self.master.getSystemState()
        publishers = dict(pubs).get(TOPIC, [])
        expected = [self.rospy.get_name()] if own_publisher else []
        if sorted(publishers) != sorted(expected):
            raise RuntimeError('Unexpected command publishers: ' + repr(publishers))
        if dict(pubs).get('/cmd_vel', []):
            raise RuntimeError('/cmd_vel has another publisher')
        if dict(subs).get(TOPIC, []) != ['/base_control']:
            raise RuntimeError('Bench command topic must have only /base_control subscriber')

    def check(self):
        if self.rospy.is_shutdown() or self.errors or self.guard_fired.is_set():
            raise RuntimeError('ROS/data/guard error: ' + repr(self.errors))
        with self.lock:
            last = self.rows[-1] if self.rows else None
        if last is None or now()-self.started-last['t'] > 0.25:
            raise RuntimeError('Odometry is missing/stale; stop and review')
        if self.armed and (last['vx'] < -0.03 or abs(last['vx']) > 0.25 or abs(last['wz']) > 0.40):
            raise RuntimeError('Unexpected reverse/excessive speed/yaw feedback; stop and review')

    def send(self, speed):
        with self.tx_lock:
            if speed != 0 and self.guard_fired.is_set():
                raise RuntimeError('Guard already stopped the pulse')
            msg = self.twist()
            msg.linear.x = speed
            self.pub.publish(msg)
            self.report['commands'].append({'t': now()-self.started, 'vx': speed, 'wz': 0.0})

    def guard_loop(self, deadline):
        while not self.guard_stop.wait(0.01):
            if now() >= deadline:
                with self.tx_lock:
                    if not self.report.get('zero_guard_triggered', False):
                        self.report['zero_guard_triggered'] = True
                        self.event('ZERO_GUARD_TRIGGERED')
                    self.guard_fired.set()
                    try:
                        self.send(0.0)
                    except Exception as exc:
                        self.errors.append('Guard zero failed: ' + str(exc))

    def arm(self):
        self.armed = True
        self.guard = threading.Thread(target=self.guard_loop,
                                      args=(now()+PULSE_SECONDS+SILENCE_SECONDS+0.15,))
        self.guard.daemon = True
        self.guard.start()

    def cleanup(self):
        if self.armed and self.pub is not None:
            self.guard_fired.set()  # Forbid any later positive command.
            for unused in range(12):
                try:
                    self.send(0.0)
                    self.guard_stop.set()  # First cleanup zero queued; guard no longer needed.
                except Exception as exc:
                    self.errors.append('Cleanup zero failed: ' + str(exc))
                time.sleep(0.05)
        self.guard_stop.set()
        if self.guard is not None:
            self.guard.join(0.5)
        with self.lock:
            self.report['odom'] = list(self.rows)
        self.report['cleanup_errors'] = list(self.errors)


def assess(rows, timing, origin):
    last = timing['last_positive_publish']-origin
    end = timing['silence_end']-origin
    start = timing['pulse_begin']-origin
    moving = [r for r in rows if start <= r['t'] <= last+0.30]
    tail = [r for r in rows if end-0.40 <= r['t'] <= end]
    return {'movement_seen_in_odom': any(r['vx'] > 0.03 for r in moving),
            'reverse_seen_in_odom': any(r['vx'] < -0.03 for r in moving),
            'silence_tail_samples': len(tail),
            'silence_tail_below_0_02_m_s': bool(len(tail) >= 10 and
                                               all(abs(r['vx']) <= 0.02 and abs(r['vy']) <= 0.02 for r in tail)),
            'physical_wheel_stop_requires_observer': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels-off-ground', action='store_true')
    args = parser.parse_args()
    report = {'status': 'REFUSED', 'events': [], 'commands': [], 'odom': [],
              'speed_m_s': SPEED, 'max_pulse_seconds': PULSE_SECONDS,
              'silence_seconds': SILENCE_SECONDS, 'hardware_stop_verified': False}
    channel, rospy, sub = None, None, None
    exit_code = 1
    try:
        if not args.wheels_off_ground or not sys.platform.startswith('linux') or os.path.expanduser('~') != '/home/EPRobot':
            raise RuntimeError('Run on robot as EPRobot only after stable support lifts all four wheels')
        report['driver'] = driver_identity()
        socket.setdefaulttimeout(2.0)
        import rospy as ros
        import rosgraph
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        rospy = ros
        rospy.init_node('medical_bench_pulse', anonymous=True, disable_signals=True)
        def interrupted(signum, frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        expected = {'wheelbase': 0.17, 'command_timeout': 0.35, 'base_kv': 1.0,
                    'base_kp': 1000.0, 'base_ki': 100.0, 'base_kd': 0.0, 'odom_freq': 50,
                    'cmd_vel_topic': TOPIC, 'is_send_anger': 'false', 'is_pub_odom_tf': 'true',
                    'Laser_Mode': 'Boost', 'port': '/dev/EPRobot_base', 'baudrate': 115200}
        actual = {key: rospy.get_param('/base_control/'+key) for key in expected}
        if actual != expected or rospy.get_param('/use_sim_time') is not False:
            raise RuntimeError('Actual bench parameters differ from expected: ' + repr(actual))
        report['parameters'] = actual
        report['run_id'] = rospy.get_param('/run_id')
        channel = Channel(rospy, rosgraph.Master(rospy.get_name()), Twist, report)
        channel.graph()
        sub = rospy.Subscriber('/odom', Odometry, channel.callback, queue_size=20)
        time.sleep(0.60)
        channel.check()
        with channel.lock:
            baseline = list(channel.rows)
        if len(baseline) < 15 or any(abs(r['vx']) > 0.02 or abs(r['vy']) > 0.02 for r in baseline):
            raise RuntimeError('Insufficient or nonstationary baseline; no commands sent')
        channel.pub = rospy.Publisher(TOPIC, Twist, queue_size=1, latch=False)
        deadline = now()+5.0
        while channel.pub.get_num_connections() < 1 and now() < deadline:
            channel.check()
            time.sleep(0.05)
        if channel.pub.get_num_connections() != 1:
            raise RuntimeError('Expected exactly one base connection; no commands sent')
        channel.graph(own_publisher=True)
        channel.event('BENCH_PREFLIGHT_OK', driver_pid=report['driver']['pid'])
        channel.arm()
        timing = fixed_sequence(channel, now, time.sleep)
        channel.graph(own_publisher=True)
        with channel.lock:
            report['assessment'] = assess(list(channel.rows), timing, channel.started)
        report['timing_relative'] = {key: value-channel.started for key, value in timing.items()}
        report['status'] = 'DATA_SAVED_FOR_REVIEW'
        exit_code = 0
    except (Exception, KeyboardInterrupt) as exc:
        report['error'] = str(exc) or 'Interrupted by operator'
        report['status'] = 'ABORTED' if channel and channel.armed else 'REFUSED'
        emit(report['status'], reason=report['error'])
    finally:
        if channel is not None:
            channel.cleanup()
            if channel.errors:
                report['status'], exit_code = 'ABORTED', 1
        if report.get('driver', {}).get('log'):
            try:
                with open(report['driver']['log'], 'rb') as stream:
                    snapshot = stream.read(2*1024*1024).decode('utf-8', 'replace')
                report['driver_log_before_launch_exit'] = snapshot
                if any(word in snapshot for word in ['MEDICAL_SERIAL_WRITE_FAILED', 'Traceback', 'Invalid Index']):
                    report['status'], exit_code = 'ABORTED', 1
                    report['error'] = 'Driver log contains errors during pulse'
            except Exception as exc:
                report['driver_log_read_error'] = str(exc)
                report['status'], exit_code = 'ABORTED', 1
        if sub is not None:
            sub.unregister()
        if rospy is not None:
            rospy.signal_shutdown('bench pulse complete')
        with io.open(REPORT, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(report, ensure_ascii=True, indent=2)+u'\n')
        emit(report['status'], report=REPORT,
             movement_seen=report.get('assessment', {}).get('movement_seen_in_odom'),
             stopped_in_silence=report.get('assessment', {}).get('silence_tail_below_0_02_m_s'))
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
