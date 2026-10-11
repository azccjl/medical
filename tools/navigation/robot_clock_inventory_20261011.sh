#!/bin/bash
# Read-only: no clock change, no ROS/control startup.
set -e
date -u -Ins
timedatectl status || true
timedatectl show || true
for command in chronyc chronyd ntpd ntpq adjtimex; do command -v "$command" || true; done
systemctl is-active systemd-timesyncd chrony ntp || true
systemctl is-enabled systemd-timesyncd chrony ntp || true
ps -eo pid,args | grep -E '[c]hronyd|[n]tpd|[t]imesyncd|[m]edical_offline_clock' || true
for path in /etc/systemd/timesyncd.conf /etc/chrony/chrony.conf /etc/ntp.conf; do
  if test -e "$path"; then echo "CLOCK_CONFIG $path"; cat "$path"; fi
done
python2 - <<'PY'
import os,glob,json
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for f in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(pid)
        except OSError:pass
print('BASE_SERIAL_OWNERS',json.dumps(owners))
assert not owners,owners
PY
sha256sum /home/EPRobot/medical_offline_clock.py
cat /home/EPRobot/medical_offline_clock.py
