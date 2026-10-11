#!/usr/bin/env python2
"""Analytic swept-body laser guard candidate. No ROS, serial or motion output.

Not selected by the live command gate until footprint/occlusion is resolved.
Unknown intersecting rays still refuse motion. Finite self returns are excluded
only inside the existing measured footprint. Source ranges are never modified.
"""
from __future__ import division
import math
import threading

_cache = {}
_cache_lock = threading.RLock()
BODY = (-.100, .245, -.11, .11)
LASER_X = .135


def finite(x):
    return not math.isnan(x) and not math.isinf(x)


def ray_box(ox, oy, dx, dy, bounds):
    """Exact ray/rectangle slab intersection; returns radial interval."""
    lo, hi = 0., float('inf')
    for o, d, a, b in ((ox, dx, bounds[0], bounds[1]),
                        (oy, dy, bounds[2], bounds[3])):
        if abs(d) < 1e-12:
            if not a <= o <= b:
                return None
        else:
            u, v = (a-o)/d, (b-o)/d
            lo, hi = max(lo, min(u, v)), min(hi, max(u, v))
            if hi < lo:
                return None
    return lo, hi


def geometry(message, v, w, stop_distance):
    if (message.header.frame_id != 'base_laser_link' or len(message.ranges) < 100 or
            not all(finite(x) for x in (message.angle_min, message.angle_increment,
                    message.range_min, message.range_max, v, w, stop_distance)) or
            message.angle_increment == 0 or message.range_min < 0 or
            message.range_max <= message.range_min or v <= 0 or stop_distance < 0):
        raise ValueError('SCAN_OR_FORWARD_GEOMETRY_INVALID')
    horizon = max(.605, stop_distance + v*.20 + .15)
    curvature = w/v
    if horizon > 2 or abs(curvature) > 6:
        raise ValueError('SWEEP_OUTSIDE_SUPPORTED_BOUNDS')
    key = (len(message.ranges), message.angle_min, message.angle_increment,
           message.range_min, horizon, curvature)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
        n = int(math.ceil(horizon/.01))
        # Additional bound on translation and corner rotation between samples;
        # does not reduce the existing 5 cm clearance margin.
        corner_radius = math.hypot(.245, .11)
        discretization_margin = horizon/n/2 * (1+abs(curvature)*corner_radius)
        margin = .05 + discretization_margin
        padded = (BODY[0]-margin, BODY[1]+margin,
                  BODY[2]-margin, BODY[3]+margin)
        poses = []
        for j in range(n+1):
            d = j*horizon/n
            h = d*curvature
            x = d if abs(curvature) < 1e-10 else math.sin(h)/curvature
            y = 0. if abs(curvature) < 1e-10 else (1-math.cos(h))/curvature
            poses.append((x, y, math.cos(h), math.sin(h)))
        beams = []
        for i in range(len(message.ranges)):
            a = message.angle_min+i*message.angle_increment
            dx, dy = math.cos(a), math.sin(a)
            own_interval = ray_box(LASER_X, 0, dx, dy, BODY)
            own_exit = own_interval[1] if own_interval else 0.
            intervals = []
            for px, py, c, s in poses:
                ox, oy = LASER_X-px, -py
                it = ray_box(c*ox+s*oy, -s*ox+c*oy,
                             c*dx+s*dy, -s*dx+c*dy, padded)
                if it and it[1] > max(it[0], own_exit, message.range_min)+1e-9:
                    intervals.append((max(it[0], own_exit, message.range_min), it[1]))
            intervals.sort()
            merged = []
            for lo, hi in intervals:
                if merged and lo <= merged[-1][1]+1e-10:
                    merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
                else:
                    merged.append((lo, hi))
            beams.append((math.atan2(dy, dx), dx, dy, merged))
        result = dict(beams=beams, poses=poses, horizon=horizon,
                      clearance_margin_m=.05, discretization_margin_m=discretization_margin)
        if len(_cache) >= 8:
            _cache.clear()
        _cache[key] = result
        return result


def evaluate_scan(message, v, w, stop_distance):
    g = geometry(message, v, w, stop_distance)
    obstacles, unknown, occluded, self_returns, irrelevant_near = [], [], [], [], []
    required = clear = 0
    for i, r in enumerate(message.ranges):
        a, c, s, intervals = g['beams'][i]
        valid = finite(r) and message.range_min <= r <= message.range_max
        if not valid and r != float('inf'):
            raise ValueError('INVALID_SCAN_BEAM')
        x, y = (LASER_X+r*c, r*s) if valid else (None, None)
        own = valid and BODY[0] < x < BODY[1] and BODY[2] < y < BODY[3]
        row = dict(index=i, angle_deg=math.degrees(a), range_m=r if valid else None,
                   x=x, y=y)
        if own:
            self_returns.append(row)
        if not intervals:
            continue
        required += 1
        if valid and not own and any(lo-1e-9 <= r <= hi+1e-9 for lo, hi in intervals):
            obstacles.append(row)
        elif not valid:
            unknown.append(row)
        elif r < intervals[-1][1]:
            # A finite return before an unseen part of the sweep does NOT
            # establish free space behind it (including actual self occlusion).
            occluded.append(row)
        else:
            clear += 1
        if valid and x > 0 and abs(y) <= .35 and x < .85 and not own and not any(lo <= r <= hi for lo, hi in intervals):
            irrelevant_near.append(row)
    error = ('SWEPT_CORRIDOR_OBSTACLE' if obstacles else
             'SWEPT_CORRIDOR_UNKNOWN' if unknown else
             'SWEPT_CORRIDOR_OCCLUDED' if occluded else
             'SWEPT_CORRIDOR_COVERAGE_INSUFFICIENT' if not required else None)
    return dict(passed=error is None, error=error, required_beams=required,
                clear_beams=clear, obstacles=obstacles, unknown=unknown,
                occluded=occluded, finite_self_returns=self_returns,
                old_rectangular_false_blockers=irrelevant_near,
                lookahead_rear_axle_m=g['horizon'], measured_footprint_m=BODY,
                clearance_margin_m=g['clearance_margin_m'],
                discretization_margin_m=g['discretization_margin_m'],
                unknown_filled=False, ranges_modified=False)


def swept_scan_guard(message, v, w, stop_distance):
    result = evaluate_scan(message, v, w, stop_distance)
    if not result['passed']:
        raise ValueError(result['error'])
    return result
