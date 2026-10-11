# 架空零速诊断结果与下一断点

## 本轮结果

用户确认已稳固架空后授权观测，随后两次要求重做，实际执行三次独立 30 秒零速诊断。**第三次用户确认“全程没转、没抖，无异常”**，与串口反馈一致。第一次和第二次没有取得现场确认，不能把第三次观察补写到前两次。

三次退出均为0，退出后串口 owner 为空，原 `/base_control` 未重启。保留雷达、地图与AMCL节点；网页位姿缺少有效里程计/TF，仍不用于导航。未发送正速、倒车、转弯或导航目标，未修改固件、里程计比例、停车门限与地图。

## 数据核对

时间为北京时间，含初始化和收尾的实际时长约30.2秒，查询/速度数量以 audit 的 TX_BEGIN 计数。

| 次数 | 起止 | RX有效里程帧 | 查询 TX_BEGIN | 零速 TX_BEGIN | max abs(vx) | max原始abs(wz) | 现场结果 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 13:40:46–13:41:16 | 1493 | 1494 | 265 | 0 m/s | 0.00960 rad/s | 未确认，用户要求重做 |
| 2 | 13:45:27–13:45:57 | 1494 | 1494 | 265 | 0 m/s | 0.01082 rad/s | 未确认，用户要求重做 |
| 3 | 13:48:10–13:48:40 | 1493 | 1493 | 266 | 0 m/s | 0.01169 rad/s | 全程没转、没抖，无异常 |

离线重放全部发送帧的长度、CRC、类型、速度/转向、PID与保留字节白名单；重放RX数据的CRC解析。三次RX均无拒绝字节、溢出或尾部未完整帧。第2/3次没有发送失败或诊断fault；反馈线速度全为零。原始角速度仍有稀疏非零值，本轮没有放宽门限，也不将其解读为肉眼观察到的车体旋转。

第1次收尾有一条查询在等待发送间隔时撞上关闭流程。原驱动返回False、没有实际serial.write；audit却已经写了TX_BEGIN，所以原离线结果保守标为 `DIAGNOSTIC_REQUIRES_REVIEW`。该原始结果与audit保留。第2次前修补为等待间隔后重新检查关闭状态、记录 `TX_CANCELLED_SHUTDOWN`，与真正写失败区分；本轮第2/3次未触发这类取消。没有忽略串口错误或修改运动保护。

启动前另修补了Python2旧式类兼容：`BaseControl`没有继承object，不能用super调用；候选显式调用原基类方法。此修补发生在第一次硬件运行之前。运行默认仍不导入ROS、不打开串口。

## 候选与结论的范围

原驱动SHA仍为 `d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1`，未覆盖。

- 首次车端候选 `/home/EPRobot/medical_serial_zero_diagnostic_20261011.py` SHA：`be5a619f02cda4a3643a73347a26696edc0e10ce2237cb21147b7323d8819e34`。
- 第2/3次候选 `/home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py` SHA：`b04c466479d72139c02ec27561c81d9f254da5fa75072ac357bca21aa41b4c0f`。
- 最新本地源码为 `tools/localization/medical_serial_zero_diagnostic_20261011.py`，对应第2/3次内容。首次车端文件和日志保留。

本候选禁用了电池/主机信息帧，串口发送增加帧间隔，且只允许零速/零转向。这证明**此候选在本次架空30秒观测中未见驱动轮异常**，不证明究竟是 `0x21`、共享缓冲区、PID、编码器或其他因素引发原问题。没有在运行中的候选上进行专门上传/SSH负载对照；第三次复用已有候选，没有再次向小车上传程序。

仍未解决：原意外运动的确切触发者、实测15cm与odom约4.2cm的差异、转向半径标定和自主路线余量。暂不在地面执行整圈，也不把这份只允许零速的诊断程序作为导航驱动。

## 完整执行命令与输出

