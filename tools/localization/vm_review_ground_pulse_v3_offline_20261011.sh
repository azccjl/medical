#!/bin/bash
exec >/tmp/medical-ground-pulse-v3-offline-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_ground_straight_pulse_v3_20261011.py
python2 /tmp/medical_ground_straight_pulse_v3_20261011.py
python2 /tmp/review_ground_pulse_v3_offline_20261011.py \
  --source /tmp/medical_ground_straight_pulse_v3_20261011.py \
  --previous /tmp/medical_ground_straight_pulse_v2_20261011.py \
  --scans /tmp/ground-scan-inspection-for-v3-20261011.json \
  --output /home/ncut/medical_localization_assets_20261011/ground-pulse-v3-offline-review-20261011.json
echo OFFLINE_REVIEW_COMPLETE_NO_ROBOT_CONNECTION
