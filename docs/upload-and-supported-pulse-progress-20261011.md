# 上传对照与架空受控短脉冲：阶段结果

## 当前结论与断点

已完成运行中的纯文本上传对照，随后按用户要求结束反复上传排查，接续一次受控架空前转短脉冲及用户要求的重复观测。**第二次短脉冲现场确认“两侧一起前转并停住，无异常”**；发令前后均取得原连续4秒严格静止反馈窗口。候选已退出，串口无人占用，原底盘未重启，无导航目标。

不宣称原先约15cm额外实车运动的触发者已查明。用户本轮要求推进，本阶段保存异常记录、不继续反复上传测试。下一阶段为场地摆放、重新定位、最短地面闭环验证；仍未标定实际距离、停止余量和转向半径，不能直接自动绕场。

## 上传对照

时间为北京时间。用已核对SHA的零速候选，Boost查询和零速帧保持原参数，不发送主机信息帧；上传内容为纯文本、从未执行。

| 轮次 | 时间 | 上传 | RX里程帧 | 结果 |
| --- | --- | --- | ---: | --- |
| 4 | 13:54:21–13:54:52 | 启动窗口检查拒绝，没有复制 | 1492 | vx全部0；不能算上传对照 |
| 5 | 13:56:13–13:56:43 | 两份68800字节文本成功，覆盖运行第3.06–14.13秒的标记窗口 | 1493 | 全部vx=0，用户要求重复，未确认现场 |
| 6 | 13:58:33–13:58:54 | 两份68800字节文本成功，覆盖运行第3.15–14.22秒的标记窗口 | 994 | 约20.77秒提前退出；用户确认轮子没转没抖、未碰车或支架 |

第4次的拒绝日志和audit原样保留。启动同步修补为等audit进入原指定3–20秒窗口，不更改停车门限、反馈新鲜度或诊断时长。第5/6次确认复制发生在候选运行中，两个文件大小与SHA一致；窗口包含SSH开销，不是SCP精确传输耗时。

第6次复制窗口内553帧线速度全部为0。复制完成约5.84秒后出现**一帧**CRC有效 `vx=-0.003 m/s`，原门限为0.002，诊断退出。audit中的10条 `ZERO_ONLY_FEEDBACK_FAULT` 是监控重复读取同一帧，不是10次独立非零反馈。原始角速度最大约0.52883 rad/s，不能称为只有编码器小噪声，也不能据此声称实车确实转动。用户现场否认轮子运动与接触，记录与实车存在差异；没有归因于用户操作，没有过滤掉此帧或放宽门限。

第6次全部TX帧仍为零速或查询，没有串口写失败、CRC拒绝字节或RX溢出；退出后串口owner为空。`UPLOAD_WINDOW_OVERLAP_CONFIRMED`只代表上传与运行时间重合，不代表本轮保护通过。

## 参考源码研究范围

下面基于本地20210520参考源码，尚未确认车上固件一致；未刷固件或更改硬件。

- `bottom_uart.c:133`选择速度case后，若中断将共享buffer换成Boost查询帧，第4/5字节`02 00`会按速度解释为0.512m/s。`illustrate_shared_rx_buffer_hazard.py`只演示这一人为安排的交错，**不是实际MCU执行轨迹**，不能据此宣称找到根因。
- `bottom_encode.c:130`编码器ISR把“不是期望正向下一态”的情况全部减计数，没有单独拒绝同态或非法跳变。参考参数20ms、1560脉冲/转、轮径0.062m及整数RPM量化下，两轮各一个反向计数可输出约-0.003m/s；只是数量级示例，未获取左右轮原始计数，不证明本次发生编码器毛刺。
- `bottom_mpu6050.c:252`读取14字节时没有检查I2C返回值，后续继续使用全局缓冲；串口CRC只能验证传输帧，不能验证传感器测量真实。尚无车端I2C错误记录，不证明角速度峰值由此触发。

上述风险保留给后续硬件维护。遵照用户最新要求，本轮转到受控动作，不继续开展原因对照。

## 独立架空短脉冲候选

`tools/localization/medical_supported_wheel_pulse_20261011.py`继承已核对SHA的原驱动，保留串口收发审计、禁用电池/主机信息帧、发送间隔与零速看门狗，原驱动不覆盖。默认不导入ROS、不打开串口；须 `--execute-wheel-pulse --wheels-supported --power-stop-confirmed` 才执行。

非零帧只允许程序内部PULSE阶段的精确+0.10m/s、零转向，最多0.30秒发送窗口；过期后拒绝，外部ROS非零命令拒绝。等待发送间隔后再次检查截止时间。发令前后都复用原 `StopWindow`，4秒、至少100帧、速度门限0.002、最大gap0.2，不改停车门限。数据按单调接收时刻检查，协议本身没有MCU时间戳/序号；仍只能证明反馈连续，不代替现场观察。

运动响应阶段允许合理的非零反馈，超过0.20m/s会中止；这是运动响应上限，不是停车门限。异常退出仍发送零速、关闭串口。命令发布窗口不等于实车停止时间；没有以速度×窗口估算地面距离。

