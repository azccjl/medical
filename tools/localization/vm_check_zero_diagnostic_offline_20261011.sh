#!/bin/bash
exec >/tmp/medical-zero-diagnostic-offline-v2-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_serial_zero_diagnostic_20261011.py
python2 /tmp/medical_serial_zero_diagnostic_20261011.py
python2 /tmp/medical_serial_zero_diagnostic_20261011.py --offline-check
# No SSH call, upload to robot, ROS import or serial opening in this script.
