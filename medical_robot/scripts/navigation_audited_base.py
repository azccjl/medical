#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Staged audited base. Default never imports ROS or opens serial."""
from __future__ import print_function
import argparse,binascii,glob,hashlib,json,math,os,sys,threading,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from navigation_policy import acceptance_errors,command_policy
DRIVER='/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py'
DRIVER_SHA='d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'


def crc8(values):
    result=0
    for value in values:
        value^=result;result=0
        for unused in range(8):
            result=((result^0x18)>>1)|0x80 if (result^value)&1 else result>>1
            value>>=1
    return result


def velocity_frame(v,steering):
    """Encode the requested speed without the legacy 0.10 m/s clamp."""
    speed=int(v*1000);angle=int(steering*1000)
    b=[0x5a,18,1,1,(speed>>8)&255,speed&255,0,0,(angle>>8)&255,angle&255,0x27,0x10,3,0xe8,0,0,0]
    return bytearray(b+[crc8(b)])


def frame_policy(data,label,cert,nonzero_authorized):
    b=list(bytearray(data))
    if len(b)<6 or b[:3]!=[0x5a,len(b),1] or crc8(b[:-1])!=b[-1]:raise ValueError('INVALID_TX_FRAME')
    if label=='odom_query' and b[:-1]==[0x5a,7,1,9,2,0]:return
    if label!='velocity' or len(b)!=18 or b[3]!=1:raise ValueError('TX_TYPE_NOT_ALLOWED')
    if b[6:8]!=[0,0] or b[10:17]!=[0x27,0x10,3,0xe8,0,0,0]:raise ValueError('PID_OR_UNSUPPORTED_AXES_CHANGED')
    def signed(h,l):
        n=h*256+l;return (n-65536 if n>=32768 else n)/1000.
    v= signed(b[4],b[5]);steering=signed(b[8],b[9])
    if not v and not steering:return
    if not nonzero_authorized:raise ValueError('BASE_NOT_AUTHORIZED_FOR_NONZERO_TX')
    if not cert['measured_min_reliable_speed_m_s']-.001<=v<=cert['navigation_speed_limit_m_s'] or abs(steering)>math.atan(.17/max(.75,cert['measured_min_turn_radius_m']))+.001:
        raise ValueError('NONZERO_TX_OUT_OF_BOUND')