候选SHA为 `7870c57e4865f5cd04f826f257a6c4d79d0abdddef4ecbb230ff27ad02ca7c0f`。原驱动SHA仍为 `d671e564242b9058d2ab4fc6fd7d2b64dfa5406c49618e1715fba176f77efce1`，StopWindow源码SHA为 `15fe40895e854575cc8fcfd041535dee3ef8aea09a070ee3fc965e6baab60c43`。全部身份核对通过。

| 架空短脉冲 | 正速TX帧 | 首末正速跨度 | 首正速至零速记录 | 最大原始vx | 基线/末端静止样本 | 现场 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 第1次 | 5 | 0.24074s | 0.30064s | 0.126m/s | 202/202，各约4.02s | 未确认，用户要求重做 |
| 第2次 | 5 | 0.23558s | 0.29605s | 0.123m/s | 202/201，各约4.01/4.00s | 两侧一起前转并停住，无异常 |

两次无TX策略错误、写失败或诊断fault，RX解析无拒绝或溢出，执行退出码均为0，最终串口owner为空。第2次不能当第1次现场证明。受控动作中的非零反馈及停车窗口reset正常保留，停车等待直到连续4秒满足原条件；不把停发时刻当作实际停车。

## 完整离线命令与执行位置

执行位置：**VMware Ubuntu终端**。候选检查、SSH执行、下载均从Ubuntu完成。

```bash
# 不连接ROS/串口的语法与策略检查，已执行。
python2 -m py_compile /tmp/medical_supported_wheel_pulse_20261011.py
python2 /tmp/medical_supported_wheel_pulse_20261011.py
python2 /tmp/medical_supported_wheel_pulse_20261011.py --offline-check
# 预期：PREPARED_ONLY；零速策略12项通过，正速阶段策略9项通过。

# 只读车端检查，已执行。
python2 /home/ncut/vm_connection_check_20261009.py \
  --command-file /tmp/robot_zero_bench_preflight_20261011.sh
# 预期：BENCH_PREFLIGHT_PASSED，串口owner空、原SHA一致。

# 本轮第二次完整短脉冲执行及下载脚本；已经运行结束。
# 一次性报告/锁保留，不要删除锁后重复运行。
bash /tmp/vm_execute_supported_pulse_run2_20261011.sh
# 实际：SUPPORTED_PULSE_EXIT=0，POST_SUPPORTED_PULSE_SERIAL_OWNERS []。
```

第二次脚本通过Ubuntu SSH执行的硬件命令如下（已执行，不再次运行）：

```bash
source /home/EPRobot/medical_robot_env.sh
timeout --signal=INT --kill-after=5s 40s \
  python2 /home/EPRobot/medical_supported_wheel_pulse_20261011.py \
  --execute-wheel-pulse --wheels-supported --power-stop-confirmed --duration 30 \
  --audit /home/EPRobot/medical-supported-wheel-pulse-audit2-20261011.jsonl \
  >/home/EPRobot/medical-supported-wheel-pulse-run2-20261011.log 2>&1
```

`--duration 30`是整阶段上限，包含基线与收尾，不是连续行驶30秒；正速窗口固定0.30秒。

## 下载证据与下一步

Windows目录：`D:/BaiduNetdiskDownload/F1/medical-localization-20261011/`。Ubuntu下载副本为 `/home/ncut/medical_localization_assets_20261011/`，车端原证据在 `/home/EPRobot/`，均保留。

- `zero-bench-upload-load-run4/5/6.log`，相应 `medical-zero-bench-run4/5/6-20261011.log`。
- `medical-zero-bench-audit4/5/6-20261011.jsonl`与原lock；`zero-bench-audit4/5/6-review.json`。
- 第5/6次 `medical-zero-bench-upload-window5/6-20261011.json`、`medical-zero-bench-upload-completed5/6-20261011.json`及 `zero-upload-load5/6-review.json`。第4次未生成复制标记，不伪造。
- `supported-pulse-offline.log`，`supported-pulse-execute.log`与`supported-pulse-execute-run2.log`。
- 两份 `medical-supported-wheel-pulse-audit[-或2-]20261011.jsonl`、原lock、两份run日志、`supported-wheel-pulse-review.json`、`supported-wheel-pulse2-review.json`。
- `upload-and-pulse-physical-observation.json`单独保存用户现场观察，不覆盖任何原audit/报告。

下载第二次短脉冲audit的完整Ubuntu命令（已执行，不覆盖既有副本）：

```bash
python2 /home/ncut/vm_connection_check_20261009.py --download \
  /home/EPRobot/medical-supported-wheel-pulse-audit2-20261011.jsonl \
  /home/ncut/medical_localization_assets_20261011/medical-supported-wheel-pulse-audit2-20261011.jsonl
```

本地分析工具为 `analyze_zero_upload_load.py` 与 `analyze_supported_wheel_pulse.py`，仅读取下载文件、输出新报告，不接触ROS/串口。根因未证实这一事实与小幅异常继续保留；用户不要求本轮继续研究。

下一步需将车放回实际场地并明确位置、朝向、前方余量。只读定位先恢复；地面驱动必须采用对应的受控版本，不能直接将仅供架空的脉冲脚本当导航驱动。取得现场短距测量和停止响应后再做转向标定、短段闭环与整圈路线。
