#!/bin/bash
# Root installation; package/config files must already be staged by Ubuntu SSH.
set -eu
role=$1
stage=$2
test "$(id -u)" = 0
test "$role" = vm || test "$role" = robot
case "$stage" in /home/ncut/medical_clock_sync_20261011|/home/EPRobot/medical_clock_sync_20261011) ;; *) exit 12;; esac
backup=/var/backups/medical-clock-sync-20261011
test ! -e "$backup"
if [ "$role" = robot ]; then
  test -d /home/EPRobot/robot_ws
  pkg=chrony_3.2-4ubuntu4.5_arm64.deb
  expected=ed36dda3659d3039244ad0c5bcfd690d88335bec90ad642066f1ea4af7c23264
else
  test ! -d /home/EPRobot/robot_ws
  pkg=chrony_3.2-4ubuntu4.5_amd64.deb
  expected=6add943b7a4882525510d67b851283883f9f84d3808660ce7f793568e2a3ccef
fi
echo "$expected  $stage/$pkg" | sha256sum --check
mkdir -m 700 "$backup"
systemctl is-enabled systemd-timesyncd >"$backup/timesyncd-enabled.txt" || true
systemctl is-active systemd-timesyncd >"$backup/timesyncd-active.txt" || true
cp -a /etc/systemd/timesyncd.conf "$backup/"
if test -e /etc/chrony; then cp -a /etc/chrony "$backup/chrony"; fi
# Prevent the package's default service from starting with external sources.
systemctl mask chrony.service
DEBIAN_FRONTEND=noninteractive dpkg -i "$stage/$pkg"
install -m 644 "$stage/chrony-$role-offline.conf" /etc/chrony/chrony.conf
mkdir -p /etc/systemd/system/chrony.service.d
cat >/etc/systemd/system/chrony.service.d/medical-network.conf <<'EOF'
[Unit]
Wants=network-online.target
After=network-online.target
[Service]
Restart=on-failure
RestartSec=15s
EOF
if [ "$role" = robot ]; then
  install -m 644 "$stage/chrony-robot-boot.conf" /etc/chrony/medical-boot.conf
  install -m 755 "$stage/medical_clock_boot_guard.py" /usr/local/sbin/medical_clock_boot_guard.py
  mkdir -p /etc/systemd/system/chrony.service.d
  cat >/etc/systemd/system/chrony.service.d/medical-boot.conf <<'EOF'
[Service]
ExecStartPre=/usr/bin/python2 /usr/local/sbin/medical_clock_boot_guard.py
EOF
fi
systemctl disable --now systemd-timesyncd
systemctl daemon-reload
systemctl unmask chrony.service
systemctl enable --now chrony.service
systemctl --no-pager --full status chrony.service
chronyc tracking
chronyc sources -v
echo MEDICAL_CHRONY_INSTALLED_$role
