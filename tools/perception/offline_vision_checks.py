#!/usr/bin/env python2
from __future__ import print_function
import cv2, numpy as np, time, json, os
import camera_vision_web_20261011 as web
web.rospy.Time.now=staticmethod(lambda:web.rospy.Time.from_sec(time.time()))
checks={}
for marker_id in (0,1,7,49):
 marker=cv2.aruco.drawMarker(cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50),marker_id,240)
 image=np.full((400,400),255,np.uint8);image[80:320,80:320]=marker
 result=web.detect_markers(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR))
 checks['marker_'+str(marker_id)]=len(result)==1 and result[0]['id']==marker_id
state=web.VisionState();now=time.time()
state.last_image_wall=now;state.image_stamp=now;state.preview_stamp=now
checks['fresh_camera']=state.status()['camera_status']=='fresh'
state.image_stamp=now-5
checks['stale_source_rejected']=state.status()['camera_status']!='fresh'
state.image_stamp=now+5
checks['future_source_rejected']=state.status()['camera_status']!='fresh'
state.image_stamp=now;state.preview_stamp=now-5
checks['stale_preview_rejected']=state.status()['camera_status']!='fresh'
state.amcl=dict(stamp=now+5)
checks['future_amcl_rejected']=state.status()['amcl_status']=='stale'
checks['no_fusion']=state.status()['map_fusion'].startswith('disabled')
checks['no_motion_topics']=all(x not in open(os.path.join(os.path.dirname(__file__),f)).read()
 for f in ('camera_readonly_bridge.py',) for x in ('/cmd_vel','/initialpose','TransformBroadcaster'))
print(json.dumps(checks,indent=2))
assert all(checks.values()),checks
