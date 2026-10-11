#!/usr/bin/env python2
"""Mock action workflow only. No ROS master, network or serial connection."""
from __future__ import print_function
import argparse,json,os,sys,types,time

p=argparse.ArgumentParser();p.add_argument('--scripts',required=True);p.add_argument('--acceptance',required=True)
p.add_argument('--output-dir',required=True);a=p.parse_args();sys.path.insert(0,a.scripts)
import route_action_runner as runner
from route_geometry import fillet_route
from navigation_policy import CHECKS
template=json.load(open(a.acceptance));approved=json.loads(json.dumps(template))
approved.update(status='FIELD_ACCEPTED',map_pgm_sha256='MOCK_ONLY',measured_min_turn_radius_m=.75,
                measured_min_reliable_speed_m_s=.01,measured_max_stop_distance_m=.1)
for key in CHECKS:approved['checks'][key]=dict(passed=True,evidence='IN_MEMORY_MOCK_ONLY')
route=fillet_route([[0,0],[.5,0]],.75)
route.update(map_hashes={'raw':{'pgm_sha256':'MOCK_ONLY'}},screens={'raw':{'passed':True},'structured':{'passed':True}})
class Obj(object):pass
def module(name):
    m=types.ModuleType(name);sys.modules[name]=m;return m
def make_goal():
    g=Obj();g.target_pose=Obj();g.target_pose.header=Obj();g.target_pose.pose=Obj()
    g.target_pose.pose.position=Obj();g.target_pose.pose.orientation=Obj();return g
class Stamp(object):
    def __sub__(self,other):return self
    def to_sec(self):return 0.
rospy=module('rospy');rospy.init_node=lambda n:None;rospy.get_name=lambda:'/medical_route_action_runner'
rospy.is_shutdown=lambda:False;rospy.Duration=lambda v:v
lease_messages=[]
rospy.Publisher=lambda *args,**kwargs:type('Publisher',(object,),{'publish':lambda s,m:lease_messages.append(json.loads(m.data))})()
rospy.Timer=lambda *args,**kwargs:type('Timer',(object,),{'shutdown':lambda s:None})()
rospy.Time=Obj();rospy.Time.now=lambda:Stamp()
module('move_base_msgs');move=module('move_base_msgs.msg');move.MoveBaseAction=Obj;move.MoveBaseGoal=make_goal
module('std_msgs');std=module('std_msgs.msg')
class String(object):
    def __init__(self,data):self.data=data
std.String=String
module('geometry_msgs');geo=module('geometry_msgs.msg');geo.PoseWithCovarianceStamped=Obj
rosgraph=module('rosgraph');rosgraph.Master=lambda n:Obj()
rosgraph.Master=lambda n:type('Master',(object,),{'getSystemState':lambda s:[[],[],[]]})()
def message(topic,kind,timeout=0):
    m=Obj()
    if topic.endswith('gate_status'):
        m.data=json.dumps(dict(output_enabled=True,fault=None,wall=time.time(),strict_stop_available=True));return m
    m.header=Obj();m.header.stamp=Stamp();m.pose=Obj();m.pose.pose=Obj();m.pose.pose.position=Obj()
    m.pose.pose.position.x=0;m.pose.pose.position.y=0;m.pose.pose.orientation=Obj()
    q=m.pose.pose.orientation;q.x=q.y=q.z=0;q.w=1;return m
rospy.wait_for_message=message
actionlib=module('actionlib');rows=[];original_load=json.load
os.makedirs(a.output_dir)
for mode in ('normal','pause_resume','cancel'):
    control=os.path.join(a.output_dir,mode+'.control');audit=os.path.join(a.output_dir,mode+'.jsonl')
    with open(control,'w') as f:f.write('RUN')
    counters={'sent':0,'cancelled':0,'ticks':0,'paused':False}
    class Client(object):
        def wait_for_server(self,d):return True
        def send_goal(self,g):counters['sent']+=1
        def cancel_goal(self):counters['cancelled']+=1
        def cancel_all_goals(self):counters['cancelled']+=1
        def get_state(self):return 3
        def wait_for_result(self,d):
            counters['ticks']+=1
            if counters['ticks']==1 and mode!='normal':
                with open(control,'w') as f:f.write('PAUSE' if mode=='pause_resume' else 'STOP')
                return False
            return True
    actionlib.SimpleActionClient=lambda *unused:Client()
    def sleep(d):
        if open(control).read()=='PAUSE':
            counters['paused']=True
            with open(control,'w') as f:f.write('RUN')
    rospy.sleep=sleep
    # Calibration fixture exists only in memory; no approval file is created.
    json.load=lambda f:approved if f.name==a.acceptance else route if f.name.endswith('route-mock.json') else original_load(f)
    routefile=os.path.join(a.output_dir,'route-mock.json')
    if not os.path.exists(routefile):
        with open(routefile,'w') as f:json.dump(route,f)
    sys.argv=['runner','--route',routefile,'--acceptance',a.acceptance,'--execute-route','--site-ready-confirmed',
              '--audit',audit,'--control-file',control]
    error=None
    try:assert runner.main()==0
    except RuntimeError as exc:error=str(exc)
    events=[json.loads(line)['event'] for line in open(audit)]
    if mode=='cancel':assert error=='OPERATOR_CANCELLED' and 'ROUTE_ABORT' in events
    else:assert error is None and 'ROUTE_GOALS_SUCCEEDED_AWAITING_PHYSICAL_STOP' in events
    if mode=='pause_resume':assert counters['paused'] and 'PAUSED' in events and 'RESUMED' in events
    assert events[-1]=='GOALS_CANCELLED_ON_EXIT'
    assert lease_messages[-1]['active'] is False and any(m['active'] for m in lease_messages)
    rows.append(dict(mode=mode,counters=counters,events=events,error=error))
json.load=original_load
report=dict(status='MOCK_ROUTE_CONTROL_PASSED',cases=rows,physical_motion_sent=False,ros_master_connected=False,
            calibration_fixture='IN_MEMORY_ONLY_NOT_FIELD_EVIDENCE')
with open(os.path.join(a.output_dir,'review.json'),'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
