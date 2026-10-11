#!/bin/bash
set -e
test "$(id -u)" = 0
test ! -e /etc/systemd/system/chrony.service.d/medical-network.conf
mkdir -p /etc/systemd/system/chrony.service.d
cat >/etc/systemd/system/chrony.service.d/medical-network.conf <<'EOF'
[Unit]
Wants=network-online.target
After=network-online.target
[Service]
Restart=on-failure
RestartSec=15s
EOF
systemctl daemon-reload
systemctl is-enabled chrony
systemctl is-active chrony
echo BOOT_RETRY_CONFIGURED_WITHOUT_RESTART_OR_CLOCK_STEP
