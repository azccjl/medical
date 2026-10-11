#!/usr/bin/env python2
"""Pure filter checks. No ROS imports, serial or robot access."""
from __future__ import print_function
import argparse,importlib,json,math,os,sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--scripts',required=True)
    p.add_argument('--scans',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    if os.path.exists(a.output):raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
    sys.path.insert(0,a.scripts);mod=importlib.import_module('navigation_forward_scan')
    class M(object):pass
    checks=0;rows=[]
    for raw in json.load(open(a.scans))['scans']:
        if raw['topic']!='/scan':continue
        m=M();m.header=M();m.header.frame_id=raw['frame']
        for k in ('angle_min','angle_increment','range_min','range_max'):setattr(m,k,raw[k])
        m.ranges=[float(v) for v in raw['ranges']];before=list(m.ranges)
        out,evidence=mod.filtered_ranges(m)
        assert before==m.ranges and out is not m.ranges
        for i,(v,new) in enumerate(zip(m.ranges,out)):
            ang=m.angle_min+i*m.angle_increment;c,s=math.cos(ang),math.sin(ang)
            rear=abs(math.atan2(s,c))>math.radians(120)+1e-6
            finite=not math.isnan(v) and not math.isinf(v) and m.range_min<=v<=m.range_max
            own=finite and -.1<.135+v*c<.245 and abs(v*s)<.11
            assert math.isnan(new) if rear or own else new==v
            checks+=1
        rows.append(evidence)
    assert 'rospy' not in sys.modules and 'serial' not in sys.modules
    result=dict(status='FORWARD_SCAN_FILTER_OFFLINE_PASSED',raw_frames=len(rows),
                beam_checks=checks,motion_sent=False,original_ranges_modified=False,
                blind_marked_free=False,rows=rows)
    with os.fdopen(os.open(a.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
        json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__=='__main__':main()
