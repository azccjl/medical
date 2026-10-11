#!/bin/bash
set -e
source /home/EPRobot/medical_robot_env.sh
python2 - <<'PY'
import cv2, json
print('CV2',cv2.__version__,'ARUCO',hasattr(cv2,'aruco'))
try:
 from pyzbar.pyzbar import decode, ZBarSymbol
 print('QR_DECODER_AVAILABLE')
except Exception as e: print('QR_DECODER_UNAVAILABLE',str(e))
from cv_bridge import CvBridge
print('CV_BRIDGE_AVAILABLE')
PY
