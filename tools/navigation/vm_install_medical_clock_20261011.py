#!/usr/bin/env python2
"""Install staged clock packages from Ubuntu. Credentials stay out of files/logs.

VM sudo password is supplied as a transient command argument. Robot password is
read from the already authorized Ubuntu SSH helper, never printed or copied.
All uploads/preflight use that existing helper; root install uses Ubuntu SSH
with its pinned known-host file. There is no Windows-to-robot connection.
"""
from __future__ import print_function
import ast
import os
import shlex
import subprocess
import sys
import tempfile

helper = '/home/ncut/vm_connection_check_20261009.py'
stage = '/home/ncut/medical_clock_sync_20261011'
robot_stage = '/home/EPRobot/medical_clock_sync_20261011'
log = open(stage + '/install.log', 'a', 0)
sys.stdout = log
sys.stderr = log
vm_password = sys.argv[1]
robot_password = None
askpass_script = None
for node in ast.walk(ast.parse(open(helper).read())):
    if isinstance(node, ast.Call) and len(node.args) == 2:
        try:
            value = ast.literal_eval(node.args[1])
            if isinstance(value, str) and value.startswith('#!/bin/sh\nprintf'):
                robot_password = shlex.split(value.splitlines()[1])[-1]
                askpass_script = value
        except (ValueError, TypeError):
            pass
assert robot_password, 'AUTHORIZED_HELPER_CREDENTIAL_UNAVAILABLE'
if sys.argv[2:3] == ['--vm-script']:
    name = sys.argv[3]
    assert os.path.basename(name) == name
    process = subprocess.Popen(['sudo','-S','-p','','/bin/bash',stage+'/'+name],
        stdin=subprocess.PIPE,stdout=log,stderr=log)
    process.communicate(vm_password+'\n')
    assert process.returncode == 0, 'VM_ROOT_SCRIPT_FAILED'
    print('VM_ROOT_SCRIPT_COMPLETE')
    sys.exit(0)
subprocess.check_call(['python2', helper, '--command-file',
                       '/home/ncut/robot_field_static_preflight_20261011.sh'])
robot_script = sys.argv[3] if sys.argv[2:3] == ['--robot-script'] else None
if robot_script:
    assert os.path.basename(robot_script) == robot_script
    subprocess.check_call(['python2',helper,'--upload',stage+'/'+robot_script,robot_stage+'/'+robot_script])
    if robot_script == 'robot_fix_clock_guard_20261011.sh':
        subprocess.check_call(['python2',helper,'--upload',stage+'/medical_clock_boot_guard.py',
                              robot_stage+'/medical_clock_boot_guard_v2.py'])
elif sys.argv[2:] != ['--robot-only']:
    create = stage + '/create-stage.sh'
    with open(create, 'w') as stream:
        stream.write('set -e\ntest ! -e ' + robot_stage + '\nmkdir -m 700 ' + robot_stage + '\n')
    subprocess.check_call(['python2', helper, '--command-file', create])
    for name in ['chrony_3.2-4ubuntu4.5_arm64.deb', 'chrony-robot-offline.conf',
                 'chrony-robot-boot.conf', 'medical_clock_boot_guard.py',
                 'install_medical_chrony_20261011.sh']:
        subprocess.check_call(['python2', helper, '--upload', stage + '/' + name,
                              robot_stage + '/' + name])
    process = subprocess.Popen(['sudo', '-S', '-p', '', '/bin/bash',
        stage + '/install_medical_chrony_20261011.sh', 'vm', stage],
        stdin=subprocess.PIPE, stdout=log, stderr=log)
    process.communicate(vm_password + '\n')
    assert process.returncode == 0, 'VM_INSTALL_FAILED'
else:
    subprocess.check_call(['systemctl','is-active','chrony'])
    print('ROBOT_INSTALL_RETRY_PINNED_OPENSSH')
fd, askpass = tempfile.mkstemp(prefix='medical-clock-askpass-')
try:
    os.write(fd, askpass_script)
    os.close(fd)
    os.chmod(askpass, 0o700)
    env = os.environ.copy()
    env['DISPLAY'] = ':0'
    env['SSH_ASKPASS'] = askpass
    options = ['-T','-o','StrictHostKeyChecking=yes','-o',
               'UserKnownHostsFile=/home/ncut/medical-robot-known-hosts',
               '-o','HostKeyAlgorithms=ssh-ed25519','-o','ConnectTimeout=8',
               '-o','NumberOfPasswordPrompts=1']
    command = 'sudo -S -p "" /bin/bash ' + robot_stage + '/' + \
        (robot_script if robot_script else 'install_medical_chrony_20261011.sh robot '+robot_stage)
    process = subprocess.Popen(['setsid','ssh'] + options +
        ['EPRobot@192.168.12.1',command], stdin=subprocess.PIPE,
        stdout=log,stderr=log,env=env)
    process.communicate(robot_password + '\n')
    assert process.returncode == 0, 'ROBOT_INSTALL_FAILED'
finally:
    os.unlink(askpass)
print('ONE_WAY_CONTINUOUS_CLOCK_SERVICES_INSTALLED_NO_BASE_STARTED')
