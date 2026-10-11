#!/bin/bash
exec >/tmp/medical-clock-inventory-20261011.log 2>&1
set -e
date -u -Ins
timedatectl status || true
timedatectl show || true
for command in chronyc chronyd ntpd ntpq adjtimex vmware-toolbox-cmd; do command -v "$command" || true; done
systemctl is-active systemd-timesyncd chrony ntp open-vm-tools || true
systemctl is-enabled systemd-timesyncd chrony ntp open-vm-tools || true
vmware-toolbox-cmd timesync status || true
cat /sys/devices/system/clocksource/clocksource0/current_clocksource
cat /sys/devices/system/clocksource/clocksource0/available_clocksource
ps -eo pid,args | grep -E '[c]hronyd|[n]tpd|[t]imesyncd|[v]mtoolsd|[m]edical_offline_clock' || true
for path in /etc/systemd/timesyncd.conf /etc/chrony/chrony.conf /etc/ntp.conf; do
  if test -e "$path"; then echo "CLOCK_CONFIG $path"; cat "$path"; fi
done
find /var/cache/apt/archives -maxdepth 1 -type f -name '*chrony*' -print
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_clock_inventory_20261011.sh
