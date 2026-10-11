#!/bin/bash
# Root, with all ROS and chassis processes stopped. Preserve every backup.
set -e
test "$(id -u)" = 0
python2 - <<'PY'
import os,glob
names=set(['roscore','rosmaster','roslaunch','rosout','nodelet','rviz'])
active=[]
for p in os.listdir('/proc'):
    if not p.isdigit() or int(p)==os.getpid():continue
    try:args=open('/proc/'+p+'/cmdline','rb').read().split('\0')
    except IOError:continue
    if any('/opt/ros/' in a or '/robot_ws/' in a or '/carto_ws/' in a or os.path.basename(a) in names for a in args):active.append(p)
d=os.path.realpath('/dev/EPRobot_base');owners=[]
for p in os.listdir('/proc'):
    if not p.isdigit():continue
    for f in glob.glob('/proc/'+p+'/fd/*'):
        try:
            if os.readlink(f)==d:owners.append(p)
        except OSError:pass
assert not active and not owners, ('STOP_ROS_AND_BASE_BEFORE_CLOCK_ROLLBACK',active,owners)
PY
test -e /var/backups/medical-clock-sync-20261011/timesyncd.conf
systemctl disable --now chrony
cp -a /var/backups/medical-clock-sync-20261011/timesyncd.conf /etc/systemd/timesyncd.conf
if grep -qx enabled /var/backups/medical-clock-sync-20261011/timesyncd-enabled.txt; then
  systemctl enable systemd-timesyncd
fi
if grep -qx active /var/backups/medical-clock-sync-20261011/timesyncd-active.txt; then
  systemctl start systemd-timesyncd
fi
echo PREVIOUS_TIME_SERVICE_RESTORED_BACKUPS_PRESERVED
