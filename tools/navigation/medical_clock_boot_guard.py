#!/usr/bin/env python2
"""Permit chrony's initial clock step only with no ROS and no serial owner."""
from __future__ import print_function
import glob
import os
import socket
import subprocess
import sys

if os.geteuid() != 0 or socket.gethostname() != 'EPRobot' or not os.path.isfile('/etc/chrony/medical-boot.conf'):
    raise RuntimeError('ROBOT_ROOT_REQUIRED')

def active_ros_processes():
    # Standalone to retain chrony's ProtectHome=yes systemd sandbox.
    names = set(['roscore','rosmaster','roslaunch','rosout','nodelet','rviz',
                 'art_racecar.py','eprobot_joy_node','huanyu_joy_node'])
    found = []
    for pid in os.listdir('/proc'):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            args = open('/proc/'+pid+'/cmdline','rb').read().split('\0')
        except IOError:
            continue
        if any('/opt/ros/' in arg or '/robot_ws/' in arg or '/carto_ws/' in arg or
               os.path.basename(arg) in names for arg in args):
            found.append(pid)
    return found

device = os.path.realpath('/dev/EPRobot_base')
owners = []
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    for fd in glob.glob('/proc/' + pid + '/fd/*'):
        try:
            if os.readlink(fd) == device:
                owners.append(pid)
        except OSError:
            pass
ros = active_ros_processes()
if ros or owners:
    print('BOOT_STEP_SKIPPED_ROS_OR_SERIAL_ACTIVE; continuous slew only')
    sys.exit(0)
print('BOOT_CLOCK_INITIALIZATION_WITH_NO_ROS_NO_SERIAL')
sys.stdout.flush()
sys.exit(subprocess.call(['/usr/sbin/chronyd', '-q', '-t', '25',
                          '-f', '/etc/chrony/medical-boot.conf']))
