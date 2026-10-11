#!/usr/bin/env python2
"""Front/side scan for navigation costmaps; original /scan remains untouched.

Masked beams become NaN, so they neither mark obstacles nor clear blind space.
Localization and mapping retain their existing input topics. No base access.
"""
from __future__ import print_function
import math


def filtered_ranges(message):
    if (message.header.frame_id != 'base_laser_link' or len(message.ranges) < 100 or
            not all(not math.isnan(x) and not math.isinf(x) for x in
                (message.angle_min,message.angle_increment,message.range_min,message.range_max)) or
            message.angle_increment == 0 or message.range_min < 0 or
            message.range_max <= message.range_min):
        raise ValueError('INVALID_SCAN_GEOMETRY')
    result = list(message.ranges); rear = own = 0
    for i,r in enumerate(message.ranges):
        a = message.angle_min+i*message.angle_increment
        c,s = math.cos(a),math.sin(a)
        a = math.atan2(s,c)
        if abs(a)>math.radians(120)+1e-6:
            result[i]=float('nan'); rear+=1
        elif not math.isnan(r) and not math.isinf(r) and message.range_min<=r<=message.range_max:
            x,y=.135+r*c,r*s
            if -.100<x<.245 and abs(y)<.11:
                result[i]=float('nan'); own+=1
    return result,dict(rear_masked=rear,finite_self_masked=own,
                       blind_marked_free=False,source_modified=False)


def main():
    import copy,json,rospy
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String
    rospy.init_node('medical_navigation_forward_scan')
    pub=rospy.Publisher('/medical_navigation_forward_scan',LaserScan,queue_size=1)
    status=rospy.Publisher('/medical_navigation_forward_scan/status',String,queue_size=1,latch=True)
    def callback(message):
        try:
            values,evidence=filtered_ranges(message)
            out=copy.deepcopy(message);out.ranges=values
            # Header frame/timestamps, time_increment, scan_time, geometry,
            # intensities and finite external front/side returns are retained.
            # rospy may assign the output topic its own sequence counter.
            pub.publish(out)
            evidence.update(source_seq=message.header.seq,source_stamp=message.header.stamp.to_sec(),
                            motion_output=False,usable_for='navigation costmap only',
                            localization_input_changed=False)
            status.publish(String(json.dumps(evidence)))
        except ValueError as exc:
            rospy.logwarn_throttle(2,'Forward scan refused: '+str(exc))
    rospy.Subscriber('/scan',LaserScan,callback,queue_size=1,tcp_nodelay=True)
    rospy.spin()


if __name__=='__main__':main()
