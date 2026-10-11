#!/usr/bin/env python2
"""Software checks and map screening. No ROS imports, serial or SSH."""
from __future__ import print_function
import argparse,json,math,os,sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--scripts',required=True);p.add_argument('--raw-map',required=True)
    p.add_argument('--structured-map',required=True);p.add_argument('--acceptance',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();sys.path.insert(0,a.scripts)
    from route_geometry import fillet_route,screen_route,body_collision
    from site_localization_view import load_map
    from navigation_policy import acceptance_errors,command_policy,CHECKS
    from navigation_audited_base import frame_policy,crc8,velocity_frame
    from navigation_scan_guard import swept_scan_guard
    from route_workbench import control_transition
    from navigation_command_gate import lease_is_active
    count=0
    def reject(fn):
        try:fn()
        except (ValueError,TypeError):return
        raise AssertionError('EXPECTED_REJECTION')
    for points,radius in [([], .75),([[0,0],[.01,0]],.75),([[0,0],[1,0],[0,0]],.75),
                          ([[0,0],[.2,0],[.2,.2]],.75),([[0,0],[float('nan'),1]],.75),([[0,0],[1,1]],.01)]:
        reject(lambda:fillet_route(points,radius));count+=1
    route=fillet_route([[1,1],[4,1],[4,4]],.75)
    assert max(abs(p['curvature']) for p in route['path'])<=1/.75+1e-9
    assert abs(route['path'][0]['yaw'])<1e-9 and abs(route['path'][-1]['yaw']-math.pi/2)<1e-9;count+=1
    assert all(math.hypot(b['x']-a['x'],b['y']-a['y'])<=.01501 for a,b in zip(route['path'][:-1],route['path'][1:]));count+=1
    grid=dict(width=200,height=200,resolution=.05,origin=[0,0,0],data=[0]*40000)
    assert screen_route(grid,route)['passed'];count+=1
    pose=route['path'][0];grid['data'][20*200+20]=100
    assert body_collision(grid,pose)=='OCCUPIED_CELL';count+=1
    grid['data'][20*200+20]=-1;assert body_collision(grid,pose)=='UNKNOWN_CELL';count+=1
    assert body_collision(grid,dict(x=-1,y=-1,yaw=0))=='OUTSIDE_MAP';count+=1
    cert=json.load(open(a.acceptance));assert acceptance_errors(cert);count+=1
    reject(lambda:command_policy(.1,0,cert));count+=1
    approved=json.loads(json.dumps(cert));approved.update(status='FIELD_ACCEPTED',measured_min_turn_radius_m=.55,
                      measured_min_reliable_speed_m_s=.10,measured_max_stop_distance_m=.10,map_pgm_sha256='OFFLINE_FIXTURE')
    for k in CHECKS:approved['checks'][k]=dict(passed=True,evidence='OFFLINE_TEST_ONLY_NOT_FIELD_EVIDENCE')
    assert command_policy(.10,.10,approved)['v']==.10;count+=1
    for v,w in [(.05,0),(-.1,0),(0,.1),(.13,0),(.1,1),(float('nan'),0)]:
        reject(lambda:command_policy(v,w,approved));count+=1
    assert acceptance_errors(approved,'OTHER_MAP');count+=1
    assert command_policy(0,0,cert)['v']==0;count+=1
    slow=json.loads(json.dumps(approved));slow['measured_min_reliable_speed_m_s']=.01
    for v in (.01,.02,.05,.10):
        assert command_policy(v,0,slow)['v']==v
        b=velocity_frame(v,0);assert (b[4]*256+b[5])/1000.==v
        frame_policy(b,'velocity',slow,True);count+=1
    reject(lambda:command_policy(.005,0,slow));count+=1
    assert control_transition('RUN','PAUSE')=='PAUSE';count+=1
    assert control_transition('PAUSE','RUN')=='RUN';count+=1
    assert control_transition('RUN','STOP')=='STOP';count+=1
    reject(lambda:control_transition('STOP','RUN'));count+=1
    reject(lambda:control_transition('STOP','PAUSE'));count+=1
    assert lease_is_active((10.,True),10.1);count+=1
    assert not lease_is_active(None,10.1);count+=1
    assert not lease_is_active((10.,True),10.21);count+=1
    assert not lease_is_active((10.,True),9.99);count+=1
    assert not lease_is_active((10.,False),10.1);count+=1
    def frame(v,steer=0):
        v=int(v*1000);s=int(steer*1000);b=[0x5a,18,1,1,(v>>8)&255,v&255,0,0,(s>>8)&255,s&255,0x27,0x10,3,0xe8,0,0,0]
        return bytearray(b+[crc8(b)])
    frame_policy(frame(0),'velocity',cert,False);count+=1
    frame_policy(frame(.10,.10),'velocity',approved,True);count+=1
    for b,label,allowed in [(frame(.1),'velocity',False),(frame(.05),'velocity',True),(frame(-.1),'velocity',True),
                             (frame(.1,.5),'velocity',True),(frame(0),'battery_query',True)]:
        reject(lambda:frame_policy(b,label,approved,allowed));count+=1
    class M(object):pass
    m=M();m.header=M();m.header.frame_id='base_laser_link';m.angle_min=-math.pi;m.angle_increment=2*math.pi/720
    m.range_min=.10;m.range_max=100.;m.ranges=[3.]*720
    assert swept_scan_guard(m,.1,0,.10)['passed'];count+=1
    m.ranges[360]=float('inf');reject(lambda:swept_scan_guard(m,.1,0,.1));count+=1
    m.ranges[360]=.30;reject(lambda:swept_scan_guard(m,.1,0,.1));count+=1
    m.ranges[360]=float('nan');reject(lambda:swept_scan_guard(m,.1,0,.1));count+=1
    maps={name:load_map(path) for name,path in [('raw',a.raw_map),('structured',a.structured_map)]}
    candidate=fillet_route([[-.35,.075],[.9,.075],[.9,3.55],[-2.4,3.55],[-2.4,.075],[-.35,.075]],.75)
    screens={name:screen_route(g,candidate) for name,g in maps.items()}
    assert all(s['passed'] for s in screens.values());count+=1
    assert 'rospy' not in sys.modules and 'serial' not in sys.modules
    for filename in ('route_geometry.py','route_workbench.py','navigation_policy.py','navigation_scan_guard.py',
                     'navigation_audited_base.py','navigation_command_gate.py','route_action_runner.py'):
        with open(os.path.join(a.scripts,filename),'rb') as f:compile(f.read(),filename,'exec')
    report=dict(status='PRE_NAVIGATION_SOFTWARE_REVIEW_PASSED',checks=count,motion_sent=False,ros_imported=False,
                field_acceptance=False,outer_candidate=dict(length_m=candidate['length_m'],min_turn_radius_m=.75,
                samples=len(candidate['path']),screens=screens),note='Synthetic calibration fixture used only in memory, never saved as approval.')
    with os.fdopen(os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
