#!/usr/bin/env python2
"""Prepare by default; field-approved route sends sequential move_base goals."""
from __future__ import print_function
import argparse,json,math,os,sys,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from navigation_policy import acceptance_errors


def main():
    p=argparse.ArgumentParser();p.add_argument('--route',required=True);p.add_argument('--acceptance',required=True)
    p.add_argument('--execute-route',action='store_true');p.add_argument('--site-ready-confirmed',action='store_true')
    p.add_argument('--audit');p.add_argument('--control-file');a=p.parse_args();r=json.load(open(a.route));cert=json.load(open(a.acceptance))
    sha=r['map_hashes']['raw']['pgm_sha256'];errors=acceptance_errors(cert,sha)
    for name in ('raw','structured'):
        if not r.get('screens',{}).get(name,{}).get('passed'):errors.append('ROUTE_MAP_SCREEN_FAILED_'+name)
    if r['min_turn_radius_m']<max(.75,cert.get('measured_min_turn_radius_m') or .75):errors.append('ROUTE_TURN_RADIUS_TOO_SMALL')
    if not a.execute_route:
        print(json.dumps(dict(status='PREPARED_ONLY',errors=errors,goals_sent=0,ros_imported=False)));return 0
    if errors or not a.site_ready_confirmed or not a.audit:
        print(json.dumps(dict(status='REFUSED_BEFORE_ROS',errors=errors or ['SITE_CONFIRMATION_AND_NEW_AUDIT_REQUIRED'])));return 2
    import rospy,actionlib,rosgraph
    from move_base_msgs.msg import MoveBaseAction,MoveBaseGoal
    from std_msgs.msg import String
    from geometry_msgs.msg import PoseWithCovarianceStamped
    rospy.init_node('medical_route_action_runner')
    os.close(os.open(a.audit+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
    log=os.fdopen(os.open(a.audit,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w')
    def record(event,**k):k.update(event=event,wall=time.time());log.write(json.dumps(k)+'\n');log.flush()
    client=actionlib.SimpleActionClient('/medical_field_move_base',MoveBaseAction)
    lease_active=[False]
    lease_pub=rospy.Publisher('/medical_navigation/route_lease',String,queue_size=1,latch=False)
    def lease_tick(unused=None):lease_pub.publish(String(json.dumps(dict(active=lease_active[0],wall=time.time()))))
    lease_timer=rospy.Timer(rospy.Duration(.05),lease_tick)
    def control_request():
        if a.control_file:
            try:value=open(a.control_file).read().strip()
            except IOError:raise RuntimeError('CONTROL_FILE_UNAVAILABLE')
            if value not in ('RUN','PAUSE','STOP'):raise RuntimeError('CONTROL_FILE_INVALID')
            return value
        return 'RUN'
    def ready(require_stop=False):
        m=rospy.wait_for_message('/medical_navigation/gate_status',String,timeout=2);s=json.loads(m.data)
        if not s['output_enabled'] or s['fault'] or not 0<=time.time()-s.get('wall',0)<=.3:raise RuntimeError('GATE_NOT_READY')
        graph=dict(rosgraph.Master(rospy.get_name()).getSystemState()[0])
        if graph.get('/medical_field_move_base/goal') not in (None,[],[rospy.get_name()]):raise RuntimeError('OTHER_GOAL_PUBLISHER')
        return s.get('strict_stop_available',False) if require_stop else True
    def await_stop():
        deadline=time.time()+15
        while not rospy.is_shutdown() and time.time()<deadline:
            if control_request()=='STOP':raise RuntimeError('OPERATOR_CANCELLED')
            if ready(True):return
            rospy.sleep(.1)
        raise RuntimeError('STRICT_STOP_BEFORE_SEGMENT_UNAVAILABLE')
    def await_run():
        while not rospy.is_shutdown():
            request=control_request()
            if request=='STOP':raise RuntimeError('OPERATOR_CANCELLED')
            if request=='RUN':return
            ready();rospy.sleep(.1)
        raise RuntimeError('ROS_SHUTDOWN')
    try:
        ready()
        if not client.wait_for_server(rospy.Duration(3)):raise RuntimeError('MOVE_BASE_UNAVAILABLE')
        m=rospy.wait_for_message('/amcl_pose',PoseWithCovarianceStamped,timeout=2)
        q=m.pose.pose.orientation;h=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z));start=r['path'][0]
        if (not -.02<=(rospy.Time.now()-m.header.stamp).to_sec()<=1 or
            math.hypot(m.pose.pose.position.x-start['x'],m.pose.pose.position.y-start['y'])>.10 or
            abs(math.atan2(math.sin(h-start['yaw']),math.cos(h-start['yaw'])))>.15):
            raise RuntimeError('ROUTE_START_POSE_MISMATCH')
        targets=[];distance=0
        for prev,item in zip(r['path'][:-1],r['path'][1:]):
            distance+=math.hypot(item['x']-prev['x'],item['y']-prev['y'])
            if distance>=.35:targets.append(item);distance=0
        targets.append(r['path'][-1])
        for i,t in enumerate(targets):
            ready();await_run();await_stop();await_run();goal=MoveBaseGoal();goal.target_pose.header.frame_id='map';goal.target_pose.header.stamp=rospy.Time.now()
            goal.target_pose.pose.position.x=t['x'];goal.target_pose.pose.position.y=t['y']
            goal.target_pose.pose.orientation.z=math.sin(t['yaw']/2);goal.target_pose.pose.orientation.w=math.cos(t['yaw']/2)
            record('GOAL',index=i,target=t);lease_active[0]=True;lease_tick();client.send_goal(goal)
            deadline=time.time()+30
            while time.time()<deadline and not rospy.is_shutdown():
                request=control_request()
                if request=='STOP':raise RuntimeError('OPERATOR_CANCELLED')
                if request=='PAUSE':
                    lease_active[0]=False;lease_tick();client.cancel_goal();record('PAUSED',index=i)
                    while control_request()=='PAUSE' and not rospy.is_shutdown():ready();rospy.sleep(.1)
                    if control_request()=='STOP':raise RuntimeError('OPERATOR_CANCELLED')
                    await_stop();goal.target_pose.header.stamp=rospy.Time.now();lease_active[0]=True;lease_tick();client.send_goal(goal)
                    record('RESUMED',index=i);deadline=time.time()+30
                ready()
                if client.wait_for_result(rospy.Duration(.2)):break
            else:raise RuntimeError('SEGMENT_TIMEOUT')
            if client.get_state()!=3:raise RuntimeError('MOVE_BASE_SEGMENT_FAILED_'+str(client.get_state()))
            lease_active[0]=False;lease_tick()
            record('SEGMENT_SUCCEEDED',index=i)
        await_stop()
        record('ROUTE_GOALS_SUCCEEDED_AWAITING_PHYSICAL_STOP')
    except Exception as exc:record('ROUTE_ABORT',error=str(exc));raise
    finally:
        lease_active[0]=False
        for unused in range(5):lease_tick();time.sleep(.02)
        lease_timer.shutdown();client.cancel_all_goals();record('GOALS_CANCELLED_ON_EXIT');log.close()
    return 0


if __name__=='__main__':sys.exit(main())
