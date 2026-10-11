#!/bin/bash
exec >/tmp/medical-zero-bench-upload-load-run6-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_bench_preflight_20261011.sh
python2 - <<'PY'
import os
path='/tmp/medical-inert-upload-load6-20261011.txt'
text=('INERT TEXT FOR COPY TIMING; NEVER EXECUTE.\n' * 1600)
with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as handle:
    handle.write(text)
PY
# Independent SSH session keeps the bounded bench run active during SCP.
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_execute_zero_bench_run6_20261011.sh >/tmp/medical-zero-bench-run6-command-20261011.log 2>&1 &
bench_job=$!
sleep 7
load_status=0
if python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_upload_window6_20261011.sh; then
    if python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical-inert-upload-load6-20261011.txt /home/EPRobot/medical-inert-upload-load-a6-20261011.txt; then
        if python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical-inert-upload-load6-20261011.txt /home/EPRobot/medical-inert-upload-load-b6-20261011.txt; then
            python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_upload_completed6_20261011.sh || load_status=$?
        else load_status=$?; fi
    else load_status=$?; fi
else load_status=$?; fi
bench_status=0
wait "$bench_job" || bench_status=$?
cat /tmp/medical-zero-bench-run6-command-20261011.log
echo LOAD_STATUS=$load_status BENCH_STATUS=$bench_status
for filename in medical-zero-bench-run6-20261011.log medical-zero-bench-audit6-20261011.jsonl medical-zero-bench-audit6-20261011.jsonl.lock medical-zero-bench-upload-window6-20261011.json medical-zero-bench-upload-completed6-20261011.json; do
    python2 /home/ncut/vm_connection_check_20261009.py --download "/home/EPRobot/$filename" "/home/ncut/medical_localization_assets_20261011/$filename"
done
test "$bench_status" -eq 0
test "$load_status" -eq 0
