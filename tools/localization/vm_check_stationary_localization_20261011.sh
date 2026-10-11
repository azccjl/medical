#!/bin/bash
exec >/tmp/medical-stationary-localization-offline-v2-20261011.log 2>&1
set -e
python2 -m py_compile /tmp/medical_stationary_localization_20261011.py
python2 /tmp/medical_stationary_localization_20261011.py
python2 /tmp/medical_stationary_localization_20261011.py --offline-check
sha256sum /tmp/medical_stationary_localization_20261011.py
