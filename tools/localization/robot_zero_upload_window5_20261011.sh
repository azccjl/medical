#!/bin/bash
set -e
python2 - <<'PY'
from __future__ import print_function
import os,glob,json,time
audit='/home/EPRobot/medical-zero-bench-audit5-20261011.jsonl'
output='/home/EPRobot/medical-zero-bench-upload-window5-20261011.json'
deadline=time.time()+12
while True:
    try:
        with open(audit,'rb') as handle:
            rows=[json.loads(line) for line in handle if line.endswith('\n')]
        start=next(row for row in rows if row['event']=='BENCH_START')
        if time.time()-start['wall']>=3: break
    except (IOError,StopIteration): pass
    if time.time()>=deadline: raise RuntimeError('BENCH_START_WAIT_TIMED_OUT')
    time.sleep(.2)
if any(row['event']=='BENCH_END' for row in rows): raise RuntimeError('BENCH_ALREADY_ENDED')
begin=next(row for row in rows if row['event']=='BENCH_START')
age=time.time()-begin['wall']
if not 3<=age<=20: raise RuntimeError('OUTSIDE_UPLOAD_WINDOW age='+str(age))
if time.time()-rows[-1]['wall']>1: raise RuntimeError('AUDIT_NOT_UPDATING')
device=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:
                command=open('/proc/'+pid+'/cmdline','rb').read()
                if 'medical_serial_zero_diagnostic_v2_20261011.py' not in command:
                    raise RuntimeError('OTHER_SERIAL_OWNER')
                owners.append(int(pid))
        except OSError: pass
if len(owners)!=1: raise RuntimeError('DIAGNOSTIC_OWNER_NOT_UNIQUE')
targets=['/home/EPRobot/medical-inert-upload-load-a-20261011.txt',
         '/home/EPRobot/medical-inert-upload-load-b-20261011.txt']
if any(os.path.exists(path) for path in targets): raise RuntimeError('LOAD_TARGET_ALREADY_EXISTS')
report=dict(event='UPLOAD_WINDOW_BEGIN',wall=time.time(),bench_start_wall=begin['wall'],
            serial_owners=owners,audit_last_event=rows[-1],targets=targets,
            payload_executed=False)
with os.fdopen(os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as handle:
    json.dump(report,handle,indent=2)
print(json.dumps(report))
PY
