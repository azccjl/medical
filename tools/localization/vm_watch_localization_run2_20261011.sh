#!/bin/bash
exec >/tmp/medical-localization-watch-run2-20261011.log 2>&1
set -e
echo RESTORE_EXECUTION_LOG
tail -n 12 /tmp/medical-stationary-localization-execute-v3-run2-20261011.log
echo ZERO_ONLY_HARDWARE_LOG
if test -e /tmp/medical-stationary-localization-hardware-v3-run2-20261011.log; then
  tail -n 8 /tmp/medical-stationary-localization-hardware-v3-run2-20261011.log
fi
python2 - <<'PY'
from __future__ import print_function
import json,os,urllib2
d=json.load(urllib2.urlopen('http://127.0.0.1:8080/api/state',timeout=5))
print('LIVE_STATUS',d['status'].encode('utf-8'))
print('LIVE_POSE',json.dumps(d.get('pose')))
print('LIVE_UNCERTAINTY',json.dumps(d.get('uncertainty')))
result='/home/ncut/medical_localization_assets_20261011/zero-only-site-reinitialized-v3-run2-20261011.json'
if os.path.isfile(result):
    report=json.load(open(result))
    print('CAPTURE_STATUS',report['status'],report.get('error'))
else:print('CAPTURE_NOT_FINISHED')
PY
