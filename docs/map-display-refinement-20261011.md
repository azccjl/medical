# 地图显示优化与后续绕场断点（2026-10-11）

## 本阶段范围与结果

用户最新要求是“先不要运动，先做建图的修改，待会绕场一周”。本阶段只修改离线地图导出和 Ubuntu 网页显示，未运行底盘、未发送速度、未重新建图。车端执行的命令只读取底盘串口占用情况，未向小车复制程序。

整理图之前已经按规则生成直角；本次修正网页显示栅格放大造成的锯齿。原始扫描地图和旧整理图均保留，新版本位于 `maps/site-layout-display-v2-20261011/`。

- 外围和中央矩形、L 形挡板使用矢量轮廓显示，右下角保持直角。
- 默认展示整理图，可切换原始扫描图；增加 1 米比例尺。
- 保留 1、2、3、4、A、B、C 七个 0.5 米方框及两条识别线，没有 D。
- 注释文件增加独立地图元数据和地图坐标多边形。方框不再依赖当前显示地图的尺寸、分辨率来重新计算位置，防止日后切换不同地图时错位。
- 无新鲜定位/雷达时隐藏旧雷达回波；静止程序结束后提示定位数据过期。
- 候选占用地图的 PGM 内容与上一版本完全一致；AMCL 继续使用原始扫描地图。

矢量显示解决的是边缘显示问题。规则轮廓与实车雷达的配准、窗口停车点和方向仍需现场确认；本次不能作为 SLAM 几何精度或自主绕场验收。

## 校验记录

`maps/site-layout-display-v2-20261011/map-review.json` 记录：

- 地图 100×99 格，分辨率 0.05 米，原点 `[-3.206440, -0.726359, 0]`。
- 外围 4.5×4.5 米，外围及挡板共 14 条轴向边。
- 七个方框中心与地图坐标多边形一致，两条识别线存在。
- 新旧候选 PGM SHA256 都是 `93903a951828d76c4f9e763cab1549c9a31ae0749569b0b5afdc80333af64d41`。
- 原图 SHA256 仍为 `e301b8e583d1e019f88d42bebba92234fba7c3af62a274a46a72904b7f5be88c`。

通过 VMware 在 Ubuntu 内完成 Python 2 编译检查、显示服务更新和 API 核对。只重启网页显示进程，没有重启 AMCL、map_server 或雷达。更新前后 `/cmd_vel`、`/medical_ground_cmd_vel`、`/medical_nav_cmd_vel`、导航目标话题的发布者均为空；显示节点除 ROS 日志外没有数据发布者。更新前后车端均报告 `SERIAL_OWNERS []`。

网页截图 `maps/site-layout-display-v2-20261011/live-display-v2.jpg` 已检查墙线和标记；PNG/SVG 可单独查看。

## 离线重现命令与执行位置

在 Windows PowerShell 中进入 `D:/BaiduNetdiskDownload/F1/medical`，执行以下完整命令。不需要互联网，也不连接底盘：

```powershell
Set-Location -LiteralPath 'D:/BaiduNetdiskDownload/F1/medical'
& 'C:/Users/mine/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tools/map_review/build_structured_site_map.py --source-dir maps/slam-20261010 --output-dir maps/site-layout-display-v2-20261011
& 'C:/Users/mine/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tools/map_review/review_structured_site_map.py --raw-dir maps/slam-20261010 --previous-dir maps/site-layout-20261011 --output-dir maps/site-layout-display-v2-20261011
```

预期第二条命令输出 `OFFLINE_GEOMETRY_AND_COORDINATES_CHECKED`、`occupancy_unchanged: true`、`axis_aligned_edges: 14`、`robot_motion_sent: false`。

已部署的 Ubuntu 显示程序与地图：`/home/ncut/medical_map_display_v2_20261011/`；原程序和旧资产保留在原路径。以下 Ubuntu 终端命令用于单独启动新显示程序，仅在 8080 端口未被已有显示服务占用、同一 AMCL 初始化会话仍保留时执行。它不恢复底盘数据，也不初始化定位：

```bash
source /opt/ros/melodic/setup.bash
source /home/ncut/medical_ws/devel/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 /home/ncut/medical_map_display_v2_20261011/site_localization_view_v2.py \
  --raw-map /home/ncut/medical_localization_assets_20261011/map.yaml \
  --structured-map /home/ncut/medical_map_display_v2_20261011/site-geometry-candidate.yaml \
  --annotations /home/ncut/medical_map_display_v2_20261011/site-annotations.json \
  --port 8080 --resume-initialized
```

预期 `SITE_LOCALIZATION_VIEW port=8080 offline=False`。本阶段当前定位显示过期属于预期：零速底盘程序已结束，不能据旧位姿发车。新 AMCL 会话需重新初始化，届时不要使用 `--resume-initialized` 绕过显示等待状态。

## 已下载与可查看文件

Windows 证据目录：`D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`：

- `map-display-inspection.log`：原显示服务、地图元数据、控制发布者。
- `map-display-v2-deploy.log`：更新过程、车端前后只读检查、服务核对。
- `map-display-v2-refresh.log`：最终显示状态提示更新及串口复核。
- `map-display-v2-state.json`：最终 API 状态、两份占用地图、注释。

地图目录可查看 `site-annotated.png`、`site-annotated.svg`、`map-before-after.png`；占用地图为 `site-geometry-candidate.pgm` 与相对路径 YAML，语义坐标为 `site-annotations.json`。语义方框和识别线不作为占用障碍。

## 接续阶段

本阶段结束时底盘仍停止，没有地面脉冲，也没有绕场。以后运动前先告知动作并等待现场准备。

绕场之前先明确是手柄复核还是自主巡航。自主巡航需要恢复实时定位、确认起点及方向、完成地面速度/位移和转向验证、核对路线车体净距，再分段验收一圈。此前短脉冲的实测位移与里程计仍有差异，不能以整理图更平直为由跳过这些条件。未执行的地面脉冲候选继续暂停，雷达边界浮点筛选问题另行修补。
