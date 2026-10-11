#!/usr/bin/env python2
"""GetPlan service checks only on local synthetic master. No action goals."""
from __future__ import print_function
import os,json,math,argparse
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
if os.environ.get('ROS_MASTER_URI')!='http://127.0.0.1:11312':raise RuntimeError('ISOLATED_MASTER_REQUIRED')
import rospy,rosgraph
from geometry_msgs.msg import PoseStamped
from nav_msgs.srv import GetPlan
rospy.init_node('medical_isolated_get_plan_review')
master=rosgraph.Master(rospy.get_name());rospy.wait_for_service('/medical_field_move_base/make_plan',timeout=20)
request=rospy.ServiceProxy('/medical_field_move_base/make_plan',GetPlan)
rows=[]
for name,x,y,h in [('short_straight',.15,.075,0),('upper_right',.9,3.55,math.pi/2),('upper_left',-2.4,3.55,math.pi)]:
    start=PoseStamped();start.header.frame_id='map';start.header.stamp=rospy.Time.now()
    start.pose.position.x=-.35;start.pose.position.y=.075;start.pose.orientation.w=1
    goal=PoseStamped();goal.header=start.header;goal.pose.position.x=x;goal.pose.position.y=y
    goal.pose.orientation.z=math.sin(h/2);goal.pose.orientation.w=math.cos(h/2)
    result=request(start,goal,0)
    rows.append(dict(name=name,pose_count=len(result.plan.poses)))
    if not result.plan.poses:raise RuntimeError('EMPTY_PLAN_'+name)
publishers,subscribers,unused=master.getSystemState()
assert not dict(subscribers).get('/medical_field_candidate/cmd_vel')
assert not dict(publishers).get('/medical_navigation_gated_cmd_vel')
assert not dict(publishers).get('/medical_field_move_base/simple_goal')
assert not any('audited_base' in n for topic,nodes in publishers for n in nodes)
report=dict(status='ISOLATED_MOVE_BASE_NAVFN_TEB_LOADED_AND_GETPLAN_PASSED',plans=rows,
            local_planner=rospy.get_param('/medical_field_move_base/base_local_planner'),
            global_planner=rospy.get_param('/medical_field_move_base/base_global_planner'),
            radius=rospy.get_param('/medical_field_move_base/TebLocalPlannerROS/min_turning_radius'),
            ros_master=os.environ['ROS_MASTER_URI'],sensor_data='SYNTHETIC_SOFTWARE_FIXTURE_ONLY',
            action_goals_sent=0,physical_robot_connected=False,command_output_subscribers=[])
out=a.output
with os.fdopen(os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
