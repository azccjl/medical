#!/bin/bash
systemctl --no-pager --full status chrony || true
systemctl cat chrony
journalctl -u chrony --no-pager -n 35
ls -l /usr/local/sbin/medical_clock_boot_guard.py
cat /etc/chrony/chrony.conf
cat /etc/systemd/system/chrony.service.d/medical-boot.conf
chronyc tracking || true
