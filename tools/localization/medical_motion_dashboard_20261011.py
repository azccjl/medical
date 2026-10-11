#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""VM-hosted passive scan view; explicit POST launches one guarded robot pulse."""
from __future__ import print_function
import argparse
import ctypes
import hashlib
import json
import os
import pipes
import subprocess
import threading
import time
import uuid
try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer
from medical_scan_report_20261011 import scan_report

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = '/home/ncut/vm_connection_check_20261009.py'
ROBOT_DIR = '/home/EPRobot/medical_dashboard_20261011'
CONTROL_TYPES = ('geometry_msgs/Twist','geometry_msgs/TwistStamped',
                 'ackermann_msgs/AckermannDrive','ackermann_msgs/AckermannDriveStamped')


class TS(ctypes.Structure):
    _fields_ = [('s',ctypes.c_long),('ns',ctypes.c_long)]


lib = ctypes.CDLL('librt.so.1')
def now():
    ts=TS()
    if lib.clock_gettime(1,ctypes.byref(ts)) != 0:
        raise RuntimeError('MONOTONIC_FAILED')
    return ts.s+ts.ns/1e9


class Dashboard(object):
    def __init__(self, output_dir):
        import rospy, rosgraph, tf2_ros
        from sensor_msgs.msg import LaserScan
        self.ros=rospy
        self.lock=threading.RLock()
        self.output_dir=output_dir
        self.csrf=uuid.uuid4().hex
        self.scan=None; self.consecutive=0; self.last_stamp=None; self.received=None
        self.graph_errors=['ROS_GRAPH_UNAVAILABLE']; self.graph_time=None
        self.arm=None; self.run=None; self.busy=False
        self.master=rosgraph.Master(rospy.get_name())
        self.buffer=tf2_ros.Buffer()
        self.listener=tf2_ros.TransformListener(self.buffer)
        self.sub=rospy.Subscriber('/medical_slam_scan',LaserScan,self.on_scan,queue_size=1,tcp_nodelay=True)
        self.timer=rospy.Timer(rospy.Duration(.4),lambda unused:self.check_graph())
        with open(os.path.join(HERE,'dashboard-manifest.json')) as f:self.manifest=json.load(f)
        for name,digest in self.manifest.items():
            if hashlib.sha256(open(os.path.join(HERE,name),'rb').read()).hexdigest()!=digest:
                raise RuntimeError('LOCAL_STAGED_FILE_CHANGED_'+name)

    def on_scan(self,m):
        received=now(); stamp=m.header.stamp.to_sec(); r=scan_report(m)
        age=self.ros.Time.now().to_sec()-stamp
        with self.lock:
            seq=self.last_stamp is None or (stamp>self.last_stamp and 0<received-self.received<=.30)
            self.consecutive=self.consecutive+1 if r['passed'] and seq and -.02<=age<=.30 else 0
            self.last_stamp=stamp; self.received=received
            self.scan=r

    def check_graph(self):
        errors=[]
        try:
            types=dict(self.master.getTopicTypes())
            for topic,nodes in self.master.getSystemState()[0]:
                if nodes and (types.get(topic) in CONTROL_TYPES or topic in ('/odom','/move_base/goal','/move_base_simple/goal')):
                    errors.append('UNEXPECTED_PUBLISHER_'+topic)
            if self.ros.get_param('/use_sim_time',False):errors.append('SIM_TIME_FORBIDDEN')
            t=self.buffer.lookup_transform('base_footprint','base_laser_link',self.ros.Time(0),self.ros.Duration(.1)).transform
            if (abs(t.translation.x-.135)>.001 or abs(t.translation.y)>.001 or
                    abs(t.translation.z-.135)>.001 or
                    max(abs(t.rotation.x),abs(t.rotation.y),abs(t.rotation.z))>.001 or abs(abs(t.rotation.w)-1)>.001):
                errors.append('LASER_TRANSFORM_CHANGED')
        except Exception as exc:
            errors.append('ROS_GRAPH_UNAVAILABLE')
        with self.lock:
            self.graph_errors=errors; self.graph_time=now()

    def snapshot(self):
        with self.lock:
            age=None if self.received is None else now()-self.received
            ros_age=None if self.last_stamp is None else self.ros.Time.now().to_sec()-self.last_stamp
            errors=list(self.scan['errors']) if self.scan else ['SCAN_STALE']
            if age is None or not 0<=age<=.30 or not -.02<=ros_age<=.30:
                if 'SCAN_STALE' not in errors:errors.append('SCAN_STALE')
            if self.consecutive<5:errors.append('NO_FIVE_CONSECUTIVE_VALID_SCANS')
            errors.extend(self.graph_errors)
            if self.graph_time is None or not 0<=now()-self.graph_time<=1:
                errors.append('GRAPH_STALE')
            if self.busy:errors.append('EXECUTION_BUSY')
            return dict(ready=not errors,blockers=errors,scan=self.scan,consecutive=self.consecutive,
                        receive_age_s=age,ros_age_s=ros_age,busy=self.busy,csrf=self.csrf,run=self.run)

    def prepare(self):
        self.check_graph()
        with self.lock:
            s=self.snapshot()
            if not s['ready']:return 409,dict(errors=s['blockers'])
            self.arm=(uuid.uuid4().hex,now()+10)
            return 200,dict(arm=self.arm[0],expires_ms=(time.time()+10)*1000)

    def start(self, request):
        self.check_graph()
        with self.lock:
            arm=self.arm; self.arm=None
            if not arm or request.get('arm')!=arm[0] or now()>arm[1] or request.get('confirmed') is not True:
                return 409,dict(error='准备已过期，请重新复核并准备')
            s=self.snapshot()
            if not s['ready']:return 409,dict(errors=s['blockers'])
            self.busy=True
            name='ground-'+uuid.uuid4().hex
            audit=ROBOT_DIR+'/'+name+'.jsonl'
            self.run=dict(status=u'车端复核中；尚未确认发车',audit=audit,output='',name=name)
            thread=threading.Thread(target=self.execute,args=(name,audit))
            thread.daemon=True;thread.start()
            return 202,dict(status='SUBMITTED_ONCE')

    def ssh_command(self,command,name):
        path=os.path.join(self.output_dir,name+'.sh')
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(command)
        return subprocess.check_output(['python2',HELPER,'--command-file',path],stderr=subprocess.STDOUT)

    def execute(self,name,audit):
        output=''; code=1
        try:
            command="set -e\nsource /home/EPRobot/medical_robot_env.sh\ncd "+ROBOT_DIR+"\n"
            command+="python2 - <<'PY'\nimport hashlib,json\nmanifest="+repr(self.manifest)+"\n"
            command+="for name,digest in manifest.items():\n assert hashlib.sha256(open(name,'rb').read()).hexdigest()==digest, 'STAGED_FILE_CHANGED_'+name\nPY\n"
            command+="task_status=0\ntimeout --signal=INT --kill-after=5s 40s python2 medical_ground_straight_pulse_v5_20261011.py --execute-ground-pulse --clear-floor-confirmed --power-stop-confirmed --duration 30 --audit "+pipes.quote(audit)+" >"+pipes.quote(audit+'.log')+" 2>&1 || task_status=$?\n"
            command+="echo GROUND_PULSE_EXIT=$task_status\ntail -n 12 "+pipes.quote(audit+'.log')+"\nexit $task_status\n"
            # Verify the stopped process released the port before reporting completion.
            command=command.replace('exit $task_status\n',
                "python2 - <<'PY'\nimport os,glob,json\nd=os.path.realpath('/dev/EPRobot_base');owners=[]\n"
                "for pid in os.listdir('/proc'):\n if not pid.isdigit():continue\n"
                " for f in glob.glob('/proc/'+pid+'/fd/*'):\n  try:\n   if os.readlink(f)==d:owners.append(pid)\n"
                "  except OSError:pass\nprint('POST_RUN_SERIAL_OWNERS '+json.dumps(owners))\nassert not owners,'SERIAL_OWNER_REMAINS'\nPY\nexit $task_status\n")
            output=self.ssh_command(command,name+'-execute');code=0
        except subprocess.CalledProcessError as exc:
            output=exc.output;code=exc.returncode
        except Exception as exc:
            output=str(exc)
        finally:
            # Download evidence even after a rejected run; no automatic retry.
            for suffix in ('','.lock','.log'):
                try:
                    output+=subprocess.check_output(['python2',HELPER,'--download',audit+suffix,
                                                    os.path.join(self.output_dir,name+'.jsonl'+suffix)],stderr=subprocess.STDOUT)
                except Exception as exc:
                    output+='\nEVIDENCE_DOWNLOAD_ERROR '+str(exc)
            with self.lock:
                self.run.update(status=u'本次进程结束；请观察并确认实车停稳' if code==0 else u'本次被拒绝或中止；请查看记录',
                                output=output.decode('utf-8','replace') if isinstance(output,bytes) else output,exit_code=code)
                self.busy=False

    def stop(self):
        with self.lock:
            self.arm=None
            if not self.busy or not self.run:return 200,dict(status='NO_ACTIVE_RUN')
            audit=self.run['audit'];name=self.run['name']
        def cancel():
            try:
                # Persistent cancellation prevents starting after an early stop request.
                self.ssh_command("umask 077\n: > "+pipes.quote(audit+'.cancel')+"\n",name+'-cancel-'+uuid.uuid4().hex)
            except Exception as exc:
                with self.lock:self.run['output']+='\nCANCEL_DELIVERY_ERROR '+str(exc)
        t=threading.Thread(target=cancel);t.daemon=True;t.start()
        return 202,dict(status='CANCEL_REQUESTED_NETWORK_DELIVERY_PENDING')


