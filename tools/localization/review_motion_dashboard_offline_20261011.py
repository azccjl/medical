#!/usr/bin/env python2
"""Offline policy and web state checks. No ROS import, SSH or serial access."""
from __future__ import print_function
import argparse,json,sys,os,threading
import medical_motion_dashboard_20261011 as web
import medical_ground_straight_pulse_v5_20261011 as pulse


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    pulse.offline_check()
    class Ros(object):
        class Time(object):
            @staticmethod
            def now():
                class Stamp(object):
                    def to_sec(self):return 100.
                return Stamp()
    d=object.__new__(web.Dashboard)
    d.lock=threading.RLock();d.ros=Ros();d.scan=None;d.consecutive=0;d.received=None
    d.last_stamp=None;d.graph_errors=[];d.graph_time=web.now();d.busy=False;d.csrf='offline';d.run=None;d.arm=None
    d.check_graph=lambda:None
    assert not d.snapshot()['ready']
    assert d.prepare()[0]==409
    assert d.start(dict(arm='invalid',confirmed=True))[0]==409
    assert d.stop()[1]['status']=='NO_ACTIVE_RUN'
    d.scan=dict(errors=[],passed=True);d.consecutive=5;d.last_stamp=100.;d.received=web.now()
    assert d.snapshot()['ready']
    code,token=d.prepare();assert code==200
    assert d.start(dict(arm=token['arm'],confirmed=False))[0]==409
    assert d.arm is None
    d.prepare();d.received=web.now()-1
    assert not d.snapshot()['ready']
    assert d.start(dict(arm=d.arm[0],confirmed=True))[0]==409
    d.received=web.now();d.graph_errors=['UNEXPECTED_PUBLISHER_/cmd_vel']
    assert not d.snapshot()['ready'] and d.prepare()[0]==409
    d.graph_errors=[];d.graph_time=web.now()-2
    assert not d.snapshot()['ready']
    d.graph_time=web.now();d.busy=True
    assert not d.snapshot()['ready']
    assert 'rospy' not in sys.modules and 'serial' not in sys.modules
    r=dict(status='DASHBOARD_OFFLINE_REVIEW_PASSED',cases=14,hardware_opened=False,ssh_executed=False,
           ros_imported=False,stale_scans_blocked=True,foreign_publishers_blocked=True,
           expired_graph_blocked=True,invalid_tokens_blocked=True,confirmation_required=True)
    with os.fdopen(os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(r,f,indent=2)
    print(json.dumps(r))

if __name__=='__main__':main()
