#!/usr/bin/env python2
from __future__ import print_function
import os, json, time, cv2, numpy as np, rospy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from camera_vision_web_20261011 import detect_markers

stage='/home/ncut/medical_camera_assist1_20261011'
out=stage+'/camera-acceptance.json'
# Reserve a new evidence output before touching any image or report.
fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
frames=[]; qr=[]
def frame(m): frames.append((time.time(),m))
def observe(m): qr.append(json.loads(m.data))
rospy.init_node('medical_camera_acceptance_readonly',anonymous=True)
rospy.Subscriber('/medical_vision/image/compressed',CompressedImage,frame,queue_size=1)
rospy.Subscriber('/medical_vision/qr_observations',String,observe,queue_size=1)
time.sleep(10)
report=dict(frames=len(frames),qr_messages=len(qr),motion_sent=False)
if frames:
 report['rate_hz']=(len(frames)-1)/(frames[-1][0]-frames[0][0]) if len(frames)>1 else 0
 m=frames[-1][1]
 image=cv2.imdecode(np.frombuffer(m.data,dtype=np.uint8),cv2.IMREAD_COLOR)
 report.update(width=int(image.shape[1]),height=int(image.shape[0]),frame_id=m.header.frame_id,
               jpeg_bytes=len(m.data),source_stamp=m.header.stamp.to_sec(),last_qr=qr[-1] if qr else None)
 with open(stage+'/bridge-sample.jpg','wb') as f:f.write(m.data)
else: report['error']='no bridge frames'

dictionary=cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
marker=cv2.aruco.drawMarker(dictionary,0,360)
test=np.full((480,640),255,np.uint8);test[60:420,140:500]=marker
detected=detect_markers(cv2.cvtColor(test,cv2.COLOR_GRAY2BGR))
report['synthetic_aruco_id0_pass']=bool(detected and detected[0]['id']==0)
cv2.imwrite(stage+'/aruco-id0-detection-test.png',test)
# SVG explicit physical dimensions: the black outer square is 120 mm.
grid=cv2.aruco.drawMarker(dictionary,0,6)
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="140mm" height="140mm" viewBox="0 0 140 140">',
     '<rect width="140" height="140" fill="white"/>']
for y in range(6):
 for x in range(6):
  if grid[y,x]==0:svg.append('<rect x="%d" y="%d" width="20" height="20" fill="black"/>'%(10+x*20,10+y*20))
svg.append('</svg>')
open(stage+'/aruco-id0-120mm.svg','w').write('\n'.join(svg))
with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
assert frames and report['synthetic_aruco_id0_pass'] and len(qr)>0,report
