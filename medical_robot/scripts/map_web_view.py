#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function
import json
import threading
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import rospy
from nav_msgs.msg import OccupancyGrid

state = {'map': None}
display_mode = 'live'
source_name = ''
lock = threading.Lock()

PAGE = '''<!doctype html><meta charset="utf-8"><title>医运机器人实时建图</title>
<style>body{font-family:Arial;margin:16px;background:#222;color:#eee}#s{color:#8f8}canvas{background:#aaa;max-width:92vw;max-height:82vh;border:1px solid #777;image-rendering:pixelated}</style>
<h2 id="heading">地图显示</h2><div id="s">等待地图...</div><canvas id="c"></canvas>
<script>
const c=document.getElementById('c'),x=c.getContext('2d');
function draw(m){c.width=m.width;c.height=m.height;let im=x.createImageData(m.width,m.height),a=im.data;
for(let y=0;y<m.height;y++)for(let i=0;i<m.width;i++){let v=m.data[y*m.width+i],q=((m.height-1-y)*m.width+i)*4,g=v<0?160:(v>=65?20:245);a[q]=a[q+1]=a[q+2]=g;a[q+3]=255}x.putImageData(im,0,0);
const preview=m.display_mode==='saved_preview';
document.getElementById('heading').textContent=preview?'已保存地图预览（未进行实时建图）':'实时建图';
const age=Math.max(0,(Date.now()-m.received_ms)/1000),fresh=preview?'':(age>5?' | 地图超过5秒未更新':'');
document.getElementById('s').textContent=`${m.source_name||''} | ${m.width}×${m.height} 栅格 | 分辨率 ${m.resolution.toFixed(2)} m | 当前栅格已知比例 ${m.known_pct}%（非建图完成度） | 黑色：障碍 白色：空地 灰色：未知 | 地图接收于 ${new Date(m.received_ms).toLocaleTimeString()}${fresh}`}
async function tick(){try{let r=await fetch('/api/map?'+Date.now());if(r.ok)draw(await r.json())}catch(e){}setTimeout(tick,1000)}tick();
</script>'''

def cb(msg):
    known = sum(1 for v in msg.data if v >= 0)
    occupied = sum(1 for v in msg.data if v >= 65)
    n = float(len(msg.data) or 1)
    import time
    payload = {'display_mode': display_mode, 'source_name': source_name,
               'received_ms': time.time()*1000, 'width': msg.info.width, 'height': msg.info.height,
               'resolution': msg.info.resolution, 'origin': [msg.info.origin.position.x, msg.info.origin.position.y],
               'known_pct': round(100.0 * known / n, 1), 'occupied_pct': round(100.0 * occupied / n, 1),
               'data': list(msg.data)}
    with lock: state['map'] = payload

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/map'):
            with lock: payload = state['map']
            if payload is None: self.send_response(404); self.end_headers(); return
            body = json.dumps(payload)
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            body = PAGE
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, fmt, *args): pass

rospy.init_node('medical_map_web_view', anonymous=True)
display_mode = rospy.get_param('~display_mode', 'live')
source_name = rospy.get_param('~source_name', '')
if display_mode not in ('live', 'saved_preview'):
    raise ValueError('display_mode must be live or saved_preview')
rospy.Subscriber('/map', OccupancyGrid, cb, queue_size=1)
server = HTTPServer(('0.0.0.0', 8080), Handler)
worker=threading.Thread(target=server.serve_forever)
worker.daemon=True
worker.start()
print('MAP_WEB_VIEW http://0.0.0.0:8080')
rospy.spin()
server.shutdown()
