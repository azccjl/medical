#!/usr/bin/env python2
"""Pure acceptance and Ackermann command checks; no ROS or serial imports."""
from __future__ import division
import math
from route_geometry import finite

CHECKS=('map_alignment','distance_scale','low_speed_response','left_right_turns',
        'watchdog_and_stop','localization_in_motion','command_gate_bench')


def acceptance_errors(cert,map_sha=None):
    errors=[]
    if cert.get('schema_version')!=1 or cert.get('status')!='FIELD_ACCEPTED':errors.append('FIELD_ACCEPTANCE_NOT_COMPLETE')
    for key in CHECKS:
        row=cert.get('checks',{}).get(key,{})
        if row.get('passed') is not True or not isinstance(row.get('evidence'),(str,type(u''))) or not row['evidence'].strip():
            errors.append('FIELD_CHECK_REQUIRED_'+key)
    for key,lo,hi in [('measured_min_turn_radius_m',.17,2),('measured_min_reliable_speed_m_s',.01,.10),
                      ('measured_max_stop_distance_m',0,.30),('navigation_speed_limit_m_s',.10,.12),
                      ('command_timeout_s',.05,.20)]:
        v=cert.get(key)
        if not finite(v) or not lo<=v<=hi:errors.append('INVALID_CALIBRATION_'+key)
    if map_sha is not None and cert.get('map_pgm_sha256')!=map_sha:errors.append('MAP_IDENTITY_CHANGED')
    if cert.get('driver_sha256')!='d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1':errors.append('DRIVER_IDENTITY_CHANGED')
    return errors


def command_policy(v,w,cert):
    if not all(finite(x) for x in (v,w)):raise ValueError('NONFINITE_COMMAND')
    if v==0 and w==0:return dict(v=0.,w=0.,steering=0.)
    errors=acceptance_errors(cert)
    if errors:raise ValueError(errors[0])
    if v<=0:raise ValueError('REVERSE_OR_ROTATE_IN_PLACE_FORBIDDEN')
    if v<cert['measured_min_reliable_speed_m_s']:raise ValueError('COMMAND_BELOW_MEASURED_RELIABLE_SPEED')
    if v>cert['navigation_speed_limit_m_s']:raise ValueError('COMMAND_SPEED_TOO_HIGH')
    radius=max(.75,cert['measured_min_turn_radius_m'])
    if abs(w)>v/radius+1e-9:raise ValueError('TURN_RADIUS_TOO_SMALL')
    return dict(v=v,w=w,steering=math.atan(.17*w/v))
