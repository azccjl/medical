#!/bin/bash
exec >/home/ncut/medical_camera_assist1_20261011/inventory.log 2>&1
set -e
export PYTHONIOENCODING=utf-8
python2 /home/ncut/vm_connection_check_20261009.py --command-file /home/ncut/medical_camera_assist1_20261011/robot_camera_inventory_20261011.sh
source /opt/ros/melodic/setup.bash
python2 - <<'PY'
import cv2,sys
print('VM_CV2',cv2.__version__,'aruco',hasattr(cv2,'aruco'),'QRCodeDetector',hasattr(cv2,'QRCodeDetector'))
try:
 from pyzbar.pyzbar import decode
 print('VM_PYZBAR_AVAILABLE')
except Exception as e:print('VM_PYZBAR_UNAVAILABLE',str(e))
from cv_bridge import CvBridge
print('VM_CV_BRIDGE_AVAILABLE')
PY
