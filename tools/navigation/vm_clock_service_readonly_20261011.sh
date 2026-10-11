#!/bin/bash
exec >/tmp/medical-clock-service-readonly-20261011.log 2>&1
export PYTHONIOENCODING=utf-8
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_service_readonly_20261011.sh
