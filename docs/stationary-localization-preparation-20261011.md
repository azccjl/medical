# 架空验证后的静止定位准备

## 当前结果

用户确认第二次架空脉冲“两侧一起前转并停住，无异常”。此前审计与严格停车结果见 `upload-and-supported-pulse-progress-20261011.md`；不重复运动。

本次仅从 VMware Ubuntu 经 SSH 作只读检查。小车时间为北京时间 2026-10-11 14:21:25，串口无人占用，原驱动 SHA 一致，无 Twist/Ackermann 控制发布者。雷达、AMCL、地图服务和网页节点还在。网页返回“定位或传感器数据已过期”，不能使用旧箭头安排自主行驶。

用户回复“好的”表示愿意准备，尚未提供已经落地、车头方向、前方余量与观察条件；没有据此启动底盘或发送速度。

## 新增候选与实际部署范围

`tools/localization/medical_stationary_localization_20261011.py` 从已核对的零速诊断版本派生，恢复 `/odom` 和 `odom -> base_footprint` TF，以便后续静止定位。IMU 与反馈保持独立话题；不启动 move_base、不接导航速度，不含正速或转向发送路径。

- 默认调用不导入 ROS、不打开串口。复制文件不执行。
- 运行需要三个显式标志：`--execute-stationary --vehicle-stationary-confirmed --power-stop-confirmed`，并指定全新 audit 路径。
- 沿用零速串口帧白名单、收发审计、发送间隔、0.35 秒命令看门狗、原驱动 SHA 校验；禁用电池和主机信息查询。
- 启动拒绝现存串口 owner、控制发布者及 `/odom` 发布者；运行期间继续检查控制发布者。
- 沿用原 SHA 的 StopWindow，接收时间检查方式、停车门限、最小样本数与间隔规则保持不变。首次窗口通过才记录 `STRICT_STATIONARY_LOCALIZATION_READY`；之后窗口失效即退出并零速收尾。
- 默认整体期限 120 秒，允许 30–120 秒；期限结束关闭串口。不是持续导航驱动，退出后定位输入会再次过期。

候选最终 SHA256：`0ca0235c6fa1d96c1e6b9e6d22b717c403956cd646c2ff3fdf081600046da217`。

**实际仅复制到 Ubuntu `/tmp/`，没有上传到小车，没有使用执行标志。** Ubuntu Python2 语法检查、默认调用及原有 12 项零速策略检查通过；尚未验证实际 odom/TF、定位和地面表现。主机零速限制不等于固件根因已经修复。

## 完整离线命令

执行位置：VMware Ubuntu 终端。以下已执行，不接触小车串口：

```bash
python2 -m py_compile /tmp/medical_stationary_localization_20261011.py
python2 /tmp/medical_stationary_localization_20261011.py
python2 /tmp/medical_stationary_localization_20261011.py --offline-check
sha256sum /tmp/medical_stationary_localization_20261011.py
```

预期：`PREPARED_ONLY`、`OFFLINE_POLICY_CHECK_PASSED`、`cases: 12`、`serial_opened: false`，SHA 与上述一致。完整批处理为 `bash /tmp/vm_check_stationary_localization_20261011.sh`。

本次只读车端检查命令如下，不启动底盘：

```bash
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /tmp/robot_zero_bench_preflight_20261011.sh
curl --fail --max-time 5 -s http://127.0.0.1:8080/api/state
```

预期：`BENCH_PREFLIGHT_PASSED`、`serial_owners: []`；网页状态必须如实反映过期。现有 preflight 只证明底盘与控制入口当前停止，不是定位验收。

## 下载与接续

Windows 已下载到 `D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`：

- `next-stage-readonly.log`：ROS 节点、串口 owner、原驱动 SHA、网页完整状态。
- `stationary-localization-offline.log`：首版离线结果，保留。
- `stationary-localization-offline-v2.log`：最终候选离线结果与 SHA。

本阶段没有新的车端 audit 或运动报告，不伪造执行记录。原 JSON、lock、地图和日志全部保留。

下一步等待用户确认落地后的具体位置、车头朝向、前方空旷距离和观察/断电条件。先上传但不执行候选，核对源文件及 SHA，再预告雷达和转向回中表现，运行有限时静止定位；摆放改变后重置 AMCL，检查实车与网页参考点。后续地面短距程序须另行准备与预告，不能直接使用架空脉冲程序或本零速候选导航。
