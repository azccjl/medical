# 自动导航上场前准备记录

日期：2026-10-11（北京时间）。本轮仅完成软件准备、上传与检查，没有启动实车底盘、没有发运动指令。

## 1. 当前断点

**可进入现场验证阶段，尚未完成实车自主导航验收。** 小车目前不在已确认的地图起点；网页保留的旧定位不能作为发车依据。

路线工作台：http://192.168.12.71:8083/

定位显示：http://192.168.12.71:8080/

雷达与短直行检查：http://192.168.12.71:8082/

已完成：

- 网页点选路线、撤销、清空、圆弧转角预览、双地图整车检查、保存和下载草稿。
- 导航任务的开始、暂停、继续、取消接口及页面状态。默认全部禁止发车；现场验收通过并显式启用后才允许发目标。
- ROS1 的 move_base、Navfn、TEB 转向底盘候选配置；输出独立在 `/medical_field_candidate/cmd_vel`。
- 速度控制门、串口发送/接收审计、唯一控制发布者检查、断流停车、路线任务心跳。
- 取消状态不可被后续“继续”请求撤销；路线任务退出/失联时，控制门停止非零输出。
- Windows 和 VMware Ubuntu 各 50 项纯函数检查通过；任务正常结束、暂停/恢复、取消的模拟检查通过。
- Ubuntu `catkin_make` 和安装通过；安装目录中实际运行候选脚本的导入与任务模拟通过。
- 独立环回 ROS master 上 Navfn/TEB 加载和 GetPlan 服务通过，未发送 action 目标。
- 最新底盘候选上传后以默认模式检查：`PREPARED_ONLY`，不导入 ROS、不打开串口。车端串口无人占用。

最终状态证据：`docs/evidence/navigation-ready-20261011/final-passive-state.json`。

## 2. 地图与绕场候选

定位及原始地图：`maps/slam-20261010/map.yaml`。

整理显示地图：`maps/site-layout-display-v2-20261011/site-geometry-candidate.yaml`。

地面 1、2、3、4、A、B、C 与两条识别区域线仅作为标记显示，尚未标定为停车目标。场地尺寸按 4.5 m × 4.5 m；整理图需要现场雷达墙线配准后才可确认其位置准确性。

绕场候选后轴坐标（米，`map` 坐标系）：

```json
[[-0.35,0.075],[0.90,0.075],[0.90,3.55],[-2.40,3.55],[-2.40,0.075],[-0.35,0.075]]
```

- 圆弧半径：候选 0.75 m，仍须实测。
- 路线长度：12.2623 m，823 个采样点。
- 原始图和整理图均为 0 个碰撞失败采样。
- 使用整车轮廓，并预留 0.10 m，以及栅格与采样离散余量；未知区和地图外区域拒绝通过。
- 实际导航用沿线间隔约 0.35 m 的目标逐段执行，每段间检查停车。TEB 实际轨迹允许在目标附近调整，预览蓝线不是已经实测的车辆轨迹，也不是强制精确贴线控制。
- 页面 123 秒只估算 0.10 m/s 的行驶时间；逐段停车和现场检查会增加总用时。

草稿：`docs/evidence/navigation-ready-20261011/outer-route-draft.json`。保存草稿不会执行导航。

## 3. 本轮修补与仍须实测的限制

原驱动 `_medical_raw_cmdCB` 会把 `0 < v < 0.10` 自动抬到 0.10 m/s。直接接入 TEB 会改变起步和减速指令。

本轮在独立 `navigation_audited_base.py` 中覆盖编码方法，按请求速度编码，保持原协议、CRC 与 PID 字段，**没有修改原车端驱动**。离线验证了 0.01、0.02、0.05、0.10 m/s 不被抬高。这个结果只验证编码，不能证明电机在这些速度下能可靠转动。

现场必须测最低可靠速度、响应比例和停车距离。低于实测可靠速度的非零命令会拒绝并停车，不能用自动放大速度绕过。若 TEB 起步/减速输出与实测最低速度不兼容，先完成针对性调整和检查，再开放整圈导航。

