#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Local RGB -> 5 Hz JPEG + QR observations. No control publications."""
from __future__ import print_function
import json
import threading
import time
import cv2
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import String
from pyzbar.pyzbar import decode, ZBarSymbol


class CameraBridge(object):
    def __init__(self):
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.frame = None
        self.last_seq = None
        self.image_pub = rospy.Publisher('/medical_vision/image/compressed', CompressedImage, queue_size=1)
        self.qr_pub = rospy.Publisher('/medical_vision/qr_observations', String, queue_size=1)
        rospy.Subscriber('/medical_astra/rgb/image_raw', Image, self.receive, queue_size=1, buff_size=2**22)

    def receive(self, msg):
        with self.lock:
            self.frame = msg

    def run(self):
        rate = rospy.Rate(5)
        while not rospy.is_shutdown():
            with self.lock:
                msg = self.frame
            if msg is not None and (msg.header.stamp.to_nsec(), msg.header.seq) != self.last_seq:
                self.last_seq = (msg.header.stamp.to_nsec(), msg.header.seq)
                try:
                    image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
                    observations = []
                    for code in decode(image, symbols=[ZBarSymbol.QRCODE]):
                        text = code.data.decode('utf-8', 'replace')
                        points = [[int(p.x), int(p.y)] for p in code.polygon]
                        x, y, w, h = code.rect
                        cv2.rectangle(image, (x,y), (x+w,y+h), (255,180,0), 2)
                        cv2.putText(image, 'QR', (x,max(15,y-5)), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,180,0), 2)
                        observations.append(dict(text=text, polygon=points, rect=[x,y,w,h]))
                    ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        compressed = CompressedImage()
                        compressed.header = msg.header
                        compressed.format = 'jpeg'
                        compressed.data = data.tostring()
                        self.image_pub.publish(compressed)
                    self.qr_pub.publish(String(data=json.dumps(dict(
                        stamp=msg.header.stamp.to_sec(), frame_id=msg.header.frame_id,
                        observations=observations, read_only=True, task_execution=False), ensure_ascii=True)))
                except Exception as exc:
                    rospy.logwarn_throttle(5, 'camera bridge: %s' % exc)
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('medical_camera_readonly_bridge')
    CameraBridge().run()
