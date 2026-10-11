#!/usr/bin/env python3
"""Bundle clock configuration, verified vendor packages and offline commands."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('--evidence-dir',type=Path,required=True)
cli.add_argument('--output',type=Path,required=True)
a=cli.parse_args()
repo=Path(__file__).resolve().parents[2]
source=repo/'tools/navigation'
names=['chrony-vm-offline.conf','chrony-robot-offline.conf','chrony-robot-boot.conf',
       'medical_clock_boot_guard.py','install_medical_chrony_20261011.sh',
       'vm_install_medical_clock_20261011.py','vm_verify_medical_clock_20261011.py',
       'vm_verify_medical_clock_20261011.sh','vm_verify_medical_clock_v2_20261011.sh',
       'robot_clock_verify_20261011.sh','robot_clock_verify_v2_20261011.sh',
       'robot_field_static_preflight_20261011.sh','rollback_medical_clock_20261011.sh']
files={n:(source/n).read_bytes() for n in names}
files['vm_verify_medical_clock_v2_20261011.py']=files['vm_verify_medical_clock_20261011.py']
vendor={'chrony_3.2-4ubuntu4.5_amd64.deb':'6add943b7a4882525510d67b851283883f9f84d3808660ce7f793568e2a3ccef',
        'chrony_3.2-4ubuntu4.5_arm64.deb':'ed36dda3659d3039244ad0c5bcfd690d88335bec90ad642066f1ea4af7c23264'}
for name,sha in vendor.items():
    files[name]=(a.evidence_dir/name).read_bytes()
    assert hashlib.sha256(files[name]).hexdigest()==sha,name
for name in ['chrony-amd64-metadata.txt','chrony-arm64-metadata.txt']:
    files[name]=(a.evidence_dir/name).read_bytes()
files['README.md']=(repo/'docs/offline-clock-sync-20261011.md').read_bytes()
manifest=dict(files={n:hashlib.sha256(v).hexdigest() for n,v in files.items()},
              motion_commands_sent=False,credential_files_included=False,
              package_sources=['https://archive.ubuntu.com/ubuntu/',
                               'https://ports.ubuntu.com/ubuntu-ports/'])
with zipfile.ZipFile(a.output,'x',zipfile.ZIP_DEFLATED) as z:
    for name,data in files.items():z.writestr(name,data)
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(json.dumps(dict(output=str(a.output),files=len(files),sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())))