导航速度上限候选 0.12 m/s；禁止倒车和原地旋转。转弯半径至少 `max(0.75 m, 实测半径)`。门限、实时雷达有效覆盖与停车规则均保留。

严格停车规则仍是 vx、vy、wz 绝对值不超过 0.002；连续 4 秒、至少 100 帧、相邻反馈间隔不超过 0.20 秒。没有把停车门限放宽。

控制门还要求 odom、scan、AMCL 新鲜、定位协方差合格、来源唯一、前方弯曲整车停车走廊可用。未知雷达射线进入停车走廊时拒绝，不虚构空闲读数。现场墙线、黑色围挡或雷达布置有差异时，先核对原始数据。

本轮未证明全套控制链已经在实车运动中通过；只完成软件与模拟检查。旧架空验证不能替代新编码候选的现场验证。

## 4. 部署位置

| 位置 | 路径/用途 |
|---|---|
| Windows 仓库 | `D:/BaiduNetdiskDownload/F1/medical` |
| Ubuntu 软件工作区 | `/home/ncut/medical_navigation_prepare_v2_20261011` |
| Ubuntu 被动网页 | 工作区 `src/medical_robot/scripts/route_workbench.py`，8083 |
| 小车候选目录 | `/home/EPRobot/medical_navigation_prepare_v2_20261011` |
| 小车原驱动 | `/home/EPRobot/robot_ws/src/eprobot_start/script/medical_art_racecar_heading_v2_candidate.py` |
| Windows 离线包与截图 | `D:/BaiduNetdiskDownload/F1/medical-navigation-prepare-20261011` |

小车候选目录内的 `navigation_audited_base.py`、`navigation_policy.py`、`route_geometry.py` 和验收模板已核对 SHA256。所有实车访问通过 Ubuntu 的 `/home/ncut/vm_connection_check_20261009.py`；Windows 没有直接 SSH 小车。

初始构建脚本误假定 catkin 为 `#!/usr/bin/env python2` 脚本生成 `devel/lib` 包装文件，检查因此退出。后续改为实际 `rosrun` 源脚本入口和 `install/lib/medical_robot` 入口，两者通过；完整初始构建与失败记录均保留。最后更新还在安装目录重跑了任务控制模拟。

## 5. 完整离线复查命令

下面命令均在 **VMware Ubuntu 终端** 执行，不需要联网安装依赖，不启动实车底盘。现有工作区直接复查时，报告使用新目录，避免覆盖任何 JSON/lock。

```bash
set -e
navstage=/home/ncut/medical_navigation_prepare_v2_20261011
navrun="$navstage/review-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$navrun"
source /opt/ros/melodic/setup.bash
source "$navstage/devel/setup.bash"

python2 "$navstage/review_navigation_offline.release.py" \
  --scripts "$navstage/src/medical_robot/scripts" \
  --raw-map "$navstage/maps/raw/map.yaml" \
  --structured-map "$navstage/maps/structured/site-geometry-candidate.yaml" \
  --acceptance "$navstage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --output "$navrun/offline.json"

python2 "$navstage/review_route_runner_mock.release.py" \
  --scripts "$navstage/install/lib/medical_robot" \
  --acceptance "$navstage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --output-dir "$navrun/mock"

python2 "$navstage/review_workbench_http.py" \
  --url http://192.168.12.71:8083 --output "$navrun/http.json"

python2 "$navstage/src/medical_robot/scripts/navigation_audited_base.py" \
  --acceptance "$navstage/src/medical_robot/config/navigation/site_acceptance.template.json" \
  --map-sha UNACCEPTED
```

预期：50 项检查、三个模拟任务流程通过；HTTP 预览/保存成功，start/pause/resume/cancel 在默认模式全部返回拒绝；最后打印 `PREPARED_ONLY`、`ros_imported:false`、`serial_opened:false`。

### 从离线包重新构建独立工作区

将 `navigation-ready-offline.zip` 复制到 Ubuntu `/home/ncut/` 后执行：

