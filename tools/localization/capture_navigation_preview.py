#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Calls GetPlan only; does not publish navigation goals or driving commands."""
from __future__ import print_function
import os, json, math, time, urllib2
import rospy, rosgraph
from geometry_msgs.msg import PoseStamped
from nav_msgs.srv import GetPlan

output='/home/ncut/medical_localization_assets_20261011/navigation-plan-preview-v2-20261011.json'
if os.path.exists(output):raise RuntimeError('PRESERVE_EXISTING_OUTPUT')
os.close(os.open(output+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
rospy.init_node('medical_navigation_preview_get_plan',anonymous=True)
master=rosgraph.Master(rospy.get_name())
def verify():
    pubs,subs,services=master.getSystemState()
    for topic,nodes in pubs:
        if topic in ('/medical_ground_cmd_vel','/cmd_vel','/medical_nav_cmd_vel',
                     '/medical_navigation_preview/goal','/medical_navigation_preview/simple_goal',
                     '/move_base/goal','/move_base_simple/goal') and nodes:
            raise RuntimeError('UNEXPECTED_CONTROL_PUBLISHER %r' % ((topic,nodes),))
    preview_subs=dict(subs).get('/medical_nav_preview_cmd_vel',[])
    if preview_subs:raise RuntimeError('PREVIEW_OUTPUT_HAS_SUBSCRIBERS %r' % preview_subs)
    # move_base advertises an internal goal forwarder; it emits only on simple_goal input.
    forwarders=dict(pubs).get('/medical_preview_action/goal',[])
    if forwarders != ['/medical_navigation_preview']:
        raise RuntimeError('PREVIEW_ACTION_HAS_EXTERNAL_GOAL_PUBLISHER %r' % forwarders)
    if '/base_control' not in dict(subs).get('/medical_ground_cmd_vel',[]):
        raise RuntimeError('BASE_SUBSCRIPTION_CHANGED')
    return dict(publishers=pubs,subscribers=subs)
report=dict(status='INCOMPLETE',motion_sent=False,checks=[],plans=[])
try:
    report['checks'].append(verify())
    state=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
    if not state['pose']['fresh']:raise RuntimeError('STALE_LOCALIZATION')
    rospy.wait_for_service('/medical_navigation_preview/make_plan',timeout=20)
    request=rospy.ServiceProxy('/medical_navigation_preview/make_plan',GetPlan)
    # First short straight and four outer-channel positions; service only.
    positions=[('short_straight',.34356,-.026359,0.),
               ('bottom_right',.54356,-.026359,0.),
               ('upper_right',.94356,3.123641,math.pi/2),
               ('upper_left',-2.45644,3.123641,math.pi),
               ('lower_left',-2.45644,.623641,-math.pi/2)]
    p=state['pose']
    for name,x,y,yaw in positions:
        report['checks'].append(verify())
        start=PoseStamped();start.header.frame_id='map';start.header.stamp=rospy.Time.now()
        start.pose.position.x=p['x'];start.pose.position.y=p['y']
        start.pose.orientation.z=math.sin(p['yaw']/2);start.pose.orientation.w=math.cos(p['yaw']/2)
        goal=PoseStamped();goal.header=start.header
        goal.pose.position.x=x;goal.pose.position.y=y
        goal.pose.orientation.z=math.sin(yaw/2);goal.pose.orientation.w=math.cos(yaw/2)
        answer=request(start,goal,0.)
        rows=[dict(x=v.pose.position.x,y=v.pose.position.y,
                   q=[v.pose.orientation.x,v.pose.orientation.y,v.pose.orientation.z,v.pose.orientation.w])
              for v in answer.plan.poses]
        report['plans'].append(dict(name=name,goal=[x,y,yaw],poses=rows))
    report['checks'].append(verify())
    report['footprint']=rospy.get_param('/medical_navigation_preview/global_costmap/footprint')
    report['status']='PLANS_CAPTURED_NO_GOALS_SENT'
    report['note']='Navfn paths are not Ackermann feasibility or clearance approval.'
except Exception as exc:report['error']=str(exc)
finally:
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle:
        json.dump(report,handle,indent=2,allow_nan=False)
print(report['status'],report.get('error'),[(r['name'],len(r['poses'])) for r in report['plans']])
raise SystemExit(0 if report['status']=='PLANS_CAPTURED_NO_GOALS_SENT' else 1)
