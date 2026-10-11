#!/bin/bash
exec >/tmp/medical-vm-small-forward-clock-v2-20261011.log 2>&1
set -e
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_stationary_localization_preflight_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_clock_server2_20261011.sh
sudo -n python2 /tmp/vm_align_small_forward_clock_v2_20261011.py
