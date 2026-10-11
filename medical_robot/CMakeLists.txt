cmake_minimum_required(VERSION 3.0.2)
project(medical_robot)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/medical_status.py
  scripts/map_web_view.py
  scripts/mapping_heading_scale.py
  scripts/site_localization_view.py
  scripts/route_geometry.py
  scripts/navigation_policy.py
  scripts/navigation_scan_guard.py
  scripts/route_workbench.py
  scripts/navigation_command_gate.py
  scripts/navigation_audited_base.py
  scripts/route_action_runner.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY config launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
install(FILES scripts/route_workbench.html
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
install(FILES scripts/heading_fix/medical_stop_window.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}/heading_fix
)
install(PROGRAMS scripts/install_ros1_navigation.sh
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
