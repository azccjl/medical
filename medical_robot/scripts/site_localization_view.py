#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Display maps, task regions and live ROS localization. No ROS publishers."""
from __future__ import print_function
import argparse
import json
import math
import os
import threading
import time
try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer


def yaw(q):
    return math.atan2(2.0 * (q.w*q.z + q.x*q.y), 1.0-2.0*(q.y*q.y+q.z*q.z))


def load_map(filename):
    import yaml
    with open(filename) as handle:
        meta = yaml.safe_load(handle)
    path = meta['image']
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(filename), path)
    with open(path, 'rb') as handle:
        blob = handle.read()
    tokens, at = [], 0
    while len(tokens) < 4:
        if blob[at:at+1] == b'#':
            at = blob.index(b'\n', at)+1
        elif blob[at:at+1].isspace():
            at += 1
        else:
            end = at
            while not blob[end:end+1].isspace():
                end += 1
            tokens.append(blob[at:end]); at = end
    if tokens[0] != b'P5' or int(tokens[3]) != 255:
        raise ValueError('Expected 8-bit P5 PGM')
    if blob[at:at+2] == b'\r\n':
        at += 2
    else:
        at += 1
    width, height = int(tokens[1]), int(tokens[2])
    pixels = bytearray(blob[at:])
    if len(pixels) != width*height:
        raise ValueError('PGM dimensions do not match data')
    cells = []
    for row in range(height-1, -1, -1):
        for col in range(width):
            pixel = pixels[row*width+col]
            occ = pixel/255.0 if meta.get('negate', 0) else (255-pixel)/255.0
            cells.append(100 if occ > meta['occupied_thresh'] else 0 if occ < meta['free_thresh'] else -1)
    return dict(width=width, height=height, resolution=float(meta['resolution']),
                origin=meta['origin'], data=cells)


