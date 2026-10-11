#!/usr/bin/env python2
"""Paired live scan observation only. Never publishes or opens serial."""
from __future__ import print_function
import json,math,os,sys,threading,time
import rospy
from sensor_msgs.msg import LaserScan
from navigation_forward_scan import filtered_ranges

def main():
    p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'live-forward-filter-review.json')
    os.close(os.open(p+'.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600))
    if os.path.exists(p):raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
    rospy.init_node('medical_forward_filter_readonly_review',anonymous=True)
    lock=threading.RLock();raw={};filtered={};frames=[];errors=[]
    def encoded(values):
        return [v if not math.isnan(v) and not math.isinf(v) else
                'nan' if math.isnan(v) else 'inf' if v>0 else '-inf' for v in values]
    def callback(m,kind):
        key=m.header.stamp.to_nsec()
        with lock:
            (raw if kind=='raw' else filtered)[key]=m
            if key not in raw or key not in filtered:return
            a,b=raw.pop(key),filtered.pop(key);expected,evidence=filtered_ranges(a)
            if encoded(expected)!=encoded(b.ranges):
                errors.append('FILTERED_RANGES_MISMATCH');return
            fields=('angle_min','angle_max','angle_increment','time_increment','scan_time','range_min','range_max')
            if not all(getattr(a,k)==getattr(b,k) for k in fields):
                errors.append('SCAN_METADATA_MISMATCH');return
            if a.header.frame_id!=b.header.frame_id or list(a.intensities)!=list(b.intensities):
                errors.append('SCAN_FRAME_OR_INTENSITY_MISMATCH');return
            evidence.update(stamp=a.header.stamp.to_sec(),age=(rospy.Time.now()-a.header.stamp).to_sec(),
                            raw_ranges=encoded(a.ranges),filtered_ranges=encoded(b.ranges),
                            source_seq=a.header.seq,output_seq=b.header.seq)
            frames.append(evidence)
    subs=[rospy.Subscriber('/scan',LaserScan,callback,callback_args='raw',queue_size=1,tcp_nodelay=True),
          rospy.Subscriber('/medical_navigation_forward_scan',LaserScan,callback,callback_args='filtered',queue_size=1,tcp_nodelay=True)]
    rospy.sleep(6)
    for sub in subs:sub.unregister()
    with lock:
        if len(frames)<20:raise RuntimeError('TOO_FEW_LIVE_PAIRED_FRAMES')
        if errors:raise RuntimeError('LIVE_FILTER_ERRORS_'+repr(errors))
        result=dict(status='LIVE_FORWARD_FILTER_PAIRED_CHECK_PASSED',frames=frames,
                    matched_frames=len(frames),motion_sent=False,serial_opened=False,
                    original_topic='/scan',output_topic='/medical_navigation_forward_scan',
                    mapping_input_changed=False,localization_input_changed=False,blind_marked_free=False)
        with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:
            json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='frames'}))

if __name__=='__main__':main()
