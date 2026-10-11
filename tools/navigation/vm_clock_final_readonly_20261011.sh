#!/bin/bash
exec >/tmp/medical-clock-final-readonly-20261011.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
systemctl is-active chrony
systemctl is-enabled chrony
chronyc tracking
systemctl is-active systemd-timesyncd || true
systemctl show chrony --property=Restart --property=RestartUSec
cat /etc/chrony/chrony.conf
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_final_readonly_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_field_static_preflight_20261011.sh
python2 - <<'PY'
import urllib2,json
def get(path):return json.load(urllib2.urlopen(path,timeout=4))
c=get('http://192.168.12.71:8083/api/config')
j=get('http://192.168.12.71:8083/api/job')
d=get('http://192.168.12.71:8082/api/state')
assert not c['motion_enabled'] and j['job'] is None and not d['busy'] and d['run'] is None
print('FINAL_NO_NAVIGATION_TASK_OR_MOTION_RUN')
PY
