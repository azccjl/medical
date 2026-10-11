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

## 短距定位验证与速度原因（2026-10-11）

用户确认前方至少 1 m 空旷后，执行一次受监督的直行验证。程序先检查控制话题唯一性、雷达通道和静止基线，再向 `/medical_ground_cmd_vel` 发布 `linear.x=0.05 m/s` 持续 4 s，随后发送零速并等待 4 s 严格静止窗口。输出 `short-motion-localization-20261011.json` 状态为 `STOPPED_STATIC_WINDOW_PASSED`，没有错误，控制发布者结束后为 None。

用户现场量得实际移动约 60 cm；程序记录的里程计位移约前进 0.411 m、侧向 -0.071 m，现场测量优先用于判断真实位移。本次验证主程序确实发送了正速度；仅凭这一程序记录不能排除上传与排查期间另外发生的非预期运动。后续用户已确认另一次排查期间有额外前进，见本文末尾调查断点。

已确认的一项速度原因是车端候选底盘源码 `medical_art_racecar_heading_v2_candidate.py` 的 `_medical_raw_cmdCB`：当 `trans_x` 为正且小于 `0.1` 时，代码将其改为 `0.1`；负速度也有相同下限。因此本次发送的 `0.05` 被底盘转换成 `0.1`，不能用低于 0.1 的命令实现更慢速度。这不单独解释全部实际距离，也不解释无行驶命令阶段的非预期运动。后续自主运动必须先按这一规则重新设计脉冲时长，并单独标定“命令速度—实际位移”。

## 搬回起点后的恢复与规划预览

用户随后将小车搬回起点，再次明确车头朝右、车体最前端对齐识别板一旁黑线、拔掉充电器并停稳。本阶段没有发送行驶命令。

采用此前实测后轴到车头 0.245 m，更新粗略初始位置为 (-0.15144,-0.026359,0)。第一次发布存在 ROS 连接时序问题：AMCL 仍保持旧位置，该 JSON 的 `REINITIALIZED_NO_MOTION` 不能作为成功恢复的证明；原文件保留。修补为等待包括 AMCL 在内的初始位置订阅连接、锁存消息，并校验新的定位结果接近种子后，第二次恢复成功。日志包含显示节点在发布者退出期间的连接警告；AMCL 新结果和网页状态已独立核对。

第二次末位姿约 (-0.210,-0.026)，航向 -2.27°。另做仅订阅的停车收尾，取得 202 帧、4.017 s 的连续严格窗口，最大允许速度仍为 0.002，单帧间隔不超过 0.2 s。收尾位姿约 (-0.175,-0.028)，航向 -3.22°，轴向位置标准差约 0.126/0.057 m，航向标准差约 5.64°。无行驶发布者。位姿修正不是车体实测移动。

已将导航 footprint 和 TEB footprint 改成已有实测边界 `(0.245,0.11),(0.245,-0.11),(-0.100,-0.11),(-0.100,0.11)`；0.45 m 配置转弯半径仍是暂定值。只部署配置，未启用实体控制。

离线生成带圆弧的外圈路线预览，状态 `PREVIEW_ONLY_MOTION_DISABLED`，圆弧半径 0.55 m 是候选。原图上沿该路线采样的最小车身障碍净距约 0.040 m；当前定位不确定性下筛查余量不足。雷达端点约94%接近墙格，但562条射线中137条在回波前穿过旧占用格，说明端点贴合不能代替完整定位/地图验收。实际边界仍需核对，不使用人工平滑图抹掉实测障碍以便强行通行。

已运行隔离的 `navigation_plan_preview.launch`：不重复启动 AMCL、底盘、雷达或地图服务，速度输出到没有订阅者的 `/medical_nav_preview_cmd_vel`，动作接口也单独重映射。只调用 `GetPlan` 服务，捕获5条预览路径，未发送导航目标。预览结束后关闭规划节点，保留网页、AMCL、雷达与底盘观察输入；`/medical_ground_cmd_vel` 发布者仍为 None。Navfn 路径不是 Ackermann 转向可行性验收。

旧 `vm_short_motion_localization_20261011.py` 已禁止执行：其 0.05 m/s 命令被提升，且其停车检查缺少原严格窗口的完整时序要求，不能将旧报告名称当作严格停车证明。旧代码曾删除它自己的执行锁；本阶段不伪造旧锁，也不删除任何现存 JSON/lock。新脚本使用原 `StopWindow`、单调计时和永久保留锁。

下一次运动候选为 `medical_supervised_short_pulse_20261011.py`，复用已核对 SHA 的车端安全通道与严格停车窗口。命令为 +0.10 m/s、最多0.50 s，里程计位移达到0.08 m提前停发；有驱动超时、独立定时零速保护、异常收尾、雷达通道与控制发布者检查。默认不执行，只有 `--execute --clear-floor --power-stop-confirmed` 才进入运行。尚未执行；预计实际5–15 cm只是观察预期，不能当真实距离保证。暂不改车端速度下限，不按一次约60 cm观察直接修改里程计比例。

