#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Pure scan diagnostics. Keeps v4 thresholds; never imports ROS or serial."""
from __future__ import division
import math


def finite(v):
    return not math.isnan(v) and not math.isinf(v)


def scan_report(message):
    errors = []
    result = dict(passed=False, errors=errors, front_clearance_m=None,
                  unknown_front_angles_deg=[], finite_self_returns=[], points=[],
                  max_unknown_gap_deg=None, central_valid=0, central_total=0,
                  required_front_clearance_m=.605, half_corridor_width_m=.21)
    if message.header.frame_id != 'base_laser_link':
        errors.append('SCAN_FRAME_CHANGED')
    if (len(message.ranges) < 100 or
            not all(finite(v) for v in (message.angle_min, message.angle_increment,
                                       message.range_min, message.range_max)) or
            message.angle_increment == 0 or
            not 0 <= message.range_min < message.range_max):
        errors.append('SCAN_GEOMETRY_INVALID')
        return result
    tolerance = min(abs(message.angle_increment)*1e-4, 1e-6)
    xs, rows = [], []
    for index, distance in enumerate(message.ranges):
        angle = message.angle_min+index*message.angle_increment
        a = math.atan2(math.sin(angle), math.cos(angle))
        front = abs(a) <= math.radians(20)+tolerance
        valid = finite(distance) and message.range_min <= distance <= message.range_max
        if not valid and distance != float('inf') and 'INVALID_SCAN_BEAM' not in errors:
            errors.append('INVALID_SCAN_BEAM')
        if front:
            rows.append((a, valid))
        if not valid:
            continue
        x, y = .135+distance*math.cos(angle), distance*math.sin(angle)
        own = -.100 < x < .245 and abs(y) < .11
        if own:
            result['finite_self_returns'].append(dict(index=index,x=x,y=y,range=distance))
        elif x > 0 and abs(y) <= .21:
            xs.append(x)
        if abs(a) <= math.radians(60) and distance <= 3:
            result['points'].append([x,y,own])
    rows.sort()
    valid_count = sum(int(v) for a,v in rows)
    result.update(central_total=len(rows), central_valid=valid_count,
                  unknown_front_angles_deg=[math.degrees(a) for a,v in rows if not v],
                  finite_corridor_returns=len(xs), angle_rounding_tolerance_rad=tolerance,
                  self_footprint_m=[[-.100,-.11],[.245,.11]])
    if valid_count < 3 or len(rows) < 3 or len(xs) < 3:
        errors.append('FRONT_SCAN_COVERAGE_INSUFFICIENT')
    if rows and (not rows[0][1] or not rows[-1][1]):
        errors.append('FRONT_SCAN_EDGE_UNKNOWN')
    if rows and valid_count/len(rows) < .90:
        errors.append('FRONT_SCAN_COVERAGE_BELOW_90_PERCENT')
    run = maximum = 0
    for a,v in rows:
        run = 0 if v else run+1
        maximum = max(maximum,run)
    gap = maximum*abs(message.angle_increment)
    result['max_unknown_gap_deg'] = math.degrees(gap)
    if gap > math.radians(1.01):
        errors.append('FRONT_UNKNOWN_GAP_TOO_WIDE')
    if xs:
        result.update(min_x_from_rear_axle_m=min(xs), front_clearance_m=min(xs)-.245)
        if min(xs) < .85:
            errors.append('FRONT_CORRIDOR_NOT_CLEAR')
    result['passed'] = not errors
    return result


def scan_clearance(message):
    report = scan_report(message)
    if not report['passed']:
        raise ValueError(report['errors'][0])
    return report
