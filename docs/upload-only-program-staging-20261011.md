# 只上传程序，暂不启动小车（2026-10-11）

用户说明场地正在被其他人使用，要求先上传程序，待会再启动。本阶段通过 Windows vmrun → VMware Ubuntu → SSH helper 上传文件，没有执行车端候选、没有启动底盘、没有发送速度、没有设置自动启动。

## 已上传与已核对

新上传文件：

- `/home/EPRobot/medical_ground_straight_pulse_v3_20261011.py`
- `/home/EPRobot/medical_staged_files_20261011.json`

v3 程序 SHA256：`c997fda7951424d7c29053b530809beff8cb6b658abdf7664b55807686dbd71c`。

既有 `/home/EPRobot/medical_stationary_localization_v3_20261011.py` 已静态核对，SHA256 仍为 `aa06ade75f042131310bf2bad910070728472d68c486ebd3592e206a31b6384d`。底盘驱动与原 StopWindow 源码校验值也一致；实际 StopWindow 文件位于 `/home/EPRobot/medical_stop_window.py`。未覆盖旧驱动、旧程序、JSON、日志或锁。

v3 是未来一次受观察的短直行标定候选：固定 +0.10 m/s、最多 0.20 秒正速发令窗口、零转向，保留原连续 4 秒停车门限和速度超限保护。它不是整圈导航控制器。车端未上传执行脚本，尚未现场启动。

## 离线修补与核对

修补仅增加微小的 LaserScan 角度浮点误差容差，约 `8.73e-7 rad`，让名义 -20° 的边界射线不会因 float32 舍入被错排除。停车门限、走廊净距、有限覆盖率、未知角度缺口限制均未改变。

Ubuntu 离线检查通过：12 个零速/查询帧策略检查、9 个正速发令窗口检查、9 个雷达策略检查，以及合成浮点边界、未知边界、近障碍案例。未导入 ROS 或串口模块。

更正此前概括：保存的三条真实 `/medical_slam_scan` 中第 680 条（名义 -20°）实际上也为 `+inf`，不能认为其为有限回波。v3 对三条保存扫描仍拒绝 `FRONT_SCAN_EDGE_UNKNOWN`，报告明确保留这一结果。合成输入证明数值修补有效，不代表真实扫描已通过运动前检查。没有用这些历史扫描批准本次或后续运动。

## 上传前后结果

车端只执行标准库文件/进程读取检查，没有 import 或运行候选程序。上传完成后确认：

```text
STAGED_FILES_SHA256_MATCH
SERIAL_OWNERS []
STAGED_OR_BASE_PROCESSES []
READ_ONLY_CHECK_COMPLETE_NO_PROGRAM_EXECUTED
NO_CONTROL_PUBLISHERS_AFTER_UPLOAD
UPLOAD_ONLY_COMPLETE_NO_BASE_START_NO_MOTION
```

上传前控制发布者也为空。首次核对因 StopWindow 路径假设错误中止；第二次因检查器把远程 shell 的命令文本误匹配为底盘程序中止。两次均发生在传输前，没有启动候选。修正为实际源码位置和独立 argv 文件名匹配后，第三次完成上传并通过校验。

## 执行位置、完整离线命令与下载文件

离线检查在 Ubuntu 终端执行，使用已经复制到 `/tmp` 的文件；以下命令是本次已执行记录，输出文件已经存在，再次核对须给不同输出文件名：

```bash
python2 -m py_compile /tmp/medical_ground_straight_pulse_v3_20261011.py
python2 /tmp/review_ground_pulse_v3_offline_20261011.py \
  --source /tmp/medical_ground_straight_pulse_v3_20261011.py \
  --previous /tmp/medical_ground_straight_pulse_v2_20261011.py \
  --scans /tmp/ground-scan-inspection-for-v3-20261011.json \
  --output /home/ncut/medical_localization_assets_20261011/ground-pulse-v3-offline-review-20261011.json
```

预期 `OFFLINE_REVIEW_PASSED`；保存扫描为 `REFUSED_UNCHANGED_PROTECTION`，`live_motion_readiness` 为 `NOT_CHECKED_NO_MOTION_AUTHORIZATION`。

本次上传在 Ubuntu 执行 `bash /tmp/vm_upload_only_ground_pulse_v3_20261011.sh`，已成功完成；该脚本只检查、传输、校验，不调用候选入口。上传 helper 拒绝覆盖目标文件，勿把重跑此脚本当作启动方法。

若只复核当前文件和停止状态，可在 Ubuntu 执行：

```bash
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /tmp/robot_verify_staged_files_20261011.sh
```

预期 `STAGED_FILES_SHA256_MATCH`、`SERIAL_OWNERS []`、`STAGED_OR_BASE_PROCESSES []`。

已下载到 Windows `D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`：

- `upload-only-ground-v3-final.log`：完整传输与前后只读检查结果。
- `ground-pulse-v3-offline-review.json`：离线审查报告。
- `ground-pulse-v3-offline-final.log`：Ubuntu 离线输出。
- 失败尝试日志保留，没有覆盖或删除。

仓库 `docs/evidence/program-staging-20261011/` 保存最终上传日志和离线报告副本。

## 后续断点

保持底盘停止，等待用户告知场地空闲。恢复静止定位前重新确认小车位置和方向；运动前重新核对实时雷达、停车状态和现场观察条件，并提前说明动作。没有安排延时启动，也没有取得当前地面运动授权。整圈路线仍需地面位移、转向与净距验证。
