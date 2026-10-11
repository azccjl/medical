#!/bin/bash
exec >/tmp/medical-zero-bench-execute-run2-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_serial_zero_diagnostic_v2_20261011.py
python2 /tmp/medical_serial_zero_diagnostic_v2_20261011.py --offline-check
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_bench_preflight_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_serial_zero_diagnostic_v2_20261011.py /home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py
task_status=0
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_execute_zero_bench_run2_20261011.sh || task_status=$?
echo VM_ZERO_BENCH_EXIT=$task_status
python2 /home/ncut/vm_connection_check_20261009.py --download /home/EPRobot/medical-zero-bench-run2-20261011.log /home/ncut/medical_localization_assets_20261011/medical-zero-bench-run2-20261011.log
python2 /home/ncut/vm_connection_check_20261009.py --download /home/EPRobot/medical-zero-bench-audit2-20261011.jsonl /home/ncut/medical_localization_assets_20261011/medical-zero-bench-audit2-20261011.jsonl
python2 /home/ncut/vm_connection_check_20261009.py --download /home/EPRobot/medical-zero-bench-audit2-20261011.jsonl.lock /home/ncut/medical_localization_assets_20261011/medical-zero-bench-audit2-20261011.jsonl.lock
exit "$task_status"
