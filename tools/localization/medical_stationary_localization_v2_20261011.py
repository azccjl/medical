#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Stationary localization candidate: zero-only serial writes, odom and TF.
Default and --offline-check never import ROS/serial. Explicit supervised
execution required. This program contains no forward or steering command.
It is not a navigation driver or a repair of the unverified MCU firmware.
"""
from __future__ import print_function
import argparse
import binascii
import glob
import hashlib
import imp
import json
import math
import os
import sys
import threading
import time

DRIVER_SHA = 'd671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'
DRIVER = '/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'


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


def observe(args):
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
    rospy.init_node('medical_stationary_localization', disable_signals=False)
    master = rosgraph.Master(rospy.get_name())
    control_types = ('geometry_msgs/Twist', 'geometry_msgs/TwistStamped',
                     'ackermann_msgs/AckermannDrive', 'ackermann_msgs/AckermannDriveStamped')
    types = dict(master.getTopicTypes())
    for topic, publishers in master.getSystemState()[0]:
        if publishers and (types.get(topic) in control_types or topic in ('/move_base/goal', '/move_base_simple/goal')):
            raise RuntimeError('EXISTING_CONTROL_PUBLISHER_' + topic)
    publishers = dict(master.getSystemState()[0])
    if publishers.get('/odom'):
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
    stop_handle, stop_source, stop_description = imp.find_module('medical_stop_window')
    try:
        stop_digest = hashlib.sha256(open(stop_source, 'rb').read()).hexdigest()
    finally:
        if stop_handle is not None:
            stop_handle.close()
    if stop_digest != '15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43':
        raise RuntimeError('STOP_WINDOW_SOURCE_CHANGED')
    from medical_stop_window import StopWindow
    class Diagnostic(legacy.BaseControl):
        def __init__(self):
            self.diag_next = 0.0
            self.diag_fault = None
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
            if sample is not None and abs(sample['vx']) > 0.002:
                self.diag_fault = 'NONZERO_LINEAR_FEEDBACK_DURING_ZERO_ONLY'
                record('ZERO_ONLY_FEEDBACK_FAULT', vx=sample['vx'])
            return result
        def cmdCB(self, message):
            values = [message.linear.x, message.linear.y, message.linear.z,
                      message.angular.x, message.angular.y, message.angular.z]
            record('ROS_INPUT', values=values,
                   caller=getattr(message, '_connection_header', {}).get('callerid', 'unknown'))
            if any(not math.isfinite(v) if hasattr(math, 'isfinite') else
                   (math.isnan(v) or math.isinf(v)) for v in values) or any(values):
                record('ROS_NONZERO_REJECTED')
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
                    frame_policy(output, label)
                    delay = self.diag_next - now()
                    if delay > 0:
                        time.sleep(delay)
                    # Shutdown can start while a query waits for its gap.
                    # Log cancellation separately; no serial write was tried.
                    if self._medical_closing and label != 'velocity':
                        record('TX_CANCELLED_SHUTDOWN', label=label)
                        return False
                    record('TX_BEGIN', label=label, hex=binascii.hexlify(output).decode('ascii'))
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
                    self.diag_fault = str(exc)
                    record('TX_BLOCKED_OR_FAILED', label=label, error=str(exc))
                    return False
    params = dict(port='/dev/EPRobot_base', baudrate=115200, odom_freq=50,
                  base_kp=1000.0, base_ki=100.0, base_kd=0.0, base_kv=1.0,
                  wheelbase=0.17, Laser_Mode='Boost', is_pub_odom_tf='true',
                  is_send_anger='false', command_timeout=0.35,
                  stationary_start_confirmed=True,
                  odom_topic='/odom',
                  imu_topic='/medical_stationary_localization/imu',
                  cmd_vel_topic='/medical_stationary_localization/zero_only_input',
                  feedback_vel_topic='/medical_stationary_localization/feedback')
    for key, value in params.items():
        rospy.set_param('~' + key, value)
    record('STATIONARY_LOCALIZATION_START', driver_sha256=DRIVER_SHA, parameters=params,
           duration=args.duration, floor_motion_permitted=False)
    control = None
    try:
        deadline = now() + args.duration
        control = Diagnostic()
        ready = False
        last_graph_check = 0.0
        while not rospy.is_shutdown() and now() < deadline and not control.diag_fault:
            with control._medical_rx_lock:
                evidence = control.stop_window.evidence(now())
            if evidence['passed'] and not ready:
                ready = True
                record('STRICT_STATIONARY_LOCALIZATION_READY', evidence=evidence)
            elif ready and not evidence['passed']:
                raise RuntimeError('STRICT_STATIONARY_WINDOW_LOST')
            if now() - last_graph_check >= .5:
                live_types = dict(master.getTopicTypes())
                live_pubs = dict(master.getSystemState()[0])
                own_feedback = '/medical_stationary_localization/feedback'
                for topic, pubs in live_pubs.items():
                    if topic == own_feedback and pubs == [rospy.get_name()]:
                        continue  # Own measured telemetry, never a command input.
                    if pubs and (live_types.get(topic) in control_types or
                                 topic in ('/move_base/goal', '/move_base_simple/goal')):
                        raise RuntimeError('CONTROL_PUBLISHER_APPEARED_' + topic)
                if live_pubs.get('/odom') != [rospy.get_name()]:
                    raise RuntimeError('ODOM_PUBLISHER_CONFLICT')
                last_graph_check = now()
            time.sleep(0.05)
        if not ready:
            raise RuntimeError(control.diag_fault or 'STRICT_STATIONARY_WINDOW_NEVER_READY')
        if control.diag_fault:
            raise RuntimeError(control.diag_fault)
    finally:
        if control is not None:
            control.medical_shutdown()
        rospy.signal_shutdown('Stationary localization finished')
        record('STATIONARY_LOCALIZATION_END', startup_completed=control is not None,
               diagnostic_fault=None if control is None else control.diag_fault)
        # Keep flushed audit open until process exit: a read callback may be
        # finishing after shutdown. No report or .lock is removed.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-check', action='store_true')
    parser.add_argument('--execute-stationary', action='store_true')
    parser.add_argument('--vehicle-stationary-confirmed', action='store_true')
    parser.add_argument('--power-stop-confirmed', action='store_true')
    parser.add_argument('--audit')
    parser.add_argument('--duration', type=float, default=120.0)
    args = parser.parse_args()
    if args.offline_check:
        offline_check()
        return
    if not (args.execute_stationary and args.vehicle_stationary_confirmed and args.power_stop_confirmed):
        print('PREPARED_ONLY: no ROS import, no serial open, no hardware commands')
        return
    if not args.audit or not 30 <= args.duration <= 120:
        raise SystemExit('NEW_AUDIT_PATH_AND_DURATION_30_TO_120_REQUIRED')
    observe(args)


if __name__ == '__main__':
    main()
