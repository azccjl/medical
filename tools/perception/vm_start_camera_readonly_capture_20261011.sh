#!/bin/bash
set +e
export PYTHONIOENCODING=utf-8
bash /home/ncut/medical_camera_assist1_20261011/vm_start_camera_readonly_20261011.sh > /home/ncut/medical_camera_assist1_20261011/start-camera.out 2>&1
echo $? > /home/ncut/medical_camera_assist1_20261011/start-camera.rc
