# 摄像头接入与右下角视觉参照物（2026-10-11）

## 本轮断点

相机 RGB、网页预览、二维码观测和 ArUco 检测已接入。10 秒实机采集收到 50 帧（5.022 Hz，640×480）和 50 条二维码观测消息。当前实景无二维码，尚未验收真实二维码识别率；ArUco 已用合成 ID 0/1/7/49 验证。未发布底盘指令、初始定位或相机 TF。

已停止本轮 Astra、RGB 桥接进程并复查：`camera_processes=[]`、`base_serial_owners=[]`。小车可关机充电。Ubuntu 网页可保留，但停止取流后应显示过期，旧图像不是实时画面。

用户允许在场地右下角放置纸质视觉标记。尚未放标记、测量位置或完成相机到底盘标定，**视觉地图定位尚未实现，不能把“检测到标记”称作“已知道车在地图哪里”**。本次车在场地外，不做定位初始化或运动。

## 已有链路

| 部分 | 当前设置 |
|---|---|
| 小车 | EPRobot，192.168.12.1，ROS Melodic |
| Ubuntu | 本轮 IP 192.168.12.70；网页启动脚本自动取到小车的出站接口 IP |
| 驱动 | `astra_camera astra.launch camera:=medical_astra publish_tf:=false` |
| 原图 | `/medical_astra/rgb/image_raw`，约 30 Hz |
| 相机内参 | `/medical_astra/rgb/camera_info`，640×480，K/D 非零；这不等于已完成独立标定验收 |
| 无线预览 | 小车本地 JPEG 编码，75 质量，5 Hz，`/medical_vision/image/compressed` |
| 二维码 | 小车 `pyzbar`，`/medical_vision/qr_observations`，只输出文字/像素框，不自动执行任务 |
| ArUco | Ubuntu OpenCV 3.2，`DICT_4X4_50`，输出 ID/像素角点 |
| 网页 | `http://192.168.12.70:8085/`，画面、检测和定位新鲜度；8084 已被原有服务占用 |
| 米制视觉定位 | 未启用；没有相机外参、实测标记位置，不输出候选地图位姿或融合到 AMCL |

实机单帧 JPEG 约 50 KB，5 Hz 约 2 Mbps 图像负载，显著低于把 RGB 原图全速传到 Ubuntu。

当前网页和桥接独立于导航；相机启动、文件上传不会启动底盘。尚未加入自动开机服务。停机前最后画面显示实验室环境，而非场地，因此本轮网页没有可用 AMCL 位置是符合现状的。

## 下一步：用一个固定标记辅助定位

1. 打印 `aruco-id0-120mm.svg`，选择实际大小/100%，用尺确认黑色外框边长 **12 cm**。白色外缘保留，平贴在硬纸板上。
2. 在右下角固定标记，使相机接近时能完整看到四边。记录黑框中心距场地右墙、下墙的距离和距地高度、朝向；不要把“右下角”直接当作精确地图坐标。
3. 校验相机内参和相机相对后轴参考点的安装位姿，再利用角点 PnP 获得相机相对标记的位置。根据实测标记地图位姿换算后轴地图位姿。
4. 首先显示视觉候选位置与 AMCL 位置的偏差，不自动修正 AMCL；静止条件下验证后再决定融合方式。

单个角落标记只在看得见时提供绝对参照。绕场中看不见标记时仍使用 AMCL、里程计和 IMU，摄像头不会恢复被挡住的后方雷达视野。全圈导航还需完成实际左转及一轮综合路线验证，不能因为摄像头接入就视作绕圈验收通过。

## 离线恢复命令（执行位置：VMware Ubuntu 终端）

这些文件已准备在 `/home/ncut/medical_camera_assist1_20261011/`。小车开机、Ubuntu 接上小车网络、ROS Master 可用后运行。相机启动阶段车保持停稳，不启动底盘。

```bash
export PYTHONIOENCODING=utf-8
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /home/ncut/medical_camera_assist1_20261011/robot_start_camera_readonly_20261011.sh

python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /home/ncut/medical_camera_assist1_20261011/robot_start_camera_bridge_20261011.sh

bash /home/ncut/medical_camera_assist1_20261011/vm_reset_vision_web_20261011.sh
```

预期：`CAMERA_LAUNCH_ALIVE`、`CAMERA_BRIDGE_STARTED_NO_BASE_NO_TF_NO_INITIALPOSE`，并打印当前网页 URL。若提示重复实例，先核对已运行的实例，不要反复启动同名节点。代码文件已经经 Ubuntu helper 上传到小车，关机充电不会删除文件。

停止摄像头：

```bash
export PYTHONIOENCODING=utf-8
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /home/ncut/medical_camera_assist1_20261011/robot_stop_camera_readonly_20261011.sh
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /home/ncut/medical_camera_assist1_20261011/robot_camera_shutdown_check_20261011.sh
```

预期：`CAMERA_SHUTDOWN_CONFIRMED_BASE_CLOSED`。ROS Master 不可用或小车关机时，不运行恢复定位和运动程序。本轮验收采集脚本仅用于该次证据，后续复测另建输出目录，保留已保存的 JSON/锁/日志。

## 本地记录

目录：`D:/BaiduNetdiskDownload/F1/medical-camera-assist1-20261011/`

- `camera-acceptance.json`：10 秒图像和二维码观测统计、合成 ArUco 检测结果。
- `shutdown-check.out`：相机退出和底盘串口关闭证据。
- `offline-checks.out`：11 项通过，含过期图像、未来时间戳、过期预览和未来 AMCL 拒绝显示为实时。
- `rgb-sample.jpg` / `bridge-sample.jpg`：本轮实际图像，保存在本地资料包；不作为导航地图。
- `aruco-id0-120mm.svg`：右下角参照物打印文件。

离线检查命令（Ubuntu，无需启动底盘）：

```bash
source /opt/ros/melodic/setup.bash
python2 /home/ncut/medical_camera_assist1_20261011/offline_vision_checks.py
```

离线检查结果全为 `true`。真实标记可见性、视觉定位精度和竞赛二维码识别仍留待充电后的现场综合观测。