def main():
    p=argparse.ArgumentParser();p.add_argument('--bind',default='192.168.12.71');p.add_argument('--port',type=int,default=8082)
    p.add_argument('--output-dir',required=True);args=p.parse_args()
    if not os.path.isdir(args.output_dir):os.makedirs(args.output_dir,0o700)
    import rospy
    rospy.init_node('medical_motion_dashboard',disable_signals=False)
    dashboard=Dashboard(args.output_dir)
    page=open(os.path.join(HERE,'medical_motion_dashboard_20261011.html'),'rb').read()
    expected_host=args.bind+':'+str(args.port)
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,payload):
            body=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.headers.get('Host')!=expected_host:self.send_error(403);return
            if self.path.split('?')[0]=='/api/state':self.reply(200,dashboard.snapshot());return
            if self.path=='/api/report':
                body=json.dumps(dashboard.snapshot(),ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')
                self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Disposition','attachment; filename=medical-scan-preflight.json')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body);return
            if self.path.startswith('/api/evidence/'):
                name=self.path[len('/api/evidence/'):]
                with dashboard.lock:run=dict(dashboard.run) if dashboard.run else None
                allowed=[] if run is None else [run['name']+'.jsonl'+suffix for suffix in ('','.lock','.log')]
                if name not in allowed:self.send_error(404);return
                path=os.path.join(args.output_dir,name)
                if not os.path.isfile(path):self.send_error(404);return
                body=open(path,'rb').read()
                self.send_response(200);self.send_header('Content-Type','application/octet-stream')
                self.send_header('Content-Disposition','attachment; filename='+name)
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body);return
            if self.path.split('?')[0]!='/':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page)
        def do_POST(self):
            if (self.headers.get('Host')!=expected_host or self.headers.get('Origin')!='http://'+expected_host or
                    self.headers.get('X-Medical-Token')!=dashboard.csrf or self.headers.get('Content-Type')!='application/json'):
                self.reply(403,dict(error='同源操作校验失败'));return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=2048:raise ValueError()
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict):raise ValueError()
            except ValueError:self.reply(400,dict(error='请求格式不符'));return
            if self.path=='/api/arm':code,s=dashboard.prepare()
            elif self.path=='/api/pulse':code,s=dashboard.start(request)
            elif self.path=='/api/stop':code,s=dashboard.stop()
            else:self.send_error(404);return
            self.reply(code,s)
        def log_message(self,*unused):pass
    class Server(HTTPServer):allow_reuse_address=True
    server=Server((args.bind,args.port),Handler)
    worker=threading.Thread(target=server.serve_forever);worker.daemon=True;worker.start()
    print('PASSIVE_DASHBOARD http://%s:%s; no base started' % (args.bind,args.port))
    try:rospy.spin()
    finally:
        dashboard.stop();server.shutdown();server.server_close()


if __name__=='__main__':main()