def main():
    p=argparse.ArgumentParser();p.add_argument('--acceptance',required=True);p.add_argument('--map-sha',required=True)
    p.add_argument('--execute-base',action='store_true');p.add_argument('--stationary-confirmed',action='store_true')
    p.add_argument('--power-stop-confirmed',action='store_true');p.add_argument('--audit');a=p.parse_args()
    cert=json.load(open(a.acceptance));errors=acceptance_errors(cert,a.map_sha)
    if not a.execute_base:
        print(json.dumps(dict(status='PREPARED_ONLY',errors=errors,ros_imported=False,serial_opened=False)));return 0
    if errors or not a.stationary_confirmed or not a.power_stop_confirmed or not a.audit:
        print(json.dumps(dict(status='REFUSED_BEFORE_ROS',errors=errors or ['PHYSICAL_CONFIRMATIONS_REQUIRED'])));return 2
    if hashlib.sha256(open(DRIVER,'rb').read()).hexdigest()!=DRIVER_SHA:raise RuntimeError('BASE_SOURCE_CHANGED')
    device=os.path.realpath('/dev/EPRobot_base')
    for pid in os.listdir('/proc'):
        if not pid.isdigit():continue
        for fd in glob.glob('/proc/'+pid+'/fd/*'):
            try:
                if os.readlink(fd)==device:raise RuntimeError('SERIAL_ALREADY_OWNED_'+pid)
            except OSError:pass
    import rospy,rosgraph
    rospy.init_node('medical_navigation_audited_base')
    master=rosgraph.Master(rospy.get_name());types=dict(master.getTopicTypes())
    for topic,nodes in master.getSystemState()[0]:
        if nodes and (types.get(topic) in ('geometry_msgs/Twist','geometry_msgs/TwistStamped','ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped') or topic in ('/odom','/move_base/goal','/move_base_simple/goal')):
            raise RuntimeError('EXISTING_CONTROL_OR_ODOM_'+topic)
    if rospy.get_param('/use_sim_time',False):raise RuntimeError('SIM_TIME_FORBIDDEN')
    os.close(os.open(a.audit+'.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600))
    log=os.fdopen(os.open(a.audit,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w');guard=threading.RLock()
    sys.path.insert(0,os.path.dirname(DRIVER));import medical_art_racecar_heading_v2_candidate as legacy
    import medical_stop_window
    src=medical_stop_window.__file__.replace('.pyc','.py')
    if hashlib.sha256(open(src,'rb').read()).hexdigest()!='15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43':raise RuntimeError('STOP_WINDOW_CHANGED')
    now=legacy._medical_now
    def record(event,**k):
        with guard:
            k.update(event=event,mono=now(),wall=time.time());log.write(json.dumps(k,allow_nan=False)+'\n');log.flush()
    serial_factory=legacy.serial.Serial
    class SerialAudit(object):
        def __init__(self,*args,**kwargs):self.raw=serial_factory(*args,**kwargs);self.allowed=False;record('SERIAL_OPEN')
        def __getattr__(self,n):return getattr(self.raw,n)
        def read(self,n):
            b=self.raw.read(n)
            if b:record('RX_BYTES',hex=binascii.hexlify(b).decode('ascii'))
            return b
        def readall(self):
            b=self.raw.readall();record('STARTUP_DISCARDED_RX',hex=binascii.hexlify(b).decode('ascii'));return b
        def write(self,b):
            if not self.allowed:raise RuntimeError('BYPASS_WRITE_FORBIDDEN')
            return self.raw.write(b)
    legacy.serial.Serial=SerialAudit
    class Base(legacy.BaseControl):
        def __init__(self):
            self.nav_ready=False;self.nav_fault=None;self.next_tx=0.;self.stop_window=medical_stop_window.StopWindow();self.last_sample=None
            try:legacy.BaseControl.__init__(self)
            except Exception:
                if hasattr(self,'_medical_stop_event'):self._medical_stop_event.set()
                self._medical_closing=True
                for name in ('timer_odom','timer_battery','timer_communication'):
                    timer=getattr(self,name,None)
                    if timer is not None:timer.shutdown()
                with self._medical_tx_lock:
                    port=getattr(self,'serial',None)
                    if port is not None:port.close()
                raise
        def timerBatteryCB(self,event):return
        def _medical_raw_cmdCB(self,m):
            # The inherited watchdog/shutdown use this method too. Zero remains zero.
            values=command_policy(m.linear.x,m.angular.z,cert)
            self.last_cmd_vel_time=rospy.Time.now()
            b=velocity_frame(values['v'],values['steering'])
            return self._medical_write(''.join(chr(x) for x in b),'velocity')
        def timerCommunicationCB(self,event):
            result=legacy.BaseControl.timerCommunicationCB(self,event);sample=self._medical_fresh_odom()
            if self._medical_heading.failed:self.nav_fault='HEADING_CALIBRATION_FAILED'
            if sample and sample['received_mono']!=self.last_sample:
                with self._medical_rx_lock:
                    self.last_sample=sample['received_mono'];self.stop_window.feed(dict(t=self.last_sample,stamp=self.last_sample,vx=sample['vx'],vy=sample['vy'],wz=sample['wz']))
                if not self.nav_ready and abs(sample['vx'])>.002:self.nav_fault='NONZERO_STARTUP_FEEDBACK'
                if abs(sample['vx'])>.20:self.nav_fault='FEEDBACK_SPEED_LIMIT'
            return result
        def cmdCB(self,m):
            caller=getattr(m,'_connection_header',{}).get('callerid')
            try:
                if caller!='/medical_navigation_command_gate':raise ValueError('UNKNOWN_BASE_COMMAND_CALLER')
                if any(getattr(m.linear,n)!=0 for n in ('y','z')) or any(getattr(m.angular,n)!=0 for n in ('x','y')):raise ValueError('UNSUPPORTED_TWIST_AXES')
                values=command_policy(m.linear.x,m.angular.z,cert)
                if values['v'] and (not self.nav_ready or self.nav_fault):raise ValueError('BASE_NOT_READY')
                record('ROS_INPUT',caller=caller,**values)
                return legacy.BaseControl.cmdCB(self,m)
            except ValueError as exc:
                self.nav_fault=str(exc);record('COMMAND_REJECTED',reason=str(exc))
                with self._medical_command_lock:self._medical_last_command=None;self._medical_raw_cmdCB(legacy.Twist())
        def _medical_write(self,b,label):
            with self._medical_tx_lock:
                if (self._medical_closing or self.nav_fault) and label!='velocity':return False
                try:
                    frame_policy(b,label,cert,self.nav_ready and not self.nav_fault and not self._medical_closing)
                    delay=self.next_tx-now()
                    if delay>0:time.sleep(delay)
                    values=list(bytearray(b));nonzero=label=='velocity' and any(values[4:10])
                    if nonzero:
                        frame_policy(b,label,cert,self.nav_ready and not self.nav_fault and not self._medical_closing)
                        if self._medical_fresh_odom() is None or self._medical_last_command is None or not 0<=now()-self._medical_last_command<=.20:
                            raise ValueError('BASE_FEEDBACK_OR_COMMAND_STALE')
                    record('TX_BEGIN',label=label,hex=binascii.hexlify(b).decode('ascii'))
                    self.serial.allowed=True
                    try:result=legacy.BaseControl._medical_write(self,b,label)
                    finally:self.serial.allowed=False
                    self.next_tx=now()+len(b)*10./115200+.010
                    record('TX_END',success=result)
                    if not result:self.nav_fault='SERIAL_WRITE_FAILED'
                    return result
                except ValueError as exc:self.nav_fault=str(exc);record('TX_REJECTED',reason=str(exc));return False
    params=dict(port='/dev/EPRobot_base',baudrate=115200,odom_freq=50,base_kp=1000.,base_ki=100.,base_kd=0.,base_kv=1.,
                wheelbase=.17,Laser_Mode='Boost',is_pub_odom_tf='true',is_send_anger='false',command_timeout=.20,
                stationary_start_confirmed=True,odom_topic='/odom',imu_topic='/medical_navigation_base/imu',
                cmd_vel_topic='/medical_navigation_gated_cmd_vel',feedback_vel_topic='/medical_navigation_base/feedback')
    for k,v in params.items():rospy.set_param('~'+k,v)
    control=None
    try:
        control=Base();deadline=now()+30
        while not rospy.is_shutdown() and now()<deadline and not control.nav_fault:
            with control._medical_rx_lock:e=control.stop_window.evidence(now())
            if e['passed']:control.nav_ready=True;record('BASE_STRICT_STARTUP_READY',evidence=e);break
            time.sleep(.05)
        if not control.nav_ready:raise RuntimeError(control.nav_fault or 'STRICT_STARTUP_STOP_UNAVAILABLE')
        # Gate must be started after BASE_STRICT_STARTUP_READY, not during gyro calibration.
        while not rospy.is_shutdown() and not control.nav_fault:
            if control._medical_fresh_odom() is None:control.nav_fault='ODOM_FEEDBACK_STALE';break
            time.sleep(.02)
        if control.nav_fault:raise RuntimeError(control.nav_fault)
    except Exception as exc:record('BASE_ABORT',reason=str(exc));raise
    finally:
        if control:control.medical_shutdown()
        record('BASE_EXIT_SERIAL_CLOSED',initialized=control is not None)
    return 0


if __name__=='__main__':sys.exit(main())
