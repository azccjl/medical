#!/usr/bin/env python2
"""Conservative laser check for a curved stopping corridor. No interpolation."""
from __future__ import division
import math
from route_geometry import finite


def swept_scan_guard(m,v,w,stop_distance):
    if m.header.frame_id!='base_laser_link' or len(m.ranges)<100 or not finite(m.angle_increment) or m.angle_increment==0:
        raise ValueError('SCAN_GEOMETRY_INVALID')
    if not all(finite(x) for x in (m.angle_min,m.range_min,m.range_max,v,w,stop_distance)) or m.range_min<0 or m.range_max<=m.range_min:
        raise ValueError('SCAN_GEOMETRY_INVALID')
    horizon=max(.605,stop_distance+abs(v)*.20+.15)
    curvature=w/v if v else 0
    poses=[]
    n=int(math.ceil(horizon/.015))
    for j in range(n+1):
        d=j*horizon/n;h=d*curvature
        x=d if abs(curvature)<1e-8 else math.sin(h)/curvature
        y=0 if abs(curvature)<1e-8 else (1-math.cos(h))/curvature
        poses.append((x,y,math.cos(h),math.sin(h)))
    def own(x,y):return -.100<x<.245 and abs(y)<.11
    def intersects(x,y):
        if own(x,y):return False
        for px,py,c,s in poses:
            dx,dy=x-px,y-py;bx,by=c*dx+s*dy,-s*dx+c*dy
            if -.150<=bx<=.295 and abs(by)<=.16:return True
        return False
    relevant=0
    for i,r in enumerate(m.ranges):
        angle=m.angle_min+i*m.angle_increment;c,s=math.cos(angle),math.sin(angle)
        valid=finite(r) and m.range_min<=r<=m.range_max
        if not valid and r!=float('inf'):raise ValueError('INVALID_SCAN_BEAM')
        if valid:
            if intersects(.135+r*c,r*s):raise ValueError('SWEPT_CORRIDOR_OBSTACLE')
        else:
            # Check unknown rays against the future whole body, not only its centre.
            # Unknown intersecting rays block motion; no fabricated free readings.
            for j in range(10,151):
                d=j*.01
                if intersects(.135+d*c,d*s):raise ValueError('SWEPT_CORRIDOR_UNKNOWN')
        if abs(math.atan2(s,c))<=math.radians(70) and valid:relevant+=1
    if relevant<20:raise ValueError('SWEPT_CORRIDOR_COVERAGE_INSUFFICIENT')
    return dict(passed=True,lookahead_rear_axle_m=horizon,finite_front_returns=relevant)
