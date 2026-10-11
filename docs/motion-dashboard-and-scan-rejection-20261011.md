# 雷达拒绝原因与网页短直行控制

## 本轮结果

- 新网页：<http://192.168.12.71:8082/>，运行在 VMware Ubuntu。原定位页 <http://192.168.12.71:8080/> 嵌入其中。
- 文件经 Ubuntu SSH helper 上传到小车；上传后 SHA256 匹配，底盘串口无人占用。
- 本轮没有执行运动程序，没有发送前进指令，也没有启动底盘。雷达、AMCL 和地图显示服务继续运行。
- 用户确认小车已不在原起点。因此旧位置、朝向及空旷距离确认不继续用于发车；本页面也不支持点击场地图导航。

## 为什么此前拒绝发车

1. 原 v3 把部分位于车体范围内的有限回波算入前进走廊，导致非常小的净距。v4 候选已过滤这些回波；本轮 v5 使用同一过滤范围，并在页面单独显示它们。
2. 前方确有未知回波。历史 v4 记录的 100 帧里，74 帧边缘未知，27 帧连续未知角宽超限；同一帧可能触发两项。
3. 本轮现场已经换位置。新的原始 `/scan` 与 `/medical_slam_scan` 对比均存在缺失，原始扫描有效覆盖约 62%–70%，转换扫描约 65%–72%；无法仅通过改变建图重采样解决。本轮后续网页扫描还会随环境变化。
4. 旧检查在第一条失败时抛异常，没有展示其余条件和测量值。现在共享模块一次列出全部原因。

未知回波保持为未知，不插值为空地、不从地图推测为实测空闲。数值来自当前扫描，不是固定的故障码展示。

## 修补范围

- `medical_scan_report_20261011.py`：无 ROS/串口依赖的完整诊断；与 v4 的扫描接受/拒绝条件一致。
- `medical_ground_straight_pulse_v5_20261011.py`：新增打开底盘串口前的连续扫描门禁；发令仍严格限定 `+0.10 m/s`、最多 `0.20 s`、零转向。增加持久取消标记。
- `medical_motion_dashboard_20261011.py/.html`：显示前方回波、未知方向、车体内回波、净距、覆盖率、缺失角宽、拒绝原因、原定位页和证据下载。

保留原门限：停车三个速度分量不超过 `0.002`，连续静止至少 4 秒、样本间隔不超过 0.2 秒、至少 100 帧；前方有限回波覆盖至少 90%，未知缺口不超过 1.01°，前方净距至少 0.605 m。没有删除任何原始 JSON、lock、日志、地图或录包。

## 网页怎么用

1. 保持车辆静止，查看雷达预检。若显示红色拒绝，查看具体原因与橙色未知方向；按钮禁用。
2. 小车放回可行驶位置后，现场确认位置、车头方向、前方至少 1 米空旷、充电器拔掉，并能观察和断电。
3. 预检通过后，勾选现场确认，点“复核并准备”。这步不打开底盘串口、不发车；准备有效 10 秒。
4. 点“开始一次短直行”。服务端再次检查扫描和 ROS 图，车端检查文件哈希、串口占用、控制发布者，再收集严格静止反馈；通过才发送一次固定短脉冲。
5. 运行结束后查看日志、确认实车停稳。拒绝或失败不会自动重试。每次请求使用新的 UUID 审计文件和永久保留的 `.lock`。

“取消本次运行 / 请求停车”经网络发送持久取消标记，执行器在开串口前、停车等待和每次前进写入前检查。取消不是硬件急停；网络可能延迟，异常时现场断电。独立 0.20 秒计时器和原底盘超时继续生效。

本阶段没有执行实车按钮运动，因此不能声称网页运动已通过实车验收。底盘停止后定位会过期；搬动后须重置定位，不能用旧箭头直接绕场。

## 校验

- 回放历史 100 帧：v4 与新诊断的接受/拒绝结果完全一致。
- 固定串口零速白名单 12 项、正向帧窗口 9 项、扫描政策 9 项离线检查通过。
- 网页状态门禁 14 项检查通过：无扫描、扫描过期、外来发布者、ROS 图过期、无效准备令牌、缺少现场确认、已有运行均拒绝。
- Ubuntu 页面可访问，实时指标与拒绝原因显示正确；刷新后没有请求运行，车端串口仍无人占用。

## 完整离线命令与执行位置

以下在 **VMware Ubuntu 的 ncut 终端**执行，无需联网下载安装。目录文件已准备好。

只做离线校验（不连接 ROS、不执行 SSH、不打开串口）：

```bash
cd /home/ncut/medical_motion_dashboard_20261011
python2 medical_ground_straight_pulse_v5_20261011.py --offline-check
python2 review_motion_dashboard_offline_20261011.py \
  --output "/home/ncut/medical_motion_dashboard_20261011/dashboard-review-$(date +%s).json"
```

预期输出包含 `OFFLINE_POLICY_CHECK_PASSED`、`OFFLINE_FORWARD_POLICY_PASSED`、`OFFLINE_SCAN_POLICY_PASSED`、`DASHBOARD_OFFLINE_REVIEW_PASSED`；硬件打开为 false。

网页服务若以后已经退出，可在 Ubuntu 手动启动被动页面（不会启动底盘）；现已运行，无需重复启动：

```bash
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
cd /home/ncut/medical_motion_dashboard_20261011
python2 medical_motion_dashboard_20261011.py \
  --bind 192.168.12.71 --port 8082 \
  --output-dir /home/ncut/medical_motion_dashboard_20261011/evidence
```

预期输出 `PASSIVE_DASHBOARD ... no base started`。端口占用则说明已有页面服务，请勿重复启动。部署脚本是一次性上传流程，会拒绝覆盖已有车端目录；不是恢复页面的命令。

## 下载和证据位置

- 页面“下载当前预检 JSON”：只下载当时扫描和门禁状态。
- 按钮执行完成后，页面出现本次 `.jsonl`、`.jsonl.lock`、`.jsonl.log` 下载链接。无运行时没有运动证据文件。
- Ubuntu：`/home/ncut/medical_motion_dashboard_20261011/evidence/`。
- 小车：`/home/EPRobot/medical_dashboard_20261011/`。
- 本轮 Windows 校验记录：`D:/BaiduNetdiskDownload/F1/medical-localization-20261011/dashboard-*.json` 与 `dashboard-*.log`；仓库另存本轮选定证据。

下一阶段：车辆放回场地后先复核当前雷达与定位，再通过网页完成一次短直行及现场观察，之后才继续转向验证和绕场导航。
