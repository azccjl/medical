#!/usr/bin/env python2
"""Align VM wall clock forward by <=0.5s to read-only robot UDP time service.
No ROS publishers or robot clock changes. Reject large/backwards changes.
"""
from __future__ import print_function
import ctypes, json, os, sys, time
sys.path.insert(0, '/tmp')
from medical_offline_clock import sample

output='/home/ncut/medical_localization_assets_20261011/vm-small-forward-clock-v2-20261011.json'
if os.path.exists(output): raise RuntimeError('OUTPUT_EXISTS')
os.close(os.open(output+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
result=dict(status='REFUSED',robot_clock_changed=False)
try:
    if os.geteuid()!=0: raise RuntimeError('VM_ROOT_REQUIRED')
    if os.path.isdir('/home/EPRobot/robot_ws'): raise RuntimeError('VM_ONLY')
    before=[sample('192.168.12.1',18080) for unused in range(9)]
    result['before']=before
    if max(r['offset_seconds'] for r in before)-min(r['offset_seconds'] for r in before)>.01:
        raise RuntimeError('UNSTABLE_TIME_MEASUREMENT')
    best=min(before,key=lambda r:r['round_trip_seconds'])
    offset=best['offset_seconds']
    if not 0 <= offset <= .5: raise RuntimeError('ONLY_SMALL_FORWARD_ALIGNMENT_ALLOWED')
    if best['round_trip_seconds']>.01: raise RuntimeError('CLOCK_NETWORK_DELAY_TOO_LARGE')
    class TS(ctypes.Structure):
        _fields_=[('s',ctypes.c_long),('ns',ctypes.c_long)]
    lib=ctypes.CDLL('librt.so.1',use_errno=True)
    target=time.time()+offset
    stamp=TS(int(target),int((target-int(target))*1e9))
    if lib.clock_settime(0,ctypes.byref(stamp))!=0:
        raise RuntimeError('VM_CLOCK_SET_FAILED_ERRNO_'+str(ctypes.get_errno()))
    result['applied_forward_seconds']=offset
    after=[sample('192.168.12.1',18080) for unused in range(9)]
    result['after']=after
    if max(abs(r['offset_seconds']) for r in after)>.01:
        raise RuntimeError('ALIGNMENT_NOT_VERIFIED')
    result['status']='VM_SMALL_FORWARD_ALIGNMENT_VERIFIED'
except Exception as exc:
    result['error']=str(exc)
finally:
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644),'w') as f:
        json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(result))
raise SystemExit(0 if result['status']=='VM_SMALL_FORWARD_ALIGNMENT_VERIFIED' else 1)
