#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Supervised ground straight pulse: +0.10 m/s, at most 0.20s command window.
Default never imports ROS or opens serial. Separate odom topic, no odom TF.
Physical travel and stopping must be measured; this is not a navigation driver.
"""
from __future__ import print_function
import argparse
import binascii
import glob
import hashlib
import json
import math
import os
import sys
import threading
import time

DRIVER_SHA = 'd671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'
DRIVER = '/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def scan_clearance(message):
    """Measured laser offset and straight swept corridor; no navigation claims."""
    if message.header.frame_id != 'base_laser_link':
        raise ValueError('SCAN_FRAME_CHANGED')
    if (len(message.ranges) < 100 or not finite(message.angle_min) or
            not finite(message.angle_increment) or message.angle_increment == 0 or
            not finite(message.range_min) or not finite(message.range_max) or
            not 0 <= message.range_min < message.range_max):
        raise ValueError('SCAN_GEOMETRY_INVALID')
    xs = []
    central_total = central_valid = 0
    front_rows = []
    for index, distance in enumerate(message.ranges):
        angle = message.angle_min + index * message.angle_increment
        normalized_angle=math.atan2(math.sin(angle), math.cos(angle))
        front = abs(normalized_angle) <= math.radians(20)+1e-9
        central_total += int(front)
        valid = finite(distance) and message.range_min <= distance <= message.range_max
        if not valid and distance != float('inf'):
            raise ValueError('INVALID_SCAN_BEAM')
        if front:
            front_rows.append((normalized_angle,valid))
        if not valid:
            continue
        central_valid += int(front)
        x = .135 + distance * math.cos(angle)
        y = distance * math.sin(angle)
        if x > 0 and abs(y) <= .21:
            xs.append(x)
    if central_valid < 3 or central_total < 3 or len(xs) < 3:
        raise ValueError('FRONT_SCAN_COVERAGE_INSUFFICIENT')
    front_rows.sort()
    if not front_rows[0][1] or not front_rows[-1][1]:
        raise ValueError('FRONT_SCAN_EDGE_UNKNOWN')
    if float(central_valid)/central_total < .90:
        raise ValueError('FRONT_SCAN_COVERAGE_BELOW_90_PERCENT')
    run=max_run=0
    for angle,valid in front_rows:
        run=0 if valid else run+1
        max_run=max(max_run,run)
    missing_width=max_run*abs(message.angle_increment)
    if missing_width > math.radians(1.01):
        raise ValueError('FRONT_UNKNOWN_GAP_TOO_WIDE')
    if min(xs) < .85:
        raise ValueError('FRONT_CORRIDOR_NOT_CLEAR')
    return dict(min_x_from_rear_axle_m=min(xs), front_clearance_m=min(xs)-.245,
                finite_corridor_returns=len(xs), central_valid=central_valid,
                central_total=central_total, unknown_front_beams=central_total-central_valid,
                max_unknown_gap_deg=math.degrees(missing_width),
                unknown_front_angles_deg=[math.degrees(a) for a,v in front_rows if not v],
                half_corridor_width_m=.21, required_front_clearance_m=.605)


def crc8(values):
    result = 0
    for value in values:
        value ^= result
        result = 0
        for unused in range(8):
            if (result ^ value) & 1:
                result = ((result ^ 0x18) >> 1) | 0x80
            else:
                result >>= 1
            value >>= 1
    return result


def bytes_list(frame):
    return list(bytearray(frame))


def frame_policy(frame, label):
    data = bytes_list(frame)
    if len(data) < 6 or data[0] != 0x5a or data[1] != len(data) or data[2] != 1:
        raise ValueError('INVALID_FRAME_LENGTH_OR_HEADER')
    if crc8(data[:-1]) != data[-1]:
        raise ValueError('INVALID_TX_CRC')
    if label == 'velocity' and data[3] == 1 and len(data) == 18:
        if any(data[4:10]):
            raise ValueError('NONZERO_SPEED_OR_STEERING_FORBIDDEN')
        if data[10:16] != [0x27, 0x10, 0x03, 0xe8, 0, 0] or data[16] != 0:
            raise ValueError('PID_OR_RESERVED_BYTES_CHANGED')
        return True
    if label == 'odom_query' and data[3] == 9 and len(data) == 7:
        if data[4:6] != [2, 0]:
            raise ValueError('LASER_MODE_CHANGED')
        return True
    raise ValueError('TX_COMMAND_NOT_WHITELISTED')


def forward_frame_policy(frame, phase, current, deadline):
    data = bytes_list(frame)
    if phase != 'PULSE' or deadline is None or current >= deadline:
        raise ValueError('FORWARD_WINDOW_CLOSED')
    expected = [0x5a,18,1,1,0,100,0,0,0,0,0x27,0x10,3,0xe8,0,0,0]
    expected.append(crc8(expected))
    if data != expected:
        raise ValueError('ONLY_EXACT_010_FORWARD_ZERO_STEER_ALLOWED')
    return True


def offline_check():
    def encoded(data):
        return bytearray(data + [crc8(data)])
    zero = [0x5a, 18, 1, 1, 0, 0, 0, 0, 0, 0, 0x27, 0x10, 3, 0xe8, 0, 0, 0]
    odom = [0x5a, 7, 1, 9, 2, 0]
    cases = [(encoded(zero), 'velocity', True), (encoded(odom), 'odom_query', True)]
    for index, value in [(5, 100), (4, 255), (8, 1), (10, 0), (16, 1)]:
        modified = zero[:]
        modified[index] = value
        cases.append((encoded(modified), 'velocity', False))
    cases.extend([(encoded(odom), 'velocity', False),
                  (encoded([0x5a, 6, 1, 7, 0]), 'battery_query', False),
                  (encoded([0x5a, 6, 1, 0x21, 0]), 'rpi_info', False),
                  (bytearray(zero + [crc8(zero) ^ 1]), 'velocity', False),
                  (encoded(zero)[:-1], 'velocity', False)])
    for frame, label, expected in cases:
        try:
            actual = frame_policy(frame, label)
        except ValueError:
            actual = False
        if actual != expected:
            raise AssertionError((label, list(frame), expected))
    print(json.dumps(dict(status='OFFLINE_POLICY_CHECK_PASSED', cases=len(cases),
                          ros_imported=False, serial_opened=False)))
    positive = [0x5a,18,1,1,0,100,0,0,0,0,0x27,0x10,3,0xe8,0,0,0]
    positive = encoded(positive)
    pulse_cases = [(positive, 'PULSE', 1., 1.3, True),
                   (positive, 'BASELINE', 1., 1.3, False),
                   (positive, 'POST_STOP', 1., 1.3, False),
                   (positive, 'PULSE', 1.3, 1.3, False),
                   (positive, 'PULSE', 1., None, False)]
    for index, value in [(5,101),(4,255),(9,1),(10,0)]:
        modified = list(positive[:-1]); modified[index] = value
        pulse_cases.append((encoded(modified),'PULSE',1.,1.3,False))
    for frame, phase, current, deadline, expected in pulse_cases:
        try: actual = forward_frame_policy(frame,phase,current,deadline)
        except ValueError: actual = False
        if actual != expected: raise AssertionError('PULSE_POLICY_CHECK_FAILED')
    print(json.dumps(dict(status='OFFLINE_FORWARD_POLICY_PASSED',cases=len(pulse_cases),hardware_opened=False)))
    class Mock(object):
        pass
    def mock(front_distance):
        result = Mock(); result.header = Mock(); result.header.frame_id = 'base_laser_link'
        result.angle_min = -.5; result.angle_increment = .01
        result.range_min = .02; result.range_max = 6.
        result.ranges = [front_distance / math.cos(-.5+i*.01) for i in range(101)]
        return result
    probes = [(mock(1.), True), (mock(.5), False)]
    for value in (float('nan'), -float('inf'), -1.):
        item=mock(1.); item.ranges[50]=value; probes.append((item,False))
    item=mock(1.); item.ranges[50]=float('inf'); probes.append((item,True))
    item=mock(1.)
    for index in (49,50,51):item.ranges[index]=float('inf')
    probes.append((item,False))
    item=mock(1.)
    for index in (25,30,35,40,45,50,55,60,65):item.ranges[index]=float('inf')
    probes.append((item,False))
    item=mock(1.); item.header.frame_id='unknown'; probes.append((item,False))
    for item, expected in probes:
        try: scan_clearance(item); actual=True
        except ValueError: actual=False
        if actual != expected: raise AssertionError('OFFLINE_SCAN_POLICY_FAILED')
    print(json.dumps(dict(status='OFFLINE_SCAN_POLICY_PASSED',cases=len(probes),hardware_opened=False)))


def ground(args):
    if hashlib.sha256(open(DRIVER, 'rb').read()).hexdigest() != DRIVER_SHA:
        raise RuntimeError('BASE_DRIVER_CHANGED')
    if not os.path.isabs(args.audit) or os.path.exists(args.audit):
        raise RuntimeError('ABSOLUTE_NEW_AUDIT_PATH_REQUIRED')
    device = os.path.realpath('/dev/EPRobot_base')
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        for fd in glob.glob('/proc/' + pid + '/fd/*'):
            try:
                owner = os.readlink(fd)
            except OSError:
                continue
            if owner == device:
                raise RuntimeError('SERIAL_ALREADY_OWNED_BY_PID_' + pid)
    import rospy
    import rosgraph
    rospy.init_node('medical_ground_straight_pulse', disable_signals=False)
    master = rosgraph.Master(rospy.get_name())
    control_types = ('geometry_msgs/Twist', 'geometry_msgs/TwistStamped',
                     'ackermann_msgs/AckermannDrive', 'ackermann_msgs/AckermannDriveStamped')
    types = dict(master.getTopicTypes())
    for topic, publishers in master.getSystemState()[0]:
        if publishers and (types.get(topic) in control_types or topic in ('/move_base/goal','/move_base_simple/goal')):
            raise RuntimeError('EXISTING_CONTROL_PUBLISHER_' + topic)
    if dict(master.getSystemState()[0]).get('/odom'):
        raise RuntimeError('EXISTING_ODOM_PUBLISHER')
    if rospy.get_param('/use_sim_time', False):
        raise RuntimeError('SIM_TIME_FORBIDDEN')
    lockfd = os.open(args.audit + '.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(lockfd)  # Kept permanently, including failed starts.
    auditfd = os.open(args.audit, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    auditfile = os.fdopen(auditfd, 'w')
    auditlock = threading.RLock()
    sys.path.insert(0, os.path.dirname(DRIVER))
    import medical_art_racecar_heading_v2_candidate as legacy
    now = legacy._medical_now
    def record(event, **data):
        data.update(event=event, mono=now(), wall=time.time())
        with auditlock:
            auditfile.write(json.dumps(data, sort_keys=True) + '\n')
            auditfile.flush()
    original_serial = legacy.serial.Serial
    class AuditSerial(object):
        def __init__(self, *params, **kwargs):
            self.raw = original_serial(*params, **kwargs)
            record('SERIAL_OPEN')
        def __getattr__(self, name):
            return getattr(self.raw, name)
        def read(self, count):
            data = self.raw.read(count)
            if data:
                record('RX_BYTES', hex=binascii.hexlify(data).decode('ascii'))
            return data
        def readall(self):
            data = self.raw.readall()
            record('STARTUP_DISCARDED_RX', hex=binascii.hexlify(data).decode('ascii'))
            return data
        def write(self, data):
            # Every caller must first pass Diagnostic._medical_write.
            if not getattr(self, 'authorized', False):
                raise RuntimeError('BYPASS_WRITE_FORBIDDEN')
            return self.raw.write(data)
    legacy.serial.Serial = AuditSerial
    import medical_stop_window
    stop_source = medical_stop_window.__file__
    if stop_source.endswith('.pyc'): stop_source = stop_source[:-1]
    if hashlib.sha256(open(stop_source, 'rb').read()).hexdigest() != '15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43':
        raise RuntimeError('STOP_WINDOW_SOURCE_CHANGED')
    from medical_stop_window import StopWindow
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    import tf2_ros
    state_lock = threading.RLock()
    state = dict(scan=None, odom=None, origin=None)
    def scan_cb(message):
        received = now()
        try:
            summary = scan_clearance(message)
            summary.update(received_mono=received, stamp=message.header.stamp.to_sec())
        except ValueError as exc:
            summary = dict(received_mono=received, stamp=message.header.stamp.to_sec(), error=str(exc))
        with state_lock:
            state['scan'] = summary
        record('SCAN_CLEARANCE', **summary)
    def odom_cb(message):
        q=message.pose.pose.orientation
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        row=dict(received_mono=now(),stamp=message.header.stamp.to_sec(),
                 x=message.pose.pose.position.x,y=message.pose.pose.position.y,yaw=yaw,
                 vx=message.twist.twist.linear.x,wz=message.twist.twist.angular.z,
                 frame=message.header.frame_id,child=message.child_frame_id,
                 q_norm=sum(v*v for v in (q.x,q.y,q.z,q.w)))
        with state_lock:
            state['odom']=row
        record('ODOM_POSE', **row)
    subscribers=[rospy.Subscriber('/medical_slam_scan',LaserScan,scan_cb,queue_size=5),
                 rospy.Subscriber('/medical_ground_straight_pulse/odom',Odometry,odom_cb,queue_size=100)]
    tf_buffer=tf2_ros.Buffer(); tf_listener=tf2_ros.TransformListener(tf_buffer)
    def graph_guard():
        live_types=dict(master.getTopicTypes())
        for topic, pubs in master.getSystemState()[0]:
            if topic=='/medical_ground_straight_pulse/feedback' and pubs==[rospy.get_name()]:
                continue
            if pubs and (live_types.get(topic) in control_types or topic in ('/move_base/goal','/move_base_simple/goal','/odom')):
                raise RuntimeError('CONTROL_OR_ODOM_PUBLISHER_APPEARED_'+topic)
    def floor_guard():
        with state_lock:
            scan=dict(state['scan']) if state['scan'] else None
            odom=dict(state['odom']) if state['odom'] else None
            origin=state['origin']
        current=now(); ros_now=rospy.Time.now().to_sec()
        if scan is None or not 0 <= current-scan['received_mono'] <= .30 or not -.02 <= ros_now-scan['stamp'] <= .30:
            raise RuntimeError('GROUND_SCAN_STALE')
        if scan.get('error'): raise RuntimeError(scan['error'])
        if odom is None or not 0 <= current-odom['received_mono'] <= .20 or not -.02 <= ros_now-odom['stamp'] <= .20:
            raise RuntimeError('GROUND_ODOM_STALE')
        if odom['frame']!='odom' or odom['child']!='base_footprint' or not all(finite(odom[k]) for k in ('x','y','yaw','vx','wz','q_norm')) or abs(odom['q_norm']-1)>.02:
            raise RuntimeError('GROUND_ODOM_INVALID')
        if origin is not None:
            distance=math.hypot(odom['x']-origin['x'],odom['y']-origin['y'])
            if distance >= .025: raise RuntimeError('EARLY_ODOM_DISTANCE_LIMIT')
            yaw_delta=math.atan2(math.sin(odom['yaw']-origin['yaw']),math.cos(odom['yaw']-origin['yaw']))
            if abs(yaw_delta)>.10: raise RuntimeError('GROUND_HEADING_CHANGED')
        return dict(scan=scan,odom=odom)
    class Diagnostic(legacy.BaseControl):
        def __init__(self):
            self.diag_next = 0.0
            self.diag_fault = None
            self.pulse_deadline = None
            self.phase = 'BASELINE'
            self.stop_window = StopWindow()
            self.last_stop_sample = None
            try:
                # Legacy BaseControl is an old-style class on Python2.
                legacy.BaseControl.__init__(self)
            except Exception:
                # The legacy shutdown hook is registered only after startup.
                if hasattr(self, '_medical_stop_event'):
                    self._medical_stop_event.set()
                self._medical_closing = True
                for name in ('timer_odom', 'timer_battery', 'timer_communication'):
                    timer = getattr(self, name, None)
                    if timer is not None:
                        timer.shutdown()
                with self._medical_tx_lock:
                    port = getattr(self, 'serial', None)
                    if port is not None:
                        port.close()
                raise
        def timerBatteryCB(self, event):
            # No 0x07/0x21 frame, CPU-info shell commands or battery telemetry.
            return
        def timerCommunicationCB(self, event):
            result = legacy.BaseControl.timerCommunicationCB(self, event)
            if self._medical_heading.failed:
                self.diag_fault = 'HEADING_CALIBRATION_FAILED_' + str(self._medical_heading.failed)
            sample = self._medical_fresh_odom()
            if sample is not None and sample['received_mono'] != self.last_stop_sample:
                with self._medical_rx_lock:
                    self.last_stop_sample = sample['received_mono']
                    self.stop_window.feed(dict(t=sample['received_mono'], stamp=sample['received_mono'],
                                               vx=sample['vx'], vy=sample['vy'], wz=sample['wz']))
            if sample is not None and self.phase == 'BASELINE' and abs(sample['vx']) > 0.002:
                self.diag_fault = 'NONZERO_LINEAR_FEEDBACK_DURING_ZERO_ONLY'
                record('ZERO_ONLY_FEEDBACK_FAULT', vx=sample['vx'])
            if sample is not None and self.phase != 'BASELINE' and abs(sample['vx']) > .20:
                self.diag_fault = 'WHEEL_RESPONSE_SPEED_LIMIT'
                record('WHEEL_RESPONSE_SPEED_LIMIT', vx=sample['vx'])
            return result
        def cmdCB(self, message):
            values = [message.linear.x, message.linear.y, message.linear.z,
                      message.angular.x, message.angular.y, message.angular.z]
            record('ROS_INPUT', values=values,
                   caller=getattr(message, '_connection_header', {}).get('callerid', 'unknown'))
            if any(not math.isfinite(v) if hasattr(math, 'isfinite') else
                   (math.isnan(v) or math.isinf(v)) for v in values) or any(values):
                record('ROS_NONZERO_REJECTED')
                self.diag_fault = 'UNEXPECTED_EXTERNAL_NONZERO_COMMAND'
                with self._medical_command_lock:
                    self._medical_last_command=None
                    self._medical_raw_cmdCB(legacy.Twist())
                return
            return legacy.BaseControl.cmdCB(self, message)
        def _medical_write(self, output, label):
            with self._medical_tx_lock:
                if self._medical_closing and label != 'velocity':
                    return False
                if self.diag_fault and label != 'velocity':
                    # Do not renew MCU communication through queries after a
                    # fault, even during the legacy constructor's startup wait.
                    return False
                try:
                    data = bytes_list(output)
                    forward = label == 'velocity' and any(data[4:10])
                    if forward:
                        forward_frame_policy(output,self.phase,now(),self.pulse_deadline)
                        if self._medical_fresh_odom() is None:
                            raise RuntimeError('GROUND_RAW_FEEDBACK_STALE')
                        floor_guard()
                    else:
                        frame_policy(output, label)
                    delay = self.diag_next - now()
                    if delay > 0:
                        time.sleep(delay)
                    # Shutdown can start while a query waits for its gap.
                    # Log cancellation separately; no serial write was tried.
                    if self._medical_closing and label != 'velocity':
                        record('TX_CANCELLED_SHUTDOWN', label=label)
                        return False
                    if forward and (self.diag_fault or self._medical_closing or now() >= self.pulse_deadline):
                        record('FORWARD_CANCELLED_AT_DEADLINE', label=label)
                        return False
                    if forward:
                        floor_guard()  # Recheck after the on-wire gap, before actual write.
                    record('TX_BEGIN', label=label, phase=self.phase,
                           hex=binascii.hexlify(output).decode('ascii'))
                    self.serial.authorized = True
                    try:
                        result = legacy.BaseControl._medical_write(self, output, label)
                    finally:
                        self.serial.authorized = False
                    # Estimate on-wire time; this gap is mitigation, not an MCU acknowledgement.
                    self.diag_next = now() + len(output) * 10.0 / self.baudrate + 0.010
                    record('TX_END', label=label, success=result)
                    if not result:
                        self.diag_fault = 'SERIAL_WRITE_FAILED'
                    return result
                except Exception as exc:
                    if str(exc)=='EARLY_ODOM_DISTANCE_LIMIT':
                        record('EARLY_ODOM_DISTANCE_STOP_INSIDE_TX_GUARD')
                        self.phase='POST_STOP'
                        self.pulse_deadline=None
                        self._medical_last_command=None
                        self._medical_raw_cmdCB(legacy.Twist())
                        return False
                    self.diag_fault = str(exc)
                    record('TX_BLOCKED_OR_FAILED', label=label, error=str(exc))
                    return False
    params = dict(port='/dev/EPRobot_base', baudrate=115200, odom_freq=50,
                  base_kp=1000.0, base_ki=100.0, base_kd=0.0, base_kv=1.0,
                  wheelbase=0.17, Laser_Mode='Boost', is_pub_odom_tf='false',
                  is_send_anger='false', command_timeout=0.35,
                  stationary_start_confirmed=True,
                  odom_topic='/medical_ground_straight_pulse/odom',
                  imu_topic='/medical_ground_straight_pulse/imu',
                  cmd_vel_topic='/medical_ground_straight_pulse/reject_external_motion_input',
                  feedback_vel_topic='/medical_ground_straight_pulse/feedback')
    for key, value in params.items():
        rospy.set_param('~' + key, value)
    record('GROUND_PULSE_START', driver_sha256=DRIVER_SHA, parameters=params,
           duration=args.duration, floor_motion_permitted=True)
    control = None
    pulse_timer = None
    try:
        deadline = now() + args.duration
        control = Diagnostic()
        def wait_strict_stop(stage):
            while not rospy.is_shutdown() and now() < deadline and not control.diag_fault:
                graph_guard()
                with control._medical_rx_lock:
                    evidence = control.stop_window.evidence(now())
                if evidence['passed']:
                    record(stage, evidence=evidence)
                    return
                time.sleep(.05)
            raise RuntimeError(control.diag_fault or 'STRICT_STOP_WINDOW_UNAVAILABLE')
        wait_strict_stop('BASELINE_STRICT_STOP')
        graph_guard()
        transform=tf_buffer.lookup_transform('base_footprint','base_laser_link',rospy.Time(0),rospy.Duration(2))
        t=transform.transform.translation; q=transform.transform.rotation
        if abs(t.x-.135)>.001 or abs(t.y)>.001 or abs(t.z-.135)>.001 or max(abs(q.x),abs(q.y),abs(q.z))>.001 or abs(abs(q.w)-1)>.001:
            raise RuntimeError('MEASURED_LASER_TRANSFORM_CHANGED')
        evidence=floor_guard()
        with state_lock:
            state['origin']=dict(evidence['odom'])
        with control._medical_rx_lock:
            if not control.stop_window.evidence(now())['passed']:
                raise RuntimeError('BASELINE_LOST_BEFORE_ARM')
        record('GROUND_PRE_PULSE_EVIDENCE', **evidence)
        # One fixed 0.20s positive window, never a route or automatic repetition.
        # External ROS nonzero inputs remain rejected by cmdCB.
        with control._medical_command_lock:
            control.phase = 'PULSE'
            control.pulse_deadline = now() + .20
        record('AUTHORIZED_GROUND_STRAIGHT_PULSE_BEGIN', command_vx=.10, max_window_s=.20)
        def deadline_zero():
            with control._medical_command_lock:
                if control.phase=='PULSE':
                    control.phase='POST_STOP'
                    control.pulse_deadline=None
                    control._medical_last_command=None
                    control._medical_raw_cmdCB(legacy.Twist())
                    record('INDEPENDENT_PULSE_DEADLINE_ZERO')
        pulse_timer=threading.Timer(max(0.,control.pulse_deadline-now()),deadline_zero)
        pulse_timer.daemon=True; pulse_timer.start()
        try:
            while not control.diag_fault and not rospy.is_shutdown():
                with control._medical_command_lock:
                    if control.phase!='PULSE' or control.pulse_deadline is None or now() >= control.pulse_deadline: break
                    try: floor_guard()
                    except RuntimeError as exc:
                        if str(exc)=='EARLY_ODOM_DISTANCE_LIMIT':
                            record('EARLY_ODOM_DISTANCE_STOP')
                            break
                        raise
                    control._medical_last_command = now()
                    message = legacy.Twist()
                    message.linear.x = .10
                    control._medical_raw_cmdCB(message)
                time.sleep(.05)
        finally:
            with control._medical_command_lock:
                control.pulse_deadline = None
                control.phase = 'POST_STOP'
                control._medical_last_command = None
                control._medical_raw_cmdCB(legacy.Twist())
            record('AUTHORIZED_GROUND_STRAIGHT_PULSE_END_ZERO_SENT')
        if control.diag_fault: raise RuntimeError(control.diag_fault)
        wait_strict_stop('POST_PULSE_STRICT_STOP')
        with state_lock:
            measured=dict(state['odom']) if state['odom'] else None
            origin=state['origin']
        record('GROUND_STRAIGHT_PULSE_COMPLETE_AWAITING_PHYSICAL_MEASUREMENT',origin=origin,final_odom=measured)
    except Exception as exc:
        record('GROUND_PULSE_ABORT',error=str(exc))
        raise
    finally:
        if pulse_timer is not None:
            pulse_timer.cancel()
        if control is not None:
            control.medical_shutdown()
        rospy.signal_shutdown('Supervised ground pulse finished')
        record('GROUND_PULSE_END', startup_completed=control is not None,
               diagnostic_fault=None if control is None else control.diag_fault)
        # Keep flushed audit open until process exit: a read callback may be
        # finishing after shutdown. No report or .lock is removed.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-check', action='store_true')
    parser.add_argument('--execute-ground-pulse', action='store_true')
    parser.add_argument('--clear-floor-confirmed', action='store_true')
    parser.add_argument('--power-stop-confirmed', action='store_true')
    parser.add_argument('--audit')
    parser.add_argument('--duration', type=float, default=30.0)
    args = parser.parse_args()
    if args.offline_check:
        offline_check()
        return
    if not (args.execute_ground_pulse and args.clear_floor_confirmed and args.power_stop_confirmed):
        print('PREPARED_ONLY: no ROS import, no serial open, no hardware commands')
        return
    if not args.audit or not 5 <= args.duration <= 30:
        raise SystemExit('NEW_AUDIT_PATH_AND_DURATION_5_TO_30_REQUIRED')
    ground(args)


if __name__ == '__main__':
    main()
