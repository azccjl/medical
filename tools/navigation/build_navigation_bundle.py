#!/usr/bin/env python3
"""Create a self-contained, versioned Ubuntu staging bundle; never deploy/run it."""
import argparse, hashlib, json, os, zipfile
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--repository',required=True);p.add_argument('--output',required=True)
a=p.parse_args();root=Path(a.repository);files={}
scripts=('medical_status.py','map_web_view.py','mapping_heading_scale.py','site_localization_view.py',
         'route_geometry.py','route_workbench.py','route_workbench.html','navigation_policy.py',
         'navigation_scan_guard.py','navigation_command_gate.py','navigation_audited_base.py',
         'route_action_runner.py','install_ros1_navigation.sh','heading_fix/medical_stop_window.py')
for n in scripts:files['src/medical_robot/scripts/'+n]=root/'medical_robot/scripts'/n
for n in ('CMakeLists.txt','package.xml'):files['src/medical_robot/'+n]=root/'medical_robot'/n
for f in (root/'medical_robot/config/navigation').glob('*'):
    if f.is_file():files['src/medical_robot/config/navigation/'+f.name]=f
for n in ('navigation_field_staging.launch','site_localization_observe.launch'):
    files['src/medical_robot/launch/'+n]=root/'medical_robot/launch'/n
for n in ('map.yaml','medical-live-map-20261010.pgm'):files['maps/raw/'+n]=root/'maps/slam-20261010'/n
for n in ('site-geometry-candidate.yaml','site-geometry-candidate.pgm','site-annotations.json'):
    files['maps/structured/'+n]=root/'maps/site-layout-display-v2-20261011'/n
for f in (root/'tools/navigation').glob('*'):
    if f.is_file() and f.name!='build_navigation_bundle.py':files[f.name]=f
blobs={n:f.read_bytes() for n,f in files.items()}
manifest={'schema_version':1,'motion_enabled':False,'files':{n:hashlib.sha256(b).hexdigest() for n,b in blobs.items()}}
with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for n,b in blobs.items():z.writestr(n,b)
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(json.dumps({'files':len(files),'zip':a.output,'motion_enabled':False}))
