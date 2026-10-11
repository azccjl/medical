#!/bin/bash
set -e
echo ROBOT_ARCH
dpkg --print-architecture
apt-cache policy chrony
apt-cache show chrony | head -n 65
apt-get --print-uris --yes --download-only -o Debug::NoLocking=1 install chrony || true
systemctl list-unit-files | grep -E 'medical.*clock|ntp|chrony|timesync' || true
