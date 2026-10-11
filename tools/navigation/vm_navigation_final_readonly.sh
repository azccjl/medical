#!/bin/bash
exec >/tmp/medical-navigation-final-readonly-20261011.log 2>&1
set -e
stage=/home/ncut/medical_navigation_prepare_v2_20261011
python2 - "$stage" <<'PY'
import urllib2,json,os,sys,socket,hashlib
stage=sys.argv[1];url='http://192.168.12.71:8083'
config=json.load(urllib2.urlopen(url+'/api/config',timeout=3));job=json.load(urllib2.urlopen(url+'/api/job',timeout=3))
assert config['motion_enabled'] is False and job['job'] is None
dashboard=json.load(urllib2.urlopen('http://192.168.12.71:8082/api/state',timeout=3))
assert not dashboard['busy'] and dashboard['run'] is None
s=socket.socket();s.settimeout(1);assert s.connect_ex(('127.0.0.1',11312))!=0;s.close()
blocked=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    try:args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError:continue
    for name in ('navigation_audited_base.py','navigation_command_gate.py','route_action_runner.py','isolated_navigation_fixture.py'):
        if any(arg.endswith('/'+name) for arg in args):blocked.append((pid,args))
assert not blocked,blocked
names=('route_workbench.py','route_workbench.html','navigation_audited_base.py','navigation_policy.py','navigation_scan_guard.py',
       'navigation_command_gate.py','route_action_runner.py','route_geometry.py')
report=dict(status='FINAL_PASSIVE_STATE_CONFIRMED',navigation_enabled=False,route_job=None,
            short_pulse_job=None,isolated_master_closed=True,physical_motion_sent=False,
            candidate_processes_running=[],source_sha256={n:hashlib.sha256(open(stage+'/src/medical_robot/scripts/'+n,'rb').read()).hexdigest() for n in names})
with os.fdopen(os.open(stage+'/final-passive-state-final.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
PY
python2 /home/ncut/vm_connection_check_20261009.py --command-file "$stage/robot_nav_verify_v2_staged.sh"
