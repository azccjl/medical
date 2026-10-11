#!/bin/bash
exec >/tmp/medical-supported-wheel-pulse-execute-run2-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_bench_preflight_20261011.sh
task_status=0
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_execute_supported_pulse_run2_20261011.sh || task_status=$?
echo VM_SUPPORTED_PULSE_EXIT=$task_status
for filename in medical-supported-wheel-pulse-run2-20261011.log medical-supported-wheel-pulse-audit2-20261011.jsonl medical-supported-wheel-pulse-audit2-20261011.jsonl.lock; do
    python2 /home/ncut/vm_connection_check_20261009.py --download "/home/EPRobot/$filename" "/home/ncut/medical_localization_assets_20261011/$filename"
done
exit "$task_status"
