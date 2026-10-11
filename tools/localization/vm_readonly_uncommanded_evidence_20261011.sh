#!/bin/bash
exec >/tmp/medical-uncommanded-raw-evidence-v2-20261011.log 2>&1
set -e
# The command file stays in Ubuntu; SSH runs only its read-only contents.
python2 /home/ncut/vm_connection_check_20261009.py --command-file /tmp/robot_readonly_uncommanded_evidence_20261011.sh
