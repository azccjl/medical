#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# No motion unless all three explicit execution flags are given.
from __future__ import print_function
import os,sys,json,time,math,signal,socket,threading,hashlib
import argparse
parser=argparse.ArgumentParser(description="One supervised 0.10 m/s pulse, maximum 0.50 seconds. Upload alone never executes it.")
parser.add_argument('--execute',action='store_true')
parser.add_argument('--clear-floor',action='store_true')
parser.add_argument('--power-stop-confirmed',action='store_true')
args=parser.parse_args()
if not (args.execute and args.clear_floor and args.power_stop_confirmed):
    raise SystemExit('PREPARED_ONLY_NO_ROS_COMMANDS: explicit execute andonsite confirmations required')
import medical_bench_pulse_heading_v7_logclassification as safety
from medical_stop_window import StopWindow

OUT='/home/EPRobot/medical-supervised-short-pulse-v2-20261011.json'
if os.path.exists(OUT):raise SystemExit('PRESERVE_EXISTING_REPORT')
fd=os.open(OUT+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
report=dict(status='REFUSED',events=[],commands=[],odom=[],scans=[],yaw_samples=[],amcl=[],max_odom_displacement_m=.08,
            speed_m_s=.10,max_positive_seconds=.50,physical_measurement_required=True)
channel=None;subs=[];ros=None;active=True;lock=threading.RLock();stop=StopWindow();exitcode=1
try:
    helper=os.path.join(os.path.dirname(__file__),'medical_bench_pulse_heading_v7_logclassification.py')
    assert hashlib.sha256(open(helper,'rb').read()).hexdigest()=='fc2cdc6cc3cf8107878fd3d585f1bcbd4450ff9faa391885700d7853417cac46','HELPER_CHANGED'
    report['driver']=safety.driver_identity()
    safety.PULSE_SECONDS=.50;safety.SILENCE_SECONDS=.20
    socket.setdefaulttimeout(2)
    import rospy as ros
    import rosgraph
    from geometry_msgs.msg import Twist,PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    ros.init_node('medical_supervised_short_pulse_20261011',anonymous=True,disable_signals=True)
    def interrupted(signum,frame):raise KeyboardInterrupt()
    signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
    expected={'wheelbase':.17,'command_timeout':.35,'base_kv':1.,'base_kp':1000.,'base_ki':100.,'base_kd':0.,'odom_freq':50,'cmd_vel_topic':safety.TOPIC,'is_send_anger':'false','is_pub_odom_tf':'true','Laser_Mode':'Boost','port':'/dev/EPRobot_base','baudrate':115200}
    actual={k:ros.get_param('/base_control/'+k) for k in expected}
    if actual!=expected or ros.get_param('/use_sim_time') is not False:raise RuntimeError('BASE_PARAMETERS_CHANGED')
    report['parameters']=actual;report['run_id']=ros.get_param('/run_id')
    master=rosgraph.Master(ros.get_name())
    class VerifiedChannel(safety.Channel):
        def graph(self,own_publisher=False):
            safety.Channel.graph(self,own_publisher)
            types=dict(master.getTopicTypes())
            for name,pubs in master.getSystemState()[0]:
                if name=='/feedback_vel' and pubs==['/base_control']:continue
                if types.get(name) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped'):
                    if name!=safety.TOPIC or sorted(pubs)!=([ros.get_name()] if own_publisher else []):raise RuntimeError('OTHER_CONTROL_PUBLISHER '+repr((name,pubs)))
    channel=VerifiedChannel(ros,master,Twist,report)
    def amcl_callback(m):
        p=m.pose.pose
        with lock:
            if active:report['amcl'].append(dict(stamp=m.header.stamp.to_sec(),x=p.position.x,y=p.position.y,q=[p.orientation.x,p.orientation.y,p.orientation.z,p.orientation.w],covariance=list(m.pose.covariance)))
    latest_scan=[None]
    def odom(m):
        with lock:
            if not active:return
            channel.callback(m)
            with channel.lock:r=dict(channel.rows[-1])
            r['t']=safety.now();stop.feed(r)
            q=m.pose.pose.orientation
            if abs(sum(v*v for v in [q.x,q.y,q.z,q.w])-1)>.02:channel.errors.append('Invalid quaternion')
            report['yaw_samples'].append(dict(t=safety.now()-channel.started,stamp=m.header.stamp.to_sec(),yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))))
    def scan(m):
        with lock:
            if not active:return
            latest_scan[0]=(safety.now(),m)
            if not report['scans'] or safety.now()-report['scans'][-1]['t']>=.18:
                report['scans'].append(dict(t=safety.now(),stamp=m.header.stamp.to_sec(),frame=m.header.frame_id,angle_min=m.angle_min,angle_increment=m.angle_increment,ranges=[v if safety.finite(v) else None for v in m.ranges]))
    subs=[ros.Subscriber('/odom',Odometry,odom,queue_size=1000),ros.Subscriber('/medical_slam_scan',LaserScan,scan,queue_size=20),ros.Subscriber('/amcl_pose',PoseWithCovarianceStamped,amcl_callback,queue_size=20)]
    def corridor():
        with lock:latest=latest_scan[0]
        if latest is None or safety.now()-latest[0]>.30:raise RuntimeError('SCAN_STALE')
        m=latest[1];age=ros.Time.now().to_sec()-m.header.stamp.to_sec()
        if not -.02<=age<=.30 or m.header.frame_id!='base_laser_link':raise RuntimeError('SCAN_TIME_OR_FRAME_INVALID')
        xs=[]
        for i,r in enumerate(m.ranges):
            if math.isnan(r) or r==-float('inf'):raise RuntimeError('SCAN_INVALID')
            if not safety.finite(r):continue
            if not m.range_min<=r<=m.range_max:raise RuntimeError('SCAN_RANGE_INVALID')
            a=m.angle_min+i*m.angle_increment;x=.135+r*math.cos(a);y=r*math.sin(a)
            if x>.245 and abs(y)<=.21:xs.append(x)
        if len(xs)<3 or min(xs)<.85:raise RuntimeError('FRONT_CORRIDOR_NOT_CLEAR')
        return dict(min_x_from_base_m=min(xs),finite_returns=len(xs),automatic_obstacle_avoidance=False)
    def wait_stop(own):
        deadline=safety.now()+25
        while safety.now()<deadline:
            channel.graph(own)
            if ros.is_shutdown() or channel.errors:raise RuntimeError('ROS_OR_ODOM_ERROR')
            with lock:e=stop.evidence(safety.now())
            if e['passed']:return e
            time.sleep(.10)
        raise RuntimeError('STRICT_STOP_WINDOW_UNAVAILABLE')
    report['baseline_stop']=wait_stop(False);report['initial_corridor']=corridor()
    channel.pub=ros.Publisher(safety.TOPIC,Twist,queue_size=1,latch=False)
    deadline=safety.now()+5
    while channel.pub.get_num_connections()<1 and safety.now()<deadline:time.sleep(.05)
    if channel.pub.get_num_connections()!=1:raise RuntimeError('BASE_CONNECTION_NOT_UNIQUE')
    channel.graph(True);channel.check();corridor()
    with lock:
        if not stop.evidence(safety.now())['passed']:raise RuntimeError('PARKING_BASELINE_LOST')
    with channel.lock:origin=dict(channel.rows[-1])
    channel.arm();began=safety.now();report['positive_begin']=began-channel.started
    channel.event('MEASURED_STRAIGHT_BEGIN',speed=.10,max_seconds=.50)
    while safety.now()-began<.50:
        channel.check();channel.graph(True);corridor()
        with channel.lock:last=dict(channel.rows[-1])
        if math.hypot(last['x']-origin['x'],last['y']-origin['y'])>=.08:
            report['events'].append(dict(event='ODOM_DISTANCE_LIMIT_REACHED',t=safety.now()-channel.started));break
        if safety.now()-began>=.50:break
        channel.send(.10);time.sleep(.05)
    report['positive_end']=safety.now()-channel.started
    channel.cleanup()
    report['post_stop']=wait_stop(True)
    report['status']='STOP_WINDOW_PASSED_AWAITING_PHYSICAL_MEASUREMENT';exitcode=0
except (Exception,KeyboardInterrupt) as e:
    report['error']=str(e) or 'Interrupted';report['status']='ABORTED' if channel and channel.armed else 'REFUSED'
finally:
    if channel:channel.cleanup()
    with lock:
        active=False;report['stop_at_capture_end']=stop.evidence(safety.now())
        if channel:
            with channel.lock:report['odom']=list(channel.rows)
    for sub in subs:sub.unregister()
    with os.fdopen(os.open(OUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2,allow_nan=False)
    if ros:ros.signal_shutdown('Single measured straight complete; no repeat')
print(json.dumps(dict(status=report['status'],error=report.get('error'),commands=len(report['commands']),post_stop=report.get('post_stop'))))
sys.exit(exitcode)
