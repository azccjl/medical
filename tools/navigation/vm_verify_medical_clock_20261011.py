#!/usr/bin/env python2
"""Read-only 180s NTP offset + scan freshness verification; no publishers."""
from __future__ import print_function
import ctypes
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import rospy
from sensor_msgs.msg import LaserScan
sys.path.insert(0, '/tmp')
from medical_offline_clock import sample

cli = argparse.ArgumentParser(description=__doc__)
cli.add_argument('--output', default='/home/ncut/medical_clock_sync_20261011/verification.json')
cli.add_argument('--port', type=int, default=18080)
args = cli.parse_args()
output = args.output
assert not os.path.exists(output)
os.close(os.open(output + '.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
class TS(ctypes.Structure):
    _fields_ = [('s', ctypes.c_long), ('ns', ctypes.c_long)]
lib = ctypes.CDLL('librt.so.1', use_errno=True)
def monotonic():
    stamp = TS()
    assert lib.clock_gettime(1, ctypes.byref(stamp)) == 0
    return stamp.s + stamp.ns * 1e-9

start = monotonic()
scans = []
samples = []
errors = []
lock = threading.Lock()
def scan_cb(message):
    with lock:
        scans.append(dict(elapsed=monotonic()-start,
                          age=(rospy.Time.now()-message.header.stamp).to_sec()))

rospy.init_node('medical_continuous_clock_readonly', anonymous=True)
assert not rospy.get_param('/use_sim_time', False)
subscriber = rospy.Subscriber('/medical_slam_scan', LaserScan, scan_cb, queue_size=1, tcp_nodelay=True)
before = subprocess.check_output(['chronyc', 'tracking'])
while monotonic()-start < 180 and not rospy.is_shutdown():
    try:
        row = min([sample('192.168.12.1', args.port) for i in range(3)],
                  key=lambda x:x['round_trip_seconds'])
        row['elapsed'] = monotonic()-start
        samples.append(row)
    except Exception as exc:
        errors.append(dict(elapsed=monotonic()-start,error=str(exc)))
    time.sleep(2)
subscriber.unregister()
stable_samples = [r for r in samples if r['elapsed'] >= 60]
stable_scans = [r for r in scans if r['elapsed'] >= 60]
max_offset = max([abs(r['offset_seconds']) for r in stable_samples] or [999])
ages = [r['age'] for r in stable_scans]
result = dict(status='REFUSED', motion_commands_sent=False,
              capture_transport='TCP_NODELAY_QUEUE_1',
              elapsed=monotonic()-start, samples=samples, scans=scans, errors=errors,
              tracking_before=before, tracking_after=subprocess.check_output(['chronyc','tracking']),
              sources_after=subprocess.check_output(['chronyc','-n','sources','-v']),
              stable_sample_count=len(stable_samples),stable_scan_count=len(stable_scans),
              stable_max_abs_offset_seconds=max_offset,
              stable_scan_age_min=min(ages or [999]),stable_scan_age_max=max(ages or [999]))
result['clock_status'] = 'CONTINUOUS_CLOCK_VERIFIED' if len(stable_samples)>=50 and not errors and max_offset<=.01 else 'REFUSED'
result['scan_status'] = 'SCAN_FRESHNESS_VERIFIED' if len(stable_scans)>=500 and min(ages)>=-.02 and max(ages)<=.30 else 'REFUSED'
if result['clock_status']=='CONTINUOUS_CLOCK_VERIFIED' and result['scan_status']=='SCAN_FRESHNESS_VERIFIED':
    result['status']='CONTINUOUS_CLOCK_AND_SCAN_FRESHNESS_VERIFIED'
with os.fdopen(os.open(output, os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644),'w') as stream:
    json.dump(result,stream,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','scans')}))
sys.exit(0 if result['status']=='CONTINUOUS_CLOCK_AND_SCAN_FRESHNESS_VERIFIED' else 1)
