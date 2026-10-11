#!/bin/bash
set -e
test "$(id -u)" = 0
test -e /var/backups/medical-clock-sync-20261011
cp -a /usr/local/sbin/medical_clock_boot_guard.py /var/backups/medical-clock-sync-20261011/boot-guard-v1.py
install -m 755 /home/EPRobot/medical_clock_sync_20261011/medical_clock_boot_guard_v2.py /usr/local/sbin/medical_clock_boot_guard.py
systemctl reset-failed chrony
systemctl start chrony
systemctl --no-pager --full status chrony
chronyc tracking
chronyc -n sources -v
