#!/usr/bin/env python3
from pathlib import Path
import json
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1]; md=root/'medical-live-mapping-20261010'
origin=[-3.206440,-0.726359]; res=.05; width,height=100,99
left,top,right,bottom=4.,3.,94.,93.
layout={'1':(.55,1.65),'2':(1.45,2.20),'3':(.55,2.75),'4':(1.45,3.25),'A':(3.15,1.65),'B':(4.05,.85),'C':(4.05,1.85),'识别板一':(4.05,4.00),'识别板二':(.55,.45),'起点':(3.20,4.05)}
def project(u,v):
 col=left+u/4.5*(right-left); row=top+v/4.5*(bottom-top)
 return {'diagram_m':{'from_left':u,'from_top':v},'map_pixel':{'col':round(col,2),'row':round(row,2)},'map_xy_m':{'x':round(origin[0]+col*res,3),'y':round(origin[1]+(height-row)*res,3)},'yaw_rad':None}
points={k:project(*v) for k,v in layout.items()}
out={'status':'DIAGRAM_ESTIMATE_ONLY','map':'medical-live-map-20261010.yaml','field_size_m':[4.5,4.5],'coordinate_note':'Map x is right, map y is up. Diagram v increases from top wall downward.','calibration_required':'Measure each actual stopping center and approach yaw in RViz; do not feed these estimates to AMCL/move_base.','D':{'status':'UNKNOWN','reason':'D is absent from official rules and supplied site photo.'},'points':points}
(md/'site-waypoints-diagram-estimate.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
im=Image.open(md/'medical-live-map-20261010.pgm').convert('RGB').resize((width*8,height*8)); dr=ImageDraw.Draw(im)
for name,p in points.items():
 c=p['map_pixel']['col']*8; r=p['map_pixel']['row']*8; dr.ellipse((c-8,r-8,c+8,r+8),fill=(220,30,30),outline=(255,255,0),width=2); dr.text((c+10,r-10),name,fill=(0,0,255))
im.save(md/'site-waypoints-diagram-estimate.png')
print(json.dumps(out,ensure_ascii=False,indent=2))
