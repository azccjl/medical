#!/usr/bin/env python2
"""Replay saved scans in Ubuntu without ROS or any hardware imports."""
from __future__ import print_function
import hashlib
import imp
import json
import os
import sys


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--previous',required=True)
    parser.add_argument('--scans',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if os.path.exists(args.output): raise RuntimeError('OUTPUT_EXISTS')
    module=imp.load_source('ground_v3_offline',args.source)
    previous=imp.load_source('ground_v2_offline',args.previous)
    module.offline_check()
    report={'status':'OFFLINE_REVIEW_PASSED','robot_program_executed':False,
            'hardware_opened':False,'source_sha256':hashlib.sha256(open(args.source,'rb').read()).hexdigest(),
            'scan_replays':[]}
    class Mock(object): pass
    for sample in json.load(open(args.scans))['samples']:
        if sample['topic']!='/medical_slam_scan': continue
        scan=Mock();scan.header=Mock();scan.header.frame_id=sample['frame']
        for key in ['angle_min','angle_increment','range_min','range_max']:setattr(scan,key,sample[key])
        scan.ranges=[]
        for value,kind in zip(sample['ranges'],sample['range_kinds']):
            if kind=='finite':scan.ranges.append(value)
            elif kind=='positive_inf':scan.ranges.append(float('inf'))
            else:raise RuntimeError('UNEXPECTED_SAVED_RANGE_KIND_'+kind)
        try:previous.scan_clearance(scan)
        except ValueError as exc:old_error=str(exc)
        else:raise AssertionError('EXPECTED_PREVIOUS_BOUNDARY_REFUSAL')
        assert old_error=='FRONT_SCAN_EDGE_UNKNOWN'
        try:module.scan_clearance(scan)
        except ValueError as exc:new_error=str(exc)
        else:raise AssertionError('SAVED_UNKNOWN_BOUNDARY_MUST_STILL_REFUSE')
        assert new_error=='FRONT_SCAN_EDGE_UNKNOWN'
        report['scan_replays'].append(dict(stamp=sample['stamp'],old_error=old_error,
                                          new_error=new_error,status='REFUSED_UNCHANGED_PROTECTION'))
    assert len(report['scan_replays'])==3
    # Synthetic input isolates float32 rounding; saved scans are never altered.
    probe=Mock();probe.header=Mock();probe.header.frame_id='base_laser_link'
    probe.angle_min=0.;probe.angle_increment=.008726646192371845
    probe.range_min=.1;probe.range_max=100.;probe.ranges=[1.]*720
    probe.ranges[681]=float('inf')
    try:previous.scan_clearance(probe)
    except ValueError as exc:assert str(exc)=='FRONT_SCAN_EDGE_UNKNOWN'
    else:raise AssertionError('PREVIOUS_ROUNDING_CASE_NOT_REPRODUCED')
    report['synthetic_finite_boundary_rounding']=module.scan_clearance(probe)
    probe.ranges[680]=float('inf')
    try:module.scan_clearance(probe)
    except ValueError as exc:assert str(exc)=='FRONT_SCAN_EDGE_UNKNOWN'
    else:raise AssertionError('UNKNOWN_BOUNDARY_MUST_STILL_REFUSE')
    probe.ranges[680]=1.;probe.ranges[0]=.3
    try:module.scan_clearance(probe)
    except ValueError as exc:assert str(exc)=='FRONT_CORRIDOR_NOT_CLEAR'
    else:raise AssertionError('NEAR_OBSTACLE_MUST_STILL_REFUSE')
    report['synthetic_unknown_boundary_refused']=True
    report['synthetic_near_obstacle_refused']=True
    report['live_motion_readiness']='NOT_CHECKED_NO_MOTION_AUTHORIZATION'
    assert 'rospy' not in sys.modules and 'serial' not in sys.modules
    report['ros_imported']=False
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle:
        json.dump(report,handle,indent=2,allow_nan=False)
    print(json.dumps(report))


if __name__=='__main__':main()
