# 实时定位准备（2026-10-11）

已完成 `site_localization_view.py` 和 `site_localization_observe.launch`，并部署到 VMware Ubuntu 的 `/home/ncut/medical_ws/src/medical_robot/`。本轮地图文件部署在 `/home/ncut/medical_localization_assets_20261011/`。界面显示原始地图、整理地图、七个窗口方框、两条识别区域线；实车模式读取 `map → base_footprint` TF 显示车头箭头，并将实时雷达回波投影到地图。蓝色箭头的中心明确标为后轴参考点，橙色圆点为雷达中心，二者以实测前向 0.135 m 的细线相连；红点为雷达回波。显示 AMCL 位置与航向标准差，过期的 TF、里程计或扫描会提示异常。协方差较小不代表真实位置正确，仍须对照回波与墙线确认。

程序仅订阅定位与传感器话题，没有 ROS 速度或导航目标发布者。launch 包含 map_server、AMCL、显示节点，不包含底盘、手柄、move_base 或自主运动程序。原始地图与整理图可切换显示；默认 AMCL 使用原始扫描地图。整理图是按规则尺寸配准的候选，需要现场对齐核验后才能替换定位底图。

当前已运行的是离线预览 `http://192.168.12.71:8081/`，不连接任何 ROS master、不订阅小车。页面明确显示“场地图预览 · 实时定位尚未启动”，没有伪造小车位置。已通过 Ubuntu Python2 语法与依赖导入核查、launch 节点清单检查和网页 API 读取；两图均为100×99、9900格，七个窗口和两个识别区域均加载。原始地图副本与原 PGM 字节一致。

## 现场启动条件

用户放回场地起点、拔掉充电器并确认车头方向和停车后，再启动已验证底盘/雷达输入节点。硬件启动可能进行转向回中校准；本阶段不发车。先在 ROS 未运行时同步时钟，然后确认 `/odom`、`/medical_slam_scan`、`odom → base_footprint → base_laser_link`。小车搬动或重启后旧位置无效，必须重新设置初始位置和朝向。

执行位置：VMware Ubuntu 终端。传感器已运行、无地图/AMCL/SLAM重复发布者后执行：

```bash
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
assets=/home/ncut/medical_localization_assets_20261011
roslaunch medical_robot site_localization_observe.launch \
  raw_map:="$assets/map.yaml" \
  structured_map:="$assets/site-geometry-candidate.yaml" \
  annotations:="$assets/site-annotations.json" port:=8080
```

预期输出：map_server 加载地图，AMCL 读取扫描，显示服务监听8080；没有行驶控制发布者。用 RViz 的 `2D Pose Estimate` 设置实际位置及朝向后，网页会出现蓝色箭头与红色雷达点。不要用 `2D Nav Goal`。只出现箭头不等于定位通过；要确认当前位置、车头、雷达墙线和中央障碍都对应。

## 实车定位进展

用户确认已拔掉充电器、在右下起点黑线附近停车，车头朝场地图右侧、车头前端在黑线上。只读核对后，未发现已有 ROS 驱动或手柄。候选底盘源码 SHA256 为 `d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1`，与已使用版本一致。

在 ROS 启动前将小车时钟从 2025-10-30 同步到 Ubuntu 当前时间，五个校时后样本的最大偏差约 5.3 ms。启动既有硬件输入 launch 和扫描适配节点，未改底盘参数；控制话题 Publishers: None，启动读到线速度0，角速度约 -0.000177 rad/s。

已启动 Ubuntu 的 map_server、AMCL 和网页实车模式。当前实时界面为 `http://192.168.12.71:8080/`；8081仍是离线预览。粗略初始位姿为地图坐标(-0.12644,-0.026359,0)，位置标准差0.30m、航向标准差20°。此种子依赖临时假定的车头前伸距离0.22m，不属于实测车身尺寸，不能用于导航 footprint 标定。随后调用 AMCL 的无运动更新服务取得静止扫描匹配，不发布行驶命令。

第一段采集得到6条AMCL、531条odom、15帧末端扫描。扫描有效端点574个，其中93.4%处于原图占用格中心10cm内，整理图为86.2%；该统计仅说明近邻贴合，不保证射线无穿墙、定位唯一或导航合格。保留原图作定位底图，整理图只作切换展示。原始odom有稀疏角速度峰值约0.00977rad/s，属于此前已经记录的问题，不将峰值自动解释为实车转动；现场表现待用户确认。

针对初始协方差偏大，再执行20次有界无运动更新，取得11条AMCL。末位置约(-0.2247,-0.0235)，航向约-2.2°；位置标准差约0.120m与0.056m、航向标准差4.8°。该段估计位置变化幅度约5cm×4cm，是滤波器修正，不当作实际位移。网页位置TF新鲜度约23ms，数据更新正常。8+20次控制发布者检查均为空。全程未发布速度或导航目标。

实时位置显示已经工作；尚需用户确认箭头与实车方向和位置一致、启动时车轮/车体未移动。下一步安排带现场观察的短距离低速定位验证，再考虑闭环自主绕场。地图、车身尺寸、路线余量和定位尚未通过完整运动验收，不自动发送整圈路线。

## 参考点显示升级（2026-10-11）

用户确认网页蓝色箭头与实车大体一致，但需要区分雷达位置。只替换显示节点，没有重启底盘、地图服务或 AMCL，也没有发布速度或导航目标。显示节点以 `--resume-initialized` 恢复本次仍在运行的初始化事实，不重新发送 `/initialpose`。

静止验证文件：Windows `medical-localization-20261011/reference-display-before-retry2.json`、`reference-display-after-retry2.json` 和 `reference-display-update-retry2.log`。验证得到后轴参考点到雷达中心距离 0.135000 m，车头方向投影 0.135000 m，横向偏差 0.000004 m；网页 API 的 TF、雷达和里程计均新鲜，AMCL 协方差约为 x 0.112 m、y 0.053 m、航向 4.85°。控制话题 `/cmd_vel`、`/medical_ground_cmd_vel`、`/medical_nav_cmd_vel`、`/move_base/goal`、`/move_base_simple/goal` 均无发布者。

本轮下载记录：`medical-localization-20261011/prepare.txt`、`offline-state.json`、`hardware-preflight.txt`、`clock-sync.txt`、`inputs-start.txt`、`localization-start.txt`、`initialization.txt`、`site-initial-localization.json`、`live-state.json`、`alignment-review.json`、`site-convergence.json`、`live-convergence.json`、`localization.log`。原地图、位姿图与既有录包保留。