执行位置：**VMware Ubuntu终端**。三轮已执行完毕；下列脚本包含一次性输出/lock保护，重复执行会拒绝旧输出，不能删除lock重试。

```bash
# 启动前只读检查，Python2离线白名单检查。
python2 -m py_compile /tmp/medical_serial_zero_diagnostic_v2_20261011.py
python2 /tmp/medical_serial_zero_diagnostic_v2_20261011.py --offline-check
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /tmp/robot_zero_bench_preflight_20261011.sh

# 本轮第三次完整执行脚本：只在已获现场架空准备时执行。
# 当前已经执行结束，不要重复运行。
bash /tmp/vm_execute_zero_bench_run3_20261011.sh
```

预期且本轮实际取得：离线 `OFFLINE_POLICY_CHECK_PASSED` cases=12；启动前 `BENCH_PREFLIGHT_PASSED`、串口owner空、SHA一致；结束 `ZERO_BENCH_EXIT=0`、`POST_BENCH_SERIAL_OWNERS []`、`VM_ZERO_BENCH_EXIT=0`。全过程无ROS行驶命令发布者。运行脚本和SSH命令文件均保存在仓库 `tools/localization/`。

已在Ubuntu执行的第三次SSH内容中，实际硬件命令如下（仅作本次审计说明，不再次执行）：

```bash
source /home/EPRobot/medical_robot_env.sh
timeout --signal=INT --kill-after=5s 40s \
  python2 /home/EPRobot/medical_serial_zero_diagnostic_v2_20261011.py \
  --execute-bench --wheels-supported --power-stop-confirmed --duration 30 \
  --audit /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl \
  >/home/EPRobot/medical-zero-bench-run3-20261011.log 2>&1
```

## 下载文件与复查

Windows目录：`D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`。

- `zero-bench-preflight.log`，三版 `zero-bench-execute*.log`。
- `medical-zero-bench-run-20261011.log`、`medical-zero-bench-run2-20261011.log`、`medical-zero-bench-run3-20261011.log`。
- `medical-zero-bench-audit-20261011.jsonl`、`medical-zero-bench-audit2-20261011.jsonl`、`medical-zero-bench-audit3-20261011.jsonl`，及各自原 `.lock`。
- `zero-bench-audit-review.json`、`zero-bench-audit2-review.json`、`zero-bench-audit3-review.json`。
- `zero-bench-physical-observation.json`：用户观察单独记录，不覆盖原始audit/分析JSON。

Ubuntu副本在 `/home/ncut/medical_localization_assets_20261011/`，车端原文件在 `/home/EPRobot/`。完整离线下载命令（第三次已执行，目标为既有文件时不要重复覆盖）：

```bash
python2 /home/ncut/vm_connection_check_20261009.py --download \
  /home/EPRobot/medical-zero-bench-run3-20261011.log \
  /home/ncut/medical_localization_assets_20261011/medical-zero-bench-run3-20261011.log
python2 /home/ncut/vm_connection_check_20261009.py --download \
  /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl \
  /home/ncut/medical_localization_assets_20261011/medical-zero-bench-audit3-20261011.jsonl
python2 /home/ncut/vm_connection_check_20261009.py --download \
  /home/EPRobot/medical-zero-bench-audit3-20261011.jsonl.lock \
  /home/ncut/medical_localization_assets_20261011/medical-zero-bench-audit3-20261011.jsonl.lock
```

本地可用 `tools/localization/analyze_zero_bench_audit.py` 对已下载audit重放，输出必须为新的路径。原audit SHA在各份review JSON中，仓库仅同步代码和交接说明，不包含连接凭据。

## 接续阶段

下一阶段优先在相同架空、零速条件下增加受控SSH/文件复制负载，记录TX/RX和现场反应，区分“静止时无异常”和“上传时无异常”。确认后再决定运行驱动的最小修补；不直接启用地面运动或刷固件。当前断点：**第三次架空零速现场与反馈一致；候选已退出，原底盘保持停止，尚未开展负载对照。**
