# 落地静止定位恢复（2026-10-11）

## 现场与执行范围

用户确认已经落地，前方约 1 m；随后确认仍在识别板一旁起点黑线、车头朝右、车头在线、充电器已拔掉。只执行静止定位，未运行架空脉冲程序，未发送导航目标或正速度。

全部连接、文件上传和车端操作经 VMware Ubuntu 与现有 SSH helper 完成。原驱动、地图、JSON、lock 和原日志保留。

## 两个软件问题与时间对齐

1. 初版候选的持续控制发布者检查会把自己的 `Twist` 反馈误认为行驶输入。v2 仅豁免独立反馈话题与精确的自身节点组合；其他 Twist/Ackermann 发布者、导航目标和 `/odom` 冲突仍拒绝。
2. 首次启动在雷达新鲜度检查处拒绝，时间差约 -0.094 s，串口未打开。旧车端时钟同步工具因 ROS 正在运行拒绝修改，车端时间未改。随后使用只读 UDP 时间服务测量，将 **Ubuntu VM 时钟向前调整约 0.248057 s**；9 次核验最大差约 0.002165 s。没有放宽数据新鲜度范围。第一版 UDP 测量有服务启动时序问题；原拒绝报告和锁保留，第二版等待服务启动后才测量。

车端时钟服务只读取时间、35 秒自动结束。VM 调整工具拒绝向后或大于 0.5 秒的修改，要求稳定且低延迟的样本。仓库脚本使用已有 sudo 缓存；不包含连接密码。

## v2 实际拒绝与最小修补

v2 约运行 23 秒，949 帧原始线速度均为零，1110 个发送帧通过零速/查询白名单回放；用户确认实车没有移动、无异常。一条角速度约 0.009948 rad/s 超过原 0.002 门限，新候选的“停车窗口失效就立即关闭”逻辑退出；随后定位采集无法取得最后停车窗口，状态 `INCOMPLETE`，不能算通过。原数据和超限帧保留。

v3 只调整 **零速观测的等待流程**：角速度超限仍重置原 StopWindow，记录失效并继续发送零速；重新连续满足原 4 秒、至少 100 帧、0.002 门限、最大间隔 0.2 秒后才恢复静止状态。不新增非零发送入口，不过滤超限帧。线速度超限、反馈过期、控制发布者和里程计发布者冲突仍退出。结束前另要求一个严格停车窗口，并显式记录异常退出原因。

原 StopWindow SHA 保持 `15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43`。候选 v3 SHA：`aa06ade75f042131310bf2bad910070728472d68c486ebd3592e206a31b6384d`。

## 重新定位采集结果

使用新路径运行一次 v3，重新定位脚本只发布 `/initialpose` 并调用无运动定位更新。记录状态 `REINITIALIZED_NO_MOTION`，收到 13 条 AMCL 消息，初始和末端严格停车窗口通过。

采集时后轴参考点约 `x=-0.148631 m，y=-0.026544 m，yaw=-0.375°`，网页位姿年龄约 0.0274 秒、雷达坐标亦新鲜。轴向标准差约 0.0879/0.0587 m，航向标准差约 4.43°。用户确认网页位置/方向与实车一致，驱动轮和车体未动、无异常。

仍不能把近种子结果或该不确定度当作整圈导航验收。原地面实测与里程计比例差异、转向半径和停车距离尚未标定；非预期运动根因尚未证实。

完整限时观测已结束，退出码 0，串口 owner 为空。审计回放 7098 个发送帧均符合零速/查询白名单，5995 帧原始线速度全部为 0，无发送策略错误、CRC 拒绝或解析溢出。记录了 4 次静止窗口失效及重新等待，原始角速度最大约 0.010297 rad/s；全部保留，未声称全过程都满足停车门限。硬件结束前最终窗口为 202 帧、4.013495 秒；定位采集自身前后窗口分别为 200 帧/4.003055 秒、202 帧/4.021351 秒，采集中的一次时序重置也保留。

离线分析状态仍写 `…AWAITING_PHYSICAL_OBSERVATION`，因为分析器只读原始记录，不读取聊天。用户现场确认另存 `zero-only-site-physical-observation-20261011.json`，不修改 audit 或分析结论。

## Ubuntu 离线与执行命令

执行位置：VMware Ubuntu 终端。离线命令已通过，不打开串口：

```bash
python2 -m py_compile /tmp/medical_stationary_localization_v3_20261011.py
python2 /tmp/medical_stationary_localization_v3_20261011.py
python2 /tmp/medical_stationary_localization_v3_20261011.py --offline-check
sha256sum /tmp/medical_stationary_localization_v3_20261011.py
```

预期：`PREPARED_ONLY`、12 项 `OFFLINE_POLICY_CHECK_PASSED`，SHA 与上述一致。

以下是本次已经执行的脚本，使用过的 audit/JSON/lock 不允许覆盖或删除后重跑：

```bash
bash /tmp/vm_prepare_stationary_localization_v3_20261011.sh
bash /tmp/vm_execute_stationary_localization_v3_20261011.sh
```

实际车端零速命令如下，经 Ubuntu helper 执行；120 秒是整个零速观测期限，没有行驶窗口：

```bash
source /home/EPRobot/medical_robot_env.sh
timeout --signal=INT --kill-after=5s 135s \
  python2 /home/EPRobot/medical_stationary_localization_v3_20261011.py \
  --execute-stationary --vehicle-stationary-confirmed --power-stop-confirmed \
  --duration 120 \
  --audit /home/EPRobot/medical-stationary-localization-v3-audit-20261011.jsonl \
  >/home/EPRobot/medical-stationary-localization-v3-run-20261011.log 2>&1
```

候选期限结束关闭串口，网页 TF 随后会过期；本程序不能持续驱动导航。成功重新定位并不代表关闭后还能用旧网页位置发车。

## 下载证据

Windows：`D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`；Ubuntu 副本：`/home/ncut/medical_localization_assets_20261011/`；车端审计原件：`/home/EPRobot/`。

- `stationary-localization-prepare-v2/v3.log`、首次时间检查拒绝日志。
- `vm-small-forward-clock-v2-20261011.json`、原锁、时钟核验日志；先前拒绝记录保留。
- v2/v3 原始 `medical-stationary-localization-…-audit-20261011.jsonl`、锁和驱动日志。
- `zero-only-site-reinitialized-20261011.json`（失败）与 `zero-only-site-reinitialized-v3-20261011.json`（新采集），对应锁保留。
- `zero-only-site-live-v3-20261011.json`、执行日志和只读分析报告。
- `stationary-localization-v3-review.json`、`zero-only-site-physical-observation-20261011.json`。

Ubuntu 下载示例（本次执行脚本已经完成，既有副本不能覆盖）：

```bash
python2 /home/ncut/vm_connection_check_20261009.py --download \
  /home/EPRobot/medical-stationary-localization-v3-audit-20261011.jsonl \
  /home/ncut/medical_localization_assets_20261011/medical-stationary-localization-v3-audit-20261011.jsonl
```

下一阶段是另行准备地面适用的最短直行候选，明确运动预告后量同一固定点的实际位移并验证停车。当前不发送该动作，不启动整圈。
