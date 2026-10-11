#!/bin/bash
exec >/tmp/medical-field-clock-align-run1-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_field_static_preflight_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_field_clock_server_run1_20261011.sh
sudo -n python2 /home/ncut/vm_field_clock_align_run1_20261011.py
