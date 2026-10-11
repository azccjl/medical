#!/bin/bash
set -e
cat /etc/os-release
uname -a
dpkg-query -W libc6 libcap2 libedit2 libnss3 libseccomp2 ucf iproute2 lsb-base libcap2-bin adduser || true
sudo -n true && echo ROBOT_PASSWORDLESS_SUDO || true
find /etc/systemd/system /lib/systemd/system -maxdepth 2 -type f -iname '*clock*' -print
grep -R -l 'medical_offline_clock' /etc/systemd/system /etc/rc.local /etc/cron* /home/EPRobot/.bashrc 2>/dev/null || true
ps -eo pid,comm,args | grep -E '[m]edical.*clock|[r]oslaunch|[r]oscore|[r]plidar' || true
cat /etc/apt/sources.list
ss -ulnp | grep ':123 ' || true
