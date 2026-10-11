#!/bin/bash
exec >/tmp/medical-stationary-localization-prepare-v3-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_stationary_localization_v3_20261011.py /tmp/reinitialize_zero_only_site_20261011.py
python2 /tmp/medical_stationary_localization_v3_20261011.py
python2 /tmp/medical_stationary_localization_v3_20261011.py --offline-check
sha256sum /tmp/medical_stationary_localization_v3_20261011.py /tmp/reinitialize_zero_only_site_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py --upload /tmp/medical_stationary_localization_v3_20261011.py /home/EPRobot/medical_stationary_localization_v3_20261011.py
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_stationary_localization_preflight_v3_20261011.sh
