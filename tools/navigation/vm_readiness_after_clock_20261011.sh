#!/bin/bash
# Read-only: no hardware startup and no velocity/action publishers.
exec >/tmp/medical-readiness-after-clock-20261011.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
date -Ins
systemctl is-active chrony
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_final_readonly_20261011.sh
python2 - <<'PY'
from __future__ import print_function
import json,urllib2
def get(url):return json.load(urllib2.urlopen(url,timeout=4))
c=get('http://192.168.12.71:8083/api/config')
j=get('http://192.168.12.71:8083/api/job')
p=get('http://192.168.12.71:8080/api/state')
d=get('http://192.168.12.71:8082/api/state')
print(json.dumps(dict(navigation_enabled=c['motion_enabled'],route_job=j['job'],
                     field_blockers=c.get('field_blockers'),
                     localization={k:p.get(k) for k in ('status','pose','uncertainty')},
                     short_pulse_busy=d['busy'],short_pulse_run=d['run']),ensure_ascii=True))
PY
