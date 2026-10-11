#!/bin/bash
# Standard-library read-only inspection. Never imports or executes robot programs.
set -e
python2 - <<'PY'
from __future__ import print_function
import os,glob,json,hashlib
candidate='/home/EPRobot/medical_ground_straight_pulse_v3_20261011.py'
manifest='/home/EPRobot/medical_staged_files_20261011.json'
expected={candidate:'c997fda7951424d7c29053b530809beff8cb6b658abdf7664b55807686dbd71c',
 '/home/EPRobot/medical_stationary_localization_v3_20261011.py':'aa06ade75f042131310bf2bad910070728472d68c486ebd3592e206a31b6384d',
 '/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py':'d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1'}
stop_paths=[p for p in ['/home/EPRobot/robot_ws/src/eprobot_start/script/medical_stop_window.py',
                      '/home/EPRobot/medical_stop_window.py'] if os.path.isfile(p)]
assert stop_paths, 'STOP_WINDOW_SOURCE_NOT_FOUND'
for path in stop_paths:
    expected[path]='15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43'
print('STOP_WINDOW_SOURCE_PATHS',json.dumps(stop_paths))
if os.path.exists(candidate):
    for path,value in expected.items():
        assert hashlib.sha256(open(path,'rb').read()).hexdigest()==value, ('FILE_SHA_MISMATCH',path)
    staged=json.load(open(manifest))
    assert staged['state']=='UPLOADED_NOT_STARTED'
    assert staged['candidate_sha256']==expected[candidate]
    print('STAGED_FILES_SHA256_MATCH')
else:
    assert not os.path.exists(manifest), 'UNEXPECTED_STAGE_MANIFEST'
    for path,value in expected.items():
        if path==candidate:continue
        assert hashlib.sha256(open(path,'rb').read()).hexdigest()==value, ('DEPENDENCY_CHANGED',path)
    print('CANDIDATE_TARGET_ABSENT_DEPENDENCIES_MATCH')
device=os.path.realpath('/dev/EPRobot_base');owners=[];running=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():continue
    for fd in glob.glob('/proc/'+pid+'/fd/*'):
        try:
            if os.readlink(fd)==device:owners.append(int(pid))
        except OSError:pass
    try:args=open('/proc/'+pid+'/cmdline','rb').read().split('\0')
    except IOError:continue
    if any(arg==candidate or (os.path.basename(arg).startswith(('medical_art_racecar','art_racecar')) and arg.endswith('.py'))
           or arg=='/home/EPRobot/medical_stationary_localization_v3_20261011.py' for arg in args):
        running.append(int(pid))
print('SERIAL_OWNERS',json.dumps(owners))
print('STAGED_OR_BASE_PROCESSES',json.dumps(running))
assert not owners and not running,'BASE_OR_CANDIDATE_RUNNING'
print('READ_ONLY_CHECK_COMPLETE_NO_PROGRAM_EXECUTED')
PY
