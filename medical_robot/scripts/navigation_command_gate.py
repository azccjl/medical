#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Observe by default. Output requires explicit flags and field evidence."""
from __future__ import print_function
import argparse,hashlib,json,math,os,sys,threading,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from navigation_policy import acceptance_errors,command_policy


def lease_is_active(item,monotonic_now):
    return bool(item and 0<=monotonic_now-item[0]<=.20 and item[1] is True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--acceptance',required=True);p.add_argument('--map-sha',required=True)
    p.add_argument('--enable-output',action='store_true');p.add_argument('--site-ready-confirmed',action='store_true')
    p.add_argument('--audit',required=True)
    p.add_argument('--scan-topic',choices=('/scan',),default='/scan',help='Original M10 scan; do not use SLAM resampling for motion clearance')
    p.add_argument('--clearance-policy',choices=('full-scan','forward-map'),default='full-scan')
    p.add_argument('--static-map',help='Map YAML matching --map-sha; required for forward-map policy')
    a=p.parse_args();cert=json.load(open(a.acceptance))
    errors=acceptance_errors(cert,a.map_sha)
    if a.clearance_policy=='forward-map' and cert.get('clearance_policy')!='forward-map':
        errors.append('FORWARD_MAP_FIELD_POLICY_NOT_ACCEPTED')
    if a.enable_output and (errors or not a.site_ready_confirmed):
        print(json.dumps(dict(status='REFUSED_BEFORE_ROS',errors=errors or ['SITE_CONFIRMATION_REQUIRED'])));return 2
    clearance_map=None
    if a.clearance_policy=='forward-map':
        if not a.static_map:raise ValueError('STATIC_MAP_REQUIRED_FOR_FORWARD_POLICY')
        import yaml
        meta=yaml.safe_load(open(a.static_map))
        image=meta['image']
        if not os.path.isabs(image):image=os.path.join(os.path.dirname(a.static_map),image)
        if hashlib.sha256(open(image,'rb').read()).hexdigest()!=a.map_sha:
            raise ValueError('CLEARANCE_MAP_IDENTITY_CHANGED')
        from site_localization_view import load_map
        clearance_map=load_map(a.static_map)
    import rospy,rosgraph
    from geometry_msgs.msg import Twist,PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String
    import ctypes
    class TS(ctypes.Structure):_fields_=[('s',ctypes.c_long),('ns',ctypes.c_long)]
    lib=ctypes.CDLL('librt.so.1')
    def now():
        t=TS()
        if lib.clock_gettime(1,ctypes.byref(t)):raise RuntimeError('MONOTONIC_FAILED')
        return t.s+t.ns/1e9
    sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'heading_fix'))
    from medical_stop_window import StopWindow
    rospy.init_node('medical_navigation_command_gate')
    master=rosgraph.Master(rospy.get_name());lock=threading.RLock();stop=StopWindow()
    os.close(os.open(a.audit+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
    audit=os.fdopen(os.open(a.audit,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w')
    state=dict(odom=None,scan=None,pose=None,command=None,armed=False,fault=None,scan_received=None,lease=None)
    pub=rospy.Publisher('/medical_navigation/gate_status',String,queue_size=1,latch=True)
    output=rospy.Publisher('/medical_navigation_gated_cmd_vel',Twist,queue_size=1,latch=False) if a.enable_output else None
    def record(event,**kw):
        with lock:
            kw.update(event=event,mono=now(),wall=time.time());audit.write(json.dumps(kw,allow_nan=False)+'\n');audit.flush()
    def fault(reason):
        with lock:state['fault']=reason;state['armed']=False
        if output:output.publish(Twist())
        record('FAULT',reason=reason)
    def odom(m):
        t=now();age=(rospy.Time.now()-m.header.stamp).to_sec();v=m.twist.twist
        q=m.pose.pose.orientation;n=sum(x*x for x in (q.x,q.y,q.z,q.w))
        if m.header.frame_id!='odom' or m.child_frame_id!='base_footprint' or not -.02<=age<=.20 or abs(n-1)>.02:
            fault('INVALID_ODOM');return
        with lock:
            state['odom']=(t,m);stop.feed(dict(t=t,stamp=m.header.stamp.to_sec(),vx=v.linear.x,vy=v.linear.y,wz=v.angular.z))
    def scan(m):
        with lock:state['scan']=m;state['scan_received']=now()
    def pose(m):
        with lock:state['pose']=(now(),m)
    def lease(m):
        try:
            if getattr(m,'_connection_header',{}).get('callerid')!='/medical_route_action_runner':raise ValueError('UNEXPECTED_ROUTE_LEASE_CALLER')
            data=json.loads(m.data)
            if not isinstance(data.get('active'),bool) or not 0<=time.time()-data.get('wall',0)<=.20:raise ValueError('INVALID_ROUTE_LEASE')
            with lock:
                state['lease']=(now(),data['active'])
                if not data['active']:
                    state['command']=None;state['armed']=False
                    if output:output.publish(Twist())
        except (ValueError,TypeError) as exc:fault(str(exc))
    def lease_ready():
        return lease_is_active(state['lease'],now())
    def graph():
        publishers,subscribers,unused=master.getSystemState()
        ps,ss=dict(publishers),dict(subscribers)
        if ps.get('/medical_field_candidate/cmd_vel')!=['/medical_field_move_base']:
            raise ValueError('NAVIGATION_COMMAND_PUBLISHER_NOT_UNIQUE')
        if output:
            if ps.get('/medical_navigation_gated_cmd_vel')!=[rospy.get_name()]:raise ValueError('GATED_PUBLISHER_CONFLICT')
            if ss.get('/medical_navigation_gated_cmd_vel')!=['/medical_navigation_audited_base']:
                raise ValueError('VALIDATED_BASE_SUBSCRIBER_REQUIRED')
            if ps.get('/medical_navigation/route_lease')!=['/medical_route_action_runner']:
                raise ValueError('ROUTE_LEASE_PUBLISHER_NOT_UNIQUE')
        for topic in ('/cmd_vel','/medical_ground_cmd_vel','/medical_nav_cmd_vel','/joy_raw','/move_base_simple/goal'):
            if ps.get(topic):raise ValueError('FOREIGN_CONTROL_PUBLISHER_'+topic)
        if ps.get('/odom')!=['/medical_navigation_audited_base'] and output:raise ValueError('UNEXPECTED_ODOM_SOURCE')
    def live_guard(v,w):
        t=now()
        with lock:o=state['odom'];s=state['scan'];pr=state['pose'];sr=state['scan_received']
        if o is None or not 0<=t-o[0]<=.20:raise ValueError('ODOM_STALE')
        if s is None or not 0<=t-sr<=.30 or not -.02<=(rospy.Time.now()-s.header.stamp).to_sec()<=.30:
            raise ValueError('SCAN_STALE')
        if pr is None or not 0<=t-pr[0]<=1 or not -.02<=(rospy.Time.now()-pr[1].header.stamp).to_sec()<=1:
            raise ValueError('AMCL_STALE')
        covariance=pr[1].pose.covariance
        if any(math.isnan(covariance[i]) or math.isinf(covariance[i]) or covariance[i]<0 for i in (0,7,35)):
            raise ValueError('AMCL_INVALID')
        if max(covariance[0],covariance[7])>.01 or covariance[35]>math.radians(8)**2:
            raise ValueError('AMCL_UNCERTAINTY_TOO_HIGH')
        if a.clearance_policy=='forward-map':
            from navigation_forward_map_guard_candidate import evaluate
            p=pr[1].pose.pose;q=p.orientation
            pose=dict(x=p.position.x,y=p.position.y,
                yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
            result=evaluate(s,clearance_map,pose,
                [math.sqrt(covariance[0]),math.sqrt(covariance[7])],math.sqrt(covariance[35]),
                (rospy.Time.now()-pr[1].header.stamp).to_sec(),
                (rospy.Time.now()-s.header.stamp).to_sec(),v,w,cert['measured_max_stop_distance_m'])
            if not result['passed']:
                raise ValueError(result['map']['error'] or result['scan']['error'])
        else:
            from navigation_scan_guard import swept_scan_guard
            swept_scan_guard(s,v,w,cert['measured_max_stop_distance_m'])
        graph()
    def command(m):
        caller=getattr(m,'_connection_header',{}).get('callerid')
        if caller!='/medical_field_move_base':fault('UNEXPECTED_COMMAND_CALLER');return
        if any(getattr(m.linear,k)!=0 for k in ('y','z')) or any(getattr(m.angular,k)!=0 for k in ('x','y')):
            fault('UNSUPPORTED_TWIST_AXES');return
        if not a.enable_output:
            record('OBSERVED_COMMAND_NO_OUTPUT',v=m.linear.x,w=m.angular.z);return
        with lock:
            if (m.linear.x or m.angular.z) and not lease_ready():
                record('COMMAND_WITHOUT_ACTIVE_ROUTE_IGNORED');return
        try:
            values=command_policy(m.linear.x,m.angular.z,cert)
            with lock:
                if state['fault']:raise ValueError(state['fault'])
                if values['v']:
                    live_guard(values['v'],values['w'])
                    if not state['armed']:
                        if not stop.evidence(now())['passed']:raise ValueError('STRICT_BASELINE_STOP_REQUIRED')
                        state['armed']=True
                else:state['armed']=False
                state['command']=(now(),m)
            record('COMMAND_ACCEPTED',**values)
        except ValueError as exc:fault(str(exc))
    def tick(event):
        with lock:
            item=state['command'];error=state['fault'];armed=state['armed']
            m=Twist()
            if output and armed and not error and not lease_ready():fault('ROUTE_LEASE_TIMEOUT')
            elif output and not error and item and 0<=now()-item[0]<=.20:
                try:
                    if item[1].linear.x:live_guard(item[1].linear.x,item[1].angular.z)
                    m=item[1]
                except ValueError as exc:fault(str(exc))
            elif output and armed and not error:fault('COMMAND_WATCHDOG_TIMEOUT')
            if output:output.publish(m)
            pub.publish(String(json.dumps(dict(output_enabled=a.enable_output,armed=state['armed'],fault=state['fault'],field_blockers=errors,
                         clearance_policy=a.clearance_policy,rear_laser_required=a.clearance_policy=='full-scan',
                         strict_stop_available=stop.evidence(now())['passed'],wall=time.time()))))
    rospy.Subscriber('/odom',Odometry,odom,queue_size=1,tcp_nodelay=True)
    rospy.Subscriber('/amcl_pose',PoseWithCovarianceStamped,pose,queue_size=1)
    rospy.Subscriber('/medical_navigation/route_lease',String,lease,queue_size=1,tcp_nodelay=True)
    rospy.Subscriber(a.scan_topic,LaserScan,scan,queue_size=1,tcp_nodelay=True)
    rospy.Subscriber('/medical_field_candidate/cmd_vel',Twist,command,queue_size=1,tcp_nodelay=True)
    timer=rospy.Timer(rospy.Duration(.05),tick)
    record('GATE_START',output_enabled=a.enable_output,field_blockers=errors,scan_topic=a.scan_topic,
           clearance_policy=a.clearance_policy,static_map=a.static_map)
    try:rospy.spin()
    finally:
        if output:
            for unused in range(5):output.publish(Twist());time.sleep(.02)
        record('GATE_END');audit.close()
    return 0


if __name__=='__main__':sys.exit(main())