PAGE = u'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>医运机器人 · 实时定位</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#192536;font-family:Arial,"Microsoft YaHei",sans-serif}
header{padding:18px 24px;background:white;border-bottom:1px solid #dde4ec}h1{font-size:23px;margin:0 0 8px}.muted{color:#637389;font-size:14px}
main{display:flex;gap:20px;padding:20px;align-items:flex-start}.map{flex:1;max-width:850px;background:white;border-radius:14px;padding:16px}
canvas{width:100%;aspect-ratio:1;display:block;background:#f8fafc}aside{width:290px;background:white;border-radius:14px;padding:20px}h2{font-size:17px;margin:0 0 16px}
button{padding:9px 12px;border:1px solid #bac6d4;border-radius:7px;background:white;cursor:pointer;margin:0 6px 8px 0}button.active{background:#263c59;color:white}
.status{padding:12px;background:#fff1cf;border-radius:8px;margin-bottom:16px}.data{line-height:1.9;font-size:14px}.legend{font-size:13px;color:#637389;line-height:1.9}
@media(max-width:800px){main{flex-direction:column}aside{width:100%}}
</style><header><h1>医运机器人 · 实时定位</h1><div class="muted">蓝色箭头的小圆心表示后轴参考点，箭头指向车头；橙色圆点表示雷达中心。</div></header>
<main><section class="map"><button id="raw" class="active" onclick="select('raw')">原始扫描地图</button><button id="structured" onclick="select('structured')">整理后场地图</button>
<canvas id="c" width="800" height="800"></canvas><div class="legend">蓝色箭头：后轴参考点及车头方向　橙点：雷达中心（参考点前方 13.5 cm）　红点：雷达回波<br>绿色方框 A/B/C：取样　黄色方框 1–4：送样　紫色线：识别区域<br>整理图按规则尺寸生成，窗口及识别区域坐标待实地标定。</div></section>
<aside><h2>定位状态</h2><div class="status" id="status">正在连接显示服务…</div><div class="data" id="pose">等待位置估计</div><hr><div class="legend">本页用于观察位置和地图对齐。当前阶段需要核对雷达点与墙线、挡板边界是否重合。</div></aside></main>
<script>
let mode='raw',latest=null;const c=document.getElementById('c'),ctx=c.getContext('2d');
function select(k){mode=k;for(let id of ['raw','structured'])document.getElementById(id).classList.toggle('active',id===k);if(latest)draw(latest)}
function draw(s){let m=s.maps[mode];if(!m)return;ctx.clearRect(0,0,800,800);let scale=Math.min(750/m.width,750/m.height),dx=(800-m.width*scale)/2,dy=(800-m.height*scale)/2;
let off=document.createElement('canvas');off.width=m.width;off.height=m.height;let o=off.getContext('2d'),im=o.createImageData(m.width,m.height);
for(let row=0;row<m.height;row++)for(let col=0;col<m.width;col++){let v=m.data[row*m.width+col],i=((m.height-1-row)*m.width+col)*4,g=v<0?205:(v>=65?25:254);im.data[i]=im.data[i+1]=im.data[i+2]=g;im.data[i+3]=255}o.putImageData(im,0,0);ctx.imageSmoothingEnabled=false;ctx.drawImage(off,dx,dy,m.width*scale,m.height*scale);
const a=m.origin[2]||0,ca=Math.cos(a),sa=Math.sin(a);function point(x,y){let u=x-m.origin[0],v=y-m.origin[1];return [dx+(ca*u+sa*v)/m.resolution*scale,dy+(m.height-(-sa*u+ca*v)/m.resolution)*scale]}
function region(p,color,fill){ctx.beginPath();p.forEach((v,i)=>{let z=point(v[0],v[1]);i?ctx.lineTo(...z):ctx.moveTo(...z)});if(fill){ctx.closePath();ctx.fillStyle=fill;ctx.fill()}ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke()}
for(let [k,v]of Object.entries(s.annotations.windows||{})){let b=v.bounds_from_left_top_m,p=[];for(let q of [[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]])p.push(site(q));let col='ABC'.includes(k)?'#15965f':'#b57a00';region(p,col,'ABC'.includes(k)?'#24b36b22':'#ffb80022');let z=point(...v.center_map_xy_estimate_m);ctx.fillStyle=col;ctx.font='bold 27px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(k,...z)}
function site(q){let reg=s.annotations.registration;return [m.origin[0]+(reg.left_col+q[0]*20)*m.resolution,m.origin[1]+(m.height-reg.top_row-q[1]*20)*m.resolution]}
for(let [k,v]of Object.entries(s.annotations.recognition_boards||{})){region(v.line_map_xy_estimate_m,'#8c48bd');let p=point(...v.line_map_xy_estimate_m[0]);ctx.font='16px Arial';ctx.fillStyle='#8c48bd';ctx.textAlign='left';ctx.fillText(k,p[0]+9,p[1]+22)}
if(s.pose&&s.pose.available){for(let p of s.scan_points||[]){let z=point(...p);ctx.fillStyle='#ee545488';ctx.fillRect(z[0]-1,z[1]-1,2,2)}let p=s.pose,z=point(p.x,p.y),theta=-(p.yaw-a);let l=s.laser_pose;if(l&&l.fresh&&p.fresh){let q=point(l.x,l.y);ctx.beginPath();ctx.moveTo(...z);ctx.lineTo(...q);ctx.strokeStyle='#e89320';ctx.lineWidth=2;ctx.stroke()}ctx.save();ctx.translate(...z);ctx.rotate(theta);ctx.beginPath();ctx.moveTo(18,0);ctx.lineTo(-12,-9);ctx.lineTo(-7,0);ctx.lineTo(-12,9);ctx.closePath();ctx.fillStyle=p.fresh?'#1677df':'#8795a5';ctx.fill();ctx.beginPath();ctx.arc(0,0,3,0,2*Math.PI);ctx.fillStyle='white';ctx.fill();ctx.restore();if(l&&l.fresh&&p.fresh){let q=point(l.x,l.y);ctx.beginPath();ctx.arc(...q,5,0,2*Math.PI);ctx.fillStyle='#ed9117';ctx.fill();ctx.strokeStyle='white';ctx.lineWidth=1.5;ctx.stroke()}}
document.getElementById('status').textContent=s.status;let p=s.pose;document.getElementById('pose').textContent=p&&p.available?`后轴参考点\nX：${p.x.toFixed(2)} m　Y：${p.y.toFixed(2)} m\n车头角度：${(p.yaw*180/Math.PI).toFixed(1)}°\n位置标准差：${s.uncertainty?Math.max(...s.uncertainty.xy_std_m).toFixed(2)+' m':'等待'}\n航向标准差：${s.uncertainty?s.uncertainty.yaw_std_deg.toFixed(1)+'°':'等待'}`:'小车放回场地并初始化定位后显示';document.getElementById('pose').style.whiteSpace='pre-line'}
async function tick(){try{let r=await fetch('/api/state');if(!r.ok)throw Error();latest=await r.json();draw(latest)}catch(e){document.getElementById('status').textContent='显示服务已断开'}setTimeout(tick,250)}tick();
</script></html>'''


class View(object):
    def __init__(self, raw_map, structured_map, annotations, offline=False):
        self.lock = threading.RLock()
        self.maps = {'raw': load_map(raw_map), 'structured': load_map(structured_map)}
        with open(annotations) as handle:
            self.annotations = json.load(handle)
        self.offline = offline
        self.pose = None
        self.uncertainty = None
        self.scan_points = []
        self.laser_pose = None
        self.scan_wall = None
        self.odom_wall = None
        self.scan_ros_age = None
        self.initialized = False

    def snapshot(self):
        with self.lock:
            status = u'等待小车放回场地并初始化定位'
            p = dict(self.pose) if self.pose else None
            laser = dict(self.laser_pose) if self.laser_pose else None
            if laser:
                laser['fresh'] = (time.time()-laser['wall_time'] <= 1.0
                                  and self.scan_ros_age is not None and abs(self.scan_ros_age) <= 1.0)
            if self.offline:
                status = u'场地图预览 · 实时定位尚未启动'
            elif p and p['available']:
                p['fresh'] = (abs(p['ros_age']) <= 1.0 and time.time()-p['wall_time'] <= 1.0
                              and self.odom_wall is not None and time.time()-self.odom_wall <= 1.0)
                scan_fresh = (self.scan_wall is not None and time.time()-self.scan_wall <= 1.0
                              and self.scan_ros_age is not None and abs(self.scan_ros_age) <= 1.0)
                status = u'位置估计更新中 · 请核对雷达与墙线' if p['fresh'] and scan_fresh else u'定位或传感器数据已过期'
                if not self.initialized:
                    status = u'等待指定小车初始位置和朝向'
                elif not self.uncertainty:
                    status = u'等待 AMCL 定位结果'
                elif max(self.uncertainty['xy_std_m']) > .25 or self.uncertainty['yaw_std_deg'] > 15:
                    status = u'定位不确定性较大 · 需要重新核对位置'
            return dict(maps=self.maps, annotations=self.annotations, pose=p,
                        uncertainty=self.uncertainty, scan_points=self.scan_points, laser_pose=laser,
                        status=status, offline=self.offline)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-map', required=True)
    parser.add_argument('--structured-map', required=True)
    parser.add_argument('--annotations', required=True)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--resume-initialized', action='store_true',
                        help='Display-only restart within the same initialized AMCL session; does not initialize AMCL')
    args, unused = parser.parse_known_args()
    view = View(args.raw_map, args.structured_map, args.annotations, args.offline)
    view.initialized = args.resume_initialized and not args.offline
    if not args.offline:
        import rospy
        import tf2_ros
        from geometry_msgs.msg import PoseWithCovarianceStamped
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        rospy.init_node('medical_site_localization_view')
        buffer = tf2_ros.Buffer(rospy.Duration(10))
        listener = tf2_ros.TransformListener(buffer)

        def on_amcl(msg):
            cov = msg.pose.covariance
            values = [cov[0], cov[7], cov[35]]
            if msg.header.frame_id != 'map' or any(not math.isfinite(x) if hasattr(math, 'isfinite') else math.isnan(x) or math.isinf(x) for x in values) or min(values) < 0:
                return
            with view.lock:
                view.uncertainty = {'xy_std_m': [math.sqrt(cov[0]), math.sqrt(cov[7])],
                                    'yaw_std_deg': math.degrees(math.sqrt(cov[35]))}

        def on_initialpose(msg):
            if msg.header.frame_id == 'map':
                with view.lock:
                    view.initialized = True
                    view.uncertainty = None

        def on_odom(msg):
            with view.lock:
                age = (rospy.Time.now()-msg.header.stamp).to_sec()
                if abs(age) <= 1.0:
                    view.odom_wall = time.time()

        def on_scan(msg):
            try:
                trans = buffer.lookup_transform('map', msg.header.frame_id, msg.header.stamp, rospy.Duration(.05))
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                return
            t = trans.transform.translation; heading = yaw(trans.transform.rotation)
            if any(math.isnan(x) or math.isinf(x) for x in [t.x, t.y, heading]):
                return
            points = []
            for i, r in enumerate(msg.ranges):
                if math.isnan(r) or math.isinf(r) or r < msg.range_min or r > min(msg.range_max, 6):
                    continue
                angle = heading+msg.angle_min+i*msg.angle_increment
                points.append([t.x+r*math.cos(angle), t.y+r*math.sin(angle)])
            with view.lock:
                view.scan_points = points
                view.scan_wall = time.time()
                view.laser_pose = dict(x=t.x, y=t.y, frame=msg.header.frame_id,
                                       wall_time=view.scan_wall, stamp=msg.header.stamp.to_sec())
                view.scan_ros_age = (rospy.Time.now()-msg.header.stamp).to_sec()

        def update_pose(event):
            try:
                trans = buffer.lookup_transform('map', 'base_footprint', rospy.Time(0))
                t = trans.transform.translation
                angle = yaw(trans.transform.rotation)
                if any(math.isnan(x) or math.isinf(x) for x in [t.x, t.y, angle]):
                    raise ValueError('Nonfinite TF')
                with view.lock:
                    view.pose = dict(available=True, fresh=True, x=t.x, y=t.y, yaw=angle,
                                     ros_age=(rospy.Time.now()-trans.header.stamp).to_sec(), wall_time=time.time())
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException, ValueError):
                with view.lock:
                    view.pose = None

        rospy.Subscriber('/amcl_pose', PoseWithCovarianceStamped, on_amcl, queue_size=1)
        rospy.Subscriber('/initialpose', PoseWithCovarianceStamped, on_initialpose, queue_size=1)
        rospy.Subscriber('/odom', Odometry, on_odom, queue_size=1)
        rospy.Subscriber('/medical_slam_scan', LaserScan, on_scan, queue_size=1)
        timer = rospy.Timer(rospy.Duration(.2), update_pose)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?')[0] == '/api/state':
                body = json.dumps(view.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                ctype = 'application/json; charset=utf-8'
            elif self.path.split('?')[0] == '/':
                body = PAGE.encode('utf-8'); ctype = 'text/html; charset=utf-8'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *unused):
            pass

    class Server(HTTPServer):
        allow_reuse_address = True
    server = Server(('0.0.0.0', args.port), Handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.daemon = True; worker.start()
    print('SITE_LOCALIZATION_VIEW port=%d offline=%s' % (args.port, args.offline))
    try:
        if args.offline:
            while True:
                time.sleep(.5)
        else:
            rospy.spin()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