```bash
set -e
navrestore="/home/ncut/medical_navigation_offline_$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$navrestore"
python2 - "$navrestore" <<'PY'
import zipfile,sys,json,hashlib
d=sys.argv[1]
with zipfile.ZipFile('/home/ncut/navigation-ready-offline.zip') as z:
    z.extractall(d)
m=json.load(open(d+'/manifest.json'))
for name,sha in m['files'].items():
    assert hashlib.sha256(open(d+'/'+name,'rb').read()).hexdigest()==sha,name
print('MANIFEST_OK')
PY
source /opt/ros/melodic/setup.bash
cd "$navrestore"
chmod +x src/medical_robot/scripts/*.py src/medical_robot/scripts/*.sh
catkin_make -DPYTHON_EXECUTABLE=/usr/bin/python2
catkin_make install
source devel/setup.bash
rosrun medical_robot route_workbench.py --help
python2 review_navigation_offline.py \
  --scripts src/medical_robot/scripts \
  --raw-map maps/raw/map.yaml \
  --structured-map maps/structured/site-geometry-candidate.yaml \
  --acceptance src/medical_robot/config/navigation/site_acceptance.template.json \
  --output offline-review.json
python2 review_route_runner_mock.py --scripts install/lib/medical_robot \
  --acceptance src/medical_robot/config/navigation/site_acceptance.template.json \
  --output-dir mock-review
```

预期：编译、安装、帮助入口和检查通过。此过程不启动网页、不连接小车、不运行真实导航。不要直接重跑已执行的一次性部署脚本；它们会检查目录/证据不存在，并拒绝覆盖。

## 6. 接下来上场的顺序

1. 拔充电器，把小车放回场地起点黑线；确认位置和车头朝向。先停稳，不碰手柄。
2. 仅恢复雷达、静止底盘数据与定位；观察轮子不转，检查蓝色后轴点、箭头、雷达墙线和地图是否相符。
3. 针对新编码候选先做架空控制/断流停车验证，再做地面短直行、距离比例、最低可靠速度、左右小弧和停车距离。每次实际运动前说明动作与观察项目。
4. 验证运动时定位；证据完整后生成独立现场验收文件，不把软件模拟数据写为现场通过。
5. 先运行一段很短的网页路线，确认开始/暂停/继续/取消、定位跟随和停车，再执行绕场候选。
6. 绕场稳定后标定七个任务站点的后轴停车位置和朝向，再接识别与自主取送任务。

正式控制链启动顺序必须是：审计底盘在无控制发布者情况下完成零速校准与严格停车 → 静止定位与地图对齐 → move_base 隔离输出 → 控制门 → 路线任务。不能在底盘陀螺校准期间先连接控制发布者。

现场验收模板 `site_acceptance.template.json` 始终保持 `FIELD_VALIDATION_REQUIRED`；本轮未创建可发车的验收文件。物理数据确认后，下一轮再提供对应实车执行命令，避免误启动。

## 7. 可下载文件和证据

- 离线程序、地图与清单：Windows 证据目录 `navigation-ready-offline.zip`。
- 路线 JSON：仓库 `docs/evidence/navigation-ready-20261011/outer-route-draft.json`。
- 50 项检查：同目录 `offline-review-windows.json`、`offline-review-ubuntu.json`。
- 任务控制模拟：`mock-route-controls.json`。
- 规划器集成：`isolated-planners.json`；ROS master 是 `127.0.0.1:11312`，action 目标发送数为 0。
- 默认网页接口：`passive-http.json`。
- 最终无任务/底盘串口状态：`final-passive-state.json`、`final-readonly.log`。
- 部署和构建：`passive-deploy.log`、`build.log`。

所有旧地图、JSON、lock、录包和日志均保留。没有重复已通过的静止 SLAM，没有执行自动整圈导航。

仓库中的报告副本只整理了 JSON 缩进和日志行末空格，便于版本管理；原始下载内容保留在 Windows 证据目录的 `raw-downloaded-evidence/` 及原始日志文件，Ubuntu 原记录未改动。
