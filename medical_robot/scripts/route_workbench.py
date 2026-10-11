#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Default is a passive workbench; field evidence and flags unlock action goals."""
from __future__ import print_function
import argparse,hashlib,json,os,threading,time,uuid,sys,subprocess
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
try:
    from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
    from SocketServer import ThreadingMixIn
except ImportError:
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from socketserver import ThreadingMixIn
from site_localization_view import load_map
from route_geometry import fillet_route,screen_route
from navigation_policy import acceptance_errors


def control_transition(current,value):
    if current=='STOP':raise ValueError('CANCELLATION_ALREADY_REQUESTED')
    if value not in ('RUN','PAUSE','STOP'):raise ValueError('INVALID_CONTROL_REQUEST')
    if value=='RUN' and current!='PAUSE':raise ValueError('ROUTE_NOT_PAUSED')
    if value=='PAUSE' and current!='RUN':raise ValueError('ROUTE_NOT_RUNNING')
    return value


def main():
    p=argparse.ArgumentParser()
    for name in ('raw-map','structured-map','annotations','acceptance','output-dir'):p.add_argument('--'+name,required=True)
    p.add_argument('--bind',default='192.168.12.71');p.add_argument('--port',type=int,default=8083)
    p.add_argument('--enable-navigation',action='store_true')
    p.add_argument('--site-ready-confirmed',action='store_true')
    a=p.parse_args();maps={'raw':load_map(a.raw_map),'structured':load_map(a.structured_map)}
    annotations=json.load(open(a.annotations));cert=json.load(open(a.acceptance))
    if not os.path.isdir(a.output_dir):os.makedirs(a.output_dir,0o700)
    hashes={}
    for name,yamlfile in [('raw',a.raw_map),('structured',a.structured_map)]:
        import yaml
        meta=yaml.safe_load(open(yamlfile));image=meta['image']
        if not os.path.isabs(image):image=os.path.join(os.path.dirname(yamlfile),image)
        hashes[name]=dict(pgm_sha256=hashlib.sha256(open(image,'rb').read()).hexdigest(),
                          yaml_sha256=hashlib.sha256(open(yamlfile,'rb').read()).hexdigest())
    page=open(os.path.join(os.path.dirname(__file__),'route_workbench.html'),'rb').read()
    csrf=uuid.uuid4().hex;plans={};lock=threading.RLock();host=a.bind+':'+str(a.port)
    navigation_enabled=a.enable_navigation and a.site_ready_confirmed and not acceptance_errors(cert,hashes['raw']['pgm_sha256'])
    if a.enable_navigation and not navigation_enabled:raise RuntimeError('FIELD_ACCEPTANCE_REQUIRED_BEFORE_NAVIGATION_INTERFACE')
    job=[None]
    def job_snapshot():
        with lock:
            if job[0] is None:return None
            j=job[0];code=j['process'].poll()
            return dict(id=j['id'],running=code is None,exit_code=code,control=j['control'],audit=j['audit'])
    def control_job(value):
        with lock:
            j=job[0]
            if j is None or j['process'].poll() is not None:raise ValueError('NO_RUNNING_ROUTE')
            value=control_transition(j['control'],value)
            temp=j['control_file']+'.'+uuid.uuid4().hex
            with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(value)
            os.rename(temp,j['control_file']);j['control']=value
    boundary=annotations['geometry']['outer_boundary_map_xy_m']
    left=min(q[0] for q in boundary)+.50;right=max(q[0] for q in boundary)-.50
    bottom=min(q[1] for q in boundary)+.50;top=max(q[1] for q in boundary)-.50
    # Offline-screened for this map version; still not a surveyed field route.
    preset=[[-.35,.075],[.90,.075],[.90,3.55],[-2.40,3.55],[-2.40,.075],[-.35,.075]]
    class Handler(BaseHTTPRequestHandler):
        def json_reply(self,status,payload):
            b=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)))
            self.end_headers();self.wfile.write(b)
        def do_GET(self):
            if self.headers.get('Host')!=host:self.send_error(403);return
            if self.path=='/api/config':
                self.json_reply(200,dict(maps=maps,annotations=annotations,csrf=csrf,preset=preset,
                                        map_hashes=hashes,field_blockers=acceptance_errors(cert,hashes['raw']['pgm_sha256']),
                                        motion_enabled=navigation_enabled,min_turn_radius_m=.75,preset_radius_m=.75));return
            if self.path=='/api/job':self.json_reply(200,dict(job=job_snapshot(),motion_enabled=navigation_enabled));return
            if self.path.startswith('/api/routes/'):
                name=self.path[len('/api/routes/'):]
                if not name.endswith('.json') or len(name)!=37 or any(c not in '0123456789abcdef' for c in name[:-5]):
                    self.send_error(404);return
                path=os.path.join(a.output_dir,name)
                if not os.path.isfile(path):self.send_error(404);return
                b=open(path,'rb').read();self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Disposition','attachment; filename=medical-route-'+name)
                self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
            if self.path!='/':self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(page)))
            self.end_headers();self.wfile.write(page)
        def do_POST(self):
            if (self.headers.get('Host')!=host or self.headers.get('Origin')!='http://'+host or
                self.headers.get('X-Medical-Token')!=csrf or self.headers.get('Content-Type')!='application/json'):
                self.json_reply(403,dict(error='ORIGIN_OR_TOKEN_INVALID'));return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:raise ValueError('INVALID_REQUEST_SIZE')
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict):raise ValueError('INVALID_REQUEST')
                if self.path=='/api/preview':
                    r=fillet_route(request.get('waypoints',[]),request.get('radius',.55))
                    r['screens']={name:screen_route(m,r) for name,m in maps.items()}
                    r.update(schema_version=1,frame='map',map_hashes=hashes,motion_enabled=False,
                             status='PREVIEW_ONLY',id=uuid.uuid4().hex,created_wall=time.time())
                    with lock:
                        if len(plans)>=100:plans.pop(next(iter(plans)))
                        plans[r['id']]=r
                    self.json_reply(200,r);return
                if self.path=='/api/save':
                    with lock:r=plans.get(request.get('id'))
                    if r is None:raise ValueError('PREVIEW_EXPIRED')
                    # Save is a draft, including rejected geometry; it never starts navigation.
                    name=uuid.uuid4().hex+'.json'
                    with os.fdopen(os.open(os.path.join(a.output_dir,name),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
                        json.dump(r,f,indent=2,allow_nan=False)
                    self.json_reply(200,dict(url='/api/routes/'+name));return
                if self.path=='/api/start':
                    if not navigation_enabled:raise ValueError('FIELD_ACCEPTANCE_REQUIRED_NO_GOALS_SENT')
                    if request.get('confirmed') is not True:raise ValueError('FRESH_SITE_CONFIRMATION_REQUIRED')
                    with lock:
                        r=plans.get(request.get('id'))
                        if r is None:raise ValueError('PREVIEW_EXPIRED')
                        if not all(s['passed'] for s in r['screens'].values()):raise ValueError('ROUTE_MAP_SCREEN_FAILED')
                        if job[0] and job[0]['process'].poll() is None:raise ValueError('ROUTE_ALREADY_RUNNING')
                        name=uuid.uuid4().hex;routefile=os.path.join(a.output_dir,name+'.json');audit=os.path.join(a.output_dir,name+'.jsonl')
                        control=routefile+'.control'
                        with os.fdopen(os.open(routefile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(r,f,allow_nan=False)
                        with os.fdopen(os.open(control,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write('RUN')
                        out=os.fdopen(os.open(audit+'.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w')
                        process=subprocess.Popen(['python2',os.path.join(os.path.dirname(__file__),'route_action_runner.py'),
                            '--route',routefile,'--acceptance',a.acceptance,'--execute-route','--site-ready-confirmed','--audit',audit,'--control-file',control],stdout=out,stderr=subprocess.STDOUT)
                        out.close();job[0]=dict(id=name,process=process,audit=audit,control_file=control,control='RUN')
                    self.json_reply(202,dict(job=job_snapshot()));return
                if self.path in ('/api/pause','/api/resume','/api/cancel'):
                    if not navigation_enabled:raise ValueError('FIELD_ACCEPTANCE_REQUIRED_NO_GOALS_SENT')
                    control_job({'/api/pause':'PAUSE','/api/resume':'RUN','/api/cancel':'STOP'}[self.path])
                    self.json_reply(202,dict(job=job_snapshot()));return
                self.json_reply(404,dict(error='NO_MOTION_ENDPOINT_IN_WORKBENCH'))
            except (ValueError,TypeError,KeyError) as exc:self.json_reply(400,dict(error=str(exc)))
        def log_message(self,*unused):pass
    class Server(ThreadingMixIn,HTTPServer):
        allow_reuse_address=True
        daemon_threads=True
    server=Server((a.bind,a.port),Handler)
    print('ROUTE_WORKBENCH http://%s navigation_enabled=%s'%(host,navigation_enabled))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        if job_snapshot() and job_snapshot()['running'] and job_snapshot()['control']!='STOP':control_job('STOP')
        server.server_close()


if __name__=='__main__':main()
