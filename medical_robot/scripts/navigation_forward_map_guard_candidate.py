#!/usr/bin/env python2
"""Forward-only candidate: whole-body static-map check and directional laser.

No ROS, serial, output publisher or authorization creation. Rear laser is not
required. This explicitly cannot detect new obstacles in the rear blind area.
Use field acceptance and supervision separately; a static map is not a live
measurement. Original map, ranges and timestamps are never modified.
"""
from __future__ import division
import math
from navigation_scan_guard_candidate_v2 import geometry, finite
from route_geometry import body_collision


def directional_scan(message, v, w, stop_distance):
    g = geometry(message, v, w, stop_distance)
    # Forward hemisphere plus the turn side. Rearward blind readings are
    # retained in the source, but cannot by themselves refuse forward travel.
    left, right = math.radians(90), -math.radians(90)
    if w > 0: left = math.radians(120)
    if w < 0: right = -math.radians(120)
    cells = {}; obstacles = []; excluded_rear = 0; missing_side = []
    step = max(abs(message.angle_increment), math.radians(.5))
    for i, distance in enumerate(message.ranges):
        a, c, s, intervals = g['beams'][i]
        if not right <= a <= left:
            excluded_rear += 1
            continue
        valid = finite(distance) and message.range_min <= distance <= message.range_max
        if not valid and distance != float('inf'):
            raise ValueError('INVALID_DIRECTIONAL_SCAN_BEAM')
        if abs(a) <= math.radians(45)+1e-6:
            key = int(math.floor(a/step+.5))
            cells[key] = cells.get(key, False) or valid
        if not valid:
            if abs(a) > math.radians(45):
                missing_side.append(math.degrees(a))
            continue
        x, y = .135+distance*c, distance*s
        own = -.100 < x < .245 and abs(y) < .11
        if not own and any(lo-1e-9 <= distance <= hi+1e-9 for lo,hi in intervals):
            obstacles.append(dict(index=i, x=x, y=y, range_m=distance,
                                  angle_deg=math.degrees(a)))
    if not cells or min(cells)*step > -math.radians(45)+step or max(cells)*step < math.radians(45)-step:
        raise ValueError('FORWARD_SCAN_FOV_INCOMPLETE')
    values = [cells.get(k, False) for k in range(min(cells),max(cells)+1)]
    run = max_run = 0
    for valid in values:
        run = 0 if valid else run+1; max_run = max(max_run, run)
    ratio = sum(values)/len(values); gap = math.degrees(max_run*step)
    error = ('DIRECTIONAL_SWEPT_OBSTACLE' if obstacles else
             'FORWARD_COVERAGE_BELOW_90_PERCENT' if ratio < .90 else
             'FORWARD_UNKNOWN_GAP_TOO_WIDE' if gap > 1.01 else None)
    return dict(passed=error is None, error=error, obstacles=obstacles,
                forward_cell_coverage=ratio, max_forward_unknown_gap_deg=gap,
                directional_fov_deg=[math.degrees(right),math.degrees(left)],
                rear_realtime_required=False, excluded_rear_beams=excluded_rear,
                side_unknown_angles_deg=missing_side,
                side_unknown_is_live_free=False, rear_unknown_is_live_free=False,
                ranges_modified=False, lookahead_rear_axle_m=g['horizon'])


def map_and_localization_guard(grid, pose, xy_std, yaw_std, pose_age,
                               v, w, stop_distance):
    if not all(finite(pose[k]) for k in ('x','y','yaw')):
        raise ValueError('INVALID_MAP_POSE')
    if (not all(finite(x) and x >= 0 for x in xy_std) or len(xy_std) != 2 or
            not finite(yaw_std) or yaw_std < 0 or not finite(pose_age)):
        raise ValueError('INVALID_POSE_UNCERTAINTY')
    if not -.02 <= pose_age <= 1.:
        raise ValueError('LOCALIZATION_STALE')
    # Keep the existing field uncertainty limits. No offline record can
    # become a current driving pose merely by resetting its age to zero.
    if max(xy_std) > .10 or yaw_std > math.radians(8):
        raise ValueError('LOCALIZATION_UNCERTAINTY_TOO_HIGH')
    if not all(finite(x) for x in (v,w,stop_distance)) or v <= 0 or stop_distance < 0:
        raise ValueError('FORWARD_ONLY_COMMAND_REQUIRED')
    horizon = max(.605, stop_distance+v*.20+.15); k = w/v
    if horizon > 2 or abs(k) > 6:
        raise ValueError('SWEEP_OUTSIDE_SUPPORTED_BOUNDS')
    n = int(math.ceil(horizon/.01)); c0,s0 = math.cos(pose['yaw']),math.sin(pose['yaw'])
    failures = []
    # A confidence reserve for the whole body, with angular corner motion.
    # This is a bounded screening policy, not a probabilistic guarantee.
    corner = math.hypot(.245,.11)
    padding = max(.10, .05+2*max(xy_std)+corner*abs(math.sin(2*yaw_std)))
    for j in range(n+1):
        d = j*horizon/n; h = d*k
        x = d if abs(k)<1e-10 else math.sin(h)/k
        y = 0. if abs(k)<1e-10 else (1-math.cos(h))/k
        p = dict(x=pose['x']+c0*x-s0*y, y=pose['y']+s0*x+c0*y,
                 yaw=pose['yaw']+h)
        why = body_collision(grid,p,padding)
        if why:
            failures.append(dict(sample=j,reason=why,x=p['x'],y=p['y']))
    return dict(passed=not failures, error='MAP_FULL_BODY_NOT_CLEAR' if failures else None,
                map_failed_samples=len(failures), first_failures=failures[:10],
                full_body_checked=True, confidence_padding_m=padding,
                map_unknown_is_blocked=True, lookahead_rear_axle_m=horizon,
                field_acceptance_created=False)


def evaluate(message, grid, pose, xy_std, yaw_std, pose_age,
             scan_age, v, w, stop_distance):
    if not finite(scan_age) or not -.02 <= scan_age <= .30:
        raise ValueError('SCAN_STALE')
    mapped = map_and_localization_guard(grid,pose,xy_std,yaw_std,pose_age,v,w,stop_distance)
    scanned = directional_scan(message,v,w,stop_distance)
    return dict(passed=mapped['passed'] and scanned['passed'],
                map=mapped, scan=scanned, motion_output=False,
                mode='FORWARD_STATIC_MAP_WITH_DIRECTIONAL_LIVE_SCAN_CANDIDATE',
                rear_dynamic_obstacle_detection=False,
                supervision_required=True, field_accepted=False)