### 离线可用的 Ubuntu 命令（本轮已执行过，不自动重复）

```bash
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=$(ip -4 route get 192.168.12.1 | sed -n 's/.* src \([^ ]*\).*/\1/p')
unset ROS_HOSTNAME
# 下面只读检查，不发车；已经保存的采集文件拒绝覆盖。
rostopic info /medical_ground_cmd_vel
rosnode list
python2 /tmp/medical_supervised_short_pulse_20261011.py
```

预期：底盘控制话题 `Publishers: None`，节点保留 AMCL/map_server/网页/硬件输入；候选程序打印 `PREPARED_ONLY_NO_ROS_COMMANDS` 并以拒绝执行的返回码退出。文件复制和默认调用不启动运动。

下载目录 `D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`：`site-reinitialize.log`、`site-reinitialize-v2.log`、两版 `site-reinitialized-after-relocation*.json`、`site-final-stop-after-reset-20261011.json`、`site-final-stop.log`、`outer-loop-final-stop-review/outer-loop-preview.png/json`、两版 `navigation-preview*.log` 与 `navigation-plan-preview*.json`、`plan-preview-finish.log`、`short-pulse-prepare.log`。原报告和地图保留。

### 短脉冲实际执行与断点

用户确认网页位置一致、车前至少1 m空旷并能观察/断电后，开始短脉冲验证。第一版检查到当前驱动日志中的 `Traceback` 而拒绝，`commands=0`。只读下载核对完整错误，实际是 `rospy` 内部的入站 TCPROS 握手未收完即断开，紧随只读停车节点退出；后续串口有效反馈持续，未出现串口写入失败。

新增独立安全辅助候选，只将已经完整核对的六行、0字节 TCPROS 握手断开堆栈精确分类。其他 Traceback、`MEDICAL_SERIAL_WRITE_FAILED` 和 `Invalid Index` 仍拒绝，停车阈值与数据新鲜度未修改。原辅助源码和原驱动未覆盖。中间版遇到 Python2 文件迭代与 `readline()` 混用错误，仍在任何行驶命令前拒绝；改为统一逐行读取后再运行新文件名。三份 JSON 与 lock 保留，实际只执行了一次正速度运动。

成功版本为车端 `medical_supervised_short_pulse_v3_20261011.py`，安全辅助 `medical_bench_pulse_heading_v8_logclassification.py` SHA256 `6d82b66a72b608975ed513e307a56d5f587119d57e9ad723149ab61a64c3085b`。原驱动 SHA 未变。JSON 状态 `STOP_WINDOW_PASSED_AWAITING_PHYSICAL_MEASUREMENT`：6次正速度发布，首末跨度0.449 s，随后24次零速发布；主循环到零速收尾前约0.538 s，不能把发布窗口当作物理停止时间。严格停车窗口201帧、4.003 s，阈值0.002、最大间隔0.2 s，错误与cleanup_errors均为空。退出后 `/medical_ground_cmd_vel` 发布者 None。

雷达通道初始最小前向坐标（相对后轴）约1.220 m。里程计固定 odom 坐标变化约 (+0.0343,-0.0243) m，odom参考系与当前地图朝向不同，不能将固定轴的dy直接当作跑偏。此结果仍需结合用户对同一个车体固定点量得的实际距离、停车与方向判断；暂不自动继续转弯或整圈。

下载新增：`medical-supervised-short-pulse-20261011.json`、`medical-supervised-short-pulse-v2-20261011.json`（均零行驶命令拒绝）、`medical-supervised-short-pulse-v3-20261011.json`、对应三版 `supervised-short-pulse-execute*.log`、`base-log-before-pulse-review.log`、`handshake-trace.log`、`short-pulse-final-view-v3.json`。此处原断点已被下方的非预期运动调查替代。

## 最新断点：非预期运动调查

用户确认两次前进总约30 cm，第二次正式动作约15 cm；第一段发生在“保护检查拒绝”的排查与上传修补期间。正式动作的车体前向 odom 约4.20 cm，与实测不符。历史原始反馈有多次正式动作之外的短暂非零线速度，尚无完整TX证据确认触发者。

已停止底盘驱动，随后再次从Ubuntu经SSH核对其节点退出、串口无人占用、控制话题消失。网页TF会过期，不能继续自主运动。原JSON、lock、地图和日志保留。独立零速串口诊断候选已准备，Ubuntu离线检查通过，尚未上传或启动。用户明确当前不方便架空、要求保持底盘停止，本轮不启动硬件诊断。以后现场能稳固架空驱动轮、随时断电后再作针对性观测。完整结论、源码风险、命令与下载文件见 [非预期运动调查](uncommanded-motion-investigation-20261011.md)。

本轮下载记录：`medical-localization-20261011/prepare.txt`、`offline-state.json`、`hardware-preflight.txt`、`clock-sync.txt`、`inputs-start.txt`、`localization-start.txt`、`initialization.txt`、`site-initial-localization.json`、`live-state.json`、`alignment-review.json`、`site-convergence.json`、`live-convergence.json`、`localization.log`。原地图、位姿图与既有录包保留。
