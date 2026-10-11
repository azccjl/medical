#!/usr/bin/env python3
"""Read-only geometry/scan review. Never imports ROS or issues robot commands."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / 'outer-loop-preview.json'
    image_path = args.output_dir / 'outer-loop-preview.png'
    if result_path.exists() or image_path.exists():
        raise RuntimeError('PRESERVE_EXISTING_PREVIEW')
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    state = evidence['view']
    raw = state['maps']['raw']
    annotation = state['annotations']['registration']
    resolution = raw['resolution']
    ox, oy, origin_yaw = raw['origin']
    if abs(origin_yaw) > 1e-8:
        raise RuntimeError('UNSUPPORTED_MAP_ORIGIN_ROTATION')
    width, height = raw['width'], raw['height']
    left = ox + annotation['left_col']*resolution
    top = oy + (height-annotation['top_row'])*resolution
    def map_xy(u, v): return (left+u, top-v)
    # Rounded rectangle preview, counterclockwise in ROS map coordinates.
    # Radius is a candidate only. A physical turn has not validated it.
    uv = []
    def line(a, b):
        for t in np.linspace(0, 1, max(2, int(math.dist(a,b)/.04)+1)):
            uv.append((a[0]*(1-t)+b[0]*t, a[1]*(1-t)+b[1]*t))
    def arc(c, first, last):
        for angle in np.linspace(first, last, 24):
            uv.append((c[0]+.55*math.cos(angle), c[1]+.55*math.sin(angle)))
    start=(2.855,4.1)
    line(start,(3.55,4.1)); arc((3.55,3.55),math.pi/2,0)
    line((4.1,3.55),(4.1,.95)); arc((3.55,.95),0,-math.pi/2)
    line((3.55,.4),(.95,.4)); arc((.95,.95),-math.pi/2,-math.pi)
    line((.4,.95),(.4,3.55)); arc((.95,3.55),math.pi,math.pi/2)
    line((.95,4.1),start)
    positions=np.array([map_xy(*p) for p in uv])
    heads=[]
    for index,p in enumerate(positions):
        delta=positions[(index+1)%len(positions)]-p
        if np.linalg.norm(delta)<1e-6:
            delta=positions[(index+2)%len(positions)]-p
        heads.append(math.atan2(delta[1],delta[0]))
    cells=np.array(raw['data']).reshape(height,width)
    cy,cx=np.where(cells>=65)
    occupied=np.column_stack((ox+(cx+.5)*resolution,oy+(cy+.5)*resolution))
    # Sample the whole measured rectangle, not only the reference point.
    body=np.array([(x,y) for x in np.linspace(-.1,.245,15) for y in np.linspace(-.11,.11,11)])
    required_clearance=.15+2*max(state['uncertainty']['xy_std_m'])
    minima=[];unknown=[]
    for pos,heading in zip(positions,heads):
        c,s=math.cos(heading),math.sin(heading)
        world=body @ np.array([[c,s],[-s,c]])+pos
        dist=np.linalg.norm(world[:,None,:]-occupied[None,:,:],axis=2).min()
        # Occupied cell centres are up to half a diagonal inside cell edges.
        minima.append(max(0.,float(dist)-resolution/math.sqrt(2)))
        col=np.floor((world[:,0]-ox)/resolution).astype(int)
        row=np.floor((world[:,1]-oy)/resolution).astype(int)
        bounds=(col>=0)&(col<width)&(row>=0)&(row<height)
        bad=not bounds.all() or np.any(cells[row[bounds],col[bounds]]<0)
        unknown.append(bool(bad))
    # Endpoint proximity and ray occlusion, using the laser origin saved with scan.
    scan=np.array(state['scan_points'])
    laser=state['laser_pose']; source=np.array([laser['x'],laser['y']])
    distances=np.linalg.norm(scan[:,None,:]-occupied[None,:,:],axis=2).min(axis=1)
    blocked=0
    for end in scan:
        delta=end-source; length=np.linalg.norm(delta)
        if length<=.3:continue
        fractions=np.arange(.2,length-.15,resolution/2)/length
        points=source+fractions[:,None]*delta
        col=np.floor((points[:,0]-ox)/resolution).astype(int)
        row=np.floor((points[:,1]-oy)/resolution).astype(int)
        keep=(col>=0)&(col<width)&(row>=0)&(row<height)
        if np.any(cells[row[keep],col[keep]]>=65):blocked+=1
    report=dict(status='PREVIEW_ONLY_MOTION_DISABLED', evidence=str(args.evidence),
        layout_registration='approximate, not site surveyed',
        min_turn_radius_m=.55, turn_radius_validated=False,
        measured_footprint_m=[[.245,.11],[.245,-.11],[-.1,-.11],[-.1,.11]],
        clearance_requirement_m=required_clearance,
        required_clearance_note='0.15 m clearance plus 2 times maximum axis position std; screening only, not probability guarantee',
        minimum_body_clearance_m=min(minima),
        route_samples_below_clearance=sum(v<required_clearance for v in minima),
        route_samples_in_unknown=sum(unknown),
        scan_endpoint_within_10cm_fraction=float(np.mean(distances<=.1)),
        scan_rays_with_premature_occupied_cells=blocked, scan_endpoint_count=len(scan),
        navigation_ready=False,
        blockers=['Speed response and distance calibration incomplete',
                  'Steering radius has not been measured',
                  'Candidate path clearance and localization require review',
                  'Navigation command gate has not been validated'],
        route=[dict(x=float(p[0]),y=float(p[1]),yaw=float(h)) for p,h in zip(positions,heads)])
    raster=np.flipud(cells)
    gray=np.where(raster<0,205,np.where(raster>=65,25,254)).astype('uint8')
    im=Image.fromarray(gray).convert('RGB').resize((width*8,height*8),Image.Resampling.NEAREST)
    draw=ImageDraw.Draw(im)
    def screen(p):return ((p[0]-ox)/resolution*8,(height-(p[1]-oy)/resolution)*8)
    for p in scan:
        x,y=screen(p); draw.ellipse((x-1,y-1,x+1,y+1),fill='#eb5353')
    for i in range(len(positions)-1):
        color='#c9580d' if minima[i]<required_clearance or unknown[i] else '#248448'
        draw.line((screen(positions[i]),screen(positions[i+1])),fill=color,width=3)
    p=state['pose']; point=np.array([p['x'],p['y']]); heading=p['yaw']
    tip=point+.23*np.array([math.cos(heading),math.sin(heading)])
    draw.line((screen(point),screen(tip)),fill='#1677df',width=6)
    x,y=screen(point);draw.ellipse((x-5,y-5,x+5,y+5),fill='#1677df')
    im.save(image_path)
    result_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='route'},indent=2))


if __name__=='__main__':main()
