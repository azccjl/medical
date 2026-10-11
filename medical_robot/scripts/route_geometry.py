#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Pure forward route fillets and conservative full-footprint grid screening."""
from __future__ import division
import math


def finite(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and not math.isnan(x) and not math.isinf(x)


def fillet_route(waypoints,radius=.55,step=.015):
    if not finite(radius) or not .45<=radius<=2:
        raise ValueError('TURN_RADIUS_OUT_OF_RANGE')
    if not 2<=len(waypoints)<=30:
        raise ValueError('NEED_2_TO_30_WAYPOINTS')
    points=[]
    for p in waypoints:
        if not isinstance(p,list) or len(p)!=2 or not all(finite(v) and abs(v)<100 for v in p):
            raise ValueError('INVALID_WAYPOINT')
        points.append(tuple(p))
    segments=[]
    for a,b in zip(points[:-1],points[1:]):
        d=math.hypot(b[0]-a[0],b[1]-a[1])
        if d<.08:raise ValueError('WAYPOINTS_TOO_CLOSE')
        segments.append((d,((b[0]-a[0])/d,(b[1]-a[1])/d)))
    if sum(s[0] for s in segments)>80:raise ValueError('ROUTE_TOO_LONG')
    corners={}
    for i in range(1,len(points)-1):
        u,v=segments[i-1][1],segments[i][1]
        turn=math.atan2(u[0]*v[1]-u[1]*v[0],u[0]*v[0]+u[1]*v[1])
        if abs(turn)<1e-6:continue
        if abs(turn)>math.radians(160):raise ValueError('CORNER_REQUIRES_REVERSAL_%s'%i)
        d=radius*math.tan(abs(turn)/2)
        p=points[i];entry=(p[0]-d*u[0],p[1]-d*u[1]);exitp=(p[0]+d*v[0],p[1]+d*v[1])
        sign=1 if turn>0 else -1
        center=(entry[0]-sign*radius*u[1],entry[1]+sign*radius*u[0])
        corners[i]=(entry,exitp,center,turn,d)
    for i,(length,u) in enumerate(segments):
        trim_start=corners[i][4] if i in corners else 0
        trim_end=corners[i+1][4] if i+1 in corners else 0
        if trim_start+trim_end>length-.02:raise ValueError('INSUFFICIENT_ROOM_FOR_TURN_SEGMENT_%s'%i)
    path=[]
    def append(x,y,h,k):
        if path and math.hypot(path[-1]['x']-x,path[-1]['y']-y)<1e-9:
            path[-1].update(yaw=h,curvature=k);return
        path.append(dict(x=x,y=y,yaw=h,curvature=k))
    def line(a,b):
        length=math.hypot(b[0]-a[0],b[1]-a[1]);h=math.atan2(b[1]-a[1],b[0]-a[0])
        if length<1e-9:return
        n=max(1,int(math.ceil(length/step)))
        for j in range(n+1):
            t=j/n;append(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]),h,0)
    current=points[0]
    for i in range(1,len(points)):
        if i not in corners:line(current,points[i]);current=points[i];continue
        entry,exitp,center,turn,d=corners[i];line(current,entry)
        a=math.atan2(entry[1]-center[1],entry[0]-center[0]);sign=1 if turn>0 else -1
        n=max(1,int(math.ceil(radius*abs(turn)/step)))
        for j in range(n+1):
            t=j/n;angle=a+turn*t
            append(center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle),angle+sign*math.pi/2,sign/radius)
        current=exitp
    if len(path)<2:raise ValueError('EMPTY_ROUTE')
    length=sum(math.hypot(b['x']-a['x'],b['y']-a['y']) for a,b in zip(path[:-1],path[1:]))
    return dict(path=path,waypoints=[list(p) for p in points],length_m=length,min_turn_radius_m=radius,
                sample_step_m=step,algorithm='forward circular fillets; user-selected corridor, no automatic obstacle detour',
                estimated_drive_seconds_at_010=length/.10,turn_radius_validated=False)


def body_collision(grid,pose,padding=.10):
    r=grid['resolution'];ox,oy,angle=grid['origin'];ca,sa=math.cos(angle),math.sin(angle)
    # Reserve for pixel half-diagonal and between-sample body motion.
    extra=padding+r/math.sqrt(2)+.025
    xmin,xmax,ymax=-.100-extra,.245+extra,.11+extra
    h=pose['yaw'];c,s=math.cos(h),math.sin(h)
    corners=[]
    for x,y in [(xmin,-ymax),(xmax,-ymax),(xmax,ymax),(xmin,ymax)]:
        wx=pose['x']+c*x-s*y-ox;wy=pose['y']+s*x+c*y-oy
        corners.append(((ca*wx+sa*wy)/r,(-sa*wx+ca*wy)/r))
    xlo=int(math.floor(min(v[0] for v in corners)));xhi=int(math.floor(max(v[0] for v in corners)))
    ylo=int(math.floor(min(v[1] for v in corners)));yhi=int(math.floor(max(v[1] for v in corners)))
    if xlo<0 or ylo<0 or xhi>=grid['width'] or yhi>=grid['height']:
        return 'OUTSIDE_MAP'
    for row in range(ylo,yhi+1):
        for col in range(xlo,xhi+1):
            value=grid['data'][row*grid['width']+col]
            if value==0:continue
            wx=ox+ca*(col+.5)*r-sa*(row+.5)*r-pose['x']
            wy=oy+sa*(col+.5)*r+ca*(row+.5)*r-pose['y']
            bx=c*wx+s*wy;by=-s*wx+c*wy
            if xmin<=bx<=xmax and abs(by)<=ymax:
                return 'UNKNOWN_CELL' if value<0 else 'OCCUPIED_CELL'
    return None


def screen_route(grid,route,padding=.10):
    failures=[];count=0
    for i,p in enumerate(route['path']):
        reason=body_collision(grid,p,padding)
        if reason:
            count+=1
            if len(failures)<30:failures.append(dict(index=i,x=p['x'],y=p['y'],reason=reason))
    return dict(passed=count==0,failed_samples=count,first_failures=failures,padding_m=padding,
                footprint=[[-.100,-.11],[.245,.11]],unknown_is_blocked=True,
                cell_diagonal_and_sample_motion_reserved=True)
