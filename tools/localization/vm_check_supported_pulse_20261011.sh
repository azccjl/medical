#!/bin/bash
exec >/tmp/medical-supported-pulse-offline-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_supported_wheel_pulse_20261011.py
python2 /tmp/medical_supported_wheel_pulse_20261011.py
python2 /tmp/medical_supported_wheel_pulse_20261011.py --offline-check
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_zero_bench_preflight_20261011.sh
