#!/usr/bin/env python2
"""Offline-only regression/replay for the forward map-backed policy."""
from __future__ import print_function
import argparse
import hashlib
import importlib
import json
import math
import os
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--scripts',required=True)
    p.add_argument('--scans',required=True)
    p.add_argument('--pose-evidence',required=True)
    p.add_argument('--output',required=True)
    a = p.parse_args()
    if os.path.exists(a.output): raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
    sys.path.insert(0,a.scripts)
    policy = importlib.import_module('navigation_forward_map_guard_candidate')
    class M(object): pass
    def scan(n=720):
        m = M(); m.header=M(); m.header.frame_id='base_laser_link'
        m.angle_min=-math.pi; m.angle_increment=2*math.pi/n
        m.range_min=.1; m.range_max=100.; m.ranges=[3.]*n
        return m
    grid=dict(width=200,height=200,resolution=.05,origin=[-5.,-5.,0.],data=[0]*40000)
    pose=dict(x=0.,y=0.,yaw=0.); vx=.1; wz=vx*math.tan(.222)/.17; checks=[]
    def run(m=None,**overrides):
        kw=dict(message=m or scan(),grid=grid,pose=pose,xy_std=[.01,.01],
                yaw_std=math.radians(1),pose_age=.05,scan_age=.10,v=vx,w=wz,stop_distance=.1)
        kw.update(overrides); return policy.evaluate(**kw)
    def rejects(label,fn):
        try:
            r=fn()
            if r['passed']: raise AssertionError('EXPECTED_REFUSAL_'+label)
        except ValueError: pass
        checks.append(label)
    assert run()['passed']; checks.append('open_map_and_scan')
    m=scan()
    for i in range(720):
        ang=m.angle_min+i*m.angle_increment
        if abs(ang)>math.radians(120):m.ranges[i]=float('inf')
    assert run(m)['passed']; checks.append('rear_unknown_does_not_refuse_forward')
    m=scan();m.ranges[0]=.25
    assert run(m)['passed']; checks.append('rear_component_does_not_refuse_forward')
    m=scan();m.ranges[360]=.30
    rejects('front_obstacle_refused',lambda:run(m))
    m=scan();m.ranges[430]=.45
    rejects('turn_side_obstacle_refused',lambda:run(m))
    m=scan()
    for i in range(356,363):m.ranges[i]=float('inf')
    rejects('forward_wide_unknown_refused',lambda:run(m))
    m=scan();m.ranges[360]=float('nan')
    rejects('front_invalid_refused',lambda:run(m))
    for n in (979,980,981,982):
        assert run(scan(n))['passed'];checks.append('varying_count_%d'%n)
    for tag,kw in [('scan_stale',dict(scan_age=.301)),('scan_future',dict(scan_age=-.021)),
                   ('pose_stale',dict(pose_age=1.001)),('pose_uncertain',dict(xy_std=[.101,.01])),
                   ('reverse',dict(v=-.1)),('spin',dict(v=0.,w=.1))]:
        rejects(tag,lambda:run(**kw))
    # Full-body map check includes the rear, despite no rear scan requirement.
    index=100*200+98;old=grid['data'][index]
    grid['data'][index]=100;rejects('mapped_rear_obstacle_refused',lambda:run())
    grid['data'][index]=-1;rejects('mapped_rear_unknown_refused',lambda:run())
    grid['data'][index]=old
    source=json.load(open(a.scans));pose_capture=json.load(open(a.pose_evidence));view=pose_capture['view']
    rows=[];errors={}
    for raw in source['scans']:
        if raw['topic']!='/scan':continue
        m=scan();m.header.frame_id=raw['frame']
        for k in ('angle_min','angle_increment','range_min','range_max'):setattr(m,k,raw[k])
        m.ranges=[float(r) for r in raw['ranges']];before=list(m.ranges)
        r=policy.directional_scan(m,vx,wz,.1)
        assert before==m.ranges
        r.update(seq=raw['seq'],stamp=raw['stamp'],original_error=raw['pulse_guard'].get('error'))
        rows.append(r);key=r['error'] or 'PASS';errors[key]=errors.get(key,0)+1
    # Diagnostic use of saved coordinates is explicitly historical. Never
    # pass an old snapshot with a made-up fresh age to authorize live motion.
    uncertainty=view['uncertainty'];past= dict(x=view['pose']['x'],y=view['pose']['y'],yaw=view['pose']['yaw'])
    historical_map_screen={}
    for name,g in view['maps'].items():
        try:
            historical_map_screen[name]=policy.map_and_localization_guard(g,past,
                uncertainty['xy_std_m'],math.radians(uncertainty['yaw_std_deg']),
                view['pose']['ros_age'],vx,wz,.1)
        except ValueError as exc:
            historical_map_screen[name]=dict(passed=False,error=str(exc),historical_only=True)
    assert 'rospy' not in sys.modules and 'serial' not in sys.modules
    fn=os.path.join(a.scripts,'navigation_forward_map_guard_candidate.py')
    report=dict(status='FORWARD_MAP_POLICY_OFFLINE_PASSED_NOT_FIELD_ACCEPTANCE',
        checks=checks,check_count=len(checks),motion_sent=False,hardware_opened=False,
        rear_realtime_required=False,rear_dynamic_obstacle_detection=False,
        field_accepted=False,source_sha256=hashlib.sha256(open(fn,'rb').read()).hexdigest(),
        replay_raw_frames=len(rows),directional_replay_errors=errors,
        replay_rows=rows,historical_pose_screen=historical_map_screen,
        note='Directional scan PASS is not full navigation acceptance. Saved pose is historical only.')
    with os.fdopen(os.open(a.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        json.dump(report,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k!='replay_rows'}))


if __name__=='__main__':main()
