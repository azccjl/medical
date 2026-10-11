#!/bin/bash
set -e
python2 - <<'PY'
from __future__ import print_function
import os,json,time,hashlib
audit='/home/EPRobot/medical-zero-bench-audit6-20261011.jsonl'
with open(audit,'rb') as handle:
    rows=[json.loads(line) for line in handle if line.endswith('\n')]
targets=['/home/EPRobot/medical-inert-upload-load-a6-20261011.txt',
         '/home/EPRobot/medical-inert-upload-load-b6-20261011.txt']
files=[]
for path in targets:
    with open(path,'rb') as handle: data=handle.read()
    files.append(dict(path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
report=dict(event='UPLOADS_COMPLETED',wall=time.time(),files=files,
            bench_end_seen=any(row['event']=='BENCH_END' for row in rows),
            audit_last_event=rows[-1],payload_executed=False)
output='/home/EPRobot/medical-zero-bench-upload-completed6-20261011.json'
with os.fdopen(os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as handle:
    json.dump(report,handle,indent=2)
print(json.dumps(report))
PY
