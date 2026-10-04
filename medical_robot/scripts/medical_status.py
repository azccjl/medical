#!/usr/bin/env python2
from __future__ import print_function

import rospy


EXPECTED_TOPICS = [
    '/cmd_vel',
    '/scan',
    '/odom',
    '/map',
    '/camera/rgb/image_raw',
]


def main():
    rospy.init_node('medical_status', anonymous=False)
    topics = set(name for name, _ in rospy.get_published_topics())
    rospy.loginfo('ROS master: %s', rospy.get_master().getUri())
    for name in EXPECTED_TOPICS:
        state = 'OK' if name in topics else 'MISSING'
        rospy.loginfo('[%s] %s', state, name)
    rospy.loginfo('Published topics: %d', len(topics))


if __name__ == '__main__':
    main()
