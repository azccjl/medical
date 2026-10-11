#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Read-only camera preview and marker observation page.

This process never publishes /cmd_vel, /initialpose, TF, or any base command.
It intentionally reports camera observations separately from AMCL.  Camera to
map fusion stays disabled until measured landmark poses and camera/base
extrinsics are supplied and validated.
"""
from __future__ import print_function
import BaseHTTPServer
import json
import math
import os
import socket
import threading
import time
import urllib
import SocketServer

import cv2
import numpy as np
import rospy
from geometry_msgs.msg import PoseWithCovarianceStamped
from sensor_msgs.msg import CameraInfo, CompressedImage
from std_msgs.msg import String


HOST = os.environ.get('MEDICAL_VISION_HOST', '0.0.0.0')
PORT = int(os.environ.get('MEDICAL_VISION_PORT', '8085'))
IMAGE_TOPIC = os.environ.get('MEDICAL_VISION_IMAGE_TOPIC',
                             '/medical_vision/image/compressed')
CAMERA_INFO_TOPIC = os.environ.get('MEDICAL_VISION_CAMERA_INFO_TOPIC',
                                   '/medical_astra/rgb/camera_info')
AMCL_TOPIC = '/amcl_pose'
LANDMARK_FILE = os.environ.get(
    'MEDICAL_VISION_LANDMARK_FILE',
    '/home/ncut/medical_camera_assist1_20261011/landmarks.json')


class VisionState(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.jpeg = None
        self.last_image_wall = 0.0
        self.image_stamp = 0.0
        self.frame_id = ''
        self.preview_stamp = 0.0
        self.markers = []
        self.last_process_wall = 0.0
        self.camera_info = None
        self.amcl = None
        self.qr = None
        self.landmarks = {}
        self.load_landmarks()

    def load_landmarks(self):
        try:
            with open(LANDMARK_FILE, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.landmarks = data.get('markers', {})
        except Exception:
            self.landmarks = {}

    def image_cb(self, msg):
        now = time.time()
        # Limit CPU and web refresh work while retaining the latest frame.
        if now - self.last_process_wall < 0.12:
            with self.lock:
                self.last_image_wall = now
                self.image_stamp = msg.header.stamp.to_sec()
                self.frame_id = msg.header.frame_id
            return
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return
            markers = detect_markers(frame)
            annotated = frame.copy()
            for item in markers:
                pts = np.asarray(item['corners'], dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(annotated, [pts], True, (0, 255, 0), 2)
                cx, cy = item['center']
                cv2.circle(annotated, (int(cx), int(cy)), 4, (0, 0, 255), -1)
                cv2.putText(annotated, 'ArUco %s' % item['id'],
                            (int(cx) + 6, int(cy) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            with self.lock:
                self.last_process_wall = now
                self.last_image_wall = now
                self.image_stamp = msg.header.stamp.to_sec()
                self.frame_id = msg.header.frame_id
                self.markers = markers
            # Encode outside the lock; text overlay keeps the browser useful
            # even when no marker is visible.
            with self.lock:
                info = self.status_locked()
            lines = [
                'camera: %s  frame: %s' % (info['camera_status'], self.frame_id or '?'),
                'markers: %d  map fusion: %s' % (len(markers), info['map_fusion']),
                'AMCL: %s' % info['amcl_status'],
            ]
            y = 22
            for line in lines:
                cv2.putText(annotated, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.52, (0, 255, 255), 2)
                y += 21
            ok, encoded = cv2.imencode('.jpg', annotated,
                                       [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if ok:
                with self.lock:
                    self.jpeg = encoded.tostring()
                    self.preview_stamp = msg.header.stamp.to_sec()
        except Exception as exc:
            rospy.logwarn_throttle(5.0, 'camera vision frame error: %s' % exc)

    def camera_info_cb(self, msg):
        with self.lock:
            self.camera_info = {
                'width': int(msg.width), 'height': int(msg.height),
                'frame_id': msg.header.frame_id,
                'K': [float(x) for x in msg.K],
                'D': [float(x) for x in msg.D],
                'valid_intrinsics': bool(msg.width and msg.height and msg.K[0] > 0 and msg.K[4] > 0),
            }

    def amcl_cb(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        with self.lock:
            self.amcl = {
                'stamp': msg.header.stamp.to_sec(),
                'frame_id': msg.header.frame_id,
                'x': float(p.x), 'y': float(p.y), 'yaw': float(yaw),
                'cov_x': float(msg.pose.covariance[0]),
                'cov_y': float(msg.pose.covariance[7]),
                'cov_yaw': float(msg.pose.covariance[35]),
            }

    def qr_cb(self, msg):
        try:
            value = json.loads(msg.data)
            with self.lock:
                self.qr = value
        except (ValueError, TypeError):
            pass

    def status_locked(self):
        now = time.time()
        ros_now = rospy.Time.now().to_sec()
        image_age = None if not self.last_image_wall else max(0.0, now - self.last_image_wall)
        source_age = None if not self.image_stamp else ros_now - self.image_stamp
        preview_age = None if not self.preview_stamp else ros_now - self.preview_stamp
        fresh = (image_age is not None and image_age < 1.0 and source_age is not None
                 and -.02 <= source_age <= 1.0 and preview_age is not None and -.02 <= preview_age <= 1.0)
        camera_status = 'no frame' if image_age is None else ('fresh' if fresh else 'stale or clock mismatch')
        if self.amcl is None:
            amcl_status = 'unavailable'
        else:
            age = ros_now - self.amcl['stamp'] if self.amcl['stamp'] else None
            if age is None or age > 2.0 or age < -.02:
                amcl_status = 'stale'
            else:
                amcl_status = 'x=%.3f y=%.3f yaw=%.1fdeg age=%.2fs' % (
                    self.amcl['x'], self.amcl['y'], math.degrees(self.amcl['yaw']), age)
        map_fusion = 'disabled: extrinsics/landmarks unvalidated'
        if self.landmarks:
            map_fusion = 'observation only: manifest present, fusion disabled'
        return {
            'camera_status': camera_status, 'image_age_s': image_age,
            'image_source_age_s': source_age, 'preview_source_age_s': preview_age,
            'frame_id': self.frame_id, 'markers': self.markers,
            'amcl_status': amcl_status, 'amcl': self.amcl,
            'camera_info': self.camera_info, 'map_fusion': map_fusion,
            'landmark_manifest': bool(self.landmarks),
            'read_only': True,
            'qr': self.qr,
        }

    def status(self):
        with self.lock:
            return self.status_locked()


def detect_markers(frame):
    if not hasattr(cv2, 'aruco'):
        return []
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        else:
            dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        params = cv2.aruco.DetectorParameters_create()
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dictionary, parameters=params)
        result = []
        if ids is None:
            return result
        for c, marker_id in zip(corners, ids.flatten().tolist()):
            pts = c.reshape((-1, 2))
            center = (float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1])))
            result.append({'id': int(marker_id), 'center': center,
                           'corners': [[float(x), float(y)] for x, y in pts.tolist()]})
        return result
    except Exception:
        return []


STATE = VisionState()


HTML = r'''<!doctype html><meta charset="utf-8"><title>Medical Camera Assist</title>
<style>body{font-family:Arial;background:#111;color:#eee;margin:18px}img{max-width:100%;border:1px solid #555}pre{background:#222;padding:10px;white-space:pre-wrap}.ok{color:#6f6}.warn{color:#fc6}</style>
<h2>车载摄像头观测</h2><p class="warn">只读观测，不控制车辆。标记安装和标定完成后才能辅助地图定位。</p>
<p id="summary">等待相机...</p><img src="/stream.mjpg"/>
<p id="codes"></p><details><summary>诊断详情</summary><pre id="state">加载中...</pre></details>
<script>async function poll(){try{let r=await fetch('/state.json',{cache:'no-store'});let j=await r.json();let fresh=j.camera_status==='fresh';let s=document.getElementById('summary');s.textContent=(fresh?'相机实时在线':'相机未在线、画面过期或时钟异常')+' ｜ 定位：'+(j.amcl_status==='unavailable'?'尚无实时位置':j.amcl_status==='stale'?'位置已过期':j.amcl_status)+' ｜ 视觉地图定位：尚未标定';s.className=fresh?'ok':'warn';document.getElementById('codes').textContent='ArUco ID：'+j.markers.map(m=>m.id).join(', ')+' ｜ 二维码：'+((j.qr&&j.qr.observations)||[]).map(q=>q.text).join('，');document.getElementById('state').textContent=JSON.stringify(j,null,2)}catch(e){document.getElementById('summary').textContent='连接中断'}}setInterval(poll,1000);poll()</script>'''


class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index.html'):
            body = HTML.encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path.startswith('/state.json'):
            body = json.dumps(STATE.status(), ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path.startswith('/snapshot.jpg'):
            with STATE.lock: body = STATE.jpeg
            if body is None:
                self.send_error(503, 'No camera frame'); return
            self.send_response(200); self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.path.startswith('/stream.mjpg'):
            self.send_response(200); self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame'); self.end_headers()
            try:
                while not rospy.is_shutdown():
                    with STATE.lock: frame = STATE.jpeg
                    if frame:
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(frame)); self.wfile.write(frame); self.wfile.write(b'\r\n'); self.wfile.flush()
                    time.sleep(0.2)
            except Exception:
                pass
            return
        self.send_error(404)


def main():
    global STATE
    rospy.init_node('medical_camera_vision_web_readonly', anonymous=False)
    rospy.Subscriber(IMAGE_TOPIC, CompressedImage, STATE.image_cb, queue_size=1, buff_size=2**24)
    rospy.Subscriber(CAMERA_INFO_TOPIC, CameraInfo, STATE.camera_info_cb, queue_size=1)
    rospy.Subscriber(AMCL_TOPIC, PoseWithCovarianceStamped, STATE.amcl_cb, queue_size=1)
    rospy.Subscriber('/medical_vision/qr_observations', String, STATE.qr_cb, queue_size=1)
    class ThreadingHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    rospy.loginfo('medical camera vision web listening on %s:%d topic=%s', HOST, PORT, IMAGE_TOPIC)
    server.timeout = 0.5
    while not rospy.is_shutdown():
        server.handle_request()
    server.server_close()


if __name__ == '__main__':
    main()
