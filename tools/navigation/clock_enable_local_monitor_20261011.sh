#!/bin/bash
set -e
test "$(id -u)" = 0
test ! -e /var/backups/medical-clock-sync-20261011/chrony-before-local-monitor.conf
cp -a /etc/chrony/chrony.conf /var/backups/medical-clock-sync-20261011/chrony-before-local-monitor.conf
sed -i 's/^cmdport 0$/bindcmdaddress 127.0.0.1\ncmdport 323/' /etc/chrony/chrony.conf
systemctl restart chrony
systemctl is-active chrony
chronyc tracking
