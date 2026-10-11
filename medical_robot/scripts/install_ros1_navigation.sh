#!/bin/bash
set -e
source /opt/ros/melodic/setup.bash
sudo apt-get update
sudo apt-get install -y ros-melodic-slam-toolbox ros-melodic-amcl ros-melodic-map-server \
  ros-melodic-move-base ros-melodic-teb-local-planner
echo 'ROS1_NAVIGATION_PACKAGES_INSTALLED'
rospack find slam_toolbox
rospack find amcl
rospack find move_base
rospack find teb_local_planner
