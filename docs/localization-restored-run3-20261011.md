# 起点静止定位恢复（2026-10-11）

## 结果与当前状态

用户确认小车在起点，朝右、车头在线，拔掉充电器且停稳。本阶段只运行既有 v3 零速候选，没有执行短距脉冲或导航。run3 成功重设 AMCL 初始位置并通过采集、收尾审查；用户确认网页位置方向与实车一致，驱动轮和车体无异常。

这是 **120 秒限时静止观测**。运行期间定位实时更新；期限结束程序退出、串口关闭，网页随后显示定位过期，不能依据旧位姿直接发车。显示地图为整理图，AMCL 仍用原始扫描图，没有替换定位地图。

## 两轮记录与最小修改

run2 线速度全零，但角速度偶发超限；Ubuntu 接收里程计也出现间断或非单调时间戳。30 秒采集等待内未获得严格窗口，未重设定位。车端曾六次就绪，但到期未就绪，因此退出 1；错误 `STRICT_STATIONARY_WINDOW_NEVER_READY` 在该路径表示到期未就绪，不能解释成全程从未就绪。用户确认实车没有移动，此轮记录保留为未通过。

run3 的独立采集器 `reinitialize_zero_only_site_v2_20261011.py` 把 `/odom` 订阅改为 `queue_size=1, tcp_nodelay=True`，减少排队；初始窗口等待上限从 30 增至 60 秒。所有接收到的间断和超限仍重置窗口。StopWindow 门限 0.002、至少 100 帧、连续 4 秒、最大间断 0.2 秒均不变。车端程序和底盘发送策略未改。

此轮通过不代表角速度毛刺或传输间断已根治：硬件仍记录三个就绪后窗口重置；采集收尾记录一次间断和两次非静止重置，随后取得合格窗口。原始角速度最大绝对值约 0.010821 rad/s，不能称全程满足静止门限。

## run3 核对数据

| 项目 | 结果 |
| --- | --- |
| 原始里程计 | 5994 帧，线速度全部 0 |
| 发送帧 | 7095 帧，回放全部符合零速/查询策略 |
| 解析拒绝/溢出 | 0 / 0 |
| 硬件退出 | 0，最终串口无人占用 |
| 硬件最终静止 | 202 帧 / 4.019131 秒，通过 |
| 定位采集基线 | 191 帧 / 4.022809 秒，通过 |
| 定位采集收尾 | 196 帧 / 4.016205 秒，通过 |
| AMCL 结果 | 12 条 |
| 后轴位姿 | x=-0.196558 m，y=-0.069702 m，yaw=+0.409° |
| x/y 标准差 | 0.12687 / 0.05789 m |
| 航向标准差 | 5.915° |

采集退出附近出现 `/initialpose` 临时订阅重连警告，保留原日志；重设后的 AMCL 时间戳、位置及新鲜 TF 已核对。用户“是的，可以移动了理论上”作为现场位置和无异常确认保留，没有据此在本轮发车。这是单次静止定位结果，不是移动导航精度验收。

## 执行位置、完整命令与预期结果

本轮 Ubuntu 中已执行：

```bash
bash /tmp/vm_execute_stationary_localization_v3_run3_20261011.sh
```

该脚本先核对程序、依赖、无控制发布者、新鲜扫描与新证据路径，随后执行零速候选。预期本轮日志 `REINITIALIZED_NO_MOTION`、`ZERO_ONLY_HARDWARE_EXIT=0`、`POST_STATIONARY_SERIAL_OWNERS []`、`STATIONARY_STAGE_DOWNLOAD_COMPLETE`。这是已执行记录，JSON 和锁现已存在，不重跑或删除它们。

仅复核停止状态，在 Ubuntu 执行（不启动硬件）：

```bash
bash /tmp/vm_restore_localization_postflight_run3_20261011.sh
cat /tmp/medical-localization-restore-postflight-run3-20261011.log
```

预期 `SERIAL_OWNERS []`、`STAGED_OR_BASE_PROCESSES []`、`CONTROL_AND_ODOM_PUBLISHERS_EMPTY`，以及已过期的定位提示。

Windows PowerShell 完全离线复核命令，新输出文件必须尚未存在：

```powershell
Set-Location -LiteralPath 'D:/BaiduNetdiskDownload/F1/medical'
& 'C:/Users/mine/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tools/localization/analyze_stationary_localization_20261011.py '../medical-localization-20261011/medical-stationary-localization-v3-run3-audit-20261011.jsonl' '../medical-localization-20261011/stationary-localization-execute-v3-run3.log' '../medical-localization-20261011/zero-only-site-reinitialized-v3-run3-20261011.json' '../medical-localization-20261011/stationary-localization-v3-run3-review-repeat.json'
```

预期 `ZERO_ONLY_LOCALIZATION_CAPTURE_PASSED_AWAITING_PHYSICAL_OBSERVATION`、硬件退出 `[0]`；现场确认独立保存在下述文件，没有修改原软件审查状态。

## 下载文件与断点

Windows `D:/BaiduNetdiskDownload/F1/medical-localization-20261011/` 已保存：

- run2/run3 原始车端日志、审计 JSONL、定位重设 JSON；原锁均保留。
- `stationary-localization-v3-run2-review.json`、`stationary-localization-v3-run3-review.json`。
- `localization-restore-preflight-run2.log`、`localization-restore-postflight-run3.log`。
- `localization-restore-physical-observation-20261011.json`、`localization-restored-run3.jpg`。

仓库 `docs/evidence/localization-restore-20261011/` 保存审查、现场确认和最终只读检查副本；完整原始日志留在下载目录。

后续运动前提前说明动作，重新恢复新鲜定位和扫描并确认现场路线空闲。地面位移、转向和路线车体净距仍需验证，不能直接用本次静止结果批准整圈自主巡航。
