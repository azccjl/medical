#!/bin/bash
exec >/tmp/medical-clock-details-20261011.log 2>&1
set -e
cat /etc/os-release
grep -R -l 'medical_offline_clock' /etc/systemd/system /etc/rc.local /etc/cron* /home/ncut/.bashrc 2>/dev/null || true
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_details_20261011.sh
