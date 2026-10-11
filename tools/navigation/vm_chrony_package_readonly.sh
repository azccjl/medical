#!/bin/bash
exec >/tmp/medical-chrony-package-readonly-20261011.log 2>&1
set -e
echo VM_ARCH
dpkg --print-architecture
apt-cache policy chrony
apt-cache show chrony | head -n 65
apt-get --print-uris --yes --download-only -o Debug::NoLocking=1 install chrony || true
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/robot_chrony_package_readonly.sh
